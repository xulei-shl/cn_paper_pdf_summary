# 开发变更记录
- **日期**: 2026-04-30
- **对应设计文档**: `docs/design/telegram命令兼容legacy_id_20260430.md`

## 1. 变更摘要
- Telegram `/papers` 命令新增尾部 `@ID` 解析能力，与 CLI / API 的 legacy `id` 语义对齐
- 兼容 `标题@123` 与 `标题 @123` 两种写法
- 仅在显式传入 `@ID` 时透传 `id`，未传时继续按纯标题处理
- 同步更新帮助文案、README 与 API 文档，避免接口说明分叉

## 2. 文件清单
- `telegram-bot/command-parser.ts`: 新增尾部 `@ID` 解析逻辑
- `telegram-bot/index.ts`: 调整 API 调用参数并更新帮助文案
- `telegram-bot/command-parser.test.ts`: 补充 `@ID` 解析与异常输入测试
- `README.md`: 更新 Telegram 命令说明
- `api.md`: 更新 Telegram 命令说明
- `docs/design/telegram命令兼容legacy_id_20260430.md`: 新增设计文档

## 3. 测试结果
- [x] `npm test`（`telegram-bot/`）
- [x] `npm run typecheck`（`telegram-bot/`）
- [x] 核心路径验证通过：`title@id` 与 `title @id` 均可解析并透传
