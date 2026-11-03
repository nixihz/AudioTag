import SwiftUI

struct MetadataWorkspace: View {
    @Bindable var editor: Editor
    @State private var editingLyrics = false
    @State private var importExpanded = true
    @FocusState private var focusedField: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            introduction
            textImport
            tags
        }
    }

    private var introduction: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 8) {
                Text("音乐资料 / 标签编辑")
                    .font(.system(size: 10, weight: .semibold)).foregroundStyle(EditorTheme.accent)
                Spacer()
                if editor.files.count > 1 { EditorBadge(text: "批量编辑 · \(editor.files.count) 个文件") }
            }
            Text(editor.values["title"].flatMap { $0.isEmpty ? nil : $0 } ?? "为音乐，整理好每个细节。")
                .font(.system(size: 27, weight: .medium, design: .serif))
                .tracking(-0.5).lineLimit(2).textSelection(.enabled)
            Text(editor.files.isEmpty ? "先打开文件，也可以先粘贴信息准备标签。" : "粘贴歌曲信息快速填入，或直接编辑需要更新的字段。")
                .font(.system(size: 12)).foregroundStyle(EditorTheme.muted)
        }
    }

    private var textImport: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Button { importExpanded.toggle() } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "text.badge.plus").foregroundStyle(EditorTheme.accent)
                        Text("从文本快速填入").fontWeight(.semibold)
                        Image(systemName: importExpanded ? "chevron.down" : "chevron.right")
                            .font(.system(size: 9, weight: .semibold)).foregroundStyle(EditorTheme.muted)
                    }
                    .font(.system(size: 12)).contentShape(Rectangle())
                }
                .buttonStyle(.plain).disabled(editor.busy)
                .accessibilityLabel(importExpanded ? "收起文本导入" : "展开文本导入")
                Spacer()
                Button("使用示例") { editor.example(); importExpanded = true }
                    .buttonStyle(EditorButtonStyle(quiet: true)).disabled(editor.busy)
            }
            if importExpanded {
                textArea($editor.rawText, label: "歌曲信息文本", placeholder: "歌曲名称 (Title)：Beneath the Metal Sky\n艺术家 (Artist)：Silent Horizon\n歌词 (Lyrics)：…", height: 104, id: "raw")
                HStack {
                    Text("支持中英文标签 · 歌词放在最后").font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
                    Spacer()
                    Button {
                        Task {
                            await editor.parse()
                            if !editor.failed { importExpanded = false; focusedField = nil }
                        }
                    } label: { Label("解析并填入", systemImage: "arrow.down.to.line") }
                        .buttonStyle(EditorButtonStyle())
                        .disabled(editor.busy || editor.rawText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            } else {
                Text("已填入的内容可继续编辑；展开可重新粘贴。")
                    .font(.system(size: 11)).foregroundStyle(EditorTheme.muted)
            }
        }
        .padding(16)
        .background(EditorTheme.surface, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(EditorTheme.line, lineWidth: 1))
    }

    private var tags: some View {
        VStack(alignment: .leading, spacing: 17) {
            HStack {
                Picker("编辑内容", selection: $editingLyrics) {
                    Text("基本标签").tag(false)
                    Text("歌词").tag(true)
                }
                .pickerStyle(.segmented).labelsHidden().frame(width: 174).disabled(editor.busy)
                Spacer()
                EditorBadge(text: "\(editor.patch.count) 项待写入")
                Menu {
                    Button("勾选所有非空字段") {
                        editor.selected = Set(editor.values.filter { !$0.value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }.keys)
                    }
                    Button("取消全部勾选") { editor.selected.removeAll() }
                } label: { Image(systemName: "ellipsis.circle").font(.system(size: 16)) }
                    .menuStyle(.borderlessButton).frame(width: 22).disabled(editor.busy)
                    .help("批量选择字段").accessibilityLabel("字段选择")
            }
            HStack(alignment: .top, spacing: 6) {
                Image(systemName: "checkmark.square").foregroundStyle(EditorTheme.accent)
                Text(editor.files.count > 1 ? "仅写入勾选且非空的字段，将应用到全部 \(editor.files.count) 个文件。" : "勾选表示写入；未勾选或留空的字段保留原值。")
            }
            .font(.system(size: 11)).foregroundStyle(EditorTheme.muted)
            if editingLyrics { lyrics }
            else { basicFields }
        }
    }

    private var basicFields: some View {
        VStack(alignment: .leading, spacing: 17) {
            field("title", "歌曲名称")
            HStack(alignment: .top, spacing: 18) {
                field("artist", "艺术家 / 歌手")
                field("album", "专辑")
            }
            field("genre", "流派")
            HStack(alignment: .top, spacing: 18) {
                field("year", "年份")
                field("track", "音轨编号")
                field("bpm", "BPM")
            }
            if let text = editor.values["lyrics"], !text.isEmpty {
                Button { editingLyrics = true } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "text.alignleft").foregroundStyle(EditorTheme.accent)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(editor.selected.contains("lyrics") ? "歌词待写入" : "已有歌词 · 保留原值")
                                .font(.system(size: 12, weight: .medium))
                            Text("\(text.split(separator: "\n").count) 行 · 点击查看与编辑")
                                .font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
                        }
                        Spacer()
                        Image(systemName: "chevron.right").font(.system(size: 10, weight: .semibold)).foregroundStyle(EditorTheme.accent)
                    }
                    .padding(13)
                    .background(EditorTheme.accentSoft.opacity(0.6), in: RoundedRectangle(cornerRadius: 9))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain).disabled(editor.busy)
            }
        }
    }

    private var lyrics: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                fieldToggle("lyrics", "写入歌词")
                Spacer()
                let text = editor.values["lyrics"] ?? ""
                Text("\(text.isEmpty ? 0 : text.split(separator: "\n", omittingEmptySubsequences: false).count) 行")
                    .font(.system(size: 10, design: .monospaced)).foregroundStyle(EditorTheme.muted)
            }
            textArea(valueBinding("lyrics"), label: "歌词", placeholder: "在这里填写完整歌词，保留段落与换行。", height: 300, id: "lyrics")
            Text("保留换行与段落；此处编辑普通歌词，不生成同步时间轴。")
                .font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
        }
    }

    private func valueBinding(_ key: String) -> Binding<String> {
        Binding(get: { editor.values[key] ?? "" }, set: {
            editor.values[key] = $0
            if $0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { editor.selected.remove(key) }
            else { editor.selected.insert(key) }
        })
    }

    private func fieldToggle(_ key: String, _ label: String) -> some View {
        Toggle(label, isOn: Binding(get: { editor.selected.contains(key) }, set: {
            if $0 { editor.selected.insert(key) } else { editor.selected.remove(key) }
        }))
        .toggleStyle(.checkbox).font(.system(size: 11, weight: .medium)).disabled(editor.busy)
        .help("勾选且非空时写入，取消勾选则保留原值")
    }

    private func field(_ key: String, _ label: String) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            fieldToggle(key, label)
            TextField("保留原值", text: valueBinding(key))
                .textFieldStyle(.plain).font(.system(size: 13))
                .padding(.horizontal, 12).frame(height: 39)
                .background(EditorTheme.surface, in: RoundedRectangle(cornerRadius: 8))
                .overlay {
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(focusedField == key ? EditorTheme.accent : editor.selected.contains(key) ? EditorTheme.accent.opacity(0.5) : EditorTheme.line, lineWidth: focusedField == key ? 1.5 : 1)
                }
                .focused($focusedField, equals: key).disabled(editor.busy).accessibilityLabel(label)
        }
        .frame(maxWidth: .infinity)
    }

    private func textArea(_ binding: Binding<String>, label: String, placeholder: String, height: CGFloat, id: String) -> some View {
        ZStack(alignment: .topLeading) {
            if binding.wrappedValue.isEmpty {
                Text(placeholder).font(.system(size: 12)).foregroundStyle(EditorTheme.muted)
                    .padding(.horizontal, 13).padding(.vertical, 12).allowsHitTesting(false)
            }
            TextEditor(text: binding).font(.system(size: 12)).lineSpacing(4)
                .scrollContentBackground(.hidden).padding(8)
                .focused($focusedField, equals: id).disabled(editor.busy).accessibilityLabel(label)
        }
        .frame(height: height)
        .background(EditorTheme.surface, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(focusedField == id ? EditorTheme.accent : EditorTheme.line, lineWidth: focusedField == id ? 1.5 : 1)
        }
    }
}
