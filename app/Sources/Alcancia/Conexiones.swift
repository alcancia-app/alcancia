import AppKit
import PiezaHost
import Security

// MARK: - Conexiones: probar la llave, traer movimientos y revisar solas cada 6 horas

/// Las llaves de los conectores quedan en el Llavero (pieza «host-mac»: `Secretos`, solo en este Mac), con el servicio y la cuenta
/// de siempre («Alcancía · conexiones» / el id del conector): quien ya conectó una cuenta no tiene que volver a hacerlo. Nunca van
/// a ~/Alcancia ni a ningún archivo: llegan a bin/sincronizar.py por la entrada estándar (`Procesador.conSecreto`) y una llave
/// nueva vuelve por su salida estándar («CREDENCIAL {json}»).
@MainActor
enum Conexiones {
    static let llavero = Secretos(servicio: "Alcancía · conexiones")
    private static var reloj: Timer?
    private static var enCurso = Set<String>()
    /// Un conector pide varias páginas a su API (cada pedido tiene su tope en bin/red.py).
    static let limite = 600

    static func valido(_ id: String) -> String { String(id.filter { $0.isLowercase || $0.isNumber || $0 == "_" }.prefix(40)) }

    static func conectar(_ id: String, campos: [String: Any], fin: @escaping @MainActor ([String: Any]) -> Void) {
        let limpio = campos.compactMapValues { $0 as? String }
        guard !id.isEmpty, let d = try? JSONSerialization.data(withJSONObject: limpio), let json = String(data: d, encoding: .utf8) else {
            return fin(["ok": false, "error": Idioma.t("No se pudo conectar.")])
        }
        Procesador.conSecreto("sincronizar.py", ["probar", id], secreto: json, limite: 120) { res in
            let r = res.respuesta
            guard r["ok"] as? Bool == true else { return fin(r) }
            // Si el servicio canjeó la llave por una definitiva, se guarda esa.
            let cred = credencial(res.salidaEstandar) ?? json
            guard llavero.guardar(cred, cuenta: id) else { return fin(["ok": false, "error": Idioma.t("No pude guardar la llave en el Llavero.")]) }
            fin(r)
            traer(id, manual: false)
        }
    }

    static func desconectar(_ id: String) {
        llavero.borrar(id)
        Procesador.conEntrada("guardar.py", "desconectar", ["conector": id], limite: 30) { _ in Estado.enviar() }
    }

    static func traer(_ id: String, manual: Bool) {
        guard !enCurso.contains(id) else { return }
        guard let cred = llavero.leer(id) else {
            return Puente.shared.llamar("sincronizado", ["conector": id, "ok": false, "error": Idioma.t("Vuelve a conectar esta cuenta.")])
        }
        enCurso.insert(id)
        Procesador.conSecreto("sincronizar.py", ["traer", id], secreto: cred, limite: limite) { res in
            enCurso.remove(id)
            if let nueva = credencial(res.salidaEstandar) { llavero.guardar(nueva, cuenta: id) }
            var r = res.respuesta
            r["conector"] = id
            r["manual"] = manual
            Puente.shared.llamar("sincronizado", r)
            Estado.enviar()
        }
    }

    /// «CREDENCIAL {json}» en la salida estándar del script: la llave nueva (ya como JSON de texto, tal cual se guarda).
    private static func credencial(_ salida: String) -> String? {
        guard let linea = salida.split(separator: "\n").last(where: { $0.hasPrefix("CREDENCIAL ") }) else { return nil }
        let texto = String(linea.dropFirst("CREDENCIAL ".count))
        guard let d = texto.data(using: .utf8), (try? JSONSerialization.jsonObject(with: d)) is [String: Any] else { return nil }
        return texto
    }

    /// Los conectores que tienen llave guardada. `Secretos` no lista cuentas (pendiente para Pieza): se pregunta al Llavero
    /// por el mismo servicio.
    static func conectados() -> [String] {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: llavero.servicio,
                                kSecReturnAttributes as String: true, kSecMatchLimit as String: kSecMatchLimitAll]
        var r: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &r) == errSecSuccess, let lista = r as? [[String: Any]] else { return [] }
        return lista.compactMap { $0[kSecAttrAccount as String] as? String }.sorted()
    }

    static func traerTodo() { conectados().forEach { traer($0, manual: false) } }

    /// Al abrir la app y luego cada 6 horas (los servicios ponen límites de consultas; más seguido no aporta).
    static func revisarCadaRato() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) { traerTodo() }
        reloj?.invalidate()
        reloj = Timer.scheduledTimer(withTimeInterval: 6 * 3600, repeats: true) { _ in Task { @MainActor in traerTodo() } }
    }
}

// MARK: - Carpeta vigilada: las cartolas que la persona descarga se agregan solas (bin/vigilar.py decide qué importar)

/// El vigilante de la pieza «host-mac» (FSEvents) sobre ~/Downloads, aparte del de la carpeta elegida (Alcancía no tiene una):
/// cuando la carpeta queda quieta 5 segundos, bin/vigilar.py importa lo nuevo que reconozca una receta.
@MainActor
enum Descargas {
    private static var vigilante: Vigilante?
    private static var revisando = false
    private static var otraVez = false

    static var carpeta: URL { FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Downloads") }

    static func activar(_ si: Bool) {
        Config.guardar(["vigilar": si], desdeInterfaz: false)
        if si {
            Procesador.correrJSON("vigilar.py", ["activar"], limite: 30) { _ in empezar() }
        } else {
            detener()
        }
    }

    static func empezar() {
        detener()
        guard Config.leer()["vigilar"] as? Bool == true else { return }
        let v = Vigilante(extensiones: Cartolas.extensiones, espera: 5)
        v.alCambiar = { _ in revisar() }
        v.empezar(carpeta)
        vigilante = v
        revisar()
    }

    static func detener() {
        vigilante?.detener()
        vigilante = nil
    }

    private static func revisar() {
        guard !revisando else { otraVez = true; return }
        revisando = true
        Procesador.correrJSON("vigilar.py", [carpeta.path], limite: 1800) { r in
            revisando = false
            if otraVez { otraVez = false; revisar() }
            let importados = r["importados"] as? [[String: Any]] ?? []
            let sinReceta = r["sin_receta"] as? [String] ?? []
            guard !importados.isEmpty || !sinReceta.isEmpty else { return }
            Puente.shared.llamar("importadoSolo", r)
            Estado.enviar()
            if !importados.isEmpty, !NSApp.isActive { NSApp.requestUserAttention(.informationalRequest) }
        }
    }
}
