import AppKit
import UniformTypeIdentifiers
import WebKit

/// Ventana principal: la interfaz web (ui/) dentro de un WKWebView. La interfaz llama `host.enviar(accion, datos)`
/// y la app responde con `window.Alcancia.<funcion>(json)`. El contrato lo revisa pruebas/contrato.py.
@MainActor
final class Ventana: NSObject, NSWindowDelegate, WKScriptMessageHandler, WKNavigationDelegate {
    static let shared = Ventana()
    private var ventana: NSWindow?
    private var web: WKWebView?
    private var lista = false
    private var pendiente: [String: Any] = [:]
    private var relojImportar: Timer?

    func mostrar() {
        if ventana == nil { crear() }
        ventana?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func crear() {
        let control = WKUserContentController()
        control.add(self, name: "alcancia")
        control.addUserScript(WKUserScript(source: "window.ALCANCIA_HOST = 'mac';", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        let conf = WKWebViewConfiguration()
        conf.userContentController = control
        // La interfaz lee sus traducciones (ui/idiomas/*.json) con fetch desde los mismos archivos locales.
        conf.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")
        let w = WKWebView(frame: NSRect(x: 0, y: 0, width: 1180, height: 780), configuration: conf)
        w.navigationDelegate = self
        let v = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1180, height: 780),
                         styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView], backing: .buffered, defer: false)
        v.titlebarAppearsTransparent = true
        v.titleVisibility = .hidden
        v.title = "Alcancía"
        v.minSize = NSSize(width: 820, height: 560)
        let contenedor = NSView(frame: w.frame)
        w.frame = contenedor.bounds
        w.autoresizingMask = [.width, .height]
        contenedor.addSubview(w)
        // La web tapa la barra de título: esta franja de arriba es la que mueve la ventana (la interfaz deja ese espacio libre en Mac).
        let franja = FranjaArrastre(frame: NSRect(x: 0, y: contenedor.bounds.height - 30, width: contenedor.bounds.width, height: 30))
        franja.autoresizingMask = [.width, .minYMargin]
        contenedor.addSubview(franja)
        v.contentView = contenedor
        v.delegate = self
        v.isReleasedWhenClosed = false
        v.setFrameAutosaveName("Alcancia")
        if !v.setFrameUsingName("Alcancia") { v.center() }
        ventana = v
        web = w
        let ui = Rutas.recursos.appendingPathComponent("ui")
        w.loadFileURL(ui.appendingPathComponent("index.html"), allowingReadAccessTo: ui)
    }

    @objc func abrirAjustes() {
        mostrar()
        web?.evaluateJavaScript("window.Alcancia && window.Alcancia._probar(E => { E.ajustes = true })")
    }

    /// Al tocar un aviso de compromisos: la ventana adelante y la vista de Compromisos.
    func abrirCompromisos() {
        mostrar()
        web?.evaluateJavaScript("window.Alcancia && window.Alcancia._probar(E => { E.vista = 'compromisos' })")
    }

    @objc func abrirCarpetaDatos() {
        try? FileManager.default.createDirectory(at: Rutas.base, withIntermediateDirectories: true)
        NSWorkspace.shared.open(Rutas.base)
    }

    // MARK: Hacia la interfaz

    func llamar(_ funcion: String, _ datos: Any) {
        guard let web, let d = try? JSONSerialization.data(withJSONObject: datos), let json = String(data: d, encoding: .utf8) else { return }
        web.evaluateJavaScript("window.Alcancia && window.Alcancia.\(funcion)(\(json))")
    }

    /// El estado completo: lo que hay en ~/Alcancia (lo lee bin/estado.py) más lo propio de la app.
    func enviarEstado(aviso: String? = nil) {
        guard lista else { return }
        if let aviso { pendiente["aviso"] = aviso }
        Procesador.correrJSON("estado.py", []) { datos in
            var e = datos
            e.removeValue(forKey: "ok"); e.removeValue(forKey: "error")
            let hoy = DateFormatter()
            hoy.dateFormat = "yyyy-MM-dd"
            hoy.locale = Locale(identifier: "en_US_POSIX")
            e["hoy"] = hoy.string(from: Date())
            e["ias"] = IA.paraJS
            e["version"] = Actualizaciones.version
            e["carpeta"] = Rutas.base.path.replacingOccurrences(of: FileManager.default.homeDirectoryForCurrentUser.path, with: "~")
            e["actualizacion"] = Actualizaciones.disponible
            e["celular"] = Celular.paraJS
            if e["config"] == nil { e["config"] = Config.leer() }
            e.merge(Ventana.shared.pendiente) { _, nuevo in nuevo }
            Ventana.shared.pendiente = [:]
            Ventana.shared.llamar("estado", e)
            // «Alcancía en tu celular»: con el estado recién llegado, la interfaz arma y cifra la copia (si toca) y la devuelve.
            Celular.despuesDelEstado()
        }
    }

    /// Mientras se importa una cartola, el avance (bin/importar.py lo deja en ~/Alcancia/.alcancia/estado.json) llega cada medio segundo.
    private func seguirImportacion(_ activo: Bool) {
        relojImportar?.invalidate()
        relojImportar = nil
        guard activo else { return }
        relojImportar = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
            Task { @MainActor in
                let p = Archivos.leerJSON(Rutas.estadoImportar)
                if !p.isEmpty { Ventana.shared.llamar("importarProgreso", p) }
            }
        }
    }

    // MARK: Navegación: la ventana solo muestra la interfaz que viene dentro de la app

    /// Carpeta ui/ dentro de la app (sin enlaces simbólicos), para comparar rutas.
    private var carpetaUI: String { Rutas.recursos.appendingPathComponent("ui").resolvingSymlinksInPath().path + "/" }

    /// Un enlace o una redirección nunca carga una página de internet dentro de la ventana (esa página tendría el puente con la app):
    /// solo se permiten los archivos de ui/. Un enlace https que la persona toca se abre en su navegador.
    func webView(_ webView: WKWebView, decidePolicyFor accion: WKNavigationAction) async -> WKNavigationActionPolicy {
        guard let u = accion.request.url else { return .cancel }
        if u.isFileURL, u.resolvingSymlinksInPath().path.hasPrefix(carpetaUI) { return .allow }
        if u.scheme == "https", accion.navigationType == .linkActivated { NSWorkspace.shared.open(u) }
        return .cancel
    }

    // MARK: Desde la interfaz

    func userContentController(_ c: WKUserContentController, didReceive mensaje: WKScriptMessage) {
        // Solo la interfaz local (el marco principal, un archivo de ui/: la navegación de arriba no deja cargar otra cosa) puede
        // pedirle cosas a la app; una página de internet o un iframe, nunca.
        guard mensaje.frameInfo.isMainFrame, mensaje.frameInfo.securityOrigin.protocol == "file" else { return }
        guard let m = mensaje.body as? [String: Any], let accion = m["accion"] as? String else { return }
        let d = m["datos"] as? [String: Any] ?? [:]
        let ruta = d["ruta"] as? String ?? ""
        let archivoValido = !ruta.isEmpty && FileManager.default.isReadableFile(atPath: ruta)
        switch accion {
        case "listo":
            lista = true
            enviarEstado()
        case "config":
            Config.guardar(d)
            if d["idioma_ui"] != nil {
                // Los menús se rearman en el idioma nuevo y el estado se vuelve a mandar (las categorías base salen en ese idioma).
                Menu.instalar()
                enviarEstado()
            }
            // Primer uso: recién elegido el idioma, parte lo que esperaba (conexiones, carpeta vigilada, actualizaciones, MCP).
            if Idioma.elegido { AlcanciaApp.iniciarTareas() }
        case "probarIA":
            // La prueba la hace la pieza «ia» (bin/ia.py) con las mismas protecciones que todo pedido: sin herramientas, sin MCP,
            // sin la memoria de la persona y en una carpeta temporal. La IA va en el archivo de entrada, nunca como argumento.
            // Forma común de la familia (pieza «host-ui»): probarIA {ia} → iaProbada {ia, ok, codigo, plantilla, valores, ayuda, texto}.
            let id = d["ia"] as? String ?? ""
            guard IA.conocidas.contains(where: { $0.id == id }) else {
                return llamar("iaProbada", ["ia": String(id.prefix(30)), "ok": false, "codigo": "desconocida", "texto": Idioma.t("No conozco esa IA.")])
            }
            Procesador.conEntrada("ia.py", "probar", ["ia": id]) { r in
                let ok = r["ok"] as? Bool == true
                if ok { Config.guardar(["ia": id]) }
                var respuesta: [String: Any] = ["ia": id, "ok": ok, "texto": r["error"] as? String ?? "", "codigo": r["codigo"] as? String ?? ""]
                // La frase con sus marcadores: la interfaz la muestra en el idioma elegido.
                if let p = r["plantilla"] as? String { respuesta["plantilla"] = p }
                if let v = r["valores"] as? [String: Any] { respuesta["valores"] = v }
                if let a = r["ayuda"] as? String { respuesta["ayuda"] = a }
                Ventana.shared.llamar("iaProbada", respuesta)
            }
        case "elegirCartola":
            let panel = NSOpenPanel()
            panel.allowsMultipleSelection = false
            panel.canChooseDirectories = false
            panel.allowedContentTypes = [.commaSeparatedText, .tabSeparatedText, .plainText] + ["xlsx", "csv", "pdf", "ofx", "qfx", "qif", "xml"].compactMap { UTType(filenameExtension: $0) }
            panel.message = Idioma.t("Elige la cartola que descargaste de tu banco o billetera (CSV, Excel, PDF, OFX, QIF o CAMT.053)")
            guard let v = ventana else { return }
            panel.beginSheetModal(for: v) { r in
                guard r == .OK, let u = panel.url else { return }
                Ventana.shared.llamar("cartolaElegida", ["ruta": u.path, "nombre": u.lastPathComponent])
            }
        case "vistaCartola":
            guard archivoValido else { return llamar("vistaLista", ["ok": false, "error": Idioma.t("No pude leer el archivo.")]) }
            Procesador.correrJSON("importar.py", ["vista", ruta]) { Ventana.shared.llamar("vistaLista", $0) }
        case "aprenderReceta":
            guard archivoValido else { return llamar("recetaAprendida", ["ok": false, "error": Idioma.t("No pude leer el archivo.")]) }
            let pais = (d["pais"] as? String ?? "CL").filter(\.isLetter).prefix(2)
            Procesador.correrJSON("receta_ia.py", [ruta, String(pais).uppercased()]) { Ventana.shared.llamar("recetaAprendida", $0) }
        case "guardarReceta":
            Procesador.conEntrada("guardar.py", "receta", ["receta": d["receta"] ?? [:]]) { r in
                if r["ok"] as? Bool != true { Ventana.shared.enviarEstado(aviso: r["error"] as? String) }
            }
        case "importar":
            guard archivoValido else { return llamar("importado", ["ok": false, "error": Idioma.t("No pude leer el archivo.")]) }
            let receta = (d["receta"] as? String ?? "").filter { $0.isLetter || $0.isNumber || $0 == "-" }
            try? FileManager.default.removeItem(at: Rutas.estadoImportar)
            seguirImportacion(true)
            Procesador.correrJSON("importar.py", ["guardar", ruta, receta, (d["ia"] as? Bool ?? false) ? "1" : "0"]) { r in
                Ventana.shared.seguirImportacion(false)
                Ventana.shared.llamar("importado", r)
                Ventana.shared.enviarEstado()
            }
        case "categoria", "regla", "presupuesto", "categoriaNueva", "saldo":
            // La interfaz ya pintó el cambio; si no se pudo guardar, se recarga el estado real y se avisa.
            Procesador.conEntrada("guardar.py", accion, d) { r in
                if r["ok"] as? Bool != true { Ventana.shared.enviarEstado(aviso: r["error"] as? String) }
            }
        case "chat":
            // Conversar con Alcancía (bin/chat.py). Los mensajes van en un archivo de entrada, nunca como argumento (se verían en la
            // lista de procesos); chat.py los limpia (sin RUT ni números de cuenta) y valida lo que responde la IA.
            switch d["accion"] as? String ?? "" {
            case "enviar":
                let hoy = (d["hoy"] as? String ?? "").filter { $0.isNumber || $0 == "-" }
                let mensajes: [[String: Any]] = (d["mensajes"] as? [[String: Any]] ?? []).suffix(10).map { m in
                    ["rol": (m["rol"] as? String) == "persona" ? "persona" : "alcancia", "texto": String((m["texto"] as? String ?? "").prefix(1500))]
                }
                Procesador.conEntrada("chat.py", "enviar", ["hoy": hoy, "mensajes": mensajes]) { Ventana.shared.llamar("chatRespuesta", $0) }
            case "marcar":
                let id = (d["id"] as? String ?? "").filter { $0.isLetter || $0.isNumber || $0 == "-" }
                var datos: [String: Any] = ["id": id, "i": d["i"] as? Int ?? -1, "estado": (d["estado"] as? String) == "hecha" ? "hecha" : "no"]
                if let j = d["j"] as? Int { datos["j"] = j }
                Procesador.conEntrada("chat.py", "marcar", datos) { _ in }
            case "borrar":
                Procesador.conEntrada("chat.py", "borrar", [:]) { _ in }
            default:
                break
            }
        case "compromiso":
            Procesador.conEntrada("guardar.py", "compromiso", d) { r in
                guard r["ok"] as? Bool == true else { return Ventana.shared.enviarEstado(aviso: r["error"] as? String) }
                // Primer compromiso: recién ahí se activan los avisos y se pide el permiso del sistema (si la persona no los apagó antes).
                if r["primero"] as? Bool == true, Config.leer()["avisos"] == nil { Avisos.activar(true) }
                Ventana.shared.enviarEstado()
                Avisos.revisar()
            }
        case "avisos":
            Avisos.activar(d["activo"] as? Bool ?? false)
        case "celular":
            // «Alcancía en tu celular» (Celular.swift). Elegir la carpeta de la nube es una hoja de esta ventana.
            if d["accion"] as? String == "carpeta" {
                let panel = Celular.panelCarpeta()
                guard let v = ventana else { return }
                panel.beginSheetModal(for: v) { r in
                    Celular.carpetaElegida(r == .OK ? panel.url : nil)
                }
            } else {
                Celular.atender(d)
            }
        case "pedirConsejos":
            let hoy = (d["hoy"] as? String ?? "").filter { $0.isNumber || $0 == "-" }
            Procesador.correrJSON("consejos.py", [hoy]) { Ventana.shared.llamar("consejosListos", $0) }
        case "abrirEnlace":
            if let u = URL(string: d["url"] as? String ?? ""), u.scheme == "https" { NSWorkspace.shared.open(u) }
        case "abrirCarpeta":
            abrirCarpetaDatos()
        case "conectar":
            let id = Conexiones.valido(d["conector"] as? String ?? "")
            Conexiones.conectar(id, campos: d["campos"] as? [String: Any] ?? [:]) { r in
                var x = r
                x["conector"] = id
                Ventana.shared.llamar("conectado", x)
                Ventana.shared.enviarEstado()
            }
        case "sincronizar":
            Conexiones.traer(Conexiones.valido(d["conector"] as? String ?? ""), manual: true)
        case "desconectar":
            Conexiones.desconectar(Conexiones.valido(d["conector"] as? String ?? ""))
        case "vigilar":
            Vigilante.activar(d["activo"] as? Bool ?? false)
        case "mcpConectar":
            let cliente = Conexiones.valido(d["cliente"] as? String ?? "")
            let quitar = d["quitar"] as? Bool ?? false
            Procesador.correrJSON("mcp_conectar.py", [quitar ? "quitar" : "conectar", cliente]) { r in
                var x = r
                x["cliente"] = cliente
                x["quitar"] = quitar
                Ventana.shared.llamar("mcpListo", x)
            }
        case "buscarActualizacion":
            Actualizaciones.revisar { hay, detalle in
                // `notas` es la forma de la pieza «componentes» (la fila de actualización); `detalle` queda por compatibilidad.
                Ventana.shared.llamar("actualizacionRevisada", ["hay": hay, "detalle": detalle, "notas": hay ? detalle : "", "sinConexion": detalle == Actualizaciones.sinConexion])
            }
        case "actualizar":
            // Nunca en medio de una importación: cerrar la app la cortaría.
            guard relojImportar == nil else {
                llamar("actualizacionProgreso", ["paso": "error", "texto": Idioma.t("Espera a que termine de importar y vuelve a intentarlo.")])
                return
            }
            Actualizaciones.seguir { Ventana.shared.llamar("actualizacionProgreso", $0) }
            Actualizaciones.instalar { ok, error in
                if !ok { Ventana.shared.llamar("actualizacionProgreso", ["paso": "error", "texto": error]) }
            }
        default:
            break
        }
    }
}

/// Franja invisible arriba de la ventana: arrastrar la mueve y el doble clic la agranda, como una barra de título normal.
/// (WKWebView no entiende `-webkit-app-region`.)
final class FranjaArrastre: NSView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func mouseDown(with e: NSEvent) {
        if e.clickCount == 2 { window?.performZoom(nil) } else { window?.performDrag(with: e) }
    }
}
