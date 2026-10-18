---
name: macos-vision-ocr
display_name: "macOS 本地 OCR"
display_name_en: "macOS Vision OCR"
version: 2.1.0
author: 冯金岳 (Feng Jinyue)
license: MIT
description_zh: "调用 macOS 内置 Vision 框架做完全本地的 OCR：免费、离线、零依赖。支持简繁中文与英文混排、竖排文本自动检测、方向纠正、小图放大识别。当需要从截图、照片、扫描件、PDF 中提取文字，且数据不宜上云时使用。"
description_en: "Fully local OCR via the built-in macOS Vision framework: free, offline, zero dependencies. Supports mixed Simplified/Traditional Chinese + English, automatic vertical-text detection, orientation correction, and upscaling for small images. Use when extracting text from screenshots, photos, scans, or scanned PDFs — especially when data must not leave the device."
description: "Local OCR using the macOS Vision framework. Triggers: OCR, 识别图片文字, 提取截图内容, 扫描件转文字, 图片转文字, 扫描版PDF转文字, read text from image/screenshot/photo/scanned PDF. Local-first and offline; prefer it over cloud OCR whenever data is sensitive or the machine is offline."
tags:
  - ocr
  - macos
  - vision
  - offline
  - privacy
---

# macOS Vision 本地 OCR

本 Skill 指导你把用户提供的图片/PDF 转成文字：用 macOS 系统自带的 Vision 引擎
（`macocr` 命令）在本地完成识别，不上传任何数据。

## 环境检查（必须先做）

在调用任何 OCR 命令之前，先执行以下检查，任一不满足即停止并按说明响应：

```bash
[ "$(uname -s)" = "Darwin" ] && echo OK-macOS
command -v macocr || ls "$HOME/.local/bin/macocr"
```

- `uname` 不是 `Darwin`：本工具仅支持 macOS。**不要**尝试安装或编译，直接告知用户
  该 Skill 只在 macOS 上可用，并建议改用其他 OCR 方案。
- `macocr` 不存在：引导用户在本包目录运行 `./install.sh`（编译需 Xcode Command Line
  Tools；Apple Silicon 无编译环境时自动回退到随附的预编译二进制）。安装完成后用
  `sh scripts/selftest.sh` 做一次端到端自检，通过后再继续。

安装与自检都完成后，每次会话无需重复执行。

## 执行任务的标准流程

按以下步骤处理用户的 OCR 请求，不要跳步：

1. **确认输入类型**。用户给的是图片（png/jpg/jpeg/heic/tiff）直接进第 3 步；
   是扫描版 PDF（无文字层）先进第 2 步转图。
2. **PDF 转图**（仅扫描版 PDF 需要）。用系统自带的 sips 渲染，144dpi 起步：

   ```bash
   sips -s format png -s dpiHeight 144 -s dpiWidth 144 输入.pdf --out /tmp/p1.png
   ```

   注意 sips 只处理单页；多页 PDF 需逐页指定或有 pymupdf 时用 4 倍矩阵渲染
   （小字号课件效果显著更好，见「扫描版 PDF 怎么用」）。
3. **运行识别**。默认命令即可覆盖绝大多数场景：

   ```bash
   macocr <图片路径>            # 多图可依次列出，输出用 === 分隔
   ```

   按场景追加参数（参数表见下）。识别结果是纯文本，已按视觉行序排好。
4. **结果交付**。直接向用户展示识别文本；表格/数字密集的结果必须提醒用户
   关键数字需二次确认（见「表格数据的特殊注意」）。

## 参数速查

| 参数 | 用途 |
|:--|:--|
| `--fast` | 关闭语言纠错。表格与数字场景推荐，避免数字被"纠错"成奇怪的值 |
| `--lang zh-Hans+en-US` | 默认中英混排。纯英文设 `en-US` 提速；繁体用 `zh-Hant` |
| `--rect x,y,w,h` | 只识别矩形区域（左上原点，像素）。大图里只提某个表格时使用 |
| `--upscale N` | 模糊小图（宽 <1000px 的转发图、旧扫描件）先 Lanczos 放大 N 倍（1.0–4.0）。**只在普通模式识别率差时逐级试 2 → 3**，清晰大图盲目放大会引入笔画粘连 |
| `--orientation up\|left\|right\|180` | 照片旋转/倒置时手动转正。Vision 不按 EXIF 自动转正，侧拍图必须用这个 |
| `--list-langs` | 列出本机支持的识别语言（用于安装自检，输出应含 zh-Hans） |

## 识别率低时的处理顺序

按成本从低到高尝试，不要一上来就上复杂方案：

1. **找原图**：聊天转发图识别率极低，先请用户提供原始文件
2. `--rect` 圈出目标区域，减少噪声
3. `--upscale 2`（模糊小图）
4. `--fast`（表格数字场景）
5. 图像预处理（裁剪 + 灰度 + 自动对比度 + 锐化 + 二值化），示例见下

```python
from PIL import Image, ImageOps, ImageEnhance
im = Image.open("src.JPG")
im.crop((x0, y0, x1, y1)).resize((w*2, h*2), Image.LANCZOS)   # 裁剪 + 放大
ImageOps.autocontrast(im.convert("L"))                         # 灰度 + 自动对比度
ImageEnhance.Sharpness(im).enhance(2.0)                        # 锐化
im.convert("L").point(lambda p: 255 if p > 128 else 0)         # 二值化
```

**多版本投票**：对同一个表格跑 2–3 种预处理，取一致部分，不一致的数字单独复核。
**交叉验证**：整行/整列求和能对上基本可信；对不上说明某个数字错了。

## 为什么「照片」App 的实况文本看起来比裸调 API 准？

同一个 Vision 引擎，差距来自**前后处理**，不是模型本身：

1. **方向**：「照片」按 EXIF 转正再识别；裸调 API 默认按 `.up` 处理 → 用 `--orientation` 补上
2. **分辨率**：「照片」用全分辨率原图；工作流里流转的常是压缩预览图 → 永远优先用原始文件
3. **隐式降采样**：`NSImage` 按「点」出图，@2x/@3x 截图与部分 HEIC 会被砍掉一半像素 → 本工具遍历 rep 取最大像素位图
4. **竖排文本**：实况文本能处理竖排；裸调用会把竖排切成碎行 → 本工具自动检测并做置信度仲裁
5. **交互红利**（无法完全复制）：实况文本允许点选局部，感知上"错得少"；命令行一次吐全文，任何错字都显眼

结论：**引擎相同，管线决定上限。**

## 表格数据的特殊注意

OCR 在表格上最容易出错：小数点被吞（`.` → `,`）、相邻列并成一串、行混淆。
关键数字必须二次确认：有 PDF 原件就抽文字层对照；只有照片就靠多版本投票 + 行列逻辑校验。

## 何时不用本工具

| 场景 | 更合适的选择 |
|---|---|
| 所用 AI 模型本身支持读图 | 直接让它看图，不必绕 OCR |
| 需要复杂版面还原（多栏、公式、表格框线结构） | MinerU 等版面级解析服务（数据会上云） |
| 整份扫描 PDF 批量转文字且可上云 | 云端 OCR 服务的批量接口 |

规则：**本地优先，数据不外发；确实需要更高精度再上云，且先确认数据可以外发。**

## 验证与排错

- 安装后自检：`sh scripts/selftest.sh`（用包内测试图端到端验证，输出 PASS/FAIL）
- 语言列表不含 zh-Hans：系统语言数据不完整，极少见；检查 macOS 版本是否 ≥ 13
- 输出为空或全错：先确认图片本身可读（`sips -g pixelWidth -g pixelHeight 图片`），
  再按「识别率低时的处理顺序」逐级尝试

## 系统要求

- macOS 13+（`automaticallyDetectsLanguage` 需要 13.0）
- 编译需要 Xcode Command Line Tools（`xcode-select --install`）；
  或使用随附的 Apple Silicon 预编译二进制（`scripts/macocr-arm64`，ad-hoc 签名）

## 包内文件说明

| 文件 | 用途 | 何时需要 |
|---|---|---|
| `install.sh` | 安装 macocr（编译优先，预编译兜底） | 环境检查发现 macocr 不存在时 |
| `scripts/selftest.sh` + `scripts/selftest.png` | 端到端自检（脚本 + 自带测试图） | 安装后验证；排查"识别异常"时先跑它确认工具本身正常 |
| `scripts/vision_ocr.swift` | 源代码（约 200 行，可审计） | 需要自行编译或审计时 |
| `scripts/macocr-arm64` | Apple Silicon 预编译二进制 | 无 swiftc 的 Apple Silicon 机器，由 install.sh 自动使用 |
