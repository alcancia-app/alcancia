import AppKit
import PiezaHost

// MARK: - Cartolas: elegir el archivo, leer una muestra, aprender la receta e importar (con su avance)

/// Estas acciones no se declaran en acciones.json porque trabajan con un archivo de la persona fuera de la carpeta de datos (una ruta
/// absoluta que la interfaz nunca puede inventar): solo sirve la última cartola que la persona eligió en el panel del sistema.
@MainActor
enum Cartolas {
    static let extensiones = ["csv", "tsv", "txt", "xlsx", "pdf", "ofx", "qfx", "qif", "xml"]
    /// La última cartola que eligió la persona (el panel del sistema): la única ruta que se acepta de vuelta.
    private static var elegida: URL?
    private static var relojImportar: Timer?
    private static var estadoImportar: URL { Host.datos.appendingPathComponent("estado.json") }

    static func registrar(_ p: Puente) {
        p.registrar("elegirCartola") { _ in
            p.elegirArchivos(extensiones: extensiones,
                             mensaje: Idioma.t("Elige la cartola que descargaste de tu banco o billetera (CSV, Excel, PDF, OFX, QIF o CAMT.053)")) { urls in
                guard let u = urls.first else { return }
                elegida = u
                p.llamar("cartolaElegida", ["ruta": u.path, "nombre": u.lastPathComponent])
            }
        }
        p.registrar("vistaCartola") { d in
            guard let ruta = valida(d) else { return p.llamar("vistaLista", noPude) }
            Procesador.correrJSON("importar.py", ["vista", ruta], limite: 120) { p.llamar("vistaLista", $0) }
        }
        p.registrar("aprenderReceta") { d in
            guard let ruta = valida(d) else { return p.llamar("recetaAprendida", noPude) }
            let pais = (d["pais"] as? String ?? "CL").filter(\.isLetter).prefix(2)
            // La IA de la persona propone la receta (receta_ia.py la valida y la prueba con el mismo archivo).
            Procesador.correrJSON("receta_ia.py", [ruta, String(pais).uppercased()], limite: 600) { p.llamar("recetaAprendida", $0) }
        }
        p.registrar("importar") { d in
            guard let ruta = valida(d) else { return p.llamar("importado", noPude) }
            let receta = String((d["receta"] as? String ?? "").filter { $0.isLetter || $0.isNumber || $0 == "-" }.prefix(80))
            let ia = Texto.esBool(d["ia"]) && d["ia"] as? Bool == true
            try? FileManager.default.removeItem(at: estadoImportar)
            seguirImportacion(true)
            // Con la IA completando categorías puede tardar: hasta una hora. Mientras corre, actualizar o salir esperan (el host).
            Procesador.correrJSON("importar.py", ["guardar", ruta, receta, ia ? "1" : "0"], limite: 3600) { r in
                seguirImportacion(false)
                p.llamar("importado", r)
                Estado.enviar()
            }
        }
    }

    private static var noPude: [String: Any] { ["ok": false, "error": Idioma.t("No pude leer el archivo.")] }

    /// La ruta que manda la interfaz sirve solo si es la cartola que la persona eligió y todavía se puede leer.
    private static func valida(_ d: [String: Any]) -> String? {
        guard let e = elegida, let ruta = d["ruta"] as? String, ruta == e.path, FileManager.default.isReadableFile(atPath: ruta) else { return nil }
        return ruta
    }

    /// Mientras se importa, el avance (bin/importar.py lo deja en ~/Alcancia/.alcancia/estado.json) llega cada medio segundo.
    private static func seguirImportacion(_ activo: Bool) {
        relojImportar?.invalidate()
        relojImportar = nil
        guard activo else { return }
        relojImportar = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
            Task { @MainActor in
                let x = Archivos.leerJSON(estadoImportar)
                if !x.isEmpty { Puente.shared.llamar("importarProgreso", x) }
            }
        }
    }
}
