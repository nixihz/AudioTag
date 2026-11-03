import XCTest
@testable import AudioTagApp

final class ExportPlanTests: XCTestCase {
    private func makeFolder() throws -> URL {
        let folder = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        return folder
    }

    func testFileNameFollowsTheOutputMode() {
        let source = URL(fileURLWithPath: "/tmp/目录/我的歌.mp4")
        XCTAssertEqual(ExportPlan.fileName(for: source, convertingToMP3: true), "我的歌.mp3")
        XCTAssertEqual(ExportPlan.fileName(for: source, convertingToMP3: false), "我的歌.tagged.mp4")
    }

    func testEverySourceGetsATarget() throws {
        let folder = try makeFolder()
        defer { try? FileManager.default.removeItem(at: folder) }
        let sources = [URL(fileURLWithPath: "/tmp/a.mp3"), URL(fileURLWithPath: "/tmp/b.flac")]
        let targets = try ExportPlan.targets(for: sources, in: folder, convertingToMP3: false)
        XCTAssertEqual(targets.map(\.lastPathComponent), ["a.tagged.mp3", "b.tagged.flac"])
        XCTAssertTrue(targets.allSatisfy { $0.deletingLastPathComponent().path == folder.path })
    }

    func testExistingTargetIsRejected() throws {
        let folder = try makeFolder()
        defer { try? FileManager.default.removeItem(at: folder) }
        try Data().write(to: folder.appendingPathComponent("song.tagged.mp3"))
        let source = URL(fileURLWithPath: "/tmp/song.mp3")
        XCTAssertThrowsError(try ExportPlan.targets(for: [source], in: folder, convertingToMP3: false)) { error in
            XCTAssertTrue(error.localizedDescription.contains("输出文件已存在或文件名重复"))
        }
    }

    func testDuplicateNamesAreRejected() {
        let folder = URL(fileURLWithPath: NSTemporaryDirectory())
        let sources = [URL(fileURLWithPath: "/tmp/Song.mp3"), URL(fileURLWithPath: "/tmp/song.mp3")]
        XCTAssertThrowsError(try ExportPlan.targets(for: sources, in: folder, convertingToMP3: false))
    }

    func testConvertingAlwaysProducesMP3Names() throws {
        let folder = try makeFolder()
        defer { try? FileManager.default.removeItem(at: folder) }
        let sources = [URL(fileURLWithPath: "/tmp/clip.mp4")]
        let targets = try ExportPlan.targets(for: sources, in: folder, convertingToMP3: true)
        XCTAssertEqual(targets.map(\.lastPathComponent), ["clip.mp3"])
    }
}
