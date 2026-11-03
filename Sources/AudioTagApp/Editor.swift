import AppKit
import SwiftUI
import UniformTypeIdentifiers
import AudioTagBridge

/// 编辑器的全部状态与操作。
///
/// 只负责协调：读取文件、解析文本、规划导出，
/// 具体的字段规则交给标签引擎，文件命名交给 ExportPlan。
@MainActor @Observable final class Editor {
    /// 打开的源文件。
    var files: [URL] = []
    /// 字段当前值。
    var values: [String: String] = [:]
    /// 待写入的字段名。
    var selected = Set<String>()
    /// 粘贴的歌曲信息原文。
    var rawText = ""

    /// 输出设置。
    var convert = false
    var useFirstFrame = true
    var bitrate = 320
    var audioStreams: [EngineResult.AudioStream] = []
    var audioStream = 0

    /// 封面来源：自选图片、原文件封面、视频首帧。
    var customCover: URL?
    var existingCover: NSImage?
    var frameCover: NSImage?

    /// 运行状态与底部提示。
    var busy = false
    var message = "选择文件，粘贴信息，再写入标签。"
    var failed = false
    var outputURLs: [URL] = []

    /// 当前应展示的封面。
    var preview: NSImage? {
        if let customCover { return NSImage(contentsOf: customCover) }
        return convert && useFirstFrame ? frameCover : existingCover
    }

    /// 待写入的补丁，只包含勾选且非空的字段。
    var patch: [String: String] {
        values.filter { selected.contains($0.key) && !$0.value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    }

    /// 是否可以导出。
    var canExport: Bool { !busy && !files.isEmpty && (convert || !patch.isEmpty || customCover != nil) }

    /// 标签引擎实例，定位一次后复用。
    private var engine: Engine?

    // MARK: - 引擎调用

    /// 向标签引擎发送一条请求并返回结果。
    func call(_ request: [String: Any]) async throws -> EngineResult {
        let data = try JSONSerialization.data(withJSONObject: request)
        let response = try await resolvedEngine().call(data)
        let reply = try JSONDecoder().decode(EngineReply.self, from: response)
        guard reply.ok, let result = reply.result else { throw EngineError(reply.error?.message ?? "操作失败") }
        return result
    }

    private func resolvedEngine() throws -> Engine {
        if let engine { return engine }
        let engine = try Engine.bundled()
        self.engine = engine
        return engine
    }

    /// 更新底部状态提示。
    func report(_ text: String, error: Bool = false) { message = text; failed = error }

    /// 把 data URI 还原成图片。
    func image(_ encoded: String?) -> NSImage? {
        guard let encoded, let body = encoded.split(separator: ",", maxSplits: 1).last, let data = Data(base64Encoded: String(body)) else { return nil }
        return NSImage(data: data)
    }

    // MARK: - 打开文件

    /// 弹出系统面板选择音频或视频。
    func chooseFiles() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = ["mp3", "flac", "m4a", "mp4", "ogg", "opus", "wav"].compactMap { UTType(filenameExtension: $0) }
        panel.allowsMultipleSelection = true
        if panel.runModal() == .OK { Task { await load(panel.urls) } }
    }

    /// 读取一批文件，以首个文件的标签作为参考。
    func load(_ urls: [URL]) async {
        guard !busy, !urls.isEmpty else { return }
        guard urls.count <= 32 else { report("每批最多 32 个文件", error: true); return }
        files = urls; busy = true; existingCover = nil; frameCover = nil; audioStreams = []; outputURLs = []
        values = values.filter { selected.contains($0.key) }
        defer { busy = false }
        report("正在读取文件信息…")
        do {
            try await readSource(urls[0])
            report("已读取 \(urls.count) 个文件。字段显示首个文件的值，勾选字段将应用到全部文件。")
        } catch { report(error.localizedDescription, error: true) }
    }

    /// 读取首个文件的标签、封面与音视频流信息。
    private func readSource(_ source: URL) async throws {
        let info = try await call(["operation": "inspect", "input": source.path, "include_cover": true])
        for (key, value) in info.metadata ?? [:] where !selected.contains(key) { values[key] = value }
        existingCover = image(info.cover)
        convert = files.allSatisfy { $0.pathExtension.lowercased() == "mp4" }
        guard source.pathExtension.lowercased() == "mp4" else { return }
        let probe = try await call(["operation": "probe", "input": source.path])
        audioStreams = probe.audioStreams ?? []
        audioStream = audioStreams.first?.index ?? 0
        if !(probe.videoStreams ?? []).isEmpty {
            let frame = try await call(["operation": "frame", "input": source.path])
            frameCover = image(frame.cover)
        } else {
            useFirstFrame = false
        }
    }

    // MARK: - 封面与文本

    /// 弹出系统面板选择封面图片。
    func chooseCover() {
        let panel = NSOpenPanel(); panel.allowedContentTypes = [.jpeg, .png]
        if panel.runModal() == .OK, let url = panel.url {
            customCover = url; report("导出时使用所选封面；未选封面时使用视频首帧或保留原封面。")
        }
    }

    /// 解析粘贴的歌曲信息并填入字段。
    func parse() async {
        busy = true; defer { busy = false }
        do {
            let result = try await call(["operation": "parse", "text": rawText])
            for (key, value) in result.metadata ?? [:] { values[key] = value; selected.insert(key) }
            report("已解析 \(result.metadata?.count ?? 0) 个字段。" + (result.warnings ?? []).joined(separator: "；"))
        } catch { report(error.localizedDescription, error: true) }
    }

    /// 载入内置示例。
    func example() {
        if let url = Bundle.main.url(forResource: "example", withExtension: "txt"), let text = try? String(contentsOf: url, encoding: .utf8) { rawText = text }
    }

    // MARK: - 导出

    /// 选择目录并导出副本，原文件始终不修改。
    func export() async {
        let panel = NSOpenPanel(); panel.canChooseFiles = false; panel.canChooseDirectories = true; panel.canCreateDirectories = true
        panel.prompt = "导出到此文件夹"
        guard panel.runModal() == .OK, let folder = panel.url else { return }
        busy = true; outputURLs = []; defer { busy = false }
        let metadata = patch
        let isConverting = convert
        let cover = customCover
        let targets: [URL]
        do {
            targets = try ExportPlan.targets(for: files, in: folder, convertingToMP3: isConverting)
        } catch {
            report(error.localizedDescription, error: true); return
        }
        for (index, source) in files.enumerated() {
            report("正在处理 \(index + 1)/\(files.count)：\(source.lastPathComponent)…")
            do {
                let request = exportRequest(source: source, target: targets[index], metadata: metadata, converting: isConverting, cover: cover)
                let result = try await call(request)
                if let output = result.output { outputURLs.append(URL(fileURLWithPath: output)) }
            } catch {
                report("处理失败：\(error.localizedDescription)\n已完成 \(outputURLs.count) 个文件，原文件未修改。", error: true); return
            }
        }
        report("已导出 \(outputURLs.count) 个文件，标签与封面已校验。原文件未修改。")
    }

    /// 组装单个文件的导出请求。
    private func exportRequest(source: URL, target: URL, metadata: [String: String], converting: Bool, cover: URL?) -> [String: Any] {
        var request: [String: Any] = ["operation": converting ? "extract" : "patch", "input": source.path, "output": target.path, "metadata": metadata]
        if let cover { request["cover"] = cover.path }
        if converting {
            request["first_frame"] = useFirstFrame
            request["bitrate"] = bitrate
            if files.count == 1 { request["audio_stream"] = audioStream }
        }
        return request
    }
}
