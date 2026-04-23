#!/usr/bin/env python3
"""
AI KOL Daily Digest
  fetch       - 抓推文 + 行业新闻 → today_tweets.json + today_digest.json
  summarize   - Python整理内容 + Claude API写摘要 → today_summary.md
  publish_web - 生成网页存档
  publish     - publish_web + 发Gmail
"""

import json, os, sys, time, re, smtplib, datetime, requests
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
DIGEST_FILE   = DATA_DIR / "today_digest.json"
SUMMARY_FILE  = DATA_DIR / "today_summary.md"

MAX_TWEETS_PER_USER = 8
NEWS_QUERIES = [
    "AI model release OR launch min_faves:500",
    "OpenAI OR Anthropic OR Google DeepMind announcement min_faves:300",
    "LLM benchmark OR AI research paper min_faves:200",
    "AI startup funding OR AI product launch min_faves:200",
    "AGI OR AI safety news min_faves:300",
]
MAX_NEWS_PER_QUERY = 10


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

    # KOL 推文
    print(f"[Apify] 抓取 {len(usernames)} 个KOL...")
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
        print(f"  批次 {i//10+1}: {run_id}")
        for tweet in _wait_for_run(run_id):
            author = tweet.get("author", {}).get("userName", "").lower()
            if author:
                kol_results.setdefault(author, []).append(_parse_tweet(tweet))
        time.sleep(2)

    # 行业新闻
    print("[Apify] 抓取行业新闻...")
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
                    "category": query.split(" min_faves")[0],
                })
            time.sleep(2)
        except Exception as e:
            print(f"  [警告] {e}")

    # 去重
    seen, deduped = set(), []
    for n in news_results:
        key = n.get("text", "")[:60]
        if key not in seen:
            seen.add(key)
            deduped.append(n)

    today = datetime.date.today().strftime("%Y-%m-%d")
    output = {
        "date": today,
        "accounts": accounts,
        "tweets": kol_results,
        "news": deduped,
        "total_tweets": sum(len(v) for v in kol_results.values()),
        "active_kols": len(kol_results),
        "total_news": len(deduped),
    }
    TWEETS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    # 自动生成 digest
    _build_digest(output)
    print(f"[完成] KOL {output['total_tweets']} 条 + 新闻 {output['total_news']} 条")


def _parse_tweet(tweet):
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


def _build_digest(data):
    accounts_map = {a["username"].lower(): a for a in data.get("accounts", [])}

    # KOL：按点赞排序，每人最多3条，正文截断150字
    kol_digest = []
    for username, tweets in data.get("tweets", {}).items():
        acc = accounts_map.get(username, {})
        sorted_tweets = sorted(tweets, key=lambda t: t.get("likes", 0), reverse=True)[:3]
        compressed = []
        for t in sorted_tweets:
            text = t.get("text", "")
            urls = re.findall(r'https?://\S+', text)
            clean = re.sub(r'https?://\S+', '', text).strip()
            if len(clean) > 150:
                clean = clean[:150] + "..."
            compressed.append({
                "text": clean,
                "links": urls[:2],
                "likes": t.get("likes", 0),
                "retweets": t.get("retweets", 0),
            })
        if compressed:
            kol_digest.append({
                "username": username,
                "display_name": acc.get("display_name", username),
                "note": acc.get("note", ""),
                "tweets": compressed,
            })
    kol_digest.sort(key=lambda k: max((t["likes"] for t in k["tweets"]), default=0), reverse=True)

    # 新闻：500赞以上，最多15条
    filtered_news = sorted(
        [n for n in data.get("news", []) if n.get("likes", 0) >= 500],
        key=lambda n: n.get("likes", 0), reverse=True
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
            "category": n.get("category", ""),
        })

    digest = {
        "date": data.get("date", ""),
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
    print(f"[Digest] {len(kol_digest)}个KOL，新闻{len(compressed_news)}条")


# ── summarize ──────────────────────────────────────────────────────────

def summarize():
    """
    Python 直接生成 KOL 详情和新闻列表
    只调用 Claude API 生成整体摘要（输出很短，不会超时）
    """
    digest = json.loads(DIGEST_FILE.read_text(encoding="utf-8"))
    date = digest.get("date", datetime.date.today().strftime("%Y-%m-%d"))

    print("[摘要] 调用 Claude API 生成整体摘要...")
    overview = _call_claude_for_overview(digest)

    print("[摘要] Python 生成详细内容...")
    body = _build_body(digest)

    full = f"{overview}\n\n---\n{body}"
    SUMMARY_FILE.write_text(full, encoding="utf-8")
    print(f"[摘要] 已保存 today_summary.md ({len(full)} 字符)")


def _call_claude_for_overview(digest: dict) -> str:
    """只让 Claude 写整体摘要，输出控制在200字以内"""

    # 构造给 Claude 的简短数据描述
    kol_highlights = []
    for kol in digest.get("kols", [])[:20]:  # 只取前20个
        username = kol.get("username", "")
        note = kol.get("note", "")
        top_tweet = kol.get("tweets", [{}])[0].get("text", "")[:80]
        kol_highlights.append(f"@{username}({note}): {top_tweet}")

    news_highlights = []
    for n in digest.get("news", [])[:10]:
        news_highlights.append(f"♥{n.get('likes',0)} {n.get('text','')[:80]}")

    prompt = f"""以下是今日({digest.get('date','')}) AI领域的推文摘要，请用中英双语各写一段整体摘要（各100字左右），提炼最重要的3-5个话题趋势，要有观点。

KOL动态：
{chr(10).join(kol_highlights)}

行业新闻：
{chr(10).join(news_highlights)}

输出格式：
【整体摘要 / Daily Overview】

（中文摘要，100字左右）

(English summary, ~100 words)"""

    try:
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        print(f"  [警告] Claude API 调用失败: {e}，使用备用摘要")
        return _fallback_overview(digest)


def _fallback_overview(digest: dict) -> str:
    """Claude API 失败时的备用摘要"""
    stats = digest.get("stats", {})
    date = digest.get("date", "")
    return f"""【整体摘要 / Daily Overview】

今日共有 {stats.get('total_kols', 0)} 位 AI 领域 KOL 活跃，发布 {stats.get('total_tweets_raw', 0)} 条推文，行业新闻 {stats.get('news_after_filter', 0)} 条。

Today {stats.get('total_kols', 0)} AI KOLs were active with {stats.get('total_tweets_raw', 0)} tweets and {stats.get('news_after_filter', 0)} industry news items."""


def _build_body(digest: dict) -> str:
    """Python 直接生成新闻列表和 KOL 详情，无需 AI"""
    lines = []

    # 行业新闻
    lines.append("【行业新闻 / Industry News】")
    lines.append("")
    for n in digest.get("news", []):
        handle = n.get("author_handle", "")
        text = n.get("text", "")
        likes = n.get("likes", 0)
        links = n.get("links", [])
        link_str = f" → {links[0]}" if links else ""
        lines.append(f"- {text}{link_str} (@{handle} ♥{likes:,})")
    lines.append("")
    lines.append("---")

    # KOL 详情
    lines.append("【各KOL详情 / KOL Details】")
    lines.append("")
    for kol in digest.get("kols", []):
        username = kol.get("username", "")
        note = kol.get("note", "")
        lines.append(f"**@{username}（{note}）**")
        for t in kol.get("tweets", []):
            text = t.get("text", "")
            likes = t.get("likes", 0)
            links = t.get("links", [])
            link_str = f" → {links[0]}" if links else ""
            lines.append(f"- {text}{link_str} ♥{likes:,}")
        lines.append("")

    return "\n".join(lines)


# ── publish_web ────────────────────────────────────────────────────────

def publish_web():
    if not SUMMARY_FILE.exists():
        print("[错误] data/today_summary.md 不存在，请先运行 summarize")
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
    print(f"[网页] 已生成 ✓")


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


# ── publish ────────────────────────────────────────────────────────────

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
    html_body = summary.replace("\n", "<br>")
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
    elif cmd == "summarize":
        summarize()
    elif cmd == "publish_web":
        publish_web()
    elif cmd == "publish":
        publish()
    else:
        print("用法: python src/main.py fetch | summarize | publish_web | publish")
