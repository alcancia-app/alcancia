//! Alcancía en tu celular: la copia cifrada en una carpeta de la nube de la persona. Lo mismo que hacía Celular.swift.
//!
//! El computador sigue siendo la fuente: lee cartolas y conectores y guarda las llaves. Para que el celular vea los números, deja en
//! una carpeta de la nube que elige la persona (iCloud Drive, Google Drive, OneDrive, Dropbox…) el archivo
//! `Alcancia-celular.alcancia`, cifrado con una frase que la persona elige una vez (formato en el README, «Copia para el celular»;
//! código en ui/copia.js, sobre la pieza «cifrado»). La interfaz deriva la llave de la frase con WebCrypto y la manda aquí: se guarda
//! **la llave, no la frase**, en el llavero del sistema (solo este computador). Cuando toca copiar, la llave vuelve a la interfaz
//! (`copiaCelular`), que arma y cifra el contenido con el estado que acaba de recibir y devuelve el texto; aquí solo se escribe.
//! Toca copiar: al abrir, cada vez que se manda el estado si algo cambió (la interfaz compara la huella), con «Copiar ahora» y cada
//! 6 horas aunque no haya cambios. Ninguna ruta, llave de conector ni token entra al archivo (AlcanciaCopia.paraCelular).
//!
//! Dónde está la carpeta, si está activa y la última copia quedan en ~/Alcancia/.alcancia/celular.json (0600; nunca en config.json
//! ni en el estado). La app de Swift lo guardaba en sus preferencias (UserDefaults): la primera vez se trae de ahí.

use crate::pieza::enchufe as e;
use crate::pieza::host::Host;
use crate::{enviar_estado, responder};
use serde_json::{json, Map, Value};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime};

pub const ARCHIVO: &str = "Alcancia-celular.alcancia";
const CUENTA: &str = "llave";
const CADA: u64 = 6 * 3600;
const MAXIMO: usize = 100 * 1024 * 1024;
/// Pieza «cifrado»: las llaves nuevas son de 64 bytes (AES + HMAC); una de 32 (solo AES, de antes) sigue sirviendo.
const LARGOS_LLAVE: [usize; 2] = [32, 64];

static FORZAR: AtomicBool = AtomicBool::new(false);
static PEDIDA: Mutex<Option<Instant>> = Mutex::new(None);
/// La carpeta que eligió en el asistente: se recuerda recién al activar (con la frase).
static ELEGIDA: Mutex<Option<PathBuf>> = Mutex::new(None);
static ULTIMO_ERROR: Mutex<String> = Mutex::new(String::new());

fn ruta(h: &Host) -> PathBuf {
    h.datos.join("celular.json")
}

/// {carpeta, activo, ultima, huella}.
fn leer(h: &Host) -> Map<String, Value> {
    let r = ruta(h);
    if !r.exists() {
        migrar(h);
    }
    e::leer_json(&r, 64 * 1024).and_then(|v| v.as_object().cloned()).unwrap_or_default()
}

fn guardar(h: &Host, d: &Map<String, Value>) {
    let texto = Value::Object(d.clone()).to_string();
    let _ = e::escribir_atomico(&ruta(h), texto.as_bytes(), 0o600);
}

fn poner(h: &Host, cambios: Value) {
    let mut d = leer(h);
    for (k, v) in cambios.as_object().into_iter().flatten() {
        if v.is_null() {
            d.remove(k);
        } else {
            d.insert(k.clone(), v.clone());
        }
    }
    guardar(h, &d);
}

/// La primera vez: lo que dejó la app de Swift en sus preferencias (la carpeta como marcador, que se resuelve con el sistema).
/// Con un guion fijo de JavaScript para Automatización (osascript), sin nada de afuera adentro.
fn migrar(h: &Host) {
    #[cfg_attr(not(target_os = "macos"), allow(unused_mut))]
    let mut d = Map::new();
    #[cfg(target_os = "macos")]
    {
        const GUION: &str = r#"ObjC.import("Foundation");
var d = $.NSUserDefaults.alloc.initWithSuiteName("app.alcancia.mac");
var r = {activo: d.boolForKey("celular.activo"), ultima: ObjC.unwrap(d.stringForKey("celular.ultima")) || "", huella: ObjC.unwrap(d.stringForKey("celular.huella")) || ""};
var b = d.dataForKey("celular.carpeta");
if (b && !b.isNil()) { var u = $.NSURL.URLByResolvingBookmarkDataOptionsRelativeToURLBookmarkDataIsStaleError(b, 256, $(), null, null); if (u && !u.isNil()) r.carpeta = ObjC.unwrap(u.path); }
JSON.stringify(r);"#;
        if let Ok(s) = std::process::Command::new("/usr/bin/osascript").args(["-l", "JavaScript", "-e", GUION]).output() {
            if let Ok(Value::Object(o)) = serde_json::from_slice::<Value>(&s.stdout) {
                if o.get("activo") == Some(&Value::Bool(true)) {
                    if let Some(c) = o.get("carpeta").and_then(Value::as_str).filter(|c| Path::new(c).is_dir()) {
                        d.insert("carpeta".into(), json!(c));
                        d.insert("activo".into(), json!(true));
                    }
                }
                for k in ["ultima", "huella"] {
                    if let Some(v) = o.get(k).and_then(Value::as_str).filter(|v| !v.is_empty() && v.len() <= 64) {
                        d.insert(k.into(), json!(v));
                    }
                }
            }
        }
    }
    guardar(h, &d);
}

fn carpeta(h: &Host) -> Option<PathBuf> {
    leer(h).get("carpeta").and_then(Value::as_str).map(PathBuf::from).filter(|p| p.is_absolute() && p.is_dir())
}

fn activo(h: &Host) -> bool {
    leer(h).get("activo") == Some(&Value::Bool(true)) && carpeta(h).is_some()
}

/// En qué nube está la carpeta ("" si no parece una: el celular no la va a ver).
pub fn nube(h: &Host, u: &Path) -> String {
    let p = std::fs::canonicalize(u).unwrap_or_else(|_| u.to_path_buf()).to_string_lossy().into_owned();
    if p.contains("/Library/Mobile Documents/") || p.contains("iCloudDrive") {
        "iCloud Drive".into()
    } else if p.contains("/Library/CloudStorage/GoogleDrive") || p.contains("/Google Drive") || p.contains("Google Drive") {
        "Google Drive".into()
    } else if p.contains("/Library/CloudStorage/OneDrive") || p.contains("OneDrive") {
        "OneDrive".into()
    } else if p.contains("/Library/CloudStorage/Dropbox") || p.contains("Dropbox") {
        "Dropbox".into()
    } else if p.contains("/Library/CloudStorage/Box") {
        "Box".into()
    } else if p.contains("/Library/CloudStorage/") {
        h.t("tu nube")
    } else {
        String::new()
    }
}

/// Lo que ve la interfaz en Ajustes (nunca la ruta completa: solo el nombre de la carpeta y la nube).
pub fn para_js(h: &Host) -> Value {
    let d = leer(h);
    match carpeta(h).filter(|_| d.get("activo") == Some(&Value::Bool(true))) {
        None => json!({"activo": false}),
        Some(u) => json!({
            "activo": true,
            "nombre": u.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default(),
            "nube": nube(h, &u),
            "ultima": d.get("ultima").and_then(Value::as_str).unwrap_or(""),
            "error": ULTIMO_ERROR.lock().map(|e| e.clone()).unwrap_or_default(),
        }),
    }
}

fn llavero(h: &Host) -> crate::pieza::sistema::Secretos {
    h.secretos(Some("celular"))
}

pub fn atender(h: &Host, d: &Value) {
    match d["accion"].as_str().unwrap_or("") {
        "carpeta" => elegir_carpeta(h),
        "activar" => activar(h, d),
        "escribir" => escribir(h, d),
        "copiar" => {
            FORZAR.store(true, Ordering::SeqCst);
            *PEDIDA.lock().unwrap_or_else(|e| e.into_inner()) = None;
            enviar_estado(h, None);
        }
        "desactivar" => desactivar(h),
        _ => {}
    }
}

/// El diálogo del sistema, que parte en iCloud Drive si existe.
fn elegir_carpeta(h: &Host) {
    let icloud = e::casa().join("Library/Mobile Documents/com~apple~CloudDocs");
    let titulo = h.t("Elige una carpeta de tu nube que también veas en tu celular (iCloud Drive, Google Drive, OneDrive o Dropbox)");
    let Some(u) = h.dialogo_carpeta(Some(titulo), icloud.is_dir().then_some(icloud)) else {
        return responder(h, "celularCarpeta", json!({"ok": false, "cancelado": true}));
    };
    if !escribible(&u) {
        return responder(h, "celularCarpeta", json!({"ok": false, "error": h.t("No puedo escribir en esa carpeta.")}));
    }
    let nombre = u.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
    let n = nube(h, &u);
    *ELEGIDA.lock().unwrap_or_else(|e| e.into_inner()) = Some(u);
    responder(h, "celularCarpeta", json!({"ok": true, "nombre": nombre, "nube": n}));
}

fn escribible(u: &Path) -> bool {
    let prueba = u.join(format!(".alcancia-prueba-{}", e::aleatorio_hex(4)));
    let ok = std::fs::write(&prueba, b"").is_ok();
    let _ = std::fs::remove_file(prueba);
    ok
}

fn b64_largo(s: &str) -> Option<usize> {
    // Largo en bytes de un base64 estándar bien formado (sin decodificarlo).
    let b = s.as_bytes();
    if b.is_empty() || !b.len().is_multiple_of(4) {
        return None;
    }
    let relleno = b.iter().rev().take_while(|c| **c == b'=').count();
    let cuerpo_ok = b[..b.len() - relleno].iter().all(|c| c.is_ascii_alphanumeric() || *c == b'+' || *c == b'/');
    (relleno <= 2 && cuerpo_ok).then(|| b.len() / 4 * 3 - relleno)
}

/// Cabecera de la pieza «cifrado»: PBKDF2-SHA256 con sal de 16+ bytes y su verificador.
pub fn cabecera_valida(c: &Value) -> bool {
    let k = &c["kdf"];
    k["alg"] == "PBKDF2-SHA256"
        && k["iteraciones"].as_i64().is_some_and(|n| (100_000..=10_000_000).contains(&n))
        && k["sal"].as_str().and_then(b64_largo).is_some_and(|n| n >= 16)
        && c["cifrado"] == "AES-256-GCM"
        && c["verificador"]["iv"].is_string()
        && c["verificador"]["datos"].is_string()
}

pub fn llave_valida(l: &str) -> bool {
    b64_largo(l).is_some_and(|n| LARGOS_LLAVE.contains(&n))
}

/// La llave (en base64) y la cabecera llegan de la interfaz recién derivadas de la frase; se revisan antes de guardarlas.
fn activar(h: &Host, d: &Value) {
    let no = |t: &str| responder(h, "celularEscrito", json!({"ok": false, "error": h.t(t)}));
    let (Some(llave), c) = (d["llave"].as_str().filter(|l| llave_valida(l)), &d["cabecera"]) else { return no("No pude crear la copia.") };
    if !cabecera_valida(c) {
        return no("No pude crear la copia.");
    }
    let elegida = ELEGIDA.lock().ok().and_then(|g| g.clone());
    let Some(u) = elegida.or_else(|| carpeta(h)).and_then(|u| std::fs::canonicalize(u).ok()).filter(|u| u.is_dir()) else {
        return no("Elige una carpeta de tu nube.");
    };
    if !llavero(h).guardar(CUENTA, &json!({"llave": llave, "cabecera": c}).to_string()) {
        return no("No pude guardar la llave en el Llavero.");
    }
    poner(h, json!({"carpeta": u.to_string_lossy(), "activo": true, "huella": null}));
    *ELEGIDA.lock().unwrap_or_else(|e| e.into_inner()) = None;
    ULTIMO_ERROR.lock().unwrap_or_else(|e| e.into_inner()).clear();
    FORZAR.store(true, Ordering::SeqCst);
    *PEDIDA.lock().unwrap_or_else(|e| e.into_inner()) = None;
    enviar_estado(h, None);
}

/// La interfaz devuelve la copia ya cifrada (o «sin cambios»): se escribe de una vez (escritura atómica), así la nube nunca sube un
/// archivo a medias.
fn escribir(h: &Host, d: &Value) {
    *PEDIDA.lock().unwrap_or_else(|e| e.into_inner()) = None;
    if d["sinCambios"] == true {
        return;
    }
    if let Some(err) = d["error"].as_str() {
        let err: String = err.chars().take(300).collect();
        *ULTIMO_ERROR.lock().unwrap_or_else(|e| e.into_inner()) = err.clone();
        return responder(h, "celularEscrito", json!({"ok": false, "error": err}));
    }
    let Some(texto) = d["texto"].as_str().filter(|t| t.starts_with("{\"alcancia\":\"copia-celular\"") && t.len() <= MAXIMO) else { return };
    let Some(u) = carpeta(h).filter(|_| activo(h)) else { return };
    if e::escribir_atomico(&u.join(ARCHIVO), texto.as_bytes(), 0o600).is_err() {
        let err = h.t("No pude escribir la copia en esa carpeta. ¿Sigue existiendo?");
        *ULTIMO_ERROR.lock().unwrap_or_else(|e| e.into_inner()) = err.clone();
        return responder(h, "celularEscrito", json!({"ok": false, "error": err}));
    }
    let ahora = ahora_iso();
    let huella = d["huella"].as_str().filter(|x| x.len() == 64 && x.chars().all(|c| c.is_ascii_hexdigit()));
    poner(h, json!({"ultima": ahora, "huella": huella}));
    ULTIMO_ERROR.lock().unwrap_or_else(|e| e.into_inner()).clear();
    responder(h, "celularEscrito", json!({"ok": true, "ultima": ahora}));
}

/// Deja de copiar: sin llave ni carpeta. La copia que ya está en la nube queda ahí (Alcancía nunca borra archivos de la persona).
fn desactivar(h: &Host) {
    llavero(h).borrar(CUENTA);
    guardar(h, &Map::new());
    *ELEGIDA.lock().unwrap_or_else(|e| e.into_inner()) = None;
    ULTIMO_ERROR.lock().unwrap_or_else(|e| e.into_inner()).clear();
    enviar_estado(h, None);
}

/// «2026-11-08T14:05:00Z» (ISO 8601, como antes).
fn ahora_iso() -> String {
    let s = SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
    let (a, m, d) = crate::civil((s / 86400) as i64);
    let r = s % 86400;
    format!("{a:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z", r / 3600, r % 3600 / 60, r % 60)
}

/// Segundos desde una fecha ISO 8601 escrita por `ahora_iso` (o la de Swift, que es igual). None si no se entiende.
fn hace(iso: &str) -> Option<u64> {
    let b = iso.as_bytes();
    if b.len() < 20 || b[4] != b'-' || b[10] != b'T' {
        return None;
    }
    let n = |a: usize, z: usize| iso.get(a..z)?.parse::<i64>().ok();
    let (a, m, d, hh, mm, ss) = (n(0, 4)?, n(5, 7)?, n(8, 10)?, n(11, 13)?, n(14, 16)?, n(17, 19)?);
    // Días desde 1970 (inverso de `civil`).
    let (y, mes) = if m <= 2 { (a - 1, m + 9) } else { (a, m - 3) };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let doy = (153 * mes + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let dias = era * 146_097 + doe - 719_468;
    let entonces = dias * 86400 + hh * 3600 + mm * 60 + ss;
    let ahora = SystemTime::now().duration_since(SystemTime::UNIX_EPOCH).map(|d| d.as_secs() as i64).ok()?;
    u64::try_from(ahora - entonces).ok()
}

/// Después de mandar el estado a la interfaz: se le pide la copia. Si nada cambió, la interfaz no la arma, salvo que hayan pasado
/// 6 horas o la persona la pidió. Una a la vez.
pub fn despues_del_estado(h: &Host) {
    {
        let p = PEDIDA.lock().unwrap_or_else(|e| e.into_inner());
        if p.is_some_and(|t| t.elapsed() < Duration::from_secs(60)) {
            return;
        }
    }
    if !activo(h) {
        return;
    }
    let Some(g) = llavero(h).leer(CUENTA).and_then(|t| serde_json::from_str::<Value>(&t).ok()) else { return };
    let (Some(llave), Some(cabecera)) = (g["llave"].as_str(), g.get("cabecera").filter(|c| c.is_object())) else { return };
    let d = leer(h);
    let toca = FORZAR.swap(false, Ordering::SeqCst) || d.get("ultima").and_then(Value::as_str).and_then(hace).is_none_or(|s| s + 60 >= CADA);
    *PEDIDA.lock().unwrap_or_else(|e| e.into_inner()) = Some(Instant::now());
    let anterior = d.get("huella").and_then(Value::as_str).unwrap_or("");
    responder(h, "copiaCelular", json!({"llave": llave, "cabecera": cabecera, "forzar": toca, "anterior": anterior}));
}

/// Cada 6 horas se vuelve a mandar el estado (y con él, la copia), aunque no haya conexiones que traigan movimientos.
pub fn revisar_cada_rato(h: &Host) {
    let h = h.clone();
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_secs(CADA));
        if activo(&h) {
            enviar_estado(&h, None);
        }
    });
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn llave_y_cabecera() {
        let l32 = "QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUE="; // 32 bytes
        assert!(llave_valida(l32));
        assert!(!llave_valida("QUFB")); // 3 bytes
        assert!(!llave_valida("no es base64!"));
        let c = json!({"kdf": {"alg": "PBKDF2-SHA256", "iteraciones": 600000, "sal": "AAAAAAAAAAAAAAAAAAAAAA=="}, "cifrado": "AES-256-GCM", "verificador": {"iv": "x", "datos": "y"}});
        assert!(cabecera_valida(&c));
        let mut mala = c.clone();
        mala["kdf"]["iteraciones"] = json!(10);
        assert!(!cabecera_valida(&mala));
        let mut mala = c.clone();
        mala["kdf"]["sal"] = json!("AAAA");
        assert!(!cabecera_valida(&mala));
    }

    #[test]
    fn fechas_iso() {
        let a = ahora_iso();
        assert_eq!(a.len(), 20);
        assert!(hace(&a).is_some_and(|s| s < 5));
        assert!(hace("2020-01-01T00:00:00Z").is_some_and(|s| s > 86400 * 365));
        assert!(hace("ayer").is_none());
    }
}
