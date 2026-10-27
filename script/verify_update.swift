import CryptoKit
import Foundation

guard CommandLine.arguments.count == 4,
      let signature = Data(base64Encoded: CommandLine.arguments[2]),
      let publicBytes = Data(base64Encoded: CommandLine.arguments[3]) else {
    fputs("用法：swift script/verify_update.swift 安装包 签名 公钥\n", stderr)
    exit(2)
}
do {
    let publicKey = try Curve25519.Signing.PublicKey(rawRepresentation: publicBytes)
    let archive = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]), options: .mappedIfSafe)
    guard publicKey.isValidSignature(signature, for: archive) else {
        fputs("更新包 Ed25519 签名无效\n", stderr)
        exit(1)
    }
    print("更新包 Ed25519 签名有效")
} catch {
    fputs("更新签名验证失败：\(error.localizedDescription)\n", stderr)
    exit(1)
}
