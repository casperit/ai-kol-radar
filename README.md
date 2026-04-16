# 🤖 AI KOL Daily Digest

自动抓取 42 位 AI 领域 KOL 的 Twitter 动态，每日生成中英双语总结，推送到企业微信，并生成静态网页存档。

## 架构

```
Claude Code Routine（每天北京时间 08:00，云端自动触发）
  └→ Apify 抓取各 KOL 过去24h推文
  └→ Claude API 生成中英双语总结
  └→ 企业微信 Webhook 推送
  └→ 生成 HTML 存档 → commit 到 GitHub → GitHub Pages
```

## 部署步骤

### 1. 把代码推到 GitHub

```bash
git init
git add .
git commit -m "init"
git remote add origin https://github.com/你的用户名/ai-kol-digest.git
git push -u origin main
```

### 2. 开启 GitHub Pages

仓库 → Settings → Pages → Source 选 `main` 分支，目录选 `/web`

### 3. 创建 Claude Code Routine

打开 claude.ai/code/routines，点 **+ New Routine**，填写：

| 字段 | 内容 |
|------|------|
| Name | AI KOL Daily Digest |
| Repository | 选择刚推上去的 repo |
| Schedule | Daily，08:00（本地时区） |
| Prompt | 按照 CLAUDE.md 的说明运行今日 AI KOL 日报任务 |

### 4. 配置环境变量

在 Routine 设置的 Environment 部分添加：

| 变量名 | 获取方式 |
|--------|----------|
| APIFY_TOKEN | apify.com → Settings → API & Integrations |
| ANTHROPIC_API_KEY | console.anthropic.com |
| WECOM_WEBHOOK_URL | 企业微信群 → 添加机器人 → 复制 Webhook |

### 5. 手动测试

Routine 页面点 Run now，看日志是否正常。

## 文件结构

```
├── CLAUDE.md              # Routine 运行指令（核心）
├── src/
│   ├── main.py            # 主流程
│   └── web_generator.py   # HTML 生成
├── data/
│   ├── accounts.json      # KOL 列表（42人）
│   └── archive/           # 每日 JSON 存档
└── web/                   # 静态网页 → GitHub Pages
```

## 成本估算

| 服务 | 费用 |
|------|------|
| Apify | ~$1.8/月，免费额度覆盖 |
| Claude API | < $1/月 |
| Claude Code Routine | 订阅内免费（Pro 限5次/天） |
| GitHub Pages | 免费 |
