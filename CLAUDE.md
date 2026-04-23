# AI KOL Daily Digest — Routine 运行指令

## 你的角色
你是这个项目的执行者。每次运行按以下步骤完整执行。

---

## 执行步骤

### Step 1：安装依赖
```bash
pip install requests --break-system-packages -q
```

### Step 2：抓取数据
```bash
python src/main.py fetch
```
抓取所有 KOL 推文 + 行业新闻，自动生成 `data/today_digest.json`。

### Step 3：生成总结
```bash
python src/main.py summarize
```
自动完成：
- 调用 Claude API 生成整体摘要（中英双语）
- Python 整理 KOL 详情和行业新闻
- 保存到 `data/today_summary.md`

### Step 4：用 Gmail connector 发送邮件
读取 `data/today_summary.md` 完整内容，用 Gmail connector 发送：
- 收件人：$GMAIL_TO
- 主题：🤖 AI KOL 日报 {今天日期}
- 正文：today_summary.md 完整内容
- 末尾：查看网页版 → https://casperit.github.io/ai-kol-radar/

### Step 5：生成网页存档
```bash
python src/main.py publish_web
```

### Step 6：提交并推送到 main 分支
```bash
git add data/archive/ docs/ data/today_summary.md data/today_tweets.json data/today_digest.json
git commit -m "digest: $(date +%Y-%m-%d)"
git push origin HEAD:main
```

---

## 环境变量
- `APIFY_TOKEN` — Apify API Token
- `ANTHROPIC_API_KEY` — Claude API Key（用于生成整体摘要）
- `GMAIL_TO` — 收件人邮箱

## 异常处理
- Claude API 失败：自动用备用摘要，继续执行
- 行业新闻查询失败：跳过继续
- 邮件发送失败：打印错误，继续后续步骤
- git push 失败：打印错误，不影响本地存档
