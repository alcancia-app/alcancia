import Foundation
import Capacitor
import Security
import UIKit
import UniformTypeIdentifiers

/// La copia para el celular que deja el Mac en la nube de la persona (iCloud Drive, Google Drive, OneDrive…): la persona elige el
/// archivo una vez con el selector del sistema y Alcancía guarda un marcador (bookmark) para volver a leerlo al abrir y al volver a
/// primer plano, sin preguntar de nuevo. Alcancía no se conecta a ninguna nube: lee el archivo que el sistema le muestra.
/// El archivo ya viene cifrado (ui/copia.js lo abre en la interfaz); aquí solo se lee el texto.
/// Además: la última copia que se abrió bien (para mirar sin conexión), la llave recordada en el Llavero (solo si la persona lo pidió;
/// solo este equipo, nunca en respaldos) y los ajustes del teléfono (idioma, bienvenida, avisos).
///
/// JS: Carpeta.elegir() → {nombre, texto}     Carpeta.leer() → {nombre, texto}  (SIN_ARCHIVO si nunca eligió; ARCHIVO si no se pudo)
///     Carpeta.olvidar()   Carpeta.guardarCache({texto})   Carpeta.leerCache() → {texto?}
///     Carpeta.guardarLlave({valor})   Carpeta.leerLlave() → {valor?}   Carpeta.borrarLlave()
///     Carpeta.guardarAjustes({texto})   Carpeta.leerAjustes() → {texto?}          Cancelar el selector: error con código CANCELADO.
@objc(CarpetaPlugin)
public class CarpetaPlugin: CAPPlugin, CAPBridgedPlugin, UIDocumentPickerDelegate {
    public let identifier = "CarpetaPlugin"
    public let jsName = "Carpeta"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "elegir", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "leer", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "olvidar", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "guardarCache", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "leerCache", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "guardarLlave", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "leerLlave", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "borrarLlave", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "guardarAjustes", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "leerAjustes", returnType: CAPPluginReturnPromise)
    ]

    private static let maximo = 100 * 1024 * 1024 // una copia más grande que esto no es de Alcancía
    private static let claveMarcador = "alcancia.celular.marcador"
    private static let claveAjustes = "alcancia.celular.ajustes"
    private static let servicioLlavero = "app.alcancia.movil.copia"
    private var llamada: CAPPluginCall?

    // MARK: El archivo de la nube

    @objc func elegir(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            guard self.llamada == nil, let vista = self.bridge?.viewController else { return call.reject("Ya hay un selector abierto.", "OCUPADO") }
            self.llamada = call
            // Sin copiar (asCopy: false): así queda un marcador para volver a leer el mismo archivo cuando el Mac lo actualice.
            let selector = UIDocumentPickerViewController(forOpeningContentTypes: [UTType.data, UTType.item], asCopy: false)
            selector.allowsMultipleSelection = false
            selector.delegate = self
            vista.present(selector, animated: true)
        }
    }

    public func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        guard let call = llamada else { return }
        llamada = nil
        guard let url = urls.first else { return call.reject("cancelado", "CANCELADO") }
        DispatchQueue.global(qos: .userInitiated).async {
            let acceso = url.startAccessingSecurityScopedResource()
            defer { if acceso { url.stopAccessingSecurityScopedResource() } }
            guard let marcador = try? url.bookmarkData(options: [], includingResourceValuesForKeys: nil, relativeTo: nil) else {
                return call.reject("No pude recordar ese archivo.", "ARCHIVO")
            }
            UserDefaults.standard.set(marcador, forKey: Self.claveMarcador)
            Self.responder(call, url)
        }
    }

    public func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        llamada?.reject("cancelado", "CANCELADO")
        llamada = nil
    }

    @objc func leer(_ call: CAPPluginCall) {
        guard let marcador = UserDefaults.standard.data(forKey: Self.claveMarcador) else { return call.reject("Todavía no eliges el archivo.", "SIN_ARCHIVO") }
        DispatchQueue.global(qos: .userInitiated).async {
            var viejo = false
            guard let url = try? URL(resolvingBookmarkData: marcador, options: [], relativeTo: nil, bookmarkDataIsStale: &viejo) else {
                return call.reject("No encuentro el archivo.", "ARCHIVO")
            }
            let acceso = url.startAccessingSecurityScopedResource()
            defer { if acceso { url.stopAccessingSecurityScopedResource() } }
            // El archivo se movió o se reemplazó: se renueva el marcador mientras todavía hay acceso.
            if viejo, let nuevo = try? url.bookmarkData(options: [], includingResourceValuesForKeys: nil, relativeTo: nil) {
                UserDefaults.standard.set(nuevo, forKey: Self.claveMarcador)
            }
            Self.responder(call, url)
        }
    }

    /// Lee el archivo con un NSFileCoordinator (así iCloud Drive y los demás proveedores entregan la versión más nueva) y con tope.
    private static func responder(_ call: CAPPluginCall, _ url: URL) {
        try? FileManager.default.startDownloadingUbiquitousItem(at: url) // si está en iCloud y no se ha bajado (no hace nada si no)
        var errorCoordinador: NSError?
        var datos: Data?
        NSFileCoordinator(filePresenter: nil).coordinate(readingItemAt: url, options: [], error: &errorCoordinador) { u in
            guard let manija = try? FileHandle(forReadingFrom: u) else { return }
            defer { try? manija.close() }
            datos = try? manija.read(upToCount: Self.maximo + 1)
        }
        guard errorCoordinador == nil, let d = datos, d.count <= Self.maximo, let texto = String(data: d, encoding: .utf8) else {
            return call.reject("No pude leer el archivo.", "ARCHIVO")
        }
        call.resolve(["nombre": url.lastPathComponent, "texto": texto])
    }

    /// Desconectar este teléfono: sin marcador, sin la última copia y sin la llave (los ajustes quedan).
    @objc func olvidar(_ call: CAPPluginCall) {
        UserDefaults.standard.removeObject(forKey: Self.claveMarcador)
        try? FileManager.default.removeItem(at: Self.rutaCache)
        Self.borrar()
        call.resolve()
    }

    // MARK: La última copia que se abrió bien (sigue cifrada)

    private static var rutaCache: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("Alcancia", isDirectory: true)
        return base.appendingPathComponent("copia.alcancia")
    }

    @objc func guardarCache(_ call: CAPPluginCall) {
        guard let texto = call.getString("texto"), texto.utf8.count <= Self.maximo else { return call.reject("Falta la copia.", "COPIA") }
        do {
            var carpeta = Self.rutaCache.deletingLastPathComponent()
            try FileManager.default.createDirectory(at: carpeta, withIntermediateDirectories: true)
            var fuera = URLResourceValues()
            fuera.isExcludedFromBackup = true // ya está en la nube de la persona: no hace falta en el respaldo del teléfono
            try? carpeta.setResourceValues(fuera)
            try Data(texto.utf8).write(to: Self.rutaCache, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
            call.resolve()
        } catch {
            call.reject("No pude guardar la copia.", "COPIA")
        }
    }

    @objc func leerCache(_ call: CAPPluginCall) {
        guard let d = try? Data(contentsOf: Self.rutaCache), d.count <= Self.maximo, let texto = String(data: d, encoding: .utf8) else { return call.resolve([:]) }
        call.resolve(["texto": texto])
    }

    // MARK: La llave recordada (Llavero de iOS, solo este equipo y con el teléfono desbloqueado)

    private static func consulta() -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: servicioLlavero, kSecAttrAccount as String: "llave"]
    }

    private static func borrar() { SecItemDelete(consulta() as CFDictionary) }

    @objc func guardarLlave(_ call: CAPPluginCall) {
        guard let valor = call.getString("valor"), !valor.isEmpty, valor.utf8.count < 4096 else { return call.reject("Falta la llave.", "LLAVE") }
        Self.borrar()
        var item = Self.consulta()
        item[kSecValueData as String] = Data(valor.utf8)
        item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly // no viaja a otros equipos ni a respaldos
        guard SecItemAdd(item as CFDictionary, nil) == errSecSuccess else { return call.reject("No pude guardar la llave.", "LLAVE") }
        call.resolve()
    }

    @objc func leerLlave(_ call: CAPPluginCall) {
        var q = Self.consulta()
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var r: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &r) == errSecSuccess, let d = r as? Data, let valor = String(data: d, encoding: .utf8) else {
            return call.resolve([:])
        }
        call.resolve(["valor": valor])
    }

    @objc func borrarLlave(_ call: CAPPluginCall) {
        Self.borrar()
        call.resolve()
    }

    // MARK: Ajustes del teléfono (idioma, bienvenida, avisos: nada secreto)

    @objc func guardarAjustes(_ call: CAPPluginCall) {
        guard let texto = call.getString("texto"), texto.utf8.count < 16384 else { return call.reject("Faltan los ajustes.", "AJUSTES") }
        UserDefaults.standard.set(texto, forKey: Self.claveAjustes)
        call.resolve()
    }

    @objc func leerAjustes(_ call: CAPPluginCall) {
        guard let texto = UserDefaults.standard.string(forKey: Self.claveAjustes) else { return call.resolve([:]) }
        call.resolve(["texto": texto])
    }
}
