#!/usr/bin/env bash
# db-snapshot.sh：一键 暂存+提交+推送（只作用于当前所在分支）
#   ./db-snapshot.sh "说明" push          不含数据库
#   ./db-snapshot.sh "说明" sqlite push    包含两个数据库(记录后自动恢复不跟踪)
#   ./db-snapshot.sh status / untrack      辅助
set -euo pipefail
cd "$(dirname "$0")"
FILES=(data/todo.sqlite3 data/memo.sqlite3)
now() { date +%Y-%m-%d; }
BR="$(git branch --show-current)"
tracked() { git ls-files -- "${FILES[@]}"; }

case "${1:-}" in
  status)
    echo "当前分支: $BR"
    tracked | grep -q . && echo "数据库: 在跟踪中" || echo "数据库: 未跟踪(正常 git 不会带上)"
    echo "待提交:" && git status --short | head -15 || true
    exit 0 ;;
  untrack)
    git rm --cached -- "${FILES[@]}" >/dev/null 2>&1 || true
    tracked | grep -q . && { echo "!! 仍有文件在跟踪"; exit 1; }
    echo "已解除跟踪(仅本地保留)"; exit 0 ;;
esac

MSG="${1:-update $(now)}"
INCL=false; KEEP=false
for a in "${@:2}"; do [[ "$a" == "sqlite" ]] && INCL=true; [[ "$a" == "keep" ]] && KEEP=true; done

if $INCL; then
  git add -f "${FILES[@]}"
else
  git rm --cached -- "${FILES[@]}" >/dev/null 2>&1 || true
fi
git add -A
if git diff --cached --quiet; then echo "没有可提交的改动"; exit 0; fi

git commit -m "$MSG" >/dev/null && echo "已提交(分支 $BR): $MSG" || { echo "!! 提交失败"; exit 1; }
if git push >/dev/null 2>&1; then
  echo "已推送 ✔"
else
  if git push -u origin "$BR" >/dev/null 2>&1; then
    echo "已推送到新分支并设为上游: origin/$BR ✔"
  else
    echo "!! 推送失败(网络/权限?): git push -u origin $BR"
  fi
fi
if $INCL && ! $KEEP; then
  git rm --cached -- "${FILES[@]}" >/dev/null 2>&1 || true
  git commit -m "chore: 快照已记录, 恢复数据库不跟踪" >/dev/null 2>&1 || true
  git push >/dev/null 2>&1 || true
fi
echo "完成 ✔"
