import Darwin
import Foundation

/// 标签引擎返回的错误信息。
public struct EngineError: LocalizedError, Sendable {
    public let message: String
    public var errorDescription: String? { message }
    public init(_ message: String) { self.message = message }
}

/// 与内置 Python 标签引擎之间的进程通道。
public struct Engine: Sendable {
    /// 等待引擎响应的时间上限，超时后终止进程，避免界面一直卡住。
    public static let defaultTimeout: TimeInterval = 1800

    /// 终止进程后等待其真正退出的时间。
    private static let terminationGrace: TimeInterval = 5

    public let executableURL: URL
    private let timeout: TimeInterval

    public init(executableURL: URL, timeout: TimeInterval = Engine.defaultTimeout) {
        self.executableURL = executableURL
        self.timeout = timeout
    }

    /// 定位应用包内的标签引擎。
    public static func bundled() throws -> Engine {
        guard let resources = Bundle.main.resourceURL else { throw EngineError("无法找到应用资源") }
        let url = resources.appendingPathComponent("audiotag")
        guard FileManager.default.isExecutableFile(atPath: url.path) else { throw EngineError("标签引擎缺失，请重新运行构建脚本") }
        return Engine(executableURL: url)
    }

    /// 发送一条 JSON 请求，返回引擎的 JSON 响应。
    public func call(_ request: Data) async throws -> Data {
        try await withCheckedThrowingContinuation { continuation in
            Self.queue.async {
                do {
                    let response = try Self.run(executableURL: executableURL, request: request, timeout: timeout)
                    continuation.resume(returning: response)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    /// 引擎调用在独立队列上执行，不占用主线程。
    private static let queue = DispatchQueue(label: "com.brian.audiotag.engine", qos: .userInitiated)

    private static func run(executableURL: URL, request: Data, timeout: TimeInterval) throws -> Data {
        let workspace = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: workspace, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: workspace) }

        let inputURL = workspace.appendingPathComponent("request.json")
        let outputURL = workspace.appendingPathComponent("response.json")
        let errorURL = workspace.appendingPathComponent("stderr.txt")
        try request.write(to: inputURL)
        FileManager.default.createFile(atPath: outputURL.path, contents: nil)
        FileManager.default.createFile(atPath: errorURL.path, contents: nil)

        let input = try FileHandle(forReadingFrom: inputURL)
        let output = try FileHandle(forWritingTo: outputURL)
        let errors = try FileHandle(forWritingTo: errorURL)
        defer { try? input.close(); try? output.close(); try? errors.close() }

        let process = Process()
        process.executableURL = executableURL
        process.arguments = ["request"]
        process.standardInput = input
        // 用文件承接较大的封面响应，避免管道缓冲区填满导致进程互相等待。
        process.standardOutput = output
        process.standardError = errors

        let finished = DispatchGroup()
        finished.enter()
        process.terminationHandler = { _ in finished.leave() }
        try process.run()
        if finished.wait(timeout: .now() + timeout) == .timedOut {
            stop(process, finished)
            throw EngineError("标签引擎长时间没有响应，操作已停止")
        }

        let response = try Data(contentsOf: outputURL)
        guard !response.isEmpty else {
            let details = String(data: try Data(contentsOf: errorURL), encoding: .utf8) ?? ""
            throw EngineError("标签引擎未返回结果：\(details.prefix(1000))")
        }
        return response
    }

    /// 先请求进程退出，宽限期后仍未退出则强制结束。
    private static func stop(_ process: Process, _ finished: DispatchGroup) {
        process.terminate()
        if finished.wait(timeout: .now() + terminationGrace) == .timedOut, process.isRunning {
            kill(process.processIdentifier, SIGKILL)
        }
    }
}
