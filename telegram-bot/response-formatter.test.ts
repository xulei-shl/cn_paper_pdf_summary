import test from 'node:test';
import assert from 'node:assert/strict';

import { formatProcessResponse } from './response-formatter.js';

test('Telegram 成功结束日志展示正文推送状态', () => {
  const message = formatProcessResponse('测试标题', {
    success: true,
    md_path: 'download/2026-04-30/测试标题.md',
    stages: {
      pdf_download: 'success',
      pdf_validate: 'success',
      pdf_summary: 'success',
      upload: {
        hiagent_rag: true,
        lis_rss: false,
        memos: true,
        blinko: true,
        wechat: false,
      },
      notify: {
        telegram_log: false,
        telegram_result: true,
        wechat: false,
      },
    },
  });

  assert.match(message, /📋 论文处理完成/);
  assert.match(message, /📣 正文推送:/);
  assert.match(message, /Telegram: 已发送/);
  assert.match(message, /企业微信: 未发送/);
  assert.doesNotMatch(message, /telegram_log/i);
});

test('Telegram 失败结束日志保留失败原因', () => {
  const message = formatProcessResponse('测试标题', {
    success: false,
    reason: 'PDF下载失败',
  });

  assert.match(message, /❌ 失败/);
  assert.match(message, /PDF下载失败/);
});
