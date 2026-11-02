// swift-tools-version:5.10
import PackageDescription

// Alcancía para Mac: la app nativa genérica de Pieza (host-mac) con la interfaz de ui/ y los scripts de bin/ (Python portátil adentro).
let package = Package(
    name: "Alcancia",
    platforms: [.macOS("15.0")],
    targets: [
        .executableTarget(name: "Alcancia", dependencies: ["PiezaHost", "PiezaActualizaciones"], path: "Sources/Alcancia"),
        // Pieza «host-mac» (de Pieza: no se edita a mano): la ventana, el puente con sus guardas, config e idioma desde app.json,
        // menús, apariencia, secretos, avisos, vigilante y las acciones declaradas en acciones.json. Lo propio de Alcancía se
        // registra en AlcanciaApp.swift.
        .target(name: "PiezaHost", path: "Sources/PiezaHost"),
        // Pieza «actualizaciones» (de Pieza: no se edita a mano). Alcancía la configura con su repo y su nombre.
        .target(name: "PiezaActualizaciones", path: "Sources/PiezaActualizaciones"),
    ]
)
