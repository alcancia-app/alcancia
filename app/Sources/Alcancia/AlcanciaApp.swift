import AppKit

/// Alcancía para Mac: una ventana con la interfaz web de ui/ y un puente a los scripts de bin/ (Python portátil dentro de la app).
/// Los datos de la persona viven en ~/Alcancia, fuera de la app: actualizar nunca borra nada.
@main
@MainActor
final class AlcanciaApp: NSObject, NSApplicationDelegate {
    static func main() {
        let app = NSApplication.shared
        let delegado = AlcanciaApp()
        app.delegate = delegado
        app.setActivationPolicy(.regular)
        app.run()
    }

    private static var tareasIniciadas = false

    func applicationDidFinishLaunching(_ aviso: Notification) {
        Menu.instalar()
        Ventana.shared.mostrar()
        // En el primer uso lo primero es elegir el idioma: lo que puede mostrar algo o pedir un permiso del sistema
        // (Llavero, carpeta de Descargas, archivos de otras apps) espera a que esté elegido. Ventana lo llama al guardarse idioma_ui.
        if Idioma.elegido { AlcanciaApp.iniciarTareas() }
    }

    /// Lo que corre solo: actualizaciones, conexiones, carpeta vigilada y reparar las IA conectadas por MCP. Una sola vez.
    static func iniciarTareas() {
        guard !tareasIniciadas else { return }
        tareasIniciadas = true
        Actualizaciones.revisarCadaRato()
        Conexiones.revisarCadaRato()
        Vigilante.empezar()
        // Si la app cambió de lugar (o se actualizó), las IA conectadas por MCP siguen apuntando a la ruta nueva.
        Procesador.correrJSON("mcp_conectar.py", ["reparar"]) { _ in }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        Ventana.shared.mostrar()
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
}

/// Barra de menú mínima: la app (Acerca de, Ocultar, Salir), Edición (para copiar y pegar dentro de la interfaz) y Ventana.
@MainActor
enum Menu {
    static func instalar() {
        let principal = NSMenu()
        let app = NSMenuItem()
        let menuApp = NSMenu()
        menuApp.addItem(withTitle: Idioma.t("Acerca de Alcancía"), action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        menuApp.addItem(.separator())
        let ajustes = NSMenuItem(title: Idioma.t("Ajustes…"), action: #selector(Ventana.abrirAjustes), keyEquivalent: ",")
        ajustes.target = Ventana.shared
        menuApp.addItem(ajustes)
        let carpeta = NSMenuItem(title: Idioma.t("Abrir la carpeta de tus datos"), action: #selector(Ventana.abrirCarpetaDatos), keyEquivalent: "")
        carpeta.target = Ventana.shared
        menuApp.addItem(carpeta)
        menuApp.addItem(.separator())
        menuApp.addItem(withTitle: Idioma.t("Ocultar Alcancía"), action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        menuApp.addItem(withTitle: Idioma.t("Salir de Alcancía"), action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        app.submenu = menuApp
        principal.addItem(app)

        let edicion = NSMenuItem()
        let menuEdicion = NSMenu(title: Idioma.t("Edición"))
        menuEdicion.addItem(withTitle: Idioma.t("Deshacer"), action: Selector(("undo:")), keyEquivalent: "z")
        menuEdicion.addItem(withTitle: Idioma.t("Rehacer"), action: Selector(("redo:")), keyEquivalent: "Z")
        menuEdicion.addItem(.separator())
        menuEdicion.addItem(withTitle: Idioma.t("Cortar"), action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        menuEdicion.addItem(withTitle: Idioma.t("Copiar"), action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        menuEdicion.addItem(withTitle: Idioma.t("Pegar"), action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        menuEdicion.addItem(withTitle: Idioma.t("Seleccionar todo"), action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        edicion.submenu = menuEdicion
        principal.addItem(edicion)

        let ventana = NSMenuItem()
        let menuVentana = NSMenu(title: Idioma.t("Ventana"))
        menuVentana.addItem(withTitle: Idioma.t("Minimizar"), action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        menuVentana.addItem(withTitle: Idioma.t("Cerrar"), action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        ventana.submenu = menuVentana
        principal.addItem(ventana)
        NSApp.windowsMenu = menuVentana
        NSApp.mainMenu = principal
    }
}
