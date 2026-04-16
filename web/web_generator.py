"""
生成静态 HTML 存档页面
- web/index.html     历史列表首页
- web/YYYY-MM-DD.html  每日详情页
"""

import json
import re
from pathlib import Path


def markdown_to_html(text: str) -> str:
    """简单 Markdown → HTML 转换"""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^---$', r'<hr>', text, flags=re.MULTILINE)
    lines = text.split('\n')
    html_lines = []
    for line in lines:
        if line.startswith('<h') or line.strip() == '<hr>':
            html_lines.append(line)
        elif line.strip() == '':
            html_lines.append('<br>')
        else:
            html_lines.append(f'<p>{line}</p>')
    return '\n'.join(html_lines)


CSS = """
:root {
  --bg: #0f1117;
  --card: #1a1d27;
  --border: #2a2d3a;
  --text: #e2e8f0;
  --muted: #94a3b8;
  --accent: #6366f1;
  --accent2: #8b5cf6;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  line-height: 1.7;
  padding: 2rem 1rem;
}
.container { max-width: 860px; margin: 0 auto; }
header {
  text-align: center;
  margin-bottom: 3rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid var(--border);
}
header h1 {
  font-size: 2rem;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: .5rem;
}
header p { color: var(--muted); font-size: .95rem; }
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.8rem;
  margin-bottom: 1.2rem;
  transition: border-color .2s;
}
.card:hover { border-color: var(--accent); }
.card a {
  display: flex;
  justify-content: space-between;
  align-items: center;
  text-decoration: none;
  color: var(--text);
}
.card .date { font-size: 1.1rem; font-weight: 600; }
.card .meta { color: var(--muted); font-size: .9rem; }
.card .arrow { color: var(--accent); font-size: 1.3rem; }
.content { line-height: 1.9; }
.content h1 { font-size: 1.4rem; color: var(--accent); margin: 1.5rem 0 .8rem; }
.content h2 { font-size: 1.2rem; margin: 1.2rem 0 .6rem; }
.content p { margin-bottom: .6rem; color: var(--text); }
.content hr { border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }
.content strong { color: #a5b4fc; }
.back {
  display: inline-block;
  margin-bottom: 2rem;
  color: var(--accent);
  text-decoration: none;
  font-size: .9rem;
}
.back:hover { text-decoration: underline; }
.badge {
  display: inline-block;
  background: rgba(99,102,241,.15);
  color: var(--accent);
  border-radius: 6px;
  padding: .1rem .5rem;
  font-size: .8rem;
  margin-left: .5rem;
}
"""


def build_daily_page(date_str: str, summary: str, web_dir: Path):
    web_dir.mkdir(parents=True, exist_ok=True)
    content_html = markdown_to_html(summary)
    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI KOL 日报 {date_str}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <a class="back" href="index.html">← 返回历史列表</a>
  <header>
    <h1>🤖 AI KOL 日报</h1>
    <p>{date_str}</p>
  </header>
  <div class="card">
    <div class="content">{content_html}</div>
  </div>
</div>
</body>
</html>"""
    out = web_dir / f"{date_str}.html"
    out.write_text(html, encoding="utf-8")


def build_index_page(archive_dir: Path, web_dir: Path):
    web_dir.mkdir(parents=True, exist_ok=True)

    # 读取所有存档
    entries = []
    for f in sorted(archive_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            entries.append(data)
        except Exception:
            pass

    cards_html = ""
    for e in entries:
        date = e.get("date", "")
        kol_count = e.get("kol_count", 0)
        tweet_count = e.get("tweet_count", 0)
        cards_html += f"""
  <div class="card">
    <a href="{date}.html">
      <div>
        <div class="date">{date}</div>
        <div class="meta">{kol_count} 位 KOL <span class="badge">{tweet_count} 条推文</span></div>
      </div>
      <div class="arrow">→</div>
    </a>
  </div>"""

    if not cards_html:
        cards_html = '<div class="card"><p style="color:var(--muted)">暂无存档数据</p></div>'

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI KOL 日报 - 历史存档</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🤖 AI KOL 日报</h1>
    <p>42位 AI 领域 KOL 每日动态追踪</p>
  </header>
  {cards_html}
</div>
</body>
</html>"""
    (web_dir / "index.html").write_text(html, encoding="utf-8")
