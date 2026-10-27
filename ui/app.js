// Interfaz de Alcancía: la misma en Mac (WKWebView), Windows y Linux (Electron) y en el navegador (vista previa con demo.json).
// La app manda el estado con window.Alcancia.estado(json); la interfaz pide cosas con host.enviar(accion, datos).
// Todo el dinero y los textos de la persona se muestran con esc() y data-sin-traducir.
(() => {
  "use strict";
  const HOST = window.ALCANCIA_HOST || "web";
  document.documentElement.dataset.host = HOST;
  const E = {
    vista: "resumen", mes: "", hoy: "", config: {}, ias: [], movimientos: [], categorias: [], presupuesto: { mensual: {} }, reglas: [],
    consejos: [], cuentas: [], version: "", carpeta: "", actualizacion: { hay: false }, filtro: { texto: "", categoria: "" },
    aprender: null, presEdit: null, importar: null, bv: null, bvCerrada: false, ajustes: false, probando: {}, resultadoIA: {},
    consejoSel: null, pidiendoConsejos: false, errorConsejos: "", act: null, buscando: null, idioma: "es", textos: {},
    conectores: [], conexiones: {}, vigilar: { activo: false, recientes: [] }, conectar: null, sincronizando: {}, iaExterna: [], mcpOcupado: {}, mcpError: {},
    histCat: null, compromisos: { compromisos: [], descartados: [] }, sugerencias: [], compEdit: null, sugTodas: false,
    chat: { mensajes: [], texto: "", pensando: false, bajar: false, confirmarBorrar: false },
    cifra: null, agregar: null, movVer: null, picker: null, ordenar: { i: 0, buscar: "", nueva: null }, saldoEdit: null, saldoAviso: null, reglasNo: [], compararAbierto: false,
  };
  const ENLACES = { sitio: "https://alcancia-app.github.io/alcancia/", codigo: "https://github.com/alcancia-app/alcancia",
    comunidad: "https://github.com/alcancia-app/alcancia/discussions", guiaIA: "https://alcancia-app.github.io/alcancia/ia.html",
    nuevaReceta: "https://github.com/alcancia-app/alcancia-catalogo/issues/new" };
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ───────────── Puente con la app ─────────────
  const host = {
    enviar(accion, datos = {}) {
      const msg = { accion, datos };
      if (window.webkit?.messageHandlers?.alcancia) return window.webkit.messageHandlers.alcancia.postMessage(msg);
      if (window.alcanciaEscritorio) return window.alcanciaEscritorio.enviar(msg);
      return simular(accion, datos);
    },
  };

  // ───────────── Idiomas (las claves son el texto en español) ─────────────
  function tr(t) {
    if (E.idioma === "es" || !t) return t;
    const limpio = String(t).replace(/\s+/g, " ").trim();
    if (!limpio) return t;
    if (E.textos[limpio]) return t.replace(limpio, E.textos[limpio]);
    const numeros = limpio.match(/\d+/g);
    if (numeros) {
      const plantilla = E.textos[limpio.replace(/\d+/g, "{n}")];
      if (plantilla) { let i = 0; return t.replace(limpio, plantilla.replace(/\{n\}/g, () => numeros[i++] ?? "")); }
    }
    if (window._faltantes && /\p{L}{2}/u.test(limpio)) window._faltantes.add(limpio);
    return t;
  }
  /** Frase completa con marcadores ({x}, {n}, {ia}…): se traduce entera y después se ponen los valores (ya escapados o en HTML).
   *  El resultado va dentro de un elemento con data-sin-traducir (ya está traducido). */
  function T(plantilla, valores = {}) {
    let t = plantilla;
    if (E.idioma !== "es") {
      if (E.textos[plantilla]) t = E.textos[plantilla];
      else if (window._faltantes) window._faltantes.add(plantilla);
    }
    t = esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    for (const [k, v] of Object.entries(valores)) t = t.split(`{${k}}`).join(String(v));
    return t;
  }
  const frase = (plantilla, valores, etiqueta = "span") => `<${etiqueta} data-sin-traducir>${T(plantilla, valores)}</${etiqueta}>`;
  function traducirDOM(raiz) {
    if (E.idioma === "es") return;
    const w = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
    const nodos = []; let n; while ((n = w.nextNode())) nodos.push(n);
    for (const t of nodos) {
      const el = t.parentElement;
      if (!el || el.closest("[data-sin-traducir], script, style") || !/\p{L}/u.test(t.nodeValue)) continue;
      const v = tr(t.nodeValue); if (v !== t.nodeValue) t.nodeValue = v;
    }
    for (const el of raiz.querySelectorAll("[title],[aria-label],[placeholder]")) {
      if (el.closest("[data-sin-traducir]")) continue;
      for (const a of ["title", "aria-label", "placeholder"]) { const v = el.getAttribute(a); if (v) el.setAttribute(a, tr(v)); }
    }
  }
  /** Idioma del equipo («es» o «en»): el que se sugiere en el primer paso. */
  const idiomaDelSistema = () => ((navigator.language || "es").toLowerCase().startsWith("es") ? "es" : "en");
  async function cargarIdioma() {
    const pedido = new URLSearchParams(location.search).get("idioma");
    const codigo = pedido || E.config.idioma_ui || idiomaDelSistema();
    if (codigo === E.idioma && (codigo === "es" || Object.keys(E.textos).length)) return;
    E.idioma = codigo;
    E.textos = {};
    if (codigo !== "es") {
      try { E.textos = (await (await fetch(`idiomas/${codigo}.json`)).json()).textos || {}; } catch { E.idioma = "es"; }
    }
    document.documentElement.lang = E.idioma;
  }

  // ───────────── Dinero y fechas ─────────────
  const LOCALES = { NL: "nl-NL", BE: "nl-BE", IE: "en-IE", AT: "de-AT", FI: "fi-FI", SE: "sv-SE", DK: "da-DK", NO: "nb-NO", PL: "pl-PL", AU: "en-AU", CL: "es-CL", AR: "es-AR", MX: "es-MX", CO: "es-CO", PE: "es-PE", UY: "es-UY", ES: "es-ES", US: "en-US", BR: "pt-BR", EC: "es-EC", BO: "es-BO", PY: "es-PY", VE: "es-VE", GB: "en-GB", CA: "en-CA", DE: "de-DE", FR: "fr-FR", IT: "it-IT", PT: "pt-PT" };
  const PAISES = [["CL", "Chile", "CLP"], ["AR", "Argentina", "ARS"], ["MX", "México", "MXN"], ["CO", "Colombia", "COP"], ["PE", "Perú", "PEN"],
    ["UY", "Uruguay", "UYU"], ["EC", "Ecuador", "USD"], ["BO", "Bolivia", "BOB"], ["PY", "Paraguay", "PYG"], ["ES", "España", "EUR"],
    ["US", "Estados Unidos", "USD"], ["BR", "Brasil", "BRL"], ["GB", "Reino Unido", "GBP"], ["CA", "Canadá", "CAD"], ["DE", "Alemania", "EUR"],
    ["FR", "Francia", "EUR"], ["IT", "Italia", "EUR"], ["PT", "Portugal", "EUR"], ["NL", "Países Bajos", "EUR"], ["BE", "Bélgica", "EUR"],
    ["IE", "Irlanda", "EUR"], ["AT", "Austria", "EUR"], ["FI", "Finlandia", "EUR"], ["SE", "Suecia", "SEK"], ["DK", "Dinamarca", "DKK"],
    ["NO", "Noruega", "NOK"], ["PL", "Polonia", "PLN"], ["AU", "Australia", "AUD"]];
  const MONEDAS = ["CLP", "ARS", "MXN", "COP", "PEN", "UYU", "BOB", "PYG", "BRL", "USD", "EUR", "GBP", "CAD", "AUD", "SEK", "DKK", "NOK", "PLN"];
  const locNumeros = () => LOCALES[E.config.pais] || "es-CL";
  const locFechas = () => (E.idioma === "es" ? locNumeros().startsWith("es") ? locNumeros() : "es-CL" : "en-US");
  function dinero(v, moneda = E.presupuesto.moneda || E.config.moneda || "CLP", signo = false) {
    const n = Number(v) || 0;
    let t;
    try {
      t = new Intl.NumberFormat(locNumeros(), { style: "currency", currency: moneda, minimumFractionDigits: 0, maximumFractionDigits: Number.isInteger(n) ? 0 : 2 }).format(Math.abs(n));
    } catch { t = Math.abs(n).toLocaleString(locNumeros()); }
    return (n < 0 ? "−" : signo && n > 0 ? "+" : "") + t;
  }
  /** Monto corto para las barras («$1,2 M», «$350 mil»). */
  function dineroCorto(v, moneda = E.presupuesto.moneda || E.config.moneda || "CLP") {
    try { return new Intl.NumberFormat(locNumeros(), { style: "currency", currency: moneda, notation: "compact", maximumSignificantDigits: 2 }).format(Number(v) || 0); }
    catch { return dinero(v, moneda); }
  }
  const numeroPlano = (v) => (Number(v) ? Math.round(Number(v)).toLocaleString(locNumeros()) : "");
  const primeraMayuscula = (t) => t.charAt(0).toUpperCase() + t.slice(1);
  function nombreMes(mes) {
    const [a, m] = mes.split("-").map(Number);
    return primeraMayuscula(new Date(a, m - 1, 1).toLocaleDateString(locFechas(), { month: "long", year: "numeric" }));
  }
  function nombreDia(fecha) {
    const [a, m, d] = fecha.split("-").map(Number);
    return new Date(a, m - 1, d).toLocaleDateString(locFechas(), { weekday: "long", day: "numeric", month: "long" });
  }
  function mesCorto(mes) {
    const [a, m] = mes.split("-").map(Number);
    return new Date(a, m - 1, 1).toLocaleDateString(locFechas(), { month: "short" }).replace(".", "");
  }
  const mesDe = (f) => f.slice(0, 7);
  function sumarMes(mes, n) {
    let [a, m] = mes.split("-").map(Number);
    m += n; while (m < 1) { m += 12; a--; } while (m > 12) { m -= 12; a++; }
    return `${a}-${String(m).padStart(2, "0")}`;
  }

  // ───────────── Lógica (la misma que bin/resumen.py; se prueban juntas con pruebas/casos.json) ─────────────
  const diasDelMes = (mes) => { const [a, m] = mes.split("-").map(Number); return new Date(a, m, 0).getDate(); };
  function redondearArriba(v) {
    if (v <= 0) return 0;
    const paso = 10 ** Math.max(0, String(Math.trunc(v)).length - 2);
    return Math.ceil(v / paso) * paso;
  }
  // Periodos: mes calendario o de sueldo a sueldo (igual que resumen.rango en Python). `per` = {modo, dia, llegadas}.
  const diasEntre = (a, b) => Math.round((Date.UTC(+b.slice(0, 4), +b.slice(5, 7) - 1, +b.slice(8, 10)) - Date.UTC(+a.slice(0, 4), +a.slice(5, 7) - 1, +a.slice(8, 10))) / 864e5);
  const sumarDias = (f, n) => new Date(Date.UTC(+f.slice(0, 4), +f.slice(5, 7) - 1, +f.slice(8, 10) + n)).toISOString().slice(0, 10);
  const diaSueldo = (per) => (per && per.modo === "sueldo" && Number.isInteger(per.dia) && per.dia >= 1 && per.dia <= 31 ? per.dia : null);
  function inicioNominal(mes, per) {
    const d = diaSueldo(per);
    if (!d || d === 1) return `${mes}-01`;
    const base = d >= 16 ? sumarMes(mes, -1) : mes;
    return `${base}-${String(Math.min(d, diasDelMes(base))).padStart(2, "0")}`;
  }
  function inicioPeriodo(mes, per) {
    const nominal = inicioNominal(mes, per);
    if (!diaSueldo(per)) return nominal;
    let mejor = null;
    for (const f of per.llegadas || []) {
      const d = diasEntre(nominal, f);
      if (d >= -12 && d <= 7 && (!mejor || Math.abs(d) < mejor[0] || (Math.abs(d) === mejor[0] && f < mejor[1]))) mejor = [Math.abs(d), f];
    }
    if (mejor) return mejor[1];
    // Esperando el sueldo (igual que Python): pasó el día de siempre y aún no llega; el mes anterior sigue hasta 7 días.
    if (typeof per.hoy === "string") { const d = diasEntre(nominal, per.hoy); if (d >= 0 && d <= 7) return sumarDias(nominal, 8); }
    return nominal;
  }
  function rango(mes, per = null) {
    if (!diaSueldo(per)) return [`${mes}-01`, `${mes}-${String(diasDelMes(mes)).padStart(2, "0")}`];
    const inicio = inicioPeriodo(mes, per), fin = sumarDias(inicioPeriodo(sumarMes(mes, 1), per), -1);
    return [inicio, fin > inicio ? fin : inicio];
  }
  function periodoDe(fecha, per = null) {
    const m = fecha.slice(0, 7);
    if (!diaSueldo(per)) return m;
    for (const x of [m, sumarMes(m, 1), sumarMes(m, -1)]) { const [a, b] = rango(x, per); if (a <= fecha && fecha <= b) return x; }
    return m;
  }
  function periodosConDatos(movimientos, per = null, moneda = null) {
    const fechas = new Set(movimientos.filter((m) => moneda == null || (m.moneda || moneda) === moneda).map((m) => m.fecha));
    return [...new Set([...fechas].map((f) => periodoDe(f, per)))].sort();
  }
  // Cómo se pagó: compras en cuotas con crédito (igual que resumen.py).
  const enteroTexto = (v) => { const f = Number(v); return Number.isInteger(f) ? f : 0; };
  const cuotasDe = (m) => { const n = enteroTexto(m.cuotas || 0); return m.medio === "credito" && n >= 2 && n <= 72 && m.monto < 0 ? n : 0; };
  const valorCuota = (m) => { const c = Number(m.cuota) || 0; return c > 0 ? c : Math.abs(m.monto) / cuotasDe(m); };
  const fechaMasMeses = (f, n) => { const mes = sumarMes(f.slice(0, 7), n); return `${mes}-${pad2(Math.min(+f.slice(8, 10), diasDelMes(mes)))}`; };
  function cargos(m) {
    const n = cuotasDe(m);
    if (!n) return [[m.fecha, m.monto, 0, 0]];
    const c = valorCuota(m);
    return Array.from({ length: n }, (_, k) => [fechaMasMeses(m.fecha, k), -c, k + 1, n]);
  }
  function resumen(movimientos, mes, hoy, presupuesto, categorias, per = null) {
    const neutras = new Set(categorias.filter((c) => c.tipo === "neutro").map((c) => c.id));
    const deGasto = new Set(categorias.filter((c) => c.tipo === "gasto").map((c) => c.id));
    const fijas = new Set(categorias.filter((c) => c.fijo).map((c) => c.id));
    const moneda = presupuesto.moneda || "CLP";
    const [inicio, fin] = rango(mes, per);
    let delMes = [];
    for (const m of movimientos) {
      if (neutras.has(m.categoria)) continue;
      for (const [f, monto] of cargos(m)) if (inicio <= f && f <= fin) delMes.push({ ...m, fecha: f, monto });
    }
    const otras = delMes.filter((m) => (m.moneda || moneda) !== moneda).length;
    delMes = delMes.filter((m) => (m.moneda || moneda) === moneda);
    const porCat = {}, cuantos = {}, devuelto = {};
    for (const m of delMes) {
      const c = m.categoria || "";
      if (m.monto < 0) { porCat[c] = (porCat[c] || 0) - m.monto; cuantos[c] = (cuantos[c] || 0) + 1; }
      else if (m.monto > 0 && deGasto.has(c)) devuelto[c] = (devuelto[c] || 0) + m.monto;
    }
    for (const [c, v] of Object.entries(devuelto)) { porCat[c] = Math.max(0, (porCat[c] || 0) - v); if (!porCat[c] && !cuantos[c]) delete porCat[c]; }
    const gastado = Object.values(porCat).reduce((a, b) => a + b, 0);
    const ingresos = delMes.filter((m) => m.monto > 0 && !deGasto.has(m.categoria)).reduce((a, m) => a + m.monto, 0);
    const total = diasEntre(inicio, fin) + 1;
    const dia = hoy < inicio ? 0 : hoy > fin ? total : diasEntre(inicio, hoy) + 1;
    const enCurso = dia > 0 && dia < total;
    // Proyección: lo variable (3 o más gastos en el mes) sigue al mismo ritmo; lo fijo (arriendo, cuentas) y lo esporádico queda como está.
    const ritmo = (c, g) => (!fijas.has(c) && (cuantos[c] || 0) >= 3 ? g / dia * total : g);
    const proyectar = enCurso && dia >= 3;
    const proyeccion = proyectar ? Math.round(Object.entries(porCat).reduce((a, [c, g]) => a + ritmo(c, g), 0)) : null;
    const proyeccionPorCategoria = proyectar ? Object.fromEntries(Object.entries(porCat).map(([c, g]) => [c, Math.round(ritmo(c, g))])) : {};
    const mensual = presupuesto.mensual || {};
    const limite = Object.values(mensual).filter((v) => v > 0).reduce((a, b) => a + b, 0);
    const alertas = [];
    for (const [c, tope] of Object.entries(mensual)) {
      if (!(tope > 0)) continue;
      const g = porCat[c] || 0;
      if (g > tope) alertas.push({ categoria: c, tipo: "pasado", gastado: Math.round(g), tope });
      else if (enCurso && dia >= 5 && !fijas.has(c) && (cuantos[c] || 0) >= 3 && g / dia * total > tope * 1.1) {
        alertas.push({ categoria: c, tipo: "ritmo", gastado: Math.round(g), tope, proyeccion: Math.round(g / dia * total) });
      }
    }
    const ordenado = Object.fromEntries(Object.entries(porCat).sort((a, b) => b[1] - a[1]).map(([k, v]) => [k, Math.round(v)]));
    return { mes, moneda, gastado: Math.round(gastado), ingresos: Math.round(ingresos), presupuesto: limite, por_categoria: ordenado, dia,
      dias_mes: total, desde: inicio, hasta: fin, proyeccion, proyeccion_por_categoria: proyeccionPorCategoria, alertas, otras_monedas: otras, sin_categoria: cuantos[""] || 0 };
  }
  /** Los `n` meses que terminan en `mes` (igual que resumen.historia en Python): gasto total o de una categoría, con su tope. */
  function historia(movimientos, mes, hoy, presupuesto, categorias, categoria = null, n = 6, per = null) {
    const moneda = presupuesto.moneda || "CLP";
    const conDatos = new Set(periodosConDatos(movimientos, per, moneda));
    const meses = [];
    let tope = 0;
    for (let i = n - 1; i >= 0; i--) {
      const x = sumarMes(mes, -i);
      const r = resumen(movimientos, x, hoy, presupuesto, categorias, per);
      const enCurso = r.dia > 0 && r.dia < r.dias_mes;
      let gastado, proyeccion;
      if (categoria == null) { gastado = r.gastado; proyeccion = r.proyeccion; tope = r.presupuesto; }
      else {
        gastado = r.por_categoria[categoria] || 0;
        proyeccion = r.proyeccion != null ? r.proyeccion_por_categoria[categoria] || 0 : null;
        const t = (presupuesto.mensual || {})[categoria] || 0;
        tope = t > 0 ? t : 0;
      }
      meses.push({ mes: x, gastado, proyeccion: enCurso ? proyeccion : null, en_curso: enCurso, con_datos: conDatos.has(x) });
    }
    const anteriores = meses.slice(0, -1).filter((m) => m.con_datos).map((m) => m.gastado);
    const promedio = anteriores.length ? Math.round(anteriores.reduce((a, b) => a + b, 0) / anteriores.length) : null;
    return { categoria: categoria || "", moneda: presupuesto.moneda || "CLP", tope, promedio, meses };
  }
  function presupuestoSugerido(movimientos, mesesCompletos, categorias, moneda = "CLP", per = null) {
    const r = {}, rangos = mesesCompletos.map((mes) => rango(mes, per));
    for (const c of categorias.filter((x) => x.tipo === "gasto")) {
      const valores = rangos.map(([a, b]) => movimientos.filter((m) => a <= m.fecha && m.fecha <= b && m.categoria === c.id && m.monto < 0
        && (m.moneda || moneda) === moneda).reduce((a, m) => a - m.monto, 0)).sort((a, b) => a - b);
      if (!valores.length) continue;
      const mitad = Math.floor(valores.length / 2);
      const mediana = valores.length % 2 ? valores[mitad] : (valores[mitad - 1] + valores[mitad]) / 2;
      if (mediana > 0) r[c.id] = redondearArriba(mediana);
    }
    return r;
  }
  /** Lo estable de una descripción para aprender de una corrección (igual que categorizar.regla_para en Python). */
  function reglaPara(descripcion) {
    const d = String(descripcion || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toUpperCase().replace(/[*#/\\_\-]/g, " ");
    return d.split(/\s+/).filter((p) => p.length > 1 && !/\d/.test(p)).slice(0, 3).join(" ");
  }
  const normalizar = (t) => String(t || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toUpperCase().replace(/\s+/g, " ").trim();
  // Nombre legible de un comercio (solo para mostrar; lo guardado no cambia y el original se ve al tocar):
  // «DELIVERY RAPIDITO *PEDIDO» → «Delivery Rapidito», «PAGO PENDIENTE 88231» → «Pago Pendiente», «TIENDA ONLINE *AUDIFONOS» → «Tienda Online · Audifonos».
  const SUFIJOS_GENERICOS = /^(PEDIDO|COMPRA|ORDEN|ORDER|TRIP|PAGO|PAYMENT|WEB|APP|ONLINE)$/;
  const SIGLAS = new Set(["SA", "SPA", "LTDA", "EIRL", "UF", "AFP", "ISAPRE", "CLP", "USD", "TV", "PC", "BBVA", "BCI", "HSBC"]);
  const MENORES = new Set(["a", "al", "de", "del", "la", "las", "el", "los", "y", "e", "en", "por", "para", "con", "o", "of", "the", "and", "to", "at"]);
  function nombreComercio(descripcion) {
    let t = String(descripcion || "").replace(/\s+/g, " ").trim();
    if (!t) return "";
    t = t.replace(/^(PAGO|COMPRA|COMPRAS|POS|CARGO|ABONO)\s*:\s*/i, "");
    t = t.replace(/\s*\*\s*([^*]*)$/, (_, suf) => (!suf.trim() || SUFIJOS_GENERICOS.test(normalizar(suf)) ? "" : " · " + suf.trim()));
    t = t.replace(/\s*#\s*\w+/g, "").replace(/\b\d{5,}\b/g, "").replace(/[*_]+/g, " ").replace(/\s+/g, " ").replace(/[\s·:-]+$/, "").trim();
    let primera = true;
    t = t.replace(/[\p{L}\p{N}'.]+/gu, (w) => {
      const es = primera; primera = false;
      if (/\p{Ll}/u.test(w) || /\d/.test(w)) return w;
      if (SIGLAS.has(normalizar(w).replace(/\./g, ""))) return w;
      const minus = w.toLocaleLowerCase("es");
      if (!es && MENORES.has(minus)) return minus;
      return minus.charAt(0).toLocaleUpperCase("es") + minus.slice(1);
    });
    return t || String(descripcion);
  }

  // ───────────── Compromisos (lo mismo que bin/compromisos.py; se prueban juntos con pruebas/casos.json) ─────────────
  const ANTES = 10, DESPUES = 7, TOLERANCIA = 5, UF = "UF", UF_MENSUAL = 1.5, MARGEN_UF = 15;
  const dnum = (f) => Math.round(Date.UTC(+f.slice(0, 4), +f.slice(5, 7) - 1, +f.slice(8, 10)) / 864e5);
  const dfecha = (n) => new Date(n * 864e5).toISOString().slice(0, 10);
  const isoDia = (n) => ((n % 7) + 10) % 7 + 1; // el día 0 (1970-01-01) fue jueves
  const pad2 = (n) => String(n).padStart(2, "0");
  /** A 3 cifras significativas: hacia abajo (-1), arriba (1) o al más cercano (0) (igual que compromisos.redondear3). */
  function redondear3(v, hacia = 0) {
    if (v <= 0) return 0;
    const paso = 10 ** Math.max(0, String(Math.trunc(v)).length - 3), x = v / paso;
    return (hacia < 0 ? Math.floor(x) : hacia > 0 ? Math.ceil(x) : Math.floor(x + 0.5)) * paso;
  }
  function redondearAbajo(v) {
    if (v <= 0) return 0;
    const paso = 10 ** Math.max(0, String(Math.trunc(v)).length - 2);
    return Math.floor(v / paso) * paso;
  }
  function* fechasDe(c, inicio, fin) {
    const f = c.frecuencia;
    if (f === "mensual") {
      let [a, m] = dfecha(inicio).slice(0, 7).split("-").map(Number);
      for (;;) {
        const mes = `${a}-${pad2(m)}`, v = `${mes}-${pad2(Math.min(c.dia, diasDelMes(mes)))}`;
        if (dnum(v) > fin) return;
        if (dnum(v) >= inicio) yield [mes, v];
        if (m === 12) { a++; m = 1; } else m++;
      }
    } else if (f === "semanal") {
      for (let n = inicio + (((c.dia - isoDia(inicio)) % 7) + 7) % 7; n <= fin; n += 7) yield [dfecha(n), dfecha(n)];
    } else if (f === "anual") {
      for (let a = +dfecha(inicio).slice(0, 4); a <= +dfecha(fin).slice(0, 4); a++) {
        const mes = `${a}-${c.fecha.slice(5, 7)}`, v = `${mes}-${pad2(Math.min(+c.fecha.slice(8, 10), diasDelMes(mes)))}`;
        if (dnum(v) >= inicio && dnum(v) <= fin) yield [String(a), v];
      }
    } else if (dnum(c.fecha) >= inicio && dnum(c.fecha) <= fin) yield [c.fecha, c.fecha];
  }
  function vencimientos(c, hasta) {
    let fin = dnum(hasta);
    if (c.fecha_fin) fin = Math.min(fin, dnum(c.fecha_fin));
    const maximo = c.cuotas_total ? c.cuotas_total - (c.cuotas_pagadas || 0) : null;
    const r = []; let n = 0;
    for (const [periodo, v] of fechasDe(c, dnum(c.desde) - 31, fin)) {
      if (v >= c.desde) { if (maximo != null && n >= maximo) break; n++; }
      r.push({ periodo, vence: v, n: v >= c.desde ? n : 0 });
    }
    return r;
  }
  /** [mín, máx] de un compromiso aproximado que no es en UF (igual que compromisos.rango_aprox). */
  function rangoAprox(c) {
    const a = c.aproximado;
    if (!a || c.moneda === UF) return null;
    if (a.min != null) return [a.min, a.max];
    const v = a.variacion / 100;
    return [redondear3(c.monto * (1 - v), -1), redondear3(c.monto * (1 + v), 1)];
  }
  function rangoUF(c, valor, extra) {
    const a = c.aproximado || {}, [lo, hi] = a.min != null ? [a.min, a.max] : [c.monto, c.monto];
    const v = (extra + (a.variacion || 0)) / 100;
    return [lo * valor * (1 - v), hi * valor * (1 + v)];
  }
  function coincide(m, c, moneda, uf = null) {
    const monto = m.monto;
    if (monto === 0 || (monto < 0) !== (c.signo === "gasto")) return false;
    if (m.categoria === "transferencia" && c.tipo !== "transferencia") return false; // entre tus propias cuentas: nunca es el pago de un compromiso
    const palabras = (c.buscar || []).map(normalizar).filter(Boolean), a = Math.abs(monto);
    if (c.moneda === UF) {
      if ((m.moneda || moneda) !== moneda || (!palabras.length && !uf)) return false;
      if (uf) { const [lo, hi] = rangoUF(c, uf, MARGEN_UF); if (!(lo - 1e-9 <= a && a <= hi + 1e-9)) return false; if (!palabras.length) return true; }
    } else {
      if ((m.moneda || moneda) !== c.moneda) return false;
      const dif = Math.abs(a - c.monto), r = rangoAprox(c), enRango = r != null && r[0] - 1e-9 <= a && a <= r[1] + 1e-9;
      if (!palabras.length) return dif < 0.005;
      if (dif > c.monto * (c.tolerancia ?? TOLERANCIA) / 100 + 1e-9 && !enRango) return false;
    }
    const d = normalizar(m.descripcion);
    return palabras.some((p) => d.includes(p));
  }
  // Interés por mora (igual que compromisos.py): un pago atrasado puede venir más alto (hasta +30 %) y traer un cargo aparte.
  const MORA_MAX = 30, ATRASO_MAX = 20;
  function tope(c, uf) {
    if (c.moneda === UF) { if (!uf) return null; const hi = rangoUF(c, uf, MARGEN_UF)[1]; return [hi, hi]; }
    const r = rangoAprox(c), esperado = r ? r[1] : c.monto;
    return [esperado, Math.max(esperado, c.monto * (1 + (c.tolerancia ?? TOLERANCIA) / 100))];
  }
  function coincideTarde(m, c, moneda, uf = null) {
    if (m.monto >= 0 || c.signo !== "gasto" || (m.categoria === "transferencia" && c.tipo !== "transferencia")) return false;
    const palabras = (c.buscar || []).map(normalizar).filter(Boolean), t = tope(c, uf);
    if (!palabras.length || !t || (m.moneda || moneda) !== (c.moneda === UF ? moneda : c.moneda)) return false;
    if (!(t[1] + 1e-9 < -m.monto && -m.monto <= t[1] * (1 + MORA_MAX / 100) + 1e-9)) return false;
    const d = normalizar(m.descripcion);
    return palabras.some((p) => d.includes(p));
  }
  const sinPuntos = (t) => normalizar(String(t || "").replace(/[.\-_/]/g, " "));
  const escRe = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const esMora = (m, palabras) => { const d = sinPuntos(m.descripcion); return palabras.some((p) => new RegExp(`(?<![A-Z0-9])${escRe(sinPuntos(p))}(?![A-Z0-9])`).test(d)); };
  function moras(ocs, pagos, movimientos, moneda, uf, palabras, usados) {
    const porId = new Map(movimientos.map((m) => [m.id, m]));
    const cargos = palabras.length ? movimientos.filter((m) => m.monto < 0 && !usados.has(m.id) && esMora(m, palabras))
      .sort((a, b) => (a.fecha !== b.fecha ? (a.fecha < b.fecha ? -1 : 1) : a.id < b.id ? -1 : a.id > b.id ? 1 : 0)) : [];
    const tomados = new Set();
    for (const [c, o] of ocs) {
      const p = pagos[`${c.id}|${o.periodo}`];
      if (!p || p.como !== "automatico" || c.signo !== "gasto") continue;
      const dias = dnum(p.fecha) - dnum(o.vence);
      if (dias <= 0) continue;
      const m = porId.get(p.movimiento), t = tope(c, uf);
      let extra = t && m && -m.monto > t[1] + 1e-9 ? -m.monto - t[0] : 0;
      const mon = m ? m.moneda || moneda : moneda;
      const cerca = cargos.filter((x) => !tomados.has(x.id) && Math.abs(dnum(x.fecha) - dnum(p.fecha)) <= 7 && (x.moneda || moneda) === mon);
      const lejos = (x) => Math.abs(dnum(x.fecha) - dnum(p.fecha));
      const cargo = cerca.sort((a, b) => lejos(a) - lejos(b) || (a.fecha !== b.fecha ? (a.fecha < b.fecha ? -1 : 1) : a.id < b.id ? -1 : 1))[0];
      if (cargo) { tomados.add(cargo.id); extra += -cargo.monto; }
      if (extra > 0) p.mora = { monto: Math.round(extra), dias, ...(cargo ? { movimiento: cargo.id } : {}) };
    }
  }
  /** Lo pagado este año en intereses por atraso (igual que compromisos.mora_del_anio). */
  function moraDelAnio(compromisos, movimientos, hoy, moneda, uf = null, mora = []) {
    const { pagos } = asignar(compromisos.filter((c) => c.activo !== false), movimientos, hoy, moneda, uf ? uf.valor ?? null : null, mora);
    return Math.round(Object.values(pagos).reduce((a, p) => a + (p.mora && p.fecha.slice(0, 4) === hoy.slice(0, 4) && p.fecha <= hoy ? p.mora.monto : 0), 0));
  }
  const pagoDe = (m) => ({ como: "automatico", fecha: m.fecha, monto: Math.abs(m.monto), movimiento: m.id, descripcion: m.descripcion });
  const menorTupla = (a, b) => { for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] < b[i]; return false; };
  function asignar(compromisos, movimientos, hasta, moneda, uf = null, mora = []) {
    const ocs = compromisos.flatMap((c) => vencimientos(c, hasta).map((o) => [c, o]));
    const porId = new Map(movimientos.map((m) => [m.id, m]));
    const pagos = {}, usados = new Set(), pendientes = [];
    for (const [c, o] of ocs) {
      const e = (c.pagos || {})[o.periodo] || {}, clave = `${c.id}|${o.periodo}`;
      if (e.como === "manual") pagos[clave] = { como: "manual", fecha: e.fecha || o.vence, monto: c.monto };
      else if (e.como === "automatico" && porId.has(e.movimiento) && !usados.has(e.movimiento)) { usados.add(e.movimiento); pagos[clave] = pagoDe(porId.get(e.movimiento)); }
      else pendientes.push([c, o, new Set(e.no_es || [])]);
    }
    const candidatos = {}, pares = [];
    for (const [c, o, noEs] of pendientes) {
      if (!candidatos[c.id]) candidatos[c.id] = [...movimientos.filter((m) => coincide(m, c, moneda, uf)).map((m) => [dnum(m.fecha), m, false]),
        ...movimientos.filter((m) => coincideTarde(m, c, moneda, uf)).map((m) => [dnum(m.fecha), m, true])];
      const v = dnum(o.vence), esperado = c.moneda === UF ? (uf ? c.monto * uf : 0) : c.monto;
      for (const [n, m, tarde] of candidatos[c.id]) {
        if ((!tarde || n > v) && n >= v - ANTES && n <= v + (c.frecuencia === "mensual" || c.frecuencia === "anual" ? ATRASO_MAX : DESPUES) && !usados.has(m.id) && !noEs.has(m.id) && (o.vence >= c.desde || m.fecha < c.desde))
          pares.push([[Math.abs(n - v), esperado ? Math.abs(Math.abs(m.monto) - esperado) : 0, o.vence < c.desde, o.vence, c.id, o.periodo, m.fecha, m.id], c, o, m]);
      }
    }
    pares.sort((a, b) => (menorTupla(a[0], b[0]) ? -1 : menorTupla(b[0], a[0]) ? 1 : 0));
    for (const [, c, o, m] of pares) {
      const clave = `${c.id}|${o.periodo}`;
      if (pagos[clave] || usados.has(m.id)) continue;
      usados.add(m.id); pagos[clave] = pagoDe(m);
    }
    moras(ocs, pagos, movimientos, moneda, uf, mora || [], usados);
    return { ocs, pagos, usados };
  }
  const mensualDe = (c, x = c.monto) => Math.round(c.frecuencia === "mensual" ? x : c.frecuencia === "semanal" ? x * 52 / 12 : c.frecuencia === "anual" ? x / 12 : 0);
  const mesesEntre = (a, b) => Math.max(1, Math.abs((+b.slice(0, 4) * 12 + +b.slice(5, 7)) - (+a.slice(0, 4) * 12 + +a.slice(5, 7))));
  /** Valor de la UF para cada compromiso en UF (igual que compromisos.valores_uf): su último pago, o lo más reciente entre Ajustes y otro compromiso. */
  function valoresUF(compromisos, pagos, uf = null) {
    const propios = {};
    for (const c of compromisos) {
      if (c.moneda !== UF) continue;
      let mejor = null;
      for (const [k, p] of Object.entries(pagos)) {
        if (k.split("|")[0] !== c.id || !p.movimiento) continue;
        if (!mejor || p.fecha > mejor[0] || (p.fecha === mejor[0] && k > mejor[1])) mejor = [p.fecha, k, p];
      }
      if (mejor) propios[c.id] = { valor: mejor[2].monto / c.monto, fecha: mejor[0], fuente: "pago" };
    }
    let otro = null;
    for (const [k, v] of Object.entries(propios)) if (!otro || v.fecha > otro[0] || (v.fecha === otro[0] && k > otro[1])) otro = [v.fecha, k, v];
    otro = otro ? { ...otro[2], fuente: "otro" } : null;
    const ajustes = uf && uf.valor ? { valor: uf.valor, fecha: uf.fecha, fuente: "ajustes" } : null;
    const general = ajustes && (!otro || ajustes.fecha >= otro.fecha) ? ajustes : otro;
    const r = {};
    for (const c of compromisos) if (c.moneda === UF && (propios[c.id] || general)) r[c.id] = propios[c.id] || general;
    return r;
  }
  /** El monto para mostrar y sumar (igual que compromisos.en_moneda): en UF se pasa a la moneda principal con un rango. */
  function enMoneda(c, vence, valores, moneda, ufMensual = UF_MENSUAL) {
    if (c.moneda !== UF) { const r = rangoAprox(c); return { monto: c.monto, moneda: c.moneda, rango: r ? { min: r[0], max: r[1] } : null, original: null }; }
    const ref = valores[c.id];
    if (!ref) return { monto: c.monto, moneda: UF, rango: null, original: { monto: c.monto, moneda: UF, sin_valor: true } };
    const [lo, hi] = rangoUF(c, ref.valor, ufMensual * mesesEntre(ref.fecha, vence));
    return { monto: redondear3(c.monto * ref.valor), moneda, rango: { min: redondear3(lo, -1), max: redondear3(hi, 1) },
      original: { monto: c.monto, moneda: UF, sin_valor: false, valor_uf: Math.round(ref.valor * 100) / 100, fecha_uf: ref.fecha, fuente: ref.fuente } };
  }
  /** Un préstamo entre personas (igual que compromisos.calcular_prestamo): total con interés simple, cuota y la última que ajusta. */
  function calcularPrestamo(total, cuotas, interes = 0, moneda = "CLP", cuotaFija = null) {
    const escala = moneda === UF ? 10000 : 1, pagar = Math.floor(total * (1 + interes / 100) * escala + 0.5);
    // Una cuota fija y redonda (la del plan de préstamos) si calza: al menos lo justo, no más que el total y sin pagarlo todo antes de la última.
    const fija = typeof cuotaFija === "number" && cuotaFija > 0 ? Math.floor(cuotaFija * escala + 0.5) : null, base = Math.floor(pagar / cuotas);
    const cuota = fija != null && base <= fija && fija <= pagar && fija * (cuotas - 1) < pagar ? fija : base;
    const ultima = pagar - cuota * (cuotas - 1), a = (x) => x / escala;
    return { total, interes, pagar: a(pagar), cuota: a(cuota), ultima: a(ultima) };
  }
  const maximoDe = (x) => (x.rango ? x.rango.max : x.monto), minimoDe = (x) => (x.rango ? x.rango.min : x.monto);
  // Se paga solo o lo pagas tú (igual que compromisos.modo_pago en Python).
  const PAGOS = ["automatico", "manual"], MANUAL_POR_TIPO = ["deuda", "prestamo", "cuenta", "suscripcion", "transferencia"], GRACIA_AUTO = 3;
  const escRegex = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  /** «automatico», «manual» o null (no se sabe: se recuerda como uno manual, sin etiqueta). Lo que dijo la persona manda; si no,
   *  «automatico» si el nombre o sus palabras traen una de `palabras` (PAC, Netflix…), y «manual» para deudas, préstamos,
   *  cuentas, suscripciones y transferencias. Los ingresos no tienen. */
  function modoPago(c, palabras = []) {
    if (c.signo === "ingreso" || c.tipo === "ingreso") return null;
    if (PAGOS.includes(c.pago)) return c.pago;
    const texto = [c.nombre || "", ...(c.buscar || []).map(String)].map(normalizar).join(" | ");
    for (const p of palabras) {
      const n = normalizar(p);
      if (n && new RegExp(`(?<![A-Z0-9])${escRegex(n)}(?![A-Z0-9])`).test(texto)) return "automatico";
    }
    return MANUAL_POR_TIPO.includes(c.tipo) ? "manual" : null;
  }
  /** Estado de cada compromiso en el mes (igual que compromisos.estado_mes en Python). Uno que se paga solo y ya venció queda
   *  «esperando» los primeros GRACIA_AUTO días y después «atrasado» (no vimos el cargo). */
  function estadoCompromisos(compromisos, movimientos, mes, hoy, moneda, per = null, uf = null, mora = [], auto = []) {
    const activos = compromisos.filter((c) => c.activo !== false);
    const [inicio, fin] = rango(mes, per);
    const { ocs, pagos } = asignar(activos, movimientos, fin, moneda, uf ? uf.valor ?? null : null, mora);
    const valores = valoresUF(activos, pagos, uf), ufMes = uf && uf.variacion_mensual != null ? uf.variacion_mensual : UF_MENSUAL;
    const antes = inicio <= hoy && hoy <= fin ? rango(sumarMes(mes, -1), per) : null, h = dnum(hoy);
    const items = [];
    for (const [c, o] of ocs) {
      const enMes = inicio <= o.vence && o.vence <= fin;
      if (!enMes && !(antes && antes[0] <= o.vence && o.vence <= antes[1])) continue;
      const p = pagos[`${c.id}|${o.periodo}`];
      if (!p && o.vence < c.desde) continue;
      const d = dnum(o.vence) - h, modo = modoPago(c, auto || []);
      const estado = p ? "pagado" : d > 0 ? "pendiente" : d === 0 ? "hoy" : modo === "automatico" && -d <= GRACIA_AUTO ? "esperando" : "atrasado";
      if (!enMes && estado !== "atrasado" && estado !== "esperando") continue;
      const cuota = c.cuotas_total && o.n ? { numero: (c.cuotas_pagadas || 0) + o.n, total: c.cuotas_total } : null;
      const en = enMoneda(c, o.vence, valores, moneda, ufMes);
      if (c.prestamo && cuota && cuota.numero === c.cuotas_total && c.moneda !== UF) en.monto = c.prestamo.ultima; // la última cuota ajusta el redondeo
      items.push({ id: c.id, nombre: c.nombre, tipo: c.tipo, signo: c.signo, ...en, categoria: c.categoria,
        periodo: o.periodo, vence: o.vence, estado, dias: p ? 0 : Math.abs(d), pago: p || null, cuota, anterior: !enMes, modo_pago: modo });
    }
    items.sort((a, b) => (a.vence !== b.vence ? (a.vence < b.vence ? -1 : 1) : a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const suma = (l) => Math.round(l.reduce((a, i) => a + i.monto, 0));
    const g = items.filter((i) => i.signo === "gasto" && i.moneda === moneda);
    const ing = items.filter((i) => i.signo === "ingreso" && i.moneda === moneda && !i.anterior);
    const resumen_ = activos.map((c) => {
      const en = enMoneda(c, hoy, valores, moneda, ufMes), saldo = c.saldo ?? null;
      const factor = c.moneda === UF && !en.original.sin_valor ? en.monto / c.monto : 1;
      const r = { id: c.id, nombre: c.nombre, tipo: c.tipo, signo: c.signo, ...en, frecuencia: c.frecuencia,
        categoria: c.categoria, mensual: mensualDe(c, en.monto), cuotas: null, saldo,
        por_pagar: saldo != null ? (factor !== 1 ? Math.round(saldo * factor) : saldo) : null, termina: c.fecha_fin ?? null, con: c.con ?? null,
        modo_pago: modoPago(c, auto || []) };
      if (c.cuotas_total) {
        const pagadas = (c.cuotas_pagadas || 0) + ocs.filter(([cc, o]) => cc === c && o.n && pagos[`${c.id}|${o.periodo}`]).length;
        const quedan = Math.max(0, c.cuotas_total - pagadas);
        const todas = vencimientos(c, "2299-12-31");
        const ultima = [...todas].reverse().find((o) => o.n)?.vence ?? null;
        r.cuotas = { pagadas: Math.min(pagadas, c.cuotas_total), total: c.cuotas_total, quedan };
        r.termina = ultima && c.fecha_fin ? (ultima < c.fecha_fin ? ultima : c.fecha_fin) : ultima || c.fecha_fin || null;
        if (r.por_pagar == null) {
          r.por_pagar = en.moneda !== UF ? Math.round(quedan * en.monto) : Math.round(quedan * en.monto * 10000) / 10000;
          if (c.prestamo && quedan && en.moneda !== UF) r.por_pagar += c.prestamo.ultima - c.monto;
        }
      }
      return r;
    });
    const sinPagar = g.filter((i) => i.estado !== "pagado"), sumaCon = (l, f) => Math.round(l.reduce((a, i) => a + f(i), 0));
    return { mes, moneda, items, total: suma(g.filter((i) => !i.anterior)), pagado: suma(g.filter((i) => i.estado === "pagado")),
      pendiente: suma(sinPagar), atrasado: suma(g.filter((i) => i.estado === "atrasado")),
      arrastre: suma(g.filter((i) => i.anterior)), ingresos_esperados: suma(ing), ingresos_recibidos: suma(ing.filter((i) => i.estado === "pagado")),
      total_max: sumaCon(g.filter((i) => !i.anterior), maximoDe), pendiente_max: sumaCon(sinPagar, maximoDe), arrastre_max: sumaCon(g.filter((i) => i.anterior), maximoDe),
      ingresos_esperados_min: sumaCon(ing, minimoDe), aprox: sinPagar.some((i) => i.rango), sin_valor: items.filter((i) => i.original && i.original.sin_valor).length,
      compromisos: resumen_ };
  }
  /** Día en que llegó el sueldo de cada mes (igual que compromisos.llegadas_sueldo en Python). */
  function llegadasSueldo(compromisos, movimientos, hasta, moneda) {
    const sueldo = compromisos.find((c) => c.activo !== false && c.tipo === "ingreso" && c.frecuencia === "mensual" && c.categoria === "sueldo");
    if (!sueldo) return [];
    const { ocs, pagos } = asignar([sueldo], movimientos, hasta, moneda), r = [];
    for (const [c, o] of ocs) { const p = pagos[`${c.id}|${o.periodo}`]; if (p) r.push(p.fecha); }
    return r.sort();
  }
  const PALABRAS_SUELDO = ["REMUNERACION", "SUELDO", "NOMINA", "PAYROLL", "SALARIO", "SALARY"], SUELDO_PARECIDO = 25, SUELDO_PRINCIPAL = 50;
  /** El sueldo, si se ve claro (igual que compromisos.detectar_sueldo en Python): el ingreso más grande que se repite en 2 de los
   *  últimos 3 meses (o 3 de 4) con monto parecido (±25 %), que no es entre tus cuentas; si la descripción no dice sueldo, cada
   *  llegada es al menos la mitad de lo que entró ese mes. {dia (mediana), monto, variacion, llegadas, clave, meses} o null. */
  function detectarSueldo(movimientos, hoy, categorias, moneda) {
    const mes = hoy.slice(0, 7), meses4 = [3, 2, 1, 0].map((i) => sumarMes(mes, -i));
    const neutras = new Set([...categorias.filter((c) => c.tipo === "neutro").map((c) => c.id), "transferencia"]);
    // Lo que la persona ya marcó como Sueldo manda (igual que en Python): esa descripción cuenta aunque haya quedado entre tus cuentas.
    const sueldoClaves = new Set(movimientos.filter((m) => m.categoria === "sueldo" && m.monto > 0).map((m) => reglaPara(m.descripcion)));
    const ingresos = movimientos.filter((m) => m.monto > 0 && m.fecha <= hoy && meses4.includes(m.fecha.slice(0, 7))
      && (!neutras.has(m.categoria) || sueldoClaves.has(reglaPara(m.descripcion))) && (m.moneda || moneda) === moneda);
    const totalMes = {};
    for (const m of ingresos) totalMes[m.fecha.slice(0, 7)] = (totalMes[m.fecha.slice(0, 7)] || 0) + m.monto;
    const orden = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
    const claveDe = new Map(ingresos.map((m) => [m.id, reglaPara(m.descripcion)]));
    const marcado = (m) => sueldoClaves.has(claveDe.get(m.id));
    // Primero lo que se parece a lo ya marcado como Sueldo, y solo con esa misma descripción (igual que en Python).
    const anclas = [...ingresos].sort((a, b) => (marcado(a) === marcado(b) ? 0 : marcado(a) ? -1 : 1) || b.monto - a.monto || orden(a.fecha, b.fecha) || orden(a.id, b.id));
    for (const ancla of anclas) {
      const miembros = [], mismo = marcado(ancla);
      for (const x of meses4) {
        const cerca = ingresos.filter((m) => m.fecha.slice(0, 7) === x && Math.abs(m.monto - ancla.monto) <= ancla.monto * SUELDO_PARECIDO / 100 + 1e-9
          && (!mismo || claveDe.get(m.id) === claveDe.get(ancla.id)));
        if (cerca.length) miembros.push(cerca.sort((a, b) => Math.abs(a.monto - ancla.monto) - Math.abs(b.monto - ancla.monto) || orden(a.fecha, b.fecha) || orden(a.id, b.id))[0]);
      }
      const en3 = miembros.filter((m) => meses4.slice(1).includes(m.fecha.slice(0, 7))).length;
      if (en3 < 2 && miembros.length < 3) continue;
      const dice = miembros.some((m) => m.categoria === "sueldo" || PALABRAS_SUELDO.some((p) => normalizar(m.descripcion).includes(p)));
      if (!dice && miembros.some((m) => m.monto < totalMes[m.fecha.slice(0, 7)] * SUELDO_PRINCIPAL / 100 - 1e-9)) continue;
      const dias = miembros.map((m) => +m.fecha.slice(8, 10)).sort((a, b) => a - b), k = Math.floor(dias.length / 2);
      const dia = dias.length % 2 ? dias[k] : Math.floor((dias[k - 1] + dias[k] + 1) / 2);
      const montos = miembros.map((m) => m.monto), medio = [...montos].sort((a, b) => a - b)[Math.floor((montos.length - 1) / 2)];
      const variacion = Math.min(50, Math.max(1, Math.ceil(Math.max(...montos.map((x) => Math.abs(x - medio))) / medio * 100 - 1e-9)));
      const claves = new Set(miembros.map((m) => reglaPara(m.descripcion).replace(/[^A-Z0-9]+$/, ""))), clave = claves.size === 1 ? [...claves][0] : "";
      return { dia, monto: medio, variacion, llegadas: miembros.map((m) => m.fecha).sort(), clave: clave.length >= 3 ? clave : "", meses: miembros.length };
    }
    return null;
  }
  function periodoConfig(inicioMes, compromisos, movimientos, hoy, moneda) {
    if (!inicioMes || inicioMes.modo !== "sueldo" || !Number.isInteger(inicioMes.dia) || inicioMes.dia < 1 || inicioMes.dia > 31) return null;
    const llegadas = llegadasSueldo(compromisos, movimientos, dfecha(dnum(hoy) + 62), moneda);
    return llegadas.length ? { modo: "sueldo", dia: inicioMes.dia, llegadas, hoy } : { modo: "sueldo", dia: inicioMes.dia, llegadas };
  }
  // Días hábiles y el próximo sueldo (igual que compromisos.py; los feriados llegan en el estado, de bin/feriados.json).
  const esHabil = (f, fer) => { const d = new Date(f + "T00:00:00Z").getUTCDay(); return d !== 0 && d !== 6 && !fer.includes(f); };
  function correrHabil(f, regla, fer) {
    const paso = regla === "siguiente" ? 1 : -1;
    for (let n = 0; !esHabil(f, fer) && n < 15; n++) f = sumarDias(f, paso);
    return f;
  }
  function nominalCerca(dia, llegada) {
    const m = llegada.slice(0, 7);
    const ops = [sumarMes(m, -1), m, sumarMes(m, 1)].map((x) => `${x}-${pad2(Math.min(dia, diasDelMes(x)))}`);
    return ops.sort((a, b) => Math.abs(diasEntre(llegada, a)) - Math.abs(diasEntre(llegada, b)) || (a < b ? -1 : 1))[0];
  }
  function reglaHabil(dia, llegadas, fer) {
    let antes = 0, despues = 0;
    for (const f of llegadas) { const n = nominalCerca(dia, f); if (!esHabil(n, fer)) { if (f < n) antes++; if (f > n) despues++; } }
    return despues > antes ? "siguiente" : "anterior";
  }
  function proximoSueldo(per, hoy, fer) {
    if (!per || per.modo !== "sueldo" || !Number.isInteger(per.dia)) return null;
    const siguiente = sumarMes(periodoDe(hoy, per), 1), nominal = inicioNominal(siguiente, per);
    const regla = reglaHabil(per.dia, per.llegadas || [], fer), fecha = correrHabil(nominal, regla, fer);
    const plazo = correrHabil(sumarDias(fecha, 1), "siguiente", fer);
    return { fecha, nominal, regla, periodo: siguiente, atrasado: hoy > plazo };
  }
  const mediana = (valores) => { const v = [...valores].sort((a, b) => a - b), k = Math.floor(v.length / 2); return v.length % 2 ? v[k] : (v[k - 1] + v[k]) / 2; };
  /** Cuánto se puede gastar en lo variable este mes (igual que compromisos.gasto_maximo en Python). */
  function gastoMaximo(movimientos, compromisos, mes, hoy, categorias, mesesCompletos, moneda, per = null, uf = null) {
    const e = estadoCompromisos(compromisos, movimientos, mes, hoy, moneda, per, uf);
    const [inicio, fin] = rango(mes, per), rangos = mesesCompletos.map((x) => rango(x, per));
    const dentro = (f, [a, b]) => a <= f && f <= b;
    const activos = compromisos.filter((c) => c.activo !== false);
    const neutras = new Set(categorias.filter((c) => c.tipo === "neutro").map((c) => c.id));
    const deCompromiso = new Set(movimientos.filter((m) => activos.some((c) => coincide(m, c, moneda, uf ? uf.valor ?? null : null))).map((m) => m.id));
    const propios = movimientos.filter((m) => (m.moneda || moneda) === moneda && !deCompromiso.has(m.id));
    let ingreso = null, fuente = "";
    if (e.ingresos_esperados > 0) { ingreso = e.ingresos_esperados_min; fuente = "compromisos"; }
    else {
      const conDatos = periodosConDatos(movimientos.filter((m) => (m.moneda || moneda) === moneda), per).filter((x) => x < mes).slice(-3);
      const rs = conDatos.map((x) => rango(x, per));
      const total = movimientos.filter((m) => rs.some((r) => dentro(m.fecha, r)) && m.monto > 0 && (m.moneda || moneda) === moneda && !neutras.has(m.categoria)).reduce((a, m) => a + m.monto, 0);
      if (conDatos.length && total > 0) { ingreso = Math.round(total / conDatos.length); fuente = "promedio"; }
    }
    const comp = e.total_max + e.arrastre_max, normal = {}, gastado = {};
    for (const c of categorias.filter((x) => x.tipo === "gasto")) {
      const valores = rangos.map((r) => propios.filter((m) => dentro(m.fecha, r) && m.categoria === c.id && m.monto < 0).reduce((a, m) => a - m.monto, 0));
      normal[c.id] = valores.length && mediana(valores) > 0 ? redondearArriba(mediana(valores)) : 0;
      gastado[c.id] = Math.round(propios.filter((m) => dentro(m.fecha, [inicio, fin]) && m.categoria === c.id && m.monto < 0).reduce((a, m) => a - m.monto, 0));
    }
    const fijas = new Set(categorias.filter((c) => c.tipo === "gasto" && c.fijo).map((c) => c.id));
    const otrosFijos = Object.entries(normal).filter(([k]) => fijas.has(k)).reduce((a, [, v]) => a + v, 0);
    const disponible = ingreso != null ? ingreso - comp - otrosFijos : null;
    const variables = categorias.filter((c) => c.tipo === "gasto" && !fijas.has(c.id)).map((c) => c.id);
    const habitual = variables.reduce((a, k) => a + normal[k], 0);
    const por = [];
    for (const k of variables) {
      if (!normal[k] && !gastado[k]) continue;
      const maximo = disponible != null && disponible > 0 && habitual > 0 ? redondearAbajo(disponible * normal[k] / habitual) : 0;
      por.push({ categoria: k, normal: normal[k], maximo, gastado: gastado[k] });
    }
    por.sort((a, b) => b.maximo - a.maximo || b.gastado - a.gastado || (a.categoria < b.categoria ? -1 : a.categoria > b.categoria ? 1 : 0));
    return { mes, moneda, ingreso, fuente, compromisos: comp, otros_fijos: otrosFijos, disponible, alcanza: disponible != null && disponible > 0, por_categoria: por };
  }
  /** Lo que tienes: el saldo de cada cuenta (igual que resumen.lo_que_tienes en Python). */
  function saldoBase(c) {
    const s = c && c.saldo;
    if (!s || typeof s !== "object" || typeof s.monto !== "number" || !/^\d{4}-\d{2}-\d{2}$/.test(String(s.fecha || ""))) return null;
    return { monto: s.monto, fecha: s.fecha, origen: ["persona", "cartola", "conector"].includes(s.origen) ? s.origen : "persona" };
  }
  const red2 = (v) => Math.round(v * 100) / 100;
  function loQueTienes(cuentas, movimientos, moneda) {
    const lista = [], vistas = new Set();
    for (const c of cuentas) if (c && c.id && !vistas.has(c.id)) { vistas.add(c.id); lista.push(c); }
    for (const m of movimientos) if (m.cuenta && !vistas.has(m.cuenta)) { vistas.add(m.cuenta); lista.push({ id: m.cuenta, nombre: m.cuenta }); }
    let total = 0, con = 0;
    const r = lista.map((c) => {
      const mon = c.moneda || moneda, base = saldoBase(c);
      let saldo = null, despues = 0;
      if (base) {
        const mios = movimientos.filter((m) => m.cuenta === c.id && m.fecha > base.fecha && m.medio !== "credito" && (m.moneda || mon) === mon);
        despues = mios.length;
        saldo = red2(base.monto + mios.reduce((a, m) => a + m.monto, 0));
        if (mon === moneda) { total += saldo; con++; }
      }
      return { id: c.id, nombre: c.nombre || c.id, moneda: mon, saldo, base, movimientos_despues: despues };
    });
    return { moneda, total: con ? red2(total) : null, con_saldo: con, sin_saldo: r.filter((x) => x.saldo == null && x.moneda === moneda).length, cuentas: r };
  }
  // Lo que debes (igual que compromisos.lo_que_debes en Python).
  const PAGO_TARJETA = ["PAGO TARJETA", "PAGO DE TARJETA", "PAGO TC", "PAGO T C", "PAGO TARJ", "TARJETA DE CREDITO", "PAGO DE RESUMEN", "CREDIT CARD PAYMENT", "PAYMENT THANK YOU"];
  const esPagoTarjeta = (m) => { const d = normalizar(String(m.descripcion || "").replace(/[.\-_/]/g, " ")); return m.monto < 0 && m.medio !== "credito" && PAGO_TARJETA.some((p) => d.includes(p)); };
  const ORDEN_ESTADO = { atrasado: 0, hoy: 1, esperando: 2, pendiente: 3 };
  const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  function loQueDebes(compromisos, movimientos, hoy, moneda, per = null, uf = null, auto = []) {
    const mes = periodoDe(hoy, per), [, fin] = rango(mes, per);
    const e = estadoCompromisos(compromisos, movimientos, mes, hoy, moneda, per, uf, [], auto);
    const conSaldo = new Map(e.compromisos.filter((c) => c.signo === "gasto" && (c.tipo === "deuda" || c.tipo === "prestamo") && c.moneda === moneda && c.por_pagar).map((c) => [c.id, c]));
    const pendientes = e.items.filter((i) => i.signo === "gasto" && i.moneda === moneda && i.estado !== "pagado")
      .sort((a, b) => ORDEN_ESTADO[a.estado] - ORDEN_ESTADO[b.estado] || cmp(a.vence, b.vence) || cmp(a.id, b.id));
    const partes = [];
    for (const i of pendientes) if (!conSaldo.has(i.id)) partes.push({ tipo: "compromiso", nombre: i.nombre, monto: Math.round(i.monto), este_mes: Math.round(i.monto),
      max: Math.round(maximoDe(i)), original: i.original, estado: i.estado, vence: i.vence, dias: i.dias, categoria: i.categoria, clave: `${i.id}|${i.periodo}`, modo_pago: i.modo_pago });
    const pagos = movimientos.filter((m) => m.fecha <= hoy && (m.moneda || moneda) === moneda && esPagoTarjeta(m)).map((m) => m.fecha).sort();
    const ultimo = pagos.length ? pagos[pagos.length - 1] : null, desde = rango(sumarMes(mes, -1), per)[0];
    let tarjeta = 0, compras = 0;
    const cuotas = [];
    for (const m of [...movimientos].sort((a, b) => cmp(a.fecha, b.fecha) || cmp(a.id || "", b.id || ""))) {
      if (m.medio !== "credito" || m.monto >= 0 || (m.moneda || moneda) !== moneda) continue;
      const enTarjeta = cargos(m).filter(([f]) => f <= fin && f >= desde && (ultimo == null || f > ultimo));
      if (enTarjeta.length) { tarjeta += enTarjeta.reduce((a, [, v]) => a - v, 0); compras++; }
      const n = cuotasDe(m), quedan = n ? cargos(m).filter(([f]) => f > fin).length : 0;
      if (quedan) { const c = valorCuota(m); cuotas.push({ tipo: "cuotas", nombre: m.descripcion, monto: Math.round(quedan * c), este_mes: 0, max: Math.round(quedan * c), original: null, cuota: Math.round(c), quedan, total: n, categoria: m.categoria || "" }); }
    }
    if (tarjeta) partes.push({ tipo: "tarjeta", nombre: "", monto: Math.round(tarjeta), este_mes: Math.round(tarjeta), max: Math.round(tarjeta), original: null, compras, desde: ultimo });
    for (const c of [...conSaldo.values()].sort((a, b) => cmp(a.id, b.id))) {
      const mias = pendientes.filter((i) => i.id === c.id);
      const extra = mias.reduce((a, i) => a + maximoDe(i) - i.monto, 0);
      partes.push({ tipo: "deuda", nombre: c.nombre, monto: Math.round(c.por_pagar), este_mes: Math.round(mias.reduce((a, i) => a + i.monto, 0)),
        max: c.rango ? Math.round(c.por_pagar * c.rango.max / c.monto) : Math.round(c.por_pagar + extra), original: c.original, con: c.con, cuotas: c.cuotas, categoria: c.categoria, termina: c.termina,
        pendientes: mias.map((i) => ({ estado: i.estado, vence: i.vence, dias: i.dias, monto: Math.round(i.monto), clave: `${i.id}|${i.periodo}`, modo_pago: i.modo_pago })) });
    }
    partes.push(...cuotas.sort((a, b) => b.monto - a.monto || cmp(a.nombre, b.nombre)));
    const esteMesMax = partes.filter((p) => p.tipo !== "deuda").reduce((a, p) => a + (p.tipo === "compromiso" ? p.max : p.este_mes), 0)
      + pendientes.filter((i) => conSaldo.has(i.id)).reduce((a, i) => a + maximoDe(i), 0);
    // Te deben: préstamos que hiciste tú. Van aparte y nunca se restan de lo que debes.
    const teDeben = e.compromisos.filter((c) => c.tipo === "prestamo" && c.signo === "ingreso" && c.moneda === moneda && c.por_pagar).sort((a, b) => cmp(a.id, b.id))
      .map((c) => ({ nombre: c.nombre, con: c.con, monto: Math.round(c.por_pagar), este_mes: Math.round(e.items.filter((i) => i.id === c.id && i.estado !== "pagado").reduce((a, i) => a + i.monto, 0)),
        cuotas: c.cuotas, termina: c.termina }));
    return { mes, moneda, total: Math.round(partes.reduce((a, p) => a + p.monto, 0)), te_deben: teDeben, te_deben_total: Math.round(teDeben.reduce((a, t) => a + t.monto, 0)),
      este_mes: Math.round(partes.reduce((a, p) => a + p.este_mes, 0)),
      total_max: Math.round(partes.reduce((a, p) => a + p.max, 0)), este_mes_max: Math.round(esteMesMax), aprox: partes.some((p) => p.max !== p.monto),
      ultimo_pago_tarjeta: ultimo, partes };
  }
  // ───────────── Para conversar con Alcancía (igual que compromisos.py: margen_mensual, plan_prestamos, inicio_plan,
  // pago_reasignable y reasignar_pago; casos en pruebas/casos.json, «chat») ─────────────
  const USO_MARGEN = 75, MESES_MAX = 60, MESES_SIN_DATOS = 12;
  const vigente = (r, hoy) => r.frecuencia !== "una_vez" && !(r.cuotas && r.cuotas.quedan === 0) && (!r.termina || r.termina >= hoy);
  /** Cuánto queda libre en un mes normal: ingreso típico − gasto típico (sin los pagos de compromisos) − compromisos al mes. */
  function margenMensual(compromisos, movimientos, hoy, categorias, moneda, per = null, uf = null, auto = [], sin = []) {
    const mes = periodoDe(hoy, per), enMon = movimientos.filter((m) => (m.moneda || moneda) === moneda);
    const completos = periodosConDatos(enMon, per).filter((x) => x < mes).slice(-3);
    const e = estadoCompromisos(compromisos, movimientos, mes, hoy, moneda, per, uf, [], auto);
    const vig = e.compromisos.filter((r) => r.moneda === moneda && vigente(r, hoy)), pres = { moneda, mensual: {} };
    let ingreso = vig.filter((r) => r.signo === "ingreso" && r.tipo === "ingreso").reduce((a, r) => a + mensualDe(r, minimoDe(r)), 0), fuente = "compromisos";
    if (ingreso <= 0) {
      ingreso = null; fuente = "";
      if (completos.length) {
        const v = Math.round(completos.reduce((a, x) => a + resumen(enMon, x, hoy, pres, categorias, per).ingresos, 0) / completos.length);
        if (v > 0) { ingreso = v; fuente = "promedio"; }
      }
    }
    const activos = compromisos.filter((c) => c.activo !== false), uv = uf ? uf.valor ?? null : null;
    const propios = enMon.filter((m) => !activos.some((c) => coincide(m, c, moneda, uv)));
    const gasto = completos.length ? Math.round(completos.reduce((a, x) => a + resumen(propios, x, hoy, pres, categorias, per).gastado, 0) / completos.length) : null;
    const comp = vig.filter((r) => r.signo === "gasto" && !sin.includes(r.id)).reduce((a, r) => a + mensualDe(r, maximoDe(r)), 0);
    return { ingreso, fuente, gasto, meses: completos.length, compromisos: comp,
      sin_valor: e.compromisos.filter((r) => r.original && r.original.sin_valor).length, margen: ingreso != null && gasto != null ? ingreso - gasto - comp : null };
  }
  const pasoCuota = (v) => (v >= 500000 ? 10000 : v >= 50000 ? 5000 : v >= 5000 ? 1000 : v >= 500 ? 100 : v >= 50 ? 10 : 1);
  /** Cuánto pagar al mes, y en cuántos meses, a cada persona que te prestó: como máximo el 75 % del margen (ver plan_prestamos). */
  function planPrestamos(deudas, margen, moneda = "CLP") {
    const pagar = deudas.map((d) => calcularPrestamo(d.total, 1, d.interes || 0, moneda).pagar);
    const disponible = margen == null ? null : Math.max(0, Math.floor(margen * USO_MARGEN / 100));
    const cuotas = (n) => pagar.map((p) => { const paso = pasoCuota(p / n); return Math.ceil(p / (n * paso)) * paso; });
    let elegido = null;
    if (disponible) for (let n = 1; n <= MESES_MAX; n++) if (cuotas(n).reduce((a, c) => a + c, 0) <= disponible) { elegido = n; break; }
    const alcanza = margen == null ? null : elegido != null;
    const cs = cuotas(elegido || (margen == null ? MESES_SIN_DATOS : MESES_MAX));
    const detalle = deudas.map((d, i) => {
      const n = Math.max(1, Math.ceil(pagar[i] / cs[i])), k = calcularPrestamo(d.total, n, d.interes || 0, moneda, cs[i]);
      return { con: d.con, total: d.total, interes: d.interes || 0, pagar: k.pagar, cuota: k.cuota, ultima: k.ultima, cuotas: n };
    });
    const alMes = detalle.reduce((a, x) => a + x.cuota, 0);
    return { margen, uso: USO_MARGEN, disponible, alcanza, al_mes: alMes, meses: Math.max(...detalle.map((x) => x.cuotas)),
      falta: alcanza === false ? Math.max(0, alMes - (disponible || 0)) : 0, deudas: detalle };
  }
  /** Desde cuándo se pagan las cuotas de un plan: el día después del próximo sueldo; si no, el 1 del mes que viene. */
  function inicioPlan(per, hoy, fer) {
    const ps = proximoSueldo(per, hoy, fer);
    return ps ? { desde: sumarDias(ps.fecha, 1), dia: per.dia % 31 + 1 } : { desde: sumarMes(hoy.slice(0, 7), 1) + "-01", dia: 1 };
  }
  // ¿Esa deuda ya está anotada? (igual que compromisos.py: claves_persona, prestamos_parecidos, plan_variante, prestamo_actualizado)
  const VACIAS_PERSONA = new Set(["MI", "MIS", "TU", "SU", "EL", "LA", "LOS", "LAS", "LO", "DE", "DEL", "AL", "CON", "Y", "PARA", "POR", "ME", "LE", "QUE",
    "DON", "DONA", "SR", "SRA", "SENOR", "SENORA", "PRESTAMO", "PRESTAMOS", "DEUDA", "DEUDAS", "CREDITO", "PAGO", "CUOTA",
    "CUOTAS", "PRESTO", "PRESTE", "MY", "THE", "LOAN", "DEBT", "FROM", "TO"]);
  const APODOS = { MAMI: "MAMA", MAMITA: "MAMA", MADRE: "MAMA", MOM: "MAMA", MOTHER: "MAMA", PAPI: "PAPA", PAPITO: "PAPA",
    PADRE: "PAPA", DAD: "PAPA", FATHER: "PAPA", ABUELITA: "ABUELA", ABUELITO: "ABUELO", TIITA: "TIA", TIITO: "TIO" };
  const PARECIDO = 15;
  /** Quién es la persona, para comparar: «Mi mamá» → ["MAMA"]; «Préstamo de Tío Matías» → ["MATIAS", "TIO"]. */
  const clavesPersona = (t) => [...new Set((normalizar(t).match(/[A-Z]+/g) || []).filter((p) => p.length > 1 && !VACIAS_PERSONA.has(p)).map((p) => APODOS[p] || p))].sort();
  const totalParecido = (a, b) => !!a && !!b && Math.abs(a - b) * 100 <= PARECIDO * Math.max(a, b);
  /** Para cada préstamo propuesto, el compromiso anotado que parece la misma deuda (o null): primero la persona, después el total
   *  (±15 %) si alguno de los dos no dice quién. Ver prestamos_parecidos en compromisos.py. */
  function prestamosParecidos(propuestas, compromisos, estado, hoy) {
    const raw = new Map(compromisos.map((c) => [c.id, c])), tomados = new Set();
    const sub = (a, b) => a.every((x) => b.includes(x));
    return propuestas.map((p) => {
      const pers = clavesPersona(p.con || p.nombre), total = p.total || (p.prestamo || {}).total;
      const moneda = p.moneda || estado.moneda, signo = p.signo || "gasto";
      let mejor = null;
      for (const x of estado.compromisos) {
        const c = raw.get(x.id);
        if (!c || tomados.has(x.id) || !["prestamo", "deuda"].includes(x.tipo) || x.signo !== signo || x.moneda !== moneda || !vigente(x, hoy)) continue;
        const con = clavesPersona(c.con), nom = clavesPersona(c.nombre);
        const persona = pers.length > 0 && ((con.length > 0 && (sub(pers, con) || sub(con, pers))) || sub(pers, nom));
        const original = (c.prestamo || {}).total;
        const cerca = [original, x.por_pagar].filter((v) => totalParecido(v, total)).map((v) => Math.abs(v - total));
        let rangoP;
        if (persona) rangoP = 0;
        else if (x.tipo === "prestamo" && cerca.length && !(pers.length && con.length)) rangoP = 1;
        else continue;
        const clave = [rangoP, cerca.length ? Math.min(...cerca) : Infinity, x.id];
        const menor = (a, b) => a[0] !== b[0] ? a[0] < b[0] : a[1] !== b[1] ? a[1] < b[1] : a[2] < b[2];
        if (!mejor || menor(clave, mejor.clave)) mejor = { clave, x, c };
      }
      if (!mejor) return null;
      const { x, c } = mejor;
      tomados.add(x.id);
      return { id: x.id, nombre: x.nombre, con: c.con || null, tipo: x.tipo, monto: x.monto, cuotas: x.cuotas, por_pagar: x.por_pagar,
        total: (c.prestamo || {}).total ?? null, motivo: mejor.clave[0] === 0 ? "persona" : "monto" };
    });
  }
  /** El plan cuando la persona dijo «es el mismo» (mismos: {índice: id}): esa cuota vuelve al margen, se planifica lo que falta
   *  pagar (si el total que dijo es parecido al anotado) y todas las deudas se recalculan. Ver plan_variante en compromisos.py. */
  function planVariante(deudas, mismos, compromisos, movimientos, hoy, categorias, moneda, per = null, uf = null, auto = []) {
    const ids = Object.values(mismos), mg = margenMensual(compromisos, movimientos, hoy, categorias, moneda, per, uf, auto, ids);
    const e = ids.length ? estadoCompromisos(compromisos, movimientos, periodoDe(hoy, per), hoy, moneda, per, uf, [], auto) : { compromisos: [] };
    const efectivas = deudas.map((d, j) => {
      const id = mismos[j], x = id ? e.compromisos.find((r) => r.id === id) : null, c = (id && compromisos.find((k) => k.id === id)) || {};
      const base = (c.prestamo || {}).total || (x || {}).por_pagar;
      return x && x.por_pagar && totalParecido(base, d.total) ? { con: d.con, total: x.por_pagar, interes: 0 } : { con: d.con, total: d.total, interes: d.interes || 0 };
    });
    const plan = planPrestamos(efectivas, mg.margen, moneda);
    return { ...plan, base: { ingreso: mg.ingreso, fuente: mg.fuente, gasto: mg.gasto, meses: mg.meses, compromisos: mg.compromisos } };
  }
  /** «Es el mismo»: el compromiso que ya estaba, con la deuda del plan desde `ini` (parte de nuevo). Ver prestamo_actualizado. */
  function prestamoActualizado(c, d, ini) {
    const nuevo = Object.fromEntries(Object.entries(c).filter(([k]) => !["pagos", "fecha", "fecha_fin", "saldo", "aproximado", "cuotas_restantes"].includes(k)));
    return { ...nuevo, tipo: "prestamo", con: c.con || d.con, prestamo: { total: d.total, interes: d.interes, cuota: d.cuota }, monto: d.cuota, cuotas_total: d.cuotas,
      cuotas_pagadas: 0, frecuencia: "mensual", dia: ini.dia, desde: ini.desde };
  }
  /** «Aún no pago la hipoteca de este mes», pero aparece pagada y el vencimiento anterior no: ese pago era del anterior. */
  function pagoReasignable(compromisos, movimientos, cid, hoy, moneda, per = null, uf = null, mora = []) {
    const activos = compromisos.filter((c) => c.activo !== false), c = activos.find((x) => x.id === cid);
    if (!c) return null;
    const [inicio, fin] = rango(periodoDe(hoy, per), per);
    const { ocs, pagos } = asignar(activos, movimientos, fin, moneda, uf ? uf.valor ?? null : null, mora);
    const mios = ocs.filter(([cc]) => cc === c).map(([, o]) => o);
    const pagados = mios.map((o, i) => [o, i]).filter(([o]) => inicio <= o.vence && o.vence <= fin && pagos[`${cid}|${o.periodo}`]).map(([, i]) => i);
    if (!pagados.length || pagados[pagados.length - 1] === 0) return null;
    const de = mios[pagados[pagados.length - 1]], a = mios[pagados[pagados.length - 1] - 1];
    if (pagos[`${cid}|${a.periodo}`]) return null;
    const p = pagos[`${cid}|${de.periodo}`];
    return { id: cid, nombre: c.nombre, de: { periodo: de.periodo, vence: de.vence }, a: { periodo: a.periodo, vence: a.vence },
      pago: { como: p.como, fecha: p.fecha, monto: p.monto, ...(p.movimiento ? { movimiento: p.movimiento } : {}) } };
  }
  /** Mueve el pago del vencimiento `de` al anterior `a` (cambia `c.pagos`). Devuelve "" o el problema (igual que reasignar_pago). */
  function reasignarPago(c, de, a, mov = null) {
    const pagos = c.pagos && typeof c.pagos === "object" ? { ...c.pagos } : {}, d = { ...(pagos[de] || {}) }, x = { ...(pagos[a] || {}) };
    const quitar = (o) => { for (const k of ["como", "fecha", "movimiento", "monto", "mora"]) delete o[k]; };
    if (!(a < de)) return "Solo se puede mover a un vencimiento anterior.";
    if (x.como) return "Ese vencimiento ya tiene un pago.";
    if (mov) {
      x.no_es = (x.no_es || []).filter((i) => i !== mov.id);
      Object.assign(x, { como: "automatico", fecha: mov.fecha, movimiento: mov.id, monto: Math.abs(mov.monto) });
      quitar(d); d.no_es = [...(d.no_es || []).filter((i) => i !== mov.id), mov.id].slice(-20);
    } else if (d.como === "manual") {
      Object.assign(x, { como: "manual", ...(d.fecha ? { fecha: d.fecha } : {}) }); quitar(d);
    } else return "No hay un pago que mover.";
    for (const [clave, v] of [[a, x], [de, d]]) {
      if (!(v.no_es || []).length) delete v.no_es;
      if (Object.keys(v).length) pagos[clave] = v; else delete pagos[clave];
    }
    c.pagos = pagos;
    return "";
  }
  const cat = (id) => E.categorias.find((c) => c.id === id) || { id: "", nombre: "Sin categoría", emoji: "🏷️", tipo: "gasto" };
  const nombreCat = (c) => (c.id && cat(c.id) === c ? c.nombre : tr("Sin categoría"));
  const nombreIA = () => E.ias.find((i) => i.id === E.config.ia)?.nombre || tr("tu IA");
  /** El «mes» de la persona: calendario o de sueldo a sueldo (Ajustes → Tu mes empieza). Se calcula una vez por pintada. */
  function per() {
    if (E._per === undefined) E._per = periodoConfig(E.config.inicio_mes, (E.compromisos && E.compromisos.compromisos) || [], E.movimientos, E.hoy, E.presupuesto.moneda || E.config.moneda || "CLP");
    return E._per;
  }
  const periodoHoy = () => periodoDe(E.hoy, per());
  const mesesConDatos = () => periodosConDatos(E.movimientos, per());
  const mesesCompletos = () => mesesConDatos().filter((m) => m < periodoHoy()).slice(-3);

  function toast(texto) {
    const t = $("#toast");
    t.textContent = tr(texto);
    t.classList.add("visible");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => t.classList.remove("visible"), 2200);
  }

  /** Markdown mínimo y seguro (todo se escapa): ### títulos, listas y **negritas**. */
  function mdHTML(texto) {
    const linea = (l) => esc(l).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    const iconos = { "Lo que va bien": "✅", "Ojo con": "👀", "Para esta semana": "🎯", "What's going well": "✅", "Watch out for": "👀", "This week": "🎯" };
    let html = "", lista = false;
    const cerrar = () => { if (lista) { html += "</ul>"; lista = false; } };
    for (const l of String(texto || "").split("\n")) {
      let m;
      if ((m = l.match(/^###\s+(.+)/))) { cerrar(); html += `<h3>${iconos[m[1].trim()] ? `<span aria-hidden="true">${iconos[m[1].trim()]}</span>` : ""}${linea(m[1])}</h3>`; }
      else if ((m = l.match(/^\s*[-*•]\s+(.+)/))) { if (!lista) { html += "<ul>"; lista = true; } html += `<li>${linea(m[1])}</li>`; }
      else if (!l.trim()) cerrar();
      else { cerrar(); html += `<p>${linea(l)}</p>`; }
    }
    cerrar();
    return html;
  }

  // ───────────── Pintar ─────────────
  function render() {
    const raiz = $("#app");
    const scroll = $(".principal-area")?.scrollTop || 0, scrollPagina = window.scrollY || 0;
    const activo = document.activeElement, idActivo = activo?.id, cursor = activo?.selectionStart;
    const scrollChat = $(".chat-cuerpo")?.scrollTop;
    E._per = undefined;
    raiz.innerHTML = `<div class="app">${lateral()}<main class="principal-area">${avisoActualizacion()}${principal()}</main></div>${E.picker ? pickerHTML() : ""}${avisoRegla()}${dialogos()}`;
    traducirDOM(raiz);
    const area = $(".principal-area"); if (area) area.scrollTop = scroll;
    const chat = $(".chat-cuerpo");
    if (chat) { if (E.chat.bajar || scrollChat == null) { chat.scrollTop = chat.scrollHeight; E.chat.bajar = false; } else chat.scrollTop = scrollChat; }
    if (scrollPagina && window.scrollY !== scrollPagina) window.scrollTo(0, scrollPagina);
    if (idActivo) { const el = document.getElementById(idActivo); if (el) { el.focus(); if (cursor != null && el.setSelectionRange) try { el.setSelectionRange(cursor, cursor); } catch {} } }
    // En la pantalla de idioma el foco parte en el sugerido: Enter ya elige.
    if (E.bv === 0 && !E.importar && !E.conectar && !document.activeElement?.closest(".dialogo")) $(`#bv-idioma-${idiomaDelSistema()}`)?.focus();
  }

  // Iconos de línea (1,8 px, sin relleno): uno por sección y por cada cosa que se puede agregar.
  const ICONOS = {
    inicio: '<path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1z" />',
    movimientos: '<path d="M4 7h16M4 12h16M4 17h10" />',
    compromisos: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5" /><path d="M3.5 10h17M8 3v4M16 3v4" /><path d="m9 15 2 2 4-4" />',
    mas: '<circle cx="5.5" cy="12" r="1.3" /><circle cx="12" cy="12" r="1.3" /><circle cx="18.5" cy="12" r="1.3" />',
    agregar: '<path d="M12 5v14M5 12h14" />',
    enviar: '<path d="M12 19V5M5.5 11.5 12 5l6.5 6.5" />',
    cartola: '<path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10A.5.5 0 0 1 7 20z" /><path d="M14 3.5V8h4M9.5 12.5h5M9.5 16h5" />',
    repetir: '<path d="M17 3.5 20.5 7 17 10.5" /><path d="M3.5 12V10a3 3 0 0 1 3-3h14M7 20.5 3.5 17 7 13.5" /><path d="M20.5 12v2a3 3 0 0 1-3 3h-14" />',
    presupuesto: '<circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r=".8" />',
    consejos: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" /><path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z" />',
    conexiones: '<path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0z" /><path d="M12 16v5" />',
    ajustes: '<path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" />',
    ordenar: '<path d="M3.5 12.5V5a1.5 1.5 0 0 1 1.5-1.5h7.5l8 8a1.5 1.5 0 0 1 0 2.1l-6.4 6.4a1.5 1.5 0 0 1-2.1 0z" /><circle cx="8" cy="8" r="1.4" />',
  };
  const icono = (id, tam = 22) => `<svg viewBox="0 0 24 24" width="${tam}" height="${tam}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONOS[id]}</svg>`;
  /** Cuatro secciones (ley de Hick) y una sola acción para agregar. En celular, barra inferior fija con «+» al centro (zona del pulgar);
   *  en escritorio, barra lateral con «+ Agregar» arriba. Por ordenar vive en Movimientos; Conexiones, Presupuesto y Consejos en Más. */
  const SECCIONES = [["resumen", "Inicio", "inicio"], ["movimientos", "Movimientos", "movimientos"], ["compromisos", "Pagos", "compromisos"], ["mas", "Más", "mas"]];
  const SECCION_DE = { ordenar: "movimientos", presupuesto: "mas", consejos: "mas", conexiones: "mas" };
  function lateral() {
    const sinCat = E.movimientos.filter((m) => !m.categoria).length;
    const atrasados = listaCompromisos().length ? estadoDelMes(periodoHoy()).items.filter((i) => i.estado === "atrasado" && i.signo === "gasto").length : 0;
    const actual = SECCION_DE[E.vista] || E.vista;
    const marca = (id) => (id === "movimientos" && sinCat ? `<span class="contador" title="${esc(tr("Sin categoría"))}" data-sin-traducir>${sinCat}</span>`
      : id === "compromisos" && atrasados ? `<span class="contador alerta-punto" title="${esc(tr(atrasados === 1 ? "1 pago atrasado" : "Pagos atrasados"))}" data-sin-traducir>${atrasados}</span>`
        : id === "mas" && conexionesConError() ? `<span class="contador alerta-punto" title="Una conexión necesita atención">!</span>` : "");
    const item = ([id, nombre, ico]) => `<button class="nav-item" data-vista="${id}" ${actual === id ? 'aria-current="page"' : ""}>
      <span class="ico">${icono(ico)}${marca(id)}</span><span class="nav-nombre">${nombre}</span></button>`;
    return `<aside class="lateral">
      <div class="cabeza"><span class="marca">${LOGO}<span>Alcancía</span></span></div>
      <nav class="nav" aria-label="Secciones">${item(SECCIONES[0])}${item(SECCIONES[1])}
        <button class="nav-agregar" data-accion="agregar" aria-haspopup="dialog" aria-label="Agregar"><span class="ico">${icono("agregar")}</span><span class="nav-nombre">Agregar</span></button>
        ${item(SECCIONES[2])}${item(SECCIONES[3])}</nav>
    </aside>`;
  }

  /** «‹ Más» o «‹ Movimientos»: para volver desde una pantalla de segundo nivel (sobre todo en celular). */
  const volver = (vista, nombre) => `<button class="volver" data-vista="${vista}"><span aria-hidden="true">‹</span> <span>${nombre}</span></button>`;

  function selectorMes() {
    const meses = mesesConDatos();
    const primero = meses[0] || E.mes, ultimo = periodoHoy();
    return `<div class="selector-mes" role="group" aria-label="Mes">
      <button data-mes="${sumarMes(E.mes, -1)}" ${E.mes <= primero ? "disabled" : ""} aria-label="Mes anterior" title="Mes anterior">‹</button>
      <span data-sin-traducir>${esc(nombreMes(E.mes))}${per() ? (([a, b]) => `<small>${esc(fechaCorta(a))} – ${esc(fechaCorta(b))}</small>`)(rango(E.mes, per())) : ""}</span>
      <button data-mes="${sumarMes(E.mes, 1)}" ${E.mes >= ultimo ? "disabled" : ""} aria-label="Mes siguiente" title="Mes siguiente">›</button></div>`;
  }

  function principal() {
    if (E.vista === "mas") return vistaMas();
    if (E.vista === "conexiones") return vistaConexiones();
    if (E.vista === "compromisos") return vistaCompromisos();
    if (!E.movimientos.length && E.vista !== "presupuesto") return vacio();
    if (E.vista === "movimientos") return vistaMovimientos();
    if (E.vista === "ordenar") return vistaOrdenar();
    if (E.vista === "presupuesto") return vistaPresupuesto();
    if (E.vista === "consejos") return vistaConsejos();
    return vistaResumen();
  }

  function vacio() {
    return `<div class="vacio">${LOGO.replace('class="logo"', 'class="logo" style="width:64px;height:64px"')}
      <h1>Empecemos a medirnos</h1>
      <p>Alcancía junta tus cartolas en un solo lugar, ordena tus gastos y te avisa a tiempo cuando algo se está pasando.</p>
      <div class="pasos-vacio">
        <div><b>1</b><span>Descarga la cartola de tu banco o billetera (CSV, Excel o PDF) desde su página web.</span></div>
        <div><b>2</b><span>Agrégala aquí: se lee en tu computador y no se duplica si la vuelves a subir.</span></div>
        <div><b>3</b><span>Tu IA pone las categorías y te dice qué va bien y a qué ponerle ojo.</span></div>
      </div>
      <div class="acciones-vacio"><button class="boton principal" data-accion="importar">＋ <span>Agregar mi primera cartola</span></button>
        <button class="boton" data-vista="conexiones">🔌 <span>Conectar una cuenta</span></button></div></div>`;
  }

  // ───────────── Más: lo que se usa de vez en cuando, en una lista simple ─────────────
  function vistaMas() {
    const conectadas = Object.values(E.conexiones || {}).filter((c) => c.conectado).length + (E.vigilar && E.vigilar.activo ? 1 : 0);
    const estadoCon = conexionesConError() ? `<small class="rojo-txt">Una conexión necesita atención</small>`
      : conectadas ? `<small data-sin-traducir>${T(conectadas === 1 ? "1 activa" : "{n} activas", { n: conectadas })}</small>` : `<small>Que tus movimientos lleguen solos.</small>`;
    const tope = Object.values(E.presupuesto.mensual || {}).filter((v) => v > 0).reduce((a, b) => a + b, 0);
    const ultimo = E.consejos[0];
    const fila = (attr, ico, titulo, detalle) => `<button class="fila-mas" ${attr}><span class="ico">${icono(ico)}</span><span class="txt"><b>${titulo}</b>${detalle}</span><span class="cf-flecha" aria-hidden="true">›</span></button>`;
    return `<div class="contenido"><div class="encabezado"><h1>Más</h1></div>
      <nav class="lista-mas" aria-label="Más">
        ${fila('data-vista="conexiones"', "conexiones", "Conexiones", estadoCon)}
        ${fila('data-vista="presupuesto"', "presupuesto", "Presupuesto", tope ? `<small data-sin-traducir>${T("{x} al mes, por categoría", { x: esc(dinero(tope)) })}</small>` : `<small>Cuánto quieres gastar como máximo en cada cosa.</small>`)}
        ${fila('data-vista="consejos"', "consejos", "Consejos", ultimo ? `<small data-sin-traducir>${T("Los últimos, del {f}", { f: esc(fechaCorta(ultimo.fecha)) })}</small>` : `<small data-sin-traducir>${T("Lo que {ia} ve en tus números", { ia: esc(nombreIA()) })}</small>`)}
        ${fila('data-accion="ajustes"', "ajustes", "Ajustes", `<small>Tu IA, país, tu mes, respaldo e idioma.</small>`)}</nav>
      <footer class="acerca"><p>${frase("**Tus datos son tuyos.** Todo queda en tu computador.", {})}</p>
        <p data-sin-traducir>${T("Alcancía {v} · Gratis y de código abierto (AGPL-3.0).", { v: esc(E.version) })}</p>
        <div class="enlaces"><a href="#" data-enlace="${ENLACES.sitio}">Sitio web</a><a href="#" data-enlace="${ENLACES.codigo}">Código</a><a href="#" data-enlace="${ENLACES.comunidad}">Comunidad</a></div></footer></div>`;
  }

  // ───────────── Conexiones: APIs oficiales con una llave de la persona, y la carpeta de descargas ─────────────
  const nombrePais = (id) => tr((PAISES.find((p) => p[0] === id) || [id, id])[1]);
  const conexionesConError = () => Object.values(E.conexiones || {}).some((c) => c.conectado && c.error);
  function hace(iso) {
    if (!iso) return "";
    const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (!(min >= 0)) return "";
    if (min < 2) return tr("recién");
    if (min < 60) return T("hace {n} min", { n: min });
    const h = Math.round(min / 60);
    return h < 24 ? T("hace {n} h", { n: h }) : T("hace {n} días", { n: Math.round(h / 24) });
  }
  function tarjetaConector(c) {
    const est = E.conexiones[c.id] || {}, sinc = E.sincronizando[c.id];
    const paises = c.paises.includes("*") ? tr("Todo el mundo") : c.paises.join(" · ");
    let estado;
    if (sinc) estado = `<small>Trayendo movimientos…</small>`;
    else if (est.conectado && est.error) estado = `<small class="error-txt" data-sin-traducir>${esc(est.error)}</small>`;
    else if (est.conectado && est.esperando) estado = `<small>${frase("{s} está preparando tus movimientos. Llegan en la próxima revisión.", { s: esc(c.nombre) })}</small>`;
    else if (est.conectado) estado = `<small class="ok-txt">${est.ultima ? frase("✓ Conectado · revisado {h}", { h: esc(hace(est.ultima)) }) : "✓ Conectado"}</small>`;
    else estado = `<small data-sin-traducir>${esc(paises)}</small>`;
    const botones = est.conectado
      ? `<button class="boton" data-sincronizar="${esc(c.id)}" ${sinc ? "disabled" : ""}>Revisar ahora</button><button class="icono" data-desconectar="${esc(c.id)}" title="Desconectar" aria-label="Desconectar">✕</button>`
      : `<button class="boton principal" data-conectar="${esc(c.id)}">Conectar</button>`;
    return `<div class="conector ${est.conectado ? "conectado" : ""}"><div class="txt"><b><span data-sin-traducir>${esc(tr(c.nombre))}</span>${c.estado === "beta" ? `<span class="chip pronto" title="Funciona con la API oficial, pero aún falta que alguien lo pruebe con su cuenta real">Beta</span>` : ""}</b>${estado}</div>
      <div class="acciones">${botones}</div></div>`;
  }
  function vistaConexiones() {
    const pais = E.config.pais || "CL";
    const delPais = E.conectores.filter((c) => c.paises.includes(pais)), mundo = E.conectores.filter((c) => c.paises.includes("*"));
    const otros = E.conectores.filter((c) => !c.paises.includes(pais) && !c.paises.includes("*"));
    const v = E.vigilar || {};
    const recientes = (v.recientes || []).slice(0, 4).map((r) => `<li data-sin-traducir>${esc(r.archivo)} · ${r.resultado === "importado"
      ? esc(T(r.nuevos === 1 ? "1 movimiento nuevo" : "{n} movimientos nuevos", { n: r.nuevos })) : esc(tr("no la sé leer todavía"))}</li>`).join("");
    return `<div class="contenido">${volver("mas", "Más")}<div class="encabezado"><h1>Conexiones</h1></div>
      <p class="intro-vista">${frase("Que tus movimientos lleguen solos. Alcancía usa la conexión oficial de cada servicio con una llave que creas tú, y la guarda cifrada en tu computador. **Nunca te pide la clave de tu banco.**", {})}</p>
      <section class="tarjeta"><div class="fila sin-borde"><div class="txt"><b>📥 Cartolas que descargues</b>
        <small>Descargas la cartola desde tu banco, como siempre, y Alcancía la agrega sola apenas llega a tu carpeta de Descargas. Sirve para cualquier banco del mundo.</small></div>
        <label class="interruptor"><input type="checkbox" data-vigilar ${v.activo ? "checked" : ""}><span class="visual" aria-hidden="true"></span><span class="oculto-accesible">Importar solas las cartolas que descargue</span></label></div>
        ${v.activo && recientes ? `<ul class="recientes">${recientes}</ul>` : ""}</section>
      ${delPais.length ? `<h2 class="subtitulo">${frase("En {p}", { p: esc(nombrePais(pais)) })}</h2><div class="conectores">${delPais.map(tarjetaConector).join("")}</div>` : ""}
      ${mundo.length ? `<h2 class="subtitulo">En todo el mundo</h2><div class="conectores">${mundo.map(tarjetaConector).join("")}</div>` : ""}
      ${otros.length ? `<details class="otros-paises"><summary>${frase("Otros países ({n})", { n: otros.length })}</summary><div class="conectores">${otros.map(tarjetaConector).join("")}</div></details>` : ""}
      ${seccionIAExterna()}
      <section class="tarjeta suave"><b>¿Tu banco no aparece?</b><p>Casi ningún banco deja que una persona use su propia API todavía. Mientras, descarga la cartola (CSV, Excel, PDF u OFX) y activa «Cartolas que descargues»: es casi igual de automático. Cuando tu país tenga finanzas abiertas oficiales, Alcancía las va a sumar.</p>
        <a href="#" data-enlace="${ENLACES.comunidad}">Proponer una conexión en la comunidad</a></section></div>`;
  }
  function seccionIAExterna() {
    const lista = E.iaExterna || [];
    const instaladas = lista.filter((c) => c.instalado || c.conectado);
    const filas = instaladas.map((c) => {
      const ocupado = E.mcpOcupado[c.id], error = E.mcpError[c.id];
      const estado = error ? `<small class="error-txt" data-sin-traducir>${esc(error)}</small>`
        : c.conectado ? `<small class="ok-txt">${c.al_dia ? "✓ Conectada: ya puede consultar tus finanzas" : "Conectada (actualizando la ruta…)"}</small>`
          : `<small>Instalada en este computador</small>`;
      const boton = c.conectado ? `<button class="boton" data-mcp-quitar="${esc(c.id)}" ${ocupado ? "disabled" : ""}>Quitar</button>`
        : `<button class="boton principal" data-mcp="${esc(c.id)}" ${ocupado ? "disabled" : ""}>${ocupado ? "Conectando…" : "Conectar"}</button>`;
      return `<div class="fila"><div class="txt"><b data-sin-traducir>${esc(tr(c.nombre))}</b>${estado}</div>${boton}</div>`;
    }).join("");
    const alguna = lista.some((c) => c.conectado);
    return `<h2 class="subtitulo">Tu IA, fuera de Alcancía</h2>
      <section class="tarjeta"><p class="intro-tarjeta">${frase("Conecta Alcancía con la IA que ya usas (Claude, ChatGPT o Gemini en tu computador) y pregúntale por tus finanzas desde ahí: **«¿cuánto gasté en comida este mes?»**, **«¿en qué se me va la plata?»**. Tu IA solo puede leer, nunca cambiar nada.", {})}</p>
        ${filas || `<p class="texto-suave">No encontré ninguna IA de escritorio en este computador. <a href="#" data-enlace="${ENLACES.guiaIA}">Cómo instalar una</a></p>`}
        ${alguna ? `<div class="candado" style="margin:14px 0 0"><span class="grande-ico" aria-hidden="true">💬</span><div>${frase("**Pruébalo:** abre tu IA y pregúntale «Según Alcancía, ¿cómo voy este mes?». Si usas la app de Claude, ciérrala y vuelve a abrirla la primera vez.", {})}</div></div>` : ""}
        <p class="nota-mcp">Cuando le preguntes, tu IA puede leer tus movimientos (fecha, descripción, monto y categoría), y lo que consulta viaja a tu proveedor de IA con tu cuenta, igual que si se lo escribieras. Alcancía no tiene servidores: todo corre en tu computador.</p></section>`;
  }
  /** Markdown mínimo para los pasos de los conectores: **negrita** y `código`. Todo lo demás se escapa. */
  const mdCorto = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
  function dialogoConectar() {
    const c = E.conectores.find((x) => x.id === E.conectar.id);
    if (!c) return "";
    const k = E.conectar;
    const campos = c.campos.map((f) => `<label class="campo"><span data-sin-traducir>${esc(tr(f.etiqueta))}</span>
      <input class="entrada" type="${f.secreto ? "password" : "text"}" id="campo-${esc(f.id)}" data-campo="${esc(f.id)}" autocomplete="off" spellcheck="false" value="${esc(k.campos[f.id] || "")}" ${k.enviando ? "disabled" : ""}></label>`).join("");
    return `<h2 id="t-conectar">${frase("Conectar {s}", { s: esc(tr(c.nombre)) })}</h2>
      <ol class="pasos-conectar">${c.pasos.map((p) => `<li data-sin-traducir>${mdCorto(tr(p))}</li>`).join("")}</ol>
      ${c.enlace ? `<p><a href="#" data-enlace="${esc(c.enlace)}">${frase("Abrir la página de {s}", { s: esc(c.nombre) })} ↗</a></p>` : ""}
      ${c.nota ? `<p class="nota-conector" data-sin-traducir>${mdCorto(tr(c.nota))}</p>` : ""}
      <div class="campos-conectar">${campos}</div>
      <div class="candado"><span class="grande-ico" aria-hidden="true">🔐</span><div>La llave se guarda cifrada en el llavero de tu computador y solo se usa para leer tus movimientos. Puedes desconectar cuando quieras.</div></div>
      ${k.error ? `<p class="error-txt" data-sin-traducir>${esc(k.error)}</p>` : ""}
      <div class="pie-dialogo"><button class="boton" data-accion="cerrar-conectar">Cancelar</button><button class="boton principal" data-accion="enviar-conectar" ${k.enviando ? "disabled" : ""}>${k.enviando ? "Revisando…" : "Conectar"}</button></div>`;
  }

  /** Barras de los últimos meses (HTML y CSS, sin librerías) con la línea del presupuesto. El dibujo es solo para la vista:
   *  los lectores de pantalla leen el texto de arriba y la tabla oculta, con los mismos números. */
  function bloqueHistoria(h, titulo, compacto = false) {
    const ult = h.meses[h.meses.length - 1];
    const max = Math.max(1, h.tope, ...h.meses.map((m) => Math.max(m.gastado, m.proyeccion || 0)));
    const alto = (v) => (v / max * 80).toFixed(1);
    let texto;
    if (ult.en_curso && ult.proyeccion != null) texto = frase("A este ritmo cierras el mes en **{x}**.", { x: esc(dinero(ult.proyeccion)) });
    else if (ult.en_curso) texto = frase("Llevas **{x}** este mes.", { x: esc(dinero(ult.gastado)) });
    else texto = frase("En {m} gastaste **{x}**.", { m: esc(nombreMes(ult.mes)), x: esc(dinero(ult.gastado)) });
    if (h.promedio == null) texto += " " + frase("Cuando tengas más meses, aquí vas a ver cómo vas comparado con ellos.", {});
    else if (h.promedio > 0 && !(ult.en_curso && ult.proyeccion == null)) {
      const v = ult.proyeccion ?? ult.gastado, pct = Math.round(Math.abs(v - h.promedio) / h.promedio * 100), p = esc(dinero(h.promedio));
      texto += " " + (pct >= 5 && v > h.promedio ? frase("Es {n}% más que tu promedio de los meses anteriores ({x}).", { n: pct, x: p })
        : pct >= 5 ? frase("Es {n}% menos que tu promedio de los meses anteriores ({x}).", { n: pct, x: p })
          : frase("Es parecido a tu promedio de los meses anteriores ({x}).", { x: p }));
    }
    const sobre = (m) => h.tope > 0 && m.gastado > h.tope;
    const cols = h.meses.map((m) => `<div class="pila ${m.en_curso ? "actual" : ""} ${m.con_datos ? "" : "sin-datos"} ${sobre(m) ? "sobre" : ""}">
        ${m.proyeccion > m.gastado ? `<i class="proy" style="height:${alto(m.proyeccion)}%"></i>` : ""}<i class="real" style="height:${alto(m.gastado)}%"></i>
        <span class="cifra-col" style="bottom:calc(${alto(Math.max(m.gastado, m.proyeccion || 0))}% + 3px)">${m.con_datos ? esc(dineroCorto(m.gastado)) : "—"}</span></div>`).join("");
    const eje = h.meses.map((m) => `<span class="${m.en_curso ? "actual" : ""}">${esc(mesCorto(m.mes))}</span>`).join("");
    const hayProy = h.meses.some((m) => m.proyeccion > m.gastado);
    const filas = h.meses.map((m) => `<tr><th scope="row" data-sin-traducir>${esc(nombreMes(m.mes))}${m.en_curso ? " " + esc(tr("(en curso)")) : ""}</th>
        <td data-sin-traducir>${m.con_datos ? esc(dinero(m.gastado)) : esc(tr("Sin datos"))}</td><td data-sin-traducir>${m.proyeccion != null ? esc(dinero(m.proyeccion)) : "—"}</td></tr>`).join("");
    return `<p class="historia-texto">${texto}</p>
      <div class="grafico ${compacto ? "compacto" : ""}" style="--n:${h.meses.length}" aria-hidden="true">
        <div class="plot" data-sin-traducir>${cols}${h.tope ? `<div class="tope-linea" style="bottom:${alto(h.tope)}%"></div>` : ""}</div>
        <div class="eje" data-sin-traducir>${eje}</div></div>
      <div class="leyenda" aria-hidden="true"><span><i class="m-real"></i>Gastado</span>${hayProy ? `<span><i class="m-proy"></i>Proyección del mes</span>` : ""}
        ${h.tope ? `<span><i class="m-tope"></i>${frase("Presupuesto: {x}", { x: esc(dinero(h.tope)) })}</span>` : ""}</div>
      <div class="oculto-accesible"><table><caption data-sin-traducir>${titulo}</caption><thead><tr><th scope="col">Mes</th><th scope="col">Gastado</th><th scope="col">Proyección</th></tr></thead>
        <tbody>${filas}</tbody></table>${h.tope ? `<p>${frase("Presupuesto: {x}", { x: esc(dinero(h.tope)) })}</p>` : ""}</div>`;
  }

  // ───────────── Resumen: tres números (lo que tienes, lo que gastaste, lo que debes) ─────────────
  /** Lo que falta pagar, en una sola línea bajo la cifra protagonista: rojo solo si está atrasado; verde si estás al día. */
  function lineaAlDia() {
    if (!listaCompromisos().length) return "";
    // Lo que se paga solo no se recuerda: solo aparece si pasaron los días de gracia y no vimos el cargo.
    const todos = estadoDelMes(periodoHoy()).items.filter((i) => i.signo === "gasto" && i.estado !== "pagado");
    const pend = todos.filter((i) => !seCobraSolo(i)).sort((a, b) => ORDEN_ESTADO[a.estado] - ORDEN_ESTADO[b.estado] || cmp(a.vence, b.vence));
    if (!pend.length) return `<div class="al-dia ok" role="status"><span class="punto" aria-hidden="true"></span><p>${todos.length ? frase("**Estás al día.** Lo que queda se paga solo.", {})
      : frase("**Estás al día.** Pagaste todo lo de este mes.", {})}</p></div>`;
    const p = pend[0], c = esc(p.nombre), x = montoCorto(p);
    let texto;
    if (p.estado === "atrasado" && p.modo_pago === "automatico") texto = p.dias === 1 ? T("No vimos el cargo de **{c}**: {x}, venció ayer.", { c, x }) : T("No vimos el cargo de **{c}**: {x}, venció hace {n} días.", { c, x, n: p.dias });
    else if (p.estado === "atrasado") texto = p.dias === 1 ? T("Te falta pagar **{c}**: {x}, venció ayer.", { c, x }) : T("Te falta pagar **{c}**: {x}, vencido hace {n} días.", { c, x, n: p.dias });
    else if (p.estado === "hoy") texto = T("Te falta pagar **{c}**: {x}, vence hoy.", { c, x });
    else texto = p.dias === 1 ? T("Te falta pagar **{c}**: {x}, vence mañana.", { c, x }) : T("Te falta pagar **{c}**: {x}, vence en {n} días.", { c, x, n: p.dias });
    const sumables = pend.filter((i) => i.moneda === monedaPrincipal());
    const mas = pend.length > 1 ? " " + T(pend.length === 2 ? "Y 1 cosa más ({x} en total)." : "Y {n} cosas más ({x} en total).", { n: pend.length - 1,
      x: (sumables.some((i) => i.rango) ? "≈ " : "") + esc(dinero(sumables.reduce((a, i) => a + i.monto, 0))) }) : "";
    return `<div class="al-dia ${p.estado === "atrasado" ? "atrasado" : "pendiente"}" role="status"><span class="punto" aria-hidden="true"></span>
      <p data-sin-traducir>${texto}${mas}</p>
      <div class="acciones"><button class="boton sutil" data-comp-pagado="${esc(`${p.id}|${p.periodo}`)}">Ya lo pagué</button>${pend.length > 1 ? `<button class="boton sutil" data-cifra-abrir="debes">Ver todo</button>` : ""}</div></div>`;
  }

  /** Cuándo empieza tu mes. `pregunta`: lo que pide algo (¿cuándo te pagan?, ¿aún no te pagan?) y va en «Pendientes»;
   *  `info`: lo que detecté de tu sueldo, que va en la explicación de la cifra protagonista. */
  function lineaMes() {
    const im = E.config.inicio_mes, p = per();
    if (!im) return { pregunta: `<div class="linea-mes"><p>${frase("¿Cuándo te pagan? Así tu mes empieza ese día.", {})}</p><button class="boton sutil" data-accion="ajustes-mes">Elegir</button></div>`, info: "" };
    if (!p) return { pregunta: "", info: "" };
    const sueldoC = listaCompromisos().find((c) => c.activo !== false && c.tipo === "ingreso" && c.frecuencia === "mensual" && c.categoria === "sueldo");
    const prox = proximoSueldo(p, E.hoy, E.feriados || []);
    const pregunta = sueldoC && prox && prox.atrasado && leerLocal("alcancia.sueldoNoHoy") !== E.hoy ? preguntaSueldo(sueldoC, prox) : "";
    if (!im.auto) return { pregunta, info: "" };
    const inicio = rango(periodoHoy(), p)[0], f = esc(fechaCorta(inicio));
    const texto = (p.llegadas || []).includes(inicio) ? frase("Tu mes va desde que llegó tu sueldo ({f}).", { f }) : frase("Tu mes va desde el {f}, el día que suele llegar tu sueldo.", { f });
    return { pregunta, info: `<div class="linea-mes"><p>${texto}</p><button class="boton sutil" data-accion="ajustes-mes">Cambiar</button></div>` };
  }
  /** «¿Aún no te pagan?»: suave, sin aviso del sistema. «Todavía no» no insiste hoy; «Ya me pagaron» busca el movimiento. */
  function preguntaSueldo(c, prox) {
    const f = esc(fechaLarga(prox.fecha));
    if (E.sueldoPregunta !== "pagaron") {
      return `<div class="linea-mes pregunta" role="status"><p>${frase("¿Aún no te pagan? Lo esperaba el {f}.", { f })}</p>
        <div class="acciones"><button class="boton sutil" data-sueldo="no">Todavía no</button><button class="boton" data-sueldo="pagaron">Ya me pagaron</button>
        <button class="icono" data-sueldo="cerrar" aria-label="${esc(tr("Cerrar"))}" title="${esc(tr("Cerrar"))}" data-sin-traducir>×</button></div></div>`;
    }
    const cand = candidatoSueldo(prox);
    if (cand && E.sueldoCandidatoNo !== cand.id) {
      return `<div class="linea-mes pregunta" role="status"><p>${frase("¿Es este? {d} · {x} · {f}", { d: esc(nombreComercio(cand.descripcion)), x: esc(dinero(cand.monto, cand.moneda || monedaPrincipal())), f: esc(fechaCorta(cand.fecha)) })}</p>
        <div class="acciones"><button class="boton principal" data-sueldo="es" data-sueldo-mov="${esc(cand.id)}">Sí, es mi sueldo</button><button class="boton sutil" data-sueldo="noes" data-sueldo-mov="${esc(cand.id)}">No es este</button></div></div>`;
    }
    const conectados = E.conectores.filter((k) => E.conexiones[k.id]?.conectado);
    return `<div class="linea-mes pregunta" role="status"><p>${frase("Agrega tu cartola o revisa tus cuentas conectadas para verlo.", {})}</p>
      <div class="acciones"><button class="boton" data-accion="importar">Agregar movimientos</button>
      ${conectados.map((k) => `<button class="boton sutil" data-sincronizar="${esc(k.id)}">${frase("Revisar {s}", { s: esc(tr(k.nombre)) })}</button>`).join("")}
      <button class="boton sutil" data-sueldo="hoy">Márcalo como recibido hoy</button></div></div>`;
  }
  /** El ingreso más probable de ser el sueldo que no se reconoció: el más grande desde 10 días antes de la fecha esperada. */
  function candidatoSueldo(prox) {
    const neutras = new Set(E.categorias.filter((c) => c.tipo === "neutro").map((c) => c.id)), desde = sumarDias(prox.fecha, -10);
    const usados = new Set(listaCompromisos().flatMap((c) => Object.values(c.pagos || {}).map((p) => p.movimiento).filter(Boolean)));
    return E.movimientos.filter((m) => m.monto > 0 && m.fecha >= desde && m.fecha <= E.hoy && !neutras.has(m.categoria) && m.categoria !== "transferencia" && !usados.has(m.id))
      .sort((a, b) => b.monto - a.monto || cmp(a.fecha, b.fecha))[0] || null;
  }
  function leerLocal(k) { try { return localStorage.getItem(k); } catch { return null; } }
  function guardarLocal(k, v) { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento: solo por esta vez */ } }
  /** Marca el sueldo como recibido ese día (el periodo parte ahí). */
  function sueldoRecibido(fecha) {
    const c = listaCompromisos().find((x) => x.activo !== false && x.tipo === "ingreso" && x.frecuencia === "mensual" && x.categoria === "sueldo");
    if (!c) return;
    const o = vencimientos(c, sumarDias(E.hoy, 7)).filter((v) => !(c.pagos || {})[v.periodo]?.como).pop();
    if (!o) return;
    c.pagos = { ...(c.pagos || {}), [o.periodo]: { como: "manual", fecha } };
    host.enviar("compromiso", { accion: "pagado", id: c.id, periodo: o.periodo, hoy: fecha });
    E.sueldoPregunta = null; E._per = undefined; E.mes = periodoHoy();
    toast(T("Listo: tu mes parte el {f}", { f: fechaCorta(fecha) })); render();
  }

  /** Una de las tres cifras de segundo nivel (fila compacta): etiqueta chica arriba, monto abajo. Tocar abre su desglose. */
  function filaCifra(id, etiqueta, num, sub = "") {
    const abierta = E.cifra === id;
    return `<button type="button" class="cifra-fila ${id} ${abierta ? "abierta" : ""}" data-cifra="${id}" aria-expanded="${abierta}" ${abierta ? 'aria-controls="desglose"' : ""}>
      <span class="cf-etiqueta">${etiqueta}</span><span class="cf-num">${num}</span>${sub ? `<span class="cf-sub">${sub}</span>` : ""}</button>`;
  }
  /** ¿Hay movimientos en más de una moneda? Solo entonces se muestra el código de la moneda (una vez, en el encabezado). */
  const variasMonedas = () => { const m = monedaPrincipal(); return E.movimientos.some((x) => x.moneda && x.moneda !== m); };
  const cifraGrande = (v, moneda = monedaPrincipal()) => `<span data-sin-traducir>${esc(dinero(v, moneda))}</span>`;

  /** La pregunta real: ¿cuánto me queda hasta el sueldo? Lo que tienes − lo que falta pagar este periodo (si no hay saldo
   *  conocido: lo que entró − lo gastado − lo que falta pagar), los días que faltan y cuánto da por día. Solo presentación:
   *  usa las mismas funciones de siempre (loQueTienes, resumen, estadoCompromisos, proximoSueldo). */
  function cuantoQueda(r, t) {
    const e = listaCompromisos().length ? estadoDelMes(periodoHoy()) : null;
    const falta = e ? e.pendiente_max : 0, aprox = !!(e && e.aprox);
    let base;
    if (t.total != null) base = t.total;
    else if (r.ingresos > 0) base = r.ingresos - r.gastado;
    else return null;
    const p = per(), prox = p ? proximoSueldo(p, E.hoy, E.feriados || []) : null;
    const sueldo = !!(prox && prox.fecha > E.hoy);
    const hasta = sueldo ? prox.fecha : sumarDias(rango(periodoHoy(), p)[1], 1);
    const dias = Math.max(1, diasEntre(E.hoy, hasta)), queda = Math.round(base - falta);
    return { queda, falta, base, fuente: t.total != null ? "tienes" : "mes", aprox, dias, hasta, sueldo, porDia: queda > 0 ? Math.floor(queda / dias) : 0, r };
  }
  /** El ritmo del mes, en una línea (dentro de la cifra protagonista). Rojo solo si te pasas del presupuesto. */
  function lineaRitmo(r, enCurso) {
    if (enCurso && r.proyeccion != null) {
      if (!r.presupuesto) return `<p class="ritmo">${frase("A este ritmo cierras el mes en **{x}**.", { x: esc(dinero(r.proyeccion)) })}</p>`;
      const dif = r.presupuesto - r.proyeccion;
      return dif >= 0 ? `<p class="ritmo">${frase("A este ritmo terminas el mes en {x}: te sobrarían {y}.", { x: esc(dinero(r.proyeccion)), y: esc(dinero(dif)) })}</p>`
        : r.proyeccion <= r.presupuesto * 1.1 ? `<p class="ritmo">${frase("A este ritmo terminas justo en el límite: {x}.", { x: esc(dinero(r.proyeccion)) })}</p>`
          : `<p class="ritmo mal">${frase("A este ritmo terminas el mes en {x}: {y} sobre tu presupuesto.", { x: esc(dinero(r.proyeccion)), y: esc(dinero(-dif)) })}</p>`;
    }
    if (!enCurso && r.presupuesto && r.dia) {
      const dif = r.presupuesto - r.gastado;
      return dif >= 0 ? `<p class="ritmo">${frase("Terminaste {x} bajo tu presupuesto. ¡Bien hecho!", { x: esc(dinero(dif)) })}</p>`
        : `<p class="ritmo mal">${frase("Te pasaste {x} del presupuesto. El próximo mes se puede.", { x: esc(dinero(-dif)) })}</p>`;
    }
    return "";
  }
  /** La escala de días del periodo (como el dial de una radio): lo que ya pasó, hoy y lo que falta hasta el sueldo. Solo dibujo. */
  function escalaDias(q) {
    const [inicio] = rango(periodoHoy(), per()), total = Math.max(1, diasEntre(inicio, q.hasta)), hoy = Math.min(total, diasEntre(inicio, E.hoy) + 1);
    if (total > 45) return "";
    return `<div class="escala" aria-hidden="true" style="--n:${total}">${Array.from({ length: total }, (_, i) => `<i class="${i + 1 < hoy ? "paso" : i + 1 === hoy ? "hoy" : ""}"></i>`).join("")}</div>`;
  }
  /** La cifra protagonista (arriba a la izquierda, el primer lugar donde se mira). */
  function heroe(r, t, enCurso) {
    const ritmo = lineaRitmo(r, enCurso);
    const codigo = variasMonedas() ? ` <span class="codigo-moneda" data-sin-traducir>${esc(monedaPrincipal())}</span>` : "";
    if (!enCurso) {
      const num = `<span class="heroe-num" data-sin-traducir>${esc(dinero(r.gastado))}${codigo}</span>`;
      const neto = r.ingresos - r.gastado;
      const sub = r.ingresos ? frase(neto >= 0 ? "Entró {i} · te sobró {s}" : "Entró {i} · te faltó {s}", { i: esc(dinero(r.ingresos)), s: esc(dinero(Math.abs(neto))) }) : "";
      return `<section class="heroe"><p class="heroe-frase" data-sin-traducir>${T("En {m} gastaste {x}", { m: esc(nombreMes(E.mes)), x: num })}</p>
        ${sub ? `<p class="heroe-sub">${sub}</p>` : ""}${ritmo}</section>`;
    }
    const q = cuantoQueda(r, t);
    if (!q) {
      const num = `<span class="heroe-num" data-sin-traducir>${esc(dinero(r.gastado))}${codigo}</span>`;
      return `<section class="heroe"><p class="heroe-frase" data-sin-traducir>${T("Llevas gastado {x}", { x: num })}</p>
        <p class="heroe-sub">${frase("Anota cuánto tienes en tus cuentas y te digo cuánto te queda hasta tu sueldo.", {})}</p>
        <div class="acciones"><button class="boton" data-cifra-abrir="tienes">Anotar lo que tengo</button></div>${ritmo}</section>`;
    }
    const negativo = q.queda < 0, abierta = E.cifra === "queda";
    const num = `<span class="heroe-num ${negativo ? "rojo-txt" : ""}" data-sin-traducir>${q.aprox ? '<span class="aprox-signo">≈</span>' : ""}${esc(dinero(Math.abs(q.queda)))}${codigo}</span>`;
    const plantilla = negativo ? (q.sueldo ? "Te faltan {x} para llegar a tu sueldo" : "Te faltan {x} para llegar a fin de mes") : (q.sueldo ? "Te quedan {x} hasta tu sueldo" : "Te quedan {x} hasta fin de mes");
    const sub = negativo ? frase(q.dias === 1 ? "1 día" : "{n} días", { n: q.dias })
      : frase(q.dias === 1 ? "1 día · ~{y} por día" : "{n} días · ~{y} por día", { n: q.dias, y: esc(dinero(q.porDia)) });
    return `<section class="heroe"><button type="button" class="heroe-boton" data-cifra="queda" aria-expanded="${abierta}" ${abierta ? 'aria-controls="desglose"' : ""}>
        <span class="heroe-frase" data-sin-traducir>${T(plantilla, { x: num })}</span>
        <span class="heroe-sub">${sub}<span class="heroe-como">Cómo lo calculo</span></span>${escalaDias(q)}</button>${ritmo}</section>`;
  }
  /** Al tocar la cifra protagonista: el cálculo en simple, con lo que detecté de tu mes y el próximo sueldo. */
  function desgloseQueda(q, info) {
    const fila = (txt, v, clase = "") => `<div class="calculo-fila ${clase}"><span data-sin-traducir>${txt}</span><span class="valor" data-sin-traducir>${v}</span></div>`;
    const base = q.fuente === "tienes" ? fila(tr("Lo que tienes hoy"), esc(dinero(q.base)))
      : fila(tr("Lo que entró este mes"), esc(dinero(q.r.ingresos))) + fila(tr("Lo que gastaste"), esc(dinero(-q.r.gastado)));
    const p = per(), prox = p ? proximoSueldo(p, E.hoy, E.feriados || []) : null, n = prox ? diasEntre(E.hoy, prox.fecha) : -1;
    const sueldo = prox && n >= 0 ? `<p class="pista-sueldo">${frase(n === 0 ? "Tu sueldo debería llegar hoy ({f})." : n === 1 ? "Próximo sueldo: {f} (aprox.), mañana." : "Próximo sueldo: {f} (aprox.), en {n} días.", { f: esc(fechaLarga(prox.fecha)), n })}</p>` : "";
    return `<h2 class="desglose-titulo">Cómo lo calculo</h2>
      <div class="calculo">${base}
        ${fila(tr("Lo que falta pagar este mes"), (q.aprox ? "≈ " : "") + esc(dinero(-q.falta)))}
        ${fila(tr(q.queda < 0 ? "Te faltan" : "Te quedan"), (q.aprox ? "≈ " : "") + esc(dinero(q.queda)), "total")}
        ${q.queda > 0 ? fila(T(q.dias === 1 ? "Repartido en 1 día" : "Repartido en {n} días", { n: q.dias }), esc(dinero(q.porDia)), "sub") : ""}</div>
      ${sueldo}${info}
      <p class="nota-mcp">${q.fuente === "tienes" ? frase("Lo que tienes sale de tus cuentas; lo que falta pagar, de tus pagos de este mes.", {}) : frase("Aún no sé cuánto tienes en tus cuentas: uso lo que entró y lo que gastaste este mes.", {})}
        <button class="enlace" data-vista="compromisos">Ver tus pagos</button></p>`;
  }

  function vistaResumen() {
    const moneda = monedaPrincipal();
    const r = resumen(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias, per());
    const enCurso = E.mes === periodoHoy() && r.dia > 0 && r.dia <= r.dias_mes;
    const t = loQueTienes(E.cuentas, E.movimientos, moneda);
    const d = loQueDebes(listaCompromisos(), E.movimientos, E.hoy, moneda, per(), ufCfg(), E.palabrasAuto || []);
    const numTienes = t.total == null ? `<span class="cf-invita">Anotar</span>` : cifraGrande(t.total, moneda);
    const atrasados = d.partes.filter((p) => p.estado === "atrasado").length;
    const subDebes = atrasados ? `<span class="rojo-txt">${frase(atrasados === 1 ? "1 atrasado" : "{n} atrasados", { n: atrasados })}</span>` : "";
    const tres = `<section class="tres" aria-label="Tus tres números">
      ${filaCifra("tienes", "Lo que tienes", numTienes)}
      ${filaCifra("gastaste", "Lo que gastaste", cifraGrande(r.gastado, moneda))}
      ${filaCifra("debes", "Lo que debes", (d.aprox ? '<span class="aprox-signo" data-sin-traducir>≈</span>' : "") + cifraGrande(d.este_mes, moneda), subDebes)}</section>`;
    const lm = E.mes === periodoHoy() ? lineaMes() : { pregunta: "", info: "" };
    const q = enCurso ? cuantoQueda(r, t) : null;
    const desglose = E.cifra === "tienes" ? desgloseTienes(t) : E.cifra === "debes" ? desgloseDebes(d) : E.cifra === "gastaste" ? desgloseGasto(r)
      : E.cifra === "queda" && q ? desgloseQueda(q, lm.info) : "";
    const caja = desglose ? `<section class="tarjeta desglose" id="desglose">${desglose}</section>` : "";
    return `<div class="contenido resumen-simple"><div class="encabezado"><h1 class="oculto-accesible">Inicio</h1>${selectorMes()}</div>
      ${heroe(r, t, enCurso)}${E.mes === periodoHoy() ? lineaAlDia() : ""}${E.cifra === "queda" ? caja : ""}
      ${tres}${E.cifra !== "queda" ? caja : ""}
      ${enQueSeFue(r)}${pendientesHTML(lm.pregunta)}
      <button class="fila-consejos fila-chat" data-accion="abrir-chat" aria-haspopup="dialog"><span class="ico chanchito">${LOGO}</span><span>Pregúntale a Alcancía</span><span class="cf-flecha" aria-hidden="true">›</span></button>
      <button class="fila-consejos" data-vista="consejos"><span class="ico">${icono("consejos", 20)}</span><span>${frase("Pídele consejos a {ia} sobre este mes", { ia: esc(nombreIA()) })}</span><span class="cf-flecha" aria-hidden="true">›</span></button></div>`;
  }

  function desgloseTienes(t) {
    const fila = (c) => {
      const editando = E.saldoEdit && E.saldoEdit.cuenta === c.id;
      const b = c.base;
      let origen = "";
      if (b) {
        const f = esc(fechaCorta(b.fecha));
        origen = b.origen === "conector" ? T("Según {s}, el {f}", { s: esc(c.nombre), f }) : b.origen === "cartola" ? T("Según tu cartola del {f}", { f }) : T("Lo anotaste el {f}", { f });
        if (c.movimientos_despues) origen += " · " + T(c.movimientos_despues === 1 ? "más 1 movimiento después" : "más {n} movimientos después", { n: c.movimientos_despues });
      }
      const editor = `<form class="saldo-editor" data-saldo-form="${esc(c.id)}"><label class="oculto-accesible" data-sin-traducir for="saldo-${esc(c.id)}">${T("¿Cuánto tienes hoy en {c}?", { c: esc(c.nombre) })}</label>
        <input class="texto" id="saldo-${esc(c.id)}" inputmode="numeric" data-saldo-input="${esc(c.id)}" value="${esc(E.saldoEdit?.cuenta === c.id ? E.saldoEdit.texto : "")}" placeholder="${esc(tr("Monto de hoy"))}" data-sin-traducir>
        <button class="boton principal" type="submit">Guardar</button>${c.saldo != null ? `<button class="boton sutil" type="button" data-saldo-cancelar>Cancelar</button>` : ""}</form>`;
      return `<div class="cuenta-fila ${c.saldo == null ? "sin" : ""}">
        <div class="txt"><b data-sin-traducir>${esc(c.nombre)}</b>${c.saldo == null ? `<small data-sin-traducir>${T("¿Cuánto tienes hoy en {c}?", { c: esc(c.nombre) })}</small>` : `<small data-sin-traducir>${origen}</small>`}</div>
        ${c.saldo != null && !editando ? `<span class="valor" data-sin-traducir>${esc(dinero(c.saldo, c.moneda))}</span><button class="boton sutil" data-saldo-editar="${esc(c.id)}">Corregir</button>` : editor}</div>`;
    };
    const aviso = E.saldoAviso ? `<p class="saldo-aviso ${E.saldoAviso.cuadra ? "ok" : ""}" role="status" data-sin-traducir>${E.saldoAviso.texto}</p>` : "";
    const lista = t.cuentas.filter((c) => c.moneda === t.moneda || c.saldo != null);
    return `<h2 class="desglose-titulo">Lo que tienes hoy</h2>
      <p class="texto-suave intro-desglose">Lo que hay en tus cuentas. Si un servicio informa su saldo (como Mercado Pago), uso ese; si no, el que me anotes, y desde ahí sumo y resto tus movimientos.</p>
      ${aviso}${lista.length ? lista.map(fila).join("") : `<p class="texto-suave">Aún no tienes cuentas: agrega una cartola o conecta una cuenta.</p>`}
      <p class="nota-mcp">Lo que compras con tarjeta de crédito no sale de tu cuenta: va a «Lo que debes».</p>`;
  }

  /** «En qué se fue»: las 5 categorías donde más se fue, con su tope sutil. Tocar una abre sus movimientos. */
  function enQueSeFue(r) {
    const mensual = E.presupuesto.mensual || {};
    const ids = Object.keys(r.por_categoria).sort((a, b) => r.por_categoria[b] - r.por_categoria[a]);
    if (!ids.length) return `<section class="seccion-inicio"><h2 class="titulo-seccion">En qué se fue</h2><p class="texto-suave">Aún no hay gastos este mes.</p></section>`;
    const max = Math.max(1, ...Object.values(r.por_categoria));
    const ver = E.verTodasCat ? ids : ids.slice(0, 5);
    const filas = ver.map((id) => {
      const c = cat(id), g = r.por_categoria[id], tope = mensual[id] || 0;
      const alerta = r.alertas.find((a) => a.categoria === id);
      const clase = !id ? "falta" : alerta?.tipo === "pasado" ? "pasado" : alerta ? "ojo" : "";
      return `<button type="button" class="cat ${clase}" data-ir-cat="${esc(id)}"><span class="emoji" aria-hidden="true">${c.emoji}</span><span class="nombre" data-sin-traducir>${esc(nombreCat(c))}</span>
        <span class="monto" data-sin-traducir>${esc(dinero(g))}${tope ? ` <small>${T("de {x}", { x: esc(dinero(tope)) })}</small>` : ""}</span>
        <span class="barra ${clase}"><i style="width:${(tope ? Math.min(100, g / tope * 100) : g / max * 100).toFixed(1)}%"></i></span></button>`;
    }).join("");
    return `<section class="seccion-inicio"><div class="cabeza-seccion"><h2 class="titulo-seccion">En qué se fue</h2><button class="boton sutil" data-vista="presupuesto">Editar topes</button></div>
      ${filas}
      ${ids.length > 5 ? `<button class="enlace mas" data-accion="ver-todas-cat" aria-expanded="${!!E.verTodasCat}">${E.verTodasCat ? "Ver menos" : frase("Ver las {n} categorías", { n: ids.length })}</button>` : ""}</section>`;
  }
  /** Al tocar «Lo que gastaste»: cómo vas comparado con los últimos meses, y las notas de cómo se cuenta. */
  function desgloseGasto(r) {
    const h = historia(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias, null, 6, per());
    const hayCuotas = E.movimientos.some((m) => cuotasDe(m));
    return `<h2 class="desglose-titulo">Comparado con los últimos meses</h2>${bloqueHistoria(h, T("Gasto total de los últimos 6 meses"))}
      ${hayCuotas ? `<p class="nota-mcp">Las compras en cuotas con crédito cuentan por la cuota de cada mes, y las devoluciones se descuentan.</p>` : ""}
      ${r.otras_monedas ? `<p class="nota-mcp">${frase("{n} movimientos en otra moneda no entran en estas cuentas.", { n: r.otras_monedas })}</p>` : ""}`;
  }

  /** «Te deben»: préstamos que hiciste tú. Línea aparte: nunca se resta de lo que debes. */
  function teDebenHTML(d) {
    if (!d.te_deben || !d.te_deben.length) return "";
    return `<h3 class="grupo">Te deben</h3>${d.te_deben.map((t) => `<div class="debe-fila"><span class="emoji" aria-hidden="true">🤝</span>
      <div class="txt"><b data-sin-traducir>${esc(t.nombre)}</b><small data-sin-traducir>${[t.cuotas ? T(t.cuotas.quedan === 1 ? "le queda 1 cuota" : "le quedan {q} de {t} cuotas", { q: t.cuotas.quedan, t: t.cuotas.total }) : "",
        t.este_mes ? T("este mes {x}", { x: esc(dinero(t.este_mes)) }) : ""].filter(Boolean).join(" · ")}</small></div>
      <span class="valor ingreso" data-sin-traducir>${esc(dinero(t.monto))}</span></div>`).join("")}
      <div class="total-pres sub"><span>Te deben en total</span><span class="ingreso" data-sin-traducir>${esc(dinero(d.te_deben_total))}</span></div>
      <p class="nota-mcp">Lo que te deben va aparte: no se resta de lo que debes.</p>`;
  }
  function desgloseDebes(d) {
    if (!d.partes.length && d.te_deben && d.te_deben.length) return `<h2 class="desglose-titulo">Lo que debes</h2><p class="nada-debes">🎉 <span>No debes nada por ahora.</span></p>${teDebenHTML(d)}`;
    if (!d.partes.length) {
      return `<h2 class="desglose-titulo">Lo que debes</h2><p class="nada-debes">🎉 <span>No debes nada por ahora.</span></p>
        <p class="texto-suave">${listaCompromisos().length ? tr("Cuando algo de tus compromisos esté por vencer, aparece aquí.") : tr("Anota tus créditos, cuentas y suscripciones en Pagos y aquí ves lo que te falta pagar.")}</p>`;
    }
    // Por pagar este mes: cuentas y suscripciones, y la cuota del mes de cada crédito (su total va más abajo).
    const comp = [...d.partes.filter((p) => p.tipo === "compromiso"),
      ...d.partes.filter((p) => p.tipo === "deuda").flatMap((p) => (p.pendientes || []).map((i) => ({ ...i, nombre: p.nombre, categoria: p.categoria })))]
      .sort((a, b) => ORDEN_ESTADO[a.estado] - ORDEN_ESTADO[b.estado] || cmp(a.vence, b.vence));
    const filaComp = (p) => `<div class="comp-fila ${esc(p.estado)}"><span class="emoji" aria-hidden="true">${p.categoria && cat(p.categoria).id ? cat(p.categoria).emoji : "🧾"}</span>
      <div class="txt"><b data-sin-traducir>${esc(p.nombre)}</b><small data-sin-traducir><span class="punto" aria-hidden="true"></span>${textoEstado({ ...p, signo: "gasto", pago: null })}</small></div>
      <span class="valor" data-sin-traducir>${p.max != null && p.max !== p.monto ? "≈ " : ""}${esc(dinero(p.monto))}</span>${seCobraSolo({ ...p, signo: "gasto" }) ? "" : `<div class="acciones"><button class="boton" data-comp-pagado="${esc(p.clave)}">Ya lo pagué</button></div>`}</div>`;
    const fila = (ico, nombre, detalle, monto) => `<div class="debe-fila"><span class="emoji" aria-hidden="true">${ico}</span>
      <div class="txt"><b data-sin-traducir>${nombre}</b><small data-sin-traducir>${detalle}</small></div><span class="valor" data-sin-traducir>${esc(dinero(monto))}</span></div>`;
    const otras = d.partes.filter((p) => p.tipo !== "compromiso").map((p) => {
      if (p.tipo === "tarjeta") return fila("💳", T("Por pagar en tu tarjeta"), p.desde ? T(p.compras === 1 ? "1 compra con crédito desde tu último pago ({f})" : "{n} compras con crédito desde tu último pago ({f})", { n: p.compras, f: esc(fechaCorta(p.desde)) })
        : T(p.compras === 1 ? "1 compra con crédito: se paga cuando llegue el estado de cuenta" : "{n} compras con crédito: se pagan cuando llegue el estado de cuenta", { n: p.compras }), p.monto);
      if (p.tipo === "deuda") return fila("🏦", esc(p.nombre), [p.cuotas ? T("Te quedan {q} de {t} cuotas", { q: p.cuotas.quedan, t: p.cuotas.total }) : T("Saldo que anotaste"),
        p.original ? T("en UF: es una estimación") : p.max !== p.monto ? T("hasta {x}", { x: esc(dinero(p.max)) }) : "",
        p.este_mes ? T("este mes {x}", { x: esc(dinero(p.este_mes)) }) : ""].filter(Boolean).join(" · "), p.monto);
      return fila(p.categoria && cat(p.categoria).id ? cat(p.categoria).emoji : "🧾", esc(nombreComercio(p.nombre)), T(p.quedan === 1 ? "Te queda 1 cuota de {c}" : "Te quedan {q} cuotas de {c}", { q: p.quedan, c: esc(dinero(p.cuota)) }), p.monto);
    }).join("");
    return `<h2 class="desglose-titulo">Lo que debes</h2>
      ${comp.length ? `<div class="por-pagar"><h3 class="grupo">Por pagar este mes</h3>${comp.map(filaComp).join("")}</div>` : ""}
      ${otras ? `<h3 class="grupo">Tarjeta, cuotas y créditos</h3>${otras}` : ""}
      <div class="total-pres"><span>Este mes</span><span data-sin-traducir>${d.aprox ? "≈ " : ""}${esc(dinero(d.este_mes))}</span></div>
      <div class="total-pres sub"><span>En total</span><span data-sin-traducir>${d.aprox ? "≈ " : ""}${esc(dinero(d.total))}</span></div>
      ${d.aprox ? `<p class="nota-mcp">${frase("Hay montos aproximados o en UF: podría llegar a {x} este mes.", { x: esc(dinero(d.este_mes_max)) })}</p>` : ""}
      ${teDebenHTML(d)}
      <p class="nota-mcp"><button class="enlace" data-vista="compromisos">Ver tus pagos</button></p>`;
  }

  /** «Aprendí esto de tus movimientos»: reglas que se ven en lo que ya ordenaste y pagos que parecen compromisos. Máximo dos filas. */
  function reglasSugeridas() {
    const grupos = {};
    for (const m of E.movimientos) {
      const k = reglaPara(m.descripcion);
      if (k.length < 3) continue;
      const g = grupos[k] || (grupos[k] = { cats: {}, sin: 0 });
      if (m.categoria) g.cats[m.categoria] = (g.cats[m.categoria] || 0) + 1; else g.sin++;
    }
    const r = [];
    for (const [k, g] of Object.entries(grupos)) {
      const cs = Object.entries(g.cats);
      if (!g.sin || cs.length !== 1 || cs[0][1] < 2 || !cat(cs[0][0]).id || (E.reglasNo || []).includes(k)) continue;
      if (E.reglas.some((x) => normalizar(x.contiene) === k)) continue;
      r.push({ contiene: k, categoria: cs[0][0], n: g.sin, veces: cs[0][1] });
    }
    return r.sort((a, b) => b.n - a.n || b.veces - a.veces || cmp(a.contiene, b.contiene));
  }
  function aprendiHTML() {
    const reglas = reglasSugeridas().slice(0, 2);
    const sug = (E.sugerencias || []).filter((s) => !(E.compromisos.descartados || []).includes(s.clave));
    const filas = [...reglas.map((r) => {
      const c = cat(r.categoria);
      return `<div class="aprendi-fila"><span class="emoji" aria-hidden="true">${c.emoji}</span><div class="txt">${frase(r.n === 1 ? "«{r}» siempre fue **{c}**. ¿Se lo pongo al que no tiene categoría y a los que vengan?" : "«{r}» siempre fue **{c}**. ¿Se lo pongo a los {n} que no tienen categoría y a los que vengan?", { r: esc(r.contiene), c: esc(nombreCat(c)), n: r.n })}</div>
        <div class="acciones"><button class="boton sutil" data-regla-no="${esc(r.contiene)}">No</button><button class="boton" data-regla-si="${esc(r.contiene)}" data-regla-cat="${esc(r.categoria)}">Sí, siempre</button></div></div>`;
    }), ...sug.slice(0, reglas.length ? 1 : 2).map((s) => `<div class="aprendi-fila"><span class="emoji" aria-hidden="true">${iconoComp(s)}</span><div class="txt">${textoSugerencia(s)}</div>
        <div class="acciones"><button class="boton sutil" data-sug-no="${esc(s.clave)}">No es</button><button class="boton" data-sug-agregar="${esc(s.clave)}">¿Lo agrego?</button></div></div>`)];
    if (!filas.length) return "";
    return `<div class="aprendi"><h3 class="grupo">Aprendí esto de tus movimientos</h3>${filas.join("")}
      ${sug.length > 2 ? `<button class="enlace" data-vista="compromisos">${frase("Ver {n} más en Pagos", { n: sug.length - (reglas.length ? 1 : 2) })}</button>` : ""}</div>`;
  }

  /** Una sola tarjeta con todo lo que pide algo de ti: el sueldo que no llega, lo que falta ordenar, lo que aprendí,
   *  la invitación a anotar tus pagos y lo pagado en intereses por atraso. Si no hay nada, no aparece. */
  function pendientesHTML(preguntaMes) {
    const sinCat = E.movimientos.filter((m) => !m.categoria).length;
    const ordenar = sinCat ? `<div class="pendiente-fila"><span class="ico">${icono("ordenar", 20)}</span><p>${frase(sinCat === 1 ? "**1 movimiento** sin categoría" : "**{n} movimientos** sin categoría", { n: sinCat })}</p>
      <button class="boton" data-vista="ordenar">Ordenar</button></div>` : "";
    const anotar = !listaCompromisos().length ? `<div class="pendiente-fila"><span class="ico">${icono("compromisos", 20)}</span><p>${frase("Anota lo que pagas seguido (arriendo, créditos, cuentas) y te digo si te falta pagar algo.", {})}</p>
      <button class="boton" data-accion="agregar-contar">Anotar</button></div>` : "";
    const pagoMora = moraDelAnio(listaCompromisos(), E.movimientos, E.hoy, monedaPrincipal(), ufCfg(), E.palabrasMora || []);
    const mora = pagoMora > 0 ? `<div class="pendiente-fila"><span class="ico rojo-txt" aria-hidden="true">!</span><p class="mora-anio">${frase("Este año pagaste {x} en intereses por atraso.", { x: esc(dinero(pagoMora)) })}</p></div>` : "";
    const partes = [preguntaMes, ordenar, aprendiHTML(), anotar, mora].filter(Boolean);
    if (!partes.length) return "";
    return `<section class="tarjeta pendientes"><h2 class="titulo-seccion">Pendientes</h2>${partes.join("")}</section>`;
  }

  function opcionesCategoria(elegida) {
    return [`<option value="" ${!elegida ? "selected" : ""}>🏷️ ${esc(tr("Sin categoría"))}</option>`,
      ...E.categorias.map((c) => `<option value="${esc(c.id)}" ${c.id === elegida ? "selected" : ""}>${c.emoji} ${esc(c.nombre)}</option>`)].join("");
  }

  // ───────────── Categorizar en uno o dos toques ─────────────
  /** Cómo se pagó, en palabras: «Crédito · 6 cuotas de $61.000», «Débito», «Con saldo». */
  function medioTexto(m) {
    const n = cuotasDe(m);
    if (n) return T("Crédito · {n} cuotas de {c}", { n, c: esc(dinero(valorCuota(m), m.moneda || monedaPrincipal())) });
    return { credito: T("Crédito"), debito: T("Débito"), saldo: T("Con saldo") }[m.medio] || "";
  }
  /** La categoría de un movimiento: icono y nombre corto en gris (un toque la cambia). Sin categoría: un «+» gris discreto. */
  function chipCat(m) {
    const c = cat(m.categoria), falta = !m.categoria;
    return `<button type="button" class="chip-cat ${falta ? "falta" : ""}" id="chip-${esc(m.id)}" data-elegir="${esc(m.id)}" aria-haspopup="dialog"
      aria-label="${falta ? esc(tr("Ponle categoría")) : T("Categoría: {c}. Cambiar", { c: esc(nombreCat(c)) })}" ${falta ? `title="${esc(tr("Ponle categoría"))}"` : ""} data-sin-traducir>${falta
        ? `<span class="mas-cat" aria-hidden="true">+</span>` : `<span aria-hidden="true">${c.emoji}</span><span class="n">${esc(nombreCat(c))}</span>`}</button>`;
  }
  /** Una fila de movimiento: el comercio legible a la izquierda (tocarlo muestra la descripción original), la categoría en gris
   *  debajo y el monto a la derecha con cifras tabulares. */
  function filaMov(m, cuentas) {
    const c = cat(m.categoria), neutro = c.tipo === "neutro", medio = medioTexto(m), abierto = E.movVer === m.id;
    const otraMoneda = m.moneda && m.moneda !== monedaPrincipal();
    return `<div class="mov ${neutro ? "neutro" : ""} ${m.categoria ? "" : "sin-cat"}">
      <button type="button" class="mov-txt" data-mov-ver="${esc(m.id)}" aria-expanded="${abierto}"><span class="t" data-sin-traducir>${esc(nombreComercio(m.descripcion))}</span></button>
      <span class="valor ${m.monto > 0 && !neutro ? "ingreso" : ""}" data-sin-traducir>${esc(dinero(m.monto, m.moneda, true))}${otraMoneda ? ` <small>${esc(m.moneda)}</small>` : ""}</span>
      <span class="mov-pie">${chipCat(m)}${abierto ? "" : medio && cuotasDe(m) ? `<span class="m" data-sin-traducir>${medio}</span>` : ""}</span>
      ${abierto ? `<p class="mov-detalle" data-sin-traducir>${esc(m.descripcion)}<br>${esc(cuentas[m.cuenta] || m.cuenta)}${medio ? ` · ${medio}` : ""} · ${esc(fechaCorta(m.fecha))}</p>` : ""}</div>`;
  }
  /** Categorías para elegir: primero las del tipo que corresponde (gasto o ingreso) y, dentro, las que más usas. */
  function opcionesPara(m, buscar) {
    const uso = {};
    for (const x of E.movimientos) if (x.categoria) uso[x.categoria] = (uso[x.categoria] || 0) + 1;
    const tipo = m && m.monto > 0 ? "ingreso" : "gasto", q = normalizar(buscar), sug = categoriaSugerida(m);
    return E.categorias.map((c, i) => [c, i]).filter(([c]) => !q || normalizar(c.nombre).includes(q))
      .sort(([a, i], [b, j]) => (b.id === sug) - (a.id === sug) || (a.tipo === tipo ? 0 : a.tipo === "neutro" ? 1 : 2) - (b.tipo === tipo ? 0 : b.tipo === "neutro" ? 1 : 2) || (uso[b.id] || 0) - (uso[a.id] || 0) || i - j)
      .map(([c]) => c);
  }
  /** Lo que aprendí de tus movimientos: la categoría que más le has puesto a este mismo comercio (va primero al elegir). */
  function categoriaSugerida(m) {
    const k = m ? reglaPara(m.descripcion) : "";
    if (k.length < 3) return "";
    const n = {};
    for (const x of E.movimientos) if (x !== m && x.categoria && reglaPara(x.descripcion) === k) n[x.categoria] = (n[x.categoria] || 0) + 1;
    const mejor = Object.entries(n).sort((a, b) => b[1] - a[1])[0];
    return mejor && cat(mejor[0]).id ? mejor[0] : "";
  }
  const EMOJIS = ["🏷️", "🍽️", "🎬", "🎉", "🎁", "✈️", "🛍️", "☕", "🎮", "🍻", "👕", "🏋️", "🧸", "💇", "🎵", "💻"];
  const PISTAS_EMOJI = [[/CINE|PELICULA|SERIE/, "🎬"], [/DIVERSION|DIVERTID|PARQUE|ENTRETEN|FUN/, "🎢"], [/JUEGO|GAME|CONSOLA/, "🎮"], [/CAFE|COFFEE/, "☕"],
    [/BAR|CERVEZA|COPETE|TRAGO|VINO|BEER|DRINK/, "🍻"], [/COMIDA|ALMUERZO|CENA|RESTAUR|FOOD|MEAL|LUNCH|DINNER/, "🍽️"], [/DELIVERY/, "🛵"], [/REGALO|GIFT|CUMPLE/, "🎁"],
    [/VIAJE|VACACION|TRAVEL|HOTEL|PASAJE/, "✈️"], [/ROPA|ZAPAT|CLOTH/, "👕"], [/DEPORTE|GYM|GIMNASIO|SPORT|FUTBOL/, "🏋️"], [/NINO|HIJO|BEBE|KID|JUGUETE/, "🧸"],
    [/PELUQ|BELLEZA|HAIR|BEAUTY/, "💇"], [/MUSICA|CONCIERTO|MUSIC/, "🎵"], [/TECNO|COMPUTA|TECH/, "💻"], [/FIESTA|PARTY|CARRETE/, "🎉"], [/LIBRO|BOOK/, "📚"],
    [/MASCOTA|PERRO|GATO|PET/, "🐾"], [/AHORRO|SAVING/, "🐷"], [/DONACION|DONATION|CARIDAD/, "🤝"], [/SALUD|MEDIC|DOCTOR|HEALTH/, "🩺"], [/CASA|HOGAR|HOME/, "🏠"],
    [/AUTO|CAR\b|BENCINA|FUEL/, "🚗"], [/TAXI|UBER/, "🚕"], [/COMPRA|SHOP/, "🛍️"]];
  const sugerirEmoji = (nombre) => (PISTAS_EMOJI.find(([re]) => re.test(normalizar(nombre))) || [null, "🏷️"])[1];
  function idNuevaCategoria(nombre) {
    let base = normalizar(nombre).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 30) || "categoria";
    if (base.length < 2) base += "_cat";
    let id = base, n = 2;
    while (E.categorias.some((c) => c.id === id)) id = `${base}_${n++}`;
    return id;
  }
  /** El elegidor de categoría: en el panel que se abre desde el chip (lugar «picker») o en «Por ordenar» (con atajos 1–9). */
  function elegidor(m, k, lugar) {
    const ops = opcionesPara(m, k.buscar), q = String(k.buscar || "").trim();
    const exacta = q && E.categorias.some((c) => normalizar(c.nombre) === normalizar(q));
    const atajos = lugar === "ordenar";
    const sug = categoriaSugerida(m);
    const botones = ops.map((c, i) => `<button type="button" class="op-cat ${c.id === m.categoria ? "actual" : ""} ${c.id === sug && !m.categoria ? "sugerida" : ""}" data-pick="${esc(c.id)}" data-lugar="${lugar}" ${c.id === sug && !m.categoria ? `title="La que sueles usar para este comercio"` : ""}>
        ${atajos && i < 9 ? `<kbd aria-hidden="true">${i + 1}</kbd>` : ""}<span class="e" aria-hidden="true">${c.emoji}</span><span class="n" data-sin-traducir>${esc(nombreCat(c))}</span></button>`).join("");
    const crear = q && !exacta ? `<button type="button" class="op-cat crear" data-nueva-cat="${lugar}" data-con-nombre="1"><span class="e" aria-hidden="true">＋ ${sugerirEmoji(q)}</span><span class="n" data-sin-traducir>${T("Crear «{x}»", { x: esc(q) })}</span></button>`
      : `<button type="button" class="op-cat nueva" data-nueva-cat="${lugar}"><span class="e" aria-hidden="true">＋</span><span class="n">Nueva</span></button>`;
    const nueva = k.nueva ? `<div class="nueva-cat" role="group" aria-label="Nueva categoría">
        <label class="campo"><span>Nombre de la categoría</span><input class="texto" id="${lugar}-nueva" data-nueva-nombre="${lugar}" maxlength="40" value="${esc(k.nueva.nombre)}" placeholder="${esc(tr("p. ej. Cine o Comida atípica"))}" data-sin-traducir></label>
        <div class="emojis" role="radiogroup" aria-label="Emoji">${[...new Set([k.nueva.emoji || sugerirEmoji(k.nueva.nombre), ...EMOJIS])].slice(0, 12).map((e) =>
          `<button type="button" role="radio" aria-checked="${e === (k.nueva.emoji || sugerirEmoji(k.nueva.nombre))}" data-nueva-emoji="${e}" data-lugar="${lugar}" data-sin-traducir>${e}</button>`).join("")}</div>
        ${k.nueva.error ? `<p class="error-txt" data-sin-traducir>${esc(k.nueva.error)}</p>` : ""}
        <div class="pie-dialogo"><button type="button" class="boton" data-nueva-cancelar="${lugar}">Cancelar</button><button type="button" class="boton principal" data-nueva-guardar="${lugar}">Crear y usar</button></div></div>` : "";
    return `<input class="texto buscar-cat" id="${lugar}-buscar" type="search" data-buscar-cat="${lugar}" value="${esc(k.buscar || "")}" placeholder="${esc(tr("Buscar o crear categoría"))}" aria-label="${esc(tr("Buscar o crear categoría"))}" autocomplete="off" data-sin-traducir>
      ${nueva || `<div class="opciones-cat">${botones}${crear}</div>`}`;
  }
  function pickerHTML() {
    const k = E.picker, m = E.movimientos.find((x) => x.id === k.id);
    if (!m) return "";
    const pos = k.hoja ? "" : `style="top:${k.top}px;left:${k.left}px;max-height:${k.alto}px"`;
    return `<div class="picker-capa" data-cerrar-picker></div><div class="picker ${k.hoja ? "hoja" : ""}" role="dialog" aria-modal="true" aria-labelledby="picker-titulo" ${pos}>
      <p class="picker-titulo" id="picker-titulo"><span data-sin-traducir>${esc(nombreComercio(m.descripcion))}</span> <span class="valor" data-sin-traducir>${esc(dinero(m.monto, m.moneda, true))}</span></p>
      ${elegidor(m, k, "picker")}</div>`;
  }
  function abrirPicker(id) {
    const chip = document.getElementById("chip-" + id), r = chip?.getBoundingClientRect();
    const hoja = innerWidth < 600 || !r;
    let top = r ? r.bottom + 6 : 0, alto = r ? innerHeight - top - 12 : 0;
    if (!hoja && alto < 300) { alto = Math.min(420, r.top - 18); top = r.top - 6 - alto; }
    E.picker = { id, buscar: "", nueva: null, hoja, top: Math.max(8, top), left: r ? Math.max(8, Math.min(r.left, innerWidth - 348)) : 0, alto: Math.min(420, Math.max(220, alto)) };
    render();
    $("#picker-buscar")?.focus();
  }
  const estadoElegidor = (lugar) => (lugar === "picker" ? E.picker : E.ordenar);
  const movDe = (lugar) => (lugar === "picker" ? E.movimientos.find((x) => x.id === E.picker?.id) : colaOrdenar()[E.ordenar.i]);
  /** Pone la categoría al tiro y ofrece, discreto, aprenderla para ese comercio. */
  function elegirCategoria(m, id, lugar, enviada = false) {
    m.categoria = id;
    if (!enviada) host.enviar("categoria", { mes: mesDe(m.fecha), id: m.id, categoria: id });
    const contiene = reglaPara(m.descripcion);
    const parecidos = E.movimientos.filter((x) => x !== m && contiene && normalizar(x.descripcion).includes(contiene) && x.categoria !== id).length;
    const ya = E.reglas.some((r) => normalizar(r.contiene) === contiene && r.categoria === id);
    E.aprender = id && contiene.length >= 2 && !ya ? { contiene, categoria: id, parecidos } : null;
    clearTimeout(elegirCategoria._t);
    if (E.aprender) { const a = E.aprender; elegirCategoria._t = setTimeout(() => { if (E.aprender === a) { E.aprender = null; render(); } }, 12000); }
    if (lugar === "picker") { E.picker = null; render(); document.getElementById("chip-" + m.id)?.focus(); return; }
    if (lugar === "ordenar") { E.ordenar.buscar = ""; E.ordenar.nueva = null; render(); $(".vista-ordenar")?.focus(); return; }
    render();
  }
  function crearCategoria(lugar) {
    const k = estadoElegidor(lugar), m = movDe(lugar);
    if (!k || !m) return;
    const nombre = String(k.nueva?.nombre ?? k.buscar ?? "").replace(/\s+/g, " ").trim().slice(0, 40);
    if (!nombre) { k.nueva = { ...(k.nueva || {}), nombre: "", error: tr("Ponle un nombre.") }; render(); return $(`#${lugar}-nueva`)?.focus(); }
    const igual = E.categorias.find((c) => normalizar(c.nombre) === normalizar(nombre));
    if (igual) return elegirCategoria(m, igual.id, lugar);
    const c = { id: idNuevaCategoria(nombre), nombre, emoji: k.nueva?.emoji || sugerirEmoji(nombre), tipo: m.monto > 0 ? "ingreso" : "gasto" };
    E.categorias = [...E.categorias, c];
    host.enviar("categoriaNueva", { categoria: c, mes: mesDe(m.fecha), id: m.id });
    toast(T("Creé «{c}»", { c: nombre }));
    elegirCategoria(m, c.id, lugar, true);
  }

  // ───────────── Por ordenar: los sin categoría, uno a uno y con el teclado ─────────────
  const colaOrdenar = () => E.movimientos.filter((m) => !m.categoria).sort((a, b) => cmp(b.fecha, a.fecha) || cmp(a.descripcion, b.descripcion) || cmp(a.id, b.id));
  function vistaOrdenar() {
    const cola = colaOrdenar(), k = E.ordenar;
    const cab = (extra = "") => `${volver("movimientos", "Movimientos")}<div class="encabezado"><h1>Por ordenar</h1>${extra}</div>`;
    if (!cola.length) {
      return `<div class="contenido vista-ordenar" tabindex="-1">${cab()}<section class="tarjeta ordenado"><p class="grande">🎉</p><h2>Todo ordenado</h2>
        <p class="texto-suave">Cada movimiento tiene su categoría. Lo que agregues después y calce con lo que aprendí se ordena solo.</p>
        <button class="boton principal" data-vista="movimientos">Ver mis movimientos</button></section></div>`;
    }
    if (k.i >= cola.length) {
      return `<div class="contenido vista-ordenar" tabindex="-1">${cab()}<section class="tarjeta ordenado"><h2>${frase(cola.length === 1 ? "Te saltaste 1" : "Te saltaste {n}", { n: cola.length })}</h2>
        <p class="texto-suave">Quedan sin categoría. Puedes volver a mirarlos cuando quieras.</p>
        <button class="boton principal" data-accion="ordenar-inicio">Volver al primero</button></section></div>`;
    }
    k.i = Math.max(0, k.i);
    const m = cola[k.i], cuentas = Object.fromEntries(E.cuentas.map((c) => [c.id, c.nombre])), medio = medioTexto(m);
    return `<div class="contenido vista-ordenar" tabindex="-1">${cab(`<span class="contador-ordenar" data-sin-traducir>${T("{i} de {n}", { i: k.i + 1, n: cola.length })}</span>`)}
      <div class="avance-ordenar" aria-hidden="true"><i style="width:${(k.i / cola.length * 100).toFixed(1)}%"></i></div>
      <section class="tarjeta mov-grande">
        <p class="desc" data-sin-traducir>${esc(nombreComercio(m.descripcion))}</p>
        <p class="cifra ${m.monto > 0 ? "ingreso" : ""}" data-sin-traducir>${esc(dinero(m.monto, m.moneda, true))}${m.moneda && m.moneda !== monedaPrincipal() ? `<span class="codigo-moneda">${esc(m.moneda)}</span>` : ""}</p>
        <p class="texto-suave" data-sin-traducir>${esc(primeraMayuscula(nombreDia(m.fecha)))} · ${esc(cuentas[m.cuenta] || m.cuenta)}${medio ? ` · ${medio}` : ""}</p>
        ${nombreComercio(m.descripcion) !== m.descripcion ? `<p class="original" data-sin-traducir>${esc(m.descripcion)}</p>` : ""}</section>
      <section class="tarjeta elegir-ordenar">${elegidor(m, k, "ordenar")}</section>
      <div class="pie-ordenar"><button class="boton" data-accion="ordenar-atras" ${k.i ? "" : "disabled"}>‹ <span>Anterior</span></button>
        <p class="atajos">${frase("Atajos: **1–9** elige · **→** salta · **←** vuelve · **/** busca", {})}</p>
        <button class="boton" data-accion="ordenar-saltar"><span>Saltar</span> ›</button></div></div>`;
  }

  function vistaMovimientos() {
    const f = E.filtro, buscado = normalizar(f.texto);
    const [desde, hasta] = rango(E.mes, per());
    const lista = E.movimientos.filter((m) => desde <= m.fecha && m.fecha <= hasta
      && (!buscado || normalizar(m.descripcion).includes(buscado) || normalizar(m.nota).includes(buscado))
      && (!f.categoria || (f.categoria === "__sin" ? !m.categoria : m.categoria === f.categoria)))
      .sort((a, b) => b.fecha.localeCompare(a.fecha) || a.descripcion.localeCompare(b.descripcion));
    const cuentas = Object.fromEntries(E.cuentas.map((c) => [c.id, c.nombre]));
    let html = "", dia = "";
    if (E.agruparMov) {
      // Agrupado por comercio (lo estable de la descripción, igual que categorizar.regla_para): total y cantidad; se despliega.
      const grupos = new Map();
      for (const m of lista) {
        const k = reglaPara(m.descripcion) || normalizar(m.descripcion).slice(0, 30) || "—";
        if (!grupos.has(k)) grupos.set(k, []);
        grupos.get(k).push(m);
      }
      const total = (l) => l.reduce((a, m) => a + (m.moneda && m.moneda !== monedaPrincipal() ? 0 : m.monto), 0);
      html = [...grupos.entries()].sort((a, b) => Math.abs(total(b[1])) - Math.abs(total(a[1])) || cmp(a[0], b[0])).map(([k, l]) => {
        const abierto = E.grupoMov === k, t = total(l);
        return `<button type="button" class="grupo-mov" data-grupo-mov="${esc(k)}" aria-expanded="${abierto}"><span class="emoji" aria-hidden="true">${cat(l[0].categoria).emoji}</span>
          <span class="txt"><b data-sin-traducir>${esc(nombreComercio(k))}</b><small data-sin-traducir>${T(l.length === 1 ? "1 movimiento" : "{n} movimientos", { n: l.length })}</small></span>
          <span class="valor ${t > 0 ? "ingreso" : ""}" data-sin-traducir>${esc(dinero(t, monedaPrincipal(), true))}</span><span class="cf-flecha" aria-hidden="true">›</span></button>
          ${abierto ? `<div class="grupo-mov-lista">${l.map((m) => filaMov(m, cuentas)).join("")}</div>` : ""}`;
      }).join("");
    }
    for (const m of E.agruparMov ? [] : lista) {
      if (m.fecha !== dia) {
        dia = m.fecha;
        const total = lista.filter((x) => x.fecha === dia && x.monto < 0 && cat(x.categoria).tipo !== "neutro").reduce((a, x) => a + x.monto, 0);
        html += `<h2 class="dia" data-sin-traducir><span>${esc(primeraMayuscula(nombreDia(dia)))}</span><span>${total ? esc(dinero(total)) : ""}</span></h2>`;
      }
      html += filaMov(m, cuentas);
    }
    const c = f.categoria && f.categoria !== "__sin" ? cat(f.categoria) : null;
    const hist = c && c.id ? `<section class="tarjeta"><div class="tarjeta-cabeza">${frase("Últimos 6 meses de {c}", { c: esc(nombreCat(c)) }, "h2")}</div>
      ${bloqueHistoria(historia(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias, c.id, 6, per()), T("Gasto en {c} de los últimos 6 meses", { c: esc(nombreCat(c)) }), true)}</section>` : "";
    const sinCat = E.movimientos.filter((m) => !m.categoria).length, soloSin = f.categoria === "__sin";
    return `<div class="contenido"><div class="encabezado"><h1>Movimientos</h1>${selectorMes()}</div>
      <div class="filtros"><input id="buscar" class="texto buscar" type="search" placeholder="${esc(tr("Buscar"))}" value="${esc(f.texto)}" data-filtro="texto" aria-label="${esc(tr("Buscar"))}" data-sin-traducir>
        <div class="chips" role="group" aria-label="Filtros">
          ${sinCat || soloSin ? `<button class="chip-filtro" data-accion="filtro-ordenar" aria-pressed="${soloSin}"><span>Por ordenar</span> <span class="n" data-sin-traducir>${sinCat}</span></button>` : ""}
          <label class="chip-filtro select ${c ? "activo" : ""}"><span class="oculto-accesible">Filtrar por categoría</span><select data-filtro="categoria" aria-label="${esc(tr("Filtrar por categoría"))}" data-sin-traducir><option value="">${esc(tr("Todas las categorías"))}</option>
            ${E.categorias.map((x) => `<option value="${esc(x.id)}" ${f.categoria === x.id ? "selected" : ""} data-sin-traducir>${x.emoji} ${esc(x.nombre)}</option>`).join("")}</select></label>
          <button class="chip-filtro" data-accion="agrupar-mov" aria-pressed="${!!E.agruparMov}">Agrupar por comercio</button></div></div>
      ${soloSin && lista.length ? `<div class="barra-ordenar"><p>${frase(lista.length === 1 ? "**1** sin categoría este mes." : "**{n}** sin categoría este mes.", { n: lista.length })}</p><button class="boton principal" data-vista="ordenar">Ordenar uno a uno</button></div>` : ""}
      ${hist}
      <div class="lista-mov">${html || `<div class="vacio corto"><p>${f.texto || f.categoria ? "Nada calza con ese filtro." : "No hay movimientos este mes."}</p>
        ${f.texto || f.categoria ? `<button class="boton" data-accion="limpiar-filtro">Ver todos</button>` : ""}</div>`}</div></div>`;
  }

  /** El aviso discreto después de elegir una categoría: «¿Siempre para este comercio?». */
  function avisoRegla() {
    const a = E.aprender;
    if (!a || !cat(a.categoria).id) return "";
    const c = cat(a.categoria);
    return `<div class="aviso-regla" role="status"><p>${frase(a.parecidos ? (a.parecidos === 1 ? "¿Siempre {c} para «{r}»? También hay 1 parecido." : "¿Siempre {c} para «{r}»? También hay {n} parecidos.") : "¿Siempre {c} para «{r}»?",
      { c: esc(c.emoji + " " + nombreCat(c)), r: esc(a.contiene), n: a.parecidos })}</p>
      <button class="boton principal" data-accion="aprender-si">Sí, siempre</button><button class="icono" data-accion="aprender-no" title="Solo este" aria-label="Solo este">✕</button></div>`;
  }

  function vistaPresupuesto() {
    if (!E.presEdit) E.presEdit = { ...(E.presupuesto.mensual || {}) };
    const r = resumen(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias, per());
    const completos = mesesCompletos();
    const promedio = presupuestoSugerido(E.movimientos, completos, E.categorias, E.presupuesto.moneda, per());
    const filas = E.categorias.filter((c) => c.tipo === "gasto").map((c) => `<div class="fila-pres"><span class="emoji" aria-hidden="true">${c.emoji}</span>
      <div style="min-width:0"><b data-sin-traducir>${esc(c.nombre)}</b>
        <small>${frase("Este mes: {x}", { x: esc(dinero(r.por_categoria[c.id] || 0)) })}${promedio[c.id] ? " · " + frase("Lo normal: {x}", { x: esc(dinero(promedio[c.id])) }) : ""}</small></div>
      <input class="texto" inputmode="numeric" data-pres="${esc(c.id)}" value="${esc(numeroPlano(E.presEdit[c.id]))}" placeholder="${esc(tr("Sin tope"))}" aria-label="${T("Tope para {c}", { c: esc(c.nombre) })}" data-sin-traducir></div>`).join("");
    const total = Object.values(E.presEdit).filter((v) => v > 0).reduce((a, b) => a + b, 0);
    const cambio = JSON.stringify(limpiarPres(E.presEdit)) !== JSON.stringify(limpiarPres(E.presupuesto.mensual || {}));
    return `<div class="contenido">${volver("mas", "Más")}<div class="encabezado"><h1>Presupuesto mensual</h1>
        <button class="boton" data-accion="sugerir" ${completos.length ? "" : "disabled"} title="${completos.length ? "Usa lo que gastas normalmente en cada categoría" : "Necesito al menos un mes completo de movimientos"}">✨ <span>Sugerir con lo que gastas</span></button></div>
      <p class="intro-vista">Cuánto quieres gastar como máximo cada mes en cada cosa. Alcancía te avisa cuando vas muy rápido, antes de que sea tarde.</p>
      ${tarjetaGastoMaximo()}
      <section class="tarjeta">${filas}<div class="total-pres"><span>Total al mes</span><span id="total-pres" data-sin-traducir>${esc(dinero(total))}</span></div></section>
      <div class="pie-dialogo"><button class="boton principal" data-accion="guardar-pres" ${cambio ? "" : "disabled"}>Guardar presupuesto</button></div></div>`;
  }
  const limpiarPres = (p) => Object.fromEntries(Object.entries(p).filter(([, v]) => v > 0).sort());

  function vistaConsejos() {
    const ia = esc(nombreIA());
    const elegido = E.consejos.find((c) => c.fecha === E.consejoSel) || E.consejos[0];
    let cuerpo;
    if (E.pidiendoConsejos) {
      cuerpo = `<section class="tarjeta progreso">${frase("{ia} está mirando tus números…", { ia }, "p")}<div class="barra indef"><i></i></div></section>`;
    } else if (!elegido) {
      cuerpo = `<section class="tarjeta"><p class="intro-tarjeta">${frase("Cuando quieras, {ia} mira tus gastos del mes y te deja tres cosas: lo que va bien, a qué ponerle ojo y algo concreto para esta semana.", { ia })}</p>
        <button class="boton principal" data-accion="pedir-consejos">✦ <span>Pedir mis primeros consejos</span></button></section>`;
    } else {
      cuerpo = `<section class="tarjeta"><div class="tarjeta-cabeza"><h2 data-sin-traducir>${esc(primeraMayuscula(nombreDia(elegido.fecha)))}</h2></div>
        <div class="md" data-sin-traducir>${mdHTML(elegido.texto)}</div></section>
        ${E.consejos.length > 1 ? `<div class="historial" aria-label="Consejos anteriores">${E.consejos.map((c) => `<button class="chip" data-consejo="${esc(c.fecha)}" aria-pressed="${c === elegido}" data-sin-traducir>${esc(c.fecha)}</button>`).join("")}</div>` : ""}`;
    }
    return `<div class="contenido">${volver("mas", "Más")}<div class="encabezado"><h1>Consejos</h1>
        ${elegido && !E.pidiendoConsejos ? `<button class="boton principal" data-accion="pedir-consejos">✦ <span>Pedir consejos nuevos</span></button>` : ""}</div>
      ${E.errorConsejos ? `<p class="error-txt" data-sin-traducir>${esc(E.errorConsejos)}</p>` : ""}${cuerpo}
      <p class="nota-mcp">${frase("{ia} trabaja con tu propia cuenta y solo ve totales por categoría y los comercios donde más gastaste. Nunca ve tus cuentas ni tus claves.", { ia })}</p></div>`;
  }

  /** Versión nueva: aviso discreto arriba (nunca una alerta del sistema) y, al actualizar, el avance por pasos. */
  function avisoActualizacion() {
    const a = E.act;
    const caja = (contenido, error) => `<div class="contenido" style="padding-bottom:0"><div class="aprender" role="status" style="${error ? "background:var(--rojo-suave)" : ""}">${contenido}</div></div>`;
    if (a) {
      const error = a.paso === "error", pct = a.pct ?? (Number(a.paso) || 0) / 3 * 100;
      return caja(`<div style="flex:1;min-width:0"><b>${error ? "No se pudo actualizar" : "Actualizando Alcancía"}</b><br><small data-sin-traducir>${esc(a.texto || "")}</small>
        ${error ? "" : `<div class="barra" style="margin-top:8px"><i style="width:${Math.round(pct)}%"></i></div>`}</div>
        ${error ? `<button class="boton" data-accion="act-cerrar">Cerrar</button><button class="boton principal" data-accion="actualizar">Reintentar</button>` : ""}`, error);
    }
    if (!E.actualizacion?.hay || E.actOculto) return "";
    return caja(`<p><b>Hay una versión nueva de Alcancía</b> <small data-sin-traducir>${esc((E.actualizacion.detalle || "").split("\n")[0])}</small></p>
      <button class="boton" data-accion="act-despues">Después</button><button class="boton principal" data-accion="actualizar">Actualizar</button>`);
  }

  // ───────────── Compromisos: lo que se paga o se recibe seguido ─────────────
  const TIPOS_COMP = [["deuda", "Deuda o crédito", "🏦"], ["prestamo", "Préstamo personal", "🤝"], ["cuenta", "Cuenta o servicio", "🧾"], ["suscripcion", "Suscripción", "📺"],
    ["transferencia", "Transferencia frecuente", "🔁"], ["ingreso", "Ingreso", "💼"], ["otro", "Otro", "📌"]];
  /** Los grupos de «Lo que estás pagando» y de las sugerencias: por tipo, con los préstamos que te deben junto a los ingresos. */
  const GRUPOS_COMP = [["creditos", "Créditos y préstamos"], ["cuentas", "Cuentas y servicios"], ["suscripciones", "Suscripciones"],
    ["transferencias", "Transferencias frecuentes"], ["otros", "Otros"], ["ingresos", "Ingresos y lo que te deben"]];
  const grupoDe = (c) => (c.signo === "ingreso" || c.tipo === "ingreso" ? "ingresos" : c.tipo === "deuda" || c.tipo === "prestamo" ? "creditos"
    : c.tipo === "cuenta" ? "cuentas" : c.tipo === "suscripcion" ? "suscripciones" : c.tipo === "transferencia" ? "transferencias" : "otros");
  const FRECUENCIAS = [["mensual", "Cada mes"], ["semanal", "Cada semana"], ["anual", "Cada año"], ["una_vez", "Una sola vez"]];
  const DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
  const monedaPrincipal = () => E.presupuesto.moneda || E.config.moneda || "CLP";
  const listaCompromisos = () => (E.compromisos && E.compromisos.compromisos) || [];
  const estadoDelMes = (mes = E.mes) => estadoCompromisos(listaCompromisos(), E.movimientos, mes, E.hoy, monedaPrincipal(), per(), ufCfg(), E.palabrasMora || [], E.palabrasAuto || []);
  const iconoComp = (c) => (c.categoria && cat(c.categoria).id ? cat(c.categoria).emoji : (TIPOS_COMP.find((t) => t[0] === c.tipo) || TIPOS_COMP[TIPOS_COMP.length - 1])[2]);
  /** «viernes 24 de noviembre» / «Friday, November 24». */
  function fechaLarga(f) {
    const [a, m, d] = f.split("-").map(Number), t = new Date(a, m - 1, d).toLocaleDateString(locFechas(), { weekday: "long", day: "numeric", month: "long" });
    return E.idioma === "es" ? t.replace(",", "") : t;
  }
  function fechaCorta(f) {
    const [a, m, d] = f.split("-").map(Number);
    return new Date(a, m - 1, d).toLocaleDateString(locFechas(), { day: "numeric", month: "short" });
  }
  function mesLargo(f) {
    const [a, m] = f.split("-").map(Number);
    return new Date(a, m - 1, 1).toLocaleDateString(locFechas(), { month: "long", year: "numeric" });
  }
  /** «Vence en 3 días», «Atrasado 8 días», «Pagado el 30 sept»… (para ingresos: «Llega…», «Llegó…»; lo que se paga solo:
   *  «Se paga solo el 25 oct» o «No vimos el cargo…»). */
  function textoEstado(i) {
    const ing = i.signo === "ingreso";
    if (i.estado === "pagado" && !ing && i.pago.mora) return T(i.pago.mora.dias === 1 ? "Pagado el {f} con 1 día de atraso · {x} de interés por mora" : "Pagado el {f} con {n} días de atraso · {x} de interés por mora",
      { f: esc(fechaCorta(i.pago.fecha)), n: i.pago.mora.dias, x: esc(dinero(i.pago.mora.monto, i.moneda)) });
    if (i.estado === "pagado") return T(ing ? "Llegó el {f}" : "Pagado el {f}", { f: esc(fechaCorta(i.pago.fecha)) });
    if (i.modo_pago === "automatico" && !ing) {
      // Se cobra solo: no se le pide nada a la persona, salvo si pasaron los días de gracia y el cargo no aparece.
      if (i.estado === "atrasado") return i.dias === 1 ? T("No vimos el cargo: venció ayer") : T("No vimos el cargo: venció hace {n} días", { n: i.dias });
      if (i.estado === "esperando") return T("Se paga solo · aún no aparece el cargo");
      return T("Se paga solo el {f}", { f: esc(fechaCorta(i.vence)) });
    }
    if (i.estado === "hoy") return T(ing ? "Llega hoy" : "Vence hoy");
    if (i.estado === "pendiente") return i.dias === 1 ? T(ing ? "Llega mañana" : "Vence mañana") : T(ing ? "Llega en {n} días" : "Vence en {n} días", { n: i.dias });
    return i.dias === 1 ? T(ing ? "No ha llegado: 1 día de atraso" : "Atrasado 1 día") : T(ing ? "No ha llegado: {n} días de atraso" : "Atrasado {n} días", { n: i.dias });
  }
  // ───────────── Montos aproximados y en UF ─────────────
  const ufCfg = () => (E.config && E.config.uf && typeof E.config.uf === "object" ? E.config.uf : null);
  const separadorDecimal = () => (1.5).toLocaleString(locNumeros()).replace(/\d/g, "").charAt(0) || ",";
  /** Un número escrito como lo escribe la persona («12,75», «39.512,30» en Chile; «12.75» en EE. UU.). */
  function numeroDecimal(texto) {
    let t = String(texto || "").replace(/[^\d.,-]/g, "");
    t = separadorDecimal() === "," ? t.replace(/\./g, "").replace(",", ".") : t.replace(/,/g, "");
    const n = parseFloat(t);
    return Number.isFinite(n) ? n : 0;
  }
  const formatoDecimal = (n) => (n ? Number(n).toLocaleString(locNumeros(), { maximumFractionDigits: 4 }) : "");
  const textoUF = (n) => `${formatoDecimal(n)} UF`;
  /** Para la columna del monto: «≈ $480.000», «$15.990» o «12,75 UF» (si aún no sé cuánto es en pesos). Ya escapado. */
  function montoCorto(x) {
    if (x.original && x.original.sin_valor) return esc(textoUF(x.original.monto));
    return (x.rango ? "≈ " : "") + esc(dinero(x.monto, x.moneda));
  }
  /** El detalle: «entre $465.000 y $495.000», «12,75 UF ≈ $490.000 – $506.000» o «12,75 UF (aún no sé cuánto es en pesos)». */
  function detalleMonto(x) {
    if (x.original && x.original.sin_valor) return T("{u} (aún no sé cuánto es en pesos)", { u: esc(textoUF(x.original.monto)) });
    if (!x.rango) return "";
    const a = esc(dinero(x.rango.min, x.moneda)), b = esc(dinero(x.rango.max, x.moneda));
    return x.original ? T("{u} ≈ {a} – {b}", { u: esc(textoUF(x.original.monto)), a, b }) : T("entre {a} y {b}", { a, b });
  }
  /** «≈ $480.000 (entre $465.000 y $495.000)», «12,75 UF ≈ $490.000 – $506.000» o el monto exacto. */
  const montoLargo = (x) => (x.original ? detalleMonto(x) : x.rango ? `≈ ${esc(dinero(x.monto, x.moneda))} (${detalleMonto(x)})` : esc(dinero(x.monto, x.moneda)));
  /** Lo último que se sabe de la UF (Ajustes o el pago de un compromiso en UF), para mostrar cuánto sería uno nuevo. */
  function ufConocida() {
    const refs = [];
    const u = ufCfg();
    if (u && u.valor && u.fecha) refs.push({ valor: u.valor, fecha: u.fecha, fuente: "ajustes" });
    for (const i of estadoDelMes(periodoHoy()).compromisos) if (i.original && !i.original.sin_valor) refs.push({ valor: i.original.valor_uf, fecha: i.original.fecha_uf, fuente: i.original.fuente });
    return refs.sort((a, b) => cmp(b.fecha, a.fecha))[0] || null;
  }
  /** «Valor de la UF hoy» (Ajustes y la invitación en Pagos): se escribe una vez; después sale de tus pagos. */
  function campoUF() {
    const u = ufCfg() || {};
    return `<div class="dos"><label class="campo"><span>Valor de la UF hoy</span><input class="texto" id="uf-valor" inputmode="decimal" data-uf="valor" value="${esc(formatoDecimal(u.valor))}" placeholder="${esc(tr("p. ej. 39.500"))}" data-sin-traducir></label>
      <label class="campo"><span>Cuánto puede variar al mes (%)</span><input class="texto" id="uf-variacion" inputmode="decimal" data-uf="variacion_mensual" value="${esc(formatoDecimal(u.variacion_mensual ?? UF_MENSUAL))}" data-sin-traducir></label></div>
      <p class="nota-mcp">${u.valor && u.fecha ? frase("Anotado el {f}. Cuando reconozca un pago en UF, uso el valor que sale de ese pago.", { f: esc(fechaCorta(u.fecha)) })
        : frase("Solo hace falta mientras no reconozca ningún pago en UF: después saco el valor de tus pagos. Es una estimación.", {})}</p>`;
  }
  const hayUF = () => listaCompromisos().some((c) => c.moneda === UF);

  /** Lo que se paga solo y todavía no pide nada a la persona (sin «Ya lo pagué»): hasta que pasan los días de gracia sin cargo. */
  const seCobraSolo = (i) => i.modo_pago === "automatico" && i.signo !== "ingreso" && i.estado !== "pagado" && i.estado !== "atrasado";
  function filaCompromiso(i, completa) {
    const clave = esc(`${i.id}|${i.periodo}`);
    let acciones = "";
    if (seCobraSolo(i)) acciones = "";
    else if (i.estado !== "pagado") acciones = `<button class="boton" data-comp-pagado="${clave}">${i.signo === "ingreso" ? "Ya llegó" : "Ya lo pagué"}</button>`;
    else if (completa && i.pago.como === "automatico") acciones = `<button class="boton sutil" data-comp-noes="${clave}|${esc(i.pago.movimiento)}" title="Ese movimiento no es el pago de este compromiso">No es este</button>`;
    else if (completa) acciones = `<button class="boton sutil" data-comp-desmarcar="${clave}">Desmarcar</button>`;
    const detalle = [textoEstado(i)];
    if (i.cuota) detalle.push(T("cuota {n} de {t}", { n: i.cuota.numero, t: i.cuota.total }));
    if (completa && i.estado === "pagado" && i.pago.como === "automatico") detalle.push(T("lo reconocí en tu cartola: {d}", { d: esc(i.pago.descripcion) }));
    if (i.anterior) detalle.push(T("de {m}", { m: esc(nombreMes(i.vence.slice(0, 7))) }));
    // Pagado y reconocido: lo que de verdad se pagó. Si no, el monto (aproximado o en UF, con su rango al lado).
    const pagadoReal = i.estado === "pagado" && i.pago.como === "automatico" && (i.rango || i.original);
    if (!pagadoReal && (i.rango || i.original)) detalle.push(detalleMonto(i));
    return `<div class="comp-fila ${esc(i.estado)}"><span class="emoji" aria-hidden="true">${iconoComp(i)}</span>
      <div class="txt"><b data-sin-traducir>${esc(i.nombre)}</b><small data-sin-traducir><span class="punto" aria-hidden="true"></span>${detalle.join(" · ")}</small></div>
      <span class="valor ${i.signo === "ingreso" ? "ingreso" : ""}" data-sin-traducir>${pagadoReal ? esc(dinero(i.pago.monto, monedaPrincipal())) : montoCorto(i)}</span>
      ${acciones ? `<div class="acciones">${acciones}</div>` : ""}</div>`;
  }
  function textoFrecuencia(c) {
    if (c.frecuencia === "mensual") return T("el {d} de cada mes", { d: c.dia });
    if (c.frecuencia === "semanal") return T("cada {d}", { d: esc(tr(DIAS_SEMANA[(c.dia || 1) - 1])) });
    if (c.frecuencia === "anual") return T("cada año, el {f}", { f: esc(fechaCorta(c.fecha)) });
    return T("una vez, el {f}", { f: esc(fechaCorta(c.fecha)) });
  }
  /** «Lo que estás pagando»: todo junto, con el avance de las deudas y el total mensual comprometido. */
  function seccionLoQuePagas(e) {
    const porId = Object.fromEntries(listaCompromisos().map((c) => [c.id, c]));
    const moneda = monedaPrincipal();
    const total = e.compromisos.filter((c) => c.signo === "gasto" && c.moneda === moneda).reduce((a, c) => a + c.mensual, 0);
    const totalAprox = e.compromisos.some((c) => c.signo === "gasto" && c.moneda === moneda && c.rango);
    const entra = e.compromisos.filter((c) => c.signo === "ingreso" && c.moneda === moneda).reduce((a, c) => a + c.mensual, 0);
    const fila = (r) => {
      const c = porId[r.id] || r;
      let extra = "";
      if (r.cuotas && r.tipo === "prestamo") {
        const pct = r.cuotas.total ? Math.round(r.cuotas.pagadas / r.cuotas.total * 100) : 0, debe = r.signo !== "ingreso";
        const x = esc(dinero(r.por_pagar || 0, r.moneda)), p = esc(r.con || ""), cu = esc(dinero(r.monto, r.moneda));
        const linea = r.cuotas.quedan === 0 ? T(debe ? "¡Le pagaste todo a {p}!" : "¡{p} te pagó todo!", { p })
          : [T(debe ? "Le debes {x} a {p}" : "{p} te debe {x}", { x, p }), T(debe ? "te quedan {q} de {t} cuotas de {c}" : "le quedan {q} de {t} cuotas de {c}", { q: r.cuotas.quedan, t: r.cuotas.total, c: cu }),
            r.termina ? T(debe ? "terminas en {m}" : "termina en {m}", { m: esc(mesLargo(r.termina)) }) : ""].filter(Boolean).join(" · ");
        extra = `<div class="avance-deuda"><div class="barra" role="img" data-sin-traducir aria-label="${T("{p}% pagado", { p: pct })}"><i style="width:${pct}%"></i></div><small data-sin-traducir>${linea}</small></div>`;
      } else if (r.cuotas) {
        const pct = r.cuotas.total ? Math.round(r.cuotas.pagadas / r.cuotas.total * 100) : 0;
        const linea = r.cuotas.quedan === 0 ? T("¡Pagaste las {t} cuotas!", { t: r.cuotas.total })
          : T("Te quedan {q} de {t} cuotas", { q: r.cuotas.quedan, t: r.cuotas.total }) + (r.termina ? " · " + T("termina en {m}", { m: esc(mesLargo(r.termina)) }) : "");
        extra = `<div class="avance-deuda"><div class="barra" role="img" data-sin-traducir aria-label="${T("{p}% pagado", { p: pct })}"><i style="width:${pct}%"></i></div>
          <small data-sin-traducir>${linea}${r.por_pagar ? " · " + T(r.saldo ? "saldo que anotaste: {x}" : "quedan por pagar {x}", { x: (r.rango ? "≈ " : "") + esc(r.moneda === UF ? textoUF(r.por_pagar) : dinero(r.por_pagar, r.moneda)) }) : ""}</small></div>`;
      } else if (r.tipo === "deuda") {
        extra = `<div class="avance-deuda"><small data-sin-traducir>${r.termina ? T("termina en {m}", { m: esc(mesLargo(r.termina)) }) + " · " : ""}${r.saldo ? T("saldo que anotaste: {x}", { x: esc(dinero(r.saldo, r.moneda)) }) + " · " : ""}<button class="enlace" data-comp-editar="${esc(r.id)}">${esc(tr("Anotar cuántas cuotas faltan"))}</button></small></div>`;
      }
      const modo = r.modo_pago !== undefined ? r.modo_pago : modoPago(c, E.palabrasAuto || []);
      const etiqueta = modo ? `<span class="chip etiqueta-pago">${esc(tr(modo === "automatico" ? "Se paga solo" : "Pagas tú"))}</span> ` : "";
      return `<div class="pagando"><span class="emoji" aria-hidden="true">${iconoComp(r)}</span>
        <div class="txt"><b data-sin-traducir>${esc(r.nombre)}</b><small data-sin-traducir>${etiqueta}${r.rango !== undefined ? montoLargo(r) : esc(r.moneda === UF ? textoUF(r.monto) : dinero(r.monto, r.moneda))} ${textoFrecuencia(c)}</small>${extra}</div>
        <button class="icono" data-comp-editar="${esc(r.id)}" data-sin-traducir title="${esc(tr("Editar"))}" aria-label="${T("Editar {c}", { c: esc(r.nombre) })}">✎</button></div>`;
    };
    const pausados = listaCompromisos().filter((c) => c.activo === false);
    const bloques = GRUPOS_COMP.map(([g, titulo]) => {
      const l = e.compromisos.filter((c) => grupoDe(c) === g);
      if (!l.length) return "";
      const mios = l.filter((c) => c.moneda === moneda), sub = mios.reduce((a, c) => a + c.mensual, 0);
      return `<h3 class="grupo con-total"><span>${titulo}</span>${sub ? `<span class="sub" data-sin-traducir>${T("{x} al mes", { x: (mios.some((c) => c.rango) ? "≈ " : "") + esc(dinero(sub)) })}</span>` : ""}</h3>${l.map(fila).join("")}`;
    }).join("");
    return `<h2 class="subtitulo">Lo que estás pagando</h2><section class="tarjeta">${bloques}
      ${pausados.length ? `<h3 class="grupo">En pausa</h3>${pausados.map((c) => fila({ ...c, mensual: 0, cuotas: null })).join("")}` : ""}
      <div class="total-pres"><span>Comprometido al mes</span><span data-sin-traducir>${totalAprox ? "≈ " : ""}${esc(dinero(total))}</span></div>
      ${entra ? `<div class="total-pres sub"><span>Ingresos que esperas al mes</span><span class="ingreso" data-sin-traducir>${esc(dinero(entra))}</span></div>` : ""}</section>`;
  }
  /** Una sugerencia (detectada en la cartola) en palabras: «Parece que pagas X cerca del día 15». */
  function textoSugerencia(s) {
    const x = (s.aproximado ? "≈ " : "") + esc(dinero(s.monto, s.moneda)), m = esc(s.nombre);
    if (s.motivo === "palabra") return frase(s.signo === "ingreso" ? "Recibiste **{x}** ({m}) el día {d} y parece algo que se repite." : "Pagaste **{x}** ({m}) el día {d} y parece un compromiso.", { x, m, d: s.dia });
    return frase(s.signo === "ingreso" ? "Parece que recibes **{x}** cerca del día {d}: {m}." : "Parece que pagas **{x}** cerca del día {d}: {m}.", { x, m, d: s.dia });
  }
  function seccionSugerencias() {
    const lista = (E.sugerencias || []).filter((s) => !(E.compromisos.descartados || []).includes(s.clave));
    if (!lista.length) return "";
    const ver = E.sugTodas ? lista : lista.slice(0, 3);
    return `<h2 class="subtitulo">Parece que pagas esto seguido</h2><section class="tarjeta">
      ${GRUPOS_COMP.map(([g, titulo]) => [titulo, ver.filter((s) => grupoDe(s) === g)]).filter(([, l]) => l.length).map(([titulo, l]) => `<h3 class="grupo">${titulo}</h3>` + l.map((s) => `<div class="sugerencia"><span class="emoji" aria-hidden="true">${iconoComp(s)}</span><div class="txt">${textoSugerencia(s)}
        ${s.cuotas_total ? `<small data-sin-traducir>${T("Según tu cartola vas en la cuota {n} de {t}.", { n: s.cuotas_pagadas, t: s.cuotas_total })}</small>` : ""}</div>
        <div class="acciones"><button class="boton sutil" data-sug-no="${esc(s.clave)}">No es</button><button class="boton principal" data-sug-agregar="${esc(s.clave)}">¿Lo agrego?</button></div></div>`).join("")).join("")}
      ${lista.length > 3 ? `<button class="enlace" data-accion="sug-todas">${E.sugTodas ? "Ver menos" : frase("Ver {n} más", { n: lista.length - 3 })}</button>` : ""}</section>`;
  }
  // ───────────── Conversar con Alcancía (el chanchito): bin/chat.py con la IA de la persona ─────────────
  /** ¿Hay una IA elegida e instalada? (En el navegador no se sabe si está instalada: basta con la elegida.) */
  const hayIA = () => !!E.config.ia && (E.ias || []).find((i) => i.id === E.config.ia)?.instalada !== false;
  /** Para empezar: tocar una llena el campo con el comienzo de la frase (la persona la completa). */
  const SUGERENCIAS_CHAT = [["Me atrasé con un pago", "Me atrasé con el pago de "], ["Ese pago era del mes pasado", "Aún no pago este mes el "],
    ["¿Cuánto puedo pagar al mes por un préstamo?", "¿Cuánto puedo pagar al mes? Me prestaron "], ["Anotar un pago que se repite", "Pago todos los meses "]];
  /** Lo que la app explica cuando algo que propuso la IA no se pudo preparar (bin/chat.py devuelve el código). */
  const NOTAS_CHAT = { no_encontre: "No encontré ese pago entre los tuyos.", sin_pago_para_mover: "Revisé: no hay un pago de este mes que mover.",
    ya_pagado: "Eso ya aparece pagado.", ya_pendiente: "Eso ya aparece pendiente.", sin_cambios: "Eso ya está así.",
    no_aplica: "Hubo algo que no pude preparar. Si quieres, dímelo de otra forma.", descartadas: "Dejé fuera algo que no entendí bien." };
  const claveAccion = (i, j = null) => (j == null ? String(i) : `${i}.${j}`);
  const estadoAccion = (m, i, j = null) => (m.estados || {})[claveAccion(i, j)] || "";
  /** Lo que respondió a «¿Es el mismo?» («mismo» u «otro»; "" si aún no): se guarda aparte, con la clave «es:<i>.<j>». */
  const esMismo = (m, i, j = null) => (m.estados || {})["es:" + claveAccion(i, j)] || "";
  const claveEstado = (i, j, estado) => (estado === "mismo" || estado === "otro" ? "es:" : "") + claveAccion(i, j);
  /** El plan según lo que respondió: bin/chat.py ya calculó cada combinación de «es el mismo» (`variantes`, con la clave de los
   *  índices: «0», «0,1»…). Aquí solo se elige; así al reabrir se ve igual aunque los datos hayan cambiado. */
  function planElegido(m, a, i) {
    const js = (a.parecidos || []).map((p, j) => (p && esMismo(m, i, j) === "mismo" ? j : null)).filter((j) => j != null);
    const v = js.length ? (a.variantes || {})[js.join(",")] : null;
    return v ? { plan: v.plan, propuestas: v.propuestas, mismos: js } : { plan: a.plan, propuestas: a.propuestas || [], mismos: [] };
  }
  const textoChat = (t) => esc(t).replace(/\n/g, "<br>");
  const primeraCuota = (c) => (c.frecuencia && c.dia && c.desde ? vencimientos({ ...c, fecha_fin: null }, "2299-12-31").find((o) => o.n) : null);
  /** Un compromiso propuesto, en una línea: cuánto, cuándo y quién lo paga. */
  function lineaPropuesta(c) {
    const partes = [];
    if (c.tipo === "prestamo" && c.prestamo && c.cuotas_total) {
      const m = (x) => esc(c.moneda === UF ? textoUF(x) : dinero(x, c.moneda));
      partes.push(T(c.prestamo.ultima !== c.prestamo.cuota ? "{c} al mes por {n} meses (la última de {u})" : "{c} al mes por {n} meses",
        { c: m(c.prestamo.cuota), n: c.cuotas_total, u: m(c.prestamo.ultima) }));
      const o = primeraCuota(c);
      if (o) partes.push(T("la primera el {f}", { f: esc(fechaCorta(o.vence)) }));
    } else if (c.monto) partes.push((c.aproximado ? "≈ " : "") + esc(c.moneda === UF ? textoUF(c.monto) : dinero(c.monto, c.moneda)) + (c.frecuencia && (c.dia || c.fecha) ? " " + textoFrecuencia(c) : ""));
    const modo = pagaLaPersona(c) ? c.pago || modoPago(c, E.palabrasAuto || []) : null;
    if (modo) partes.push(T(modo === "automatico" ? "se paga solo" : "lo pagas tú y te aviso"));
    return partes.join(" · ");
  }
  const botonesChat = (ref, opciones) => `<div class="acciones-chat">${opciones.map(([que, texto, principal]) =>
    `<button class="boton ${principal ? "principal" : que === "no" ? "sutil" : ""}" data-sin-traducir data-chat="${que}" data-msg="${esc(ref.id)}" data-i="${ref.i}" ${ref.j != null ? `data-j="${ref.j}"` : ""}>${texto}</button>`).join("")}</div>`;
  const hechoChat = (estado) => `<p class="accion-estado ${estado === "hecha" ? "hecha" : ""}">${estado === "hecha" ? "✓ Listo" : "Descartado"}</p>`;
  /** Una propuesta de compromiso (crear o una del plan): «Agregar», «Cambiar» (abre el editor) o «No».
   *  `x.parecido` (y sin respuesta): primero «¿Es el mismo?». `x.actualiza`: es el préstamo que ya estaba, con el plan nuevo
   *  («Actualizar»). `x.espera`: hay una pregunta abierta en el mismo plan y las cifras pueden cambiar (sin botones aún). */
  function tarjetaPropuesta(m, a, i, c, j = null, x = {}) {
    const estado = estadoAccion(m, i, j), ref = { id: m.id, i, j };
    const titulo = esc(c.nombre || (c.con ? T("Préstamo de {p}", { p: esc(c.con) }) : tr("Un pago nuevo")));
    const icono = `<span class="emoji" aria-hidden="true">${iconoComp(c)}</span>`;
    if (x.parecido && !x.es && !estado) {
      const p = x.parecido, mo = (v) => esc(c.moneda === UF ? textoUF(v) : dinero(v));
      const detalle = p.cuotas && p.cuotas.quedan ? T(p.cuotas.quedan === 1 ? "{c} al mes, queda 1 cuota" : "{c} al mes, quedan {n} cuotas", { c: mo(p.monto), n: p.cuotas.quedan })
        : T("{c} al mes", { c: mo(p.monto) });
      return `<div class="propuesta pregunta">${icono}<div class="txt"><b data-sin-traducir>${titulo}</b>
        <small data-sin-traducir>${T("Ya tienes anotado «{n}» ({d}). ¿Es el mismo?", { n: esc(p.nombre), d: detalle })}</small></div>
        ${botonesChat(ref, [["mismo", tr("Es el mismo")], ["otro", tr("Es otro")]])}</div>`;
    }
    const linea = a.incompleto && !x.actualiza ? T("Me faltó algo: complétalo y lo guardo.") : x.actualiza ? T("Lo actualizo: {x}", { x: lineaPropuesta(c) }) : lineaPropuesta(c);
    const pie = estado ? hechoChat(estado) : x.espera ? "" : x.actualiza ? botonesChat(ref, [["hacer", tr("Actualizar"), true], ["cambiar", tr("Cambiar")], ["no", tr("No")]])
      : a.incompleto ? botonesChat(ref, [["cambiar", tr("Completar"), true], ["no", tr("No")]])
        : botonesChat(ref, [["hacer", tr("Agregar"), true], ["cambiar", tr("Cambiar")], ["no", tr("No")]]);
    return `<div class="propuesta ${estado ? "resuelta" : ""} ${x.espera && !estado ? "en-espera" : ""}">${icono}
      <div class="txt"><b data-sin-traducir>${titulo}</b><small data-sin-traducir>${linea}</small></div>${pie}</div>`;
  }
  /** «Es el mismo» y no hay nada que cambiar (o la propuesta venía incompleta): no se agrega otro. */
  const tarjetaYaEsta = (p, c) => `<div class="propuesta resuelta"><span class="emoji" aria-hidden="true">${iconoComp(c)}</span>
    <div class="txt"><b data-sin-traducir>${esc(p.nombre)}</b><small data-sin-traducir>${T("Ya lo tienes anotado: no agrego otro.")}</small></div></div>`;
  /** Lo que la IA propone, ya resuelto con código: nada se aplica solo, la persona confirma cada cosa. */
  function tarjetaAccion(m, a, i) {
    const ref = { id: m.id, i, j: null }, estado = estadoAccion(m, i), x = (v) => `<span class="monto-chat">${esc(dinero(v))}</span>`;
    const caja = (html, botones) => `<div class="accion-chat ${estado ? "resuelta" : ""}"><p data-sin-traducir>${html}</p>${estado ? hechoChat(estado) : botonesChat(ref, botones)}</div>`;
    const no = ["no", tr("No")];
    if (a.tipo === "crear_compromiso") {
      const es = a.parecido ? esMismo(m, i) : "";
      const html = es === "mismo" ? (a.actualizar ? tarjetaPropuesta(m, a, i, a.actualizar, null, { actualiza: true }) : tarjetaYaEsta(a.parecido, a.compromiso))
        : tarjetaPropuesta(m, a, i, a.compromiso, null, { parecido: a.parecido, es });
      return `<div class="accion-chat sin-caja">${html}</div>`;
    }
    if (a.tipo === "plan_prestamos") {
      const { plan: p, propuestas, mismos } = planElegido(m, a, i), n = p.meses, parecidos = a.parecidos || [];
      const abiertas = parecidos.filter((q, j) => q && !esMismo(m, i, j) && !estadoAccion(m, i, j)).length;
      const intro = p.alcanza === null ? T("Aún no tengo meses completos para saber cuánto te queda libre, así que te propongo {n} meses. Cuando tenga más datos, lo ajustamos.", { n })
        : p.alcanza ? T("Te quedan libres cerca de {m} al mes. Uso como máximo {d} ({u}) y el resto te queda de colchón. Así terminas en {n} meses:", { m: x(p.margen), d: x(p.disponible), u: `<span class="monto-chat">${p.uso}${E.idioma === "es" ? "\u00a0%" : "%"}</span>`, n })
          : p.margen <= 0 ? T("Hoy lo que gastas y tus compromisos ya suman más de lo que entra (te faltan {m} al mes). Te dejo la cuota más chica posible, pero para pagarla tendrías que recortar en otra parte:", { m: x(-p.margen) })
            : T("Con lo que te queda libre (cerca de {m} al mes) no alcanza sin apretarte: aun en {n} meses serían {t} al mes, {f} más de lo que te recomiendo. Te dejo la propuesta más liviana; si puedes, conversa un plazo más largo:", { m: x(p.margen), n, t: x(p.al_mes), f: x(p.falta) });
      const base = p.base && p.base.ingreso != null && p.base.gasto != null ? `<small class="base-plan" data-sin-traducir>${T("Entra {i} · gastas {g} · compromisos {c}", { i: x(p.base.ingreso), g: x(p.base.gasto), c: x(p.base.compromisos) })}</small>` : "";
      const pendientes = propuestas.filter((c, j) => !estadoAccion(m, i, j)).length;
      const todos = mismos.some((j) => !estadoAccion(m, i, j)) ? "Guardar los {n}" : "Agregar los {n}";
      return `<div class="accion-chat plan"><p data-sin-traducir>${intro}</p>${base}
        ${propuestas.map((c, j) => tarjetaPropuesta(m, a, i, c, j, { parecido: parecidos[j], es: esMismo(m, i, j), actualiza: mismos.includes(j), espera: abiertas > 0 })).join("")}
        ${pendientes > 1 && !abiertas ? botonesChat(ref, [["todos", T(todos, { n: pendientes }), true]]) : ""}</div>`;
    }
    const nombre = esc(a.nombre), f = (v) => esc(fechaCorta(v));
    if (a.tipo === "reasignar_pago") return caja(T("«{c}»: el pago del {f} ({x}) era del vencimiento del {a}. Lo paso ahí y el del {d} queda pendiente.",
      { c: nombre, f: f(a.pago.fecha), x: x(a.pago.monto), a: f(a.a.vence), d: f(a.de.vence) }), [["hacer", tr("Sí, corrígelo"), true], no]);
    if (a.tipo === "marcar_pagado") return caja(T(a.signo === "ingreso" ? "«{c}» (del {f}): ¿lo marco como recibido?" : "«{c}» (vence el {f}): ¿lo marco como pagado?",
      { c: nombre, f: f(a.vence) }), [["hacer", tr("Sí, márcalo"), true], no]);
    if (a.tipo === "marcar_pendiente") return caja(T("«{c}»: quito el pago del {f} y queda pendiente (vence el {v}).", { c: nombre, f: f(a.pago.fecha), v: f(a.vence) }),
      [["hacer", tr("Sí, déjalo pendiente"), true], no]);
    if (a.tipo === "editar_compromiso") {
      const valor = (k, v) => (v == null || v === "" ? "—" : k === "monto" ? x(v) : k === "pago" ? esc(tr(v === "automatico" ? "Se paga solo" : "Lo pago yo")) : k === "fecha_fin" ? f(v) : esc(v));
      const etiqueta = { monto: tr("Monto"), dia: tr("Día"), pago: tr("Cómo se paga"), fecha_fin: tr("Termina") };
      const cambios = Object.keys(a.cambios).map((k) => `${esc(etiqueta[k])}: ${valor(k, a.antes[k])} → <b>${valor(k, a.cambios[k])}</b>`).join(" · ");
      return caja(T("«{c}»: {x}", { c: nombre, x: cambios }), [["hacer", tr("Sí, cámbialo"), true], ["cambiar", tr("Cambiar")], no]);
    }
    return "";
  }
  const avatarChat = () => `<span class="avatar" aria-hidden="true">${LOGO}</span>`;
  function mensajeChat(m) {
    if (m.rol === "persona") return `<div class="msg persona"><div class="globo" data-sin-traducir>${textoChat(m.texto)}</div></div>`;
    const notas = (m.notas || []).filter((n) => NOTAS_CHAT[n]).map((n) => `<p class="nota-chat" data-sin-traducir>${esc(tr(NOTAS_CHAT[n]))}</p>`).join("");
    const extra = m.sin_ia ? `<div class="acciones-chat"><button class="boton" data-accion="chat-ajustes">Abrir Ajustes</button></div>` : "";
    return `<div class="msg alcancia ${m.error ? "error" : ""}">${avatarChat()}<div class="cuerpo-msg"><div class="globo" data-sin-traducir>${textoChat(m.texto)}</div>
      ${(m.acciones || []).map((a, i) => tarjetaAccion(m, a, i)).join("")}${notas}${extra}</div></div>`;
  }
  /** «Cuéntale a Alcancía»: el chat con el chanchito. En celular ocupa toda la pantalla; el campo queda abajo, en la zona del pulgar. */
  function dialogoChat() {
    const k = E.chat, ia = esc(nombreIA()), msgs = k.mensajes || [], conIA = hayIA();
    const borrar = !msgs.length ? "" : k.confirmarBorrar
      ? `<span class="confirmar-borrar"><button class="boton sutil" data-accion="chat-no-borrar">Cancelar</button><button class="boton" data-accion="chat-borrar-si">Borrar la conversación</button></span>`
      : `<button class="boton sutil" data-accion="chat-borrar">Borrar</button>`;
    const cabeza = `<header class="chat-cabeza">${avatarChat()}<div class="txt"><h2 id="t-chat">Alcancía</h2><small>${frase("Con {ia}, en tu computador", { ia })}</small></div>
      ${borrar}<button class="icono" data-accion="cerrar-agregar" aria-label="Cerrar" title="Cerrar">✕</button></header>`;
    const hola = `<div class="msg alcancia">${avatarChat()}<div class="cuerpo-msg"><div class="globo">${frase(conIA
      ? "¡Hola! Soy tu alcancía. Cuéntame si te atrasaste con un pago o si un pago era del mes pasado, pregúntame cuánto puedes pagar al mes, o dime algo que pagas seguido y lo anoto."
      : "¡Hola! Soy tu alcancía. Para conversar necesito tu IA (Claude, ChatGPT o Gemini, con tu cuenta). Elígela en Ajustes: es una vez. Mientras, puedes agregar tus pagos a mano.", {})}</div>
      ${conIA ? `<p class="nota-chat">${frase("{ia} ve tus totales y tus pagos, nunca tu cartola. Nada cambia sin que lo confirmes.", { ia })}
        <button class="enlace" data-accion="comp-nuevo">Prefiero agregarlo a mano</button></p>` : ""}</div></div>`;
    const sugerencias = conIA && !msgs.length && !k.pensando ? `<div class="sugerencias-chat" role="group" aria-label="Para empezar">${SUGERENCIAS_CHAT.map(([t], n) =>
      `<button class="chip-sugerencia" data-sin-traducir data-chat-sugerencia="${n}">${esc(tr(t))}</button>`).join("")}</div>` : "";
    const pensando = k.pensando ? `<div class="msg alcancia pensando" role="status">${avatarChat()}<div class="cuerpo-msg"><div class="globo"><span class="puntos" aria-hidden="true"><i></i><i></i><i></i></span>
      ${frase("{ia} está pensando. Puede tardar un poco.", { ia })}</div></div></div>` : "";
    const pie = conIA ? `<form class="chat-pie" data-chat-form><label class="oculto-accesible" for="chat-texto">Escríbele a Alcancía</label>
        <textarea id="chat-texto" class="texto" rows="1" maxlength="500" data-chat-texto data-sin-traducir placeholder="${esc(tr("Escríbele a Alcancía…"))}" ${k.pensando ? "disabled" : ""}>${esc(k.texto)}</textarea>
        <button class="boton principal enviar" type="button" data-accion="chat-enviar" aria-label="Enviar" title="Enviar" ${k.pensando ? "disabled" : ""}>${icono("enviar")}</button></form>`
      : `<div class="chat-pie sin-ia"><button class="boton" data-accion="comp-nuevo">Agregar a mano</button><button class="boton principal" data-accion="chat-ajustes">Abrir Ajustes</button></div>`;
    return `${cabeza}<div class="chat-cuerpo" role="log" aria-live="polite">${hola}${sugerencias}${msgs.map(mensajeChat).join("")}${pensando}</div>${pie}`;
  }
  /** «+ Agregar»: lo único que se agrega en Alcancía, en un solo lugar (una cartola, un pago que se repite o una cuenta conectada). */
  function dialogoAgregar() {
    const op = (accion, ico, titulo, detalle, extra = "") => `<button class="opcion-agregar" ${accion} ${extra}><span class="ico">${icono(ico)}</span>
      <span class="txt"><b>${titulo}</b><small>${detalle}</small></span><span class="cf-flecha" aria-hidden="true">›</span></button>`;
    return `<h2 id="t-agregar">Agregar</h2>
      <div class="opciones-agregar">
        ${op('data-accion="importar"', "cartola", "Una cartola", "CSV, Excel, PDF u OFX que descargas de tu banco o billetera.")}
        ${op('data-accion="agregar-contar"', "repetir", "Un pago que se repite", "Arriendo, créditos, cuentas, suscripciones o tu sueldo. Con tus palabras.")}
        ${op('data-vista="conexiones"', "conexiones", "Conectar una cuenta", "Que tus movimientos lleguen solos.")}</div>
      <div class="pie-dialogo"><button class="boton" data-accion="cerrar-agregar">Cancelar</button></div>`;
  }
  const nuevoIdComp = () => "c-" + Array.from({ length: 10 }, () => "abcdefghijklmnopqrstuvwxyz0123456789"[Math.floor(Math.random() * 36)]).join("");
  function borradorDe(c = {}) {
    return { nombre: "", tipo: "cuenta", monto: 0, moneda: monedaPrincipal(), frecuencia: "mensual", dia: Number(E.hoy.slice(8, 10)) || 1,
      fecha: E.hoy, categoria: "", buscar: [], tolerancia: 5, activo: true, desde: E.hoy, origen: "manual", ...c,
      buscarTexto: (c.buscar || []).join(", "), aproxActivo: !!c.aproximado, aproxModo: c.aproximado && c.aproximado.min != null ? "rango" : "variacion",
      aproxVariacion: (c.aproximado && c.aproximado.variacion) || 3, aproxMin: c.aproximado ? c.aproximado.min || 0 : 0, aproxMax: c.aproximado ? c.aproximado.max || 0 : 0,
      con: c.con || "", prestamoTotal: c.prestamo ? c.prestamo.total : 0, prestamoInteres: c.prestamo ? c.prestamo.interes || 0 : 0,
      prestamoCuota: c.prestamo ? c.prestamo.cuota || 0 : 0 };
  }
  const DECIMALES_UF = ["monto", "saldo", "aproxMin", "aproxMax"];
  /** En UF, el monto, el saldo y el rango llevan decimales («12,75»); el resto, números enteros. */
  const conDecimales = (id) => E.compEdit && E.compEdit.c.moneda === UF && DECIMALES_UF.includes(id);
  const campoNum = (id, valor, etiqueta, extra = "") => `<label class="campo"><span data-sin-traducir>${etiqueta}</span><input class="texto" id="ce-${id}" inputmode="${conDecimales(id) ? "decimal" : "numeric"}" data-ce="${id}" value="${esc(valor ? (conDecimales(id) ? formatoDecimal(valor) : numeroPlano(valor)) : "")}" ${extra} data-sin-traducir></label>`;
  function editorCompromiso() {
    const k = E.compEdit, c = k.c;
    const opc = (lista, v) => lista.map(([id, n]) => `<option value="${id}" ${v === id ? "selected" : ""}>${esc(tr(n))}</option>`).join("");
    const cuando = c.frecuencia === "mensual" ? `<label class="campo"><span>Día del mes</span><input class="texto" id="ce-dia" type="number" min="1" max="31" data-ce="dia" value="${esc(c.dia || "")}"></label>`
      : c.frecuencia === "semanal" ? `<label class="campo"><span>Día de la semana</span><select id="ce-dia" data-ce="dia" data-sin-traducir>${DIAS_SEMANA.map((d, n) => `<option value="${n + 1}" ${Number(c.dia) === n + 1 ? "selected" : ""}>${esc(primeraMayuscula(tr(d)))}</option>`).join("")}</select></label>`
        : `<label class="campo"><span>Fecha</span><input class="texto" id="ce-fecha" type="date" data-ce="fecha" value="${esc(c.fecha || "")}"></label>`;
    const extraido = k.extraido;
    const deuda = c.tipo === "deuda" ? `<fieldset class="preguntas"><legend>Para saber cuánto te falta <small>(opcional)</small></legend>
        ${extraido ? `<p class="texto-suave" data-sin-traducir>${T("Según tu cartola vas en la cuota {n} de {t}.", { n: c.cuotas_pagadas, t: c.cuotas_total })}</p>`
          : `<div class="dos">${campoNum("cuotas_total", c.cuotas_total, tr("¿Cuántas cuotas son en total?"))}${campoNum("cuotas_pagadas", c.cuotas_pagadas, tr("¿Cuántas ya pagaste?"))}</div>
            <label class="campo"><span>O la fecha en que termina</span><input class="texto" id="ce-fecha_fin" type="date" data-ce="fecha_fin" value="${esc(c.fecha_fin || "")}"></label>`}
        ${campoNum("saldo", c.saldo, tr("Saldo que te queda por pagar"))}</fieldset>` : "";
    const existe = listaCompromisos().some((x) => x.id === c.id);
    return `<h2 id="t-comp">${existe ? "Editar compromiso" : k.origen === "ia" ? "¿Quedó bien?" : "Nuevo compromiso"}</h2>
      ${k.origen === "ia" ? frase("Así lo entendió {ia}. Revisa y corrige lo que haga falta antes de guardar.", { ia: esc(nombreIA()) }, "p") : ""}
      <div class="campos-comp">
        <label class="campo ancho"><span>Nombre</span><input class="texto" id="ce-nombre" maxlength="60" data-ce="nombre" value="${esc(c.nombre)}" data-sin-traducir></label>
        <div class="dos"><label class="campo"><span>Tipo</span><select id="ce-tipo" data-ce="tipo" data-sin-traducir>${opc(TIPOS_COMP, c.tipo)}</select></label>
          ${c.tipo === "prestamo" ? selMoneda(c) : `<div class="monto-moneda">${campoNum("monto", c.monto, c.moneda === UF ? tr("Monto en UF") : tr("Monto"))}${selMoneda(c)}</div>`}</div>
        ${c.tipo === "prestamo" ? camposPrestamo(c) : `${preguntaUF(k)}${estimacionUF(c)}${camposAprox(c)}`}
        ${campoPago(c)}
        <div class="dos"><label class="campo"><span>Se repite</span><select id="ce-frecuencia" data-ce="frecuencia" data-sin-traducir>${opc(FRECUENCIAS, c.frecuencia)}</select></label>${cuando}</div>
        <div class="dos"><label class="campo"><span>Categoría</span><select id="ce-categoria" data-ce="categoria" data-sin-traducir>${opcionesCategoria(c.categoria)}</select></label>
          <label class="campo"><span>Palabras para reconocerlo</span><input class="texto" id="ce-buscar" data-ce="buscarTexto" value="${esc(c.buscarTexto)}" placeholder="${esc(tr("p. ej. DIVIDENDO"))}" data-sin-traducir></label></div>
        <p class="pista-campo">Las que aparecen en tu cartola cuando lo pagas, separadas por coma. Si no pones ninguna, lo reconozco por el monto exacto.</p>
        ${deuda}
        ${existe ? `<label class="marcar"><input type="checkbox" data-ce-activo ${c.activo !== false ? "checked" : ""}><span>Activo<small>Si lo pausas, no te lo recuerdo ni lo busco en tus cartolas.</small></span></label>` : ""}
      </div>
      ${k.error ? `<p class="error-txt" data-sin-traducir>${esc(k.error)}</p>` : ""}
      <div class="pie-dialogo">${existe ? `<button class="boton izq peligro" data-accion="comp-borrar">Borrar</button>` : ""}
        <button class="boton" data-accion="comp-cancelar">Cancelar</button>
        ${c.tipo === "deuda" && !existe ? `<button class="boton" data-accion="comp-despues">Lo completo después</button>` : ""}
        <button class="boton principal" data-accion="comp-guardar">Guardar</button></div>`;
  }
  /** Lo que muestra (y guarda) «¿Cómo se paga?»: lo que eligió la persona o, si no, lo que se infiere (modoPago); si no se sabe, «Lo pago yo». */
  const pagoDelEditor = (c) => c.pago || modoPago({ ...c, buscar: String(c.buscarTexto || "").split(",") }, E.palabrasAuto || []) || "manual";
  const pagaLaPersona = (c) => !(c.tipo === "ingreso" || (c.signo === "ingreso" && (c.tipo === "prestamo" || c.tipo === "transferencia")));
  /** «¿Cómo se paga?»: dos opciones. Lo que se paga solo no se recuerda; solo aviso si no veo el cargo. */
  function campoPago(c) {
    if (!pagaLaPersona(c)) return "";
    const v = pagoDelEditor(c);
    const op = (id, titulo, detalle) => `<label class="opcion-pago"><input type="radio" name="ce-pago" value="${id}" data-ce-pago ${v === id ? "checked" : ""}><span><b>${titulo}</b><small>${detalle}</small></span></label>`;
    return `<fieldset class="pago-modo"><legend>¿Cómo se paga?</legend><div class="opciones-pago">
      ${op("automatico", "Se paga solo", "PAC o cargo a tu tarjeta. Solo te aviso si no veo el cargo.")}${op("manual", "Lo pago yo", "Te recuerdo antes de que venza.")}</div></fieldset>`;
  }
  const selMoneda = (c) => `<label class="campo"><span>Moneda</span><select id="ce-moneda" data-ce="moneda" data-sin-traducir>${[MONEDAS[0], UF, ...MONEDAS.slice(1)].concat(MONEDAS.includes(c.moneda) || c.moneda === UF ? [] : [c.moneda]).filter(Boolean).map((m) => `<option ${m === c.moneda ? "selected" : ""}>${esc(m)}</option>`).join("")}</select></label>`;
  /** Lo que se calcula de un préstamo mientras se escribe: la cuota, la primera fecha y cuándo termina. */
  function calculoPrestamo(c) {
    const total = Number(c.prestamoTotal) || 0, n = Number(c.cuotas_total) || 0, interes = Number(c.prestamoInteres) || 0;
    if (!(total > 0 && n >= 1 && n <= 1200 && interes >= 0 && interes <= 100)) return null;
    const calc = calcularPrestamo(total, n, interes, c.moneda, Number(c.prestamoCuota) || null);
    const borr = { ...c, monto: calc.cuota, desde: c.desde || E.hoy, fecha_fin: null, cuotas_total: n, cuotas_pagadas: Math.min(Number(c.cuotas_pagadas) || 0, n), dia: Number(c.dia) || 25 };
    const vs = c.frecuencia === "una_vez" ? [] : vencimientos(borr, "2299-12-31").filter((o) => o.n);
    return { ...calc, cuotas: n, primera: vs[0] ? vs[0].vence : null, ultimaFecha: vs.length ? vs[vs.length - 1].vence : null };
  }
  /** Préstamo entre personas: con quién, quién le prestó a quién, el total y en cuántas cuotas; el cálculo se ve en vivo. */
  function camposPrestamo(c) {
    const k = calculoPrestamo(c), m = c.moneda, d = (x) => esc(m === UF ? textoUF(x) : dinero(x, m));
    let vivo = "";
    if (k) {
      vivo = T(k.ultima !== k.cuota ? "Son {n} cuotas de {c} (la última de {u})." : "Son {n} cuotas de {c}.", { n: k.cuotas, c: d(k.cuota), u: d(k.ultima) });
      if (k.interes) vivo += " " + T("En total se paga {t}.", { t: d(k.pagar) });
      if (k.primera) vivo += " " + T(c.signo === "ingreso" ? "La primera el {f} y termina en {m}." : "La primera el {f} y terminas en {m}.", { f: esc(fechaCorta(k.primera)), m: esc(mesLargo(k.ultimaFecha)) });
    }
    return `<div class="dos"><label class="campo"><span>¿Con quién?</span><input class="texto" id="ce-con" maxlength="30" data-ce="con" value="${esc(c.con)}" placeholder="${esc(tr("p. ej. Mamá"))}" data-sin-traducir></label>
        <label class="campo"><span>¿Quién le prestó a quién?</span><select id="ce-signo" data-ce="signo" data-sin-traducir>
          <option value="gasto" ${c.signo !== "ingreso" ? "selected" : ""}>${esc(tr("Me prestó a mí (le debo)"))}</option><option value="ingreso" ${c.signo === "ingreso" ? "selected" : ""}>${esc(tr("Yo le presté (me debe)"))}</option></select></label></div>
      <div class="dos">${campoNum("prestamoTotal", c.prestamoTotal, tr("Total del préstamo"))}${campoNum("cuotas_total", c.cuotas_total, tr("¿En cuántas cuotas?"))}</div>
      <div class="dos"><label class="campo"><span>Interés (opcional, % sobre el total)</span><input class="texto" id="ce-prestamoInteres" inputmode="decimal" data-ce="prestamoInteres" value="${esc(formatoDecimal(c.prestamoInteres))}" placeholder="0" data-sin-traducir></label>
        ${campoNum("cuotas_pagadas", c.cuotas_pagadas, tr("Cuotas ya pagadas"))}</div>
      ${vivo ? `<p class="calculo-vivo" role="status" data-sin-traducir>${vivo}</p>` : `<p class="pista-campo">Escribe el total y en cuántas cuotas: yo calculo la cuota y cuándo terminas.</p>`}`;
  }
  /** «El monto varía (aprox.)»: más o menos un porcentaje, o entre un mínimo y un máximo. */
  function camposAprox(c) {
    const enUF = c.moneda === UF;
    return `<label class="marcar"><input type="checkbox" data-ce-aprox ${c.aproxActivo ? "checked" : ""}><span>El monto varía (aprox.)<small>${enUF
      ? "En UF ya te muestro un rango en pesos; márcalo si además el monto en UF cambia." : "Para cuentas que cambian un poco cada mes: te muestro un rango y lo reconozco aunque no sea exacto."}</small></span></label>
      ${c.aproxActivo && !String(c.buscarTexto || "").trim() && c.moneda !== UF ? `<p class="pista-campo">Pon palabras para reconocerlo: con un monto que varía, sin palabras no lo puedo reconocer en tu cartola.</p>` : ""}
      ${c.aproxActivo ? `<div class="aprox-campos"><label class="campo"><span>Cómo varía</span><select id="ce-aproxModo" data-ce="aproxModo" data-sin-traducir>
          <option value="variacion" ${c.aproxModo !== "rango" ? "selected" : ""}>${esc(tr("Más o menos un porcentaje"))}</option><option value="rango" ${c.aproxModo === "rango" ? "selected" : ""}>${esc(tr("Entre un mínimo y un máximo"))}</option></select></label>
        ${c.aproxModo === "rango" ? `<div class="dos">${campoNum("aproxMin", c.aproxMin, tr("Mínimo"))}${campoNum("aproxMax", c.aproxMax, tr("Máximo"))}</div>`
          : `<label class="campo"><span>Más o menos (%)</span><input class="texto" id="ce-aproxVariacion" inputmode="decimal" data-ce="aproxVariacion" value="${esc(formatoDecimal(c.aproxVariacion))}" data-sin-traducir></label>`}</div>` : ""}`;
  }
  /** Tras detectar un dividendo o algo con «UF»: «¿Se paga en UF?» (opcional). */
  function preguntaUF(k) {
    const c = k.c;
    if (!c.preguntar_uf) return "";
    return `<fieldset class="preguntas"><legend>¿Se paga en UF? <small>(opcional)</small></legend>
      <label class="marcar"><input type="checkbox" data-ce-uf ${c.moneda === UF ? "checked" : ""}><span>Sí, el monto está en UF<small data-sin-traducir>${c.moneda === UF && c.montoPesos
        ? T("Escribe cuántas UF son. Tu último pago fue de {x}: de ahí saco cuánto vale la UF.", { x: esc(dinero(c.montoPesos, monedaPrincipal())) })
        : esc(tr("Así te muestro un rango en pesos que sigue a la UF."))}</small></span></label></fieldset>`;
  }
  /** En UF: cuánto sería en pesos con lo último que sé de la UF, o cómo lo voy a saber. */
  function estimacionUF(c) {
    if (c.moneda !== UF) return "";
    const ref = ufConocida(), monto = c.monto || 0;
    if (!ref || !monto) return `<p class="pista-campo">${frase("Es una estimación: saco el valor de la UF de tu primer pago reconocido, o puedes escribirlo en Ajustes.", {})}</p>`;
    const borr = { id: "_", moneda: UF, monto, aproximado: c.aproxActivo ? (c.aproxModo === "rango" ? { min: c.aproxMin || monto, max: c.aproxMax || monto } : { variacion: c.aproxVariacion || 0 }) : null };
    const x = enMoneda(borr, E.hoy, { _: ref }, monedaPrincipal(), (ufCfg() || {}).variacion_mensual ?? UF_MENSUAL);
    return `<p class="pista-campo" data-sin-traducir>${T("Con la UF a {v}: {r}. Es una estimación.", { v: esc(dinero(ref.valor, monedaPrincipal())), r: detalleMonto(x) })}</p>`;
  }
  /** Lo que se va a guardar (o null y el error en el editor). Mismas reglas que compromisos.validar en Python. */
  function compromisoDelEditor(sinOpcionales) {
    const k = E.compEdit, c = k.c;
    const limpio = { id: c.id || nuevoIdComp(), nombre: String(c.nombre || "").replace(/\d(?:[\s.\-/]?\d){5,}/g, " ").replace(/\s+/g, " ").trim().slice(0, 60).trim(),
      tipo: c.tipo, signo: c.tipo === "ingreso" ? "ingreso" : c.signo === "ingreso" && (c.tipo === "transferencia" || c.tipo === "prestamo") ? "ingreso" : "gasto",
      monto: c.moneda === UF ? Math.round((Number(c.monto) || 0) * 10000) / 10000 : Number(c.monto) || 0, moneda: c.moneda || monedaPrincipal(), frecuencia: c.frecuencia, categoria: c.categoria || "",
      buscar: [...new Set(String(c.buscarTexto || "").split(",").map((p) => normalizar(p.replace(/\d(?:[\s.\-/]?\d){5,}/g, " "))).filter((p) => p.length >= 2 && p.length <= 40))].slice(0, 6),
      tolerancia: c.tolerancia ?? 5, activo: c.activo !== false, desde: c.desde || E.hoy, origen: c.origen || "manual", pagos: c.pagos || {} };
    if (pagaLaPersona({ ...c, signo: limpio.signo })) limpio.pago = pagoDelEditor(c);
    if (limpio.tipo === "prestamo") {
      // Préstamo entre personas: la cuota, la última y cuándo termina se calculan (igual que compromisos.validar en Python).
      limpio.con = String(c.con || "").replace(/\d/g, " ").replace(/\s+/g, " ").trim().slice(0, 30).trim();
      if (!limpio.con) return (k.error = tr("Falta con quién es el préstamo."), null);
      if (!(Number(c.prestamoTotal) > 0)) return (k.error = tr("Falta cuánto es el préstamo en total."), null);
      const n = Number(c.cuotas_total) || 0;
      if (!(Number.isInteger(n) && n >= 1 && n <= 1200)) return (k.error = tr("Falta en cuántas cuotas se paga."), null);
      const interes = Number(c.prestamoInteres) || 0;
      if (interes < 0 || interes > 100) return (k.error = tr("El interés tiene que ser un porcentaje entre 0 y 100."), null);
      // Una cuota fija (la del plan de préstamos) se mantiene mientras calce con el total y las cuotas; si no, se calcula.
      const calc = calcularPrestamo(Number(c.prestamoTotal), n, interes, limpio.moneda, Number(c.prestamoCuota) || null);
      Object.assign(limpio, { monto: calc.cuota, cuotas_total: n, cuotas_pagadas: Math.min(Number(c.cuotas_pagadas) || 0, n),
        prestamo: { total: calc.total, interes, cuota: calc.cuota, ultima: calc.ultima } });
      if (!limpio.nombre) limpio.nombre = (limpio.signo === "ingreso" ? tr("Préstamo a {p}") : tr("Préstamo de {p}")).replace("{p}", limpio.con).slice(0, 60);
    }
    if (!limpio.nombre) return (k.error = tr("Ponle un nombre."), null);
    if (!(limpio.monto > 0)) return (k.error = tr(limpio.moneda === UF ? "Falta el monto en UF." : "Falta el monto."), null);
    if (c.aproxActivo) {
      if (c.aproxModo === "rango") {
        const lo = Number(c.aproxMin) || 0, hi = Number(c.aproxMax) || 0;
        if (!(lo > 0 && hi > 0 && lo <= limpio.monto && limpio.monto <= hi)) return (k.error = tr("El monto tiene que estar entre el mínimo y el máximo."), null);
        limpio.aproximado = { min: lo, max: hi };
      } else {
        const v = Number(c.aproxVariacion);
        if (!(v > 0 && v <= 50)) return (k.error = tr("La variación va de 0 a 50 %."), null);
        limpio.aproximado = { variacion: v };
      }
    }
    if (limpio.frecuencia === "mensual" || limpio.frecuencia === "semanal") {
      const d = Number(c.dia), max = limpio.frecuencia === "mensual" ? 31 : 7;
      if (!(Number.isInteger(d) && d >= 1 && d <= max)) return (k.error = tr("Falta el día."), null);
      limpio.dia = d;
    } else {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(c.fecha || "")) return (k.error = tr("Falta la fecha."), null);
      limpio.fecha = c.fecha;
      if (limpio.frecuencia === "una_vez" && limpio.fecha < limpio.desde) limpio.desde = limpio.fecha;
    }
    if (limpio.tipo === "deuda" && !sinOpcionales) {
      const total = Number(c.cuotas_total) || 0, pagadas = Number(c.cuotas_pagadas) || 0;
      if (total) { limpio.cuotas_total = Math.min(1200, total); limpio.cuotas_pagadas = Math.min(pagadas, limpio.cuotas_total); }
      if (/^\d{4}-\d{2}-\d{2}$/.test(c.fecha_fin || "")) limpio.fecha_fin = c.fecha_fin;
      if (Number(c.saldo) > 0) limpio.saldo = Number(c.saldo);
    } else if (limpio.tipo === "deuda" && k.extraido) { limpio.cuotas_total = c.cuotas_total; limpio.cuotas_pagadas = c.cuotas_pagadas; }
    if (limpio.tipo === "prestamo" && limpio.frecuencia !== "una_vez") {
      const vs = vencimientos({ ...limpio, fecha_fin: null }, "2299-12-31").filter((o) => o.n);
      if (vs.length) limpio.fecha_fin = vs[vs.length - 1].vence;
    }
    k.error = "";
    return limpio;
  }
  function guardarCompromiso(sinOpcionales) {
    const c = compromisoDelEditor(sinOpcionales);
    if (!c) return render();
    const lista = listaCompromisos(), i = lista.findIndex((x) => x.id === c.id), k = E.compEdit;
    // «Es el mismo» desde el chat: el préstamo que ya estaba parte de nuevo con el plan (también cambia desde cuándo).
    const actualizar = !!k.actualizar && i >= 0 && c.tipo === "prestamo";
    if (i >= 0) lista[i] = { ...c, pagos: lista[i].pagos || {}, desde: actualizar ? c.desde : lista[i].desde }; else lista.push(c);
    E.compromisos.compromisos = lista;
    const enviar = { ...c }; delete enviar.pagos;
    host.enviar("compromiso", actualizar ? { accion: "actualizar_prestamo", id: c.id, hoy: E.hoy, compromiso: enviar } : { accion: "guardar", hoy: E.hoy, compromiso: enviar });
    if (k.sugerencia) E.sugerencias = (E.sugerencias || []).filter((s) => s.clave !== k.sugerencia);
    if (E.importar && k.detectado != null) { E.importar.hechos = { ...(E.importar.hechos || {}), [k.detectado]: "agregado" }; E.importar.paso = "listo"; }
    if (k.chat) marcarAccionChat(k.chat, "hecha", true);
    E.compEdit = null;
    toast(i >= 0 ? "Compromiso guardado" : "Listo: lo voy a reconocer en tu cartola y te recuerdo si falta");
    render();
  }
  function editarDesdeSugerencia(s, extra = {}) {
    E.compEdit = { c: borradorDe({ ...s, origen: "detectado" }), origen: "detectado", extraido: !!s.cuotas_total, sugerencia: s.clave, error: "", ...extra };
  }
  /** Pagos: primero lo que falta este mes (lo atrasado arriba, con «Ya lo pagué»), el total en una línea, después lo pagado,
   *  lo que entra, lo que parece repetirse y todo lo que estás pagando agrupado por tipo. Agregar va en «+». */
  function vistaCompromisos() {
    const e = estadoDelMes(), enCurso = E.mes === periodoHoy();
    const gastos = e.items.filter((i) => i.signo === "gasto"), ingresos = e.items.filter((i) => i.signo === "ingreso");
    const orden = { atrasado: 0, hoy: 1, esperando: 2, pendiente: 3, pagado: 4 };
    const ordenar = (l) => [...l].sort((a, b) => orden[a.estado] - orden[b.estado] || (a.vence < b.vence ? -1 : a.vence > b.vence ? 1 : 0));
    const g = gastoMaximo(E.movimientos, listaCompromisos(), E.mes, E.hoy, E.categorias, mesesCompletos(), monedaPrincipal(), per(), ufCfg());
    const hay = listaCompromisos().length;
    const anotar = `<button class="boton sutil" data-accion="agregar-contar">＋ <span>Anotar un pago</span></button>`;
    if (!hay && !(E.sugerencias || []).length) {
      return `<div class="contenido"><div class="encabezado"><h1>Pagos</h1></div>
        <section class="vacio corto"><p>${frase("Lo que pagas o recibes seguido: deudas, cuentas, suscripciones, transferencias y tu sueldo. Alcancía **reconoce el pago en tu cartola** y te recuerda lo que falta, para que no se te olvide nada.", {})}</p>
          <button class="boton principal" data-accion="agregar-contar">＋ <span>Anotar un pago</span></button></section></div>`;
    }
    // Lo que pagas tú (y lo automático sin cargo pasada la gracia) arriba; lo que se paga solo, aparte y sin «Ya lo pagué».
    const falta = ordenar(gastos.filter((i) => i.estado !== "pagado" && !seCobraSolo(i))), solos = ordenar(gastos.filter(seCobraSolo));
    const pagados = ordenar(gastos.filter((i) => i.estado === "pagado"));
    const aprox = e.total_max !== e.total || e.arrastre_max !== e.arrastre;
    const resumenLinea = hay ? `<p class="linea-total" data-sin-traducir>${T("Este mes: {t} en pagos · pagado {p} · falta {f}", { t: (aprox ? "≈ " : "") + esc(dinero(e.total + e.arrastre)), p: esc(dinero(e.pagado)),
        f: `<b>${e.aprox ? "≈ " : ""}${esc(dinero(e.pendiente))}</b>` })}${e.atrasado ? " · " + `<span class="rojo-txt">${T("{x} atrasado", { x: esc(dinero(e.atrasado)) })}</span>` : ""}</p>
      ${enCurso && g.disponible != null ? `<p class="linea-maximo">${g.alcanza ? frase("Después de tus compromisos, este mes puedes gastar hasta **{x}** en lo variable.", { x: esc(dinero(g.disponible)) })
        : frase("Este mes tus compromisos y gastos fijos suman más de lo que entra.", {})} <button class="enlace" data-vista="presupuesto">Ver el detalle</button></p>` : ""}` : "";
    const listaMes = hay ? `<section class="seccion-pagos"><h2 class="titulo-seccion" data-sin-traducir>${falta.length ? T("Falta pagar en {m}", { m: esc(nombreMes(E.mes)) }) : T("En {m}", { m: esc(nombreMes(E.mes)) })}</h2>
        ${falta.length ? falta.map((i) => filaCompromiso(i, true)).join("") : `<p class="al-dia ok"><span class="punto" aria-hidden="true"></span><span>${solos.length ? frase("**Estás al día.** Lo que queda se paga solo.", {}) : frase("**Estás al día.** Pagaste todo lo de este mes.", {})}</span></p>`}
        ${solos.length ? `<h3 class="grupo">Se paga solo</h3>${solos.map((i) => filaCompromiso(i, true)).join("")}` : ""}
        ${pagados.length ? `<h3 class="grupo">Pagado</h3>${pagados.map((i) => filaCompromiso(i, true)).join("")}` : ""}
        ${ingresos.length ? `<h3 class="grupo">Ingresos</h3>${ordenar(ingresos).map((i) => filaCompromiso(i, true)).join("")}` : ""}</section>` : "";
    const avisos = `<section class="tarjeta"><div class="fila sin-borde"><div class="txt"><b>Avisarme antes de que venza</b>
        <small>Un aviso 3 días antes, el día que vence y si se atrasa. Como máximo uno por compromiso al día. De lo que se paga solo, solo si no veo el cargo.</small></div>
        <label class="interruptor"><input type="checkbox" data-avisos ${E.config.avisos ? "checked" : ""}><span class="visual" aria-hidden="true"></span><span class="oculto-accesible">Avisarme antes de que venza</span></label></div></section>`;
    const sinValor = e.compromisos.some((c) => c.original && c.original.sin_valor);
    const invitaUF = sinValor ? `<section class="tarjeta invita-uf"><h2>¿Cuánto vale la UF hoy?</h2>
      <p class="texto-suave">${frase("Tienes compromisos en UF y aún no sé cuánto son en pesos. Escribe el valor de la UF de hoy (sale en tu banco o en las noticias) y te muestro un rango. Cuando reconozca tu primer pago, lo saco de ahí.", {})}</p>${campoUF()}</section>` : "";
    return `<div class="contenido"><div class="encabezado"><h1>Pagos</h1>${hay ? selectorMes() : ""}</div>
      ${resumenLinea}${invitaUF}${listaMes}${seccionSugerencias()}${hay ? seccionLoQuePagas(e) : ""}${hay ? avisos : ""}
      <div class="pie-vista">${anotar}</div></div>`;
  }
  /** Gasto máximo sugerido (en Presupuesto): lo que entra − compromisos − otros fijos, repartido según lo que gastas normalmente. */
  function tarjetaGastoMaximo() {
    const g = gastoMaximo(E.movimientos, listaCompromisos(), E.mes, E.hoy, E.categorias, mesesCompletos(), monedaPrincipal(), per(), ufCfg());
    const cab = `<div class="tarjeta-cabeza"><h2>Gasto máximo sugerido</h2></div>`;
    if (g.ingreso == null) return `<section class="tarjeta maximo">${cab}<p class="texto-suave">Cuando sepa cuánto te entra al mes (anota tu sueldo en Pagos o agrega cartolas con tus ingresos), aquí te digo cuánto puedes gastar en lo variable.</p></section>`;
    const origen = g.fuente === "compromisos" ? tr("Según los ingresos que anotaste en Pagos.") : tr("Según el promedio de lo que te entró los últimos meses.");
    const desglose = frase("Entra {i} · compromisos {c} · otros gastos fijos {f}", { i: esc(dinero(g.ingreso)), c: esc(dinero(g.compromisos)), f: esc(dinero(g.otros_fijos)) }, "small");
    if (!g.alcanza) {
      return `<section class="tarjeta maximo">${cab}<div class="ritmo ojo">🫶 ${frase("Este mes lo comprometido ({c}) es más de lo que entra ({i}): faltan {x}.", { c: esc(dinero(g.compromisos + g.otros_fijos)), i: esc(dinero(g.ingreso)), x: esc(dinero(-(g.disponible || 0))) })}</div>
        <p class="texto-suave">Respira: tenerlo claro ya es avanzar. Mira si algún compromiso se puede mover de fecha o si algún gasto fijo se puede bajar, y anota en Pagos lo que tengas claro.</p>
        <p class="pie-maximo">${desglose} <small data-sin-traducir>${esc(origen)}</small></p></section>`;
    }
    const filas = g.por_categoria.filter((x) => x.maximo > 0 || x.gastado > 0).map((x) => {
      const c = cat(x.categoria), pct = x.maximo ? Math.min(100, x.gastado / x.maximo * 100) : 100;
      return `<div class="cat"><span class="emoji" aria-hidden="true">${c.emoji}</span><span class="nombre" data-sin-traducir>${esc(nombreCat(c))}</span>
        <span class="monto" data-sin-traducir>${esc(dinero(x.gastado))} <small>/ ${esc(dinero(x.maximo))}</small></span>
        <span class="barra ${x.gastado > x.maximo ? "pasado" : x.gastado > x.maximo * 0.85 ? "ojo" : ""}"><i style="width:${pct.toFixed(1)}%"></i></span></div>`;
    }).join("");
    const aprox = estadoDelMes().aprox ? `<small data-sin-traducir>${esc(tr("Con los montos aproximados o en UF uso el máximo de cada uno, para que no te quedes corto."))}</small>` : "";
    return `<section class="tarjeta maximo">${cab}<p class="maximo-cifra">${frase("Este mes puedes gastar hasta **{x}** en lo variable.", { x: esc(dinero(g.disponible)) })}</p>
      <p class="pie-maximo">${desglose} <small data-sin-traducir>${esc(origen)}</small>${aprox}</p>
      ${filas ? `<p class="pista-cat">Máximo por categoría, según lo que gastas normalmente, y lo que llevas este mes:</p>${filas}
        <div class="pie-dialogo"><button class="boton" data-accion="usar-maximos">Usar estos máximos como topes</button></div>` : ""}</section>`;
  }
  /** Tras importar (o sincronizar): lo que parece un compromiso en lo nuevo, para agregarlo con un toque. */
  function detectadosHTML(r) {
    const lista = r.detectados || [];
    if (!lista.length) return "";
    const hechos = E.importar.hechos || {};
    return `<div class="detectados"><h3>Encontré pagos que parecen repetirse</h3>
      <p class="texto-suave">¿Son compromisos? Si los agregas, te aviso cuando falten y sé cuánto te queda.</p>
      ${lista.map((s, n) => `<div class="sugerencia"><span class="emoji" aria-hidden="true">${iconoComp(s)}</span><div class="txt">${textoSugerencia(s)}
        ${s.cuotas_total ? `<small data-sin-traducir>${T("Según tu cartola vas en la cuota {n} de {t}.", { n: s.cuotas_pagadas, t: s.cuotas_total })}</small>` : ""}</div>
        <div class="acciones">${hechos[n] === "agregado" ? `<span class="ok-txt">✓ Agregado</span>` : hechos[n] === "no" ? `<span class="texto-suave">No es</span>`
          : `<button class="boton sutil" data-det-no="${n}">No es</button><button class="boton principal" data-det-agregar="${n}">Agregar</button>`}</div></div>`).join("")}</div>`;
  }

  // ───────────── Diálogos ─────────────
  function filasIA() {
    return E.ias.map((ia) => {
      const enUso = E.config.ia === ia.id, probando = E.probando[ia.id], r = E.resultadoIA[ia.id];
      const estado = !ia.instalada ? `<small>No está instalada · <a href="#" data-enlace="${ENLACES.guiaIA}#${ia.id}">Cómo instalarla</a></small>`
        : r && !r.ok ? `<small class="error-txt" data-sin-traducir>${esc(r.texto || tr("No respondió."))}</small>` : `<small>Instalada</small>`;
      const accion = enUso ? `<span class="ok">✓ En uso</span>` : ia.instalada
        ? `<button class="boton" data-probar="${esc(ia.id)}" ${probando ? "disabled" : ""}>${probando ? "Probando…" : "Usar"}</button>` : "";
      return `<div class="fila"><div class="txt"><b data-sin-traducir>${esc(ia.nombre)}</b>${estado}</div>${accion}</div>`;
    }).join("");
  }
  function camposPais() {
    return `<div class="dos"><label class="campo"><span>País</span><select data-config="pais">${PAISES.map(([id, n]) =>
      `<option value="${id}" ${E.config.pais === id ? "selected" : ""}>${n}</option>`).join("")}</select></label>
      <label class="campo"><span>Moneda principal</span><select data-config="moneda">${MONEDAS.map((m) =>
        `<option value="${m}" ${(E.config.moneda || "CLP") === m ? "selected" : ""} data-sin-traducir>${m}</option>`).join("")}</select></label></div>`;
  }
  const RESPALDOS = [["nube", "☁️", "En tu nube", "iCloud Drive, Google Drive, OneDrive o Dropbox. Lo más simple."],
    ["git", "🐙", "En tu GitHub o GitLab", "En un repositorio privado de tu cuenta."], ["local", "💻", "Solo en este computador", "Sin respaldo por ahora. Lo puedes activar después."]];
  function opcionesRespaldo() {
    return `<div class="candado"><span class="grande-ico" aria-hidden="true">🔐</span><div><b>Tus datos se guardan con candado.</b><br>
      Tu respaldo viaja y se guarda cerrado con llave, y la llave queda solo en tu computador. Ni GitHub, ni Google, ni nosotros podemos abrirlo. Son tus datos y de nadie más.</div></div>
      ${RESPALDOS.map(([id, ico, n, d]) => `<button class="opcion" role="radio" aria-checked="${(E.config.respaldo || "local") === id}" data-respaldo="${id}">
        <span aria-hidden="true" style="font-size:20px">${ico}</span><span class="txt"><b><span>${n}</span>${id !== "local" ? `<span class="chip pronto">Muy pronto</span>` : ""}</b><small>${d}</small></span></button>`).join("")}`;
  }

  function dialogoImportar() {
    const im = E.importar, ia = esc(nombreIA());
    const cab = `<h2 id="t-importar">Agregar movimientos</h2>`;
    const cerrar = `<button class="boton" data-accion="cerrar-importar">Cancelar</button>`;
    const muestra = (lista) => `<table class="tabla-muestra" data-sin-traducir>${(lista || []).map((m) => `<tr><td>${esc(m.fecha)}</td><td>${esc(m.descripcion)}</td>
      <td class="${m.monto > 0 ? "ingreso" : ""}">${esc(dinero(m.monto, m.moneda, true))}</td></tr>`).join("")}</table>`;
    switch (im.paso) {
      case "leyendo": case "aprendiendo": case "guardando": {
        const p = im.progreso;
        const texto = im.paso === "leyendo" ? T("Leyendo {x}…", { x: esc(im.nombre) }) : im.paso === "aprendiendo" ? T("{ia} está aprendiendo a leer este archivo…", { ia }) : esc(p?.texto || tr("Guardando…"));
        return `${cab}<div class="progreso"><p data-sin-traducir>${texto}</p><div class="barra ${p?.paso ? "" : "indef"}"><i style="width:${p?.paso ? Math.round(p.paso / p.total * 100) : 0}%"></i></div>
          ${p?.paso ? `<small>${frase("Paso {n} de {t}", { n: p.paso, t: p.total })}</small>` : ""}</div>`;
      }
      case "vista": {
        const v = im.vista;
        return `${cab}<p>${frase("Encontré **{n} movimientos** de {b}, del {d} al {h}.", { n: v.total, b: esc(v.receta.institucion || v.receta.nombre), d: esc(v.desde), h: esc(v.hasta) })}</p>
          ${muestra(v.muestra)}
          <label class="marcar"><input type="checkbox" data-importar-ia ${im.ia ? "checked" : ""}><span>${frase("Que {ia} ponga las categorías que falten", { ia })}<small>Usa tu propia cuenta. Solo ve la descripción y el monto de cada movimiento.</small></span></label>
          ${(v.avisos || []).length ? `<details class="texto-suave" style="color:var(--suave);font-size:12.5px"><summary>${frase("{n} filas no eran movimientos", { n: v.avisos.length })}</summary><ul data-sin-traducir>${v.avisos.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></details>` : ""}
          <div class="pie-dialogo">${cerrar}<button class="boton principal" data-accion="importar-guardar">Agregar</button></div>`;
      }
      case "sin_receta":
        return `${cab}<p>${frase("Todavía no sé leer «{x}». Pasa con bancos nuevos: cada uno arma su cartola a su manera.", { x: esc(im.nombre) })}</p>
          <div class="candado"><span class="grande-ico" aria-hidden="true">🧠</span><div>${frase("{ia} puede mirar las primeras filas y aprender a leerlo. Después te muestro cómo quedó antes de guardar nada.", { ia })}</div></div>
          ${im.error ? `<p class="error-txt" data-sin-traducir>${esc(im.error)}</p>` : ""}
          <div class="pie-dialogo">${cerrar}<button class="boton principal" data-accion="aprender-receta">${frase("Que {ia} aprenda a leerlo", { ia })}</button></div>`;
      case "receta": {
        const v = im.vista;
        return `${cab}<p>${frase("{ia} aprendió a leerlo: encontré **{n} movimientos**. ¿Se ven bien?", { ia, n: v.total })}</p>${muestra(v.muestra)}
          <label class="marcar"><input type="checkbox" data-importar-ia ${im.ia ? "checked" : ""}><span>${frase("Que {ia} ponga las categorías que falten", { ia })}</span></label>
          <label class="marcar"><input type="checkbox" data-compartir ${im.compartir ? "checked" : ""}><span>Compartir la receta con la comunidad<small>Solo cómo se lee este tipo de archivo (nombres de columnas y formatos), nunca tus movimientos. Así la próxima persona con este banco no tiene que esperar.</small></span></label>
          <div class="pie-dialogo"><button class="boton izq" data-accion="receta-mal">No, se ven mal</button>${cerrar}<button class="boton principal" data-accion="importar-guardar">Sí, agregar</button></div>`;
      }
      case "listo": {
        const r = im.resultado;
        return `${cab}<p style="font-size:16px;color:var(--texto)">🎉 ${frase(r.nuevos === 1 ? "Listo: 1 movimiento nuevo." : "Listo: {n} movimientos nuevos.", { n: r.nuevos })}
          ${r.repetidos ? " " + frase("{n} ya estaban y no se duplicaron.", { n: r.repetidos }) : ""}</p>
          ${r.error_ia ? `<p class="error-txt" data-sin-traducir>${esc(r.error_ia)}</p>` : ""}
          ${r.sin_categoria ? `<p>${frase("Quedaron {n} sin categoría: ponles una en Movimientos.", { n: r.sin_categoria })}</p>` : ""}
          ${detectadosHTML(r)}
          <div class="pie-dialogo"><button class="boton" data-accion="importar">Agregar otra</button><button class="boton principal" data-accion="ver-movimientos">Ver movimientos</button></div>`;
      }
      case "compromiso":
        return E.compEdit ? editorCompromiso().replace('id="t-comp"', 'id="t-importar"') : "";
      case "error":
        return `${cab}<p class="error-txt" data-sin-traducir>${esc(im.error || "")}</p><div class="pie-dialogo">${cerrar}<button class="boton principal" data-accion="elegir-cartola">Elegir otro archivo</button></div>`;
      default:
        return `${cab}<p>Descarga la cartola desde la página de tu banco o billetera y elígela aquí. Se lee en tu computador: nada sale de aquí.</p>
          <div class="zona-archivo"><span class="grande-ico" aria-hidden="true">📄</span><button class="boton principal" data-accion="elegir-cartola">Elegir archivo</button>
            <small>CSV, Excel (.xlsx), PDF con texto, OFX, QIF o CAMT.053. Si la subes dos veces, no se duplica nada.</small></div>
          <div class="pie-dialogo">${cerrar}</div>`;
    }
  }

  function dialogoAjustes() {
    return `<h2 id="t-ajustes">Ajustes</h2><p>Todo se procesa en tu computador. La IA usa tu propia cuenta.</p>
      <div class="seccion"><h3>Tu IA</h3>${filasIA()}</div>
      <div class="seccion"><h3>País y moneda</h3>${camposPais()}</div>
      <div class="seccion"><h3>Tu mes</h3>${campoInicioMes()}</div>
      ${E.config.pais === "CL" || hayUF() ? `<div class="seccion"><h3>Unidad de Fomento (UF)</h3><p class="texto-suave intro-campo">Para tus compromisos en UF, como un dividendo.</p>${campoUF()}</div>` : ""}
      <div class="seccion"><h3>Respaldo</h3>${opcionesRespaldo()}</div>
      <div class="seccion"><h3>General</h3>
        <div class="fila"><div class="txt"><b>Idioma de la app</b></div><select data-config="idioma_ui"><option value="es" ${E.idioma === "es" ? "selected" : ""}>Español</option><option value="en" ${E.idioma === "en" ? "selected" : ""}>English</option></select></div>
        <div class="fila"><div class="txt"><b>Carpeta de tus datos</b><small data-sin-traducir>${esc(E.carpeta)}</small></div><button class="boton" data-accion="abrir-carpeta">Abrir</button></div></div>
      <div class="seccion"><h3>Acerca de Alcancía</h3><p style="margin:0 0 8px;color:var(--suave)">${frase("Alcancía {v} · Gratis y de código abierto (AGPL-3.0).", { v: esc(E.version) })}</p>
        <div class="fila"><div class="txt"><b>Actualizaciones</b><small>${E.buscando === "buscando" ? "Buscando…" : E.buscando === "alDia" ? "Estás en la última versión." : E.buscando === "sinConexion" ? "No pude revisar: ¿hay internet?" : E.actualizacion?.hay ? "Hay una versión nueva." : "Alcancía revisa sola cada 6 horas."}</small></div>
          ${E.actualizacion?.hay ? `<button class="boton principal" data-accion="actualizar">Actualizar</button>` : `<button class="boton" data-accion="buscar-act" ${E.buscando === "buscando" ? "disabled" : ""}>Buscar actualizaciones</button>`}</div>
        <div class="enlaces"><a href="#" data-enlace="${ENLACES.sitio}">Sitio web</a><a href="#" data-enlace="${ENLACES.codigo}">Código</a><a href="#" data-enlace="${ENLACES.comunidad}">Comunidad</a></div></div>
      <div class="pie-dialogo"><button class="boton principal" data-accion="cerrar">Listo</button></div>`;
  }

  /** Paso 0 de la bienvenida: lo primero es el idioma, antes de cualquier otra pregunta. Cada opción va escrita en su propio idioma
   *  (nada pasa por el traductor) y la del equipo viene marcada como sugerida y con el foco. */
  function pasoIdioma(marcas) {
    const sugerido = idiomaDelSistema();
    const opcion = (codigo, nombre, nota) => {
      const es = codigo === sugerido;
      return `<button type="button" id="bv-idioma-${codigo}" class="boton opcion-idioma ${es ? "principal" : ""}" data-idioma-bv="${codigo}" lang="${codigo}" data-sin-traducir>
        <b>${nombre}</b>${es ? `<small>${nota}</small>` : ""}</button>`;
    };
    return `${marcas}<div class="paso-idioma">${LOGO}<h2 id="t-bv" tabindex="-1" data-sin-traducir><span lang="es">Elige tu idioma</span> <span aria-hidden="true">·</span> <span lang="en">Choose your language</span></h2>
      <div class="opciones-idioma">${opcion("es", "Español", "Idioma de tu equipo")}${opcion("en", "English", "Your device’s language")}</div>
      <p class="nota-idioma" data-sin-traducir><span lang="es">Puedes cambiarlo cuando quieras en Ajustes.</span> <span lang="en">You can change it anytime in Settings.</span></p></div>`;
  }

  function bienvenida() {
    const paso = E.bv, total = 6;
    const marcas = `<div class="pasos-bv" aria-hidden="true">${Array.from({ length: total }, (_, i) => `<i class="${i <= paso ? "hecho" : ""}"></i>`).join("")}</div>`;
    if (paso === 0) return pasoIdioma(marcas);
    const pasos = [
      null,
      ["Hola, esto es Alcancía", `<p>Para quienes nos cuesta medirnos en los gastos. Juntas tus cartolas, Alcancía las ordena y tu IA te avisa a tiempo cuando algo se está pasando.</p>
        <div class="pasos-vacio" style="margin:0"><div><b>📄</b><span>Lee las cartolas de cualquier banco o billetera del mundo.</span></div>
        <div><b>✦</b><span>Tu propia IA pone las categorías y te da consejos concretos.</span></div>
        <div><b>🔐</b><span>Tus datos quedan en tu computador. Sin cuentas, sin publicidad, gratis.</span></div></div>`, true],
      ["¿Dónde vives?", `<p>Para mostrar bien la plata y sugerirte las recetas de los bancos de tu país.</p>${camposPais()}<div class="seccion">${campoInicioMes()}</div>`, true],
      ["Elige tu IA", `<p>Alcancía usa la IA que ya tienes, con tu cuenta. La probamos con una pregunta corta.</p><div class="seccion">${filasIA()}</div>`, !!E.config.ia],
      ["Tu respaldo", opcionesRespaldo(), true],
      ["Tu primera cartola", `<p>Descarga la cartola de tu banco o billetera (CSV, Excel o PDF) y agrégala. Si tu banco aún no está, tu IA aprende a leerlo.</p>
        <button class="boton principal grande" data-accion="bv-importar">＋ <span>Agregar mi primera cartola</span></button>`, true],
    ];
    const [titulo, cuerpo, puede] = pasos[paso];
    return `${marcas}<h2 id="t-bv" tabindex="-1">${titulo}</h2>${cuerpo}
      <div class="pie-dialogo" style="margin-top:18px">${paso > 0 ? `<button class="boton izq" data-bv="${paso - 1}">Atrás</button>` : ""}
        ${paso < total - 1 ? `<button class="boton" data-accion="bv-despues">Lo hago después</button><button class="boton principal" data-bv="${paso + 1}" ${puede ? "" : "disabled"}>Siguiente</button>`
          : `<button class="boton" data-accion="bv-fin">Empezar sin cartola</button>`}</div>`;
  }

  function dialogos() {
    const capa = (id, html) => `<div class="capa"><div class="dialogo" role="dialog" aria-modal="true" aria-labelledby="${id}">${html}</div></div>`;
    if (E.importar) return capa("t-importar", dialogoImportar());
    if (E.conectar) return capa("t-conectar", dialogoConectar());
    if (E.bv !== null) return capa("t-bv", bienvenida());
    if (E.ajustes) return capa("t-ajustes", dialogoAjustes());
    if (E.compEdit) return capa("t-comp", `<div class="editor-comp" id="editor-comp">${editorCompromiso()}</div>`);
    if (E.agregar === "contar") return `<div class="capa capa-chat"><div class="dialogo dialogo-chat" role="dialog" aria-modal="true" aria-labelledby="t-chat">${dialogoChat()}</div></div>`;
    if (E.agregar) return capa("t-agregar", dialogoAgregar());
    return "";
  }

  // ───────────── Eventos ─────────────
  const ocupadoImportando = () => ["leyendo", "aprendiendo", "guardando"].includes(E.importar?.paso);
  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-accion],[data-vista],[data-mes],[data-probar],[data-bv],[data-idioma-bv],[data-enlace],[data-respaldo],[data-consejo],[data-conectar],[data-sincronizar],[data-desconectar],[data-mcp],[data-mcp-quitar],[data-historia],[data-comp-pagado],[data-comp-noes],[data-comp-desmarcar],[data-comp-editar],[data-sug-agregar],[data-sug-no],[data-det-agregar],[data-det-no],[data-cifra],[data-cifra-abrir],[data-ir-cat],[data-elegir],[data-pick],[data-nueva-cat],[data-nueva-emoji],[data-nueva-cancelar],[data-nueva-guardar],[data-cerrar-picker],[data-saldo-editar],[data-saldo-cancelar],[data-regla-si],[data-regla-no],[data-grupo-mov],[data-sueldo],[data-mov-ver],[data-chat],[data-chat-sugerencia]");
    if (!el) return;
    const d = el.dataset;
    if (d.chat) return accionChat(d);
    if (d.chatSugerencia != null) {
      const s = SUGERENCIAS_CHAT[Number(d.chatSugerencia)];
      if (!s) return;
      E.chat.texto = tr(s[1]); render();
      const t = $("#chat-texto"); if (t) { t.focus(); t.setSelectionRange(t.value.length, t.value.length); }
      return;
    }
    if (d.movVer) { E.movVer = E.movVer === d.movVer ? null : d.movVer; render(); return $(`[data-mov-ver="${CSS.escape(d.movVer)}"]`)?.focus(); }
    if (d.grupoMov != null) { E.grupoMov = E.grupoMov === d.grupoMov ? null : d.grupoMov; render(); return $(`[data-grupo-mov="${CSS.escape(d.grupoMov)}"]`)?.focus(); }
    if (d.enlace) { ev.preventDefault(); return host.enviar("abrirEnlace", { url: d.enlace }); }
    if (d.cerrarPicker != null) { const id = E.picker?.id; E.picker = null; render(); return document.getElementById("chip-" + id)?.focus(); }
    if (d.vista) {
      const cambia = E.vista !== d.vista;
      E.vista = d.vista; E.presEdit = null; E.picker = null; E.agregar = null; E.movVer = null;
      if (d.vista === "ordenar") E.ordenar = { i: 0, buscar: "", nueva: null };
      render();
      if (cambia) { const a = $(".principal-area"); if (a) a.scrollTop = 0; window.scrollTo?.(0, 0); }
      if (d.vista === "ordenar") $(".vista-ordenar")?.focus();
      else if (el.closest(".nav")) $(`.nav [data-vista="${d.vista}"]`)?.focus();
      return;
    }
    if (d.cifra || d.cifraAbrir) { E.cifra = d.cifraAbrir || (E.cifra === d.cifra ? null : d.cifra); E.saldoAviso = null; render(); if (d.cifraAbrir) $("#desglose")?.scrollIntoView?.({ block: "nearest" }); return $(`[data-cifra="${E.cifra}"]`)?.focus(); }
    if (d.irCat != null) {
      if (!d.irCat) { E.vista = "ordenar"; E.ordenar = { i: 0, buscar: "", nueva: null }; return render(); }
      E.vista = "movimientos"; E.filtro = { texto: "", categoria: d.irCat }; return render();
    }
    if (d.elegir) return abrirPicker(d.elegir);
    if (d.pick != null) { const m = movDe(d.lugar); if (m) elegirCategoria(m, d.pick, d.lugar); return; }
    if (d.nuevaCat) {
      const k = estadoElegidor(d.nuevaCat), nombre = d.conNombre ? String(k.buscar || "").trim() : "";
      k.nueva = { nombre, emoji: "", error: "" };
      if (nombre) return crearCategoria(d.nuevaCat);
      render(); return $(`#${d.nuevaCat}-nueva`)?.focus();
    }
    if (d.nuevaEmoji) { const k = estadoElegidor(d.lugar); if (k?.nueva) { k.nueva.emoji = d.nuevaEmoji; render(); $(`[data-nueva-emoji="${d.nuevaEmoji}"]`)?.focus(); } return; }
    if (d.nuevaCancelar) { estadoElegidor(d.nuevaCancelar).nueva = null; render(); return $(`#${d.nuevaCancelar}-buscar`)?.focus(); }
    if (d.nuevaGuardar) return crearCategoria(d.nuevaGuardar);
    if (d.saldoEditar) { E.saldoEdit = { cuenta: d.saldoEditar, texto: "" }; E.saldoAviso = null; render(); return $(`#saldo-${CSS.escape(d.saldoEditar)}`)?.focus(); }
    if (d.saldoCancelar != null) { E.saldoEdit = null; return render(); }
    if (d.reglaSi) {
      const r = { contiene: d.reglaSi, categoria: d.reglaCat };
      host.enviar("regla", r); E.reglas.push(r); aplicarRegla(r); toast("Aprendido"); return render();
    }
    if (d.reglaNo) { E.reglasNo = [...(E.reglasNo || []), d.reglaNo]; return render(); }
    if (d.mes) { E.mes = d.mes; E.aprender = null; return render(); }
    if (d.historia != null) { E.histCat = E.histCat === d.historia ? null : d.historia; render(); $(`[data-historia="${CSS.escape(d.historia)}"]`)?.focus(); return; }
    if (d.probar) { E.probando[d.probar] = true; delete E.resultadoIA[d.probar]; host.enviar("probarIA", { id: d.probar }); return render(); }
    if (d.bv) { E.bv = Number(d.bv); return render(); }
    if (d.idiomaBv) return elegirIdioma(d.idiomaBv);
    if (d.respaldo) { if (d.respaldo !== "local") return toast("Muy pronto: el respaldo con candado llega en la próxima versión"); E.config.respaldo = d.respaldo; host.enviar("config", { respaldo: d.respaldo }); return render(); }
    if (d.consejo) { E.consejoSel = d.consejo; return render(); }
    if (d.conectar) { E.conectar = { id: d.conectar, campos: {}, error: "", enviando: false }; render(); const p = $(".campos-conectar input"); if (p) p.focus(); return; }
    if (d.mcp || d.mcpQuitar) { const id = d.mcp || d.mcpQuitar; E.mcpOcupado[id] = true; delete E.mcpError[id]; host.enviar("mcpConectar", { cliente: id, quitar: !!d.mcpQuitar }); return render(); }
    if (d.sueldo) {
      if (d.sueldo === "no" || d.sueldo === "cerrar") { guardarLocal("alcancia.sueldoNoHoy", E.hoy); E.sueldoPregunta = null; if (d.sueldo === "no") toast("Entendido: vuelvo a mirar mañana"); return render(); }
      if (d.sueldo === "pagaron") { E.sueldoPregunta = "pagaron"; render(); return $(".linea-mes.pregunta button")?.focus(); }
      if (d.sueldo === "noes") { E.sueldoCandidatoNo = d.sueldoMov; return render(); }
      if (d.sueldo === "es") { const m = E.movimientos.find((x) => x.id === d.sueldoMov); return m && sueldoRecibido(m.fecha); }
      if (d.sueldo === "hoy") return sueldoRecibido(E.hoy);
    }
    if (d.sincronizar) { E.sincronizando[d.sincronizar] = true; host.enviar("sincronizar", { conector: d.sincronizar }); return render(); }
    if (d.desconectar) { host.enviar("desconectar", { conector: d.desconectar }); E.conexiones[d.desconectar] = { conectado: false }; toast("Desconectado. Tus movimientos siguen aquí."); return render(); }
    if (d.compPagado || d.compDesmarcar || d.compNoes) return marcarCompromiso(d);
    if (d.compEditar) {
      const c = listaCompromisos().find((x) => x.id === d.compEditar);
      if (c) { E.compEdit = { c: borradorDe(c), origen: c.origen, error: "" }; render(); enfocarEditor(); }
      return;
    }
    if (d.sugAgregar || d.sugNo) {
      const s = (E.sugerencias || []).find((x) => x.clave === (d.sugAgregar || d.sugNo));
      if (!s) return;
      if (d.sugNo) { E.compromisos.descartados = [...(E.compromisos.descartados || []), s.clave]; host.enviar("compromiso", { accion: "descartar", clave: s.clave }); toast("Listo: no te lo vuelvo a sugerir"); return render(); }
      editarDesdeSugerencia(s); render(); return enfocarEditor();
    }
    if (d.detAgregar != null || d.detNo != null) {
      const n = Number(d.detAgregar ?? d.detNo), s = E.importar?.resultado?.detectados?.[n];
      if (!s) return;
      if (d.detNo != null) { E.importar.hechos = { ...(E.importar.hechos || {}), [n]: "no" }; host.enviar("compromiso", { accion: "descartar", clave: s.clave }); return render(); }
      editarDesdeSugerencia(s, { detectado: n }); E.importar.paso = "compromiso"; render(); return $("#ce-nombre")?.focus();
    }
    const im = E.importar;
    switch (d.accion) {
      case "ajustes": E.ajustes = true; E.agregar = null; return render();
      case "agregar": E.agregar = "menu"; render(); return $(".opcion-agregar")?.focus();
      case "agregar-contar": case "abrir-chat": E.agregar = "contar"; E.chat.bajar = true; E.chat.confirmarBorrar = false; render(); return ($("#chat-texto") || $('.dialogo [data-accion="chat-ajustes"]'))?.focus();
      case "chat-enviar": return enviarChat();
      case "chat-ajustes": E.agregar = null; E.ajustes = true; return render();
      case "chat-borrar": E.chat.confirmarBorrar = true; render(); return $('[data-accion="chat-borrar-si"]')?.focus();
      case "chat-no-borrar": E.chat.confirmarBorrar = false; return render();
      case "chat-borrar-si": E.chat = { ...E.chat, mensajes: [], confirmarBorrar: false }; host.enviar("chat", { accion: "borrar" }); toast("Conversación borrada"); render(); return $("#chat-texto")?.focus();
      case "cerrar-agregar": E.agregar = null; render(); return $(".nav-agregar")?.focus();
      case "filtro-ordenar": E.filtro = { ...E.filtro, categoria: E.filtro.categoria === "__sin" ? "" : "__sin" }; render(); return $('[data-accion="filtro-ordenar"]')?.focus();
      case "ajustes-mes": E.ajustes = true; render(); return $("#inicio-modo")?.focus();
      case "cerrar": E.ajustes = false; return render();
      case "importar": E.agregar = null; E.importar = { paso: "elegir", ia: !!E.config.ia, compartir: false }; return render();
      case "bv-importar": E.bv = null; E.bvCerrada = true; host.enviar("config", { bienvenida: true }); E.importar = { paso: "elegir", ia: !!E.config.ia, compartir: false }; return render();
      case "elegir-cartola": return host.enviar("elegirCartola");
      case "cerrar-conectar": if (!E.conectar?.enviando) E.conectar = null; return render();
      case "enviar-conectar": {
        const k = E.conectar, c = E.conectores.find((x) => x.id === k.id);
        const faltan = c.campos.filter((f) => !String(k.campos[f.id] || "").trim());
        if (faltan.length) { k.error = T("Completa: {x}", { x: faltan.map((f) => tr(f.etiqueta)).join(", ") }); return render(); }
        k.enviando = true; k.error = "";
        host.enviar("conectar", { conector: k.id, campos: Object.fromEntries(c.campos.map((f) => [f.id, String(k.campos[f.id]).trim()])) });
        return render();
      }
      case "cerrar-importar": if (!ocupadoImportando()) E.importar = null; return render();
      case "aprender-receta": im.paso = "aprendiendo"; im.error = ""; host.enviar("aprenderReceta", { ruta: im.ruta, pais: E.config.pais || "CL" }); return render();
      case "receta-mal": im.paso = "sin_receta"; im.receta = null; im.error = tr("Entendido: no guardé nada. Puedes intentarlo otra vez o pedir ayuda en la comunidad."); return render();
      case "importar-guardar":
        if (im.receta) { host.enviar("guardarReceta", { receta: im.receta }); if (im.compartir) compartirReceta(im.receta); }
        im.paso = "guardando"; im.progreso = null;
        host.enviar("importar", { ruta: im.ruta, receta: im.receta?.id || im.vista.receta.id, ia: !!im.ia });
        return render();
      case "ver-movimientos": E.importar = null; E.vista = "movimientos"; E.filtro = { texto: "", categoria: "" }; return render();
      case "ver-sin-categoria": E.vista = "movimientos"; E.filtro = { texto: "", categoria: "__sin" }; return render();
      case "limpiar-filtro": E.filtro = { texto: "", categoria: "" }; return render();
      case "aprender-si": { const r = { contiene: E.aprender.contiene, categoria: E.aprender.categoria }; host.enviar("regla", r); E.reglas.push(r); aplicarRegla(r); toast("Aprendido"); E.aprender = null; return render(); }
      case "ordenar-saltar": E.ordenar.i++; E.ordenar.buscar = ""; E.ordenar.nueva = null; render(); return $(".vista-ordenar")?.focus();
      case "ordenar-atras": E.ordenar.i = Math.max(0, E.ordenar.i - 1); E.ordenar.buscar = ""; E.ordenar.nueva = null; render(); return $(".vista-ordenar")?.focus();
      case "ordenar-inicio": E.ordenar = { i: 0, buscar: "", nueva: null }; render(); return $(".vista-ordenar")?.focus();
      case "aprender-no": E.aprender = null; return render();
      case "sugerir": {
        const s = presupuestoSugerido(E.movimientos, mesesCompletos(), E.categorias, E.presupuesto.moneda, per());
        E.presEdit = { ...E.presEdit, ...s };
        render(); return toast("Listo: revisa los montos y guarda");
      }
      case "guardar-pres": {
        const mensual = limpiarPres(E.presEdit);
        E.presupuesto = { ...E.presupuesto, mensual }; E.presEdit = { ...mensual };
        host.enviar("presupuesto", { mensual }); render(); return toast("Presupuesto guardado");
      }
      case "pedir-consejos": E.pidiendoConsejos = true; E.errorConsejos = ""; host.enviar("pedirConsejos", { hoy: E.hoy }); return render();
      case "abrir-carpeta": return host.enviar("abrirCarpeta", {});
      case "actualizar": E.act = { paso: "1", texto: tr("Descargando la versión nueva…") }; E.ajustes = false; host.enviar("actualizar"); return render();
      case "act-cerrar": E.act = null; return render();
      case "act-despues": E.actOculto = true; return render();
      case "buscar-act": E.buscando = "buscando"; host.enviar("buscarActualizacion"); return render();
      case "comp-nuevo": E.agregar = null; E.compEdit = { c: borradorDe(), origen: "manual", error: "" }; render(); return enfocarEditor();
      case "comp-guardar": return guardarCompromiso(false);
      case "comp-despues": return guardarCompromiso(true);
      case "comp-cancelar":
        if (E.importar && E.importar.paso === "compromiso") E.importar.paso = "listo";
        E.compEdit = null; return render();
      case "comp-borrar": {
        const id = E.compEdit?.c?.id;
        E.compromisos.compromisos = listaCompromisos().filter((x) => x.id !== id);
        host.enviar("compromiso", { accion: "borrar", id }); E.compEdit = null; toast("Compromiso borrado"); return render();
      }
      case "sug-todas": E.sugTodas = !E.sugTodas; return render();
      case "agrupar-mov": E.agruparMov = !E.agruparMov; E.grupoMov = null; render(); return $('[data-accion="agrupar-mov"]')?.focus();
      case "ver-todas-cat": E.verTodasCat = !E.verTodasCat; return render();
      case "usar-maximos": {
        const g = gastoMaximo(E.movimientos, listaCompromisos(), E.mes, E.hoy, E.categorias, mesesCompletos(), monedaPrincipal(), per(), ufCfg());
        E.presEdit = { ...E.presEdit, ...Object.fromEntries(g.por_categoria.filter((x) => x.maximo > 0).map((x) => [x.categoria, x.maximo])) };
        render(); return toast("Listo: revisa los montos y guarda");
      }
      case "bv-despues": case "bv-fin": E.bv = null; E.bvCerrada = true; host.enviar("config", { bienvenida: true }); return render();
    }
  });
  document.addEventListener("input", (ev) => {
    const ds = ev.target.dataset || {};
    if (ds.filtro === "texto") { E.filtro.texto = ev.target.value; return render(); }
    if (ds.buscarCat) { estadoElegidor(ds.buscarCat).buscar = ev.target.value; return render(); }
    if (ds.nuevaNombre) { const k = estadoElegidor(ds.nuevaNombre); k.nueva = { ...k.nueva, nombre: ev.target.value, error: "" }; return render(); }
    if (ds.saldoInput) { E.saldoEdit = { cuenta: ds.saldoInput, texto: ev.target.value.replace(/[^\d\-]/g, "").replace(/(?!^)-/g, "") }; ev.target.value = E.saldoEdit.texto ? (E.saldoEdit.texto.startsWith("-") ? "-" : "") + numeroPlano(Math.abs(Number(E.saldoEdit.texto)) || 0) : ""; return; }
    if (ds.chatTexto != null) { E.chat.texto = ev.target.value; return; }
    if (ds.ce && E.compEdit && ev.target.tagName === "INPUT") {
      const numerico = ["monto", "cuotas_total", "cuotas_pagadas", "saldo", "aproxMin", "aproxMax", "prestamoTotal"].includes(ds.ce);
      E.compEdit.c[ds.ce] = conDecimales(ds.ce) || ds.ce === "aproxVariacion" || ds.ce === "prestamoInteres" ? numeroDecimal(ev.target.value)
        : numerico ? Number(ev.target.value.replace(/\D/g, "")) || 0 : ds.ce === "dia" ? Number(ev.target.value) || 0 : ev.target.value;
      // Mientras la persona no elige cómo se paga, «Netflix» o «PAC» en el nombre o las palabras lo cambian a «Se paga solo».
      if ((ds.ce === "nombre" || ds.ce === "buscarTexto") && !E.compEdit.c.pago) {
        const r = $(`[data-ce-pago][value="${pagoDelEditor(E.compEdit.c)}"]`);
        if (r) r.checked = true;
      }
      return;
    }
    if (ds.campo && E.conectar) { E.conectar.campos[ds.campo] = ev.target.value; return; }
    if (ds.pres) {
      const v = Number(ev.target.value.replace(/\D/g, "")) || 0;
      E.presEdit[ds.pres] = v;
      const total = Object.values(E.presEdit).filter((x) => x > 0).reduce((a, b) => a + b, 0);
      $("#total-pres").textContent = dinero(total);
      const guardar = $("[data-accion=guardar-pres]");
      if (guardar) guardar.disabled = JSON.stringify(limpiarPres(E.presEdit)) === JSON.stringify(limpiarPres(E.presupuesto.mensual || {}));
    }
  });
  document.addEventListener("change", async (ev) => {
    const ds = ev.target.dataset || {};
    if (ds.pres) { ev.target.value = numeroPlano(E.presEdit[ds.pres]); return; }
    if (ds.ce && E.compEdit) {
      const c = E.compEdit.c;
      // En un préstamo, el cálculo en vivo se vuelve a pintar al salir de cada campo.
      const repintar = () => { if (c.moneda === UF || c.tipo === "prestamo") { const id = document.activeElement?.id; render(); if (id) document.getElementById(id)?.focus(); } };
      if (conDecimales(ds.ce) || ds.ce === "aproxVariacion" || ds.ce === "prestamoInteres") { ev.target.value = formatoDecimal(c[ds.ce]); return repintar(); }
      if (["monto", "cuotas_total", "cuotas_pagadas", "saldo", "aproxMin", "aproxMax", "prestamoTotal"].includes(ds.ce)) { ev.target.value = numeroPlano(c[ds.ce]); return repintar(); }
      if (ds.ce === "con") return repintar();
      if (ev.target.tagName !== "SELECT") return;
      c[ds.ce] = ds.ce === "dia" ? Number(ev.target.value) : ev.target.value;
      if (ds.ce === "frecuencia") c.dia = ev.target.value === "semanal" ? Math.min(7, c.dia || 1) : c.dia || 1;
      if (ds.ce === "tipo" && ev.target.value === "ingreso" && !c.categoria) c.categoria = "sueldo";
      if (ds.ce === "moneda" && c.moneda === UF && c.monto >= 1000) { c.montoPesos = c.montoPesos || c.monto; c.monto = 0; }
      if (ds.ce === "tipo" && ev.target.value === "prestamo") {
        // La primera cuota de un préstamo nuevo: el día del sueldo (si «Tu mes» parte con el sueldo) o el 25.
        const im = E.config.inicio_mes;
        if (!listaCompromisos().some((x) => x.id === c.id)) c.dia = im && im.modo === "sueldo" && im.dia ? im.dia : 25;
        c.frecuencia = "mensual";
      }
      if (["tipo", "frecuencia", "moneda", "aproxModo", "signo"].includes(ds.ce)) { render(); $(`#ce-${ds.ce}`)?.focus(); }
      return;
    }
    if (ds.ceActivo != null && E.compEdit) { E.compEdit.c.activo = ev.target.checked; return; }
    if (ds.cePago != null && E.compEdit) { E.compEdit.c.pago = ev.target.value; return; }
    if (ds.ceAprox != null && E.compEdit) { E.compEdit.c.aproxActivo = ev.target.checked; render(); return $("[data-ce-aprox]")?.focus(); }
    if (ds.ceUf != null && E.compEdit) {
      const c = E.compEdit.c;
      if (ev.target.checked) { c.montoPesos = c.montoPesos || c.monto; c.moneda = UF; c.monto = 0; }
      else { c.moneda = monedaPrincipal(); c.monto = c.montoPesos || c.monto; }
      render(); return $(ev.target.checked ? "#ce-monto" : "[data-ce-uf]")?.focus();
    }
    if (ds.uf) {
      const u = { ...(ufCfg() || {}) }, n = numeroDecimal(ev.target.value);
      if (ds.uf === "valor") { if (n > 0) { u.valor = n; u.fecha = E.hoy; } else { delete u.valor; delete u.fecha; } }
      else if (n >= 0 && n <= 20) u.variacion_mensual = n;
      E.config.uf = u; host.enviar("config", { uf: u });
      if (ds.uf === "valor" && n > 0) toast("Listo: uso ese valor de la UF para estimar en pesos");
      return render();
    }
    if (ds.avisos != null) {
      E.config.avisos = ev.target.checked; host.enviar("avisos", { activo: ev.target.checked });
      toast(ev.target.checked ? "Listo: te aviso antes de que venzan" : "Ya no te aviso de tus compromisos"); return render();
    }
    if (ds.inicio) {
      const actual = E.config.inicio_mes || { modo: "dia", dia: 1 };
      const sueldo = listaCompromisos().find((c) => c.tipo === "ingreso" && c.categoria === "sueldo" && c.frecuencia === "mensual");
      const nuevo = ds.inicio === "modo" ? { modo: ev.target.value, dia: ev.target.value === "sueldo" ? (actual.dia > 1 ? actual.dia : sueldo?.dia || 25) : 1 }
        : { modo: "sueldo", dia: Math.max(1, Math.min(31, Math.round(Number(ev.target.value)) || 25)) };
      E.config.inicio_mes = nuevo; host.enviar("config", { inicio_mes: nuevo });
      E._per = undefined; E.mes = E._mesHoy = periodoHoy(); E.presEdit = null; return render();
    }
    if (ds.filtro === "categoria") { E.filtro.categoria = ev.target.value; return render(); }
    if (ds.importarIa != null) { E.importar.ia = ev.target.checked; return; }
    if (ds.vigilar != null) { E.vigilar.activo = ev.target.checked; host.enviar("vigilar", { activo: ev.target.checked });
      toast(ev.target.checked ? "Listo: las cartolas que descargues desde ahora se agregan solas" : "Ya no reviso tu carpeta de Descargas"); return render(); }
    if (ds.compartir != null) { E.importar.compartir = ev.target.checked; return; }
    const clave = ds.config;
    if (!clave) return;
    E.config[clave] = ev.target.value;
    const cambios = { [clave]: ev.target.value };
    if (clave === "pais") { const p = PAISES.find(([id]) => id === ev.target.value); if (p) { E.config.moneda = p[2]; cambios.moneda = p[2]; } }
    if (cambios.moneda && !Object.keys(E.presupuesto.mensual || {}).length) E.presupuesto.moneda = cambios.moneda;
    host.enviar("config", cambios);
    if (clave === "idioma_ui") await cargarIdioma();
    render();
  });
  document.addEventListener("keydown", (ev) => {
    const t = ev.target, ds = t?.dataset || {};
    // En el chat, Enter manda y Mayúscula + Enter hace un salto de línea.
    if (ev.key === "Enter" && ds.chatTexto != null && !ev.shiftKey && !ev.isComposing) { ev.preventDefault(); return enviarChat(); }
    if (ev.key === "Enter" && (ds.buscarCat || ds.nuevaNombre)) {
      ev.preventDefault();
      const lugar = ds.buscarCat || ds.nuevaNombre, k = estadoElegidor(lugar), m = movDe(lugar);
      if (ds.nuevaNombre || !m) return crearCategoria(lugar);
      const primera = opcionesPara(m, k.buscar)[0];
      if (primera) return elegirCategoria(m, primera.id, lugar);
      if (String(k.buscar || "").trim()) { k.nueva = { nombre: k.buscar.trim(), emoji: "", error: "" }; return crearCategoria(lugar); }
      return;
    }
    // «Por ordenar» con el teclado: 1–9 elige, → salta, ← vuelve, / busca (fuera de los campos de texto).
    if (E.vista === "ordenar" && !E.picker && !E.importar && !E.conectar && !E.ajustes && !E.agregar && !E.compEdit && E.bv === null && !E.ordenar.nueva && !t.matches?.("input, textarea, select") && !ev.metaKey && !ev.ctrlKey && !ev.altKey) {
      const m = colaOrdenar()[E.ordenar.i];
      if (m && /^[1-9]$/.test(ev.key)) { const c = opcionesPara(m, E.ordenar.buscar)[Number(ev.key) - 1]; if (c) { ev.preventDefault(); return elegirCategoria(m, c.id, "ordenar"); } }
      if (ev.key === "ArrowRight") { ev.preventDefault(); E.ordenar.i++; render(); return $(".vista-ordenar")?.focus(); }
      if (ev.key === "ArrowLeft") { ev.preventDefault(); E.ordenar.i = Math.max(0, E.ordenar.i - 1); render(); return $(".vista-ordenar")?.focus(); }
      if (ev.key === "/") { ev.preventDefault(); return $("#ordenar-buscar")?.focus(); }
    }
    if (ev.key !== "Escape") return;
    if (E.picker) { const id = E.picker.id; if (E.picker.nueva) { E.picker.nueva = null; render(); return $("#picker-buscar")?.focus(); } E.picker = null; render(); return document.getElementById("chip-" + id)?.focus(); }
    if (E.vista === "ordenar" && E.ordenar.nueva) { E.ordenar.nueva = null; render(); return $("#ordenar-buscar")?.focus(); }
    if (E.importar && !ocupadoImportando()) { E.importar = null; return render(); }
    if (E.conectar && !E.conectar.enviando) { E.conectar = null; return render(); }
    if (E.ajustes) { E.ajustes = false; return render(); }
    if (E.compEdit) { E.compEdit = null; return render(); }
    if (E.agregar) { E.agregar = null; render(); return $(".nav-agregar")?.focus(); }
    if (E.aprender) { E.aprender = null; return render(); }
  });
  document.addEventListener("submit", (ev) => {
    if (ev.target.dataset?.chatForm != null) { ev.preventDefault(); return enviarChat(); }
    const cuenta = ev.target.dataset?.saldoForm;
    if (cuenta == null) return;
    ev.preventDefault();
    guardarSaldo(cuenta);
  });
  document.addEventListener("toggle", (ev) => { if (ev.target.dataset?.plegable === "comparar") E.compararAbierto = ev.target.open; }, true);
  /** Lo que la persona dice que tiene hoy en una cuenta: pasa a ser la base. Si no cuadra con lo que yo calculaba, lo digo en simple. */
  function guardarSaldo(cuenta) {
    const texto = (E.saldoEdit?.cuenta === cuenta ? E.saldoEdit.texto : $(`#saldo-${CSS.escape(cuenta)}`)?.value || "").replace(/[^\d\-]/g, "");
    if (!/^-?\d+$/.test(texto)) { toast("Escribe cuánto tienes, solo el número"); return $(`#saldo-${CSS.escape(cuenta)}`)?.focus(); }
    const monto = Number(texto), moneda = monedaPrincipal();
    const antes = loQueTienes(E.cuentas, E.movimientos, moneda).cuentas.find((c) => c.id === cuenta);
    let c = E.cuentas.find((x) => x.id === cuenta);
    if (!c) { c = { id: cuenta, nombre: antes?.nombre || cuenta, receta: "", moneda: "" }; E.cuentas = [...E.cuentas, c]; }
    c.saldo = { monto, fecha: E.hoy, origen: "persona" };
    host.enviar("saldo", { cuenta, monto, fecha: E.hoy });
    E.saldoEdit = null;
    const dif = antes && antes.saldo != null ? monto - antes.saldo : null;
    E.saldoAviso = dif == null ? { cuadra: true, texto: T("Listo: desde hoy sigo tus movimientos en {c}.", { c: esc(c.nombre) }) }
      : Math.abs(dif) < 1 ? { cuadra: true, texto: T("✓ Cuadra con lo que yo calculaba para {c}.", { c: esc(c.nombre) }) }
        : { cuadra: false, texto: T(dif > 0 ? "Había una diferencia de {x} (tienes más de lo que yo calculaba): puede ser plata que entró y no veo, como una devolución o un traspaso. Desde ahora parto de lo que me dijiste." : "Había una diferencia de {x} (tienes menos de lo que yo calculaba): puede ser plata en Reservas o movimientos que no veo. Desde ahora parto de lo que me dijiste.", { x: esc(dinero(Math.abs(dif))) }) };
    render();
  }
  /** Guarda el idioma por el mismo camino que Ajustes y sigue con la bienvenida, ya en ese idioma. */
  async function elegirIdioma(codigo) {
    if (codigo !== "es" && codigo !== "en") return;
    E.config.idioma_ui = codigo;
    host.enviar("config", { idioma_ui: codigo });
    await cargarIdioma();
    E.bv = 1;
    render();
    $("#t-bv")?.focus();
  }
  function enfocarEditor() { const el = $("#editor-comp"); if (el) { el.scrollIntoView?.({ block: "start" }); $("#ce-nombre")?.focus(); } }
  /** Manda lo que escribió la persona (con los últimos mensajes, para que la IA tenga el hilo). La respuesta llega a chatRespuesta. */
  function enviarChat() {
    const k = E.chat, texto = String(k.texto || "").trim().slice(0, 500);
    if (k.pensando || texto.length < 2) return $("#chat-texto")?.focus();
    k.mensajes = [...k.mensajes, { id: "local-" + Date.now(), rol: "persona", texto, fecha: E.hoy, local: true }];
    Object.assign(k, { texto: "", pensando: true, bajar: true, confirmarBorrar: false });
    host.enviar("chat", { accion: "enviar", hoy: E.hoy, mensajes: k.mensajes.filter((m) => !m.error).slice(-10).map((m) => ({ rol: m.rol, texto: m.texto })) });
    render();
  }
  /** Se recuerda lo que la persona hizo con cada acción (en .alcancia/chat.json), para no volver a ofrecerla. */
  function marcarAccionChat(ref, estado, sinPintar = false) {
    const m = E.chat.mensajes.find((x) => x.id === ref.id);
    if (!m) return;
    m.estados = { ...(m.estados || {}), [claveEstado(ref.i, ref.j, estado)]: estado };
    if (!String(m.id).startsWith("local")) host.enviar("chat", { accion: "marcar", id: m.id, i: ref.i, ...(ref.j == null ? {} : { j: ref.j }), estado });
    if (!sinPintar) render();
  }
  /** «Es el mismo» → «Actualizar»: el préstamo que ya estaba toma el plan nuevo (guardar.py, accion actualizar_prestamo). */
  function actualizarPrestamoChat(c) {
    const lista = listaCompromisos(), k = lista.findIndex((x) => x.id === c.id);
    if (k < 0) return toast("No encontré ese pago entre los tuyos."), false;
    lista[k] = { ...c, pagos: lista[k].pagos || {} };
    host.enviar("compromiso", { accion: "actualizar_prestamo", id: c.id, hoy: E.hoy, compromiso: { ...c } });
    return true;
  }
  function agregarCompromisoChat(c) {
    const lista = listaCompromisos();
    if (lista.some((x) => x.id === c.id)) return;
    E.compromisos.compromisos = [...lista, { ...c, pagos: {} }];
    host.enviar("compromiso", { accion: "guardar", hoy: E.hoy, compromiso: { ...c } });
  }
  /** «Agregar», «Sí, corrígelo», «Cambiar» (abre el editor con la propuesta) o «No». Se pinta al tiro y se guarda por el puente de siempre. */
  function accionChat(d) {
    const m = E.chat.mensajes.find((x) => x.id === d.msg), i = Number(d.i), j = d.j != null && d.j !== "" ? Number(d.j) : null;
    const a = m && (m.acciones || [])[i];
    if (!a) return;
    const ref = { id: m.id, i, j };
    if (d.chat === "no") return marcarAccionChat(ref, "no");
    if (d.chat === "mismo" || d.chat === "otro") return marcarAccionChat(ref, d.chat);  // «¿Es el mismo?»: la tarjeta cambia, nada se guarda aún
    const elegido = a.tipo === "plan_prestamos" ? planElegido(m, a, i) : null;
    if (d.chat === "todos") {
      elegido.propuestas.forEach((c, jj) => {
        if (estadoAccion(m, i, jj)) return;
        if (elegido.mismos.includes(jj) ? actualizarPrestamoChat(c) : (agregarCompromisoChat(c), true)) marcarAccionChat({ id: m.id, i, j: jj }, "hecha", true);
      });
      toast("Listo: te aviso antes de cada cuota"); return render();
    }
    const actualiza = elegido ? elegido.mismos.includes(j) : a.tipo === "crear_compromiso" && !!a.actualizar && esMismo(m, i) === "mismo";
    const c = elegido ? elegido.propuestas[j] : actualiza ? a.actualizar : a.compromiso;
    if (!c && (elegido || a.tipo === "crear_compromiso")) return;
    if (d.chat === "cambiar") {
      E.compEdit = { c: borradorDe(c), origen: "ia", error: a.incompleto && !actualiza ? a.error || tr("Me faltó algo: complétalo y lo guardo.") : "", chat: ref, actualizar: actualiza };
      render(); return enfocarEditor();
    }
    if (actualiza) { if (!actualizarPrestamoChat(c)) return; toast("Listo: actualicé tu préstamo"); }
    else if (a.tipo === "crear_compromiso" || a.tipo === "plan_prestamos") { agregarCompromisoChat(c); toast(c.tipo === "prestamo" ? "Listo: te aviso antes de cada cuota" : "Listo: lo voy a reconocer en tu cartola y te recuerdo si falta"); }
    else if (a.tipo === "reasignar_pago") {
      const comp = listaCompromisos().find((x) => x.id === a.id), mov = a.pago.movimiento ? E.movimientos.find((x) => x.id === a.pago.movimiento) : null;
      const problema = comp ? reasignarPago(comp, a.de.periodo, a.a.periodo, mov || null) : tr("No encontré ese pago entre los tuyos.");
      if (problema) { toast(problema); return; }
      host.enviar("compromiso", { accion: "reasignar", id: a.id, de: a.de.periodo, a: a.a.periodo, movimiento: a.pago.movimiento || "", hoy: E.hoy });
      toast("Corregido: ese pago quedó en el mes pasado");
    } else if (a.tipo === "marcar_pagado") marcarCompromiso({ compPagado: `${a.id}|${a.periodo}` });
    else if (a.tipo === "marcar_pendiente") marcarCompromiso(a.pago.como === "automatico" && a.pago.movimiento ? { compNoes: `${a.id}|${a.periodo}|${a.pago.movimiento}` } : { compDesmarcar: `${a.id}|${a.periodo}` });
    else if (a.tipo === "editar_compromiso") {
      const lista = listaCompromisos(), k = lista.findIndex((x) => x.id === a.id);
      if (k < 0) return;
      lista[k] = { ...a.compromiso, pagos: lista[k].pagos || {}, desde: lista[k].desde };
      host.enviar("compromiso", { accion: "guardar", hoy: E.hoy, compromiso: { ...a.compromiso } });
      toast("Compromiso guardado");
    }
    marcarAccionChat(ref, "hecha");
  }
  /** La conversación guardada (estado.py) manda, pero lo que la persona acaba de confirmar en esta pantalla no se pierde. */
  function mezclarChat(guardados, actuales) {
    const porId = new Map(actuales.map((m) => [m.id, m]));
    return guardados.map((m) => (porId.get(m.id)?.estados ? { ...m, estados: { ...(m.estados || {}), ...porId.get(m.id).estados } } : m));
  }
  /** «Ya lo pagué», «Desmarcar» y «No es este»: se pinta al tiro y se guarda en compromisos.json por guardar.py. */
  function marcarCompromiso(d) {
    const [id, periodo, mov] = (d.compPagado || d.compDesmarcar || d.compNoes).split("|");
    const c = listaCompromisos().find((x) => x.id === id);
    if (!c) return;
    c.pagos = { ...(c.pagos || {}) };
    const p = { ...(c.pagos[periodo] || {}) };
    const quitar = () => { delete p.como; delete p.fecha; delete p.movimiento; delete p.monto; };
    if (d.compPagado) { quitar(); Object.assign(p, { como: "manual", fecha: E.hoy }); host.enviar("compromiso", { accion: "pagado", id, periodo, hoy: E.hoy }); toast("Marcado como pagado"); }
    else if (d.compDesmarcar) { quitar(); host.enviar("compromiso", { accion: "desmarcar", id, periodo }); }
    else { if (p.movimiento === mov) quitar(); p.no_es = [...new Set([...(p.no_es || []), mov])]; host.enviar("compromiso", { accion: "no_es", id, periodo, movimiento: mov }); toast("Entendido: ese movimiento no es"); }
    if (Object.keys(p).length) c.pagos[periodo] = p; else delete c.pagos[periodo];
    render();
  }
  /** «¿Cuándo te pagan? Así tu mes empieza ese día.» (Ajustes y bienvenida). */
  function campoInicioMes() {
    const im = E.config.inicio_mes || { modo: "dia", dia: 1 }, sueldo = im.modo === "sueldo";
    return `<p class="texto-suave intro-campo">¿Cuándo te pagan? Así tu mes empieza ese día.</p>
      <div class="dos"><label class="campo"><span>Tu mes empieza</span><select data-inicio="modo" id="inicio-modo">
        <option value="dia" ${sueldo ? "" : "selected"}>El día 1</option><option value="sueldo" ${sueldo ? "selected" : ""}>Cuando llega tu sueldo</option></select></label>
        ${sueldo ? `<label class="campo"><span>¿Qué día te pagan, más o menos?</span><input class="texto" id="inicio-dia" type="number" min="1" max="31" data-inicio="dia" value="${esc(im.dia)}"></label>` : ""}</div>
      ${sueldo && im.auto ? `<p class="nota-mcp">${frase("Lo detecté de tus movimientos: tu sueldo suele llegar el día {d}. Si lo cambias, uso lo que elijas.", { d: im.dia })}</p>` : ""}
      ${sueldo ? `<p class="nota-mcp">Si anotas tu sueldo en Pagos, tu mes parte el día que de verdad llega: si te pagan antes, parte ese día. Los bonos cuentan como ingresos del mes en que caen.</p>` : ""}`;
  }
  function aplicarRegla(r) {
    for (const m of E.movimientos) if (normalizar(m.descripcion).includes(r.contiene)) m.categoria = r.categoria;
  }
  /** Abre GitHub con la propuesta de receta lista para enviar (con la cuenta de la persona). Solo la receta, nunca movimientos. */
  function compartirReceta(receta) {
    const r = { ...receta }; delete r.autor;
    const cuerpo = `Receta para **${r.institucion}** (${r.pais}), creada con Alcancía.\n\n\`\`\`json\n${JSON.stringify(r, null, 2)}\n\`\`\`\n`;
    const url = `${ENLACES.nuevaReceta}?labels=receta&title=${encodeURIComponent(`Receta: ${r.nombre}`)}&body=${encodeURIComponent(cuerpo)}`;
    host.enviar("abrirEnlace", { url });
  }

  /** Si la persona nunca eligió cuándo empieza su mes y el sueldo se ve claro, el mes va de sueldo a sueldo. La app ya lo guardó
   *  (compromisos.aplicar_sueldo, al armar el estado); aquí es lo mismo en memoria para el navegador y por si llega sin aplicar. */
  function sueldoSolo() {
    if (E.config.inicio_mes !== undefined || !E.movimientos.length) return;
    const moneda = E.presupuesto.moneda || E.config.moneda || "CLP", d = detectarSueldo(E.movimientos, E.hoy, E.categorias, moneda);
    if (!d) return;
    E.config.inicio_mes = { modo: "sueldo", dia: d.dia, auto: true };
    const lista = E.compromisos.compromisos || (E.compromisos.compromisos = []);
    if (!lista.some((c) => c.activo !== false && c.tipo === "ingreso" && c.frecuencia === "mensual" && c.categoria === "sueldo") && E.categorias.some((c) => c.id === "sueldo"))
      lista.push({ id: "c-sueldodetectado", nombre: "Sueldo", tipo: "ingreso", signo: "ingreso", monto: d.monto, moneda, frecuencia: "mensual", dia: d.dia,
        categoria: "sueldo", buscar: d.clave ? [d.clave] : [], aproximado: { variacion: d.variacion }, tolerancia: TOLERANCIA, origen: "detectado",
        desde: d.llegadas[0] < E.hoy ? d.llegadas[0] : E.hoy, activo: true, pagos: {} });
    const llegadas = new Set(d.llegadas);
    for (const m of E.movimientos) if (llegadas.has(m.fecha) && m.monto > 0 && Math.abs(m.monto - d.monto) <= d.monto * 0.5 && !m.categoria) m.categoria = "sueldo";
  }

  // ───────────── Lo que manda la app ─────────────
  window.Alcancia = {
    async estado(e) {
      Object.assign(E, { hoy: e.hoy, config: e.config || {}, ias: e.ias || [], movimientos: e.movimientos || [], categorias: e.categorias || [],
        presupuesto: e.presupuesto || { mensual: {} }, reglas: e.reglas || [], consejos: (e.consejos || []).slice().sort((a, b) => b.fecha.localeCompare(a.fecha)),
        cuentas: e.cuentas || [], version: e.version || "", carpeta: e.carpeta || "", actualizacion: e.actualizacion || { hay: false },
        conectores: e.conectores || [], conexiones: e.conexiones || {}, vigilar: e.vigilar || { activo: false, recientes: [] }, iaExterna: e.ia_externa || [],
        compromisos: e.compromisos || { compromisos: [], descartados: [] }, sugerencias: e.sugerencias || [], feriados: e.feriados || [], palabrasMora: e.palabras_mora || [], palabrasAuto: e.palabras_automatico || [] });
      if (!E.chat.pensando) E.chat.mensajes = mezclarChat(Array.isArray(e.chat) ? e.chat : [], E.chat.mensajes);
      if (!E.presupuesto.moneda) E.presupuesto.moneda = E.config.moneda || "CLP";
      sueldoSolo();
      E._per = undefined;
      // Si estaba mirando el mes en curso, sigue en el mes en curso (aunque haya cambiado el día o el periodo).
      const antes = E._mesHoy;
      E._mesHoy = periodoHoy();
      if (!E.mes || E.mes > E._mesHoy || E.mes === antes) E.mes = E._mesHoy;
      // Primer uso: la bienvenida parte por el idioma (si ya lo eligió y cerró la app a medio camino, sigue desde el saludo).
      if (!E.config.bienvenida && E.bv === null && !E.bvCerrada) E.bv = E.config.idioma_ui ? 1 : 0;
      await cargarIdioma();
      if (e.aviso) toast(e.aviso);
      render();
    },
    /** La respuesta de Alcancía (bin/chat.py). Si la IA falló, igual llega un mensaje honesto: nunca queda sin respuesta. */
    chatRespuesta(r) {
      const k = E.chat, i = k.mensajes.map((m) => !!m.local).lastIndexOf(true);
      k.pensando = false; k.bajar = true;
      if (i >= 0) k.mensajes[i] = r.persona || { ...k.mensajes[i], local: false };
      k.mensajes = [...k.mensajes, r.mensaje || { id: "local-e" + Date.now(), rol: "alcancia", texto: r.error || tr("No pude responder. Inténtalo de nuevo."), error: true, sin_ia: !!r.sin_ia }];
      render();
      if (E.agregar === "contar") $("#chat-texto")?.focus();
    },
    iaProbada(r) { delete E.probando[r.id]; E.resultadoIA[r.id] = r; if (r.ok) { E.config.ia = r.id; toast("Lista para usar"); } render(); },
    cartolaElegida(r) {
      if (!E.importar || !r?.ruta) return;
      Object.assign(E.importar, { paso: "leyendo", ruta: r.ruta, nombre: r.nombre, receta: null, error: "" });
      host.enviar("vistaCartola", { ruta: r.ruta }); render();
    },
    vistaLista(r) {
      if (!E.importar) return;
      if (r.ok) Object.assign(E.importar, { paso: "vista", vista: r });
      else if (r.sin_receta) Object.assign(E.importar, { paso: "sin_receta" });
      else Object.assign(E.importar, { paso: "error", error: r.error });
      render();
    },
    recetaAprendida(r) {
      if (!E.importar) return;
      if (r.ok) Object.assign(E.importar, { paso: "receta", receta: r.receta, vista: { ...r, receta: r.receta } });
      else Object.assign(E.importar, { paso: "sin_receta", error: r.error });
      render();
    },
    importarProgreso(p) { if (E.importar?.paso === "guardando") { E.importar.progreso = p; render(); } },
    importado(r) {
      if (!E.importar) return;
      Object.assign(E.importar, r.ok ? { paso: "listo", resultado: r } : { paso: "error", error: r.error });
      render();
    },
    consejosListos(r) {
      E.pidiendoConsejos = false;
      if (r.ok) { E.consejos = [{ fecha: r.fecha, texto: r.texto }, ...E.consejos.filter((c) => c.fecha !== r.fecha)]; E.consejoSel = r.fecha; }
      else E.errorConsejos = r.error || tr("No se pudieron crear los consejos.");
      render();
    },
    actualizacionRevisada(r) { E.buscando = r.hay ? null : r.sinConexion ? "sinConexion" : "alDia"; if (r.hay) { E.actualizacion = r; E.actOculto = false; } render(); },
    actualizacionProgreso(d) { E.act = d; render(); },
    conectado(r) {
      if (!E.conectar || E.conectar.id !== r.conector) return;
      if (r.ok) {
        const c = E.conectores.find((x) => x.id === r.conector);
        E.conectar = null; E.conexiones[r.conector] = { conectado: true }; E.sincronizando[r.conector] = true;
        toast(T("{s} conectado. Trayendo tus movimientos…", { s: c ? c.nombre : "" }));
      } else Object.assign(E.conectar, { enviando: false, error: r.error || tr("No se pudo conectar.") });
      render();
    },
    sincronizado(r) {
      delete E.sincronizando[r.conector];
      if (r.ok && (r.detectados || []).length) toast(T(r.detectados.length === 1 ? "Encontré 1 pago que parece un compromiso: revísalo en Pagos" : "Encontré {n} pagos que parecen compromisos: revísalos en Pagos", { n: r.detectados.length }));
      if (r.ok && r.nuevos) toast(T(r.nuevos === 1 ? "1 movimiento nuevo de {s}" : "{n} movimientos nuevos de {s}", { n: r.nuevos, s: r.nombre || "" }));
      else if (r.ok && !r.esperando && r.manual) toast("Todo al día");
      render();
    },
    mcpListo(r) {
      delete E.mcpOcupado[r.cliente];
      if (r.clientes) E.iaExterna = r.clientes;
      if (!r.ok) E.mcpError[r.cliente] = r.error || tr("No se pudo conectar.");
      else if (!r.quitar) toast(r.nota ? tr(r.nota) : tr("Listo: tu IA ya puede consultar Alcancía"));
      render();
    },
    importadoSolo(r) {
      for (const x of r.importados || []) toast(T(x.nuevos === 1 ? "Agregué tu cartola de {b}: 1 movimiento nuevo" : "Agregué tu cartola de {b}: {n} movimientos nuevos", { b: x.institucion, n: x.nuevos }));
      if ((r.sin_receta || []).length) toast(T("Descargaste «{x}», pero todavía no sé leerla. Agrégala a mano y tu IA aprende.", { x: r.sin_receta[0] }));
    },
    _probar(f) { f(E); render(); },
    _pruebas: { calcularPrestamo, resumen, historia, redondearArriba, presupuestoSugerido, reglaPara, estadoCompromisos, gastoMaximo, rango, periodoDe, periodoConfig, detectarSueldo, reglaHabil, proximoSueldo, correrHabil, moraDelAnio, loQueTienes, loQueDebes, cargos, modoPago,
      margenMensual, planPrestamos, inicioPlan, pagoReasignable, reasignarPago, clavesPersona, prestamosParecidos, planVariante, prestamoActualizado },
  };

  // ───────────── Vista previa en el navegador (datos ficticios de demo.json) ─────────────
  let DEMO = null;
  function simular(accion, d) {
    if (!DEMO) return;
    const A = window.Alcancia, enviar = () => A.estado(DEMO);
    const luego = (ms, f) => setTimeout(f, ms);
    switch (accion) {
      case "listo": return enviar();
      case "config": Object.assign(DEMO.config, d); return;
      case "probarIA": return luego(500, () => { DEMO.config.ia = d.id; A.iaProbada({ id: d.id, ok: true }); });
      case "elegirCartola": return luego(200, () => A.cartolaElegida({ ruta: "/demo/cartola-octubre.csv", nombre: "cartola-octubre.csv" }));
      case "vistaCartola": return luego(600, () => {
        const muestra = DEMO.movimientos.filter((m) => m.cuenta === "banco-ejemplo").slice(-6).reverse();
        A.vistaLista({ ok: true, receta: { id: "cl-banco-ejemplo", nombre: "Banco Ejemplo — cuenta corriente", institucion: "Banco Ejemplo" },
          total: 41, desde: "2026-10-01", hasta: "2026-10-17", avisos: ["Fila ignorada: Total cargos · 1.234.560"], muestra });
      });
      case "aprenderReceta": return luego(1200, () => A.recetaAprendida({ ok: true, total: 41, receta: { id: "cl-billetera-ejemplo", nombre: "Billetera Ejemplo", institucion: "Billetera Ejemplo", pais: "CL" },
        muestra: DEMO.movimientos.filter((m) => m.cuenta === "billetera-ejemplo").slice(-6).reverse() }));
      case "guardarReceta": return;
      case "importar": {
        let n = 0; const total = d.ia ? 3 : 2, textos = ["Leyendo la cartola…", "Guardando sin duplicar…", "Tu IA está poniendo categorías…"];
        const iv = setInterval(() => {
          n++;
          if (n <= total) return A.importarProgreso({ paso: n, total, texto: textos[n - 1] });
          clearInterval(iv); A.importado({ ok: true, nuevos: 2, repetidos: 39, sin_categoria: 0, categorizados_ia: 0,
            detectados: (DEMO.sugerencias || []).filter((s) => s.motivo === "palabra") });
        }, 500);
        return;
      }
      case "categoria": { const m = DEMO.movimientos.find((x) => x.id === d.id); if (m) m.categoria = d.categoria; return; }
      case "regla": DEMO.reglas.push(d); return;
      case "categoriaNueva": { DEMO.categorias = [...DEMO.categorias, d.categoria]; const m = DEMO.movimientos.find((x) => x.id === d.id); if (m) m.categoria = d.categoria.id; return; }
      case "saldo": { const c = DEMO.cuentas.find((x) => x.id === d.cuenta); if (c) c.saldo = { monto: d.monto, fecha: d.fecha, origen: "persona" }; return; }
      case "presupuesto": DEMO.presupuesto.mensual = d.mensual; return;
      case "pedirConsejos": return luego(1300, () => A.consejosListos({ ok: true, fecha: d.hoy, texto: DEMO.consejos[0].texto }));
      case "abrirEnlace": return window.open(d.url, "_blank", "noopener");
      case "abrirCarpeta": return toast("En la app, aquí se abre tu carpeta");
      case "conectar": return luego(900, () => {
        A.conectado({ conector: d.conector, ok: true });
        luego(1200, () => { DEMO.conexiones[d.conector] = { conectado: true, ultima: new Date().toISOString(), nuevos: 3 }; E.conexiones = DEMO.conexiones;
          A.sincronizado({ conector: d.conector, ok: true, nuevos: 3, nombre: (DEMO.conectores.find((c) => c.id === d.conector) || {}).nombre }); });
      });
      case "sincronizar": return luego(900, () => { DEMO.conexiones[d.conector] = { ...DEMO.conexiones[d.conector], ultima: new Date().toISOString(), error: "" }; E.conexiones = DEMO.conexiones; A.sincronizado({ conector: d.conector, ok: true, nuevos: 0, manual: true }); });
      case "desconectar": delete DEMO.conexiones[d.conector]; return;
      case "vigilar": DEMO.vigilar.activo = d.activo; return;
      case "avisos": DEMO.config.avisos = d.activo; return;
      case "chat": {
        DEMO.chat = DEMO.chat || [];
        if (d.accion === "borrar") { DEMO.chat = []; return; }
        if (d.accion === "marcar") { const m = DEMO.chat.find((x) => x.id === d.id); if (m) m.estados = { ...(m.estados || {}), [claveEstado(d.i, d.j, d.estado)]: d.estado }; return; }
        return luego(1400, () => { const r = chatSimulado(d); if (r.ok) DEMO.chat.push(r.persona, r.mensaje); A.chatRespuesta(r); });
      }
      case "compromiso": {
        const lista = DEMO.compromisos.compromisos, c = lista.find((x) => x.id === d.id);
        if (d.accion === "guardar") { const i = lista.findIndex((x) => x.id === d.compromiso.id); const n = { pagos: {}, ...(i >= 0 ? lista[i] : {}), ...d.compromiso }; if (i >= 0) lista[i] = n; else lista.push(n); }
        else if (d.accion === "actualizar_prestamo") { const i = lista.findIndex((x) => x.id === d.id); if (i >= 0) lista[i] = { ...d.compromiso, pagos: lista[i].pagos || {} }; }
        else if (d.accion === "borrar") DEMO.compromisos.compromisos = lista.filter((x) => x.id !== d.id);
        else if (d.accion === "descartar") DEMO.compromisos.descartados.push(d.clave);
        else if (c) { const e = window.Alcancia && E.compromisos.compromisos.find((x) => x.id === d.id); if (e) c.pagos = JSON.parse(JSON.stringify(e.pagos || {})); }
        return;
      }
      case "mcpConectar": return luego(700, () => { const c = DEMO.ia_externa.find((x) => x.id === d.cliente); if (c) { c.conectado = !d.quitar; c.al_dia = !d.quitar; }
        A.mcpListo({ ok: true, cliente: d.cliente, quitar: d.quitar, nota: c && c.nota, clientes: DEMO.ia_externa }); });
      case "buscarActualizacion": return luego(500, () => A.actualizacionRevisada({ hay: false }));
      case "actualizar": { let n = 1; const iv = setInterval(() => { A.actualizacionProgreso({ paso: String(n), texto: ["", "Descargando la versión nueva…", "Preparando la versión nueva…", "Instalando: Alcancía se cerrará y volverá a abrirse sola"][n], pct: n * 33 }); if (++n > 3) clearInterval(iv); }, 700); return; }
    }
  }

  /** Un préstamo propuesto con su cuota, la última y cuándo termina (lo que compromisos.validar calcula en Python). */
  function prestamoCompleto(c) {
    const k = calcularPrestamo(c.prestamo.total, c.cuotas_total, c.prestamo.interes || 0, c.moneda, c.prestamo.cuota);
    const r = { ...c, monto: k.cuota, prestamo: { total: k.total, interes: k.interes, cuota: k.cuota, ultima: k.ultima } };
    const o = vencimientos({ ...r, fecha_fin: null }, "2299-12-31").filter((v) => v.n);
    return o.length ? { ...r, fecha_fin: o[o.length - 1].vence } : r;
  }
  const canonSimple = (o) => JSON.stringify(Object.keys(o || {}).sort().map((k) => [k, o[k]]));
  const estadoSimulado = () => estadoCompromisos(listaCompromisos(), E.movimientos, periodoDe(E.hoy, per()), E.hoy, monedaPrincipal(), per(), ufCfg(), E.palabrasMora || [], E.palabrasAuto || []);
  /** En la vista previa: responde como lo haría bin/chat.py con una IA, con la misma lógica (margen, plan, pago del mes pasado). */
  function chatSimulado(d) {
    const ms = d.mensajes || [], texto = String((ms[ms.length - 1] || {}).texto || ""), n = normalizar(texto), hoy = E.hoy, moneda = monedaPrincipal();
    const idChat = () => "m-" + nuevoIdComp().slice(2);
    const persona = { id: idChat(), rol: "persona", texto, fecha: hoy };
    const responder = (respuesta, acciones = [], notas = []) => ({ ok: true, persona, mensaje: { id: idChat(), rol: "alcancia", texto: respuesta, acciones, notas, estados: {}, fecha: hoy } });
    const lista = listaCompromisos(), activos = lista.filter((c) => c.activo !== false);
    // ¿De qué compromiso habla? Por su nombre o sus palabras, con sinónimos simples (hipoteca = dividendo).
    let nn = n;
    for (const [a, b] of [["HIPOTECA", "DIVIDENDO"], ["HIPOTECARIO", "DIVIDENDO"], ["ALQUILER", "ARRIENDO"], ["ELECTRICIDAD", "LUZ"]]) nn = nn.replace(new RegExp(`\\b${a}\\b`, "g"), b);
    const delQue = activos.find((c) => [c.nombre, ...(c.buscar || [])].some((p) => normalizar(p).split(/\s+/).some((w) => w.length > 3 && nn.includes(w))));
    if (/PREST/.test(n) && !/\bEN \d+ (MESES|CUOTAS)\b/.test(n)) {
      const deudas = [...texto.matchAll(/(?<!\p{L})(?:mi|el|la)\s+((?:t[ií][oa]\s+)?\p{L}+)\s+(?:me\s+prest[oó]\s+)?(\d+(?:[.,]\d+)?)\s*(m|millones?|palos?|lucas?|mil)\b/giu)]
        .map((x) => ({ con: x[1].split(/\s+/).map((w) => primeraMayuscula(w.toLowerCase())).join(" "), total: Number(x[2].replace(",", ".")) * (/^(m|millon|palo)/i.test(x[3]) ? 1e6 : 1e3), interes: 0 }));
      if (!deudas.length) return responder(tr("¿Quién te prestó y cuánto? Por ejemplo: «mi mamá me prestó 1,5 millones»."));
      // Igual que bin/chat.py: el plan de siempre y, si alguna deuda se parece a un préstamo anotado, cada combinación de «es el mismo».
      const dd = deudas.slice(0, 4), ini = inicioPlan(per(), hoy, E.feriados || []);
      const variante = (mismos) => {
        const plan = planVariante(dd, mismos, lista, E.movimientos, hoy, E.categorias, moneda, per(), ufCfg(), E.palabrasAuto || []);
        const propuestas = plan.deudas.map((x, j) => prestamoCompleto(mismos[j] ? prestamoActualizado(lista.find((c) => c.id === mismos[j]), x, ini)
          : { id: nuevoIdComp(), nombre: tr("Préstamo de {p}").replace("{p}", x.con), con: x.con, tipo: "prestamo", signo: "gasto", moneda, frecuencia: "mensual", dia: ini.dia,
            categoria: "", buscar: [], tolerancia: TOLERANCIA, cuotas_total: x.cuotas, cuotas_pagadas: 0, prestamo: { total: x.total, interes: x.interes, cuota: x.cuota },
            pago: "manual", activo: true, desde: ini.desde, origen: "ia" }));
        return { plan, propuestas };
      };
      const accion = { tipo: "plan_prestamos", ...variante({}) };
      const parecidos = prestamosParecidos(dd.map((x) => ({ con: x.con, signo: "gasto", moneda, total: x.total })), lista, estadoSimulado(), hoy);
      const con = parecidos.map((q, j) => (q ? j : null)).filter((j) => j != null);
      if (con.length) {
        accion.parecidos = parecidos; accion.variantes = {};
        for (let n = 1; n < 2 ** con.length; n++) {
          const js = con.filter((j, k) => (n >> k) & 1);
          accion.variantes[js.join(",")] = variante(Object.fromEntries(js.map((j) => [j, parecidos[j].id])));
        }
        return responder(tr("Veamos cuánto te cabe al mes. Ojo: ya tienes anotado «{n}». Dime si es el mismo y no lo cuento dos veces.").replace("{n}", parecidos[con[0]].nombre), [accion]);
      }
      return responder(tr("Veamos cuánto te cabe al mes sin salirte de tus gastos."), [accion]);
    }
    if (/\b(AUN NO|TODAVIA NO|NO HE PAGADO|NO LO HE PAGADO|MES PASADO)\b/.test(n)) {
      if (!delQue) return responder(tr("¿De cuál pago me hablas? No lo encontré entre los tuyos."));
      const r = pagoReasignable(lista, E.movimientos, delQue.id, hoy, moneda, per(), ufCfg(), E.palabrasMora || []);
      if (r) return responder(tr("Entonces ese pago era del mes pasado y el de este mes sigue pendiente. ¿Lo corrijo?"), [{ tipo: "reasignar_pago", ...r }]);
      return responder(tr("Lo tengo pendiente: te aviso antes de que venza."), [], ["sin_pago_para_mover"]);
    }
    if (/\bYA (LO |LA )?PAGUE\b/.test(n) && delQue) {
      const i = estadoDelMes(periodoHoy()).items.find((x) => x.id === delQue.id && x.estado !== "pagado");
      if (!i) return responder(tr("Eso ya aparece pagado."));
      return responder(tr("¡Bien! ¿Lo marco como pagado?"), [{ tipo: "marcar_pagado", id: i.id, nombre: i.nombre, periodo: i.periodo, vence: i.vence, signo: i.signo }]);
    }
    const r = entenderSimulado(texto);
    if (r.ok && r.compromiso.tipo === "prestamo") {
      // ¿Ya está anotado? Igual que bin/chat.py: «Es el mismo» propone actualizar el que ya estaba con el total y las cuotas nuevas.
      const c = { ...r.compromiso, id: nuevoIdComp() }, q = prestamosParecidos([c], lista, estadoSimulado(), hoy)[0];
      if (q) {
        const actual = lista.find((x) => x.id === q.id), base = Object.fromEntries(Object.entries(actual).filter(([k]) => !["pagos", "fecha", "fecha_fin", "saldo", "aproximado", "cuotas_restantes"].includes(k)));
        const nuevo = prestamoCompleto({ ...base, tipo: "prestamo", con: actual.con || c.con, cuotas_total: c.cuotas_total, prestamo: { total: c.prestamo.total, interes: c.prestamo.interes || 0, cuota: c.prestamo.cuota } });
        const cambia = ["tipo", "con", "monto", "cuotas_total", "fecha_fin"].some((k) => nuevo[k] !== actual[k]) || canonSimple(nuevo.prestamo) !== canonSimple(actual.prestamo);
        return responder(tr("Ya tienes anotado «{n}». ¿Es el mismo?").replace("{n}", q.nombre), [{ tipo: "crear_compromiso", compromiso: c, parecido: q, actualizar: cambia ? nuevo : null }]);
      }
    }
    if (r.ok) return responder(tr("Lo anoto para recordártelo. Revísalo y agrégalo."), [{ tipo: "crear_compromiso", compromiso: { ...r.compromiso, id: nuevoIdComp() } }]);
    return responder(tr("Casi: me faltó algo para anotarlo."), [{ tipo: "crear_compromiso", compromiso: { ...r.parcial, origen: "ia" }, incompleto: true, error: r.error }]);
  }

  /** En la vista previa: entiende lo básico del texto (monto, día, cuotas) para mostrar la tarjeta, como haría tu IA. */
  function entenderSimulado(texto) {
    const t = String(texto || ""), n = normalizar(t);
    const uf = (t.match(/(\d+(?:[.,]\d+)?)\s*UF\b/i) || [])[1];
    // Montos dichos con palabras: «2M», «2 millones», «2 palos», «850 lucas», «850 mil».
    const conPalabras = [...n.matchAll(/(\d+(?:[.,]\d+)?)\s*(M|MILLONES?|PALOS?|LUCAS?|MIL)\b/g)].map((x) => Number(x[1].replace(",", ".")) * (/^(M|MILLON|PALO)/.test(x[2]) ? 1e6 : 1e3));
    const montos = uf ? [Number(uf.replace(",", "."))] : conPalabras.length ? conPalabras : (t.match(/\d[\d.]*/g) || []).map((x) => Number(x.replace(/\./g, ""))).filter((x) => x >= 1000);
    const prestamo = /ME PREST|LE PREST|PRESTE A|PRESTAMO DE/.test(n);
    if (prestamo && montos.length) {
      const ingreso = /LE PREST|PRESTE A/.test(n), cuotas = Number((n.match(/EN\s+(\d{1,3})\s+(?:MESES|CUOTAS)/) || [])[1]) || 0;
      const con = ingreso ? (n.match(/\bA\s+([A-Z]+)\b(?!.*\bA\s+[A-Z]+\b)/) || [])[1] : (n.match(/(?:MI|EL|LA)\s+([A-Z]+)\s+ME PREST/) || [])[1];
      const im = E.config.inicio_mes, diaDicho = Number((n.match(/(?:LOS|EL|DIA)\s+(\d{1,2})\b/) || [])[1]) || 0;
      const c = { tipo: "prestamo", signo: ingreso ? "ingreso" : "gasto", con: con ? primeraMayuscula(con.toLowerCase()) : "", prestamo: { total: Math.max(...montos), interes: 0 },
        cuotas_total: cuotas || 0, cuotas_pagadas: 0, monto: 0, moneda: "CLP", frecuencia: "mensual", dia: diaDicho || (im && im.modo === "sueldo" && im.dia) || 25,
        categoria: "", buscar: [], tolerancia: 5, activo: true, desde: E.hoy, origen: "ia", pagos: {} };
      if (!c.con || !c.cuotas_total) return { ok: false, error: tr("No entendí todo: falta con quién o en cuántas cuotas. Corrígelo aquí y guárdalo."), parcial: c };
      const k = calcularPrestamo(c.prestamo.total, c.cuotas_total);
      Object.assign(c, { monto: k.cuota, nombre: (ingreso ? "Préstamo a " : "Préstamo de ") + c.con, prestamo: { total: k.total, interes: 0, cuota: k.cuota, ultima: k.ultima } });
      return { ok: true, compromiso: c };
    }
    if (!montos.length) return { ok: false, parcial: { nombre: primeraMayuscula((t.split(/[,.]/)[0] || "").trim().slice(0, 40)) },
      error: "No encontré el monto: escríbelo aquí y guárdalo." };
    const dia = Number((n.match(/(?:DIA|DIAS|LOS|EL)\s+(\d{1,2})\b/) || [])[1]) || 1;
    const cuotas = Number((n.match(/(\d{1,4})\s+CUOTAS/) || [])[1]) || 0;
    const tipo = /CREDITO|DEUDA|CUOTA|DIVIDENDO|PRESTAMO/.test(n) ? "deuda" : /SUELDO|ME PAGAN/.test(n) ? "ingreso" : /NETFLIX|SPOTIFY|SUSCRIP/.test(n) ? "suscripcion" : "cuenta";
    const nombre = primeraMayuscula((t.split(/[,.]/)[0] || "Compromiso").replace(/^(tengo que pagar|pago|me quedan \d+ cuotas del|el|la)\s+/i, "").trim().slice(0, 40));
    const c = { nombre, tipo, signo: tipo === "ingreso" ? "ingreso" : "gasto", monto: Math.max(...montos), moneda: "CLP", frecuencia: "mensual", dia,
      categoria: tipo === "ingreso" ? "sueldo" : /AUTO/.test(n) ? "auto" : /ARRIENDO|HIPOTECARIO|DIVIDENDO/.test(n) ? "casa" : "", buscar: [normalizar(nombre).split(" ")[0]].filter((p) => p.length > 2),
      tolerancia: 5, activo: true, desde: E.hoy, origen: "ia", pagos: {} };
    if (cuotas) { c.cuotas_total = cuotas; c.cuotas_pagadas = 0; }
    if (uf) { c.moneda = "UF"; c.monto = montos[0]; }
    const entre = n.match(/ENTRE\s+([\d.]+)\s+Y\s+([\d.]+)/);
    if (entre && !uf) { const [lo, hi] = [entre[1], entre[2]].map((x) => Number(x.replace(/\./g, ""))); if (lo > 0 && lo <= hi) { c.aproximado = { min: lo, max: hi }; c.monto = Math.round((lo + hi) / 2); } }
    else if (/APROX|MAS O MENOS|ALREDEDOR|VARIA/.test(n)) c.aproximado = { variacion: 3 };
    return { ok: true, compromiso: c };
  }

  const LOGO = `<svg class="logo" viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="15" fill="#2b1d16"/><circle cx="30" cy="13.5" r="7" fill="#f2b632"/><rect x="27.5" y="10.5" width="5" height="6" rx="1.2" fill="#d99a1e"/><path d="M42 22.5 47.5 15l1.5 10z" fill="#cf6a3e"/><ellipse cx="30" cy="38" rx="20" ry="15" fill="#d9774b"/><rect x="23" y="23.6" width="14" height="3.4" rx="1.7" fill="#2b1d16"/><ellipse cx="50.5" cy="39" rx="4.6" ry="5.4" fill="#c2603a"/><circle cx="49.6" cy="37.4" r="1" fill="#2b1d16"/><circle cx="49.6" cy="40.8" r="1" fill="#2b1d16"/><circle cx="41.5" cy="33.5" r="1.9" fill="#2b1d16"/><rect x="17" y="49" width="6" height="7" rx="2" fill="#c2603a"/><rect x="34" y="49" width="6" height="7" rx="2" fill="#c2603a"/><path d="M10.5 36c-3 0-4.5-2-3.5-4" fill="none" stroke="#c2603a" stroke-width="2.2" stroke-linecap="round"/></svg>`;
  async function iniciar() {
    if (HOST === "web") {
      try { DEMO = await (await fetch("demo.json")).json(); } catch { DEMO = { hoy: new Date().toISOString().slice(0, 10), config: {}, ias: [], movimientos: [], categorias: [] }; }
      if (new URLSearchParams(location.search).has("bienvenida")) DEMO.config.bienvenida = false; else DEMO.config.bienvenida = true;
      if (new URLSearchParams(location.search).has("vacio")) DEMO.movimientos = [];
    }
    host.enviar("listo");
  }
  iniciar();
})();
