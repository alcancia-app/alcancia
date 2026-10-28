// swift-tools-version: 5.9
// Leer la copia cifrada de Alcancía con el selector de archivos del sistema y guardar la llave (ver movil/README.md).
import PackageDescription

let package = Package(
    name: "AlcanciaCarpeta",
    platforms: [.iOS(.v14)],
    products: [
        .library(name: "AlcanciaCarpeta", targets: ["CarpetaPlugin"])
    ],
    dependencies: [
        .package(url: "https://github.com/ionic-team/capacitor-swift-pm.git", from: "7.0.0")
    ],
    targets: [
        .target(
            name: "CarpetaPlugin",
            dependencies: [
                .product(name: "Capacitor", package: "capacitor-swift-pm"),
                .product(name: "Cordova", package: "capacitor-swift-pm")
            ],
            path: "ios/Sources/CarpetaPlugin")
    ]
)
