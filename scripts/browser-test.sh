#!/usr/bin/env bash
# 跑真浏览器（Playwright + Chromium）流程测试。
#
# 难点：Chromium 需要系统的 NSS/NSPR 库（libnspr4/libnss3）。没有免密 sudo 的机器
# （例如 WSL）可以用"下载 deb 并解包到本地目录 + LD_LIBRARY_PATH"来替代 `sudo apt install`，
# 这个脚本就是干这个的：不需要 root，也不会改动系统目录。
#
#   ./scripts/browser-test.sh              # 准备依赖并跑测试
#   TODO_SKIP_BROWSER=1 ./scripts/...      # 强制跳过
#
# 如果机器上已经有系统库（或你跑过 sudo python3 -m playwright install-deps chromium），
# 这个脚本会自动跳过下载那一步，直接跑测试。
set -uo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP"
LIBS_DIR="$APP/.playwright-libs"
LIB_PATH=""

step() { printf '\n== %s ==\n' "$1"; }

if [ "${TODO_SKIP_BROWSER:-}" = "1" ]; then
    echo "TODO_SKIP_BROWSER=1，跳过浏览器测试。"
    exit 0
fi

if ! python3 -c "import playwright" 2>/dev/null; then
    echo "没装 playwright：python3 -m pip install -r requirements-dev.txt" >&2
    exit 1
fi

step "1) 确认浏览器已下载"
if ! python3 -m playwright install chromium-headless-shell > /tmp/todo-browser-install.log 2>&1; then
    echo "下载 Chromium 失败，见 /tmp/todo-browser-install.log" >&2
    tail -5 /tmp/todo-browser-install.log >&2
    exit 1
fi
echo "   ✔ 浏览器就绪"

step "2) 检查系统库（缺就本地解包，不需要 sudo）"
BROWSER_DIR="$(ls -d "$HOME"/.cache/ms-playwright/chromium_headless_shell-* 2>/dev/null | sort | tail -1)"
BROWSER="$BROWSER_DIR/chrome-headless-shell-linux64/chrome-headless-shell"
if [ ! -x "$BROWSER" ]; then
    echo "找不到 chrome-headless-shell（$BROWSER）" >&2
    exit 1
fi

missing_libs() { ldd "$BROWSER" 2>/dev/null | grep "not found" || true; }

if [ -n "$(missing_libs)" ]; then
    echo "   缺库：$(missing_libs | awk '{print $1}' | tr '\n' ' ')"
    # 已经解包过就直接复用
    if ! find "$LIBS_DIR" -name "libnss3.so" 2>/dev/null | grep -q .; then
        mkdir -p "$LIBS_DIR/debs"
        echo "   下载 libnspr4 / libnss3 的 deb 包（约 1.6 MB）…"
        if ! (cd "$LIBS_DIR/debs" && apt-get download libnspr4 libnss3 > /tmp/todo-browser-apt.log 2>&1); then
            echo "   下载失败（可能没网或没有 apt 源）。请改用：" >&2
            echo "     sudo python3 -m playwright install-deps chromium" >&2
            tail -3 /tmp/todo-browser-apt.log >&2
            exit 1
        fi
        for deb in "$LIBS_DIR"/debs/*.deb; do
            dpkg -x "$deb" "$LIBS_DIR/extracted/" || exit 1
        done
    fi
    LIB_PATH="$(dirname "$(find "$LIBS_DIR" -name 'libnss3.so' | head -1)")"
    echo "   ✔ 已本地解包到 $LIB_PATH"
else
    echo "   ✔ 系统库齐全"
fi

step "3) 真浏览器流程测试"
if [ -n "$LIB_PATH" ]; then
    LD_LIBRARY_PATH="$LIB_PATH${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
        python3 -m unittest tests.test_browser_flows -v
else
    python3 -m unittest tests.test_browser_flows -v
fi
STATUS=$?

if [ "$STATUS" = "0" ]; then
    printf '\n真浏览器流程全部通过 ✔\n'
else
    printf '\n真浏览器流程有失败 ✘\n' >&2
fi
exit "$STATUS"
