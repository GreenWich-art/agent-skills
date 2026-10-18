# macos-vision-ocr

让 AI Agent 自动调用 macOS **系统自带**的 Vision 引擎做 OCR：完全本地、免费、离线、
零依赖。不联网、不下载模型、不装 Homebrew——识别在本地毫秒级完成，没有云端往返，
没有 API 费用，数据不出设备。

## 这是一个 Agent Skill

本包首先是一个 **Agent Skill**：把本目录放进你的 skills 目录
（如 `~/.workbuddy/skills/`、`.claude/skills/`，或其他支持 SKILL.md 规范的 Agent），
Agent 会在需要读取图片/截图/扫描件文字时，**自动**按 `SKILL.md` 的指引调用本地
`macocr` 命令——无需你手动干预，也无需把图片上传到任何云端 OCR 服务。

为什么值得装：

- **速度**：本地推理，无网络往返，批量识别扫描件时差距尤其明显
- **隐私**：涉密文档、未发表材料、证件票据照片，全程不出本机
- **成本**：零 API 费用，识别一万张和一张一个价
- **兜底**：模型本身没有视觉能力、或处于离线环境时，这是唯一能干活的路径

macOS「照片」App 的实况文本（Live Text）用的就是同一个 Vision 引擎。
本 Skill 把它在前后处理上做的几件事（EXIF 转正、全分辨率取图、竖排检测）
补齐到命令行管线里，让脚本调用达到接近实况文本的识别率。

## 安装

```bash
./install.sh                    # 编译安装 macocr 到 ~/.local/bin（可用 PREFIX 覆盖）
sh scripts/selftest.sh          # 端到端自检：识别包内测试图，输出 PASS 即正常
```

无 Xcode 命令行工具的 Apple Silicon 机器：安装脚本自动回退到随附的
预编译二进制 `scripts/macocr-arm64`。安装完成后把本目录复制到 skills 目录，
即可被 Agent 发现（具体路径取决于你用的 Agent 产品）。

## 特性

- **完全本地离线**：系统自带引擎，零网络依赖
- **零依赖**：编译只需 Xcode Command Line Tools（`xcode-select --install`）
- **简繁中文 + 英文混排**，共支持 20+ 种语言（`macocr --list-langs` 查看）
- **竖排文本自动检测**：置信度仲裁，不把表格误判成竖排
- **方向纠正**：`--orientation left/right/180` 手动转正侧拍图
- **小图增强**：`--upscale N` 对模糊小图先 Lanczos 放大再识别
- **表格友好**：`--fast` 关闭语言纠错，数字不被"改正"成错值

## 命令行手动用法（可选）

Agent 场景之外，`macocr` 本身也是一条好用的命令：

```bash
macocr 截图.png                           # 识别
macocr --fast 表格照片.jpg                 # 表格数字场景
macocr --orientation left 侧拍.jpg         # 方向纠正
macocr --rect 100,200,1400,900 大图.png    # 只识别局部区域
```

## 文件说明

| 文件 | 说明 |
|---|---|
| `SKILL.md` | Agent Skill 定义与完整使用文档（Agent 读这个） |
| `install.sh` | 安装脚本（POSIX sh，编译优先，预编译二进制兜底） |
| `scripts/selftest.sh` | 端到端自检脚本（识别自带测试图，PASS/FAIL） |
| `scripts/selftest.png` | 自检用测试图（中英混排） |
| `scripts/vision_ocr.swift` | 源代码（约 200 行，可审计） |
| `scripts/macocr-arm64` | Apple Silicon 预编译二进制（ad-hoc 签名） |

## 安全与信任

macOS 对未公证的二进制有 Gatekeeper 提示，本项目的应对分三层，按信任成本排序：

1. **源码可审计**：核心逻辑是 `scripts/vision_ocr.swift`，约 200 行 Swift，
   只调用系统 Vision 框架，无任何网络请求。默认安装路径就是**现场编译**
   （`swiftc -O`），你跑的就是自己编出来的二进制。
2. **预编译二进制已做 ad-hoc 签名**（`codesign --sign -`）：macOS 可校验其
   完整性，安装脚本同时自动移除 quarantine 属性。ad-hoc 签名不含开发者身份，
   首次运行如被 Gatekeeper 拦截，在「系统设置 → 隐私与安全性」点「仍要打开」即可。
3. **验证签名**：`codesign -dv scripts/macocr-arm64`，`Signature=adhoc` 即为
   本包发布时的状态；若显示 `code object is not signed at all`，说明文件被改动过。

## 系统要求

macOS 13+；编译需 Xcode Command Line Tools，或使用随附的 arm64 预编译二进制。

## License

MIT © 2026 冯金岳 (Feng Jinyue)
