import Foundation

public struct EngineError: LocalizedError, Sendable {
    public let message: String
    public var errorDescription: String? { message }
    public init(_ message: String) { self.message = message }
}

public struct Engine: Sendable {
    public let executableURL: URL
    public init(executableURL: URL) { self.executableURL = executableURL }

    public static func bundled() throws -> Engine {
        guard let resources = Bundle.main.resourceURL else { throw EngineError("无法找到应用资源") }
        let url = resources.appendingPathComponent("audiotag")
        guard FileManager.default.isExecutableFile(atPath: url.path) else { throw EngineError("标签引擎缺失，请重新运行构建脚本") }
        return Engine(executableURL: url)
    }

    public func call(_ request: Data) async throws -> Data {
        let executable = executableURL
        return try await Task.detached {
            let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            defer { try? FileManager.default.removeItem(at: directory) }
            let inputURL = directory.appendingPathComponent("request.json")
            let outputURL = directory.appendingPathComponent("response.json")
            let errorURL = directory.appendingPathComponent("stderr.txt")
            try request.write(to: inputURL)
            FileManager.default.createFile(atPath: outputURL.path, contents: nil)
            FileManager.default.createFile(atPath: errorURL.path, contents: nil)
            let input = try FileHandle(forReadingFrom: inputURL)
            let output = try FileHandle(forWritingTo: outputURL)
            let errors = try FileHandle(forWritingTo: errorURL)
            defer { try? input.close(); try? output.close(); try? errors.close() }
            let process = Process()
            process.executableURL = executable
            process.arguments = ["request"]
            process.standardInput = input
            // 用文件承接较大的封面响应，避免管道缓冲区填满导致进程互相等待。
            process.standardOutput = output
            process.standardError = errors
            try process.run()
            process.waitUntilExit()
            let response = try Data(contentsOf: outputURL)
            guard !response.isEmpty else {
                let details = String(data: try Data(contentsOf: errorURL), encoding: .utf8) ?? ""
                throw EngineError("标签引擎未返回结果：\(details.prefix(1000))")
            }
            return response
        }.value
    }
}
