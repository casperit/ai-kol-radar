# AI KOL Daily Digest — Routine 运行指令

## 你的角色
你是这个项目的执行者。每次运行按以下步骤完整执行，不要跳过任何步骤。

---

## 执行步骤

### Step 1：安装依赖
```bash
pip install requests --break-system-packages -q
```

### Step 2：抓取推文并生成草稿
```bash
python src/main.py fetch
python src/main.py build_prompt
```
完成后会生成 `data/today_prompt.txt`，这是一个带骨架的草稿文件，推文原文已经填好。

### Step 3：填写总结（你来做）
读取 `data/today_prompt.txt`，将文件中所有 `[TODO]` 替换为实际内容：

- `[TODO: 中文150字...]` → 写整体中文摘要
- `[TODO: English 100 words...]` → 写整体英文摘要
- `[TODO: 中文一句话摘要]` → 每条新闻写一句中文说明
- `[TODO: #标签1 #标签2]` → 从预设标签选2-3个
- `[TODO: 1-2句话说核心内容和观点]` → 每个KOL写中文总结
- `[TODO: 1-2 sentences]` → 每个KOL写英文总结

预设话题标签：#模型发布 #Vibe编程 #Prompt工程 #AI创业 #开源项目 #AI智能体 #大模型 #AI教育 #独立开发 #MCP工具 #AI工具 #AI研究

填完后将完整内容**保存到 `data/today_summary.md`**（不是修改 today_prompt.txt）。

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
