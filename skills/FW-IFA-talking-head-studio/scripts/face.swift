// 用 macOS Vision 给一批 jpg 做人脸检测：位置、大小、偏航角（yaw，判断是否正对镜头）。
// 用法：face <帧目录>   → stdout 输出 JSON {"文件名": [{"x","y","w","h","yaw","roll","conf"}...]}
// 坐标是 0–1 的归一化值，原点在左上（已从 Vision 的左下原点翻转）。
import Foundation
import Vision
import AppKit

let dir = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "."
let fm = FileManager.default
let files = ((try? fm.contentsOfDirectory(atPath: dir)) ?? []).filter { $0.hasSuffix(".jpg") }.sorted()
var result: [String: [[String: Double]]] = [:]
for f in files {
    let url = URL(fileURLWithPath: dir).appendingPathComponent(f)
    guard let img = NSImage(contentsOf: url),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNDetectFaceRectanglesRequest()
    if #available(macOS 12.0, *) { req.revision = VNDetectFaceRectanglesRequestRevision3 }
    let h = VNImageRequestHandler(cgImage: cg, options: [:])
    try? h.perform([req])
    var faces: [[String: Double]] = []
    for o in (req.results ?? []) {
        let b = o.boundingBox
        faces.append([
            "x": Double(b.origin.x), "y": Double(1 - b.origin.y - b.size.height),
            "w": Double(b.size.width), "h": Double(b.size.height),
            "yaw": o.yaw?.doubleValue ?? 0, "roll": o.roll?.doubleValue ?? 0,
            "conf": Double(o.confidence),
        ])
    }
    result[f] = faces
}
let data = try! JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
