# AI KOL Daily Digest — Routine 运行指令

## 你的角色
你是这个项目的执行者。每次运行按以下步骤完整执行，不要跳过任何步骤。

---

## 执行步骤

### Step 1：安装依赖
```bash
pip install requests --break-system-packages -q
```

### Step 2：抓取今日推文
```bash
python src/main.py fetch
```
从 Apify 抓取所有 KOL 过去24小时的推文，保存到 `data/today_tweets.json`。

### Step 3：生成总结（你来写）
读取 `data/today_tweets.json`，根据推文内容，生成一份详细的中英双语日报总结。

**总结格式要求：**

```
【整体摘要 / Daily Overview】

（中文：200字左右，提炼今天最重要的3-5个话题趋势，要有观点，不要流水账）

(English: 150 words, key AI trends and highlights, with your own perspective)

---
【各KOL详情 / KOL Details】

**@username（备注标签）**
话题标签：#标签1 #标签2 #标签3
中文：2-4句话，详细说明他今天发了什么，核心观点是什么，有什么值得关注的
EN: 2-4 sentences summary in English
推文原文摘录：
- "推文关键内容1"（保留原文，如有链接一并保留：https://...）
- "推文关键内容2"（保留原文）

（每个有推文的 KOL 都列一条，没有推文的跳过）
```

**注意：**
- 每个 KOL 的内容要详细，不要只写一句话
- 推文里的链接必须保留，放在对应推文后面
- 话题标签从以下选择：#模型发布 #Vibe编程 #Prompt工程 #AI创业 #开源项目 #AI智能体 #大模型 #AI教育 #独立开发 #MCP工具 #AI工具 #AI研究
- 如果推文内容很少或不重要，可以简短处理，但不要捏造内容

生成后将总结内容**保存到 `data/today_summary.md`**。

### Step 4：用 Gmail connector 发送邮件
直接用 Gmail connector 发送邮件，不要用 Python SMTP：
- 收件人：$GMAIL_TO
- 主题：🤖 AI KOL 日报 {今天日期}
- 正文：`data/today_summary.md` 的完整内容
- 末尾附上：查看网页版 → https://casperit.github.io/ai-kol-radar/

### Step 5：生成网页存档
```bash
python src/main.py publish_web
```

### Step 6：提交并推送到 main 分支
```bash
git add data/archive/ docs/ data/today_summary.md data/today_tweets.json
git commit -m "digest: $(date +%Y-%m-%d)"
git push origin HEAD:main
```
**注意：必须推送到 main 分支，不要推到其他分支。**

---

## 环境变量
- `APIFY_TOKEN` — Apify API Token
- `GMAIL_TO` — 收件人邮箱

## 异常处理
- 某个 KOL 没有推文：跳过，不报错
- 邮件发送失败：打印错误，继续后续步骤
- Apify 抓取超时：打印警告，用已有数据继续
- git push 失败：打印错误，不影响本地存档
