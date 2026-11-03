import Foundation

/// 标签引擎的 JSON 响应。
struct EngineReply: Decodable {
    var ok: Bool
    var result: EngineResult?
    var error: EngineFailure?

    /// 引擎返回的失败原因。
    struct EngineFailure: Decodable {
        var message: String
    }
}

/// 一次操作的结果，字段与引擎的 JSON 输出一一对应。
struct EngineResult: Decodable {
    var metadata: [String: String]?
    var warnings: [String]?
    var cover: String?
    var output: String?
    var duration: Double?
    var audioStreams: [AudioStream]?
    var videoStreams: [VideoStream]?

    /// 音频流信息。
    struct AudioStream: Decodable, Identifiable {
        var index: Int
        var codec: String
        var channels: Int
        var id: Int { index }
    }

    /// 视频流信息。
    struct VideoStream: Decodable {
        var index: Int
        var width: Int
        var height: Int
    }

    enum CodingKeys: String, CodingKey {
        case metadata, warnings, cover, output, duration
        case audioStreams = "audio_streams"
        case videoStreams = "video_streams"
    }
}
