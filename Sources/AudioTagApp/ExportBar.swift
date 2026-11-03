import AppKit
import SwiftUI

struct ExportBar: View {
    @Bindable var editor: Editor
    @State private var feedbackID = UUID()
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 10).fill(statusColor.opacity(0.08))
                if editor.busy { ProgressView().controlSize(.small) }
                else {
                    Image(systemName: statusSymbol)
                        .font(.system(size: 17)).foregroundStyle(statusColor)
                        .id(feedbackID)
                        .transition(.opacity.combined(with: .scale(scale: reduceMotion ? 1 : 0.95)))
                }
            }
            .frame(width: 38, height: 38)
            VStack(alignment: .leading, spacing: 4) {
                Text(statusTitle).font(.system(size: 12, weight: .semibold)).foregroundStyle(statusColor)
                Text(editor.message).font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
                    .lineLimit(2).textSelection(.enabled).help(editor.message)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityElement(children: .combine)
            if !editor.outputURLs.isEmpty && !editor.busy {
                Button { NSWorkspace.shared.activateFileViewerSelecting(editor.outputURLs) } label: {
                    Label("查看文件", systemImage: "folder")
                }
                .buttonStyle(EditorButtonStyle()).help("在 Finder 中显示已导出的文件")
            }
            Button {
                let feedback = EditorMotion.pointerInitiated ? (reduceMotion ? EditorMotion.gentle : EditorMotion.feedback) : nil
                Task {
                    await editor.export()
                    if !editor.outputURLs.isEmpty || editor.failed {
                        withAnimation(feedback) { feedbackID = UUID() }
                    }
                }
            } label: {
                HStack(spacing: 10) {
                    Text(editor.busy ? "正在处理…" : editor.convert ? "导出 MP3" : "写入并导出")
                    Image(systemName: "arrow.up.right").font(.system(size: 10, weight: .semibold))
                }
                .frame(minWidth: 110)
            }
            .buttonStyle(EditorButtonStyle(primary: true))
            .keyboardShortcut("e", modifiers: [.command, .shift])
            .disabled(!editor.canExport)
            .help("导出副本，不修改原文件（⌘⇧E）")
        }
        .padding(.horizontal, 24).frame(height: 80).background(EditorTheme.surface)
    }

    private var statusSymbol: String {
        if editor.failed { return "exclamationmark.triangle" }
        return editor.outputURLs.isEmpty ? "square.and.arrow.up" : "checkmark.circle"
    }

    private var statusColor: Color {
        if editor.failed { return EditorTheme.error }
        if !editor.outputURLs.isEmpty && !editor.busy { return EditorTheme.success }
        return EditorTheme.accent
    }

    private var statusTitle: String {
        if editor.busy { return "正在处理，请稍候" }
        if editor.failed { return "操作未完成" }
        if !editor.outputURLs.isEmpty { return "已导出 \(editor.outputURLs.count) 个文件 · 原文件未修改" }
        if editor.files.isEmpty { return "从打开一个文件开始" }
        if !editor.canExport { return "文件已就绪 · 编辑标签或选择封面后导出" }
        return "\(editor.files.count) 个文件 · \(editor.patch.count) 项标签待写入 · 导出副本"
    }
}
