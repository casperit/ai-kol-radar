# AI KOL Daily Digest — Routine 运行指令

## 你的角色
你是这个项目的执行者。每次运行按以下步骤完整执行，不要跳过任何步骤。

---

## 执行步骤

### Step 1：安装依赖
```bash
pip install requests --break-system-packages -q
```

### Step 2：抓取今日推文 + 行业新闻
```bash
python src/main.py fetch
```
从 Apify 抓取：
1. 所有 KOL 过去24小时的推文
2. AI 行业热门新闻（按关键词搜索）

结果保存到 `data/today_tweets.json`，包含 `tweets`（KOL）和 `news`（行业新闻）两个字段。

### Step 3：生成总结（你来写）
读取 `data/today_tweets.json`，生成一份详细的中英双语日报总结。

**总结格式：**

```
【整体摘要 / Daily Overview】

（中文：200字左右，提炼今天最重要的3-5个话题趋势，要有观点）

(English: 150 words, key AI trends and highlights, with your own perspective)

---
【行业新闻 / Industry News】

根据 news 字段里的内容，提炼今日 AI 行业最重要的5-8条新闻，格式：

- **新闻标题**：一句话说明事件，如有链接附上 → https://...
  来源：@handle（点赞数）

---
【各KOL详情 / KOL Details】

**@username（备注标签）**
话题标签：#标签1 #标签2
中文：2-4句话，详细说明他今天发了什么，核心观点是什么
EN: 2-4 sentences English summary
推文摘录：
- "推文关键内容"（如有链接：https://...）

（每个有推文的 KOL 都列一条，没有推文的跳过）
```

**注意：**
- 行业新闻和 KOL 内容要分开，不要混在一起
- 推文里的链接必须保留
- 话题标签从以下选：#模型发布 #Vibe编程 #Prompt工程 #AI创业 #开源项目 #AI智能体 #大模型 #AI教育 #独立开发 #MCP工具 #AI工具 #AI研究
- 不要捏造内容，数据里没有的不要写

生成后将总结内容**保存到 `data/today_summary.md`**。

### Step 4：用 Gmail connector 发送邮件
直接用 Gmail connector 发送邮件：
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
**注意：必须推送到 main 分支。**

---

## 环境变量
- `APIFY_TOKEN` — Apify API Token
- `GMAIL_TO` — 收件人邮箱

## 异常处理
- 某个 KOL 没有推文：跳过
- 行业新闻某个查询失败：跳过，继续其他查询
- 邮件发送失败：打印错误，继续后续步骤
- git push 失败：打印错误，不影响本地存档
