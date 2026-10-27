import AppKit
import SwiftUI

enum EditorTheme {
    static let accent = color(0xA7462D)
    static let accentSoft = color(0xF6EAE3)
    static let canvas = color(0xF6F4F0)
    static let sidebar = color(0xEFECE6)
    static let surface = color(0xFFFDF9)
    static let ink = color(0x302C28)
    static let muted = color(0x70685F)
    static let line = color(0xDDD6CC)
    static let success = color(0x39705B)
    static let error = color(0xA12F36)

    private static func color(_ hex: UInt32) -> Color {
        Color(.sRGB, red: Double((hex >> 16) & 255) / 255,
              green: Double((hex >> 8) & 255) / 255, blue: Double(hex & 255) / 255, opacity: 1)
    }
}

enum EditorMotion {
    static let press = Animation.timingCurve(0.23, 1, 0.32, 1, duration: 0.12)
    static let feedback = Animation.timingCurve(0.23, 1, 0.32, 1, duration: 0.20)
    static let gentle = Animation.timingCurve(0.23, 1, 0.32, 1, duration: 0.12)

    @MainActor static var pointerInitiated: Bool {
        guard let event = NSApp.currentEvent?.type else { return false }
        return [.leftMouseDown, .leftMouseUp, .leftMouseDragged].contains(event)
    }
}

struct EditorDivider: View {
    var vertical = false

    var body: some View {
        Rectangle().fill(EditorTheme.line)
            .frame(width: vertical ? 1 : nil, height: vertical ? nil : 1)
            .accessibilityHidden(true)
    }
}

struct EditorSectionHeading: View {
    let title: String
    var detail = ""

    var body: some View {
        HStack {
            Text(title).font(.system(size: 12, weight: .semibold))
            Spacer(minLength: 8)
            if !detail.isEmpty {
                Text(detail).font(.system(size: 10)).foregroundStyle(EditorTheme.muted)
            }
        }
    }
}

struct EditorBadge: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(size: 10, weight: .medium))
            .foregroundStyle(EditorTheme.accent)
            .padding(.horizontal, 9).padding(.vertical, 5)
            .background(EditorTheme.accentSoft, in: Capsule())
    }
}

struct EditorButtonStyle: ButtonStyle {
    var primary = false
    var quiet = false
    @Environment(\.isEnabled) private var enabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var hovering = false

    func makeBody(configuration: Configuration) -> some View {
        let pointerPress = configuration.isPressed && EditorMotion.pointerInitiated
        configuration.label
            .font(.system(size: 12, weight: .medium))
            .padding(.horizontal, quiet ? 8 : 14)
            .frame(minHeight: quiet ? 28 : 36)
            .foregroundStyle(primary ? EditorTheme.surface : quiet ? EditorTheme.accent : EditorTheme.ink)
            .background(background, in: RoundedRectangle(cornerRadius: 8))
            .overlay {
                RoundedRectangle(cornerRadius: 8)
                    .strokeBorder(primary || quiet ? .clear : EditorTheme.line, lineWidth: 1)
            }
            .opacity(enabled ? 1 : 0.42)
            .brightness(primary && hovering && enabled ? -0.035 : 0)
            .scaleEffect(pointerPress && enabled && !reduceMotion ? 0.98 : 1)
            // 键盘触发保持即时，只有鼠标按压使用轻微缩放反馈。
            .animation(EditorMotion.pointerInitiated && !reduceMotion ? EditorMotion.press : nil, value: pointerPress)
            .onHover { hovering = $0 }
    }

    private var background: Color {
        if primary { return EditorTheme.accent }
        if quiet { return hovering && enabled ? EditorTheme.accentSoft : .clear }
        return hovering && enabled ? EditorTheme.accentSoft : EditorTheme.surface
    }
}
