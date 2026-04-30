export interface ParsedCommand {
  title: string;
  id?: number;
  pushWechat: boolean;
}

export function parsePaperCommand(text: string): ParsedCommand | null {
  const rawText = text.trim();
  if (!rawText) {
    return null;
  }

  const pushWechat = /--wechat/i.test(rawText);
  const normalizedText = rawText.replace(/--wechat/gi, '').trim();
  const idMatch = normalizedText.match(/^(.*?)(?:\s*)@(\d+)$/);

  if (idMatch) {
    const title = idMatch[1].trim();
    if (!title) {
      return null;
    }

    return {
      title,
      id: Number(idMatch[2]),
      pushWechat,
    };
  }

  const title = normalizedText;

  if (!title) {
    return null;
  }

  return {
    title,
    pushWechat,
  };
}
