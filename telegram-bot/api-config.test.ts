import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveApiBaseUrl, resolveApiPort } from './api-config.js';

test('优先使用显式 TELEGRAM_API_URL', () => {
  assert.equal(
    resolveApiBaseUrl({
      TELEGRAM_API_URL: 'http://localhost:9000',
      PDF_SUMMARY_API_PORT: '8091',
    }),
    'http://localhost:9000'
  );
});

test('未配置 TELEGRAM_API_URL 时按端口拼接本地地址', () => {
  assert.equal(
    resolveApiBaseUrl({
      PDF_SUMMARY_API_PORT: '8091',
    }),
    'http://127.0.0.1:8091'
  );
});

test('未配置端口时回退默认值', () => {
  assert.equal(resolveApiPort({}), 8081);
  assert.equal(resolveApiBaseUrl({}), 'http://127.0.0.1:8081');
});

test('非法端口时回退默认值', () => {
  assert.equal(resolveApiPort({ PDF_SUMMARY_API_PORT: 'abc' }), 8081);
  assert.equal(resolveApiPort({ PDF_SUMMARY_API_PORT: '70000' }), 8081);
});
