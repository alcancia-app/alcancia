// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "Alcancia",
    platforms: [.macOS("15.0")],
    targets: [
        .executableTarget(name: "Alcancia", path: "Sources/Alcancia"),
    ]
)
