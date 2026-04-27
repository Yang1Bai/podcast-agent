#!/bin/bash
# 自动同步到 GitHub，每次更新代码后调用
cd "$(dirname "$0")"
git add -A
CHANGES=$(git diff --cached --name-only | wc -l | tr -d ' ')
if [ "$CHANGES" -gt "0" ]; then
    MSG="${1:-🔄 Auto-sync: update podcast agent}"
    git commit -m "$MSG"
    git push origin main
    echo "✅ 已同步 $CHANGES 个文件到 GitHub"
else
    echo "ℹ️  无变更，跳过同步"
fi
