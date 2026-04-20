#!/usr/bin/env python3
"""
AI KOL Daily Digest
步骤：
  1. fetch  - 从 Apify 抓取推文，保存到 data/today_tweets.json
  2. publish - 读取 data/today_summary.md，发送邮件 + 生成存档网页
"""

import json
import os
import sys
import time
import smtplib
import datetime
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

# ── 配置 ──────────────────────────────────────────────────────────────
APIFY_TOKEN    = os.environ["APIFY_TOKEN"]
GMAIL_USER     = os.environ["GMAIL_USER"]       # 你的 Gmail 地址
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]   # 应用专用密码
GMAIL_TO       = os.environ.get("GMAIL_TO", GMAIL_USER)  # 收件人，默认发给自己

BASE_DIR      = Path(__file__).parent.parent
DATA_DIR      = BASE_DIR / "data"
ARCHIVE_DIR   = DATA_DIR / "archive"
DOCS_DIR      = BASE_DIR / "docs"
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

    since = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=24)).strftime("%Y-%m-%d_%H:%M:00_UTC")
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

    today = datetime.date.today().strftime("%Y-%m-%d")
    output = {
        "date": today,
        "accounts": accounts,
        "tweets": results,
        "total_tweets": sum(len(v) for v in results.values()),
        "active_kols": len(results),
    }
    TWEETS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Apify] 完成，共 {output['total_tweets']} 条推文")


def _wait_for_run(run_id: str, timeout: int = 300) -> list:
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
    dataset_url = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items?token={APIFY_TOKEN}"
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


# ── Step 2: 发送邮件 + 生成网页 ────────────────────────────────────────

def publish():
    if not SUMMARY_FILE.exists():
        print("[错误] data/today_summary.md 不存在")
        sys.exit(1)

    summary = SUMMARY_FILE.read_text(encoding="utf-8")
    tweets_data = json.loads(TWEETS_FILE.read_text(encoding="utf-8")) if TWEETS_FILE.exists() else {}
    today = tweets_data.get("date", datetime.date.today().strftime("%Y-%m-%d"))

    _send_email(summary, today)
    _save_archive(today, summary, tweets_data)
    _generate_web(today, summary)

    print(f"\n✅ 发布完成！日期：{today}")


def _send_email(summary: str, date_str: str):
    print("[Gmail] 发送邮件...")
    subject = f"🤖 AI KOL 日报 {date_str}"

    # 纯文本版
    body_text = summary

    # HTML 版（稍微美化）
    html_summary = summary.replace("\n", "<br>").replace("**", "")
    body_html = f"""
    <html><body style="font-family: -apple-system, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; color: #333;">
    <h2 style="color: #6366f1;">🤖 AI KOL 日报 {date_str}</h2>
    <hr style="border: none; border-top: 1px solid #eee;">
    <div style="line-height: 1.8;">{html_summary}</div>
    <hr style="border: none; border-top: 1px solid #eee;">
    <p style="color: #999; font-size: 12px;">
        查看历史存档：<a href="https://casperit.github.io/ai-kol-radar/">casperit.github.io/ai-kol-radar</a>
    </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_TO
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, GMAIL_TO, msg.as_string())
        print(f"[Gmail] 发送成功 → {GMAIL_TO} ✓")
    except Exception as e:
        print(f"[Gmail] 发送失败: {e}")


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
    build_daily_page(date_str, summary, DOCS_DIR)
    build_index_page(ARCHIVE_DIR, DOCS_DIR)
    print("[网页] HTML 已生成 ✓")


# ── 入口 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "fetch":
        fetch_tweets()
    elif cmd == "publish_web":
        publish_web()
    elif cmd == "publish":
        publish()
    else:
        print("用法：python src/main.py fetch | publish")


def publish_web():
    """只生成网页存档，不发邮件（邮件由 Gmail connector 负责）"""
    if not SUMMARY_FILE.exists():
        print("[错误] data/today_summary.md 不存在")
        sys.exit(1)

    summary = SUMMARY_FILE.read_text(encoding="utf-8")
    tweets_data = json.loads(TWEETS_FILE.read_text(encoding="utf-8")) if TWEETS_FILE.exists() else {}
    today = tweets_data.get("date", datetime.date.today().strftime("%Y-%m-%d"))

    _save_archive(today, summary, tweets_data)
    _generate_web(today, summary)
    print(f"\n✅ 网页存档完成！日期：{today}")
