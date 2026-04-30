#!/bin/bash
# 统一启动 API 与 Telegram Bot

set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "错误: .env 文件不存在"
    exit 1
fi

source .env

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo "错误: TELEGRAM_BOT_TOKEN 未设置"
    exit 1
fi

API_BIND_HOST="${PDF_SUMMARY_API_BIND_HOST:-0.0.0.0}"
API_PORT="${PDF_SUMMARY_API_PORT:-8081}"
API_HEALTH_HOST="${PDF_SUMMARY_API_HEALTH_HOST:-127.0.0.1}"
API_HEALTH_URL="http://${API_HEALTH_HOST}:${API_PORT}/health"
API_START_TIMEOUT="${PDF_SUMMARY_API_START_TIMEOUT:-30}"
PYTHON_BIN="${PYTHON_BIN:-python}"

API_PID=""

cleanup() {
    if [ -n "${API_PID}" ] && kill -0 "${API_PID}" 2>/dev/null; then
        echo "停止 API 进程..."
        kill "${API_PID}" 2>/dev/null || true
        wait "${API_PID}" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

echo "启动 API 服务..."
"${PYTHON_BIN}" -m uvicorn api:app --host "${API_BIND_HOST}" --port "${API_PORT}" &
API_PID=$!

echo "等待 API 就绪: ${API_HEALTH_URL}"
for ((i=1; i<=API_START_TIMEOUT; i++)); do
    if curl -fsS "${API_HEALTH_URL}" >/dev/null 2>&1; then
        echo "API 已就绪"
        break
    fi

    if ! kill -0 "${API_PID}" 2>/dev/null; then
        echo "错误: API 进程已退出"
        exit 1
    fi

    if [ "${i}" -eq "${API_START_TIMEOUT}" ]; then
        echo "错误: API 在 ${API_START_TIMEOUT} 秒内未就绪"
        exit 1
    fi

    sleep 1
done

echo "启动 Telegram Bot..."
cd telegram-bot
npm start
