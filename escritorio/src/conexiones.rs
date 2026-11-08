//! Conexiones: probar la llave, traer movimientos y revisar solas cada 6 horas; y la carpeta vigilada (Descargas). Lo mismo que
//! hacía Conexiones.swift.
//!
//! Las llaves de los conectores quedan en el llavero del sistema (pieza «host-tauri»: `Secretos`, solo en este computador), con el
//! servicio y la cuenta de siempre («Alcancía · conexiones» / el id del conector): quien ya conectó una cuenta no tiene que volver a
//! hacerlo. Nunca van a ~/Alcancia ni a ningún archivo: llegan a bin/sincronizar.py por la entrada estándar (`Opciones.secreto`) y
//! una llave nueva vuelve por su salida estándar («CREDENCIAL {json}»).

use crate::cartolas::EXTENSIONES;
use crate::pieza::host::Host;
use crate::pieza::procesador::Opciones;
use crate::pieza::sistema::Secretos;
use crate::pieza::vigilante::Vigilante;
use crate::{enviar_estado, es_si, responder};
use serde_json::{json, Value};
use std::collections::HashSet;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::Duration;

/// Un conector pide varias páginas a su API (cada pedido tiene su tope en bin/red.py).
const LIMITE: u64 = 600;
const CADA: Duration = Duration::from_secs(6 * 3600);

static EN_CURSO: Mutex<Option<HashSet<String>>> = Mutex::new(None);

fn llavero(h: &Host) -> Secretos {
    h.secretos(Some("conexiones"))
}

pub fn valido(id: &str) -> String {
    id.chars().filter(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || *c == '_').take(40).collect()
}

/// «CREDENCIAL {json}» en la salida estándar del script: la llave nueva (ya como JSON de texto, tal cual se guarda).
pub fn credencial(salida: &str) -> Option<String> {
    let linea = salida.lines().rev().find(|l| l.starts_with("CREDENCIAL "))?;
    let texto = &linea["CREDENCIAL ".len()..];
    serde_json::from_str::<Value>(texto).ok().filter(Value::is_object).map(|_| texto.to_string())
}

pub fn registrar(host: &Host) {
    host.registrar("conectar", |d, h, _| {
        let id = valido(d["conector"].as_str().unwrap_or(""));
        let mut r = conectar(h, &id, &d["campos"]);
        if let Some(o) = r.as_object_mut() {
            o.insert("conector".into(), json!(id));
        }
        responder(h, "conectado", r.clone());
        enviar_estado(h, None);
        if r["ok"] == true {
            traer(h, &id, false);
        }
    });
    host.registrar("sincronizar", |d, h, _| traer(h, &valido(d["conector"].as_str().unwrap_or("")), true));
    host.registrar("desconectar", |d, h, _| {
        let id = valido(d["conector"].as_str().unwrap_or(""));
        llavero(h).borrar(&id);
        h.procesador.con_entrada("guardar.py", &["desconectar".into()], json!({"conector": id}), Opciones { limite: Some(30), ..Default::default() });
        enviar_estado(h, None);
    });
    host.registrar("vigilar", |d, h, _| descargas_activar(h, es_si(&d["activo"])));
}

fn conectar(h: &Host, id: &str, campos: &Value) -> Value {
    let limpio: serde_json::Map<String, Value> =
        campos.as_object().map(|o| o.iter().filter(|(_, v)| v.is_string()).map(|(k, v)| (k.clone(), v.clone())).collect()).unwrap_or_default();
    if id.is_empty() {
        return json!({"ok": false, "error": h.t("No se pudo conectar.")});
    }
    let json = Value::Object(limpio).to_string();
    let res = h.procesador.correr("sincronizar.py", &["probar".into(), id.into()], Opciones { secreto: Some(json.clone()), limite: Some(120), ..Default::default() });
    if res.respuesta["ok"] != true {
        return res.respuesta;
    }
    // Si el servicio canjeó la llave por una definitiva, se guarda esa.
    let cred = credencial(&res.salida_estandar).unwrap_or(json);
    if !llavero(h).guardar(id, &cred) {
        return json!({"ok": false, "error": h.t("No pude guardar la llave en el Llavero.")});
    }
    res.respuesta
}

pub fn traer(h: &Host, id: &str, manual: bool) {
    {
        let mut g = EN_CURSO.lock().unwrap_or_else(|e| e.into_inner());
        let en = g.get_or_insert_with(HashSet::new);
        if id.is_empty() || en.contains(id) {
            return;
        }
        let Some(cred) = llavero(h).leer(id) else {
            drop(g);
            return responder(h, "sincronizado", json!({"conector": id, "ok": false, "error": h.t("Vuelve a conectar esta cuenta.")}));
        };
        en.insert(id.to_string());
        drop(g);
        let res = h.procesador.correr("sincronizar.py", &["traer".into(), id.into()], Opciones { secreto: Some(cred), limite: Some(LIMITE), ..Default::default() });
        if let Ok(mut g) = EN_CURSO.lock() {
            if let Some(en) = g.as_mut() {
                en.remove(id);
            }
        }
        if let Some(nueva) = credencial(&res.salida_estandar) {
            llavero(h).guardar(id, &nueva);
        }
        let mut r = res.respuesta;
        if let Some(o) = r.as_object_mut() {
            o.insert("conector".into(), json!(id));
            o.insert("manual".into(), json!(manual));
        }
        responder(h, "sincronizado", r);
        enviar_estado(h, None);
    }
}

/// Los conectores que tienen llave guardada: los de bin/conectores que el llavero conoce.
fn conectados(h: &Host) -> Vec<String> {
    let mut ids: Vec<String> = std::fs::read_dir(h.recursos.join("bin").join("conectores"))
        .map(|l| {
            l.filter_map(|x| x.ok())
                .filter_map(|x| x.file_name().to_string_lossy().strip_suffix(".py").map(String::from))
                .filter(|n| !n.starts_with('_') && valido(n) == *n)
                .collect()
        })
        .unwrap_or_default();
    ids.sort();
    let l = llavero(h);
    ids.into_iter().filter(|id| l.leer(id).is_some()).collect()
}

/// Al abrir la app y luego cada 6 horas (los servicios ponen límites de consultas; más seguido no aporta).
pub fn revisar_cada_rato(h: &Host) {
    let h = h.clone();
    std::thread::spawn(move || {
        std::thread::sleep(Duration::from_secs(8));
        loop {
            for id in conectados(&h) {
                traer(&h, &id, false);
            }
            std::thread::sleep(CADA);
        }
    });
}

// ───────────── Carpeta vigilada: las cartolas que la persona descarga se agregan solas (bin/vigilar.py decide qué importar) ─────

/// El vigilante de la pieza «host-tauri» (FSEvents, inotify…) sobre ~/Downloads: cuando la carpeta queda quieta 5 segundos,
/// bin/vigilar.py importa lo nuevo que reconozca una receta. Nunca borra ni mueve nada.
static VIGILANTE: OnceLock<Vigilante> = OnceLock::new();
static REVISANDO: AtomicBool = AtomicBool::new(false);
static OTRA_VEZ: AtomicBool = AtomicBool::new(false);

fn descargas() -> PathBuf {
    crate::pieza::enchufe::casa().join("Downloads")
}

fn vigilante(h: &Host) -> &'static Vigilante {
    VIGILANTE.get_or_init(|| {
        let v = Vigilante::nuevo(Some(EXTENSIONES.iter().map(|e| format!(".{e}")).collect()), Some(Duration::from_secs(5)), None);
        let h = h.clone();
        *v.al_cambiar.lock().expect("vigilante") = Some(Arc::new(move |_: &std::path::Path| revisar_descargas(&h)));
        v
    })
}

fn descargas_activar(h: &Host, si: bool) {
    h.config.guardar(&json!({"vigilar": si}), false);
    if si {
        h.procesador.correr_json("vigilar.py", &["activar".into()], Opciones { limite: Some(30), ..Default::default() });
        descargas_empezar(h);
    } else {
        vigilante(h).detener();
    }
}

pub fn descargas_empezar(h: &Host) {
    let v = vigilante(h);
    v.detener();
    if h.config.leer().get("vigilar") != Some(&Value::Bool(true)) || !descargas().is_dir() {
        return;
    }
    v.empezar(&descargas());
    let h = h.clone();
    std::thread::spawn(move || revisar_descargas(&h));
}

fn revisar_descargas(h: &Host) {
    if REVISANDO.swap(true, Ordering::SeqCst) {
        OTRA_VEZ.store(true, Ordering::SeqCst);
        return;
    }
    loop {
        let r = h.procesador.correr_json("vigilar.py", &[descargas().to_string_lossy().into_owned()], Opciones { limite: Some(1800), ..Default::default() });
        let importados = r["importados"].as_array().map(|a| !a.is_empty()).unwrap_or(false);
        let sin_receta = r["sin_receta"].as_array().map(|a| !a.is_empty()).unwrap_or(false);
        if importados || sin_receta {
            responder(h, "importadoSolo", r);
            enviar_estado(h, None);
            if importados {
                if let Some(w) = h.ventana().filter(|w| !w.is_focused().unwrap_or(true)) {
                    let _ = w.request_user_attention(Some(tauri::UserAttentionType::Informational));
                }
            }
        }
        if !OTRA_VEZ.swap(false, Ordering::SeqCst) {
            break;
        }
    }
    REVISANDO.store(false, Ordering::SeqCst);
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn credencial_de_la_salida() {
        assert_eq!(credencial("algo\nCREDENCIAL {\"token\":\"x\"}\n").as_deref(), Some("{\"token\":\"x\"}"));
        assert_eq!(credencial("CREDENCIAL {\"a\":1}\nCREDENCIAL {\"a\":2}").as_deref(), Some("{\"a\":2}"));
        assert!(credencial("CREDENCIAL [1]").is_none());
        assert!(credencial("CREDENCIAL no").is_none());
        assert!(credencial("nada").is_none());
    }

    #[test]
    fn ids_de_conector() {
        assert_eq!(valido("mercado_pago"), "mercado_pago");
        assert_eq!(valido("../Up;rm"), "prm");
    }
}
