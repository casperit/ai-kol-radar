"""
生成静态 HTML 存档页面
- docs/index.html        按日期列表
- docs/kol.html          KOL 历史汇总
- docs/topic.html        话题汇总
- docs/YYYY-MM-DD.html   每日详情页
"""

import json, re
from pathlib import Path
from collections import defaultdict

TOPIC_KEYWORDS = {
    "模型发布": ["release", "launch", "发布", "推出", "上线", "新模型", "gpt-5", "claude", "gemini", "opus", "sonnet"],
    "Vibe Coding": ["vibe cod", "vibecode", "vibe code", "vibejam"],
    "Prompt工程": ["prompt", "提示词", "提示工程"],
    "AI创业": ["mrr", "arr", "创业", "startup", "founder", "bootstrapped", "revenue", "收入"],
    "开源项目": ["open source", "开源", "github", "repo", "open-source"],
    "AI Agent": ["agent", "智能体", "agentic", "automation", "自动化"],
    "大模型": ["llm", "large language", "大模型", "benchmark", "reasoning"],
    "AI教育": ["教育", "education", "学习", "course", "lecture", "teach"],
    "独立开发": ["indie", "solo", "独立开发", "side project", "saas"],
    "MCP工具": ["mcp", "model context protocol"],
    "AI研究": ["paper", "research", "study", "论文", "研究"],
    "AI工具": ["tool", "工具", "app", "product", "productivity"],
}

BASE_CSS = """
:root{--bg:#f8f7f4;--surface:#fff;--surface2:#f1efe8;--border:rgba(0,0,0,.08);--border2:rgba(0,0,0,.15);--text:#1a1a18;--muted:#5f5e5a;--hint:#888780;--pur-bg:#eeedfe;--pur-t:#3c3489;--teal-bg:#e1f5ee;--teal-t:#085041;--amber-bg:#faeeda;--amber-t:#633806;--blue-bg:#e6f1fb;--blue-t:#0c447c}
@media(prefers-color-scheme:dark){:root{--bg:#18181a;--surface:#222224;--surface2:#2c2c2e;--border:rgba(255,255,255,.08);--border2:rgba(255,255,255,.15);--text:#e8e8e6;--muted:#a0a09c;--hint:#6a6a66;--pur-bg:#26215c;--pur-t:#cecbf6;--teal-bg:#04342c;--teal-t:#9fe1cb;--amber-bg:#412402;--amber-t:#fac775;--blue-bg:#042c53;--blue-t:#b5d4f4}}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:15px;line-height:1.6}
a{color:inherit;text-decoration:none}
.wrap{max-width:820px;margin:0 auto;padding:2rem 1.25rem 4rem}
.nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:2rem}
.nav-logo{font-size:16px;font-weight:500}
.nav-tabs{display:flex;gap:2px;background:var(--surface2);border-radius:8px;padding:3px}
.nav-tab{font-size:13px;padding:5px 14px;border-radius:6px;color:var(--muted);cursor:pointer;border:none;background:none;transition:all .15s}
.nav-tab.active{background:var(--surface);color:var(--text);font-weight:500}
.nav-tab:hover:not(.active){color:var(--text)}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:2rem}
.stat{background:var(--surface);border:0.5px solid var(--border);border-radius:10px;padding:14px 16px}
.stat-num{font-size:24px;font-weight:500}
.stat-label{font-size:12px;color:var(--muted);margin-top:2px}
.card{background:var(--surface);border:0.5px solid var(--border);border-radius:12px;padding:1.1rem 1.25rem;margin-bottom:10px;transition:border-color .15s}
.card:hover{border-color:var(--border2)}
.card-link{display:flex;align-items:center;justify-content:space-between}
.card-date{font-size:15px;font-weight:500}
.card-meta{display:flex;gap:6px;align-items:center}
.badge{font-size:11px;font-weight:500;padding:2px 8px;border-radius:20px}
.badge-kol{background:var(--pur-bg);color:var(--pur-t)}
.badge-tweet{background:var(--teal-bg);color:var(--teal-t)}
.badge-topic{background:var(--amber-bg);color:var(--amber-t)}
.card-summary{font-size:13px;color:var(--muted);line-height:1.65;margin:8px 0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.tag{font-size:11px;padding:2px 8px;background:var(--surface2);color:var(--hint);border-radius:20px;border:0.5px solid var(--border)}
.arrow{color:var(--hint);margin-left:8px;font-size:16px}
.back{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--muted);margin-bottom:1.5rem}
.back:hover{color:var(--text)}
.page-title{font-size:22px;font-weight:500;margin-bottom:4px}
.page-sub{font-size:13px;color:var(--muted);margin-bottom:1.5rem}
.overview{background:var(--surface2);border-radius:10px;padding:1rem 1.25rem;margin-bottom:1rem}
.overview-label{font-size:11px;color:var(--hint);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;font-weight:500}
.overview-text{font-size:14px;line-height:1.75}
.section-title{font-size:12px;font-weight:500;color:var(--hint);text-transform:uppercase;letter-spacing:.06em;margin:1.5rem 0 .75rem}
.news-item{padding:10px 0;border-bottom:0.5px solid var(--border)}
.news-item:last-child{border-bottom:none}
.news-handle{font-size:12px;color:var(--muted);margin-bottom:4px}
.news-text{font-size:13px;line-height:1.65}
.news-link{font-size:12px;color:var(--blue-t);display:inline-block;margin-top:4px;word-break:break-all}
.news-likes{font-size:11px;color:var(--hint);margin-top:4px}
.kol-card{background:var(--surface);border:0.5px solid var(--border);border-radius:12px;padding:1.1rem 1.25rem;margin-bottom:10px}
.kol-header{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.avatar{width:36px;height:36px;border-radius:50%;background:var(--pur-bg);color:var(--pur-t);display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:500;flex-shrink:0}
.kol-name{font-size:15px;font-weight:500}
.kol-note{font-size:12px;color:var(--hint);margin-top:1px}
.tweet-item{padding:8px 0;border-top:0.5px solid var(--border)}
.tweet-text{font-size:13px;line-height:1.65}
.tweet-link{font-size:12px;color:var(--blue-t);display:inline-block;margin-top:3px;word-break:break-all}
.tweet-stats{font-size:11px;color:var(--hint);margin-top:4px}
.kol-index-card{background:var(--surface);border:0.5px solid var(--border);border-radius:12px;padding:1rem 1.25rem;margin-bottom:8px}
.kol-index-header{display:flex;align-items:center}
.kol-index-info{flex:1;margin-left:10px}
.topic-card{background:var(--surface);border:0.5px solid var(--border);border-radius:12px;padding:1rem 1.25rem;margin-bottom:8px}
.topic-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.topic-name{font-size:15px;font-weight:500}
.topic-dates{font-size:12px;color:var(--muted);line-height:1.6}
.topic-kols{font-size:12px;color:var(--hint);margin-top:4px}
.empty{text-align:center;padding:3rem;color:var(--hint);font-size:14px}
"""

def _page(title, body):
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{BASE_CSS}</style>
</head>
<body><div class="wrap">{body}</div></body>
</html>"""

def _nav(active, prefix=""):
    tabs = [("date","按日期",f"{prefix}index.html"),
            ("kol","按KOL",f"{prefix}kol.html"),
            ("topic","按话题",f"{prefix}topic.html")]
    html = "".join(f'<a href="{u}"><button class="nav-tab {"active" if k==active else ""}">{l}</button></a>' for k,l,u in tabs)
    return f'<nav class="nav"><span class="nav-logo">🤖 AI KOL 日报</span><div class="nav-tabs">{html}</div></nav>'

def _extract_topics(text):
    text_lower = text.lower()
    return [t for t, kws in TOPIC_KEYWORDS.items() if any(k in text_lower for k in kws)]

def _all_archives(archive_dir):
    entries = []
    for f in sorted(archive_dir.glob("*.json"), reverse=True):
        try:
            entries.append(json.loads(f.read_text(encoding="utf-8")))
        except:
            pass
    return entries


# ── 按日期首页 ──────────────────────────────────────────────────────────

def build_index_page(archive_dir, web_dir):
    web_dir.mkdir(parents=True, exist_ok=True)
    entries = _all_archives(archive_dir)

    recent7 = entries[:7]
    total_kols = sum(e.get("kol_count", 0) for e in recent7)
    total_tweets = sum(e.get("tweet_count", 0) for e in recent7)

    stats = f"""<div class="stats">
      <div class="stat"><div class="stat-num">{len(entries)}</div><div class="stat-label">累计天数</div></div>
      <div class="stat"><div class="stat-num">{total_kols}</div><div class="stat-label">近7日活跃KOL</div></div>
      <div class="stat"><div class="stat-num">{total_tweets}</div><div class="stat-label">近7日推文</div></div>
    </div>"""

    cards = ""
    for e in entries:
        date = e.get("date","")
        kol_count = e.get("kol_count", 0)
        tweet_count = e.get("tweet_count", 0)
        summary = e.get("summary","")
        # 提取中文摘要第一段
        first = ""
        for line in summary.split("\n"):
            line = line.strip()
            if line and not line.startswith("【") and not line.startswith("(") and not line.startswith("-") and not line.startswith("*") and len(line) > 20:
                first = line[:120]
                break
        topics = _extract_topics(summary)[:5]
        tag_html = "".join(f'<span class="tag">{t}</span>' for t in topics)
        cards += f"""<a href="{date}.html"><div class="card">
          <div class="card-link">
            <span class="card-date">{date}</span>
            <div class="card-meta">
              <span class="badge badge-kol">{kol_count} KOL</span>
              <span class="badge badge-tweet">{tweet_count} 条</span>
              <span class="arrow">→</span>
            </div>
          </div>
          <div class="card-summary">{first}</div>
          <div class="tags">{tag_html}</div>
        </div></a>"""

    if not cards:
        cards = '<div class="empty">暂无存档</div>'

    body = _nav("date") + stats + cards
    (web_dir / "index.html").write_text(_page("AI KOL 日报", body), encoding="utf-8")


# ── 每日详情页 ──────────────────────────────────────────────────────────

def build_daily_page(date_str, digest_data, web_dir):
    web_dir.mkdir(parents=True, exist_ok=True)

    # 整体摘要：从 today_summary.md 读取概览部分
    summary_file = web_dir.parent / "data" / "today_summary.md"
    overview_zh, overview_en = "", ""
    if summary_file.exists():
        summary = summary_file.read_text(encoding="utf-8")
        lines = summary.split("\n")
        collecting = False
        for line in lines:
            stripped = line.strip()
            if "整体摘要" in stripped or "Daily Overview" in stripped:
                collecting = True
                continue
            if stripped == "---":
                break
            if collecting and stripped and not stripped.startswith("【"):
                if not overview_zh and not stripped.startswith("("):
                    overview_zh = stripped
                elif not overview_en and stripped.startswith("("):
                    overview_en = stripped.strip("()")

    overview_html = ""
    if overview_zh:
        overview_html += f'<div class="overview"><div class="overview-label">整体摘要</div><div class="overview-text">{overview_zh}</div></div>'
    if overview_en:
        overview_html += f'<div class="overview" style="margin-top:8px"><div class="overview-label">Daily Overview</div><div class="overview-text">{overview_en}</div></div>'

    # 行业新闻
    news_html = '<div class="section-title">行业新闻 / Industry News</div>'
    news_items = digest_data.get("news", [])
    if news_items:
        news_html += '<div class="card">'
        for n in news_items:
            handle = n.get("author_handle","")
            text = n.get("text","")
            likes = n.get("likes",0)
            links = n.get("links",[])
            link_html = f'<a class="news-link" href="{links[0]}" target="_blank">→ {links[0][:60]}{"..." if len(links[0])>60 else ""}</a>' if links else ""
            news_html += f"""<div class="news-item">
              <div class="news-handle">@{handle}</div>
              <div class="news-text">{text}</div>
              {link_html}
              <div class="news-likes">♥ {likes:,}</div>
            </div>"""
        news_html += "</div>"
    else:
        news_html += '<div class="empty" style="padding:1rem">今日无符合条件的行业新闻</div>'

    # KOL 详情
    kol_html = '<div class="section-title">各KOL详情 / KOL Details</div>'
    for kol in digest_data.get("kols", []):
        username = kol.get("username","")
        note = kol.get("note","")
        av = username[0].upper() if username else "?"
        tweets_html = ""
        for t in kol.get("tweets",[]):
            text = t.get("text","")
            likes = t.get("likes",0)
            retweets = t.get("retweets",0)
            links = t.get("links",[])
            link_html = f'<a class="tweet-link" href="{links[0]}" target="_blank">→ {links[0][:60]}{"..." if len(links[0])>60 else ""}</a>' if links else ""
            tweets_html += f"""<div class="tweet-item">
              <div class="tweet-text">{text}</div>
              {link_html}
              <div class="tweet-stats">♥ {likes:,} &nbsp; ↺ {retweets:,}</div>
            </div>"""
        kol_html += f"""<div class="kol-card">
          <div class="kol-header">
            <div class="avatar">{av}</div>
            <div>
              <div class="kol-name">@{username}</div>
              <div class="kol-note">{note}</div>
            </div>
          </div>
          {tweets_html}
        </div>"""

    body = f"""{_nav("date")}
    <a class="back" href="index.html">← 返回列表</a>
    <div class="page-title">{date_str}</div>
    <div class="page-sub">AI KOL 日报</div>
    {overview_html}
    {news_html}
    {kol_html}"""

    (web_dir / f"{date_str}.html").write_text(_page(f"AI KOL 日报 {date_str}", body), encoding="utf-8")


# ── 按KOL页面 ──────────────────────────────────────────────────────────

def build_kol_page(archive_dir, web_dir, accounts):
    web_dir.mkdir(parents=True, exist_ok=True)
    entries = _all_archives(archive_dir)

    # 统计每个KOL出现的天数
    kol_days = defaultdict(list)
    for e in entries:
        date = e.get("date","")
        summary = e.get("summary","")
        # 从summary里找出现了哪些KOL
        for acc in accounts:
            username = acc.get("username","")
            if f"@{username}" in summary:
                kol_days[username].append(date)

    cards = ""
    for acc in accounts:
        username = acc.get("username","")
        note = acc.get("note","")
        days = kol_days.get(username, [])
        av = username[0].upper() if username else "?"
        day_count = len(days)
        latest = days[0] if days else "暂无记录"

        # 点击跳转到最新出现的日报，而不是 Twitter
        link = f"{latest}.html" if days else "index.html"
        cards += f"""<a href="{link}"><div class="kol-index-card">
          <div class="kol-index-header">
            <div class="avatar">{av}</div>
            <div class="kol-index-info">
              <div class="kol-name">@{username}</div>
              <div class="kol-note">{note}</div>
            </div>
            <div style="margin-left:auto;text-align:right">
              <div class="badge badge-kol" style="display:inline-block">{day_count} 天活跃</div>
              <div style="font-size:11px;color:var(--hint);margin-top:4px">最近：{latest}</div>
            </div>
          </div>
        </div></a>"""

    if not cards:
        cards = '<div class="empty">暂无数据</div>'

    body = f"""{_nav("kol")}
    <div class="page-title">KOL 列表</div>
    <div class="page-sub">{len(accounts)} 位追踪中的 AI 领域 KOL</div>
    {cards}"""

    (web_dir / "kol.html").write_text(_page("KOL 列表 - AI KOL 日报", body), encoding="utf-8")


# ── 按话题页面 ──────────────────────────────────────────────────────────

def build_topic_page(archive_dir, web_dir):
    web_dir.mkdir(parents=True, exist_ok=True)
    entries = _all_archives(archive_dir)

    # 统计每个话题出现的日期 + 相关KOL
    topic_data = defaultdict(lambda: {"dates": [], "kols": set()})
    for e in entries:
        date = e.get("date","")
        summary = e.get("summary","")
        topics = _extract_topics(summary)
        for t in topics:
            topic_data[t]["dates"].append(date)
            # 找出当天提到这个话题的KOL
            for line in summary.split("\n"):
                if line.strip().startswith("**@") and any(kw in summary[summary.find(line):summary.find(line)+500].lower() for kw in TOPIC_KEYWORDS.get(t,[])):
                    m = re.match(r'\*\*@(\w+)', line.strip())
                    if m:
                        topic_data[t]["kols"].add(m.group(1))

    cards = ""
    for topic, data in sorted(topic_data.items(), key=lambda x: -len(x[1]["dates"])):
        dates = data["dates"]
        kols = list(data["kols"])[:5]
        dates_str = "、".join(dates[:5]) + ("等" if len(dates)>5 else "")
        kol_str = " ".join(f"@{k}" for k in kols) if kols else ""
        # 点击跳转到最新出现的日报
        link = f"{dates[0]}.html" if dates else "index.html"
        cards += f"""<a href="{link}"><div class="topic-card">
          <div class="topic-header">
            <span class="topic-name">{topic}</span>
            <span class="badge badge-topic">{len(dates)} 天</span>
          </div>
          <div class="topic-dates">出现于：{dates_str}</div>
          {"<div class='topic-kols'>相关KOL：" + kol_str + "</div>" if kol_str else ""}
        </div></a>"""

    if not cards:
        cards = '<div class="empty">话题数据积累中，每日运行后自动更新</div>'

    body = f"""{_nav("topic")}
    <div class="page-title">话题汇总</div>
    <div class="page-sub">基于历史日报自动提取的话题趋势</div>
    {cards}"""

    (web_dir / "topic.html").write_text(_page("话题汇总 - AI KOL 日报", body), encoding="utf-8")
