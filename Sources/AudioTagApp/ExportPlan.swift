import Foundation

/// 导出文件名的规划规则。
enum ExportPlan {
    /// 按输出模式给出目标文件名。
    static func fileName(for source: URL, convertingToMP3: Bool) -> String {
        let stem = source.deletingPathExtension().lastPathComponent
        return convertingToMP3 ? stem + ".mp3" : stem + ".tagged." + source.pathExtension
    }

    /// 为一批源文件规划目标路径，目标已存在或重名时抛出错误。
    static func targets(for sources: [URL], in folder: URL, convertingToMP3: Bool) throws -> [URL] {
        var targets: [URL] = []
        var seen = Set<String>()
        for source in sources {
            let name = fileName(for: source, convertingToMP3: convertingToMP3)
            let target = folder.appendingPathComponent(name)
            // 目标名按大小写不敏感比较，避免在默认文件系统上互相覆盖。
            let isDuplicate = !seen.insert(target.path.lowercased()).inserted
            guard !isDuplicate, !FileManager.default.fileExists(atPath: target.path) else {
                throw ExportPlanError("输出文件已存在或文件名重复：\(name)。请选择其他目录。")
            }
            targets.append(target)
        }
        return targets
    }
}

/// 导出规划失败时携带可读原因。
struct ExportPlanError: LocalizedError {
    let message: String
    init(_ message: String) { self.message = message }
    var errorDescription: String? { message }
}
