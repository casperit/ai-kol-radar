# AI KOL Daily Digest — Routine 运行指令

## 你的角色
你是这个项目的执行者。每次运行按以下步骤完整执行，不要跳过任何步骤。

---

## 执行步骤

### Step 1：安装依赖
```bash
pip install requests --break-system-packages -q
```

### Step 2：抓取推文并预处理
```bash
python src/main.py fetch
```
这一步会：
1. 从 Apify 抓取所有 KOL 过去24小时的推文（原始数据 → `data/today_tweets.json`）
2. 抓取 AI 行业热门新闻
3. 自动压缩筛选（A+C方案）→ 生成精简版 `data/today_digest.json`

**你只需要读 `data/today_digest.json`，不要读原始的 today_tweets.json，原始文件太大会超时。**

### Step 3：生成总结（你来写）
读取 `data/today_digest.json`，生成一份详细的中英双语日报总结。

数据结构说明：
- `kols`：每个 KOL 的精选推文（已按点赞排序，每人最多5条，正文截断到150字，链接单独保留）
- `news`：点赞300+的行业新闻（最多50条，已去重排序）
- `stats`：统计数据

**总结格式：**

```
【整体摘要 / Daily Overview】

（中文：200字左右，提炼今天最重要的3-5个话题趋势，要有观点不要流水账）

(English: 150 words, key AI trends and highlights, with your own perspective)

---
【行业新闻 / Industry News】

从 news 字段提炼今日最重要的5-8条，格式：
- **事件摘要**：一句话说清楚，如有链接 → https://...（来源：@handle，♥ 点赞数）

---
【各KOL详情 / KOL Details】

**@username（备注标签）**
话题标签：#标签1 #标签2
中文：2-4句话，说明今天的核心观点和内容
EN: 2-4 sentences English summary
推文摘录：
- "推文内容"（链接：https://... 如有）♥ 点赞数

（每个有推文的 KOL 都列一条，没有推文的跳过）
```

**注意：**
- 行业新闻和 KOL 内容分开，不要混在一起
- links 字段里的链接必须保留，放在对应内容后面
- 话题标签从以下选：#模型发布 #Vibe编程 #Prompt工程 #AI创业 #开源项目 #AI智能体 #大模型 #AI教育 #独立开发 #MCP工具 #AI工具 #AI研究
- 不要捏造内容

生成后将总结内容**保存到 `data/today_summary.md`**。

### Step 4：用 Gmail connector 发送邮件
直接用 Gmail connector 发送邮件：
- 收件人：$GMAIL_TO
- 主题：🤖 AI KOL 日报 {今天日期}
- 正文：`data/today_summary.md` 的完整内容
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
