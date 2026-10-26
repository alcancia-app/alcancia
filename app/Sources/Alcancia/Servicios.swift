import AppKit

// MARK: - Rutas y configuración (compartidas con bin/datos.py)

enum Rutas {
    /// Datos de la persona: fuera de la app, así actualizar no borra nada.
    static var base: URL { FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Alcancia") }
    static var interno: URL { base.appendingPathComponent(".alcancia") }
    static var config: URL { interno.appendingPathComponent("config.json") }
    static var estadoImportar: URL { interno.appendingPathComponent("estado.json") }
    /// Código (bin/, ui/, recetas/): dentro de Alcancia.app.
    static var recursos: URL { Bundle.main.resourceURL!.appendingPathComponent("alcancia") }
    static var python: URL { Bundle.main.resourceURL!.appendingPathComponent("python/bin/python3") }
}

enum Archivos {
    static func leerJSON(_ url: URL) -> [String: Any] {
        guard let d = try? Data(contentsOf: url), let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return [:] }
        return j
    }

    static func escribirJSON(_ url: URL, _ valor: Any) {
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let d = try? JSONSerialization.data(withJSONObject: valor, options: [.prettyPrinted, .sortedKeys]) { try? d.write(to: url, options: .atomic) }
    }
}

enum Config {
    static func leer() -> [String: Any] { Archivos.leerJSON(Rutas.config) }

    /// Solo se aceptan claves conocidas con valores simples (lo que manda la interfaz no puede escribir cualquier cosa).
    static let permitidas: Set<String> = ["ia", "idioma_ui", "pais", "moneda", "respaldo", "bienvenida", "vigilar", "ia_en_conexiones"]

    static func guardar(_ cambios: [String: Any]) {
        var d = leer()
        for (k, v) in cambios where permitidas.contains(k) && (v is String || v is Bool) { d[k] = v }
        Archivos.escribirJSON(Rutas.config, d)
    }

    static func texto(_ clave: String) -> String { (leer()[clave] as? String) ?? "" }
}

// MARK: - Idioma (las claves son el texto en español, igual que en ui/idiomas)

enum Idioma {
    nonisolated(unsafe) private static var cache: (codigo: String, textos: [String: String])?

    static var codigo: String {
        let elegido = Config.texto("idioma_ui")
        if !elegido.isEmpty { return elegido }
        return Locale.preferredLanguages.first?.hasPrefix("es") == true ? "es" : "en"
    }

    static func t(_ texto: String) -> String {
        let c = codigo
        guard c != "es" else { return texto }
        if cache?.codigo != c {
            let j = Archivos.leerJSON(Rutas.recursos.appendingPathComponent("ui/idiomas/\(c).json"))
            cache = (c, j["textos"] as? [String: String] ?? [:])
        }
        return cache?.textos[texto] ?? texto
    }
}

// MARK: - IA de la persona (se detecta y se prueba, no se configura a mano)

@MainActor
enum IA {
    static let conocidas: [(id: String, nombre: String, comandos: [String])] = [
        ("claude", "Claude", ["claude"]),
        ("codex", "ChatGPT (Codex)", ["codex"]),
        ("gemini", "Gemini", ["agy", "gemini"]),
    ]

    /// La app no hereda el PATH de la terminal: se buscan los CLI donde suelen quedar.
    static func dirs() -> [String] {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        var d = ["/opt/homebrew/bin", "/usr/local/bin", "\(home)/.local/bin", "\(home)/.claude/local", "\(home)/.codex/bin",
                 "\(home)/.npm-global/bin", "\(home)/.volta/bin", "\(home)/.bun/bin", "/usr/bin"]
        let nvm = "\(home)/.nvm/versions/node"
        let versiones = ((try? FileManager.default.contentsOfDirectory(atPath: nvm)) ?? []).sorted { $0.compare($1, options: .numeric) == .orderedDescending }
        d += versiones.map { "\(nvm)/\($0)/bin" }
        return d
    }

    static func buscar(_ comandos: [String]) -> String? {
        for c in comandos {
            if let r = dirs().map({ "\($0)/\(c)" }).first(where: { FileManager.default.isExecutableFile(atPath: $0) }) { return r }
        }
        return nil
    }

    static var paraJS: [[String: Any]] {
        conocidas.map { ["id": $0.id, "nombre": $0.nombre, "instalada": buscar($0.comandos) != nil] }
    }

    /// Prueba real: le pide una palabra. Así sabemos que está instalada y con la sesión iniciada.
    static func probar(_ id: String, _ fin: @escaping @MainActor (Bool, String) -> Void) {
        guard let ia = conocidas.first(where: { $0.id == id }), let ruta = buscar(ia.comandos) else { fin(false, Idioma.t("No está instalada.")); return }
        let pedido = "Responde solo con la palabra: listo"
        let esAgy = (ruta as NSString).lastPathComponent == "agy"
        let args: [String]
        switch id {
        case "codex": args = ["exec", "--skip-git-repo-check", "-s", "read-only", "-"]
        case "gemini" where esAgy: args = ["--output-format", "text", "--sandbox", "-p", pedido]
        case "gemini": args = ["-p", "Responde a las instrucciones de arriba.", "-o", "text"]
        default: args = ["-p", "--output-format", "text"]
        }
        let p = Process(), salida = Pipe(), error = Pipe(), entrada = Pipe()
        p.executableURL = URL(fileURLWithPath: ruta)
        p.arguments = args
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = (dirs() + ["/bin"]).joined(separator: ":")
        p.environment = env
        p.currentDirectoryURL = FileManager.default.temporaryDirectory
        p.standardInput = entrada; p.standardOutput = salida; p.standardError = error
        p.terminationHandler = { pr in
            let texto = String(data: salida.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            let err = String(data: error.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            Task { @MainActor in
                let ok = pr.terminationStatus == 0 && !texto.isEmpty
                fin(ok, ok ? texto.trimmingCharacters(in: .whitespacesAndNewlines) : String(err.suffix(300)))
            }
        }
        do { try p.run() } catch { fin(false, error.localizedDescription); return }
        entrada.fileHandleForWriting.write(pedido.data(using: .utf8)!)
        try? entrada.fileHandleForWriting.close()
        DispatchQueue.main.asyncAfter(deadline: .now() + 90) { if p.isRunning { p.terminate() } }
    }
}

// MARK: - Scripts de bin/ (contrato: el último argumento es la ruta del JSON de salida)

@MainActor
enum Procesador {
    /// `secreto` (la llave de un conector) viaja por la entrada estándar: nunca en un archivo, en un argumento ni en el entorno.
    /// Si el script responde una llave nueva, llega por su salida estándar («CREDENCIAL {json}») y se entrega en "credencial".
    static func correrJSON(_ script: String, _ args: [String], secreto: String? = nil, fin: @escaping @MainActor ([String: Any]) -> Void) {
        let salida = FileManager.default.temporaryDirectory.appendingPathComponent("alcancia-\(UUID().uuidString).json")
        let p = Process()
        p.executableURL = Rutas.python
        p.arguments = [Rutas.recursos.appendingPathComponent("bin/\(script)").path] + args + [salida.path]
        // Nada de lo que venga del entorno con nombre ALCANCIA_* (p. ej. un modo de prueba puesto por otro programa) llega a los scripts.
        var env = ProcessInfo.processInfo.environment.filter { !$0.key.hasPrefix("ALCANCIA_") }
        env["ALCANCIA_RECURSOS"] = Rutas.recursos.path
        env["PYTHONIOENCODING"] = "utf-8"
        p.environment = env
        let entrada = Pipe(), salidaEstandar = Pipe()
        p.standardInput = secreto == nil ? FileHandle.nullDevice : entrada
        p.standardOutput = secreto == nil ? FileHandle.nullDevice : salidaEstandar
        p.standardError = FileHandle.nullDevice
        p.terminationHandler = { _ in
            let texto = secreto == nil ? "" : (String(data: salidaEstandar.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? "")
            Task { @MainActor in
                var r = Archivos.leerJSON(salida)
                try? FileManager.default.removeItem(at: salida)
                if let linea = texto.split(separator: "\n").last(where: { $0.hasPrefix("CREDENCIAL ") }),
                   let d = linea.dropFirst("CREDENCIAL ".count).data(using: .utf8),
                   let nueva = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
                    r["credencial"] = nueva
                }
                fin(r.isEmpty ? ["ok": false, "error": Idioma.t("No pude terminar. Intenta de nuevo.")] : r)
            }
        }
        do { try p.run() } catch { fin(["ok": false, "error": error.localizedDescription]); return }
        if let secreto {
            entrada.fileHandleForWriting.write(Data(secreto.utf8))
            try? entrada.fileHandleForWriting.close()
        }
    }

    /// Igual que correrJSON, pero lo que manda la interfaz va en un archivo de entrada (nada de armar comandos con su texto).
    static func conEntrada(_ script: String, _ accion: String, _ datos: [String: Any], fin: @escaping @MainActor ([String: Any]) -> Void) {
        let entrada = FileManager.default.temporaryDirectory.appendingPathComponent("alcancia-entrada-\(UUID().uuidString).json")
        Archivos.escribirJSON(entrada, datos)
        correrJSON(script, [accion, entrada.path]) { r in
            try? FileManager.default.removeItem(at: entrada)
            fin(r)
        }
    }
}
