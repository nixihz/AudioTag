import AppKit
import Foundation

let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
let iconset = root.appendingPathComponent(".build/Mp3tag.iconset")
let assets = root.appendingPathComponent("assets")
try FileManager.default.createDirectory(at: iconset, withIntermediateDirectories: true)
try FileManager.default.createDirectory(at: assets, withIntermediateDirectories: true)
for (size, suffix) in [(16, ""), (32, ""), (64, "@2x"), (128, ""), (256, ""), (512, ""), (1024, "@2x")] {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
                                  bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                  isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
    let scale = CGFloat(size) / 1024
    let transform = NSAffineTransform()
    transform.scale(by: scale)
    transform.concat()
    NSColor(srgbRed: 167 / 255, green: 70 / 255, blue: 45 / 255, alpha: 1).setFill()
    NSBezierPath(roundedRect: NSRect(x: 96, y: 96, width: 832, height: 832), xRadius: 188, yRadius: 188).fill()
    NSColor(srgbRed: 1, green: 253 / 255, blue: 249 / 255, alpha: 1).setStroke()
    for (index, height) in [160, 310, 450, 270, 140].enumerated() {
        let line = NSBezierPath()
        line.lineWidth = 39
        line.lineCapStyle = .round
        let x = CGFloat(320 + index * 96)
        line.move(to: NSPoint(x: x, y: 512 - CGFloat(height) / 2))
        line.line(to: NSPoint(x: x, y: 512 + CGFloat(height) / 2))
        line.stroke()
    }
    NSGraphicsContext.restoreGraphicsState()
    let data = bitmap.representation(using: .png, properties: [:])!
    let logical = suffix.isEmpty ? size : size / 2
    try data.write(to: iconset.appendingPathComponent("icon_\(logical)x\(logical)\(suffix).png"))
    if size == 512 { try data.write(to: assets.appendingPathComponent("icon.png")) }
}
