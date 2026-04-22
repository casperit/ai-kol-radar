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
python src/main.py build_prompt
```
第一条命令抓取数据并生成 `data/today_digest.json`。
第二条命令把数据转成紧凑文本 `data/today_prompt.txt`，这是你生成总结的数据源。

### Step 3：生成总结
读取 `data/today_prompt.txt`，根据里面的内容生成完整日报，**保存到 `data/today_summary.md`**。

文件格式说明：
- `=== AI KOL 日报数据 ===` 开头是统计信息
- `--- 行业新闻 ---` 是 AI 行业热点推文
- `--- KOL 推文 ---` 是各 KOL 的推文，格式为 `[@handle 备注]` + `♥点赞数 推文内容 | 链接`

**日报格式：**

```
【整体摘要 / Daily Overview】

（中文：150字，提炼今天3-5个最重要的AI话题趋势，要有观点）

(English: 100 words, key AI trends with your perspective)

---
【行业新闻 / Industry News】

- **事件摘要**：一句话 → 链接（如有）（@handle ♥点赞数）

（选最重要的5-8条）

---
【各KOL详情 / KOL Details】

**@username（备注）**
话题：#标签1 #标签2
中文：1-2句话说核心内容和观点
EN: 1-2 sentences
摘录："推文内容" → 链接（如有）♥点赞数

（每个有推文的 KOL 都列一条，没有推文的跳过）
```

话题标签从以下选：#模型发布 #Vibe编程 #Prompt工程 #AI创业 #开源项目 #AI智能体 #大模型 #AI教育 #独立开发 #MCP工具 #AI工具 #AI研究

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
git add data/archive/ docs/ data/today_summary.md data/today_tweets.json data/today_digest.json data/today_prompt.txt
git commit -m "digest: $(date +%Y-%m-%d)"
git push origin HEAD:main
```

---

## 环境变量
- `APIFY_TOKEN` — Apify API Token
- `GMAIL_TO` — 收件人邮箱

## 异常处理
- 某个 KOL 没有推文：跳过
- 行业新闻查询失败：跳过继续
- 邮件发送失败：打印错误，继续后续步骤
- git push 失败：打印错误，不影响本地存档
