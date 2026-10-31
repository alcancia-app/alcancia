import AppKit
import Security

// MARK: - Alcancía en tu celular: la copia cifrada en una carpeta de la nube de la persona

/// El Mac sigue siendo la fuente: lee cartolas y conectores y guarda las llaves. Para que el celular vea los números, deja en una
/// carpeta de la nube que elige la persona (iCloud Drive, Google Drive, OneDrive, Dropbox…) el archivo `Alcancia-celular.alcancia`,
/// cifrado con una frase que la persona elige una vez (formato en el README, «Copia para el celular»; código en ui/copia.js, sobre la pieza «cifrado» de ui/cifrado.js).
/// La interfaz deriva la llave de la frase con WebCrypto (PBKDF2-SHA256, 600.000 vueltas) y la manda aquí: se guarda **la llave, no
/// la frase**, en el Llavero (solo este Mac). Cuando toca copiar, la llave vuelve a la interfaz, que arma y cifra el contenido
/// (AES-256-GCM) con el estado que acaba de recibir y devuelve el texto; aquí solo se escribe el archivo.
/// Toca copiar: al abrir, cada vez que se manda el estado (importar, sincronizar, categorizar…) si algo cambió (la interfaz compara
/// la huella), con «Copiar ahora» y cada 6 horas aunque no haya cambios (así el celular sabe que el Mac sigue al día).
/// Ninguna ruta del Mac, llave de conector ni token entra al archivo: la interfaz usa una lista blanca (AlcanciaCopia.paraCelular).
@MainActor
enum Celular {
    static let archivo = "Alcancia-celular.alcancia"
    private static let servicio = "Alcancía · celular"
    private static let defaults = UserDefaults.standard
    private static let claveCarpeta = "celular.carpeta"   // marcador (bookmark) de la carpeta elegida
    private static let claveActivo = "celular.activo"
    private static let claveUltima = "celular.ultima"     // ISO 8601 de la última copia escrita
    private static let claveHuella = "celular.huella"     // SHA-256 del contenido de la última copia (sin la hora)
    private static let cada: TimeInterval = 6 * 3600
    private static let maximo = 100 * 1024 * 1024
    private static var reloj: Timer?
    private static var forzar = false
    private static var pedidaEn: Date?
    private static var elegida: URL?
    private static var ultimoError = ""

    // MARK: Llavero: la llave derivada y la cabecera (sal, vueltas, verificador). Nunca la frase.

    private static func base() -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: servicio, kSecAttrAccount as String: "llave"]
    }

    private static func guardarLlave(_ valor: [String: Any]) -> Bool {
        guard let datos = try? JSONSerialization.data(withJSONObject: valor) else { return false }
        SecItemDelete(base() as CFDictionary)
        var item = base()
        item[kSecValueData as String] = datos
        item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly  // no viaja a otros equipos ni a respaldos
        item[kSecAttrLabel as String] = "Alcancía · copia para el celular"
        return SecItemAdd(item as CFDictionary, nil) == errSecSuccess
    }

    private static func leerLlave() -> [String: Any]? {
        var q = base()
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var r: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &r) == errSecSuccess, let d = r as? Data,
              let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] else { return nil }
        return j
    }

    // MARK: La carpeta

    static var activo: Bool { defaults.bool(forKey: claveActivo) && carpeta() != nil }

    /// La carpeta elegida. Es un marcador: la sigue aunque la persona la mueva o le cambie el nombre.
    static func carpeta() -> URL? {
        guard let d = defaults.data(forKey: claveCarpeta) else { return nil }
        var vieja = false
        guard let u = try? URL(resolvingBookmarkData: d, options: [.withoutUI], relativeTo: nil, bookmarkDataIsStale: &vieja) else { return nil }
        if vieja, let nueva = try? u.bookmarkData() { defaults.set(nueva, forKey: claveCarpeta) }
        return u
    }

    /// En qué nube está la carpeta ("" si no parece una: el celular no la va a ver).
    static func nube(_ u: URL) -> String {
        if (try? u.resourceValues(forKeys: [.isUbiquitousItemKey]))?.isUbiquitousItem == true { return "iCloud Drive" }
        let p = u.resolvingSymlinksInPath().path
        if p.contains("/Library/Mobile Documents/") { return "iCloud Drive" }
        if p.contains("/Library/CloudStorage/GoogleDrive") || p.contains("/Google Drive") { return "Google Drive" }
        if p.contains("/Library/CloudStorage/OneDrive") || p.contains("/OneDrive") { return "OneDrive" }
        if p.contains("/Library/CloudStorage/Dropbox") || p.contains("/Dropbox") { return "Dropbox" }
        if p.contains("/Library/CloudStorage/Box") { return "Box" }
        if p.contains("/Library/CloudStorage/") { return Idioma.t("tu nube") }
        return ""
    }

    /// Lo que ve la interfaz en Ajustes (nunca la ruta completa: solo el nombre de la carpeta y la nube).
    static var paraJS: [String: Any] {
        guard defaults.bool(forKey: claveActivo), let u = carpeta() else { return ["activo": false] }
        return ["activo": true, "nombre": u.lastPathComponent, "nube": nube(u), "ultima": defaults.string(forKey: claveUltima) ?? "", "error": ultimoError]
    }

    static func panelCarpeta() -> NSOpenPanel {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        panel.prompt = Idioma.t("Elegir")
        panel.message = Idioma.t("Elige una carpeta de tu nube que también veas en tu celular (iCloud Drive, Google Drive, OneDrive o Dropbox)")
        let icloud = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs")
        if FileManager.default.fileExists(atPath: icloud.path) { panel.directoryURL = icloud }
        return panel
    }

    /// La carpeta que eligió en el asistente: se recuerda recién al activar (con la frase).
    static func carpetaElegida(_ u: URL?) {
        guard let u else { return Ventana.shared.llamar("celularCarpeta", ["ok": false, "cancelado": true]) }
        guard FileManager.default.isWritableFile(atPath: u.path) else {
            return Ventana.shared.llamar("celularCarpeta", ["ok": false, "error": Idioma.t("No puedo escribir en esa carpeta.")])
        }
        elegida = u
        Ventana.shared.llamar("celularCarpeta", ["ok": true, "nombre": u.lastPathComponent, "nube": nube(u)])
    }

    // MARK: Desde la interfaz

    static func atender(_ d: [String: Any]) {
        switch d["accion"] as? String ?? "" {
        case "activar": activar(d)
        case "escribir": escribir(d)
        case "copiar":
            forzar = true
            pedidaEn = nil
            Ventana.shared.enviarEstado()
        case "desactivar": desactivar()
        default: break
        }
    }

    /// La llave (en base64) y la cabecera llegan de la interfaz recién derivadas de la frase; se revisan antes de guardarlas.
    /// Pieza «cifrado»: las llaves nuevas son de 64 bytes (AES + HMAC); una de 32 (solo AES, de antes) sigue sirviendo.
    static let largosLlave: Set<Int> = [32, 64]

    private static func activar(_ d: [String: Any]) {
        guard let llave = d["llave"] as? String, let bytes = Data(base64Encoded: llave), largosLlave.contains(bytes.count),
              let cabecera = d["cabecera"] as? [String: Any], cabeceraValida(cabecera) else {
            return Ventana.shared.llamar("celularEscrito", ["ok": false, "error": Idioma.t("No pude crear la copia.")])
        }
        guard let u = elegida ?? carpeta(), let marcador = try? u.bookmarkData() else {
            return Ventana.shared.llamar("celularEscrito", ["ok": false, "error": Idioma.t("Elige una carpeta de tu nube.")])
        }
        guard guardarLlave(["llave": llave, "cabecera": cabecera]) else {
            return Ventana.shared.llamar("celularEscrito", ["ok": false, "error": Idioma.t("No pude guardar la llave en el Llavero.")])
        }
        defaults.set(marcador, forKey: claveCarpeta)
        defaults.set(true, forKey: claveActivo)
        defaults.removeObject(forKey: claveHuella)
        elegida = nil
        ultimoError = ""
        forzar = true
        pedidaEn = nil
        Ventana.shared.enviarEstado()
    }

    private static func cabeceraValida(_ c: [String: Any]) -> Bool {
        guard let k = c["kdf"] as? [String: Any], k["alg"] as? String == "PBKDF2-SHA256",
              let n = (k["iteraciones"] as? NSNumber)?.intValue, n >= 100_000, n <= 10_000_000,
              let sal = k["sal"] as? String, (Data(base64Encoded: sal)?.count ?? 0) >= 16, c["cifrado"] as? String == "AES-256-GCM",
              let v = c["verificador"] as? [String: Any], v["iv"] is String, v["datos"] is String else { return false }
        return true
    }

    /// La interfaz devuelve la copia ya cifrada (o «sin cambios»): se escribe de una vez (.atomic), así la nube nunca sube un archivo a medias.
    private static func escribir(_ d: [String: Any]) {
        pedidaEn = nil
        if d["sinCambios"] as? Bool == true { return }
        if let e = d["error"] as? String {
            ultimoError = e
            return Ventana.shared.llamar("celularEscrito", ["ok": false, "error": e])
        }
        guard activo, let u = carpeta(), let texto = d["texto"] as? String, texto.hasPrefix("{\"alcancia\":\"copia-celular\""),
              texto.utf8.count <= maximo else { return }
        let destino = u.appendingPathComponent(archivo)
        do {
            try Data(texto.utf8).write(to: destino, options: .atomic)
            try? FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: destino.path)
            let ahora = ISO8601DateFormatter().string(from: Date())
            defaults.set(ahora, forKey: claveUltima)
            if let h = d["huella"] as? String, h.count == 64 { defaults.set(h, forKey: claveHuella) }
            ultimoError = ""
            Ventana.shared.llamar("celularEscrito", ["ok": true, "ultima": ahora])
        } catch {
            ultimoError = Idioma.t("No pude escribir la copia en esa carpeta. ¿Sigue existiendo?")
            Ventana.shared.llamar("celularEscrito", ["ok": false, "error": ultimoError])
        }
    }

    /// Deja de copiar: sin llave ni carpeta. La copia que ya está en la nube queda ahí (Alcancía nunca borra archivos de la persona).
    private static func desactivar() {
        SecItemDelete(base() as CFDictionary)
        for k in [claveActivo, claveCarpeta, claveUltima, claveHuella] { defaults.removeObject(forKey: k) }
        elegida = nil
        ultimoError = ""
        Ventana.shared.enviarEstado()
    }

    // MARK: Cuándo copiar

    /// Después de mandar el estado a la interfaz (Ventana.enviarEstado): se le pide la copia. Si nada cambió, la interfaz no la arma,
    /// salvo que hayan pasado 6 horas o la persona la pidió. Una a la vez.
    static func despuesDelEstado() {
        if let p = pedidaEn, Date().timeIntervalSince(p) < 60 { return }
        guard activo, let guardado = leerLlave(), let llave = guardado["llave"] as? String, let cabecera = guardado["cabecera"] as? [String: Any] else { return }
        let ultima = defaults.string(forKey: claveUltima).flatMap { ISO8601DateFormatter().date(from: $0) }
        let toca = forzar || ultima.map { Date().timeIntervalSince($0) >= cada - 60 } ?? true
        forzar = false
        pedidaEn = Date()
        Ventana.shared.llamar("copiaCelular", ["llave": llave, "cabecera": cabecera, "forzar": toca, "anterior": defaults.string(forKey: claveHuella) ?? ""])
    }

    /// Cada 6 horas se vuelve a mandar el estado (y con él, la copia), aunque no haya conexiones que traigan movimientos.
    static func revisarCadaRato() {
        reloj?.invalidate()
        reloj = Timer.scheduledTimer(withTimeInterval: cada, repeats: true) { _ in Task { @MainActor in if activo { Ventana.shared.enviarEstado() } } }
    }
}
