#!/bin/sh
# selftest.sh —— macocr 端到端自检
# 用包内自带的测试图（scripts/selftest.png，含中英混排文字）
# 调用 macocr 识别并校验关键词命中。零依赖、离线、约 2 秒。
# 用法：
#   sh selftest.sh                 # 自动定位 macocr（~/.local/bin 或 PATH）
#   sh selftest.sh /path/to/macocr # 指定二进制
# 退出码：0 通过；1 失败；2 非 macOS 跳过
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMG="$SCRIPT_DIR/selftest.png"

if [ "$(uname -s)" != "Darwin" ]; then
    echo "SKIP: 非 macOS 环境，Vision OCR 不可用。" >&2
    exit 2
fi

if [ ! -f "$IMG" ]; then
    echo "FAIL: 缺少测试图 $IMG，包不完整。" >&2
    exit 1
fi

BIN="${1:-}"
if [ -z "$BIN" ]; then
    if [ -x "$HOME/.local/bin/macocr" ]; then
        BIN="$HOME/.local/bin/macocr"
    elif command -v macocr >/dev/null 2>&1; then
        BIN="$(command -v macocr)"
    else
        echo "FAIL: 未找到 macocr，请先运行 ./install.sh 或传入可执行文件路径。" >&2
        exit 1
    fi
fi

OUT="$(mktemp /tmp/macocr-selftest.XXXXXX)"
trap 'rm -f "$OUT"' EXIT

"$BIN" "$IMG" > "$OUT" 2>&1 || true

MISS=0
for kw in "Vision" "OCR" "2026" "自检" "English"; do
    if ! grep -q "$kw" "$OUT"; then
        echo "MISS: 识别结果中未找到关键词「$kw」" >&2
        MISS=1
    fi
done

if [ "$MISS" = "1" ]; then
    echo "--- 原始识别输出 ---" >&2
    cat "$OUT" >&2
    echo "FAIL: 自检未通过。" >&2
    exit 1
fi

echo "PASS: macocr works (binary: $BIN)"
exit 0
