#!/usr/bin/env python3
"""
AI KOL Daily Digest
步骤：
  1. fetch_tweets  - 从 Apify 抓取推文，保存到 data/today_tweets.json
  2. send_wecom    - 读取 data/today_summary.md，推送企业微信
  3. save_archive  - 生成存档 HTML

Routine 的工作流程：
  先调用 python src/main.py fetch  → 拿到推文数据
  Claude 自己读数据写总结，保存到 data/today_summary.md
  再调用 python src/main.py publish → 推送微信 + 生成网页 + commit
"""

import json
import os
import sys
import time
import datetime
import requests
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────
APIFY_TOKEN       = os.environ["APIFY_TOKEN"]
WECOM_WEBHOOK_URL = os.environ["WECOM_WEBHOOK_URL"]

BASE_DIR      = Path(__file__).parent.parent
DATA_DIR      = BASE_DIR / "data"
ARCHIVE_DIR   = DATA_DIR / "archive"
WEB_DIR       = BASE_DIR / "web"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
TWEETS_FILE   = DATA_DIR / "today_tweets.json"
SUMMARY_FILE  = DATA_DIR / "today_summary.md"

MAX_TWEETS_PER_USER = 5
# ──────────────────────────────────────────────────────────────────────


def load_accounts():
    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        return json.load(f)["accounts"]


# ── Step 1: 抓取推文 ───────────────────────────────────────────────────

def fetch_tweets():
    accounts = load_accounts()
    usernames = [a["username"] for a in accounts]
    print(f"[Apify] 开始抓取 {len(usernames)} 个账号...")

    since = (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).strftime("%Y-%m-%d_%H:%M:00_UTC")
    actor_id = "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest"
    run_url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={APIFY_TOKEN}"

    results = {}
    batch_size = 10

    for i in range(0, len(usernames), batch_size):
        batch = usernames[i:i + batch_size]
        search_terms = [f"from:{u} since:{since}" for u in batch]
        payload = {
            "searchTerms": search_terms,
            "maxTweets": MAX_TWEETS_PER_USER,
            "queryType": "Latest",
        }
        resp = requests.post(run_url, json=payload, timeout=30)
        resp.raise_for_status()
        run_id = resp.json()["data"]["id"]
        print(f"  批次 {i // batch_size + 1}: run_id={run_id}")

        items = _wait_for_run(run_id)
        for tweet in items:
            author = tweet.get("author", {}).get("userName", "").lower()
            if author:
                results.setdefault(author, []).append({
                    "text": tweet.get("text", ""),
                    "created_at": tweet.get("createdAt", ""),
                    "likes": tweet.get("likeCount", 0),
                    "retweets": tweet.get("retweetCount", 0),
                })
        time.sleep(2)

    # 保存推文数据，供 Claude 读取
    today = datetime.date.today().strftime("%Y-%m-%d")
    output = {
        "date": today,
        "accounts": accounts,
        "tweets": results,
        "total_tweets": sum(len(v) for v in results.values()),
        "active_kols": len(results),
    }
    TWEETS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Apify] 完成，共 {output['total_tweets']} 条推文，已保存到 {TWEETS_FILE}")
    print(f"\n推文数据已就绪，请 Claude 读取 data/today_tweets.json 生成总结。")


def _wait_for_run(run_id: str, timeout: int = 300) -> list:
    token = APIFY_TOKEN
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={token}"
    dataset_url = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items?token={token}"
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(status_url, timeout=10)
        status = r.json()["data"]["status"]
        if status == "SUCCEEDED":
            items = requests.get(dataset_url, timeout=10).json()
            return items if isinstance(items, list) else []
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            print(f"  [警告] run {run_id} 状态: {status}")
            return []
        time.sleep(10)
    print(f"  [警告] run {run_id} 超时")
    return []


# ── Step 2 & 3: 推送 + 存档 ────────────────────────────────────────────

def publish():
    if not SUMMARY_FILE.exists():
        print("[错误] data/today_summary.md 不存在，请先让 Claude 生成总结")
        sys.exit(1)

    summary = SUMMARY_FILE.read_text(encoding="utf-8")
    tweets_data = json.loads(TWEETS_FILE.read_text(encoding="utf-8")) if TWEETS_FILE.exists() else {}
    today = tweets_data.get("date", datetime.date.today().strftime("%Y-%m-%d"))

    # 推送企业微信
    _send_to_wecom(summary, today)

    # 生成网页存档
    _save_archive(today, summary, tweets_data)
    _generate_web(today, summary)

    print(f"\n✅ 发布完成！日期：{today}")


def _send_to_wecom(summary: str, date_str: str):
    print("[企业微信] 推送中...")
    header = f"# 🤖 AI KOL 日报 {date_str}\n\n"
    content = header + summary
    if len(content) > 4000:
        content = content[:3950] + "\n\n...(完整内容见存档网页)"
    payload = {"msgtype": "markdown", "markdown": {"content": content}}
    try:
        resp = requests.post(WECOM_WEBHOOK_URL, json=payload, timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            print("[企业微信] 推送成功 ✓")
        else:
            print(f"[企业微信] 推送失败: {result}")
    except Exception as e:
        print(f"[企业微信] 推送异常: {e}")


def _save_archive(date_str: str, summary: str, tweets_data: dict):
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive = {
        "date": date_str,
        "summary": summary,
        "tweet_count": tweets_data.get("total_tweets", 0),
        "kol_count": tweets_data.get("active_kols", 0),
    }
    path = ARCHIVE_DIR / f"{date_str}.json"
    path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[存档] 已保存 {path}")


def _generate_web(date_str: str, summary: str):
    sys.path.insert(0, str(Path(__file__).parent))
    from web_generator import build_daily_page, build_index_page
    build_daily_page(date_str, summary, WEB_DIR)
    build_index_page(ARCHIVE_DIR, WEB_DIR)
    print("[网页] HTML 已生成 ✓")


# ── 入口 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "fetch":
        fetch_tweets()
    elif cmd == "publish":
        publish()
    else:
        print("用法：python src/main.py fetch | publish")
