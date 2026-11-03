import Combine
import Foundation
import Sparkle
import SwiftUI

struct UpdateConfiguration {
    init?(info: [String: Any]) {
        guard let feed = info["SUFeedURL"] as? String,
              let url = URL(string: feed),
              url.scheme == "https", let host = url.host, !host.isEmpty,
              url.user == nil, url.password == nil, url.query == nil, url.fragment == nil,
              let key = info["SUPublicEDKey"] as? String,
              let bytes = Data(base64Encoded: key), bytes.count == 32,
              let build = info["CFBundleVersion"] as? String,
              !build.isEmpty else { return nil }
    }
}

@MainActor final class AppUpdater: ObservableObject {
    @Published private(set) var canCheck = false
    @Published private(set) var automaticallyChecks = false
    @Published private(set) var status = "当前构建未配置在线更新。"
    private var controller: SPUStandardUpdaterController?

    init() {
        guard ProcessInfo.processInfo.environment["XCTestConfigurationFilePath"] == nil,
              !ProcessInfo.processInfo.arguments.contains("--ui-testing"),
              UpdateConfiguration(info: Bundle.main.infoDictionary ?? [:]) != nil else { return }
        // 全应用共用更新控制器，避免多个窗口各自弹出检查提示。
        let controller = SPUStandardUpdaterController(startingUpdater: false, updaterDelegate: nil, userDriverDelegate: nil)
        self.controller = controller
        controller.updater.publisher(for: \.canCheckForUpdates).assign(to: &$canCheck)
        controller.updater.publisher(for: \.automaticallyChecksForUpdates).assign(to: &$automaticallyChecks)
        do {
            try controller.updater.start()
            status = "更新从 AudioTag 官网下载，并校验签名。"
        } catch {
            self.controller = nil
            status = "无法启动更新：\(error.localizedDescription)"
        }
    }

    func check() { controller?.checkForUpdates(nil) }
    func setAutomaticallyChecks(_ enabled: Bool) {
        controller?.updater.automaticallyChecksForUpdates = enabled
    }
}

struct UpdateSettings: View {
    @ObservedObject var updater: AppUpdater

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("软件更新").font(.title2.weight(.semibold))
            HStack {
                Text("AudioTag \(version)")
                Spacer()
                Button("检查更新…", action: updater.check)
                    .buttonStyle(EditorButtonStyle())
                    .disabled(!updater.canCheck)
            }
            Toggle("自动检查更新", isOn: updateToggle)
            Text(updater.status).font(.caption).foregroundStyle(EditorTheme.muted)
            Link("访问官网与版本记录", destination: URL(string: "https://audiotag.xiezhixin.com/")!)
                .foregroundStyle(EditorTheme.accent)
        }
        .padding(28).frame(width: 440)
        .background(EditorTheme.canvas).foregroundStyle(EditorTheme.ink).tint(EditorTheme.accent)
        .preferredColorScheme(.light)
    }

    private var version: String {
        let info = Bundle.main.infoDictionary ?? [:]
        return "\(info["CFBundleShortVersionString"] as? String ?? "开发版")（\(info["CFBundleVersion"] as? String ?? "—")）"
    }

    /// 开关的读写闭包。
    ///
    /// 这里必须写成显式闭包，不能直接传 `updater.setAutomaticallyChecks`：
    /// 方法引用是对隔离方法的偏应用，Swift 需要为其生成 reabstraction thunk，
    /// 而在旧版 SwiftUI SDK（`Binding.init(get:set:)` 非隔离）上，Swift 6.1/6.2
    /// 的编译器会在生成该 thunk 时崩溃。
    private var updateToggle: Binding<Bool> {
        Binding(
            get: { updater.automaticallyChecks },
            set: { enabled in updater.setAutomaticallyChecks(enabled) }
        )
    }
}
