// Alcancía para Mac (y Windows y Linux cuando lleguen), sobre la pieza «host-tauri» (src/pieza/): la ventana con la interfaz de
// ui/, el puente con sus guardas (la ventana nunca sale de ui/ y un enlace https va al navegador), config e idioma desde app.json,
// menús en el idioma elegido, apariencia que sigue config.tema, scripts de bin/ con límite de tiempo y las acciones declaradas en
// acciones.json (probarIA, guardarReceta, categoria, categoriaNueva, regla, presupuesto, saldo, chat, pedirConsejos, mcpConectar:
// solo corren un script, con sus datos validados). Los datos de la persona viven en ~/Alcancia, fuera de la app (app.json → datos):
// actualizar nunca borra nada.
//
// Aquí queda lo propio de Alcancía: las cartolas (cartolas.rs), las conexiones con la llave en el llavero del sistema y la carpeta
// vigilada en Descargas (conexiones.rs), los avisos de compromisos (avisos.rs), la copia para el celular (celular.rs) y los
// ajustes con forma propia (`inicio_mes`, `uf`). Reemplaza a app/Sources/Alcancia (Swift).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod pieza;
#[path = "pieza/actualizaciones.rs"]
mod actualizaciones;
mod avisos;
mod cartolas;
mod celular;
mod conexiones;

use pieza::host::{arrancar, Host, ItemMenu, MenuPropio, Opciones, Ventana};
use pieza::procesador::Opciones as Correr;
use serde_json::{json, Map, Value};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

/// ~/Alcancia: los datos de la persona (la carpeta interna, ~/Alcancia/.alcancia, es `host.datos`).
pub fn base(h: &Host) -> PathBuf {
    h.datos.parent().map(PathBuf::from).unwrap_or_else(|| h.datos.clone())
}

/// Algo que no se pudo guardar: va en el próximo estado y lo muestra la interfaz.
static AVISO: Mutex<Option<String>> = Mutex::new(None);

/// Manda el estado (y con él la copia para el celular, si toca), con un aviso si hace falta.
pub fn enviar_estado(h: &Host, aviso: Option<String>) {
    if let Some(a) = aviso.filter(|a| !a.is_empty()) {
        if let Ok(mut g) = AVISO.lock() {
            *g = Some(a);
        }
    }
    h.enviar_estado();
}

pub fn responder(h: &Host, funcion: &str, datos: Value) {
    h.llamar(funcion, datos, None);
}

/// Hoy en la fecha de este computador (AAAA-MM-DD): los avisos y los pagos cuentan los días con ella.
pub fn hoy() -> String {
    #[cfg(unix)]
    {
        let ahora = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs() as libc::time_t).unwrap_or(0);
        let mut t: libc::tm = unsafe { std::mem::zeroed() };
        if !unsafe { libc::localtime_r(&ahora, &mut t) }.is_null() {
            return format!("{:04}-{:02}-{:02}", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday);
        }
    }
    // Sin hora local (Windows por ahora): la de UTC.
    let dias = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs() / 86400).unwrap_or(0) as i64;
    let (a, m, d) = civil(dias);
    format!("{a:04}-{m:02}-{d:02}")
}

/// Días desde 1970-01-01 → (año, mes, día) (algoritmo de Howard Hinnant).
fn civil(dias: i64) -> (i64, u32, u32) {
    let z = dias + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (yoe + era * 400 + i64::from(m <= 2), m, d)
}

/// Un `true` de verdad (no un 1 ni un "sí").
pub fn es_si(v: &Value) -> bool {
    v == &Value::Bool(true)
}

fn abrir_carpeta_datos(h: &Host) {
    let b = base(h);
    if std::fs::create_dir_all(&b).is_ok() {
        pieza::enchufe::solo_persona(&b);
    }
    let _ = opener::open(&b);
}

/// «Tu mes empieza»: {"modo": "dia" | "sueldo", "dia": 1…31}. Nada más entra en esa clave.
fn inicio_mes(v: &Value) -> Option<Value> {
    let modo = v["modo"].as_str().filter(|m| *m == "dia" || *m == "sueldo")?;
    let dia = v["dia"].as_i64().filter(|d| (1..=31).contains(d))?;
    Some(json!({"modo": modo, "dia": dia}))
}

/// «Valor de la UF hoy»: {"valor": número, "fecha": "AAAA-MM-DD", "variacion_mensual": 0…20}. Sin valor, se borra el valor.
fn uf(v: &Value) -> Option<Value> {
    let o = v.as_object()?;
    let mut limpio = Map::new();
    let fecha = o.get("fecha").and_then(Value::as_str).filter(|f| f.len() == 10 && f.chars().enumerate().all(|(i, c)| if i == 4 || i == 7 { c == '-' } else { c.is_ascii_digit() }));
    if let (Some(valor), Some(fecha)) = (o.get("valor").and_then(Value::as_f64).filter(|x| *x > 0.0 && *x < 10_000_000.0), fecha) {
        limpio.insert("valor".into(), json!(valor));
        limpio.insert("fecha".into(), json!(fecha));
    }
    if let Some(var) = o.get("variacion_mensual").and_then(Value::as_f64).filter(|x| (0.0..=20.0).contains(x)) {
        limpio.insert("variacion_mensual".into(), json!(var));
    }
    Some(Value::Object(limpio))
}

fn main() {
    let menu = MenuPropio {
        archivo: vec![ItemMenu::Nativo { etiqueta: "Abrir la carpeta de tus datos".into(), atajo: None, f: Arc::new(abrir_carpeta_datos) }],
        ..Default::default()
    };
    let op = Opciones {
        // La ventana de siempre: sin barra de título visible (la interfaz deja libre la franja de arriba en Mac; esos 30 px la
        // mueven) y su tamaño guardado con el nombre de antes, sin tilde («Alcancia»).
        ventana: Ventana {
            ancho: 1180.0,
            alto: 780.0,
            min_ancho: 820.0,
            min_alto: 560.0,
            barra_transparente: true,
            alto_franja: 30.0,
            nombre: "Alcancia".into(),
            ..Default::default()
        },
        global: Some("Alcancia".into()),
        sitio: Some("https://alcancia-app.github.io/alcancia/".into()),
        codigo: Some("https://github.com/alcancia-app/alcancia".into()),
        menu,
        // Pieza «actualizaciones»: solo los Releases de este repo (Alcancia-macOS.zip + .sha256). Nunca con algo corriendo (una
        // importación): el host espera.
        actualizaciones: actualizaciones::Actualizaciones::nuevas("alcancia-app/alcancia", "Alcancía").ok().map(|a| Arc::new(a) as _),
        ..Default::default()
    };
    arrancar(tauri::generate_context!(), op, |host| {
        host.al_estado(|mut e, h| {
            e.insert("celular".into(), celular::para_js(h));
            if let Some(a) = AVISO.lock().ok().and_then(|mut g| g.take()) {
                e.insert("aviso".into(), json!(a));
            }
            e
        });
        // «Alcancía en tu celular»: con el estado recién llegado, la interfaz arma y cifra la copia (si toca) y la devuelve.
        host.despues_del_estado(celular::despues_del_estado);
        // Lo que corre solo y puede mostrar algo o pedir un permiso del sistema (llavero, Descargas, archivos de otras IA) espera al
        // idioma elegido: el host lo llama una vez, recién entonces. Las actualizaciones las revisa el host.
        host.al_iniciar_tareas(|h| {
            conexiones::revisar_cada_rato(h);
            conexiones::descargas_empezar(h);
            avisos::revisar_cada_rato(h);
            celular::revisar_cada_rato(h);
            // Si la app cambió de lugar (o se actualizó), las IA conectadas por MCP siguen apuntando a la ruta nueva.
            let h2 = h.clone();
            std::thread::spawn(move || {
                h2.procesador.correr_json("mcp_conectar.py", &["reparar".into()], Correr { limite: Some(120), ..Default::default() });
            });
        });
        // Tocar un aviso de compromisos: la ventana adelante (el host) y la vista de Pagos.
        host.al_tocar_aviso(|_, h| responder(h, "menu", json!({"accion": "compromisos"})));

        // `config` del host más los ajustes con forma propia de Alcancía, que app.json no puede describir (son objetos): «Tu mes
        // empieza» y «Valor de la UF hoy». Python los vuelve a validar al usarlos (datos.CONFIG_OBJETOS).
        host.registrar("config", |d, h, _| {
            if let Some(v) = d.get("inicio_mes").and_then(inicio_mes) {
                h.config.poner_propia("inicio_mes", v);
            }
            if let Some(v) = d.get("uf").and_then(uf) {
                h.config.poner_propia("uf", v);
            }
            let idioma_antes = h.config.texto("idioma_ui");
            h.config_de_interfaz(&d);
            if h.config.texto("idioma_ui") != idioma_antes {
                // Las categorías base salen en el idioma nuevo.
                enviar_estado(h, None);
            }
        });
        host.registrar("abrirCarpeta", |_, h, _| abrir_carpeta_datos(h));
        host.registrar("compromiso", |d, h, _| {
            let r = h.procesador.con_entrada("guardar.py", &["compromiso".into()], d, Correr { limite: Some(60), ..Default::default() });
            if r["ok"] != true {
                return enviar_estado(h, r["error"].as_str().map(String::from));
            }
            // Primer compromiso: recién ahí se activan los avisos (si la persona no los apagó antes).
            if es_si(&r["primero"]) && !h.config.leer().contains_key("avisos") {
                avisos::activar(h, true);
            }
            enviar_estado(h, None);
            avisos::revisar(h);
        });
        host.registrar("avisos", |d, h, _| avisos::activar(h, es_si(&d["activo"])));
        cartolas::registrar(host);
        conexiones::registrar(host);
        host.registrar("celular", |d, h, _| celular::atender(h, &d));
    });
}

#[cfg(test)]
mod pruebas {
    use super::*;

    #[test]
    fn ajustes_con_forma_propia() {
        assert_eq!(inicio_mes(&json!({"modo": "sueldo", "dia": 25, "otra": 1})), Some(json!({"modo": "sueldo", "dia": 25})));
        assert_eq!(inicio_mes(&json!({"modo": "luna", "dia": 2})), None);
        assert_eq!(inicio_mes(&json!({"modo": "dia", "dia": 32})), None);
        assert_eq!(uf(&json!({"valor": 39000.5, "fecha": "2026-11-01", "variacion_mensual": 1.5})), Some(json!({"valor": 39000.5, "fecha": "2026-11-01", "variacion_mensual": 1.5})));
        assert_eq!(uf(&json!({"valor": -1, "fecha": "2026-11-01"})), Some(json!({})));
        assert_eq!(uf(&json!({"valor": 1, "fecha": "1/11/2026", "variacion_mensual": 50})), Some(json!({})));
        assert_eq!(uf(&json!("x")), None);
    }

    #[test]
    fn fechas() {
        assert_eq!(civil(0), (1970, 1, 1));
        assert_eq!(civil(20_399), (2025, 11, 7));
        assert_eq!(civil(19_782), (2024, 2, 29));
        let h = hoy();
        assert!(h.len() == 10 && &h[4..5] == "-" && &h[7..8] == "-");
    }
}
