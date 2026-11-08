//! Avisos de compromisos: notificaciones del sistema 3 días antes, el día que vence y si quedó atrasado (lo que se paga solo,
//! únicamente si no apareció el cargo). Lo mismo que hacía Avisos.swift.
//!
//! bin/compromisos.py decide qué avisar hoy (una vez cada cosa por vencimiento y como máximo un aviso por compromiso al día); aquí
//! solo se arma el texto en el idioma elegido y se muestra (pieza «host-tauri»: `Notificaciones`). El título es genérico («Pago por
//! vencer»): el nombre va solo en el cuerpo y el monto nunca. Con la pantalla bloqueada, el sistema oculta el cuerpo (en el Mac, «Mostrar
//! vistas previas: al desbloquear», lo de siempre). Nada de esto corre antes de que exista idioma (las tareas del host) ni si la
//! persona no los activó (al agregar su primer compromiso o con «Avisarme antes de que venza»).

use crate::pieza::host::Host;
use crate::pieza::procesador::Opciones;
use serde_json::{json, Value};
use std::time::Duration;

fn activos(h: &Host) -> bool {
    h.config.leer().get("avisos") == Some(&Value::Bool(true))
}

/// La persona los activa (o agrega su primer compromiso).
pub fn activar(h: &Host, si: bool) {
    h.config.guardar(&json!({"avisos": si}), false);
    if si {
        revisar(h);
    }
}

/// Al abrir (ya con idioma) y luego cada 6 horas, igual que las conexiones.
pub fn revisar_cada_rato(h: &Host) {
    let h = h.clone();
    std::thread::spawn(move || {
        std::thread::sleep(Duration::from_secs(12));
        loop {
            revisar(&h);
            std::thread::sleep(Duration::from_secs(6 * 3600));
        }
    });
}

pub fn revisar(h: &Host) {
    if !activos(h) || !h.idioma_elegido() {
        return;
    }
    let r = h.procesador.correr_json("compromisos.py", &["avisos".into(), crate::hoy()], Opciones { limite: Some(60), ..Default::default() });
    for a in r["avisos"].as_array().into_iter().flatten() {
        let (titulo, cuerpo) = texto(h, a);
        h.notificaciones().mostrar(&id(a), &titulo, &cuerpo, false);
    }
}

/// Para saber cuál tocó la persona (solo letras, números y guiones; hasta 60).
pub fn id(a: &Value) -> String {
    let s = ["alcancia", a["id"].as_str().unwrap_or(""), a["vence"].as_str().unwrap_or(""), a["tipo"].as_str().unwrap_or("")].join("-");
    s.chars().filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_').take(60).collect()
}

/// El título nunca lleva el nombre (puede ser el de otra persona, p. ej. una transferencia); el monto no va en ningún lado.
pub fn texto(h: &Host, a: &Value) -> (String, String) {
    let nombre = a["nombre"].as_str().unwrap_or("");
    let dias = a["dias"].as_i64().unwrap_or(0);
    let poner = |p: &str| h.t(p).replace("{c}", nombre).replace("{n}", &dias.to_string());
    match a["tipo"].as_str().unwrap_or("") {
        "hoy" => (poner("Un pago vence hoy"), format!("{} {}", poner("{c} vence hoy."), poner("Si ya lo pagaste, márcalo en Alcancía."))),
        "atrasado" => (poner("Tienes un pago atrasado"), format!("{} {}", poner("{c} está atrasado."), poner("Si ya lo pagaste, márcalo en Alcancía."))),
        // Se paga solo, pasaron los días de gracia y el cargo no aparece.
        "sin_cargo" => (
            poner("Revisa un pago automático"),
            format!("{} {}", poner("No vimos el cargo de {c}."), poner("Puede que el cobro haya fallado: revísalo en Alcancía.")),
        ),
        _ => (poner("Pago por vencer"), if dias == 1 { poner("{c} vence mañana.") } else { poner("{c} vence en {n} días.") }),
    }
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn ids_de_avisos() {
        assert_eq!(id(&json!({"id": "netflix", "vence": "2026-11-10", "tipo": "hoy"})), "alcancia-netflix-2026-11-10-hoy");
        assert_eq!(id(&json!({"id": "x y/z", "tipo": "<b>"})), "alcancia-xyz--b");
        assert!(id(&json!({"id": "a".repeat(100)})).len() <= 60);
    }
}
