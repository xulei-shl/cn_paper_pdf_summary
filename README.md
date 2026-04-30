# 论文 PDF 摘要工作流

按论文标题执行单篇处理的PDF全文总结工作流。

## 当前能力

- 按标题下载 PDF
- 校验下载文件名与标题是否匹配
- 调用 HiAgent 生成 Markdown 摘要
- 可选上传到 HiAgent RAG、LIS-RSS、Memos、Blinko
- 本地通知分发
  - 错误默认推送到 Telegram
  - 成功日志按 `.env` 控制是否推送到 Telegram
  - 成功结果按 `.env` 控制是否推送到 Telegram / 企业微信

## 目录概览

```text
paper-pdf-summary/
├── api.py
├── main.py
├── config/
│   └── config.yaml
├── download/
├── logs/
├── pdf-download/
├── pdf-summary/
├── summary-update/
├── telegram-bot/
├── tests/
├── utils/
├── wechat/
└── .env.example
```

## 环境准备

### Python

建议 Python 3.12+。

安装依赖：

```bash
pip install -r requirements.txt
```

如果下载链路依赖 Playwright / Camoufox，还需要安装浏览器：

```bash
playwright install chromium
```

Linux 下如遇 `pyperclip` 缺少复制机制：

```bash
sudo apt-get install xclip
```

### Telegram Bot

进入 [telegram-bot](F:/Github/cn_paper_pdf_summary/telegram-bot) 安装 Node.js 依赖：

```bash
cd telegram-bot
npm install
```

## 配置

复制 [.env.example](F:/Github/cn_paper_pdf_summary/.env.example) 为 `.env`，按需填写。

最常用配置：

```env
MEMOS_BASE_URL=https://your-memos-instance.com
MEMOS_ACCESS_TOKEN=memos_pat_your_token_here

BLINKO_BASE_URL=https://your-blinko-instance.com
BLINKO_API_KEY=your_blinko_api_key_here

LIS_RSS_API_URL=https://your-lis-rss.com
LIS_RSS_USERNAME=your_username
LIS_RSS_PASSWORD=your_password

HIAGENT_PDF_URL=https://your-hiagent-pdf-url.com
WorkspaceType=personal
WorkspaceID=your_workspace_id
DatasetID=your_dataset_id

WECHAT_WEBHOOK_KEY=your_wechat_webhook_key_here
PDF_SUMMARY_PUSH_WECHAT=false

TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_USER_ID=your_telegram_user_id
TELEGRAM_NOTIFY_CHAT_ID=your_telegram_chat_id
PDF_SUMMARY_PUSH_TELEGRAM_LOG=false
PDF_SUMMARY_PUSH_TELEGRAM_RESULT=false
TELEGRAM_API_URL=http://localhost:8081
TELEGRAM_API_TIMEOUT=300
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

通知相关语义：

- `PDF_SUMMARY_PUSH_WECHAT=false`
  - 默认不推送成功结果到企业微信
  - Telegram `/papers ... --wechat` 或 API `push_wechat=true` 可强制开启本次推送
- `PDF_SUMMARY_PUSH_TELEGRAM_LOG`
  - 仅控制 CLI / API 成功日志是否主动推送到 Telegram
  - 不影响 Telegram Bot `/papers` 的固定结束日志
- `PDF_SUMMARY_PUSH_TELEGRAM_RESULT`
  - 控制所有入口的成功结果正文是否主动推送到 Telegram
- 错误通知不受上述开关影响
  - 关键失败会默认尝试推送到 Telegram

## config.yaml

[config/config.yaml](F:/Github/cn_paper_pdf_summary/config/config.yaml) 当前只保留直连模式必需配置。

主要字段：

```yaml
storage:
  download_root: "download"
  logs_root: "logs"

pdf_download:
  priority_scripts:
    - "pdf-download/zhesheke_pdf_download.py"
    - "pdf-download/wanfang_pdf_download.py"
    - "pdf-download/cnki_pdf_download.py"
  max_retries: 1
  match_threshold: 0

pdf_summary:
  script: "pdf-summary/hiagent_upload.py"
  delete_pdf: true

summary_upload:
  hiagent_rag:
    enabled: false
  lis_rss:
    enabled: false
  memos:
    enabled: true
  blinko:
    enabled: true
  wechat:
    timeout: 30
    max_retries: 2
```

说明：

- `summary_upload.*.enabled` 控制上传子系统是否启用
- `summary_upload.wechat` 不控制是否发送
  - 是否发送只看 `.env` 的 `PDF_SUMMARY_PUSH_WECHAT` 和运行参数

## 命令行用法

当前 [main.py](F:/Github/cn_paper_pdf_summary/main.py) 单篇处理。

```bash
python main.py --title "论文题名"
```

可选参数：

- `--id`
  - legacy 可选参数
  - 传入时执行 LIS-RSS 上传
  - 不传时跳过 LIS-RSS 上传
- `--skip-wechat`
  - 跳过企业微信成功结果推送
- `--stop-after-summary`
  - 只执行到摘要生成
  - 成功时输出 `SUMMARY_SUCCESS|...`

示例：

```bash
python main.py --title "Attention Is All You Need"
python main.py --title "Attention Is All You Need" --id 123
python main.py --title "Attention Is All You Need" --skip-wechat
python main.py --title "Attention Is All You Need" --stop-after-summary
```

## API 用法

启动 API：

```bash
uvicorn api:app --host 0.0.0.0 --port 8081
```

接口：

- `POST /process`
- `GET /health`

请求示例：

```json
{
  "title": "Deep Learning for Computer Vision",
  "id": 123,
  "push_wechat": false
}
```

字段说明：

- `title`
  - 必填
- `id`
  - legacy 可选字段
  - 传入时执行 LIS-RSS 上传
- `push_wechat`
  - 强制启用本次企业微信成功结果推送

调用示例：

```bash
curl -X POST http://localhost:8081/process \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Deep Learning for Computer Vision\"}"
```

更完整的接口说明见 [api.md](F:/Github/cn_paper_pdf_summary/api.md)。

## Telegram Bot

Bot 只负责接收命令和回传处理状态，不负责在命令回复里直接发送成功结果正文。

先启动 API，再启动 Bot：

```bash
cd telegram-bot
npm start
```

支持命令：

- `/start`
- `/help`
- `/papers <标题[@ID]> [--wechat]`

示例：

```text
/papers Attention Is All You Need
/papers Attention Is All You Need@123
/papers Attention Is All You Need --wechat
/papers Attention Is All You Need@123 --wechat
```

说明：

- 标题尾部 `@123` 会被解析为 legacy ID，并触发 LIS-RSS 上传
- 兼容 `标题 @123` 写法
- `--wechat` 强制开启本次企业微信成功结果推送

消息行为说明：

- Telegram `/papers` 会固定返回两类会话消息
  - `📥 开始处理...`
  - 处理结束日志（成功或失败）
- `PDF_SUMMARY_PUSH_TELEGRAM_LOG`
  - 只影响 CLI / API 的成功日志主动推送
  - 不控制 Telegram `/papers` 的结束日志
- `PDF_SUMMARY_PUSH_TELEGRAM_RESULT`
  - 控制是否额外主动推送最终摘要正文
  - 对 CLI / API / Telegram Bot 三种入口统一生效

## 实际处理流程

1. 按标题尝试多个下载脚本
2. 校验 PDF 文件名是否匹配
3. 生成 Markdown 摘要
4. 并行上传到启用的子系统
5. 按本地配置分发 Telegram / 企业微信通知
6. 写入 `logs/` 日报

## 输出位置

- PDF / Markdown：`download/YYYY-MM-DD/`
- 日志日报：`logs/YYYY-MM-DD.md`
- Telegram Bot 本地日志：由运行命令或进程管理器决定

## 常见问题

### 1. 不想依赖 LIS-RSS，还需要配 `LIS_RSS_*` 吗

不需要。

只有你希望保留 `id` 上传到 LIS-RSS 的 legacy 能力时，才需要配置 `LIS_RSS_API_URL`、`LIS_RSS_USERNAME`、`LIS_RSS_PASSWORD`。

### 2. 为什么成功结果没有发到企业微信

检查：

- `.env` 中 `PDF_SUMMARY_PUSH_WECHAT` 是否为 `true`
- 本次调用是否传了 `--wechat` 或 `push_wechat=true`
- `WECHAT_WEBHOOK_KEY` 是否正确

### 3. 为什么错误没有发到 Telegram

检查：

- `TELEGRAM_BOT_TOKEN` 是否正确
- `TELEGRAM_NOTIFY_CHAT_ID` 或 `TELEGRAM_USER_ID` 是否正确
- 网络 / 代理是否能访问 Telegram API

### 4. 为什么 Telegram Bot 能回复状态，但没有收到主动通知

命令回复和主动通知是两条链路：

- 命令回复由 `telegram-bot/` 负责
- 主动通知由 Python 侧 `utils/notifier.py` 负责

需要分别检查 `.env` 中的主动通知配置。

## 开发验证

Python：

```bash
python -m py_compile main.py api.py utils/api_queue.py utils/notifier.py utils/summary_uploader.py
python -m unittest discover -s tests -p "test_*.py"
```

Telegram Bot：

```bash
cd telegram-bot
npm run typecheck
npm test
```
