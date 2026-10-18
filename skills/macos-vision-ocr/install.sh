#!/bin/sh
# install.sh —— 安装 macocr（macOS Vision 本地 OCR）
# 默认安装到 ~/.local/bin（无需 sudo）；可用 PREFIX 环境变量覆盖：
#   PREFIX=/usr/local/bin ./install.sh
# 兼容 bash / zsh / dash，可直接 sh install.sh 调用。
set -eu

# --- 环境守卫：本工具仅支持 macOS ---
if [ "$(uname -s)" != "Darwin" ]; then
    echo "错误：macocr 依赖 macOS 系统自带的 Vision 框架，仅支持 macOS。" >&2
    echo "当前系统：$(uname -s)。请在 macOS 13+ 上安装。" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${PREFIX:-$HOME/.local/bin}"
BIN="$PREFIX/macocr"

mkdir -p "$PREFIX"

# 优先现场编译；没有 swiftc 时回退到预编译二进制（仅 Apple Silicon）
if command -v swiftc >/dev/null 2>&1; then
    echo "检测到 swiftc，正在编译（约 10 秒）…"
    swiftc -O "$SCRIPT_DIR/scripts/vision_ocr.swift" -o "$BIN"
    echo "编译完成。"
elif [ "$(uname -m)" = "arm64" ] && [ -f "$SCRIPT_DIR/scripts/macocr-arm64" ]; then
    echo "未检测到 swiftc（可运行 xcode-select --install 安装后自行编译）。"
    echo "改用随附的 Apple Silicon 预编译二进制。"
    cp "$SCRIPT_DIR/scripts/macocr-arm64" "$BIN"
    chmod +x "$BIN"
    xattr -d com.apple.quarantine "$BIN" 2>/dev/null || true
else
    echo "错误：未检测到 swiftc，且本机不是 Apple Silicon，无法使用预编译二进制。" >&2
    echo "请先运行 xcode-select --install 安装命令行工具后重试。" >&2
    exit 1
fi

echo "已安装到：$BIN"

# PATH 检查与提示
case ":$PATH:" in
    *":$PREFIX:"*) ;;
    *)
        echo ""
        echo "注意：$PREFIX 不在 PATH 中。把下面这行加入 ~/.zshrc 后重开终端："
        echo "  export PATH=\"$PREFIX:\$PATH\""
        ;;
esac

# 自检
if "$BIN" --list-langs 2>/dev/null | grep -q "zh-Hans"; then
    echo "自检通过：zh-Hans 在可用识别语言列表中。"
else
    echo "警告：未能在语言列表中确认 zh-Hans，请运行 macocr --list-langs 检查。" >&2
fi

echo ""
echo "进一步验证（生成测试图并识别，约 5 秒）："
echo "  sh $SCRIPT_DIR/scripts/selftest.sh"
echo "或直接试试：macocr <某张图片路径>"
