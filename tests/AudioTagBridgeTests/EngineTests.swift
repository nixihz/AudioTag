import Foundation
import XCTest
@testable import AudioTagBridge

final class EngineTests: XCTestCase {
    func testNativeBridgeUsesRealJSONEngine() async throws {
        let path = ProcessInfo.processInfo.environment["AUDIOTAG_TEST_ENGINE"] ?? ProcessInfo.processInfo.environment["AUDIOTAG_TEST_ENGINE"] ?? FileManager.default.currentDirectoryPath + "/dist/audiotag"
        guard FileManager.default.isExecutableFile(atPath: path) else { throw XCTSkip("请先运行构建脚本生成引擎") }
        let engine = Engine(executableURL: URL(fileURLWithPath: path))
        let request = try JSONSerialization.data(withJSONObject: ["operation": "parse", "text": "歌曲名称 (Title)：原生桥接验证\n音轨编号：1 / 2\n歌词：\n第一行\n\n第二行"])
        let response = try await engine.call(request)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: response) as? [String: Any])
        XCTAssertEqual(object["ok"] as? Bool, true)
        let result = try XCTUnwrap(object["result"] as? [String: Any])
        let metadata = try XCTUnwrap(result["metadata"] as? [String: String])
        XCTAssertEqual(metadata["title"], "原生桥接验证")
        XCTAssertEqual(metadata["track"], "1/2")
        XCTAssertEqual(metadata["lyrics"], "第一行\n\n第二行")
    }
    func testNativeBridgeReturnsStructuredFailure() async throws {
        let path = ProcessInfo.processInfo.environment["AUDIOTAG_TEST_ENGINE"] ?? ProcessInfo.processInfo.environment["AUDIOTAG_TEST_ENGINE"] ?? FileManager.default.currentDirectoryPath + "/dist/audiotag"
        guard FileManager.default.isExecutableFile(atPath: path) else { throw XCTSkip("请先构建引擎") }
        let engine = Engine(executableURL: URL(fileURLWithPath: path))
        let request = try JSONSerialization.data(withJSONObject: ["operation": "inspect", "input": "/nonexistent/audio.mp3"])
        let response = try await engine.call(request)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: response) as? [String: Any])
        XCTAssertEqual(object["ok"] as? Bool, false)
        XCTAssertNotNil(object["error"])
    }

    func testBridgeStopsInsteadOfHangingForever() async throws {
        let script = FileManager.default.temporaryDirectory.appendingPathComponent("audiotag-timeout-\(UUID().uuidString).sh")
        try "#!/bin/sh\nexec sleep 30\n".write(to: script, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: script.path)
        defer { try? FileManager.default.removeItem(at: script) }
        let engine = Engine(executableURL: script, timeout: 1)
        do {
            _ = try await engine.call(Data("{}".utf8))
            XCTFail("引擎无响应时应当报错而不是一直等待")
        } catch {
            XCTAssertTrue(error.localizedDescription.contains("没有响应"), error.localizedDescription)
        }
    }
}
