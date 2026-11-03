import AppKit
import SwiftUI

@main struct AudioTagApp: App {
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
