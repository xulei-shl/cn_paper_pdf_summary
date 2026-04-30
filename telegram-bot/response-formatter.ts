export interface ProcessApiResponse {
  success?: boolean;
  stages?: Record<string, unknown>;
  reason?: string;
  md_path?: string;
}

function formatSendStatus(sent: boolean | undefined): string {
  return sent ? '已发送' : '未发送';
}

export function formatProcessResponse(title: string, result: ProcessApiResponse): string {
  const success = result.success ?? false;
  const stages = result.stages ?? {};
  const reason = result.reason;
  const mdPath = result.md_path;

  const lines: string[] = [];
  lines.push('📋 论文处理完成\n');
  lines.push(`标题: ${title}\n`);

  if (success) {
    lines.push('\n✅ 成功\n');

    const pdfDownload = stages['pdf_download'] ?? '❓';
    const pdfValidate = stages['pdf_validate'] ?? '❓';
    const pdfSummary = stages['pdf_summary'] ?? '❓';

    lines.push(`📥 PDF下载: ${pdfDownload === 'success' ? '✅' : '❌'}`);
    lines.push(`📋 PDF验证: ${pdfValidate === 'success' ? '✅' : '❌'}`);
    lines.push(`📝 摘要生成: ${pdfSummary === 'success' ? '✅' : '❌'}`);

    const upload = stages['upload'] as Record<string, boolean> | undefined;
    if (upload) {
      lines.push('\n📤 上传:');
      lines.push(`   • HiAgent RAG: ${upload['hiagent_rag'] ? '✅' : '❌'}`);
      lines.push(`   • LIS-RSS: ${upload['lis_rss'] ? '✅' : '❌'}`);
      lines.push(`   • Memos: ${upload['memos'] ? '✅' : '❌'}`);
      lines.push(`   • Blinko: ${upload['blinko'] ? '✅' : '❌'}`);
      lines.push(`   • 企业微信: ${upload['wechat'] ? '✅' : '❌'}`);
    }

    const notify = stages['notify'] as Record<string, boolean> | undefined;
    if (notify) {
      lines.push('\n📣 正文推送:');
      lines.push(`   • Telegram: ${formatSendStatus(notify['telegram_result'])}`);
      lines.push(`   • 企业微信: ${formatSendStatus(notify['wechat'])}`);
    }

    if (mdPath) {
      lines.push(`\n📁 摘要文件: \`${mdPath}\``);
    }
  } else {
    lines.push('\n❌ 失败\n');
    if (reason) {
      lines.push(reason);
    }
  }

  return lines.join('\n');
}
