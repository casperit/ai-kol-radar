#!/usr/bin/env python3
"""
AI KOL Daily Digest
  fetch       - 抓推文 + 行业新闻
  summarize   - 生成总结（Claude API 写摘要，Python 整理详情）
  publish_web - 生成网页
  publish     - publish_web + Gmail
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

MAX_TWEETS_PER_USER = 10
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
            print(f"  [警告] {run_id}: {status}")
            return []
        time.sleep(10)
    return []


def _is_quality_tweet(text: str) -> bool:
    """过滤低质量推文：纯回复、无内容、太短"""
    t = text.strip()
    # 纯回复（以 @某人 开头且正文很短）
    if re.match(r'^@\w+\s*$', t):
        return False
    if re.match(r'^@\w+\s+\S{0,20}\s*$', t):
        return False
    # 去掉链接后太短
    clean = re.sub(r'https?://\S+', '', t).strip()
    if len(clean) < 20:
        return False
    return True


def _build_digest(data):
    accounts_map = {a["username"].lower(): a for a in data.get("accounts", [])}

    kol_digest = []
    for username, tweets in data.get("tweets", {}).items():
        acc = accounts_map.get(username, {})

        # 过滤低质量推文，再按点赞排序取前5条
        quality = [t for t in tweets if _is_quality_tweet(t.get("text", ""))]
        top = sorted(quality, key=lambda t: t.get("likes", 0), reverse=True)[:5]

        compressed = []
        for t in top:
            text = t.get("text", "")
            urls = re.findall(r'https?://\S+', text)
            clean = re.sub(r'https?://\S+', '', text).strip()
            if len(clean) > 200:
                clean = clean[:200] + "..."
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

    kol_digest.sort(
        key=lambda k: max((t["likes"] for t in k["tweets"]), default=0),
        reverse=True
    )

    # 新闻：过滤低质量，500赞以上，最多15条
    filtered_news = sorted(
        [n for n in data.get("news", [])
         if n.get("likes", 0) >= 500 and _is_quality_tweet(n.get("text", ""))],
        key=lambda n: n.get("likes", 0), reverse=True
    )[:15]

    compressed_news = []
    for n in filtered_news:
        text = n.get("text", "")
        urls = re.findall(r'https?://\S+', text)
        clean = re.sub(r'https?://\S+', '', text).strip()
        if len(clean) > 200:
            clean = clean[:200] + "..."
        compressed_news.append({
            "text": clean,
            "links": urls[:2],
            "likes": n.get("likes", 0),
            "author_handle": n.get("author_handle", ""),
            "author_name": n.get("author_name", ""),
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
    print(f"[Digest] {len(kol_digest)}个KOL，新闻{len(compressed_news)}条（过滤后）")


# ── summarize ──────────────────────────────────────────────────────────

def summarize():
    digest = json.loads(DIGEST_FILE.read_text(encoding="utf-8"))

    print("[摘要] 调用 Claude API 生成整体摘要...")
    overview = _call_claude_for_overview(digest)

    print("[摘要] 生成详细内容...")
    body = _build_body(digest)

    full = f"{overview}\n\n---\n{body}"
    SUMMARY_FILE.write_text(full, encoding="utf-8")
    print(f"[摘要] 完成，{len(full)} 字符")


def _call_claude_for_overview(digest: dict) -> str:
    # 给 Claude 的精简输入：每个KOL最高赞推文 + 前10条新闻
    kol_lines = []
    for kol in digest.get("kols", [])[:25]:
        top = kol.get("tweets", [{}])[0].get("text", "")[:100]
        kol_lines.append(f"@{kol['username']}({kol['note']}): {top}")

    news_lines = []
    for n in digest.get("news", [])[:10]:
        news_lines.append(f"♥{n.get('likes',0)} @{n.get('author_handle','')}: {n.get('text','')[:100]}")

    prompt = f"""今日({digest.get('date','')}) AI领域动态，请写中英双语整体摘要（各约100字），提炼3-5个最重要话题趋势，要有观点不要流水账。

KOL动态（按热度）：
{chr(10).join(kol_lines)}

行业新闻：
{chr(10).join(news_lines)}

输出格式（严格遵守）：
【整体摘要 / Daily Overview】

（中文摘要100字）

(English summary ~100 words)"""

    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        print("  [Claude API] 摘要生成成功 ✓")
        return msg.content[0].text
    except Exception as e:
        print(f"  [警告] Claude API 失败: {e}，使用备用摘要")
        return _fallback_overview(digest)


def _fallback_overview(digest: dict) -> str:
    stats = digest.get("stats", {})
    return f"""【整体摘要 / Daily Overview】

今日共 {stats.get('total_kols', 0)} 位 KOL 活跃，发布 {stats.get('total_tweets_raw', 0)} 条推文，精选行业新闻 {stats.get('news_after_filter', 0)} 条。

Today {stats.get('total_kols', 0)} KOLs were active with {stats.get('total_tweets_raw', 0)} tweets and {stats.get('news_after_filter', 0)} curated industry news items."""


def _build_body(digest: dict) -> str:
    lines = []

    # 行业新闻
    lines.append("【行业新闻 / Industry News】")
    lines.append("")
    news = digest.get("news", [])
    if news:
        for n in news:
            handle = n.get("author_handle", "")
            text = n.get("text", "")
            likes = n.get("likes", 0)
            links = n.get("links", [])
            link_str = f"  \n  → {links[0]}" if links else ""
            lines.append(f"- **@{handle}** ♥{likes:,}  \n  {text}{link_str}")
            lines.append("")
    else:
        lines.append("（今日无符合条件的行业新闻）")
        lines.append("")

    lines.append("---")
    lines.append("")

    # KOL 详情
    lines.append("【各KOL详情 / KOL Details】")
    lines.append("")
    for kol in digest.get("kols", []):
        username = kol.get("username", "")
        note = kol.get("note", "")
        lines.append(f"**@{username}（{note}）**")
        lines.append("")
        for t in kol.get("tweets", []):
            text = t.get("text", "")
            likes = t.get("likes", 0)
            retweets = t.get("retweets", 0)
            links = t.get("links", [])
            lines.append(f"> {text}")
            if links:
                lines.append(f"> → {links[0]}")
            lines.append(f"> ♥{likes:,} &nbsp; ↺{retweets:,}")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ── publish_web ────────────────────────────────────────────────────────

def publish_web():
    if not SUMMARY_FILE.exists():
        print("[错误] today_summary.md 不存在")
        sys.exit(1)

    summary = SUMMARY_FILE.read_text(encoding="utf-8")
    tweets_data = json.loads(TWEETS_FILE.read_text(encoding="utf-8")) if TWEETS_FILE.exists() else {}
    digest_data = json.loads(DIGEST_FILE.read_text(encoding="utf-8")) if DIGEST_FILE.exists() else {}
    accounts = load_accounts()
    today = tweets_data.get("date", datetime.date.today().strftime("%Y-%m-%d"))

    _save_archive(today, summary, tweets_data)

    sys.path.insert(0, str(Path(__file__).parent))
    from web_generator import build_daily_page, build_index_page, build_kol_page, build_topic_page

    build_daily_page(today, digest_data, DOCS_DIR)
    build_index_page(ARCHIVE_DIR, DOCS_DIR)
    build_kol_page(ARCHIVE_DIR, DOCS_DIR, accounts)
    build_topic_page(ARCHIVE_DIR, DOCS_DIR)
    print("[网页] 生成完成 ✓")


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


def publish():
    publish_web()
    if not GMAIL_USER:
        return
    summary = SUMMARY_FILE.read_text(encoding="utf-8")
    tweets_data = json.loads(TWEETS_FILE.read_text(encoding="utf-8")) if TWEETS_FILE.exists() else {}
    today = tweets_data.get("date", datetime.date.today().strftime("%Y-%m-%d"))
    _send_email(summary, today)


def _send_email(summary, date_str):
    print("[Gmail] 发送...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🤖 AI KOL 日报 {date_str}"
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_TO
    msg.attach(MIMEText(summary, "plain", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_USER, GMAIL_PASSWORD)
            s.sendmail(GMAIL_USER, GMAIL_TO, msg.as_string())
        print(f"[Gmail] 发送成功 ✓")
    except Exception as e:
        print(f"[Gmail] 失败: {e}")


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
