// 可选的抠图：用 Vision 把照片里的主体抠出来，背景透明，供实物格（object）用。
// 只处理使用者自己的照片；macOS 14 以上。用法：swift cutout.swift in.jpg out.png
import CoreImage
import Foundation
import Vision

func fail(_ message: String) -> Never {
    FileHandle.standardError.write((message + "\n").data(using: .utf8)!)
    exit(1)
}

let args = CommandLine.arguments
guard args.count == 3 else { fail("用法：swift cutout.swift in.jpg out.png") }
guard #available(macOS 14.0, *) else { fail("要 macOS 14 以上（VNGenerateForegroundInstanceMaskRequest）") }
guard let image = CIImage(contentsOf: URL(fileURLWithPath: args[1]), options: [.applyOrientationProperty: true]) else {
    fail("读不了 \(args[1])")
}
let handler = VNImageRequestHandler(ciImage: image)
let request = VNGenerateForegroundInstanceMaskRequest()
do { try handler.perform([request]) } catch { fail("Vision 出错：\(error)") }
guard let result = request.results?.first, !result.allInstances.isEmpty else { fail("没找到前景主体") }
guard let masked = try? result.generateMaskedImage(ofInstances: result.allInstances, from: handler,
                                                   croppedToInstancesExtent: false) else { fail("生成蒙版失败") }
let sRGB = CGColorSpace(name: CGColorSpace.sRGB)!
do {
    try CIContext().writePNGRepresentation(of: CIImage(cvPixelBuffer: masked), to: URL(fileURLWithPath: args[2]),
                                           format: .RGBA8, colorSpace: sRGB)
} catch { fail("写不了 \(args[2])：\(error)") }
print(args[2])
