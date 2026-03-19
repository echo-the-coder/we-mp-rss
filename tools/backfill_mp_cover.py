#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


API_BASE_URL = os.getenv("WERSS_API_BASE_URL", "http://127.0.0.1:8001/api/v1/wx")
WEWE_RSS_BASE_URL = os.getenv("WEWE_RSS_BASE_URL", "http://127.0.0.1:4000")
USERNAME = os.getenv("WERSS_USERNAME")
PASSWORD = os.getenv("WERSS_PASSWORD")


def http_json(url: str, method: str = "GET", headers: dict | None = None, data: bytes | None = None) -> dict:
    request = urllib.request.Request(url=url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def login() -> str:
    if not USERNAME or not PASSWORD:
        raise RuntimeError("请通过环境变量 WERSS_USERNAME / WERSS_PASSWORD 提供登录账号")

    payload = urllib.parse.urlencode({"username": USERNAME, "password": PASSWORD}).encode("utf-8")
    response = http_json(
        f"{API_BASE_URL}/auth/login",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=payload,
    )
    return response["data"]["access_token"]


def fetch_missing_feeds(token: str) -> list[dict]:
    response = http_json(
        f"{API_BASE_URL}/mps?limit=100&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    feeds = response["data"]["list"]
    return [feed for feed in feeds if not (feed.get("mp_cover") or "").strip()]


def fetch_feed_logo(feed_id: str) -> str:
    feed_url = f"{WEWE_RSS_BASE_URL.rstrip('/')}/feeds/{feed_id}.atom"
    with urllib.request.urlopen(feed_url, timeout=30) as response:
        content = response.read()

    root = ET.fromstring(content)
    for tag_name in ("logo", "icon"):
        element = root.find(f".//{{*}}{tag_name}")
        if element is not None and element.text and element.text.strip():
            return element.text.strip()

    raise RuntimeError("Atom feed 中未找到 logo/icon")


def update_feed_cover(token: str, feed_id: str, mp_cover: str) -> None:
    payload = json.dumps({"mp_cover": mp_cover}, ensure_ascii=False).encode("utf-8")
    http_json(
        f"{API_BASE_URL}/mps/{feed_id}",
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=payload,
    )


def main() -> int:
    token = login()
    feeds = fetch_missing_feeds(token)
    print(f"待补齐公众号图标数量: {len(feeds)}")

    success_count = 0
    skipped_count = 0
    failures: list[tuple[str, str]] = []

    for feed in feeds:
        mp_name = feed["mp_name"]
        feed_id = feed["id"]
        try:
            logo_url = fetch_feed_logo(feed_id)
            update_feed_cover(token, feed_id, logo_url)
            success_count += 1
            print(f"[成功] {mp_name}: {logo_url}")
        except urllib.error.HTTPError as exc:
            skipped_count += 1
            failures.append((mp_name, f"HTTP {exc.code}"))
            print(f"[跳过] {mp_name}: HTTP {exc.code}")
        except Exception as exc:
            skipped_count += 1
            failures.append((mp_name, str(exc)))
            print(f"[跳过] {mp_name}: {exc}")

    print("\n补齐结果")
    print("=" * 40)
    print(f"成功: {success_count}")
    print(f"跳过: {skipped_count}")
    print(f"失败清单: {len(failures)}")
    for mp_name, reason in failures:
        print(f"- {mp_name}: {reason}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
