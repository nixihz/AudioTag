// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AudioTagNative",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "AudioTag", targets: ["AudioTagApp"]), .library(name: "AudioTagBridge", targets: ["AudioTagBridge"])],
    dependencies: [
        .package(url: "https://github.com/sparkle-project/Sparkle", exact: "2.10.0")
    ],
    targets: [
        .target(name: "AudioTagBridge"),
        .executableTarget(name: "AudioTagApp", dependencies: [
            "AudioTagBridge", .product(name: "Sparkle", package: "Sparkle")
        ], linkerSettings: [.unsafeFlags(["-Xlinker", "-rpath", "-Xlinker", "@executable_path/../Frameworks"])]),
        .testTarget(name: "AudioTagBridgeTests", dependencies: ["AudioTagBridge"]),
        .testTarget(name: "AudioTagAppTests", dependencies: ["AudioTagApp"])
    ]
)
