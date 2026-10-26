import AppKit
import UserNotifications

// MARK: - Avisos de compromisos: notificaciones del sistema 3 días antes, el día que vence y si quedó atrasado

/// bin/compromisos.py decide qué avisar hoy (una vez cada cosa por vencimiento y como máximo un aviso por compromiso al día);
/// aquí solo se arma el texto en el idioma elegido y se muestra. Nada de esto corre antes de que exista idioma
/// (AlcanciaApp.iniciarTareas) y el permiso del sistema se pide recién cuando la persona agrega su primer compromiso o activa
/// «Avisarme antes de que venza», nunca al abrir la app.
@MainActor
enum Avisos {
    private static var reloj: Timer?
    private static let delegado = DelegadoAvisos()

    static var activos: Bool { Config.leer()["avisos"] as? Bool == true }

    /// Sin identificador de app (p. ej. `swift run` fuera de Alcancia.app) el centro de notificaciones no existe.
    private static var centro: UNUserNotificationCenter? {
        guard Bundle.main.bundleIdentifier != nil else { return nil }
        let c = UNUserNotificationCenter.current()
        if c.delegate == nil { c.delegate = delegado }
        return c
    }

    /// La persona los activa (o agrega su primer compromiso): recién ahí se pide el permiso del sistema.
    static func activar(_ si: Bool) {
        Config.guardar(["avisos": si])
        guard si, Idioma.elegido, let centro else { return }
        centro.requestAuthorization(options: [.alert, .sound]) { ok, _ in
            Task { @MainActor in if ok { revisar() } }
        }
    }

    /// Al abrir (ya con idioma) y luego cada 6 horas, igual que las conexiones.
    static func revisarCadaRato() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 12) { revisar() }
        reloj?.invalidate()
        reloj = Timer.scheduledTimer(withTimeInterval: 6 * 3600, repeats: true) { _ in Task { @MainActor in revisar() } }
    }

    /// Solo si la persona los activó y el sistema ya dio permiso (aquí nunca se pide).
    static func revisar() {
        guard activos, Idioma.elegido, let centro else { return }
        centro.getNotificationSettings { ajustes in
            let permitido = ajustes.authorizationStatus == .authorized || ajustes.authorizationStatus == .provisional
            Task { @MainActor in if permitido { pedirYMostrar() } }
        }
    }

    private static func pedirYMostrar() {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        Procesador.correrJSON("compromisos.py", ["avisos", f.string(from: Date())]) { r in
            for a in r["avisos"] as? [[String: Any]] ?? [] { mostrar(a) }
        }
    }

    private static func mostrar(_ a: [String: Any]) {
        guard let centro else { return }
        let nombre = a["nombre"] as? String ?? ""
        let monto = dinero(a["monto"], a["moneda"] as? String ?? "CLP")
        let dias = (a["dias"] as? NSNumber)?.intValue ?? 0
        let poner = { (plantilla: String) in
            Idioma.t(plantilla).replacingOccurrences(of: "{c}", with: nombre).replacingOccurrences(of: "{x}", with: monto)
                .replacingOccurrences(of: "{n}", with: String(dias))
        }
        let c = UNMutableNotificationContent()
        switch a["tipo"] as? String {
        case "hoy":
            c.title = poner("{c} vence hoy")
            c.body = poner("Vence hoy: {x}") + " " + poner("Si ya lo pagaste, márcalo en Alcancía.")
        case "atrasado":
            c.title = poner("{c} está atrasado")
            c.body = poner("Atrasado: {x}") + " " + poner("Si ya lo pagaste, márcalo en Alcancía.")
        default:
            c.title = poner("{c} vence pronto")
            c.body = dias == 1 ? poner("Vence mañana: {x}") : poner("Vence en {n} días: {x}")
        }
        c.sound = .default
        let id = ["alcancia", a["id"] as? String ?? "", a["vence"] as? String ?? "", a["tipo"] as? String ?? ""].joined(separator: "-")
        centro.add(UNNotificationRequest(identifier: id, content: c, trigger: nil))
    }

    /// El monto como lo muestra la interfaz (moneda y país de la persona, en el idioma elegido).
    static func dinero(_ v: Any?, _ moneda: String) -> String {
        let n = (v as? NSNumber)?.doubleValue ?? 0
        let pais = Config.texto("pais").isEmpty ? "CL" : Config.texto("pais")
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.currencyCode = moneda
        f.locale = Locale(identifier: "\(Idioma.codigo)_\(pais)")
        f.maximumFractionDigits = n.rounded() == n ? 0 : 2
        return f.string(from: NSNumber(value: n)) ?? String(n)
    }
}

/// Muestra el aviso aunque la app esté abierta y, al tocarlo, abre Alcancía en Compromisos.
final class DelegadoAvisos: NSObject, UNUserNotificationCenterDelegate {
    func userNotificationCenter(_ centro: UNUserNotificationCenter, willPresent aviso: UNNotification,
                                withCompletionHandler fin: @escaping (UNNotificationPresentationOptions) -> Void) {
        fin([.banner, .sound])
    }

    func userNotificationCenter(_ centro: UNUserNotificationCenter, didReceive respuesta: UNNotificationResponse,
                                withCompletionHandler fin: @escaping () -> Void) {
        Task { @MainActor in Ventana.shared.abrirCompromisos() }
        fin()
    }
}
