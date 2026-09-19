#!/usr/bin/env bash
# 一条命令跑完全部本地检查（CI 跑的就是这些）。
#
#   ./scripts/check.sh          # 全部
#   ./scripts/check.sh quick    # 跳过端到端与浏览器（只跑语法 + 单测 + 前端脚本）
#
# 说明：所有测试都用临时数据库，不会碰 data/ 下的真实数据。
set -uo pipefail

# 检查链一律在临时库上跑：即使某个测试模块忘了设 TODO_*，也绝不会碰真实 data/（2026-09-17 事故后补）
TODO_GUARD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/todo-check-XXXXXX")
export TODO_SQLITE_FILE="$TODO_GUARD_DIR/todo.sqlite3"
export TODO_SQLITE_BACKUP_DIR="$TODO_GUARD_DIR/backups"
export TODO_MEMO_SQLITE_FILE="$TODO_GUARD_DIR/memo.sqlite3"
trap 'rm -rf "$TODO_GUARD_DIR"' EXIT

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP"
MODE="${1:-full}"
FAILED=0

step() { printf '\n== %s ==\n' "$1"; }
ok()   { printf '   ✔ %s\n' "$1"; }
bad()  { printf '   ✘ %s\n' "$1"; FAILED=1; }

run() {  # run <描述> <命令...>
    local name="$1"; shift
    if "$@" > /tmp/todo-check-step.log 2>&1; then ok "$name"; else bad "$name"; tail -30 /tmp/todo-check-step.log; fi
}

step "1) Python 语法检查（compileall）"
run "python3 -m compileall" python3 -m compileall -q storage.py local_server.py backup_service.py ai_service.py \
    memo_storage.py tests

step "2) Node 语法检查"
if command -v node > /dev/null 2>&1; then
    node_ok=1
    for file in js/*.js tests/frontend/*.js; do
        node --check "$file" || node_ok=0
    done
    [ "$node_ok" = "1" ] && ok "node --check 全部通过" || bad "node --check 有失败"
else
    printf '   - 没装 node，跳过\n'
fi

step "3) 静态检查（ruff / eslint）"
if command -v ruff > /dev/null 2>&1; then
    run "ruff check ." ruff check .
else
    printf '   - 没装 ruff，跳过（pip install -r requirements-dev.txt）\n'
fi
if [ -x node_modules/.bin/eslint ]; then
    run "eslint ." node_modules/.bin/eslint .
else
    printf '   - 没装 eslint，跳过（npm install）\n'
fi

step "4) 单元测试 + HTTP 层 + 前端脚本 + 端到端"
if [ "$MODE" = "quick" ]; then
    run "python3 -m unittest（跳过 E2E 与浏览器）" env TODO_SKIP_E2E=1 TODO_SKIP_BROWSER=1 \
        python3 -m unittest discover -s tests
else
    run "python3 -m unittest discover -s tests" python3 -m unittest discover -s tests
fi

step "5) 前端冒烟（真实加载页面并点击）"
if command -v node > /dev/null 2>&1; then
    run "dom-smoke.js" node tests/frontend/dom-smoke.js
else
    printf '   - 没装 node，跳过\n'
fi

step "6) 端到端 HTTP（临时库 + 随机端口）"
if [ "$MODE" = "quick" ]; then
    printf '   - quick 模式跳过\n'
else
    run "tests/e2e-verify.sh" bash tests/e2e-verify.sh
fi

step "7) 真浏览器流程（Playwright；缺库时本地解包，不需要 sudo）"
if [ "$MODE" = "quick" ]; then
    printf '   - quick 模式跳过\n'
elif python3 -c "import playwright" 2>/dev/null; then
    run "tests/test_browser_flows.py" bash scripts/browser-test.sh
else
    printf '   - 没装 playwright，跳过（pip install -r requirements-dev.txt）\n'
fi

step "8) 反向验证：把产品改回旧行为，测试必须失败"
if [ "$MODE" = "quick" ]; then
    printf '   - quick 模式跳过\n'
else
    run "verify-tests-catch.py（54 条）" python3 scripts/verify-tests-catch.py
fi

step "9) 行尾约定（代码文件必须 CRLF，*.sh 用 LF）"
crlf_bad=0
while IFS= read -r file; do
    case "$file" in
        *.sh|.gitignore|requirements.txt|requirements-dev.txt|deepseek.env.example|package.json|package-lock.json|pyproject.toml|*.mjs|*.yml) continue ;;
    esac
    total=$(wc -l < "$file")
    crlf=$(grep -c $'\r' "$file" || true)
    doubled=$(grep -c $'\r\r' "$file" || true)
    if [ "$total" != "$crlf" ] || [ "$doubled" != "0" ]; then
        printf '   ✘ %s 行尾不对（%s 行 / %s 含 CR / %s 行双 CR）\n' "$file" "$total" "$crlf" "$doubled"
        crlf_bad=1
    fi
done < <({ git ls-files '*.py' '*.js' '*.css' '*.html' '*.md'; git ls-files --others --exclude-standard '*.py' '*.js' '*.css' '*.html' '*.md'; } | sort -u)
# *.sh 必须是 LF：以前 *.sh 在上面被直接 continue 跳过，"*.sh 用 LF"只写在标题里没真的检查，
# 于是一次脚本编辑把 tests/e2e-verify.sh 写成 CRLF，直到 e2e 步骤才以
# "$'\r': command not found" 的形式炸出来。
sh_bad=0
while IFS= read -r file; do
    if [ "$(grep -c $'\r' "$file" || true)" != "0" ]; then
        printf '   ✘ %s 含 CR（*.sh 必须是 LF）\n' "$file"
        sh_bad=1
    fi
done < <(git ls-files '*.sh')
if [ "$crlf_bad" = "0" ] && [ "$sh_bad" = "0" ]; then
    ok "行尾全部符合约定"
else
    bad "行尾检查失败"
fi

printf '\n'
if [ "$FAILED" = "0" ]; then
    printf '全部检查通过 ✔\n'
else
    printf '有检查失败 ✘\n'
fi
exit "$FAILED"
