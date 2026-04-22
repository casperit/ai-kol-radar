#!/usr/bin/env python3
"""
AI KOL Daily Digest
  fetch       - 从 Apify 抓推文 + 行业新闻 → data/today_tweets.json
  summarize   - 压缩 + 筛选数据 → data/today_digest.json（供 Claude 读取）
  publish_web - 读 today_summary.md → 生成 docs/ 网页存档
  publish     - 同上 + 发 Gmail（备用）
"""

import json, os, sys, time, smtplib, datetime, requests, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

APIFY_TOKEN    = os.environ["APIFY_TOKEN"]
GMAIL_USER     = os.environ.get("GMAIL_USER", "")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")
GMAIL_TO       = os.environ.get("GMAIL_TO", GMAIL_USER)

BASE_DIR      = Path(__file__).parent.parent
DATA_DIR      = BASE_DIR / "data"
ARCHIVE_DIR   = DATA_DIR / "archive"
DOCS_DIR      = BASE_DIR / "docs"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"
TWEETS_FILE   = DATA_DIR / "today_tweets.json"
DIGEST_FILE   = DATA_DIR / "today_digest.json"   # 压缩后的精简数据
SUMMARY_FILE  = DATA_DIR / "today_summary.md"

MAX_TWEETS_PER_USER = 8

NEWS_QUERIES = [
    "AI model release OR launch min_faves:500",
    "OpenAI OR Anthropic OR Google DeepMind announcement min_faves:300",
    "LLM benchmark OR AI research paper min_faves:200",
    "AI startup funding OR AI product launch min_faves:200",
    "AGI OR AI safety news min_faves:300",
]
MAX_NEWS_PER_QUERY = 10  # 抓多一点，筛选后留精华


def load_accounts():
    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        return json.load(f)["accounts"]


# ── fetch ──────────────────────────────────────────────────────────────

def fetch_tweets():
    accounts = load_accounts()
    usernames = [a["username"] for a in accounts]
    since = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=24)).strftime("%Y-%m-%d_%H:%M:00_UTC")
    actor_id = "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest"
    run_url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={APIFY_TOKEN}"

    # 1. 抓 KOL 推文
    print(f"[Apify] 抓取 {len(usernames)} 个 KOL 账号...")
    kol_results = {}
    for i in range(0, len(usernames), 10):
        batch = usernames[i:i+10]
        payload = {
            "searchTerms": [f"from:{u} since:{since}" for u in batch],
            "maxTweets": MAX_TWEETS_PER_USER,
            "queryType": "Latest",
        }
        resp = requests.post(run_url, json=payload, timeout=30)
        resp.raise_for_status()
        run_id = resp.json()["data"]["id"]
        print(f"  KOL 批次 {i//10+1}: run_id={run_id}")
        for tweet in _wait_for_run(run_id):
            author = tweet.get("author", {}).get("userName", "").lower()
            if author:
                kol_results.setdefault(author, []).append(_parse_tweet(tweet))
        time.sleep(2)
    print(f"[Apify] KOL 完成，共 {sum(len(v) for v in kol_results.values())} 条")

    # 2. 抓行业新闻
    print(f"[Apify] 抓取行业新闻...")
    news_results = []
    for query in NEWS_QUERIES:
        payload = {
            "searchTerms": [f"{query} since:{since}"],
            "maxTweets": MAX_NEWS_PER_QUERY,
            "queryType": "Top",
        }
        try:
            resp = requests.post(run_url, json=payload, timeout=30)
            resp.raise_for_status()
            run_id = resp.json()["data"]["id"]
            for tweet in _wait_for_run(run_id):
                news_results.append({
                    **_parse_tweet(tweet),
                    "author_name": tweet.get("author", {}).get("name", ""),
                    "author_handle": tweet.get("author", {}).get("userName", ""),
                    "query_category": query.split(" min_faves")[0],
                })
            time.sleep(2)
        except Exception as e:
            print(f"  [警告] 新闻查询失败: {e}")

    # 去重
    seen, deduped_news = set(), []
    for n in news_results:
        key = n.get("text", "")[:60]
        if key not in seen:
            seen.add(key)
            deduped_news.append(n)

    print(f"[Apify] 新闻完成，共 {len(deduped_news)} 条（去重后）")

    today = datetime.date.today().strftime("%Y-%m-%d")
    output = {
        "date": today,
        "accounts": accounts,
        "tweets": kol_results,
        "news": deduped_news,
        "total_tweets": sum(len(v) for v in kol_results.values()),
        "active_kols": len(kol_results),
        "total_news": len(deduped_news),
    }
    TWEETS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[完成] KOL {output['total_tweets']} 条 + 新闻 {output['total_news']} 条，已保存原始数据")

    # 自动生成精简摘要供 Claude 读取
    _build_digest(output)


def _parse_tweet(tweet: dict) -> dict:
    return {
        "text": tweet.get("text", ""),
        "created_at": tweet.get("createdAt", ""),
        "likes": tweet.get("likeCount", 0),
        "retweets": tweet.get("retweetCount", 0),
        "url": tweet.get("url", ""),
    }


def _wait_for_run(run_id, timeout=300):
    status_url  = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
    dataset_url = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items?token={APIFY_TOKEN}"
    start = time.time()
    while time.time() - start < timeout:
        status = requests.get(status_url, timeout=10).json()["data"]["status"]
        if status == "SUCCEEDED":
            items = requests.get(dataset_url, timeout=10).json()
            return items if isinstance(items, list) else []
        elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
            print(f"  [警告] run {run_id}: {status}")
            return []
        time.sleep(10)
    return []


# ── 预处理：压缩 + 筛选 ────────────────────────────────────────────────

def _build_digest(data: dict):
    """
    A方案：截断长推文到150字，提取链接
    C方案：KOL 按点赞排序取前5条；新闻只保留点赞300+，最多50条
    """
    accounts_map = {a["username"].lower(): a for a in data.get("accounts", [])}
    today = data.get("date", "")

    # ── KOL 部分 ──
    kol_digest = []
    for username, tweets in data.get("tweets", {}).items():
        acc = accounts_map.get(username, {})

        # C方案：按点赞排序，取前5条
        sorted_tweets = sorted(tweets, key=lambda t: t.get("likes", 0), reverse=True)[:3]

        compressed = []
        for t in sorted_tweets:
            text = t.get("text", "")
            # 提取链接
            urls = re.findall(r'https?://\S+', text)
            # A方案：截断正文到150字
            clean = re.sub(r'https?://\S+', '', text).strip()
            if len(clean) > 150:
                clean = clean[:150] + "..."

            compressed.append({
                "text": clean,
                "links": urls[:3],
                "likes": t.get("likes", 0),
                "retweets": t.get("retweets", 0),
            })

        if compressed:
            kol_digest.append({
                "username": username,
                "display_name": acc.get("display_name", username),
                "note": acc.get("note", ""),
                "tweets": compressed,
                "tweet_count": len(tweets),  # 原始总数
            })

    # 按最高点赞排序 KOL
    kol_digest.sort(key=lambda k: max((t["likes"] for t in k["tweets"]), default=0), reverse=True)

    # ── 新闻部分 ──
    news = data.get("news", [])
    # C方案：只保留点赞300+，按点赞排序，最多50条
    filtered_news = sorted(
        [n for n in news if n.get("likes", 0) >= 500],
        key=lambda n: n.get("likes", 0),
        reverse=True
    )[:15]

    compressed_news = []
    for n in filtered_news:
        text = n.get("text", "")
        urls = re.findall(r'https?://\S+', text)
        clean = re.sub(r'https?://\S+', '', text).strip()
        if len(clean) > 150:
            clean = clean[:150] + "..."
        compressed_news.append({
            "text": clean,
            "links": urls[:2],
            "likes": n.get("likes", 0),
            "author_handle": n.get("author_handle", ""),
            "author_name": n.get("author_name", ""),
            "category": n.get("query_category", ""),
        })

    digest = {
        "date": today,
        "kols": kol_digest,
        "news": compressed_news,
        "stats": {
            "total_kols": len(kol_digest),
            "total_tweets_raw": data.get("total_tweets", 0),
            "total_news_raw": data.get("total_news", 0),
            "news_after_filter": len(compressed_news),
        }
    }

    DIGEST_FILE.write_text(json.dumps(digest, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = digest["stats"]
    print(f"[Digest] 压缩完成：{stats['total_kols']} 个KOL，新闻 {stats['total_news_raw']} → {stats['news_after_filter']} 条（300+赞）")


# ── publish_web ────────────────────────────────────────────────────────

def publish_web():
    if not SUMMARY_FILE.exists():
        print("[错误] data/today_summary.md 不存在")
        sys.exit(1)

    summary = SUMMARY_FILE.read_text(encoding="utf-8")
    tweets_data = json.loads(TWEETS_FILE.read_text(encoding="utf-8")) if TWEETS_FILE.exists() else {}
    accounts = load_accounts()
    today = tweets_data.get("date", datetime.date.today().strftime("%Y-%m-%d"))

    _save_archive(today, summary, tweets_data)

    sys.path.insert(0, str(Path(__file__).parent))
    from web_generator import build_daily_page, build_index_page, build_kol_page, build_topic_page

    build_daily_page(today, summary, DOCS_DIR, tweets_data)
    build_index_page(ARCHIVE_DIR, DOCS_DIR)
    build_kol_page(ARCHIVE_DIR, DOCS_DIR, accounts)
    build_topic_page(ARCHIVE_DIR, DOCS_DIR)
    print(f"[网页] 已生成 index / {today} / kol / topic ✓")


def _save_archive(date_str, summary, tweets_data):
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    path = ARCHIVE_DIR / f"{date_str}.json"
    path.write_text(json.dumps({
        "date": date_str,
        "summary": summary,
        "tweet_count": tweets_data.get("total_tweets", 0),
        "kol_count": tweets_data.get("active_kols", 0),
        "news_count": tweets_data.get("total_news", 0),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[存档] {path}")


# ── publish (含 Gmail SMTP，备用) ──────────────────────────────────────

def publish():
    publish_web()
    if not GMAIL_USER:
        return
    summary = SUMMARY_FILE.read_text(encoding="utf-8")
    tweets_data = json.loads(TWEETS_FILE.read_text(encoding="utf-8")) if TWEETS_FILE.exists() else {}
    today = tweets_data.get("date", datetime.date.today().strftime("%Y-%m-%d"))
    _send_email(summary, today)


def _send_email(summary, date_str):
    print("[Gmail] 发送邮件...")
    html_body = summary.replace("\n", "<br>").replace("**", "")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🤖 AI KOL 日报 {date_str}"
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_TO
    msg.attach(MIMEText(summary, "plain", "utf-8"))
    msg.attach(MIMEText(f"<html><body style='font-family:sans-serif;max-width:700px;margin:0 auto;padding:20px'>{html_body}</body></html>", "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASSWORD)
            s.sendmail(GMAIL_USER, GMAIL_TO, msg.as_string())
        print(f"[Gmail] 发送成功 → {GMAIL_TO} ✓")
    except Exception as e:
        print(f"[Gmail] 发送失败: {e}")


# ── 入口 ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "fetch":
        fetch_tweets()
    elif cmd == "build_prompt":
        data = json.loads(DIGEST_FILE.read_text(encoding="utf-8"))
        prompt_text = build_prompt_text(data)
        prompt_file = DATA_DIR / "today_prompt.txt"
        prompt_file.write_text(prompt_text, encoding="utf-8")
        size_kb = len(prompt_text.encode()) / 1024
        print(f"[Prompt] 已生成 today_prompt.txt，大小 {size_kb:.1f} KB，共 {len(prompt_text.splitlines())} 行")
    elif cmd == "publish_web":
        publish_web()
    elif cmd == "publish":
        publish()
    else:
        print("用法: python src/main.py fetch | publish_web | publish")


def build_prompt_text(data: dict) -> str:
    """
    把 digest 数据转成紧凑的纯文本，供 Claude 直接读取生成总结
    目标：信息密度高，体积小，Claude 处理快
    """
    lines = []
    date = data.get("date", "")
    stats = data.get("stats", {})

    lines.append(f"=== AI KOL 日报数据 {date} ===")
    lines.append(f"活跃KOL: {stats.get('total_kols',0)} | 原始推文: {stats.get('total_tweets_raw',0)} | 行业新闻: {stats.get('news_after_filter',0)}条(筛选后)")
    lines.append("")

    # 行业新闻
    lines.append("--- 行业新闻 ---")
    for n in data.get("news", []):
        handle = n.get("author_handle", "")
        text = n.get("text", "").replace("\n", " ")
        likes = n.get("likes", 0)
        links = " ".join(n.get("links", []))
        lines.append(f"[@{handle} ♥{likes}] {text}" + (f" | {links}" if links else ""))
    lines.append("")

    # KOL 推文
    lines.append("--- KOL 推文 ---")
    for kol in data.get("kols", []):
        username = kol.get("username", "")
        note = kol.get("note", "")
        lines.append(f"[@{username} {note}]")
        for t in kol.get("tweets", []):
            text = t.get("text", "").replace("\n", " ")
            likes = t.get("likes", 0)
            links = " ".join(t.get("links", []))
            lines.append(f"  ♥{likes} {text}" + (f" | {links}" if links else ""))
        lines.append("")

    return "\n".join(lines)
