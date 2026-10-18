#!/bin/sh
# split-repos.sh — 把总库 skills/<name> 拆分为独立子库并推送（git subtree split 单向镜像）
#
# 用法（在总库根目录执行）：
#   sh scripts/split-repos.sh                      # 拆分并推送全部 skill
#   OWNER=<github用户> sh scripts/split-repos.sh   # 指定属主（默认取 git remote 或 GreenWich-art）
#
# 前提：gh 已认证（gh auth login）且对目标仓库有写权限。
# 语义：总库是唯一事实源；子库是只读镜像。要改 skill 请提交 PR 到总库，再跑本脚本同步。
# 幂等：重复执行安全（subtree split 会重建分支，推送用 -f 覆盖镜像历史）。
set -eu

# ---- 0. 属主解析：环境变量 > git remote > 默认值 ----
if [ -z "${OWNER:-}" ]; then
    ORIGIN=$(git remote get-url origin 2>/dev/null || true)
    case "$ORIGIN" in
        *github.com[:/]*)
            OWNER=$(printf '%s' "$ORIGIN" | sed -E 's#.*github.com[:/]+([^/]+)/.*#\1#')
            ;;
        *) OWNER="GreenWich-art" ;;
    esac
fi
PREFIX="${PREFIX:-skill}"

echo "总库属主: $OWNER    子库名前缀: $PREFIX-"

# ---- 1. 安全检查 ----
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "错误：不在 git 仓库内" >&2; exit 1; }
if [ -n "$(git status --porcelain)" ]; then
    echo "错误：工作树有未提交改动，请先 commit 再运行本脚本" >&2
    exit 1
fi

# ---- 2. 逐 skill 拆分推送 ----
ok=0; skip=0
for d in skills/*/; do
    [ -d "$d" ] || continue
    name=$(basename "$d")
    repo="${PREFIX}-${name}"
    echo "════ $name → $OWNER/$repo ════"

    # 2a. 子库不存在则创建（公开）
    if gh repo view "$OWNER/$repo" >/dev/null 2>&1; then
        echo "  子库已存在，跳过创建"
    else
        disp=$(grep -m1 '^display_name:' "skills/$name/SKILL.md" 2>/dev/null | sed 's/display_name: *//; s/"//g')
        gh repo create "$repo" --public \
            --description "${disp:-$name} — Agent Skill（总库 agent-skills 的只读镜像，贡献请至总库）" >/dev/null
        echo "  已创建公开子库 $OWNER/$repo"
    fi

    # 2b. subtree split（先删旧分支保证幂等）
    git branch -D "split/$name" >/dev/null 2>&1 || true
    git subtree split --prefix="skills/$name" -b "split/$name" >/dev/null
    echo "  已生成 split/${name}（仅含 skills/${name} 的历史）"

    # 2c. 推送为子库 main（-f：镜像语义，允许历史重写）
    git push -f "https://github.com/$OWNER/$repo.git" "split/$name:main" >/dev/null 2>&1 \
        && { echo "  ✓ 已推送"; ok=$((ok+1)); } \
        || { echo "  ✗ 推送失败（检查 gh 认证与仓库写权限）" >&2; skip=$((skip+1)); }
done

echo
echo "完成：$ok 个推送成功，$skip 个失败"
[ "$skip" -eq 0 ]
