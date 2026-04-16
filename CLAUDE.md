# AI KOL Daily Digest — Cowork 运行指令

## 你的角色
你是这个项目的执行者。每次运行按以下步骤完整执行，不要跳过任何步骤。

---

## 执行步骤

### Step 1：进入项目目录，安装依赖
```bash
cd ~/kol-radar
pip install requests --break-system-packages -q
```

### Step 2：抓取今日推文
```bash
python src/main.py fetch
```
这会从 Apify 抓取所有 KOL 过去24小时的推文，保存到 `data/today_tweets.json`。

### Step 3：生成总结（你来写）
读取 `data/today_tweets.json`，根据推文内容，生成一份中英双语日报总结。

**总结格式：**

```
【整体摘要 / Daily Overview】

（中文：100-150字，提炼今天3-5个最重要的 AI 话题趋势）

(English: 100-150 words, key AI trends and highlights of the day)

---
【各KOL详情 / KOL Details】

**@username（备注标签）**
中文：一句话说他今天讲了什么
EN: One-sentence English summary

（每个有推文的 KOL 都列一条，没有推文的跳过）
```

生成后将总结内容**保存到 `data/today_summary.md`**。

### Step 4：推送企业微信 + 生成网页
```bash
python src/main.py publish
```
推送企业微信，并在 `web/` 下生成 HTML 存档页面。

### Step 5：提交并推送到 GitHub
```bash
git add data/archive/ docs/ data/today_summary.md
git commit -m "digest: $(date +%Y-%m-%d)"
git push
```
推送完成后 GitHub Pages 会自动更新，网址为：
https://casperit.github.io/ai-kol-radar/

---

## 环境变量
- `APIFY_TOKEN` — Apify API Token
- `WECOM_WEBHOOK_URL` — 企业微信机器人 Webhook URL

## 异常处理
- 某个 KOL 没有推文：跳过，不报错
- 企业微信推送失败：打印错误，继续后续步骤
- Apify 抓取超时：打印警告，用已有数据继续
- git push 失败：打印错误，不影响本地存档
