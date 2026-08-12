#!/usr/bin/env sh
# 为每个 skills/<category>/<skill>/SKILL.md 在 skills/ 顶层建一个同名符号链接。
#
# 为什么需要：Claude Code 只在 skills/<skill-name>/SKILL.md 这一层发现技能，
# 不会递归进主题目录。仓库按主题分目录是给人看的，符号链接是给插件加载器看的。
#
# 用法：./scripts/sync-skill-links.sh [--check]
#   无参数  创建缺失的链接、删除失效的链接
#   --check 只报告差异，不修改（校验脚本用这个）

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
skills_dir="$repo_root/skills"
check_only=0
[ "${1:-}" = "--check" ] && check_only=1

missing=0
stale=0

# 建立缺失的链接
for skill_md in "$skills_dir"/*/*/SKILL.md; do
    [ -e "$skill_md" ] || continue
    skill_dir=$(dirname "$skill_md")
    name=$(basename "$skill_dir")
    category=$(basename "$(dirname "$skill_dir")")
    link="$skills_dir/$name"

    if [ -L "$link" ]; then
        current=$(readlink "$link")
        [ "$current" = "$category/$name" ] && continue
        if [ "$check_only" -eq 1 ]; then
            echo "指向错误: skills/$name -> $current（应为 $category/$name）"
            missing=$((missing + 1))
            continue
        fi
        rm "$link"
    elif [ -e "$link" ]; then
        echo "冲突: skills/$name 已存在且不是符号链接，跳过"
        missing=$((missing + 1))
        continue
    fi

    if [ "$check_only" -eq 1 ]; then
        echo "缺少链接: skills/$name -> $category/$name"
        missing=$((missing + 1))
    else
        ln -s "$category/$name" "$link"
        echo "已创建: skills/$name -> $category/$name"
    fi
done

# 清理失效的链接
for link in "$skills_dir"/*; do
    [ -L "$link" ] || continue
    target="$skills_dir/$(readlink "$link")"
    [ -f "$target/SKILL.md" ] && continue
    if [ "$check_only" -eq 1 ]; then
        echo "失效链接: skills/$(basename "$link") -> $(readlink "$link")"
        stale=$((stale + 1))
    else
        rm "$link"
        echo "已删除失效链接: skills/$(basename "$link")"
    fi
done

if [ "$check_only" -eq 1 ]; then
    if [ $((missing + stale)) -gt 0 ]; then
        echo "共 $((missing + stale)) 处不一致，运行 ./scripts/sync-skill-links.sh 修复"
        exit 1
    fi
    echo "符号链接与主题目录一致"
fi
