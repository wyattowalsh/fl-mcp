// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "FLMCPHelper",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "FLMCPHelper", targets: ["FLMCPHelper"])
    ],
    targets: [
        .executableTarget(
            name: "FLMCPHelper",
            path: "Sources/FLMCPHelper"
        )
    ]
)
