#!/usr/bin/env bash
# 极简版：一键 暂存+提交+推送
#   ./db-snapshot.sh "提交说明" push         不含三个数据库
#   ./db-snapshot.sh "提交说明" sqlite push   包含三个数据库(记录后自动恢复不跟踪)
#   ./db-snapshot.sh status / untrack         辅助
set -euo pipefail
cd "$(dirname "$0")"
FILES=(data/todo.sqlite3 data/memo.sqlite3 data/summary.sqlite3)
now() { date +%Y-%m-%d; }
tracked() { git ls-files -- "${FILES[@]}"; }

if [[ "${1:-}" == "status" ]]; then
  echo "分支: $(git branch --show-current)"
  tracked | grep -q . && echo "数据库: 在跟踪中" || echo "数据库: 未跟踪(正常 git 不会带上)"
  echo "待提交:" && git status --short | head -15 || true
  exit 0
fi
if [[ "${1:-}" == "untrack" ]]; then
  git rm --cached -- "${FILES[@]}" >/dev/null 2>&1 || true
  tracked | grep -q . && { echo "!! 仍有文件在跟踪"; exit 1; }
  echo "已解除跟踪(仅本地保留)"
  exit 0
fi

MSG="${1:-update $(now)}"
INCL=false; KEEP=false
for a in "${@:2}"; do [[ "$a" == "sqlite" ]] && INCL=true; [[ "$a" == "keep" ]] && KEEP=true; done

if $INCL; then
  git add -f "${FILES[@]}"
else
  # 保证不含库: 若仍在跟踪先解除(避免 add -A 带上)
  git rm --cached -- "${FILES[@]}" >/dev/null 2>&1 || true
fi
git add -A

if git diff --cached --quiet; then echo "没有可提交的改动"; exit 0; fi
git commit -m "$MSG" >/dev/null && echo "已提交: $MSG" || { echo "!! 提交失败"; exit 1; }
if git push >/dev/null 2>&1; then
  echo "已推送 ✔"
else
  echo "!! 推送失败——该分支可能还没设远端上游, 请执行:"
  echo "   git push -u origin $(git branch --show-current)"
fi
if $INCL && ! $KEEP; then
  git rm --cached -- "${FILES[@]}" >/dev/null 2>&1 || true
  git commit -m "chore: 快照已记录, 恢复数据库不跟踪" >/dev/null 2>&1 || true
  git push >/dev/null 2>&1 || true
fi
echo "完成 ✔"
