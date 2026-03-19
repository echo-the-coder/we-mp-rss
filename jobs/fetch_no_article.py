import json
import os
import subprocess
import sys
import time

import core.db as db
from core.config import cfg
from core.models.article import Article, DATA_STATUS
from core.print import print_error, print_success, print_warning
from core.queue import TaskQueueManager
from core.task import TaskScheduler
from core.wait import Wait
from tools.fix import fix_html

DB = db.Db(tag="内容修正")

CONTENT_SYNC_META_KEY = "_content_sync"
FETCH_TIMEOUT_SECONDS = 120
STALE_FETCHING_MINUTES = 15
MAX_CONSECUTIVE_FAILURES = 3
FETCH_BATCH_SIZE = 10
FETCH_RESULT_PREFIX = "__WXARTICLE_RESULT__="
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _current_unix_seconds() -> int:
    return int(time.time())


def _current_unix_millis() -> int:
    return int(time.time() * 1000)


def _touch_article(article: Article) -> None:
    article.updated_at = _current_unix_seconds()
    article.updated_at_millis = _current_unix_millis()


def _parse_extinfo(raw_extinfo) -> dict:
    if isinstance(raw_extinfo, dict):
        return dict(raw_extinfo)
    if not raw_extinfo:
        return {}
    if isinstance(raw_extinfo, str):
        try:
            data = json.loads(raw_extinfo)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {"_legacy_raw_extinfo": raw_extinfo}
    return {}


def _save_extinfo(article: Article, payload: dict) -> None:
    article.extinfo = json.dumps(payload, ensure_ascii=False)


def _get_content_sync_meta(article: Article) -> dict:
    extinfo = _parse_extinfo(article.extinfo)
    meta = extinfo.get(CONTENT_SYNC_META_KEY, {})
    return meta if isinstance(meta, dict) else {}


def _set_content_sync_meta(article: Article, meta: dict | None) -> None:
    extinfo = _parse_extinfo(article.extinfo)
    if meta:
        extinfo[CONTENT_SYNC_META_KEY] = meta
    else:
        extinfo.pop(CONTENT_SYNC_META_KEY, None)
    _save_extinfo(article, extinfo)


def _clear_failure_meta(article: Article) -> None:
    _set_content_sync_meta(article, None)


def _register_failure(article: Article, reason: str) -> int:
    meta = _get_content_sync_meta(article)
    failure_count = int(meta.get("consecutive_failures", 0)) + 1
    _set_content_sync_meta(
        article,
        {
            "consecutive_failures": failure_count,
            "last_failure_reason": reason,
            "last_failure_at_millis": _current_unix_millis(),
        },
    )
    return failure_count


def _mark_retryable_failure(article: Article, reason: str) -> int:
    failure_count = _register_failure(article, reason)
    article.status = DATA_STATUS.DELETED if failure_count >= MAX_CONSECUTIVE_FAILURES else DATA_STATUS.ACTIVE
    _touch_article(article)
    return failure_count


def _mark_fetching(article: Article) -> None:
    article.status = DATA_STATUS.FETCHING
    _touch_article(article)


def _mark_deleted(article: Article, content: str | None = None) -> None:
    if content is not None:
        article.content = content
        article.content_html = fix_html(content)
    article.status = DATA_STATUS.DELETED
    _clear_failure_meta(article)
    _touch_article(article)


def _mark_success(article: Article, content: str) -> None:
    article.content = content
    article.content_html = fix_html(content)
    article.status = DATA_STATUS.ACTIVE
    _clear_failure_meta(article)
    _touch_article(article)


def _reclaim_stale_fetching_articles(session, stale_before_millis: int) -> int:
    stale_articles = (
        session.query(Article)
        .filter(
            _empty_content_filter(),
            Article.status == DATA_STATUS.FETCHING,
            Article.updated_at_millis < stale_before_millis,
        )
        .all()
    )

    reclaimed = 0
    for article in stale_articles:
        failure_count = _mark_retryable_failure(article, "stale-fetching-lock")
        reclaimed += 1
        if article.status == DATA_STATUS.DELETED:
            print_warning(f"文章连续失败达到阈值，已自动逻辑删除: {article.id}")
        else:
            print_warning(f"回收陈旧 FETCHING 锁: {article.id} (失败次数: {failure_count})")

    if reclaimed:
        session.commit()

    return reclaimed


def _empty_content_filter():
    from sqlalchemy import or_

    return or_(Article.content.is_(None), Article.content == "")


def _query_pending_articles(session, limit: int = FETCH_BATCH_SIZE):
    return (
        session.query(Article)
        .filter(
            _empty_content_filter(),
            Article.status != DATA_STATUS.FETCHING,
            Article.status != DATA_STATUS.DELETED,
        )
        .limit(limit)
        .all()
    )


def _build_fetch_subprocess_script() -> str:
    return """
import json
import sys

repo_root = sys.argv[1]
url = sys.argv[2]
mode = sys.argv[3]
sys.path.insert(0, repo_root)

payload = {"content": ""}
if mode == "web":
    from driver.wxarticle import WXArticleFetcher

    payload["content"] = WXArticleFetcher().get_article_content(url).get("content", "")
else:
    from core.wx.base import WxGather

    payload["content"] = WxGather().Model().content_extract(url)

print("__WXARTICLE_RESULT__=" + json.dumps(payload, ensure_ascii=False))
"""


def fetch_content_with_timeout(url: str, mode: str) -> tuple[str, str | None]:
    cmd = [
        sys.executable,
        "-c",
        _build_fetch_subprocess_script(),
        REPO_ROOT,
        url,
        mode,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=FETCH_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "timeout", None

    stdout_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    payload = None
    for line in reversed(stdout_lines):
        if line.startswith(FETCH_RESULT_PREFIX):
            payload = line[len(FETCH_RESULT_PREFIX) :]
            break

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"subprocess-exit-{result.returncode}"
        return f"subprocess-error:{message}", None

    if payload is None:
        return "missing-result-payload", None

    try:
        content = json.loads(payload).get("content")
    except json.JSONDecodeError:
        return "invalid-result-payload", None

    return "ok", content


def fetch_articles_without_content():
    """
    查询 content 为空的文章并补抓正文。
    自愈策略：
    - 排除已逻辑删除文章
    - 每轮开始前回收陈旧 FETCHING 锁
    - 单篇抓取超时后继续后续文章
    - 连续失败达到阈值后自动逻辑删除
    """
    session = DB.get_session()
    try:
        stale_before_millis = _current_unix_millis() - (STALE_FETCHING_MINUTES * 60 * 1000)
        reclaimed_count = _reclaim_stale_fetching_articles(session, stale_before_millis)
        if reclaimed_count:
            print_warning(f"回收陈旧 FETCHING 锁数量: {reclaimed_count}")

        articles = _query_pending_articles(session, FETCH_BATCH_SIZE)

        if not articles:
            print_warning("暂无需要获取内容的文章")
            return

        article_ids = []
        for article in articles:
            _mark_fetching(article)
            article_ids.append(article.id)
        session.commit()

        mode = cfg.get("gather.content_mode", "web")
        for article_id in article_ids:
            article = session.query(Article).filter(Article.id == article_id).first()
            if article is None or article.status == DATA_STATUS.DELETED:
                continue

            try:
                url = article.url or f"https://mp.weixin.qq.com/s/{article.id}"
                print(f"正在处理文章: {article.title}, URL: {url}")

                status, content = fetch_content_with_timeout(url, mode)
                if status == "timeout":
                    failure_count = _mark_retryable_failure(article, "timeout")
                    session.commit()
                    print_error(f"正文抓取超时，已回收锁: {article.id}")
                    if article.status == DATA_STATUS.DELETED:
                        print_warning(f"文章连续失败达到阈值，已自动逻辑删除: {article.id}")
                    else:
                        print_warning(f"文章 {article.title} 将在后续周期重试，当前失败次数: {failure_count}")
                    continue

                if status != "ok":
                    failure_count = _mark_retryable_failure(article, status)
                    session.commit()
                    print_error(f"处理文章 {article.title} 时发生错误: {status}")
                    if article.status == DATA_STATUS.DELETED:
                        print_warning(f"文章连续失败达到阈值，已自动逻辑删除: {article.id}")
                    continue

                if content == "DELETED":
                    print_error(f"获取文章 {article.title} 内容已被发布者删除")
                    _mark_deleted(article, content)
                    session.commit()
                    continue

                if content:
                    _mark_success(article, content)
                    session.commit()
                    print_success(f"成功更新文章 {article.title} 的内容")
                else:
                    failure_count = _mark_retryable_failure(article, "empty-content")
                    session.commit()
                    print_error(f"获取文章 {article.title} 内容失败")
                    if article.status == DATA_STATUS.DELETED:
                        print_warning(f"文章连续失败达到阈值，已自动逻辑删除: {article.id}")
                    else:
                        print_warning(f"文章 {article.title} 将在后续周期重试，当前失败次数: {failure_count}")

                Wait(min=5, max=10, tips=f"修正 {article.title}... 完成")
            except Exception as e:
                failure_count = _mark_retryable_failure(article, f"exception:{e}")
                session.commit()
                print_error(f"处理文章 {article.title} 时发生错误: {e}")
                if article.status == DATA_STATUS.DELETED:
                    print_warning(f"文章连续失败达到阈值，已自动逻辑删除: {article.id}")
                else:
                    print_warning(f"文章 {article.title} 将在后续周期重试，当前失败次数: {failure_count}")
    except Exception as e:
        session.rollback()
        print_error(f"处理过程中发生错误: {e}")
    finally:
        session.close()


scheduler = TaskScheduler()
task_queue = TaskQueueManager()
task_queue.run_task_background()


def start_sync_content():
    """
    根据配置自动启动文章内容同步任务。
    """
    if not cfg.get("gather.content_auto_check", False):
        print_warning("自动检查并同步文章内容功能未启用")
        return
    interval = int(cfg.get("gather.content_auto_interval", 10))
    cron_exp = f"*/{interval} * * * *"
    task_queue.clear_queue()
    scheduler.clear_all_jobs()

    def do_sync():
        task_queue.add_task(fetch_articles_without_content)

    job_id = scheduler.add_cron_job(do_sync, cron_expr=cron_exp)
    print_success(f"已添自动同步文章内容任务: {job_id}")
    scheduler.start()


if __name__ == "__main__":
    fetch_articles_without_content()
