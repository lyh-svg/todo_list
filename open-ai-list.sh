#!/bin/sh
set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PORT="${TODO_AI_PORT:-8765}"
URL="http://127.0.0.1:${PORT}"
LOG_FILE="${TMPDIR:-/tmp}/todo-list-ai.log"
TOKEN_FILE="${TMPDIR:-/tmp}/todo-list-ai-${PORT}.token"
umask 077

if ! curl --silent --fail --max-time 1 "${URL}/api/health" >/dev/null 2>&1; then
    cd -- "$APP_DIR"
    if [ -f "$LOG_FILE" ] && [ "$(wc -c < "$LOG_FILE")" -gt 1048576 ]; then
        mv -f -- "$LOG_FILE" "${LOG_FILE}.1"
    fi
    : >>"$LOG_FILE"
    chmod 600 "$LOG_FILE"
    SESSION_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    TODO_SESSION_TOKEN="$SESSION_TOKEN" TODO_SESSION_TOKEN_FILE="$TOKEN_FILE" \
        nohup python3 local_server.py >>"$LOG_FILE" 2>&1 &
    attempt=0
    while [ "$attempt" -lt 30 ]; do
        if curl --silent --fail --max-time 1 "${URL}/api/health" >/dev/null 2>&1; then
            break
        fi
        sleep 0.1
        attempt=$((attempt + 1))
    done
fi

if ! curl --silent --fail --max-time 1 "${URL}/api/health" >/dev/null 2>&1; then
    echo "无法启动本地服务，请查看日志：${LOG_FILE}" >&2
    exit 1
fi

if [ ! -r "$TOKEN_FILE" ]; then
    echo "本地服务会话文件不存在，请关闭旧服务后重新运行此脚本" >&2
    exit 1
fi
SESSION_TOKEN="$(cat -- "$TOKEN_FILE")"

if [ "${TODO_NO_BROWSER:-0}" = "1" ]; then
    echo "${URL}/?token=${SESSION_TOKEN}"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${URL}/?token=${SESSION_TOKEN}" >/dev/null 2>&1 &
else
    echo "请重新运行本脚本自动打开受保护的页面"
fi