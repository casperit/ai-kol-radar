# AI KOL Daily Digest — Routine 运行指令

## 你的角色
你是这个项目的执行者。每次运行按以下步骤完整执行。

---

## 执行步骤

### Step 1：安装依赖
```bash
pip install requests anthropic --break-system-packages -q
```

### Step 2：抓取数据
```bash
python src/main.py fetch
```

### Step 3：生成总结
```bash
python src/main.py summarize
```
自动生成 `data/today_summary.md`。

### Step 4：用 Gmail connector 发送邮件
读取 `data/today_summary.md`，只取**前1000字**（整体摘要部分），用 Gmail connector **直接发送邮件（send，不是创建草稿）**：
- 收件人：$GMAIL_TO
- 主题：🤖 AI KOL 日报 {今天日期}
- 正文：today_summary.md 的前1000字 + "\n\n查看完整日报 → https://casperit.github.io/ai-kol-radar/"

**重要：必须直接发送，不要创建草稿（draft）。**

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
- `ANTHROPIC_API_KEY` — Claude API Key
- `GMAIL_TO` — 收件人邮箱

## 异常处理
- Claude API 失败：用备用摘要继续
- 邮件发送失败：打印错误，继续后续步骤
- git push 失败：打印错误，不影响本地存档
