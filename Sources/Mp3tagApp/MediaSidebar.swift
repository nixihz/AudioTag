import AppKit
import SwiftUI

struct MediaSidebar: View {
    @Bindable var editor: Editor
    @State private var draggingFile = false
    @State private var animateCover = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    files
                        .dropDestination(for: URL.self) { urls, _ in
                            guard !editor.busy else { return false }
                            Task { await editor.load(urls) }
                            return true
                        } isTargeted: { draggingFile = $0 }
                    EditorDivider()
                    cover
                }
                .padding(22)
            }
            EditorDivider()
            output.padding(.horizontal, 22).padding(.vertical, 18)
        }
    }

    private var files: some View {
        VStack(alignment: .leading, spacing: 12) {
            EditorSectionHeading(title: "源文件", detail: editor.files.isEmpty ? "最多 32 个" : "\(editor.files.count) 个文件")
            if editor.files.isEmpty {
                Button { editor.chooseFiles() } label: {
                    VStack(spacing: 10) {
                        Image(systemName: "arrow.down.doc")
                            .font(.system(size: 23, weight: .light)).foregroundStyle(EditorTheme.accent)
                            .frame(width: 46, height: 46)
                            .background(EditorTheme.accentSoft, in: RoundedRectangle(cornerRadius: 12))
                        Text("拖入音频或视频").font(.system(size: 13, weight: .medium))
                        Text("或点击此处选择").font(.system(size: 11)).foregroundStyle(EditorTheme.muted)
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 22).contentShape(Rectangle())
                }
                .buttonStyle(.plain).disabled(editor.busy)
                .background(draggingFile ? EditorTheme.accentSoft : EditorTheme.surface.opacity(0.7), in: RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(draggingFile ? EditorTheme.accent : EditorTheme.line, style: StrokeStyle(lineWidth: 1, dash: [5, 4]))
                }
                Text("MP3 · FLAC · M4A · MP4\nOGG · OPUS · WAV")
                    .font(.system(size: 9, design: .monospaced)).foregroundStyle(EditorTheme.muted)
            } else {
                ScrollView {
                    VStack(spacing: 0) {
                        ForEach(Array(editor.files.enumerated()), id: \.offset) { index, file in
                            fileRow(file, index: index)
                            if index < editor.files.count - 1 { EditorDivider().padding(.leading, 38) }
                        }
                    }
                }
                .frame(height: min(CGFloat(editor.files.count) * 66, 184))
                .background(EditorTheme.surface.opacity(0.75), in: RoundedRectangle(cornerRadius: 10))
                HStack {
                    Text("以首个文件的标签为参考").font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
                    Spacer(minLength: 0)
                    Button("更换") { editor.chooseFiles() }
                        .buttonStyle(EditorButtonStyle(quiet: true)).disabled(editor.busy)
                }
            }
        }
    }

    private func fileRow(_ file: URL, index: Int) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: file.pathExtension.lowercased() == "mp4" ? "film" : "music.note")
                .font(.system(size: 14)).foregroundStyle(EditorTheme.accent)
                .frame(width: 18).padding(.top, 2)
            VStack(alignment: .leading, spacing: 4) {
                Text(file.deletingPathExtension().lastPathComponent)
                    .font(.system(size: 12, weight: .medium)).lineLimit(2).help(file.path)
                Text(file.pathExtension.uppercased() + (index == 0 ? "  ·  标签参考" : ""))
                    .font(.system(size: 9, design: .monospaced)).foregroundStyle(EditorTheme.muted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(12)
    }

    private var cover: some View {
        VStack(alignment: .leading, spacing: 12) {
            EditorSectionHeading(title: "唱片封面", detail: coverDescription)
            ZStack {
                RoundedRectangle(cornerRadius: 12).fill(EditorTheme.surface)
                Group {
                    if let image = editor.preview {
                        Image(nsImage: image).resizable().scaledToFit().padding(1)
                    } else { recordPlaceholder }
                }
                .id(editor.customCover)
                .transition(.opacity)
            }
            .frame(height: 220)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(EditorTheme.line.opacity(0.7), lineWidth: 1))
            // 封面只淡入，不移动正在校对的内容；键盘打开面板时不播放。
            .animation(animateCover ? (reduceMotion ? EditorMotion.gentle : EditorMotion.feedback) : nil, value: editor.customCover)
            .accessibilityLabel("封面预览，\(coverDescription)")
            HStack(spacing: 8) {
                Button {
                    animateCover = EditorMotion.pointerInitiated
                    editor.chooseCover()
                } label: {
                    Label(editor.customCover == nil ? "选择封面" : "更换封面", systemImage: "photo")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(EditorButtonStyle())
                if editor.customCover != nil {
                    Button {
                        animateCover = EditorMotion.pointerInitiated
                        editor.customCover = nil
                    } label: { Image(systemName: "xmark") }
                        .buttonStyle(EditorButtonStyle())
                        .help("取消本次替换，恢复原封面或视频首帧").accessibilityLabel("取消替换封面")
                }
            }
            .disabled(editor.busy)
            Text("JPEG 或 PNG；不选则保留原封面。")
                .font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
        }
    }

    private var recordPlaceholder: some View {
        VStack(spacing: 12) {
            ZStack {
                Circle().fill(EditorTheme.ink)
                ForEach(0..<5) { ring in
                    Circle().strokeBorder(EditorTheme.surface.opacity(0.12), lineWidth: 1)
                        .padding(CGFloat(8 + ring * 7))
                }
                Circle().fill(EditorTheme.accent).frame(width: 45, height: 45)
                Circle().fill(EditorTheme.surface).frame(width: 8, height: 8)
            }
            .frame(width: 132, height: 132).accessibilityHidden(true)
            Text("每一首，都值得好好收藏")
                .font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
        }
    }

    private var output: some View {
        VStack(alignment: .leading, spacing: 12) {
            EditorSectionHeading(title: "输出设置")
            Picker("输出模式", selection: $editor.convert) {
                Text("保留格式").tag(false)
                Text("转为 MP3").tag(true)
            }
            .pickerStyle(.segmented).labelsHidden().disabled(editor.busy)
            if editor.convert {
                HStack {
                    Text("音频码率").font(.system(size: 11)).foregroundStyle(EditorTheme.muted)
                    Spacer()
                    Picker("音频码率", selection: $editor.bitrate) {
                        ForEach([128, 192, 256, 320], id: \.self) { Text("\($0) kbps").tag($0) }
                    }
                    .labelsHidden().frame(width: 116).disabled(editor.busy)
                }
                Toggle("使用视频首帧作封面", isOn: $editor.useFirstFrame)
                    .font(.system(size: 11)).toggleStyle(.checkbox).disabled(editor.busy || editor.customCover != nil)
                if editor.audioStreams.count > 1 && editor.files.count == 1 {
                    Picker("音轨", selection: $editor.audioStream) {
                        ForEach(editor.audioStreams) { Text("流 \($0.index) · \($0.codec)").tag($0.index) }
                    }.disabled(editor.busy)
                }
                Label("将重新编码，无法提升原音质。", systemImage: "info.circle")
                    .font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
                Text(editor.customCover != nil ? "所选封面优先于视频首帧。" : "纯音频请关闭首帧；批量使用各文件第一音轨。")
                    .font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                Text("不重新编码，只更新勾选的标签。")
                    .font(.system(size: 11)).foregroundStyle(EditorTheme.muted)
            }
        }
    }

    private var coverDescription: String {
        if editor.customCover != nil { return "本次替换" }
        if editor.convert && editor.useFirstFrame && editor.frameCover != nil { return "视频首帧" }
        return editor.existingCover == nil ? "尚未添加" : "保留原封面"
    }
}
