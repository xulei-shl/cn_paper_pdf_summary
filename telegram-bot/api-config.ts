/**
 * Telegram Bot API 地址解析
 */

const DEFAULT_API_BASE_URL = 'http://localhost:8081';
const DEFAULT_API_PORT = 8081;
const LOCALHOST_API_HOST = '127.0.0.1';

export function resolveApiBaseUrl(env: NodeJS.ProcessEnv): string {
  const explicitUrl = env.TELEGRAM_API_URL?.trim();
  if (explicitUrl) {
    return explicitUrl;
  }

  const port = resolveApiPort(env);
  return `http://${LOCALHOST_API_HOST}:${port}`;
}

export function resolveApiPort(env: NodeJS.ProcessEnv): number {
  const rawPort = env.PDF_SUMMARY_API_PORT?.trim();
  if (!rawPort) {
    return DEFAULT_API_PORT;
  }

  const parsedPort = Number.parseInt(rawPort, 10);
  if (!Number.isInteger(parsedPort) || parsedPort <= 0 || parsedPort > 65535) {
    return DEFAULT_API_PORT;
  }

  return parsedPort;
}

export function getDefaultApiBaseUrl(): string {
  return DEFAULT_API_BASE_URL;
}
