"""
生成静态 HTML 存档页面
- docs/index.html          按日期首页
- docs/kol.html            按 KOL 汇总
- docs/topic.html          按话题汇总
- docs/YYYY-MM-DD.html     每日详情页
"""

import json
import re
from pathlib import Path


def md_to_html(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^---$', r'<hr>', text, flags=re.MULTILINE)
    lines = text.split('\n')
    out = []
    for line in lines:
        s = line.strip()
        if s.startswith('<h') or s == '<hr>':
            out.append(line)
        elif s == '':
            out.append('<br>')
        else:
            out.append(f'<p>{line}</p>')
    return '\n'.join(out)


BASE_CSS = """
:root {
  --bg: #f8f7f4;
  --surface: #ffffff;
  --surface2: #f1efe8;
  --border: rgba(0,0,0,0.08);
  --border2: rgba(0,0,0,0.14);
  --text: #1a1a18;
  --muted: #5f5e5a;
  --hint: #888780;
  --purple-bg: #eeedfe;
  --purple-text: #3c3489;
  --teal-bg: #e1f5ee;
  --teal-text: #085041;
  --amber-bg: #faeeda;
  --amber-text: #633806;
  --coral-bg: #faece7;
  --coral-text: #4a1b0c;
  --blue-bg: #e6f1fb;
  --blue-text: #0c447c;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #18181a;
    --surface: #222224;
    --surface2: #2c2c2e;
    --border: rgba(255,255,255,0.08);
    --border2: rgba(255,255,255,0.14);
    --text: #e8e8e6;
    --muted: #a0a09c;
    --hint: #6a6a66;
    --purple-bg: #26215c;
    --purple-text: #cecbf6;
    --teal-bg: #04342c;
    --teal-text: #9fe1cb;
    --amber-bg: #412402;
    --amber-text: #fac775;
    --coral-bg: #4a1b0c;
    --coral-text: #f5c4b3;
    --blue-bg: #042c53;
    --blue-text: #b5d4f4;
  }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 15px;
  line-height: 1.6;
}
a { color: inherit; text-decoration: none; }
.wrap { max-width: 780px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }

/* nav */
.nav { display: flex; align-items: center; justify-content: space-between; margin-bottom: 2rem; }
.nav-logo { font-size: 16px; font-weight: 500; }
.nav-tabs { display: flex; gap: 2px; background: var(--surface2); border-radius: 8px; padding: 3px; }
.nav-tab { font-size: 13px; padding: 5px 14px; border-radius: 6px; color: var(--muted); cursor: pointer; border: none; background: none; }
.nav-tab.active { background: var(--surface); color: var(--text); font-weight: 500; box-shadow: 0 0.5px 2px var(--border2); }
.nav-tab:hover:not(.active) { color: var(--text); }

/* stats */
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 2rem; }
.stat { background: var(--surface); border: 0.5px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.stat-num { font-size: 24px; font-weight: 500; }
.stat-label { font-size: 12px; color: var(--muted); margin-top: 2px; }

/* day card */
.day-card { background: var(--surface); border: 0.5px solid var(--border); border-radius: 12px; padding: 1.1rem 1.25rem; margin-bottom: 10px; cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s; }
.day-card:hover { border-color: var(--border2); box-shadow: 0 2px 8px var(--border); }
.day-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.day-date { font-size: 15px; font-weight: 500; }
.day-meta { display: flex; gap: 6px; align-items: center; }
.badge { font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 20px; }
.badge-kol { background: var(--purple-bg); color: var(--purple-text); }
.badge-tweet { background: var(--teal-bg); color: var(--teal-text); }
.badge-topic { background: var(--amber-bg); color: var(--amber-text); }
.day-summary { font-size: 13px; color: var(--muted); line-height: 1.65; margin-bottom: 10px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.topics { display: flex; gap: 6px; flex-wrap: wrap; }
.topic-tag { font-size: 11px; padding: 2px 8px; background: var(--surface2); color: var(--hint); border-radius: 20px; border: 0.5px solid var(--border); }
.arrow { color: var(--hint); margin-left: 8px; }

/* detail page */
.back-link { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); margin-bottom: 1.5rem; }
.back-link:hover { color: var(--text); }
.overview-box { background: var(--surface2); border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 1.5rem; }
.overview-label { font-size: 11px; color: var(--hint); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; font-weight: 500; }
.overview-text { font-size: 14px; color: var(--text); line-height: 1.75; }
.section-title { font-size: 13px; font-weight: 500; color: var(--muted); margin: 1.5rem 0 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; }
.kol-card { background: var(--surface); border: 0.5px solid var(--border); border-radius: 12px; padding: 1.1rem 1.25rem; margin-bottom: 10px; }
.kol-header { margin-bottom: 10px; }
.kol-name { font-size: 15px; font-weight: 500; }
.kol-handle { font-size: 12px; color: var(--hint); margin-top: 1px; }
.tweet-item { padding: 10px 0; border-top: 0.5px solid var(--border); }
.tweet-text { font-size: 13px; color: var(--text); line-height: 1.65; }
.tweet-link { display: inline-block; margin-top: 5px; font-size: 12px; color: var(--blue-text); word-break: break-all; }
.tweet-stats { font-size: 11px; color: var(--hint); margin-top: 5px; }
.zh-summary { font-size: 13px; color: var(--muted); margin-top: 8px; padding-top: 8px; border-top: 0.5px solid var(--border); line-height: 1.65; }

/* kol index */
.kol-index-card { background: var(--surface); border: 0.5px solid var(--border); border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 10px; cursor: pointer; transition: border-color 0.15s; }
.kol-index-card:hover { border-color: var(--border2); }
.kol-index-header { display: flex; align-items: center; justify-content: space-between; }
.kol-avatar { width: 36px; height: 36px; border-radius: 50%; background: var(--purple-bg); color: var(--purple-text); display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 500; flex-shrink: 0; }
.kol-info { flex: 1; margin-left: 10px; }
.kol-note { font-size: 11px; color: var(--hint); margin-top: 1px; }
.kol-stats-row { display: flex; gap: 8px; margin-top: 8px; }

/* topic index */
.topic-card { background: var(--surface); border: 0.5px solid var(--border); border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 10px; }
.topic-name { font-size: 15px; font-weight: 500; margin-bottom: 6px; }
.topic-kols { font-size: 12px; color: var(--muted); }

/* empty */
.empty { text-align: center; padding: 3rem; color: var(--hint); font-size: 14px; }
"""


def _nav_html(active: str, root_prefix: str = "") -> str:
    tabs = [("date", "按日期", f"{root_prefix}index.html"),
            ("kol", "按 KOL", f"{root_prefix}kol.html"),
            ("topic", "按话题", f"{root_prefix}topic.html")]
    tabs_html = "".join(
        f'<a href="{url}"><button class="nav-tab {"active" if key == active else ""}">{label}</button></a>'
        for key, label, url in tabs
    )
    return f'''
    <nav class="nav">
      <span class="nav-logo">🤖 AI KOL 日报</span>
      <div class="nav-tabs">{tabs_html}</div>
    </nav>'''


def _page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="wrap">
{body}
</div>
</body>
</html>"""


def _extract_topics(summary: str) -> list[str]:
    """从总结文本里提取话题标签"""
    topic_keywords = {
        "模型发布": ["发布", "release", "launch", "推出", "上线", "新模型", "model"],
        "Vibe Coding": ["vibe cod", "vibecode", "vibe code"],
        "Prompt 工程": ["prompt", "提示词", "提示工程"],
        "AI 创业": ["创业", "startup", "founder", "MRR", "ARR", "产品", "product"],
        "开源项目": ["开源", "open source", "github", "repo"],
        "AI Agent": ["agent", "智能体", "automation", "自动化"],
        "大模型": ["llm", "gpt", "claude", "gemini", "大模型", "opus", "sonnet"],
        "AI 教育": ["教育", "education", "学习", "课程", "lecture"],
        "独立开发": ["indie", "solo", "独立开发", "bootstrapped"],
        "MCP": ["mcp", "model context protocol"],
    }
    text_lower = summary.lower()
    found = []
    for topic, keywords in topic_keywords.items():
        if any(k in text_lower for k in keywords):
            found.append(topic)
    return found[:5]


def _get_first_url(text: str) -> str:
    urls = re.findall(r'https?://[^\s\)\"\']+', text)
    return urls[0] if urls else ""


def build_index_page(archive_dir: Path, web_dir: Path, all_tweets: dict = None):
    web_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for f in sorted(archive_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            entries.append(data)
        except Exception:
            pass

    total_kols = sum(e.get("kol_count", 0) for e in entries[:7])
    total_tweets = sum(e.get("tweet_count", 0) for e in entries[:7])
    total_days = len(entries)

    stats_html = f'''
    <div class="stats">
      <div class="stat"><div class="stat-num">{total_days}</div><div class="stat-label">累计天数</div></div>
      <div class="stat"><div class="stat-num">{total_kols}</div><div class="stat-label">近7日活跃 KOL</div></div>
      <div class="stat"><div class="stat-num">{total_tweets}</div><div class="stat-label">近7日推文</div></div>
    </div>'''

    cards_html = ""
    for e in entries:
        date = e.get("date", "")
        kol_count = e.get("kol_count", 0)
        tweet_count = e.get("tweet_count", 0)
        summary = e.get("summary", "")
        first_line = summary.split("\n")[2] if len(summary.split("\n")) > 2 else ""
        first_line = re.sub(r'[#*\[\]]', '', first_line).strip()[:120]
        topics = _extract_topics(summary)
        topic_tags = "".join(f'<span class="topic-tag">{t}</span>' for t in topics)

        cards_html += f'''
    <a href="{date}.html">
      <div class="day-card">
        <div class="day-header">
          <span class="day-date">{date}</span>
          <div class="day-meta">
            <span class="badge badge-kol">{kol_count} KOL</span>
            <span class="badge badge-tweet">{tweet_count} 条</span>
            <span class="arrow">→</span>
          </div>
        </div>
        <div class="day-summary">{first_line}</div>
        <div class="topics">{topic_tags}</div>
      </div>
    </a>'''

    if not cards_html:
        cards_html = '<div class="empty">暂无存档数据</div>'

    body = _nav_html("date") + stats_html + cards_html
    (web_dir / "index.html").write_text(_page("AI KOL 日报", body), encoding="utf-8")


def build_daily_page(date_str: str, summary: str, web_dir: Path, tweets_data: dict = None):
    web_dir.mkdir(parents=True, exist_ok=True)

    lines = summary.split("\n")
    overview_zh = ""
    overview_en = ""
    kol_blocks = []

    current_kol = None
    current_lines = []
    in_overview = False
    in_kol = False

    for line in lines:
        stripped = line.strip()
        if "整体摘要" in stripped or "Daily Overview" in stripped:
            in_overview = True
            in_kol = False
            continue
        if stripped.startswith("**@") or stripped.startswith("**＠"):
            if current_kol:
                kol_blocks.append((current_kol, "\n".join(current_lines)))
            match = re.match(r'\*\*@?(\w+)[（(](.+?)[)）]\*\*', stripped)
            if match:
                current_kol = (match.group(1), match.group(2))
            else:
                current_kol = (stripped.strip("*@ "), "")
            current_lines = []
            in_overview = False
            in_kol = True
            continue
        if stripped == "---":
            in_overview = False
            continue
        if in_overview:
            if stripped and not overview_zh:
                overview_zh = stripped
            elif stripped and overview_zh and not overview_en:
                overview_en = stripped
        if in_kol and current_kol:
            current_lines.append(line)

    if current_kol:
        kol_blocks.append((current_kol, "\n".join(current_lines)))

    overview_html = f'''
    <div class="overview-box">
      <div class="overview-label">整体摘要</div>
      <div class="overview-text">{overview_zh}</div>
    </div>
    <div class="overview-box" style="margin-top:10px;">
      <div class="overview-label">Daily Overview</div>
      <div class="overview-text">{overview_en}</div>
    </div>''' if overview_zh else f'<div class="overview-box"><div class="overview-text">{md_to_html(summary[:500])}</div></div>'

    kol_html = '<div class="section-title">各 KOL 详情</div>'

    tweets_by_user = {}
    if tweets_data and "tweets" in tweets_data:
        tweets_by_user = tweets_data["tweets"]

    for (username, note), content in kol_blocks:
        avatar_letter = username[0].upper()
        zh_line = ""
        en_line = ""
        for l in content.split("\n"):
            if l.strip().startswith("中文：") and not zh_line:
                zh_line = l.strip()[3:].strip()
            if l.strip().startswith("EN:") and not en_line:
                en_line = l.strip()[3:].strip()

        user_tweets = tweets_by_user.get(username.lower(), [])
        tweets_html = ""
        for t in user_tweets[:5]:
            text = t.get("text", "")
            likes = t.get("likes", 0)
            retweets = t.get("retweets", 0)
            url = _get_first_url(text)
            clean_text = re.sub(r'https?://\S+', '', text).strip()
            link_html = f'<a class="tweet-link" href="{url}" target="_blank">→ {url[:60]}{"..." if len(url)>60 else ""}</a>' if url else ""
            tweets_html += f'''
        <div class="tweet-item">
          <div class="tweet-text">{clean_text}</div>
          {link_html}
          <div class="tweet-stats">♥ {likes:,} &nbsp; ↺ {retweets:,}</div>
        </div>'''

        if not tweets_html and zh_line:
            tweets_html = f'<div class="tweet-item"><div class="tweet-text">{zh_line}</div></div>'

        kol_html += f'''
    <div class="kol-card">
      <div class="kol-header" style="display:flex;align-items:center;gap:10px;">
        <div class="kol-avatar">{avatar_letter}</div>
        <div class="kol-info">
          <div class="kol-name">@{username}</div>
          <div class="kol-note">{note}</div>
        </div>
      </div>
      {tweets_html}
    </div>'''

    body = f'''
    <a class="back-link" href="index.html">← 返回列表</a>
    <div style="margin-bottom:1.5rem;">
      <div style="font-size:22px;font-weight:500;margin-bottom:4px;">{date_str}</div>
      <div style="font-size:13px;color:var(--muted);">AI KOL 日报</div>
    </div>
    {overview_html}
    {kol_html}'''

    content = _nav_html("date") + body
    (web_dir / f"{date_str}.html").write_text(_page(f"AI KOL 日报 {date_str}", content), encoding="utf-8")


def build_kol_page(archive_dir: Path, web_dir: Path, accounts: list):
    web_dir.mkdir(parents=True, exist_ok=True)

    kol_activity = {}
    for f in sorted(archive_dir.glob("*.json"), reverse=True)[:30]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            date = data.get("date", "")
            tweets_file = archive_dir.parent / "today_tweets.json"
        except Exception:
            pass

    cards_html = ""
    for acc in accounts:
        username = acc.get("username", "")
        display = acc.get("display_name", username)
        note = acc.get("note", "")
        avatar_letter = username[0].upper() if username else "?"
        cards_html += f'''
    <a href="https://twitter.com/{username}" target="_blank">
      <div class="kol-index-card">
        <div class="kol-index-header">
          <div class="kol-avatar">{avatar_letter}</div>
          <div class="kol-info">
            <div class="kol-name">@{username}</div>
            <div class="kol-note">{note}</div>
          </div>
          <span class="arrow">→</span>
        </div>
      </div>
    </a>'''

    body = _nav_html("kol") + f'<div style="margin-bottom:1.5rem;font-size:22px;font-weight:500;">KOL 列表</div>' + cards_html
    (web_dir / "kol.html").write_text(_page("KOL 列表 - AI KOL 日报", body), encoding="utf-8")


def build_topic_page(archive_dir: Path, web_dir: Path):
    web_dir.mkdir(parents=True, exist_ok=True)

    topic_map = {}
    for f in sorted(archive_dir.glob("*.json"), reverse=True)[:30]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            date = data.get("date", "")
            summary = data.get("summary", "")
            topics = _extract_topics(summary)
            for t in topics:
                topic_map.setdefault(t, []).append(date)
        except Exception:
            pass

    cards_html = ""
    for topic, dates in sorted(topic_map.items(), key=lambda x: -len(x[1])):
        dates_str = "、".join(dates[:5])
        cards_html += f'''
    <div class="topic-card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
        <span class="topic-name">{topic}</span>
        <span class="badge badge-topic">{len(dates)} 天</span>
      </div>
      <div class="topic-kols">出现于：{dates_str}{"等" if len(dates)>5 else ""}</div>
    </div>'''

    if not cards_html:
        cards_html = '<div class="empty">话题数据积累中，稍后查看</div>'

    body = _nav_html("topic") + f'<div style="margin-bottom:1.5rem;font-size:22px;font-weight:500;">话题汇总</div>' + cards_html
    (web_dir / "topic.html").write_text(_page("话题汇总 - AI KOL 日报", body), encoding="utf-8")
