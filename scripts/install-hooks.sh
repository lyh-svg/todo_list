#!/usr/bin/env bash
# 可选：安装 git 钩子，让"每次提交"在本地也自动跑一遍检查。
#
#   ./scripts/install-hooks.sh          # 安装 pre-commit（跑 scripts/check.sh quick）
#   rm .git/hooks/pre-commit            # 卸载
#
# 钩子跑的是 quick 模式（语法 + 静态检查 + 单测 + 前端冒烟，约 10 秒）；
# 完整检查（含端到端 HTTP）请手动跑 ./scripts/check.sh。
# 临时跳过：git commit --no-verify
set -euo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$APP/.git/hooks/pre-commit"

if [ ! -d "$APP/.git" ]; then
    echo "这里不是 git 仓库，退出。" >&2
    exit 1
fi

cat > "$HOOK" <<'HOOK_SCRIPT'
#!/usr/bin/env bash
# 由 scripts/install-hooks.sh 生成
exec "$(git rev-parse --show-toplevel)/scripts/check.sh" quick
HOOK_SCRIPT
chmod +x "$HOOK"
echo "已安装 $HOOK（提交前跑 scripts/check.sh quick）"
