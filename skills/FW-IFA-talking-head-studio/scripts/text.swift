// 用 macOS Vision 给一批 jpg 做文字识别（OCR），给 qa 的「B-roll 里有可读文字」用。
// 用法：text <帧目录>   → stdout 输出 JSON {"文件名": [{"t": "识别到的字", "c": 置信度, "x","y","w","h"}...]}
// 坐标是 0–1 归一化值，原点在左上。只报「≥4 个字且置信度 ≥0.5」的结果，避免把纹理当成字。
import Foundation
import Vision
import AppKit

let dir = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "."
// 阈值可调（默认 4 字／0.5，给 qa 用）；素材体检用 OCR_MIN_CHARS=3 OCR_MIN_CONF=0.3（缩略图上的字小，宁可多报）
let env = ProcessInfo.processInfo.environment
let minChars = Int(env["OCR_MIN_CHARS"] ?? "") ?? 4
let minConf = Float(env["OCR_MIN_CONF"] ?? "") ?? 0.5
let fm = FileManager.default
let files = ((try? fm.contentsOfDirectory(atPath: dir)) ?? []).filter { $0.hasSuffix(".jpg") }.sorted()
var result: [String: [[String: Any]]] = [:]
for f in files {
    let url = URL(fileURLWithPath: dir).appendingPathComponent(f)
    guard let img = NSImage(contentsOf: url),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    if #available(macOS 13.0, *) {
        req.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"]
    }
    let h = VNImageRequestHandler(cgImage: cg, options: [:])
    try? h.perform([req])
    var hits: [[String: Any]] = []
    for o in (req.results ?? []) {
        guard let top = o.topCandidates(1).first else { continue }
        let s = top.string.trimmingCharacters(in: .whitespacesAndNewlines)
        // 纯数字/符号、过短的都不算「可读文字」（计数器、时间码、纹理常被识别成一两个字符）
        let letters = s.filter { $0.isLetter || $0.isNumber }
        if letters.count < minChars || top.confidence < minConf { continue }
        let b = o.boundingBox
        hits.append(["t": s, "c": Double(top.confidence),
                     "x": Double(b.origin.x), "y": Double(1 - b.origin.y - b.size.height),
                     "w": Double(b.size.width), "h": Double(b.size.height)])
    }
    result[f] = hits
}
let data = try! JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
