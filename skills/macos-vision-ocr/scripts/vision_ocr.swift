#!/usr/bin/env swift
// vision_ocr.swift —— macOS Vision 框架本地 OCR
//
// 版本：2.0
// 许可：MIT
//
// 编译（只需一次，需要 Xcode Command Line Tools 自带的 swiftc）：
//   xcode-select --install        # 如未装过命令行工具
//   swiftc -O vision_ocr.swift -o macocr
//   sudo cp macocr /usr/local/bin/          # 或放进任意 PATH 目录
//
// 用法：
//   macocr <图片路径> [<图片2> ...]
//   macocr --lang zh-Hans+en-US <图片路径>     # 指定识别语言，默认 zh-Hans + en-US
//   macocr --fast <图片路径>                    # 关闭语言纠错（表格/数字更接近原值）
//   macocr --rect 100,200,1400,900 <图片路径>   # 只识别指定区域（原点左上，像素）
//   macocr --upscale 2 <图片路径>               # 先 Lanczos 放大 N 倍再识别（模糊小图）
//   macocr --orientation up|left|right|180 <图片> # 纠正拍摄方向（默认 up）
//   macocr --list-langs                         # 列出本机可用的识别语言
//
// 输出：按视觉行序输出的纯文本，多图之间用 === 分隔。
//
// v2 设计说明（对照 macOS「照片」App 实况文本的行为）：
//   1. 竖排检测 + 置信度仲裁：横向长行占比过高时旋转 90° 二次识别，
//      仅当平均分置信度显著更高才采纳（纯几何阈值在表格/时间轴版式上误判多）。
//   2. 按真实像素出图：遍历 NSImageRep 取最大像素位图，避免 NSImage 按「点」
//      出图导致 @2x/@3x 截图与部分 HEIC 被隐式降采样。
//   3. --upscale：模糊小图（转发图、旧扫描件）先 Lanczos 放大再识别。
//      注意：清晰大图盲目放大可能引入笔画粘连，仅在普通模式效果差时逐级试。
//   4. --orientation：Vision 不按 EXIF 自动转正，侧拍/倒置图需手动指定——
//      这是「照片」App 识别率更高的主因之一（它先做转正）。

import Foundation
import Vision
import AppKit

// MARK: - 参数解析

var languageCodes = ["zh-Hans", "en-US"]
var langExplicit = false   // 用户显式传 --lang 时关闭自动检测，尊重其指定
var usesLanguageCorrection = true
var cropRect: CGRect? = nil
var upscaleFactor: CGFloat = 1.0
var orientation: CGImagePropertyOrientation = .up
var inputPaths: [String] = []
var listLangs = false

let orientationMap: [String: CGImagePropertyOrientation] = [
    "up": .up, "left": .left, "right": .right, "180": .down
]

var i = 1
let argv = CommandLine.arguments
while i < argv.count {
    switch argv[i] {
    case "--lang":
        i += 1
        if i < argv.count { languageCodes = argv[i].split(separator: "+").map(String.init); langExplicit = true }
    case "--fast":
        usesLanguageCorrection = false
    case "--rect":
        i += 1
        if i < argv.count {
            let p = argv[i].split(separator: ",").compactMap { Double(String($0)) }
            if p.count == 4 { cropRect = CGRect(x: p[0], y: p[1], width: p[2], height: p[3]) }
        }
    case "--upscale":
        i += 1
        if i < argv.count, let f = Double(argv[i]), f >= 1.0, f <= 4.0 {
            upscaleFactor = CGFloat(f)
        }
    case "--orientation":
        i += 1
        if i < argv.count, let o = orientationMap[argv[i]] { orientation = o }
    case "--list-langs":
        listLangs = true
    case "-h", "--help":
        print("""
        usage: macocr [--lang LANG+LANG] [--fast] [--rect x,y,w,h] [--upscale N] [--orientation up|left|right|180] [--list-langs] <image>...
        """)
        exit(0)
    default:
        inputPaths.append(argv[i])
    }
    i += 1
}

// MARK: - 列出可用语言

if listLangs {
    let req = VNRecognizeTextRequest()
    // revision 3 起才支持全部语言；这里尽力取最新支持列表
    let supported = (try? req.supportedRecognitionLanguages()) ?? []
    print(supported.joined(separator: "\n"))
    exit(0)
}

if inputPaths.isEmpty {
    FileHandle.standardError.write("错误: 请给出至少一个图片路径\n".data(using: .utf8)!)
    exit(1)
}

// MARK: - 图像加载（按真实像素出图）

/// NSImage 是「点」坐标系的容器，直接 tiffRepresentation 可能按点尺寸出图，
/// 导致 @2x/@3x 截图与部分 HEIC 被隐式降采样。这里遍历所有 rep，
/// 取像素尺寸最大的那个，保证喂给 Vision 的是全分辨率位图。
func loadFullPixelCGImage(_ path: String) -> CGImage? {
    guard let img = NSImage(contentsOfFile: path) else { return nil }
    var best: NSBitmapImageRep? = nil
    for rep in img.representations {
        guard let b = rep as? NSBitmapImageRep else { continue }
        if best == nil || b.pixelsWide * b.pixelsHigh > best!.pixelsWide * best!.pixelsHigh {
            best = b
        }
    }
    if let cg = best?.cgImage { return cg }
    // 兜底：按图片自身点尺寸光栅化
    guard let tiff = img.tiffRepresentation,
          let bmp = NSBitmapImageRep(data: tiff) else { return nil }
    return bmp.cgImage
}

/// Lanczos 放大：小图（手机转发图、旧扫描件）上采样后识别率明显提升。
func upscale(_ cg: CGImage, factor: CGFloat) -> CGImage {
    if factor <= 1.0 { return cg }
    let w = Int(CGFloat(cg.width) * factor)
    let h = Int(CGFloat(cg.height) * factor)
    guard let ctx = CGContext(data: nil, width: w, height: h,
                              bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
        return cg
    }
    ctx.interpolationQuality = .high
    ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
    return ctx.makeImage() ?? cg
}

// MARK: - 单次识别（返回行 + 平均分置信度）

struct OCRResult {
    var lines: [String]
    var meanConfidence: Float
    var wideLineRatio: Float   // 宽 > 高 2.5 倍的观测占比（竖排文本信号）
}

func runVision(on cg: CGImage, orientation o: CGImagePropertyOrientation) -> OCRResult {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = languageCodes
    request.usesLanguageCorrection = usesLanguageCorrection
    if #available(macOS 13.0, *) {
        // 显式传了 --lang 就关掉自动检测，避免混入列表外语言；
        // 未传则开启自动检测兜底（对纯英文/纯日文图更宽容）
        request.automaticallyDetectsLanguage = !langExplicit
    }

    let handler = VNImageRequestHandler(cgImage: cg, orientation: o, options: [:])
    do { try handler.perform([request]) } catch {
        return OCRResult(lines: ["   [识别失败] — \(error)"], meanConfidence: 0, wideLineRatio: 0)
    }
    guard let obs = request.results, !obs.isEmpty else {
        return OCRResult(lines: [], meanConfidence: 0, wideLineRatio: 0)
    }

    // 按视觉行序输出：先按 y 降序分组，组内按 x 升序
    let sorted = obs.sorted { a, b in
        let ay = a.boundingBox.origin.y
        let by = b.boundingBox.origin.y
        if abs(ay - by) > 0.012 { return ay > by }
        return a.boundingBox.origin.x < b.boundingBox.origin.x
    }
    let lines = sorted.compactMap { $0.topCandidates(1).first?.string }
    let confs = sorted.map { $0.confidence }
    let mean = confs.reduce(0, +) / Float(confs.count)
    let wide = obs.filter { $0.boundingBox.width > $0.boundingBox.height * 2.5 }.count
    return OCRResult(lines: lines,
                     meanConfidence: mean,
                     wideLineRatio: Float(wide) / Float(obs.count))
}

// MARK: - 单张图识别（含竖排仲裁）

func recognize(_ path: String) -> String {
    guard var cg = loadFullPixelCGImage(path) else {
        return "   [无法读取图片] \(path)"
    }

    if let r = cropRect {
        // CGImage 的 cropping 坐标系原点在左上，与 UI 一致；超界会被自动夹住
        if let c = cg.cropping(to: r) { cg = c }
    }
    cg = upscale(cg, factor: upscaleFactor)

    let primary = runVision(on: cg, orientation: orientation)
    if primary.lines.isEmpty { return "   [无结果] \(path)" }

    // 竖排检测：大量「超宽」观测行说明文字可能是竖排被横切。
    // 不直接采纳旋转结果，而是比较两个方向的平均分置信度——
    // 纯几何阈值在表格、时间轴等版式上误判率高（2026-10 实测教训）。
    if primary.wideLineRatio > 0.5 {
        let rotated = runVision(on: cg, orientation: .right)
        if rotated.meanConfidence > primary.meanConfidence + 0.05 {
            return "   [提示] 检测到竖排文本，已按顺时针旋转 90° 识别\n" + rotated.lines.joined(separator: "\n")
        }
    }
    return primary.lines.joined(separator: "\n")
}

// MARK: - 主流程

for (n, p) in inputPaths.enumerated() {
    if inputPaths.count > 1 {
        print("=== [\(n + 1)/\(inputPaths.count)] \(p)")
    }
    let text = recognize(p)
    print(text)
    fflush(stdout)
}
