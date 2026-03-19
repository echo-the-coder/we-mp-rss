import json
import importlib.util
import pathlib
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models.article import Article
from core.models.base import DATA_STATUS

MODULE_PATH = pathlib.Path(__file__).with_name("fetch_no_article.py")
MODULE_SPEC = importlib.util.spec_from_file_location("fetch_no_article_under_test", MODULE_PATH)
FETCH_NO_ARTICLE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(FETCH_NO_ARTICLE)

_mark_retryable_failure = FETCH_NO_ARTICLE._mark_retryable_failure
_mark_success = FETCH_NO_ARTICLE._mark_success
_query_pending_articles = FETCH_NO_ARTICLE._query_pending_articles
_reclaim_stale_fetching_articles = FETCH_NO_ARTICLE._reclaim_stale_fetching_articles


class TestFetchNoArticleSelfHeal(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Article.__table__.create(engine)
        self.Session = sessionmaker(bind=engine)
        self.session = self.Session()

    def tearDown(self):
        self.session.close()

    def _article(self, article_id: str, status: int = DATA_STATUS.ACTIVE, content=None, extinfo=None, updated_at_millis=0):
        article = Article(
            id=article_id,
            mp_id="MP_WXS_TEST",
            title=article_id,
            status=status,
            content=content,
            content_html=content,
            extinfo=json.dumps(extinfo, ensure_ascii=False) if isinstance(extinfo, dict) else extinfo,
            updated_at=0,
            updated_at_millis=updated_at_millis,
        )
        self.session.add(article)
        self.session.commit()
        return article

    def test_query_pending_articles_skips_deleted_and_fetching(self):
        self._article("active-empty", status=DATA_STATUS.ACTIVE, content="")
        self._article("deleted-empty", status=DATA_STATUS.DELETED, content="")
        self._article("fetching-empty", status=DATA_STATUS.FETCHING, content="")
        self._article("active-full", status=DATA_STATUS.ACTIVE, content="ok")

        articles = _query_pending_articles(self.session, limit=10)

        self.assertEqual([article.id for article in articles], ["active-empty"])

    def test_mark_retryable_failure_auto_deletes_after_threshold(self):
        article = self._article("retry-me", status=DATA_STATUS.ACTIVE, content="")

        count1 = _mark_retryable_failure(article, "timeout")
        count2 = _mark_retryable_failure(article, "timeout")
        count3 = _mark_retryable_failure(article, "timeout")

        self.assertEqual(count1, 1)
        self.assertEqual(count2, 2)
        self.assertEqual(count3, 3)
        self.assertEqual(article.status, DATA_STATUS.DELETED)

        meta = json.loads(article.extinfo)["_content_sync"]
        self.assertEqual(meta["consecutive_failures"], 3)
        self.assertEqual(meta["last_failure_reason"], "timeout")

    def test_mark_success_clears_failure_meta(self):
        article = self._article("success-me", status=DATA_STATUS.ACTIVE, content="")
        _mark_retryable_failure(article, "empty-content")

        _mark_success(article, "<p>done</p>")

        self.assertEqual(article.status, DATA_STATUS.ACTIVE)
        self.assertEqual(article.content, "<p>done</p>")
        self.assertNotIn("_content_sync", json.loads(article.extinfo))

    def test_reclaim_stale_fetching_articles_marks_deleted_after_three_failures(self):
        article = self._article(
            "stale-fetching",
            status=DATA_STATUS.FETCHING,
            content="",
            extinfo={"_content_sync": {"consecutive_failures": 2}},
            updated_at_millis=1,
        )

        reclaimed = _reclaim_stale_fetching_articles(self.session, stale_before_millis=10)

        self.assertEqual(reclaimed, 1)
        self.session.refresh(article)
        self.assertEqual(article.status, DATA_STATUS.DELETED)


if __name__ == "__main__":
    unittest.main()
