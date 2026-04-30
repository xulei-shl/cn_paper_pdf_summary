import test from 'node:test';
import assert from 'node:assert/strict';

import { parsePaperCommand } from './command-parser.js';

test('解析基础标题命令', () => {
  assert.deepEqual(parsePaperCommand('Attention Is All You Need'), {
    title: 'Attention Is All You Need',
    pushWechat: false,
  });
});

test('解析带 --wechat 的命令', () => {
  assert.deepEqual(parsePaperCommand('Attention Is All You Need --wechat'), {
    title: 'Attention Is All You Need',
    pushWechat: true,
  });
});

test('解析 title@id 形式的命令', () => {
  assert.deepEqual(parsePaperCommand('Attention Is All You Need@123'), {
    title: 'Attention Is All You Need',
    id: 123,
    pushWechat: false,
  });
});

test('兼容解析 title @id 形式的命令', () => {
  assert.deepEqual(parsePaperCommand('Attention Is All You Need @123'), {
    title: 'Attention Is All You Need',
    id: 123,
    pushWechat: false,
  });
});

test('解析同时带 id 和 --wechat 的命令', () => {
  assert.deepEqual(parsePaperCommand('Attention Is All You Need@123 --wechat'), {
    title: 'Attention Is All You Need',
    id: 123,
    pushWechat: true,
  });
});

test('非法 @id 后缀按普通标题处理', () => {
  assert.deepEqual(parsePaperCommand('Attention Is All You Need @abc'), {
    title: 'Attention Is All You Need @abc',
    pushWechat: false,
  });
});

test('只有开关时返回空结果', () => {
  assert.equal(parsePaperCommand('--wechat'), null);
});
