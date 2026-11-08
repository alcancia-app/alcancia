//! Cartolas: elegir el archivo, leer una muestra, aprender la receta e importar (con su avance). Lo mismo que hacía Cartolas.swift.
//!
//! Estas acciones no se declaran en acciones.json porque trabajan con un archivo de la persona fuera de la carpeta de datos (una
//! ruta absoluta que la interfaz nunca puede inventar): solo sirve la última cartola que la persona eligió en el diálogo del sistema.

use crate::pieza::host::Host;
use crate::pieza::procesador::Opciones;
use crate::{enviar_estado, es_si, responder};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

pub const EXTENSIONES: [&str; 9] = ["csv", "tsv", "txt", "xlsx", "pdf", "ofx", "qfx", "qif", "xml"];

/// La última cartola que eligió la persona: la única ruta que se acepta de vuelta.
static ELEGIDA: Mutex<Option<PathBuf>> = Mutex::new(None);

fn no_pude(h: &Host) -> Value {
    json!({"ok": false, "error": h.t("No pude leer el archivo.")})
}

/// La ruta que manda la interfaz sirve solo si es la cartola que la persona eligió y todavía se puede leer.
pub fn valida(d: &Value) -> Option<String> {
    let e = ELEGIDA.lock().ok()?.clone()?;
    let ruta = d["ruta"].as_str()?;
    (Path::new(ruta) == e && std::fs::File::open(&e).is_ok()).then(|| ruta.to_string())
}

pub fn registrar(host: &Host) {
    host.registrar("elegirCartola", |_, h, _| {
        let titulo = h.t("Elige la cartola que descargaste de tu banco o billetera (CSV, Excel, PDF, OFX, QIF o CAMT.053)");
        let Some(u) = h.dialogo_archivos(Some(titulo), &EXTENSIONES, false, None).into_iter().next() else { return };
        if let Ok(mut g) = ELEGIDA.lock() {
            *g = Some(u.clone());
        }
        let nombre = u.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
        responder(h, "cartolaElegida", json!({"ruta": u.to_string_lossy(), "nombre": nombre}));
    });
    host.registrar("vistaCartola", |d, h, _| {
        let Some(ruta) = valida(&d) else { return responder(h, "vistaLista", no_pude(h)) };
        let r = h.procesador.correr_json("importar.py", &["vista".into(), ruta], Opciones { limite: Some(120), ..Default::default() });
        responder(h, "vistaLista", r);
    });
    host.registrar("aprenderReceta", |d, h, _| {
        let Some(ruta) = valida(&d) else { return responder(h, "recetaAprendida", no_pude(h)) };
        let pais: String = d["pais"].as_str().unwrap_or("CL").chars().filter(|c| c.is_ascii_alphabetic()).take(2).collect::<String>().to_uppercase();
        let pais = if pais.len() == 2 { pais } else { "CL".into() };
        // La IA de la persona propone la receta (receta_ia.py la valida y la prueba con el mismo archivo).
        let r = h.procesador.correr_json("receta_ia.py", &[ruta, pais], Opciones { limite: Some(600), ..Default::default() });
        responder(h, "recetaAprendida", r);
    });
    host.registrar("importar", |d, h, _| {
        let Some(ruta) = valida(&d) else { return responder(h, "importado", no_pude(h)) };
        let receta: String = d["receta"].as_str().unwrap_or("").chars().filter(|c| c.is_alphanumeric() || *c == '-').take(80).collect();
        let ia = if es_si(&d["ia"]) { "1" } else { "0" };
        let estado = h.datos.join("estado.json");
        let _ = std::fs::remove_file(&estado);
        // Mientras se importa, el avance (bin/importar.py lo deja en ~/Alcancia/.alcancia/estado.json) llega cada medio segundo.
        let sigue = Arc::new(AtomicBool::new(true));
        let (s2, h2) = (sigue.clone(), h.clone());
        std::thread::spawn(move || {
            while s2.load(Ordering::SeqCst) {
                std::thread::sleep(Duration::from_millis(500));
                if !s2.load(Ordering::SeqCst) {
                    break;
                }
                if let Some(x) = crate::pieza::enchufe::leer_json(&estado, 1024 * 1024).filter(|x| x.as_object().is_some_and(|o| !o.is_empty())) {
                    responder(&h2, "importarProgreso", x);
                }
            }
        });
        // Con la IA completando categorías puede tardar: hasta una hora. Mientras corre, actualizar o salir esperan (el host).
        let r = h.procesador.correr_json("importar.py", &["guardar".into(), ruta, receta, ia.into()], Opciones { limite: Some(3600), ..Default::default() });
        sigue.store(false, Ordering::SeqCst);
        responder(h, "importado", r);
        enviar_estado(h, None);
    });
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn solo_la_cartola_elegida() {
        let dir = std::env::temp_dir().join(format!("alcancia-cartola-{}", crate::pieza::enchufe::aleatorio_hex(4)));
        std::fs::create_dir_all(&dir).unwrap();
        let elegida = dir.join("cartola.csv");
        std::fs::write(&elegida, "fecha,monto\n").unwrap();
        assert!(valida(&json!({"ruta": elegida.to_string_lossy()})).is_none(), "nada elegido todavía");
        *ELEGIDA.lock().unwrap() = Some(elegida.clone());
        assert_eq!(valida(&json!({"ruta": elegida.to_string_lossy()})).as_deref(), elegida.to_str());
        assert!(valida(&json!({"ruta": "/etc/passwd"})).is_none());
        assert!(valida(&json!({"ruta": 3})).is_none());
        std::fs::remove_dir_all(dir).unwrap();
        assert!(valida(&json!({"ruta": elegida.to_string_lossy()})).is_none(), "ya no se puede leer");
    }
}
