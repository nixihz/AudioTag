import AppKit
import SwiftUI
import UniformTypeIdentifiers
import Mp3tagBridge

struct Reply: Decodable {
    var ok: Bool
    var result: ResultData?
    var error: ErrorData?
    struct ErrorData: Decodable { var message: String }
}
struct ResultData: Decodable {
    var metadata: [String: String]?
    var warnings: [String]?
    var cover: String?
    var output: String?
    var duration: Double?
    var audio_streams: [AudioStream]?
    var video_streams: [VideoStream]?
    struct AudioStream: Decodable, Identifiable { var index: Int; var codec: String; var channels: Int; var id: Int { index } }
    struct VideoStream: Decodable { var index: Int; var width: Int; var height: Int }
}

@MainActor @Observable final class Editor {
    static let fields = [("title", "歌曲名称"), ("artist", "艺术家 / 歌手"), ("album", "专辑"), ("genre", "流派"), ("year", "年份"), ("track", "音轨编号"), ("bpm", "BPM"), ("lyrics", "歌词")]
    var files: [URL] = []
    var values: [String: String] = [:]
    var selected = Set<String>()
    var rawText = ""
    var convert = false
    var useFirstFrame = true
    var bitrate = 320
    var audioStreams: [ResultData.AudioStream] = []
    var audioStream = 0
    var customCover: URL?
    var existingCover: NSImage?
    var frameCover: NSImage?
    var busy = false
    var message = "选择文件，粘贴信息，再写入标签。"
    var failed = false
    var outputURLs: [URL] = []

    var preview: NSImage? {
        if let customCover { return NSImage(contentsOf: customCover) }
        return convert && useFirstFrame ? frameCover : existingCover
    }
    var patch: [String: String] { values.filter { selected.contains($0.key) && !$0.value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty } }
    var canExport: Bool { !busy && !files.isEmpty && (convert || !patch.isEmpty || customCover != nil) }

    func call(_ request: [String: Any]) async throws -> ResultData {
        let data = try JSONSerialization.data(withJSONObject: request)
        let response = try await Engine.bundled().call(data)
        let reply = try JSONDecoder().decode(Reply.self, from: response)
        guard reply.ok, let result = reply.result else { throw EngineError(reply.error?.message ?? "操作失败") }
        return result
    }
    func report(_ text: String, error: Bool = false) { message = text; failed = error }
    func image(_ encoded: String?) -> NSImage? {
        guard let encoded, let body = encoded.split(separator: ",", maxSplits: 1).last, let data = Data(base64Encoded: String(body)) else { return nil }
        return NSImage(data: data)
    }
    func chooseFiles() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = ["mp3", "flac", "m4a", "mp4", "ogg", "opus", "wav"].compactMap { UTType(filenameExtension: $0) }
        panel.allowsMultipleSelection = true
        if panel.runModal() == .OK { Task { await load(panel.urls) } }
    }
    func load(_ urls: [URL]) async {
        guard !busy, !urls.isEmpty else { return }
        guard urls.count <= 32 else { report("每批最多 32 个文件", error: true); return }
        files = urls; busy = true; existingCover = nil; frameCover = nil; audioStreams = []; outputURLs = []
        values = values.filter { selected.contains($0.key) }
        defer { busy = false }
        report("正在读取文件信息…")
        do {
            let first = urls[0]
            let info = try await call(["operation": "inspect", "input": first.path, "include_cover": true])
            for (key, value) in info.metadata ?? [:] where !selected.contains(key) { values[key] = value }
            existingCover = image(info.cover)
            convert = urls.allSatisfy { $0.pathExtension.lowercased() == "mp4" }
            if first.pathExtension.lowercased() == "mp4" {
                let probe = try await call(["operation": "probe", "input": first.path])
                audioStreams = probe.audio_streams ?? []
                audioStream = audioStreams.first?.index ?? 0
                if !(probe.video_streams ?? []).isEmpty {
                    let frame = try await call(["operation": "frame", "input": first.path])
                    frameCover = image(frame.cover)
                } else { useFirstFrame = false }
            }
            report("已读取 \(urls.count) 个文件。字段显示首个文件的值，勾选字段将应用到全部文件。")
        } catch { report(error.localizedDescription, error: true) }
    }
    func chooseCover() {
        let panel = NSOpenPanel(); panel.allowedContentTypes = [.jpeg, .png]
        if panel.runModal() == .OK, let url = panel.url {
            customCover = url; report("导出时使用所选封面；未选封面时使用视频首帧或保留原封面。")
        }
    }
    func parse() async {
        busy = true; defer { busy = false }
        do {
            let result = try await call(["operation": "parse", "text": rawText])
            for (key, value) in result.metadata ?? [:] { values[key] = value; selected.insert(key) }
            report("已解析 \(result.metadata?.count ?? 0) 个字段。" + (result.warnings ?? []).joined(separator: "；"))
        } catch { report(error.localizedDescription, error: true) }
    }
    func example() {
        if let url = Bundle.main.url(forResource: "example", withExtension: "txt"), let text = try? String(contentsOf: url, encoding: .utf8) { rawText = text }
    }
    func export() async {
        let panel = NSOpenPanel(); panel.canChooseFiles = false; panel.canChooseDirectories = true; panel.canCreateDirectories = true
        panel.prompt = "导出到此文件夹"
        guard panel.runModal() == .OK, let folder = panel.url else { return }
        busy = true; outputURLs = []; defer { busy = false }
        let metadata = patch
        let isConverting = convert
        let cover = customCover
        var targets: [URL] = []
        var names = Set<String>()
        for source in files {
            let stem = source.deletingPathExtension().lastPathComponent
            let name = isConverting ? stem + ".mp3" : stem + ".tagged." + source.pathExtension
            let target = folder.appendingPathComponent(name)
            guard !FileManager.default.fileExists(atPath: target.path), names.insert(target.path.lowercased()).inserted else {
                report("输出文件已存在或文件名重复：\(name)。请选择其他目录。", error: true); return
            }
            targets.append(target)
        }
        for (index, source) in files.enumerated() {
            report("正在处理 \(index + 1)/\(files.count)：\(source.lastPathComponent)…")
            do {
                var request: [String: Any] = ["operation": isConverting ? "extract" : "patch", "input": source.path, "output": targets[index].path, "metadata": metadata]
                if let cover { request["cover"] = cover.path }
                if isConverting {
                    request["first_frame"] = useFirstFrame
                    request["bitrate"] = bitrate
                    if files.count == 1 { request["audio_stream"] = audioStream }
                }
                let result = try await call(request)
                if let output = result.output { outputURLs.append(URL(fileURLWithPath: output)) }
            } catch {
                report("处理失败：\(error.localizedDescription)\n已完成 \(outputURLs.count) 个文件，原文件未修改。", error: true); return
            }
        }
        report("已导出 \(outputURLs.count) 个文件，标签与封面已校验。原文件未修改。")
    }
}

@main struct Mp3tagApp: App {
    @State private var editor = Editor()
    @StateObject private var updater = AppUpdater()
    var body: some Scene {
        WindowGroup("AudioTag") {
            ContentView(editor: editor)
                .onAppear { NSApp.setActivationPolicy(.regular); NSApp.activate(ignoringOtherApps: true) }
        }.defaultSize(width: 1100, height: 780)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("打开音频或视频…") { editor.chooseFiles() }.keyboardShortcut("o")
                    .disabled(editor.busy)
            }
            CommandGroup(after: .appInfo) {
                Button("检查更新…", action: updater.check).disabled(!updater.canCheck || editor.busy)
            }
        }
        Settings { UpdateSettings(updater: updater).disabled(editor.busy) }
    }
}
