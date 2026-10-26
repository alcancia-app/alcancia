import AppKit
import Security

// MARK: - Llavero: las llaves de los conectores, cifradas por macOS (nunca en ~/Alcancia ni en ningún archivo)

enum Llavero {
    static let servicio = "Alcancía · conexiones"

    private static func base(_ cuenta: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: servicio, kSecAttrAccount as String: cuenta]
    }

    static func guardar(_ conector: String, _ valor: [String: Any]) -> Bool {
        guard let datos = try? JSONSerialization.data(withJSONObject: valor) else { return false }
        SecItemDelete(base(conector) as CFDictionary)
        var item = base(conector)
        item[kSecValueData as String] = datos
        item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly  // no viaja a otros equipos ni a respaldos
        item[kSecAttrLabel as String] = "Alcancía · \(conector)"
        return SecItemAdd(item as CFDictionary, nil) == errSecSuccess
    }

    static func leer(_ conector: String) -> String? {
        var q = base(conector)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var r: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &r) == errSecSuccess, let d = r as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }

    static func borrar(_ conector: String) { SecItemDelete(base(conector) as CFDictionary) }

    /// Los conectores que tienen llave guardada.
    static func conectados() -> [String] {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: servicio,
                                kSecReturnAttributes as String: true, kSecMatchLimit as String: kSecMatchLimitAll]
        var r: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &r) == errSecSuccess, let lista = r as? [[String: Any]] else { return [] }
        return lista.compactMap { $0[kSecAttrAccount as String] as? String }.sorted()
    }
}

// MARK: - Conexiones: probar la llave, traer movimientos y revisar solas cada 6 horas

@MainActor
enum Conexiones {
    private static var reloj: Timer?
    private static var enCurso = Set<String>()

    static func valido(_ id: String) -> String { String(id.filter { $0.isLowercase || $0.isNumber || $0 == "_" }.prefix(40)) }

    static func conectar(_ id: String, campos: [String: Any], fin: @escaping @MainActor ([String: Any]) -> Void) {
        let limpio = campos.compactMapValues { $0 as? String }
        guard let d = try? JSONSerialization.data(withJSONObject: limpio), let json = String(data: d, encoding: .utf8) else {
            return fin(["ok": false, "error": Idioma.t("No se pudo conectar.")])
        }
        Procesador.correrJSON("sincronizar.py", ["probar", id], secreto: json) { r in
            guard r["ok"] as? Bool == true else { return fin(r) }
            // Si el servicio canjeó la llave por una definitiva, se guarda esa.
            let cred = (r["credencial"] as? [String: Any]) ?? limpio
            guard Llavero.guardar(id, cred) else { return fin(["ok": false, "error": Idioma.t("No pude guardar la llave en el Llavero.")]) }
            var sin = r
            sin.removeValue(forKey: "credencial")
            fin(sin)
            traer(id, manual: false)
        }
    }

    static func desconectar(_ id: String) {
        Llavero.borrar(id)
        Procesador.conEntrada("guardar.py", "desconectar", ["conector": id]) { _ in Ventana.shared.enviarEstado() }
    }

    static func traer(_ id: String, manual: Bool) {
        guard !enCurso.contains(id), let cred = Llavero.leer(id) else {
            if Llavero.leer(id) == nil { Ventana.shared.llamar("sincronizado", ["conector": id, "ok": false, "error": Idioma.t("Vuelve a conectar esta cuenta.")]) }
            return
        }
        enCurso.insert(id)
        Procesador.correrJSON("sincronizar.py", ["traer", id], secreto: cred) { r in
            enCurso.remove(id)
            if let nueva = r["credencial"] as? [String: Any] { _ = Llavero.guardar(id, nueva) }
            var sin = r
            sin.removeValue(forKey: "credencial")
            sin["conector"] = id
            sin["manual"] = manual
            Ventana.shared.llamar("sincronizado", sin)
            Ventana.shared.enviarEstado()
        }
    }

    static func traerTodo() { Llavero.conectados().forEach { traer($0, manual: false) } }

    /// Al abrir la app y luego cada 6 horas (los servicios ponen límites de consultas; más seguido no aporta).
    static func revisarCadaRato() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) { traerTodo() }
        reloj?.invalidate()
        reloj = Timer.scheduledTimer(withTimeInterval: 6 * 3600, repeats: true) { _ in Task { @MainActor in traerTodo() } }
    }
}

// MARK: - Carpeta vigilada: las cartolas que la persona descarga se agregan solas (bin/vigilar.py decide qué importar)

@MainActor
enum Vigilante {
    private static var fuente: DispatchSourceFileSystemObject?
    private static var espera: DispatchWorkItem?
    private static var revisando = false

    static var carpeta: URL { FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Downloads") }

    static func activar(_ si: Bool) {
        Config.guardar(["vigilar": si])
        if si {
            Procesador.correrJSON("vigilar.py", ["activar"]) { _ in empezar() }
        } else {
            detener()
        }
    }

    static func empezar() {
        detener()
        guard Config.leer()["vigilar"] as? Bool == true else { return }
        let fd = open(carpeta.path, O_EVTONLY)
        guard fd >= 0 else { return }
        let f = DispatchSource.makeFileSystemObjectSource(fileDescriptor: fd, eventMask: [.write, .rename], queue: .main)
        f.setEventHandler { Task { @MainActor in programar() } }
        f.setCancelHandler { close(fd) }
        f.resume()
        fuente = f
        programar()
    }

    static func detener() {
        fuente?.cancel()
        fuente = nil
    }

    /// Las descargas escriben el archivo de a poco: se espera a que la carpeta quede quieta unos segundos.
    private static func programar() {
        espera?.cancel()
        let t = DispatchWorkItem { Task { @MainActor in revisar() } }
        espera = t
        DispatchQueue.main.asyncAfter(deadline: .now() + 5, execute: t)
    }

    private static func revisar() {
        guard !revisando else { return programar() }
        revisando = true
        Procesador.correrJSON("vigilar.py", [carpeta.path]) { r in
            revisando = false
            let importados = r["importados"] as? [[String: Any]] ?? []
            let sinReceta = r["sin_receta"] as? [String] ?? []
            guard !importados.isEmpty || !sinReceta.isEmpty else { return }
            Ventana.shared.llamar("importadoSolo", r)
            Ventana.shared.enviarEstado()
            if !importados.isEmpty, !NSApp.isActive { NSApp.requestUserAttention(.informationalRequest) }
        }
    }
}
