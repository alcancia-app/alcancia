import AppKit
import PiezaActualizaciones
import PiezaHost

/// Alcancía para Mac, sobre la pieza «host-mac» (target `PiezaHost`): la ventana con la interfaz de ui/, el puente con sus guardas
/// (solo el marco principal con un archivo de ui/; la ventana nunca sale de ui/ y un enlace https va al navegador), config e
/// idioma desde app.json, menús en el idioma elegido, apariencia que sigue config.tema, scripts de bin/ con límite de tiempo y las
/// acciones declaradas en acciones.json (probarIA, guardarReceta, categoria, categoriaNueva, regla, presupuesto, saldo, chat,
/// pedirConsejos, mcpConectar: solo corren un script, con sus datos validados). Los datos de la persona viven en ~/Alcancia,
/// fuera de la app (app.json → datos): actualizar nunca borra nada.
///
/// Aquí queda lo propio de Alcancía: las cartolas (elegir, leer, aprender la receta, importar con su avance), los compromisos y
/// sus avisos (Avisos.swift), las conexiones con la llave en el Llavero y la carpeta vigilada en Descargas (Conexiones.swift), la
/// copia para el celular (Celular.swift) y los ajustes con forma propia (`inicio_mes`, `uf`).
@main
enum AlcanciaApp {
    @MainActor static func main() {
        // La ventana de antes guardaba su tamaño como «Alcancia»; el host la guarda con el nombre de la app («Alcancía»).
        let d = UserDefaults.standard
        if d.string(forKey: "NSWindow Frame Alcancía") == nil, let antes = d.string(forKey: "NSWindow Frame Alcancia") {
            d.set(antes, forKey: "NSWindow Frame Alcancía")
        }
        Host.arrancar(.init(ancho: 1180, alto: 780, minAncho: 820, minAlto: 560, sitio: "https://alcancia-app.github.io/alcancia/",
                            codigo: "https://github.com/alcancia-app/alcancia", avisos: true, global: "Alcancia")) { p in
            p.estado = { base, listo in
                var e = base
                e["celular"] = Celular.paraJS
                if let a = Estado.aviso { e["aviso"] = a }
                Estado.aviso = nil
                listo(e)
                // «Alcancía en tu celular»: con el estado recién llegado, la interfaz arma y cifra la copia (si toca) y la devuelve.
                Celular.despuesDelEstado()
            }
            p.menus = { m in
                [m.archivo([m.nativo("Abrir la carpeta de tus datos") { abrirCarpetaDatos() }]), m.edicion()]
            }
            // Lo que corre solo y puede mostrar algo o pedir un permiso del sistema (Llavero, Descargas, archivos de otras IA) espera
            // al idioma elegido: el host llama `tareas` una vez, recién entonces. Las actualizaciones las revisa el host.
            p.tareas = {
                Conexiones.revisarCadaRato()
                Descargas.empezar()
                Avisos.revisarCadaRato()
                Celular.revisarCadaRato()
                // Si la app cambió de lugar (o se actualizó), las IA conectadas por MCP siguen apuntando a la ruta nueva.
                Procesador.correrJSON("mcp_conectar.py", ["reparar"], limite: 120) { _ in }
            }
            // Tocar un aviso de compromisos: la ventana adelante (el host) y la vista de Pagos.
            Notificaciones.alTocar = { _ in p.llamar("menu", ["accion": "compromisos"]) }

            // Pieza «actualizaciones»: solo los Releases de este repo (Alcancia-macOS.zip + .sha256). Instalación de desarrollo:
            // build.sh deja la ruta del checkout en ~/Alcancia/.alcancia/desarrollo y empaquetar.sh escribe su avance en ALCANCIA_PROGRESO.
            Actualizaciones.configurar(.init(repo: "alcancia-app/alcancia", nombre: "Alcancía",
                archivoDesarrollo: Host.datos.appendingPathComponent("desarrollo"), variableProgreso: Host.prefijo + "PROGRESO"))
            p.actualizaciones = .init(revisar: Actualizaciones.revisar, revisarCadaRato: Actualizaciones.revisarCadaRato,
                seguir: Actualizaciones.seguir, instalar: Actualizaciones.instalar, aviso: Actualizaciones.aviso,
                disponible: { Actualizaciones.disponible })

            p.registrar("config") { d in guardarConfig(d) }
            p.registrar("abrirCarpeta") { _ in abrirCarpetaDatos() }
            Cartolas.registrar(p)
            p.registrar("compromiso") { d in
                Procesador.conEntrada("guardar.py", "compromiso", d, limite: 60) { r in
                    guard r["ok"] as? Bool == true else { return Estado.enviar(aviso: r["error"] as? String) }
                    // Primer compromiso: recién ahí se activan los avisos y se pide el permiso (si la persona no los apagó antes).
                    if r["primero"] as? Bool == true, Config.leer()["avisos"] == nil { Avisos.activar(true) }
                    Estado.enviar()
                    Avisos.revisar()
                }
            }
            p.registrar("avisos") { d in Avisos.activar(Texto.esBool(d["activo"]) && d["activo"] as? Bool == true) }
            p.registrar("conectar") { d in
                let id = Conexiones.valido(d["conector"] as? String ?? "")
                Conexiones.conectar(id, campos: d["campos"] as? [String: Any] ?? [:]) { r in
                    var x = r
                    x["conector"] = id
                    p.llamar("conectado", x)
                    Estado.enviar()
                }
            }
            p.registrar("sincronizar") { d in Conexiones.traer(Conexiones.valido(d["conector"] as? String ?? ""), manual: true) }
            p.registrar("desconectar") { d in Conexiones.desconectar(Conexiones.valido(d["conector"] as? String ?? "")) }
            p.registrar("vigilar") { d in Descargas.activar(Texto.esBool(d["activo"]) && d["activo"] as? Bool == true) }
            p.registrar("celular") { d in Celular.atender(d) }

            // La ventana de siempre: sin barra de título visible (la interfaz deja libre la franja de arriba en Mac). Se ajusta
            // apenas el host la crea (justo después de este bloque).
            DispatchQueue.main.async { estiloVentana(p) }
        }
    }

    // MARK: Ajustes

    /// `config` del host más los ajustes con forma propia de Alcancía, que app.json no puede describir (son objetos):
    /// «Tu mes empieza» y «Valor de la UF hoy». Python los vuelve a validar al usarlos (datos.CONFIG_OBJETOS).
    @MainActor static func guardarConfig(_ d: [String: Any]) {
        let p = Puente.shared
        let antes = Config.leer()
        var objetos: [String: Any] = [:]
        // «Tu mes empieza»: {"modo": "dia" | "sueldo", "dia": 1…31}. Nada más entra en esa clave.
        if let im = d["inicio_mes"] as? [String: Any], let modo = im["modo"] as? String, modo == "dia" || modo == "sueldo",
           let dia = Texto.entero(im["dia"]), (1...31).contains(dia) {
            objetos["inicio_mes"] = ["modo": modo, "dia": dia]
        }
        // «Valor de la UF hoy»: {"valor": número, "fecha": "AAAA-MM-DD", "variacion_mensual": 0…20}. Sin valor, se borra el valor.
        if let u = d["uf"] as? [String: Any] {
            var limpio: [String: Any] = [:]
            if let valor = (u["valor"] as? NSNumber), !Texto.esBool(valor), valor.doubleValue > 0, valor.doubleValue < 10_000_000,
               let fecha = u["fecha"] as? String, Texto.calza(fecha, "\\d{4}-\\d{2}-\\d{2}") {
                limpio["valor"] = valor.doubleValue
                limpio["fecha"] = fecha
            }
            if let v = (u["variacion_mensual"] as? NSNumber), !Texto.esBool(v), v.doubleValue >= 0, v.doubleValue <= 20 {
                limpio["variacion_mensual"] = v.doubleValue
            }
            objetos["uf"] = limpio
        }
        if !objetos.isEmpty {
            var todo = Archivos.leerJSON(Config.ruta, maximo: 1024 * 1024)
            for (k, v) in objetos { todo[k] = v }
            Archivos.escribirJSON(Config.ruta, todo)
        }
        // Las claves simples, con las reglas de app.json (lo mismo que hace el host con `config`).
        let ahora = Config.guardar(d)
        if (antes["idioma_ui"] as? String) != (ahora["idioma_ui"] as? String) {
            // Los menús se rearman en el idioma nuevo y el estado se vuelve a mandar (las categorías base salen en ese idioma).
            Idioma.olvidar()
            p.instalarMenus()
            Avisos.idiomaCambio()
            Estado.enviar()
        }
        if (antes["tema"] as? String) != (ahora["tema"] as? String) { p.aplicarApariencia() }
        // Primer uso: recién elegido el idioma, parte lo que esperaba (conexiones, carpeta vigilada, actualizaciones, MCP).
        if Idioma.elegido { p.iniciarTareas() }
    }

    // MARK: Ventana y carpeta

    @MainActor static func abrirCarpetaDatos() {
        let base = Host.datos.deletingLastPathComponent()   // ~/Alcancia (la de la app es ~/Alcancia/.alcancia)
        try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        NSWorkspace.shared.open(base)
    }

    @MainActor static func estiloVentana(_ p: Puente) {
        guard let v = p.ventana, let w = p.web else { return }
        v.styleMask.insert(.fullSizeContentView)
        v.titlebarAppearsTransparent = true
        v.titleVisibility = .hidden
        // La web tapa la barra de título: esta franja de arriba es la que mueve la ventana.
        let franja = FranjaArrastre(frame: NSRect(x: 0, y: w.bounds.height - 30, width: w.bounds.width, height: 30))
        franja.autoresizingMask = [.width, .minYMargin]
        w.addSubview(franja)
    }
}

/// El estado con un aviso (algo que no se pudo guardar): lo muestra la interfaz al recibirlo.
@MainActor
enum Estado {
    static var aviso: String?

    static func enviar(aviso: String? = nil) {
        if let aviso { self.aviso = aviso }
        Puente.shared.enviarEstado()
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
