import Foundation
import XCTest
@testable import Mp3tagBridge

final class EngineTests: XCTestCase {
    func testNativeBridgeUsesRealJSONEngine() async throws {
        let path = ProcessInfo.processInfo.environment["MP3TAG_TEST_ENGINE"] ?? FileManager.default.currentDirectoryPath + "/dist/mp3tag"
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
        let path = ProcessInfo.processInfo.environment["MP3TAG_TEST_ENGINE"] ?? FileManager.default.currentDirectoryPath + "/dist/mp3tag"
        guard FileManager.default.isExecutableFile(atPath: path) else { throw XCTSkip("请先构建引擎") }
        let engine = Engine(executableURL: URL(fileURLWithPath: path))
        let request = try JSONSerialization.data(withJSONObject: ["operation": "inspect", "input": "/nonexistent/audio.mp3"])
        let response = try await engine.call(request)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: response) as? [String: Any])
        XCTAssertEqual(object["ok"] as? Bool, false)
        XCTAssertNotNil(object["error"])
    }
}
