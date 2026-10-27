import SwiftUI

struct ContentView: View {
    @Bindable var editor: Editor

    var body: some View {
        VStack(spacing: 0) {
            header
            EditorDivider()
            HStack(spacing: 0) {
                MediaSidebar(editor: editor)
                    .frame(width: 280)
                    .background(EditorTheme.sidebar)
                EditorDivider(vertical: true)
                ScrollView {
                    MetadataWorkspace(editor: editor)
                        .frame(maxWidth: 840)
                        .padding(30)
                        .frame(maxWidth: .infinity)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            EditorDivider()
            ExportBar(editor: editor)
        }
        .frame(minWidth: 900, minHeight: 640)
        .background(EditorTheme.canvas)
        .foregroundStyle(EditorTheme.ink)
        .tint(EditorTheme.accent)
        .preferredColorScheme(.light)
    }

    private var header: some View {
        HStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 10).fill(EditorTheme.accent)
                Image(systemName: "waveform")
                    .font(.system(size: 19, weight: .medium))
                    .foregroundStyle(EditorTheme.surface)
            }
            .frame(width: 36, height: 36)
            .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text("AudioTag").font(.system(size: 17, weight: .semibold))
                Text("音频标签工作台").font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
            }
            Spacer()
            Label("文件只在本机处理", systemImage: "lock.shield")
                .font(.system(size: 11))
                .foregroundStyle(EditorTheme.muted)
            EditorDivider(vertical: true).frame(height: 20).padding(.horizontal, 6)
            Button { editor.chooseFiles() } label: {
                HStack(spacing: 12) {
                    Label("打开文件", systemImage: "plus")
                    Text("⌘O").font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
                }
            }
            .buttonStyle(EditorButtonStyle())
            .disabled(editor.busy)
            .help("打开音频或视频（⌘O）")
        }
        .padding(.horizontal, 24)
        .frame(height: 68)
        .background(EditorTheme.surface)
    }
}
