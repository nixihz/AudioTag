import XCTest
@testable import AudioTagApp

final class EngineReplyTests: XCTestCase {
    func testDecodesSnakeCaseStreamKeys() throws {
        let json = """
        {"ok": true, "result": {"metadata": {"title": "标题"}, "duration": 12.5,
         "audio_streams": [{"index": 1, "codec": "aac", "channels": 2}],
         "video_streams": [{"index": 0, "width": 64, "height": 32}]}}
        """
        let reply = try JSONDecoder().decode(EngineReply.self, from: Data(json.utf8))
        XCTAssertTrue(reply.ok)
        XCTAssertNil(reply.error)
        XCTAssertEqual(reply.result?.metadata?["title"], "标题")
        XCTAssertEqual(reply.result?.duration, 12.5)
        XCTAssertEqual(reply.result?.audioStreams?.first?.index, 1)
        XCTAssertEqual(reply.result?.audioStreams?.first?.codec, "aac")
        XCTAssertEqual(reply.result?.videoStreams?.first?.width, 64)
        XCTAssertEqual(reply.result?.videoStreams?.first?.height, 32)
    }

    func testDecodesStructuredFailure() throws {
        let json = #"{"ok": false, "error": {"code": "operation_failed", "message": "出错了"}}"#
        let reply = try JSONDecoder().decode(EngineReply.self, from: Data(json.utf8))
        XCTAssertFalse(reply.ok)
        XCTAssertNil(reply.result)
        XCTAssertEqual(reply.error?.message, "出错了")
    }

    func testDecodesEmptyResult() throws {
        let json = #"{"ok": true, "result": {}}"#
        let reply = try JSONDecoder().decode(EngineReply.self, from: Data(json.utf8))
        XCTAssertTrue(reply.ok)
        XCTAssertNil(reply.result?.metadata)
        XCTAssertNil(reply.result?.audioStreams)
    }
}
