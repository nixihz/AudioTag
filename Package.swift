// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AudioTagNative",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "AudioTag", targets: ["Mp3tagApp"]), .library(name: "Mp3tagBridge", targets: ["Mp3tagBridge"])],
    dependencies: [
        .package(url: "https://github.com/sparkle-project/Sparkle", exact: "2.10.0")
    ],
    targets: [
        .target(name: "Mp3tagBridge"),
        .executableTarget(name: "Mp3tagApp", dependencies: [
            "Mp3tagBridge", .product(name: "Sparkle", package: "Sparkle")
        ], linkerSettings: [.unsafeFlags(["-Xlinker", "-rpath", "-Xlinker", "@executable_path/../Frameworks"])]),
        .testTarget(name: "Mp3tagBridgeTests", dependencies: ["Mp3tagBridge"]),
        .testTarget(name: "Mp3tagAppTests", dependencies: ["Mp3tagApp"])
    ]
)
