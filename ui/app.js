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
    histCat: null, compromisos: { compromisos: [], descartados: [] }, sugerencias: [], compEdit: null, compTexto: "",
    compIA: { pidiendo: false, error: "" }, sugTodas: false,
    cifra: "gastaste", picker: null, ordenar: { i: 0, buscar: "", nueva: null }, saldoEdit: null, saldoAviso: null, reglasNo: [], compararAbierto: false,
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
    return mejor ? mejor[1] : nominal;
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

  // ───────────── Compromisos (lo mismo que bin/compromisos.py; se prueban juntos con pruebas/casos.json) ─────────────
  const ANTES = 10, DESPUES = 7, TOLERANCIA = 5;
  const dnum = (f) => Math.round(Date.UTC(+f.slice(0, 4), +f.slice(5, 7) - 1, +f.slice(8, 10)) / 864e5);
  const dfecha = (n) => new Date(n * 864e5).toISOString().slice(0, 10);
  const isoDia = (n) => ((n % 7) + 10) % 7 + 1; // el día 0 (1970-01-01) fue jueves
  const pad2 = (n) => String(n).padStart(2, "0");
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
  function coincide(m, c, moneda) {
    const monto = m.monto;
    if (monto === 0 || (monto < 0) !== (c.signo === "gasto") || (m.moneda || moneda) !== c.moneda) return false;
    const dif = Math.abs(Math.abs(monto) - c.monto);
    const palabras = (c.buscar || []).map(normalizar).filter(Boolean);
    if (!palabras.length) return dif < 0.005;
    if (dif > c.monto * (c.tolerancia ?? TOLERANCIA) / 100 + 1e-9) return false;
    const d = normalizar(m.descripcion);
    return palabras.some((p) => d.includes(p));
  }
  const pagoDe = (m) => ({ como: "automatico", fecha: m.fecha, monto: Math.abs(m.monto), movimiento: m.id, descripcion: m.descripcion });
  const menorTupla = (a, b) => { for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] < b[i]; return false; };
  function asignar(compromisos, movimientos, hasta, moneda) {
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
      if (!candidatos[c.id]) candidatos[c.id] = movimientos.filter((m) => coincide(m, c, moneda)).map((m) => [dnum(m.fecha), m]);
      const v = dnum(o.vence);
      for (const [n, m] of candidatos[c.id]) {
        if (n >= v - ANTES && n <= v + DESPUES && !usados.has(m.id) && !noEs.has(m.id) && (o.vence >= c.desde || m.fecha < c.desde))
          pares.push([[Math.abs(n - v), Math.abs(Math.abs(m.monto) - c.monto), o.vence < c.desde, o.vence, c.id, o.periodo, m.fecha, m.id], c, o, m]);
      }
    }
    pares.sort((a, b) => (menorTupla(a[0], b[0]) ? -1 : menorTupla(b[0], a[0]) ? 1 : 0));
    for (const [, c, o, m] of pares) {
      const clave = `${c.id}|${o.periodo}`;
      if (pagos[clave] || usados.has(m.id)) continue;
      usados.add(m.id); pagos[clave] = pagoDe(m);
    }
    return { ocs, pagos, usados };
  }
  const mensualDe = (c) => Math.round(c.frecuencia === "mensual" ? c.monto : c.frecuencia === "semanal" ? c.monto * 52 / 12 : c.frecuencia === "anual" ? c.monto / 12 : 0);
  /** Estado de cada compromiso en el mes (igual que compromisos.estado_mes en Python). */
  function estadoCompromisos(compromisos, movimientos, mes, hoy, moneda, per = null) {
    const activos = compromisos.filter((c) => c.activo !== false);
    const [inicio, fin] = rango(mes, per);
    const { ocs, pagos } = asignar(activos, movimientos, fin, moneda);
    const antes = inicio <= hoy && hoy <= fin ? rango(sumarMes(mes, -1), per) : null, h = dnum(hoy);
    const items = [];
    for (const [c, o] of ocs) {
      const enMes = inicio <= o.vence && o.vence <= fin;
      if (!enMes && !(antes && antes[0] <= o.vence && o.vence <= antes[1])) continue;
      const p = pagos[`${c.id}|${o.periodo}`];
      if (!p && o.vence < c.desde) continue;
      const d = dnum(o.vence) - h;
      const estado = p ? "pagado" : d > 0 ? "pendiente" : d === 0 ? "hoy" : "atrasado";
      if (!enMes && estado !== "atrasado") continue;
      const cuota = c.cuotas_total && o.n ? { numero: (c.cuotas_pagadas || 0) + o.n, total: c.cuotas_total } : null;
      items.push({ id: c.id, nombre: c.nombre, tipo: c.tipo, signo: c.signo, monto: c.monto, moneda: c.moneda, categoria: c.categoria,
        periodo: o.periodo, vence: o.vence, estado, dias: p ? 0 : Math.abs(d), pago: p || null, cuota, anterior: !enMes });
    }
    items.sort((a, b) => (a.vence !== b.vence ? (a.vence < b.vence ? -1 : 1) : a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const suma = (l) => Math.round(l.reduce((a, i) => a + i.monto, 0));
    const g = items.filter((i) => i.signo === "gasto" && i.moneda === moneda);
    const ing = items.filter((i) => i.signo === "ingreso" && i.moneda === moneda && !i.anterior);
    const resumen_ = activos.map((c) => {
      const r = { id: c.id, nombre: c.nombre, tipo: c.tipo, signo: c.signo, monto: c.monto, moneda: c.moneda, frecuencia: c.frecuencia,
        categoria: c.categoria, mensual: mensualDe(c), cuotas: null, saldo: c.saldo ?? null, por_pagar: c.saldo ?? null, termina: c.fecha_fin ?? null };
      if (c.cuotas_total) {
        const pagadas = (c.cuotas_pagadas || 0) + ocs.filter(([cc, o]) => cc === c && o.n && pagos[`${c.id}|${o.periodo}`]).length;
        const quedan = Math.max(0, c.cuotas_total - pagadas);
        const todas = vencimientos(c, "2299-12-31");
        const ultima = [...todas].reverse().find((o) => o.n)?.vence ?? null;
        r.cuotas = { pagadas: Math.min(pagadas, c.cuotas_total), total: c.cuotas_total, quedan };
        r.termina = ultima && c.fecha_fin ? (ultima < c.fecha_fin ? ultima : c.fecha_fin) : ultima || c.fecha_fin || null;
        if (r.por_pagar == null) r.por_pagar = Math.round(quedan * c.monto);
      }
      return r;
    });
    return { mes, moneda, items, total: suma(g.filter((i) => !i.anterior)), pagado: suma(g.filter((i) => i.estado === "pagado")),
      pendiente: suma(g.filter((i) => i.estado !== "pagado")), atrasado: suma(g.filter((i) => i.estado === "atrasado")),
      arrastre: suma(g.filter((i) => i.anterior)), ingresos_esperados: suma(ing), ingresos_recibidos: suma(ing.filter((i) => i.estado === "pagado")),
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
  function periodoConfig(inicioMes, compromisos, movimientos, hoy, moneda) {
    if (!inicioMes || inicioMes.modo !== "sueldo" || !Number.isInteger(inicioMes.dia) || inicioMes.dia < 1 || inicioMes.dia > 31) return null;
    return { modo: "sueldo", dia: inicioMes.dia, llegadas: llegadasSueldo(compromisos, movimientos, dfecha(dnum(hoy) + 62), moneda) };
  }
  const mediana = (valores) => { const v = [...valores].sort((a, b) => a - b), k = Math.floor(v.length / 2); return v.length % 2 ? v[k] : (v[k - 1] + v[k]) / 2; };
  /** Cuánto se puede gastar en lo variable este mes (igual que compromisos.gasto_maximo en Python). */
  function gastoMaximo(movimientos, compromisos, mes, hoy, categorias, mesesCompletos, moneda, per = null) {
    const e = estadoCompromisos(compromisos, movimientos, mes, hoy, moneda, per);
    const [inicio, fin] = rango(mes, per), rangos = mesesCompletos.map((x) => rango(x, per));
    const dentro = (f, [a, b]) => a <= f && f <= b;
    const activos = compromisos.filter((c) => c.activo !== false);
    const neutras = new Set(categorias.filter((c) => c.tipo === "neutro").map((c) => c.id));
    const deCompromiso = new Set(movimientos.filter((m) => activos.some((c) => coincide(m, c, moneda))).map((m) => m.id));
    const propios = movimientos.filter((m) => (m.moneda || moneda) === moneda && !deCompromiso.has(m.id));
    let ingreso = null, fuente = "";
    if (e.ingresos_esperados > 0) { ingreso = e.ingresos_esperados; fuente = "compromisos"; }
    else {
      const conDatos = periodosConDatos(movimientos.filter((m) => (m.moneda || moneda) === moneda), per).filter((x) => x < mes).slice(-3);
      const rs = conDatos.map((x) => rango(x, per));
      const total = movimientos.filter((m) => rs.some((r) => dentro(m.fecha, r)) && m.monto > 0 && (m.moneda || moneda) === moneda && !neutras.has(m.categoria)).reduce((a, m) => a + m.monto, 0);
      if (conDatos.length && total > 0) { ingreso = Math.round(total / conDatos.length); fuente = "promedio"; }
    }
    const comp = e.total + e.arrastre, normal = {}, gastado = {};
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
  const ORDEN_ESTADO = { atrasado: 0, hoy: 1, pendiente: 2 };
  const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  function loQueDebes(compromisos, movimientos, hoy, moneda, per = null) {
    const mes = periodoDe(hoy, per), [, fin] = rango(mes, per);
    const e = estadoCompromisos(compromisos, movimientos, mes, hoy, moneda, per);
    const conSaldo = new Map(e.compromisos.filter((c) => c.signo === "gasto" && c.tipo === "deuda" && c.moneda === moneda && c.por_pagar).map((c) => [c.id, c]));
    const pendientes = e.items.filter((i) => i.signo === "gasto" && i.moneda === moneda && i.estado !== "pagado")
      .sort((a, b) => ORDEN_ESTADO[a.estado] - ORDEN_ESTADO[b.estado] || cmp(a.vence, b.vence) || cmp(a.id, b.id));
    const partes = [];
    for (const i of pendientes) if (!conSaldo.has(i.id)) partes.push({ tipo: "compromiso", nombre: i.nombre, monto: Math.round(i.monto), este_mes: Math.round(i.monto),
      estado: i.estado, vence: i.vence, dias: i.dias, categoria: i.categoria, clave: `${i.id}|${i.periodo}` });
    const pagos = movimientos.filter((m) => m.fecha <= hoy && (m.moneda || moneda) === moneda && esPagoTarjeta(m)).map((m) => m.fecha).sort();
    const ultimo = pagos.length ? pagos[pagos.length - 1] : null, desde = rango(sumarMes(mes, -1), per)[0];
    let tarjeta = 0, compras = 0;
    const cuotas = [];
    for (const m of [...movimientos].sort((a, b) => cmp(a.fecha, b.fecha) || cmp(a.id || "", b.id || ""))) {
      if (m.medio !== "credito" || m.monto >= 0 || (m.moneda || moneda) !== moneda) continue;
      const enTarjeta = cargos(m).filter(([f]) => f <= fin && f >= desde && (ultimo == null || f > ultimo));
      if (enTarjeta.length) { tarjeta += enTarjeta.reduce((a, [, v]) => a - v, 0); compras++; }
      const n = cuotasDe(m), quedan = n ? cargos(m).filter(([f]) => f > fin).length : 0;
      if (quedan) { const c = valorCuota(m); cuotas.push({ tipo: "cuotas", nombre: m.descripcion, monto: Math.round(quedan * c), este_mes: 0, cuota: Math.round(c), quedan, total: n, categoria: m.categoria || "" }); }
    }
    if (tarjeta) partes.push({ tipo: "tarjeta", nombre: "", monto: Math.round(tarjeta), este_mes: Math.round(tarjeta), compras, desde: ultimo });
    for (const c of [...conSaldo.values()].sort((a, b) => cmp(a.id, b.id))) {
      const mias = pendientes.filter((i) => i.id === c.id);
      partes.push({ tipo: "deuda", nombre: c.nombre, monto: Math.round(c.por_pagar), este_mes: Math.round(mias.reduce((a, i) => a + i.monto, 0)), cuotas: c.cuotas, categoria: c.categoria, termina: c.termina,
        pendientes: mias.map((i) => ({ estado: i.estado, vence: i.vence, dias: i.dias, monto: Math.round(i.monto), clave: `${i.id}|${i.periodo}` })) });
    }
    partes.push(...cuotas.sort((a, b) => b.monto - a.monto || cmp(a.nombre, b.nombre)));
    return { mes, moneda, total: Math.round(partes.reduce((a, p) => a + p.monto, 0)), este_mes: Math.round(partes.reduce((a, p) => a + p.este_mes, 0)), ultimo_pago_tarjeta: ultimo, partes };
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
    const scroll = $(".principal-area")?.scrollTop || 0;
    const activo = document.activeElement, idActivo = activo?.id, cursor = activo?.selectionStart;
    E._per = undefined;
    raiz.innerHTML = `<div class="app">${lateral()}<main class="principal-area">${avisoActualizacion()}${principal()}</main></div>${E.picker ? pickerHTML() : ""}${avisoRegla()}${dialogos()}`;
    traducirDOM(raiz);
    const area = $(".principal-area"); if (area) area.scrollTop = scroll;
    if (idActivo) { const el = document.getElementById(idActivo); if (el) { el.focus(); if (cursor != null && el.setSelectionRange) try { el.setSelectionRange(cursor, cursor); } catch {} } }
    // En la pantalla de idioma el foco parte en el sugerido: Enter ya elige.
    if (E.bv === 0 && !E.importar && !E.conectar && !document.activeElement?.closest(".dialogo")) $(`#bv-idioma-${idiomaDelSistema()}`)?.focus();
  }

  const ICONOS = {
    resumen: '<path d="M4 20V11M10 20V5M16 20v-6M22 20H2" />',
    movimientos: '<path d="M4 7h16M4 12h16M4 17h10" />',
    presupuesto: '<circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r=".8" />',
    consejos: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z" /><path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z" />',
    conexiones: '<path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0z" /><path d="M12 16v5" />',
    ordenar: '<path d="M3.5 12.5V5a1.5 1.5 0 0 1 1.5-1.5h7.5l8 8a1.5 1.5 0 0 1 0 2.1l-6.4 6.4a1.5 1.5 0 0 1-2.1 0z" /><circle cx="8" cy="8" r="1.4" />',
    compromisos: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5" /><path d="M3.5 10h17M8 3v4M16 3v4" /><path d="m9 15 2 2 4-4" />',
  };
  const icono = (id) => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONOS[id]}</svg>`;
  const VISTAS = [["resumen", "Resumen"], ["compromisos", "Compromisos"], ["movimientos", "Movimientos"], ["ordenar", "Por ordenar"], ["presupuesto", "Presupuesto"], ["consejos", "Consejos"], ["conexiones", "Conexiones"]];
  function lateral() {
    const sinCat = E.movimientos.filter((m) => !m.categoria).length;
    const atrasados = listaCompromisos().length ? estadoDelMes(periodoHoy()).items.filter((i) => i.estado === "atrasado" && i.signo === "gasto").length : 0;
    return `<aside class="lateral">
      <div class="cabeza"><span class="marca">${LOGO}<span>Alcancía</span></span>
        <button class="icono" data-accion="ajustes" title="Ajustes" aria-label="Ajustes">⚙︎</button></div>
      <div class="agregar-caja"><button class="boton principal grande" data-accion="importar"><span aria-hidden="true">＋</span><span>Agregar movimientos</span></button></div>
      <nav class="nav" aria-label="Secciones">${VISTAS.filter(([id]) => id !== "ordenar" || sinCat || E.vista === "ordenar").map(([id, nombre]) => `<button data-vista="${id}" ${E.vista === id ? 'aria-current="page"' : ""}>
        <span class="ico">${icono(id)}</span><span>${nombre}</span>${id === "ordenar" && sinCat ? `<span class="contador" title="Sin categoría">${sinCat}</span>` : ""}${id === "compromisos" && atrasados ? `<span class="contador alerta-punto" title="${atrasados === 1 ? "1 compromiso atrasado" : "Compromisos atrasados"}">${atrasados}</span>` : ""}${id === "conexiones" && conexionesConError() ? `<span class="contador alerta-punto" title="Una conexión necesita atención">!</span>` : ""}</button>`).join("")}</nav>
      <div class="pie-lateral"><span aria-hidden="true">🔒</span><span><b>Tus datos son tuyos.</b> Todo queda en tu computador.</span></div>
    </aside>`;
  }

  function selectorMes() {
    const meses = mesesConDatos();
    const primero = meses[0] || E.mes, ultimo = periodoHoy();
    return `<div class="selector-mes" role="group" aria-label="Mes">
      <button data-mes="${sumarMes(E.mes, -1)}" ${E.mes <= primero ? "disabled" : ""} aria-label="Mes anterior" title="Mes anterior">‹</button>
      <span data-sin-traducir>${esc(nombreMes(E.mes))}${per() ? (([a, b]) => `<small>${esc(fechaCorta(a))} – ${esc(fechaCorta(b))}</small>`)(rango(E.mes, per())) : ""}</span>
      <button data-mes="${sumarMes(E.mes, 1)}" ${E.mes >= ultimo ? "disabled" : ""} aria-label="Mes siguiente" title="Mes siguiente">›</button></div>`;
  }

  function principal() {
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
    return `<div class="contenido"><div class="encabezado"><h1>Conexiones</h1></div>
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
  /** Lo primero que se lee: si te falta pagar algo (con los compromisos) o si estás al día. */
  function lineaAlDia() {
    if (!listaCompromisos().length) {
      return `<div class="al-dia neutro"><span class="ico" aria-hidden="true">📌</span><p>${frase("Anota lo que pagas seguido (arriendo, créditos, cuentas) y te digo si te falta pagar algo.", {})}</p>
        <button class="boton" data-vista="compromisos">Anotar</button></div>`;
    }
    const orden = { atrasado: 0, hoy: 1, pendiente: 2 };
    const pend = estadoDelMes(periodoHoy()).items.filter((i) => i.signo === "gasto" && i.estado !== "pagado")
      .sort((a, b) => orden[a.estado] - orden[b.estado] || cmp(a.vence, b.vence));
    if (!pend.length) return `<div class="al-dia ok" role="status"><span class="ico" aria-hidden="true">✓</span><p>${frase("**Estás al día.** Pagaste todo lo de este mes.", {})}</p></div>`;
    const p = pend[0], c = esc(p.nombre), x = esc(dinero(p.monto, p.moneda));
    let texto;
    if (p.estado === "atrasado") texto = p.dias === 1 ? T("Te falta pagar **{c}**: {x}, venció ayer.", { c, x }) : T("Te falta pagar **{c}**: {x}, vencido hace {n} días.", { c, x, n: p.dias });
    else if (p.estado === "hoy") texto = T("Te falta pagar **{c}**: {x}, vence hoy.", { c, x });
    else texto = p.dias === 1 ? T("Te falta pagar **{c}**: {x}, vence mañana.", { c, x }) : T("Te falta pagar **{c}**: {x}, vence en {n} días.", { c, x, n: p.dias });
    const mas = pend.length > 1 ? " " + T(pend.length === 2 ? "Y 1 cosa más ({x} en total)." : "Y {n} cosas más ({x} en total).", { n: pend.length - 1, x: esc(dinero(pend.reduce((a, i) => a + i.monto, 0))) }) : "";
    return `<div class="al-dia ${p.estado === "atrasado" ? "atrasado" : "pendiente"}" role="status"><span class="ico" aria-hidden="true">${p.estado === "atrasado" ? "!" : "•"}</span>
      <p data-sin-traducir>${texto}${mas}</p>
      <div class="acciones"><button class="boton" data-comp-pagado="${esc(`${p.id}|${p.periodo}`)}">Ya lo pagué</button>${pend.length > 1 ? `<button class="boton sutil" data-cifra-abrir="debes">Ver todo</button>` : ""}</div></div>`;
  }

  function filaCifra(id, etiqueta, num, sub) {
    const abierta = E.cifra === id;
    return `<button type="button" class="cifra-fila ${id} ${abierta ? "abierta" : ""}" data-cifra="${id}" aria-expanded="${abierta}" aria-controls="desglose">
      <span class="cf-txt"><span class="cf-etiqueta"><i class="cf-punto" aria-hidden="true"></i>${etiqueta}</span><span class="cf-sub">${sub}</span></span>
      <span class="cf-num">${num}</span><span class="cf-flecha" aria-hidden="true">›</span></button>`;
  }
  const cifraGrande = (v, moneda = monedaPrincipal()) => `<span data-sin-traducir>${esc(dinero(v, moneda))}<span class="codigo-moneda">${esc(moneda)}</span></span>`;

  function vistaResumen() {
    const moneda = monedaPrincipal();
    const r = resumen(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias, per());
    const enCurso = r.dia > 0 && r.dia < r.dias_mes;
    const t = loQueTienes(E.cuentas, E.movimientos, moneda);
    const d = loQueDebes(listaCompromisos(), E.movimientos, E.hoy, moneda, per());
    // Lo que tienes: si falta el saldo de alguna cuenta, se invita a anotarlo (nunca un cero inventado).
    const nombresSin = t.cuentas.filter((c) => c.saldo == null && c.moneda === moneda).map((c) => c.nombre);
    const subTienes = t.total == null ? frase("¿Cuánto tienes hoy en tus cuentas? Anótalo una vez y yo sigo tus movimientos.", {})
      : nombresSin.length ? frase(nombresSin.length === 1 ? "Falta anotar cuánto tienes en {c}." : "Falta anotar {n} cuentas.", { c: esc(nombresSin[0]), n: nombresSin.length })
        : frase(t.con_saldo === 1 ? "Hoy, en tu cuenta" : "Hoy, sumando tus {n} cuentas", { n: t.con_saldo });
    const numTienes = t.total == null ? `<span class="cf-invita">Anotar</span>` : cifraGrande(t.total, moneda);
    const subGasto = r.presupuesto ? frase("de {x} de presupuesto", { x: esc(dinero(r.presupuesto)) })
      : enCurso ? frase("En {m}, hasta hoy", { m: esc(nombreMes(E.mes)) }) : frase("En {m}", { m: esc(nombreMes(E.mes)) });
    const atrasados = d.partes.filter((p) => p.estado === "atrasado").length;
    const subDebes = !d.total ? frase("Nada pendiente", {})
      : frase("Este mes: {x}", { x: esc(dinero(d.este_mes)) }) + (atrasados ? ` <span class="rojo-txt">${frase(atrasados === 1 ? "· 1 atrasado" : "· {n} atrasados", { n: atrasados })}</span>` : "");
    const tres = `<section class="tres" aria-label="Tus tres números">
      ${filaCifra("tienes", "Lo que tienes", numTienes, subTienes)}
      ${filaCifra("gastaste", enCurso ? "Lo que llevas gastado" : "Lo que gastaste", cifraGrande(r.gastado, moneda), subGasto)}
      ${filaCifra("debes", "Lo que debes", cifraGrande(d.total, moneda), subDebes)}</section>`;
    const desglose = E.cifra === "tienes" ? desgloseTienes(t) : E.cifra === "debes" ? desgloseDebes(d) : desgloseGasto(r);
    return `<div class="contenido resumen-simple"><div class="encabezado"><h1>Resumen</h1>${selectorMes()}</div>
      ${lineaAlDia()}${tres}
      <section class="tarjeta desglose ${esc(E.cifra)}" id="desglose">${desglose}</section>
      ${aprendiHTML()}${sinCategoriaHTML(r)}${secundario(r, enCurso)}</div>`;
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

  function desgloseGasto(r) {
    const mensual = E.presupuesto.mensual || {};
    const ids = Object.keys(r.por_categoria).sort((a, b) => r.por_categoria[b] - r.por_categoria[a]);
    const max = Math.max(1, ...Object.values(r.por_categoria));
    const ver = E.verTodasCat ? ids : ids.slice(0, 6);
    const filas = ver.map((id) => {
      const c = cat(id), g = r.por_categoria[id], tope = mensual[id] || 0;
      const alerta = r.alertas.find((a) => a.categoria === id);
      const clase = !id ? "falta" : !tope ? "libre" : alerta?.tipo === "pasado" ? "pasado" : alerta ? "ojo" : "";
      return `<button type="button" class="cat" data-ir-cat="${esc(id)}"><span class="emoji" aria-hidden="true">${c.emoji}</span><span class="nombre" data-sin-traducir>${esc(nombreCat(c))}</span>
        <span class="monto" data-sin-traducir>${esc(dinero(g))}${tope ? ` <small>/ ${esc(dinero(tope))}</small>` : ""}</span>
        <span class="barra ${clase}"><i style="width:${(tope ? Math.min(100, g / tope * 100) : g / max * 100).toFixed(1)}%"></i></span></button>`;
    }).join("");
    const hayCuotas = E.movimientos.some((m) => cuotasDe(m));
    return `<div class="tarjeta-cabeza"><h2>En qué se fue</h2><button class="boton sutil" data-vista="presupuesto">Editar topes</button></div>
      ${filas ? `<p class="pista-cat">Toca una categoría para ver sus movimientos.</p>${filas}` : `<p class="texto-suave">Aún no hay gastos este mes.</p>`}
      ${ids.length > 6 ? `<button class="enlace mas" data-accion="ver-todas-cat" aria-expanded="${!!E.verTodasCat}">${E.verTodasCat ? "Ver menos" : frase("Ver las {n} categorías", { n: ids.length })}</button>` : ""}
      ${hayCuotas ? `<p class="nota-mcp">Las compras en cuotas con crédito cuentan por la cuota de cada mes, y las devoluciones se descuentan.</p>` : ""}
      ${r.otras_monedas ? `<p class="nota-mcp">${frase("{n} movimientos en otra moneda no entran en estas cuentas.", { n: r.otras_monedas })}</p>` : ""}`;
  }

  function desgloseDebes(d) {
    if (!d.partes.length) {
      return `<h2 class="desglose-titulo">Lo que debes</h2><p class="nada-debes">🎉 <span>No debes nada por ahora.</span></p>
        <p class="texto-suave">${listaCompromisos().length ? tr("Cuando algo de tus compromisos esté por vencer, aparece aquí.") : tr("Anota tus créditos, cuentas y suscripciones en Compromisos y aquí ves lo que te falta pagar.")}</p>`;
    }
    // Por pagar este mes: cuentas y suscripciones, y la cuota del mes de cada crédito (su total va más abajo).
    const comp = [...d.partes.filter((p) => p.tipo === "compromiso"),
      ...d.partes.filter((p) => p.tipo === "deuda").flatMap((p) => (p.pendientes || []).map((i) => ({ ...i, nombre: p.nombre, categoria: p.categoria })))]
      .sort((a, b) => ORDEN_ESTADO[a.estado] - ORDEN_ESTADO[b.estado] || cmp(a.vence, b.vence));
    const filaComp = (p) => `<div class="comp-fila ${esc(p.estado)}"><span class="emoji" aria-hidden="true">${p.categoria && cat(p.categoria).id ? cat(p.categoria).emoji : "🧾"}</span>
      <div class="txt"><b data-sin-traducir>${esc(p.nombre)}</b><small data-sin-traducir><span class="punto" aria-hidden="true"></span>${textoEstado({ ...p, signo: "gasto", pago: null })}</small></div>
      <span class="valor" data-sin-traducir>${esc(dinero(p.monto))}</span><div class="acciones"><button class="boton" data-comp-pagado="${esc(p.clave)}">Ya lo pagué</button></div></div>`;
    const fila = (ico, nombre, detalle, monto) => `<div class="debe-fila"><span class="emoji" aria-hidden="true">${ico}</span>
      <div class="txt"><b data-sin-traducir>${nombre}</b><small data-sin-traducir>${detalle}</small></div><span class="valor" data-sin-traducir>${esc(dinero(monto))}</span></div>`;
    const otras = d.partes.filter((p) => p.tipo !== "compromiso").map((p) => {
      if (p.tipo === "tarjeta") return fila("💳", T("Por pagar en tu tarjeta"), p.desde ? T(p.compras === 1 ? "1 compra con crédito desde tu último pago ({f})" : "{n} compras con crédito desde tu último pago ({f})", { n: p.compras, f: esc(fechaCorta(p.desde)) })
        : T(p.compras === 1 ? "1 compra con crédito: se paga cuando llegue el estado de cuenta" : "{n} compras con crédito: se pagan cuando llegue el estado de cuenta", { n: p.compras }), p.monto);
      if (p.tipo === "deuda") return fila("🏦", esc(p.nombre), [p.cuotas ? T("Te quedan {q} de {t} cuotas", { q: p.cuotas.quedan, t: p.cuotas.total }) : T("Saldo que anotaste"),
        p.este_mes ? T("este mes {x}", { x: esc(dinero(p.este_mes)) }) : ""].filter(Boolean).join(" · "), p.monto);
      return fila(p.categoria && cat(p.categoria).id ? cat(p.categoria).emoji : "🧾", esc(p.nombre), T(p.quedan === 1 ? "Te queda 1 cuota de {c}" : "Te quedan {q} cuotas de {c}", { q: p.quedan, c: esc(dinero(p.cuota)) }), p.monto);
    }).join("");
    return `<h2 class="desglose-titulo">Lo que debes</h2>
      ${comp.length ? `<div class="por-pagar"><h3 class="grupo">Por pagar este mes</h3>${comp.map(filaComp).join("")}</div>` : ""}
      ${otras ? `<h3 class="grupo">Tarjeta, cuotas y créditos</h3>${otras}` : ""}
      <div class="total-pres"><span>Este mes</span><span data-sin-traducir>${esc(dinero(d.este_mes))}</span></div>
      <div class="total-pres sub"><span>En total</span><span data-sin-traducir>${esc(dinero(d.total))}</span></div>
      <p class="nota-mcp"><button class="enlace" data-vista="compromisos">Ver y editar tus compromisos</button></p>`;
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
        <div class="acciones"><button class="boton sutil" data-regla-no="${esc(r.contiene)}">No</button><button class="boton principal" data-regla-si="${esc(r.contiene)}" data-regla-cat="${esc(r.categoria)}">Sí, siempre</button></div></div>`;
    }), ...sug.slice(0, reglas.length ? 1 : 2).map((s) => `<div class="aprendi-fila"><span class="emoji" aria-hidden="true">${iconoComp(s)}</span><div class="txt">${textoSugerencia(s)}</div>
        <div class="acciones"><button class="boton sutil" data-sug-no="${esc(s.clave)}">No es</button><button class="boton principal" data-sug-agregar="${esc(s.clave)}">¿Lo agrego?</button></div></div>`)];
    if (!filas.length) return "";
    return `<section class="tarjeta aprendi"><h2 class="aprendi-titulo"><span aria-hidden="true">💡</span> Aprendí esto de tus movimientos</h2>${filas.join("")}
      ${sug.length > 2 ? `<button class="enlace" data-vista="compromisos">${frase("Ver {n} más en Compromisos", { n: sug.length - (reglas.length ? 1 : 2) })}</button>` : ""}</section>`;
  }

  /** Gastos sin categoría del mes: cada uno con su chip para ordenarlo ahí mismo, y el atajo a «Por ordenar». */
  function sinCategoriaHTML(r) {
    const [desde, hasta] = rango(E.mes, per());
    const lista = E.movimientos.filter((m) => !m.categoria && desde <= m.fecha && m.fecha <= hasta).sort((a, b) => cmp(b.fecha, a.fecha));
    if (!lista.length) return "";
    const cuentas = Object.fromEntries(E.cuentas.map((c) => [c.id, c.nombre]));
    return `<section class="tarjeta sin-categoria"><div class="tarjeta-cabeza"><h2>${frase(lista.length === 1 ? "1 sin categoría" : "{n} sin categoría", { n: lista.length })}</h2>
        <button class="boton" data-vista="ordenar">Ordenar uno a uno</button></div>
      ${lista.slice(0, 3).map((m) => filaMov(m, cuentas)).join("")}
      ${lista.length > 3 ? `<button class="enlace mas" data-vista="ordenar">${frase("Y {n} más", { n: lista.length - 3 })}</button>` : ""}</section>`;
  }

  /** Lo de antes, en segundo plano: el ritmo, las alertas, la tendencia y los consejos. */
  function secundario(r, enCurso) {
    let ritmo = "";
    if (r.presupuesto && enCurso && r.proyeccion != null) {
      const dif = r.presupuesto - r.proyeccion;
      ritmo = dif >= 0 ? `<div class="ritmo bien">🙌 ${frase("A este ritmo terminas el mes en {x}: te sobrarían {y}.", { x: dinero(r.proyeccion), y: dinero(dif) })}</div>`
        : r.proyeccion <= r.presupuesto * 1.1 ? `<div class="ritmo ojo">⚖️ ${frase("A este ritmo terminas justo en el límite: {x}.", { x: dinero(r.proyeccion) })}</div>`
          : `<div class="ritmo mal">🔥 ${frase("A este ritmo terminas el mes en {x}: {y} sobre tu presupuesto.", { x: dinero(r.proyeccion), y: dinero(-dif).replace("−", "") })}</div>`;
    } else if (r.presupuesto && !enCurso && r.dia) {
      const dif = r.presupuesto - r.gastado;
      ritmo = dif >= 0 ? `<div class="ritmo bien">🏆 ${frase("Terminaste {x} bajo tu presupuesto. ¡Bien hecho!", { x: dinero(dif) })}</div>`
        : `<div class="ritmo mal">📉 ${frase("Te pasaste {x} del presupuesto. El próximo mes se puede.", { x: dinero(-dif) })}</div>`;
    }
    const alertas = r.alertas.map((a) => {
      const c = cat(a.categoria), n = esc(nombreCat(c));
      return a.tipo === "pasado"
        ? `<div class="alerta pasado"><span class="emoji" aria-hidden="true">${c.emoji}</span><div>${frase("{c}: te pasaste del tope", { c: n }, "b")}
            ${frase("Llevas {g} y el tope es {t}.", { g: esc(dinero(a.gastado)), t: esc(dinero(a.tope)) })}</div></div>`
        : `<div class="alerta ritmo"><span class="emoji" aria-hidden="true">${c.emoji}</span><div>${frase("{c}: vas muy rápido", { c: n }, "b")}
            ${frase("Llevas {g}. A este ritmo llegas a {p} y tu tope es {t}.", { g: esc(dinero(a.gastado)), p: esc(dinero(a.proyeccion)), t: esc(dinero(a.tope)) })}</div></div>`;
    }).join("");
    const sueldo = per() && enCurso ? `<p class="pista-sueldo">${frase(r.dias_mes - r.dia + 1 === 1 ? "Mañana empieza tu próximo mes (llega tu sueldo)." : "Quedan {n} días para tu próximo sueldo.", { n: r.dias_mes - r.dia + 1 })}</p>` : "";
    const h = historia(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias, null, 6, per());
    return `<h2 class="subtitulo">Cómo vas</h2>
      ${ritmo || alertas || sueldo ? `<section class="tarjeta como-vas">${ritmo}${alertas}${sueldo}</section>` : ""}
      <details class="tarjeta plegable" ${E.compararAbierto ? "open" : ""} data-plegable="comparar"><summary><span>Comparado con los últimos meses</span></summary>
        ${bloqueHistoria(h, T("Gasto total de los últimos 6 meses"))}</details>
      <button class="tarjeta fila-consejos" data-vista="consejos"><span aria-hidden="true">✦</span><span>${frase("Pídele consejos a {ia} sobre este mes", { ia: esc(nombreIA()) })}</span><span class="cf-flecha" aria-hidden="true">›</span></button>`;
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
  function chipCat(m) {
    const c = cat(m.categoria), falta = !m.categoria;
    return `<button type="button" class="chip-cat ${falta ? "falta" : ""}" id="chip-${esc(m.id)}" data-elegir="${esc(m.id)}" aria-haspopup="dialog"
      aria-label="${falta ? esc(tr("Ponle categoría")) : T("Categoría: {c}. Cambiar", { c: esc(nombreCat(c)) })}" data-sin-traducir><span aria-hidden="true">${c.emoji}</span><span class="n">${falta ? esc(tr("Ponle categoría")) : esc(nombreCat(c))}</span></button>`;
  }
  function filaMov(m, cuentas) {
    const c = cat(m.categoria), neutro = c.tipo === "neutro", medio = medioTexto(m);
    return `<div class="mov ${neutro ? "neutro" : ""}"><div class="mov-txt"><span class="t" data-sin-traducir>${esc(m.descripcion)}</span>
        <span class="m" data-sin-traducir>${esc(cuentas[m.cuenta] || m.cuenta)}${medio ? ` · <span class="medio">${medio}</span>` : ""}</span></div>
      ${chipCat(m)}<span class="valor ${m.monto > 0 && !neutro ? "ingreso" : ""}" data-sin-traducir>${esc(dinero(m.monto, m.moneda, true))}</span></div>`;
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
      <p class="picker-titulo" id="picker-titulo"><span data-sin-traducir>${esc(m.descripcion)}</span> <span class="valor" data-sin-traducir>${esc(dinero(m.monto, m.moneda, true))}</span></p>
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
    const cab = (extra = "") => `<div class="encabezado"><h1>Por ordenar</h1>${extra}</div>`;
    if (!cola.length) {
      return `<div class="contenido vista-ordenar" tabindex="-1">${cab()}<section class="tarjeta ordenado"><p class="grande">🎉</p><h2>Todo ordenado</h2>
        <p class="texto-suave">Cada movimiento tiene su categoría. Lo que agregues después y calce con lo que aprendí se ordena solo.</p>
        <button class="boton principal" data-vista="resumen">Ver el resumen</button></section></div>`;
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
        <p class="desc" data-sin-traducir>${esc(m.descripcion)}</p>
        <p class="cifra ${m.monto > 0 ? "ingreso" : ""}" data-sin-traducir>${esc(dinero(m.monto, m.moneda, true))}<span class="codigo-moneda">${esc(m.moneda || monedaPrincipal())}</span></p>
        <p class="texto-suave" data-sin-traducir>${esc(primeraMayuscula(nombreDia(m.fecha)))} · ${esc(cuentas[m.cuenta] || m.cuenta)}${medio ? ` · ${medio}` : ""}</p></section>
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
    for (const m of lista) {
      if (m.fecha !== dia) {
        dia = m.fecha;
        const total = lista.filter((x) => x.fecha === dia && x.monto < 0 && cat(x.categoria).tipo !== "neutro").reduce((a, x) => a + x.monto, 0);
        html += `<div class="dia" data-sin-traducir><span>${esc(nombreDia(dia))}</span><span>${total ? esc(dinero(total)) : ""}</span></div>`;
      }
      html += filaMov(m, cuentas);
    }
    const c = f.categoria && f.categoria !== "__sin" ? cat(f.categoria) : null;
    const hist = c && c.id ? `<section class="tarjeta"><div class="tarjeta-cabeza">${frase("Últimos 6 meses de {c}", { c: esc(nombreCat(c)) }, "h2")}</div>
      ${bloqueHistoria(historia(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias, c.id, 6, per()), T("Gasto en {c} de los últimos 6 meses", { c: esc(nombreCat(c)) }), true)}</section>` : "";
    return `<div class="contenido"><div class="encabezado"><h1>Movimientos</h1>${selectorMes()}</div>
      <div class="filtros"><input id="buscar" class="texto" type="search" placeholder="Buscar" value="${esc(f.texto)}" data-filtro="texto" aria-label="Buscar" data-sin-traducir>
        <select data-filtro="categoria" aria-label="${esc(tr("Filtrar por categoría"))}" data-sin-traducir><option value="">${esc(tr("Todas las categorías"))}</option>
          <option value="__sin" ${f.categoria === "__sin" ? "selected" : ""}>🏷️ ${esc(tr("Sin categoría"))}</option>
          ${E.categorias.map((c) => `<option value="${esc(c.id)}" ${f.categoria === c.id ? "selected" : ""} data-sin-traducir>${c.emoji} ${esc(c.nombre)}</option>`).join("")}</select>
        ${f.categoria === "__sin" && lista.length ? `<button class="boton" data-vista="ordenar">Ordenar uno a uno</button>` : ""}</div>
      ${hist}
      ${html || `<div class="vacio" style="padding:40px 20px"><p>${f.texto || f.categoria ? "Nada calza con ese filtro." : "No hay movimientos este mes."}</p>
        ${f.texto || f.categoria ? `<button class="boton" data-accion="limpiar-filtro">Ver todos</button>` : ""}</div>`}</div>`;
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
    return `<div class="contenido"><div class="encabezado"><h1>Presupuesto mensual</h1>
        <button class="boton" data-accion="sugerir" ${completos.length ? "" : "disabled"} title="${completos.length ? "Usa lo que gastas normalmente en cada categoría" : "Necesito al menos un mes completo de movimientos"}">✨ <span>Sugerir con lo que gastas</span></button></div>
      <p class="texto-suave" style="color:var(--suave);margin:-8px 0 18px;line-height:1.55">Cuánto quieres gastar como máximo cada mes en cada cosa. Alcancía te avisa cuando vas muy rápido, antes de que sea tarde.</p>
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
      cuerpo = `<section class="tarjeta"><p style="margin:0 0 14px;line-height:1.6">${frase("Cuando quieras, {ia} mira tus gastos del mes y te deja tres cosas: lo que va bien, a qué ponerle ojo y algo concreto para esta semana.", { ia })}</p>
        <button class="boton principal" data-accion="pedir-consejos">✦ <span>Pedir mis primeros consejos</span></button></section>`;
    } else {
      cuerpo = `<section class="tarjeta"><div class="tarjeta-cabeza"><h2 data-sin-traducir>${esc(primeraMayuscula(nombreDia(elegido.fecha)))}</h2></div>
        <div class="md" data-sin-traducir>${mdHTML(elegido.texto)}</div></section>
        ${E.consejos.length > 1 ? `<div class="historial" aria-label="Consejos anteriores">${E.consejos.map((c) => `<button class="chip" data-consejo="${esc(c.fecha)}" aria-pressed="${c === elegido}" data-sin-traducir>${esc(c.fecha)}</button>`).join("")}</div>` : ""}`;
    }
    return `<div class="contenido"><div class="encabezado"><h1>Consejos</h1>
        ${elegido && !E.pidiendoConsejos ? `<button class="boton principal" data-accion="pedir-consejos">✦ <span>Pedir consejos nuevos</span></button>` : ""}</div>
      ${E.errorConsejos ? `<p class="error-txt" data-sin-traducir>${esc(E.errorConsejos)}</p>` : ""}${cuerpo}
      <p style="color:var(--suave);font-size:12.5px;line-height:1.5;margin-top:16px">${frase("{ia} trabaja con tu propia cuenta y solo ve totales por categoría y los comercios donde más gastaste. Nunca ve tus cuentas ni tus claves.", { ia })}</p></div>`;
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
  const TIPOS_COMP = [["deuda", "Deuda o crédito", "🏦"], ["cuenta", "Cuenta o servicio", "🧾"], ["suscripcion", "Suscripción", "📺"],
    ["transferencia", "Transferencia frecuente", "🔁"], ["ingreso", "Ingreso", "💼"], ["otro", "Otro", "📌"]];
  const FRECUENCIAS = [["mensual", "Cada mes"], ["semanal", "Cada semana"], ["anual", "Cada año"], ["una_vez", "Una sola vez"]];
  const DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
  const monedaPrincipal = () => E.presupuesto.moneda || E.config.moneda || "CLP";
  const listaCompromisos = () => (E.compromisos && E.compromisos.compromisos) || [];
  const estadoDelMes = (mes = E.mes) => estadoCompromisos(listaCompromisos(), E.movimientos, mes, E.hoy, monedaPrincipal(), per());
  const iconoComp = (c) => (c.categoria && cat(c.categoria).id ? cat(c.categoria).emoji : (TIPOS_COMP.find((t) => t[0] === c.tipo) || TIPOS_COMP[5])[2]);
  function fechaCorta(f) {
    const [a, m, d] = f.split("-").map(Number);
    return new Date(a, m - 1, d).toLocaleDateString(locFechas(), { day: "numeric", month: "short" });
  }
  function mesLargo(f) {
    const [a, m] = f.split("-").map(Number);
    return new Date(a, m - 1, 1).toLocaleDateString(locFechas(), { month: "long", year: "numeric" });
  }
  /** «Vence en 3 días», «Atrasado 8 días», «Pagado el 30 sept»… (para ingresos: «Llega…», «Llegó…»). */
  function textoEstado(i) {
    const ing = i.signo === "ingreso";
    if (i.estado === "pagado") return T(ing ? "Llegó el {f}" : "Pagado el {f}", { f: esc(fechaCorta(i.pago.fecha)) });
    if (i.estado === "hoy") return T(ing ? "Llega hoy" : "Vence hoy");
    if (i.estado === "pendiente") return i.dias === 1 ? T(ing ? "Llega mañana" : "Vence mañana") : T(ing ? "Llega en {n} días" : "Vence en {n} días", { n: i.dias });
    return i.dias === 1 ? T(ing ? "No ha llegado: 1 día de atraso" : "Atrasado 1 día") : T(ing ? "No ha llegado: {n} días de atraso" : "Atrasado {n} días", { n: i.dias });
  }
  function filaCompromiso(i, completa) {
    const clave = esc(`${i.id}|${i.periodo}`);
    let acciones = "";
    if (i.estado !== "pagado") acciones = `<button class="boton" data-comp-pagado="${clave}">${i.signo === "ingreso" ? "Ya llegó" : "Ya lo pagué"}</button>`;
    else if (completa && i.pago.como === "automatico") acciones = `<button class="boton sutil" data-comp-noes="${clave}|${esc(i.pago.movimiento)}" title="Ese movimiento no es el pago de este compromiso">No es este</button>`;
    else if (completa) acciones = `<button class="boton sutil" data-comp-desmarcar="${clave}">Desmarcar</button>`;
    const detalle = [textoEstado(i)];
    if (i.cuota) detalle.push(T("cuota {n} de {t}", { n: i.cuota.numero, t: i.cuota.total }));
    if (completa && i.estado === "pagado" && i.pago.como === "automatico") detalle.push(T("lo reconocí en tu cartola: {d}", { d: esc(i.pago.descripcion) }));
    if (i.anterior) detalle.push(T("de {m}", { m: esc(nombreMes(i.vence.slice(0, 7))) }));
    return `<div class="comp-fila ${esc(i.estado)}"><span class="emoji" aria-hidden="true">${iconoComp(i)}</span>
      <div class="txt"><b data-sin-traducir>${esc(i.nombre)}</b><small data-sin-traducir><span class="punto" aria-hidden="true"></span>${detalle.join(" · ")}</small></div>
      <span class="valor ${i.signo === "ingreso" ? "ingreso" : ""}" data-sin-traducir>${esc(dinero(i.monto, i.moneda))}</span>
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
    const grupos = [["deuda", "Deudas y créditos"], ["cuenta", "Cuentas y servicios"], ["suscripcion", "Suscripciones"],
      ["transferencia", "Transferencias frecuentes"], ["otro", "Otros"], ["ingreso", "Ingresos"]];
    const moneda = monedaPrincipal();
    const total = e.compromisos.filter((c) => c.signo === "gasto" && c.moneda === moneda).reduce((a, c) => a + c.mensual, 0);
    const entra = e.compromisos.filter((c) => c.signo === "ingreso" && c.moneda === moneda).reduce((a, c) => a + c.mensual, 0);
    const fila = (r) => {
      const c = porId[r.id] || r;
      let extra = "";
      if (r.cuotas) {
        const pct = r.cuotas.total ? Math.round(r.cuotas.pagadas / r.cuotas.total * 100) : 0;
        const linea = r.cuotas.quedan === 0 ? T("¡Pagaste las {t} cuotas!", { t: r.cuotas.total })
          : T("Te quedan {q} de {t} cuotas", { q: r.cuotas.quedan, t: r.cuotas.total }) + (r.termina ? " · " + T("termina en {m}", { m: esc(mesLargo(r.termina)) }) : "");
        extra = `<div class="avance-deuda"><div class="barra" role="img" data-sin-traducir aria-label="${T("{p}% pagado", { p: pct })}"><i style="width:${pct}%"></i></div>
          <small data-sin-traducir>${linea}${r.por_pagar ? " · " + T(r.saldo ? "saldo que anotaste: {x}" : "quedan por pagar {x}", { x: esc(dinero(r.por_pagar, r.moneda)) }) : ""}</small></div>`;
      } else if (r.tipo === "deuda") {
        extra = `<div class="avance-deuda"><small data-sin-traducir>${r.termina ? T("termina en {m}", { m: esc(mesLargo(r.termina)) }) + " · " : ""}${r.saldo ? T("saldo que anotaste: {x}", { x: esc(dinero(r.saldo, r.moneda)) }) + " · " : ""}<button class="enlace" data-comp-editar="${esc(r.id)}">${esc(tr("Anotar cuántas cuotas faltan"))}</button></small></div>`;
      }
      return `<div class="pagando"><span class="emoji" aria-hidden="true">${iconoComp(r)}</span>
        <div class="txt"><b data-sin-traducir>${esc(r.nombre)}</b><small data-sin-traducir>${esc(dinero(r.monto, r.moneda))} ${textoFrecuencia(c)}</small>${extra}</div>
        <button class="icono" data-comp-editar="${esc(r.id)}" data-sin-traducir title="${esc(tr("Editar"))}" aria-label="${T("Editar {c}", { c: esc(r.nombre) })}">✎</button></div>`;
    };
    const pausados = listaCompromisos().filter((c) => c.activo === false);
    const bloques = grupos.map(([tipo, titulo]) => {
      const l = e.compromisos.filter((c) => c.tipo === tipo);
      return l.length ? `<h3 class="grupo">${titulo}</h3>${l.map(fila).join("")}` : "";
    }).join("");
    return `<h2 class="subtitulo">Lo que estás pagando</h2><section class="tarjeta">${bloques}
      ${pausados.length ? `<h3 class="grupo">En pausa</h3>${pausados.map((c) => fila({ ...c, mensual: 0, cuotas: null })).join("")}` : ""}
      <div class="total-pres"><span>Comprometido al mes</span><span data-sin-traducir>${esc(dinero(total))}</span></div>
      ${entra ? `<div class="total-pres sub"><span>Ingresos que esperas al mes</span><span class="ingreso" data-sin-traducir>${esc(dinero(entra))}</span></div>` : ""}</section>`;
  }
  /** Una sugerencia (detectada en la cartola) en palabras: «Parece que pagas X cerca del día 15». */
  function textoSugerencia(s) {
    const x = esc(dinero(s.monto, s.moneda)), m = esc(s.nombre);
    if (s.motivo === "palabra") return frase(s.signo === "ingreso" ? "Recibiste **{x}** ({m}) el día {d} y parece algo que se repite." : "Pagaste **{x}** ({m}) el día {d} y parece un compromiso.", { x, m, d: s.dia });
    return frase(s.signo === "ingreso" ? "Parece que recibes **{x}** cerca del día {d}: {m}." : "Parece que pagas **{x}** cerca del día {d}: {m}.", { x, m, d: s.dia });
  }
  function seccionSugerencias() {
    const lista = (E.sugerencias || []).filter((s) => !(E.compromisos.descartados || []).includes(s.clave));
    if (!lista.length) return "";
    const ver = E.sugTodas ? lista : lista.slice(0, 3);
    return `<h2 class="subtitulo">Parece que pagas esto seguido</h2><section class="tarjeta">
      ${ver.map((s) => `<div class="sugerencia"><span class="emoji" aria-hidden="true">${iconoComp(s)}</span><div class="txt">${textoSugerencia(s)}
        ${s.cuotas_total ? `<small data-sin-traducir>${T("Según tu cartola vas en la cuota {n} de {t}.", { n: s.cuotas_pagadas, t: s.cuotas_total })}</small>` : ""}</div>
        <div class="acciones"><button class="boton sutil" data-sug-no="${esc(s.clave)}">No es</button><button class="boton principal" data-sug-agregar="${esc(s.clave)}">¿Lo agrego?</button></div></div>`).join("")}
      ${lista.length > 3 ? `<button class="enlace" data-accion="sug-todas">${E.sugTodas ? "Ver menos" : frase("Ver {n} más", { n: lista.length - 3 })}</button>` : ""}</section>`;
  }
  /** El cuadro «Cuéntale a Alcancía»: con tu IA lo escribes con tus palabras; sin IA, el formulario a mano. */
  function cuadroContar() {
    if (E.compEdit && !E.importar) return `<section class="tarjeta editor-comp" id="editor-comp">${editorCompromiso()}</section>`;
    const ia = esc(nombreIA()), k = E.compIA;
    if (!E.config.ia) {
      return `<section class="tarjeta contar"><h2>Agrega lo que pagas seguido</h2>
        <p class="texto-suave">El dividendo, el arriendo, el plan del celular, una suscripción o tu sueldo. Alcancía reconoce el pago en tu cartola y te recuerda lo que falta.</p>
        <button class="boton principal" data-accion="comp-nuevo">＋ <span>Agregar un compromiso</span></button>
        <p class="nota-mcp">Con tu IA configurada (en Ajustes) también puedes escribirlo con tus palabras.</p></section>`;
    }
    return `<section class="tarjeta contar"><h2><label for="comp-texto">Cuéntale a Alcancía</label></h2>
      <p class="texto-suave">${frase("Escríbelo como se lo dirías a alguien: «el arriendo vence el 5 de cada mes, son 450.000» o «me quedan 24 cuotas del crédito del auto, 189.000 los días 20».", {})}</p>
      <textarea id="comp-texto" class="texto" rows="2" data-comp-texto data-sin-traducir aria-label="${esc(tr("Cuéntale a Alcancía"))}" ${k.pidiendo ? "disabled" : ""} placeholder="${esc(tr("¿Qué pagas, cuánto y cuándo?"))}">${esc(E.compTexto)}</textarea>
      ${k.pidiendo ? `<div class="progreso">${frase("{ia} está leyendo lo que escribiste…", { ia }, "p")}<div class="barra indef"><i></i></div></div>` : ""}
      ${k.error ? `<p class="error-txt" data-sin-traducir>${esc(k.error)}</p>` : ""}
      <div class="pie-dialogo"><button class="boton izq" data-accion="comp-nuevo">Agregar a mano</button>
        <button class="boton principal" data-accion="comp-entender" ${k.pidiendo ? "disabled" : ""}>✦ <span>Entender</span></button></div>
      <p class="nota-mcp">${frase("{ia} solo ve lo que escribes aquí, la fecha de hoy y tus categorías. Antes de guardar, te muestro cómo quedó.", { ia })}</p></section>`;
  }
  const nuevoIdComp = () => "c-" + Array.from({ length: 10 }, () => "abcdefghijklmnopqrstuvwxyz0123456789"[Math.floor(Math.random() * 36)]).join("");
  function borradorDe(c = {}) {
    return { nombre: "", tipo: "cuenta", monto: 0, moneda: monedaPrincipal(), frecuencia: "mensual", dia: Number(E.hoy.slice(8, 10)) || 1,
      fecha: E.hoy, categoria: "", buscar: [], tolerancia: 5, activo: true, desde: E.hoy, origen: "manual", ...c,
      buscarTexto: (c.buscar || []).join(", ") };
  }
  const campoNum = (id, valor, etiqueta, extra = "") => `<label class="campo"><span data-sin-traducir>${etiqueta}</span><input class="texto" id="ce-${id}" inputmode="numeric" data-ce="${id}" value="${esc(valor ? numeroPlano(valor) : "")}" ${extra} data-sin-traducir></label>`;
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
          <div class="monto-moneda">${campoNum("monto", c.monto, tr("Monto"))}<label class="campo"><span>Moneda</span><select id="ce-moneda" data-ce="moneda" data-sin-traducir>${MONEDAS.concat(MONEDAS.includes(c.moneda) ? [] : [c.moneda]).filter(Boolean).map((m) => `<option ${m === c.moneda ? "selected" : ""}>${esc(m)}</option>`).join("")}</select></label></div></div>
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
  /** Lo que se va a guardar (o null y el error en el editor). Mismas reglas que compromisos.validar en Python. */
  function compromisoDelEditor(sinOpcionales) {
    const k = E.compEdit, c = k.c;
    const limpio = { id: c.id || nuevoIdComp(), nombre: String(c.nombre || "").replace(/\d(?:[\s.\-/]?\d){5,}/g, " ").replace(/\s+/g, " ").trim().slice(0, 60).trim(),
      tipo: c.tipo, signo: c.tipo === "ingreso" ? "ingreso" : c.signo === "ingreso" && c.tipo === "transferencia" ? "ingreso" : "gasto",
      monto: Number(c.monto) || 0, moneda: c.moneda || monedaPrincipal(), frecuencia: c.frecuencia, categoria: c.categoria || "",
      buscar: [...new Set(String(c.buscarTexto || "").split(",").map((p) => normalizar(p.replace(/\d(?:[\s.\-/]?\d){5,}/g, " "))).filter((p) => p.length >= 2 && p.length <= 40))].slice(0, 6),
      tolerancia: c.tolerancia ?? 5, activo: c.activo !== false, desde: c.desde || E.hoy, origen: c.origen || "manual", pagos: c.pagos || {} };
    if (!limpio.nombre) return (k.error = tr("Ponle un nombre."), null);
    if (!(limpio.monto > 0)) return (k.error = tr("Falta el monto."), null);
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
    k.error = "";
    return limpio;
  }
  function guardarCompromiso(sinOpcionales) {
    const c = compromisoDelEditor(sinOpcionales);
    if (!c) return render();
    const lista = listaCompromisos(), i = lista.findIndex((x) => x.id === c.id);
    if (i >= 0) lista[i] = { ...c, pagos: lista[i].pagos || {}, desde: lista[i].desde }; else lista.push(c);
    E.compromisos.compromisos = lista;
    const enviar = { ...c }; delete enviar.pagos;
    host.enviar("compromiso", { accion: "guardar", hoy: E.hoy, compromiso: enviar });
    const k = E.compEdit;
    if (k.sugerencia) E.sugerencias = (E.sugerencias || []).filter((s) => s.clave !== k.sugerencia);
    if (E.importar && k.detectado != null) { E.importar.hechos = { ...(E.importar.hechos || {}), [k.detectado]: "agregado" }; E.importar.paso = "listo"; }
    E.compEdit = null;
    toast(i >= 0 ? "Compromiso guardado" : "Listo: lo voy a reconocer en tu cartola y te recuerdo si falta");
    render();
  }
  function editarDesdeSugerencia(s, extra = {}) {
    E.compEdit = { c: borradorDe({ ...s, origen: "detectado" }), origen: "detectado", extraido: !!s.cuotas_total, sugerencia: s.clave, error: "", ...extra };
  }
  function vistaCompromisos() {
    const e = estadoDelMes(), enCurso = E.mes === periodoHoy();
    const gastos = e.items.filter((i) => i.signo === "gasto"), ingresos = e.items.filter((i) => i.signo === "ingreso");
    const orden = { atrasado: 0, hoy: 1, pendiente: 2, pagado: 3 };
    const ordenar = (l) => [...l].sort((a, b) => orden[a.estado] - orden[b.estado] || (a.vence < b.vence ? -1 : a.vence > b.vence ? 1 : 0));
    const g = gastoMaximo(E.movimientos, listaCompromisos(), E.mes, E.hoy, E.categorias, mesesCompletos(), monedaPrincipal(), per());
    const hay = listaCompromisos().length;
    const cifras = hay ? `<div class="cifras">
        <div class="tarjeta"><small>Compromisos del mes</small><b data-sin-traducir>${esc(dinero(e.total + e.arrastre))}</b></div>
        <div class="tarjeta"><small>Pagado</small><b class="ingreso" data-sin-traducir>${esc(dinero(e.pagado))}</b></div>
        <div class="tarjeta"><small>Falta</small><b data-sin-traducir style="${e.atrasado ? "color:var(--rojo)" : ""}">${esc(dinero(e.pendiente))}</b>
          ${e.atrasado ? `<div class="pista">${frase("{x} atrasado", { x: esc(dinero(e.atrasado)) })}</div>` : ""}</div></div>
      ${enCurso && g.disponible != null ? `<p class="linea-maximo">${g.alcanza ? frase("Después de tus compromisos, este mes puedes gastar hasta **{x}** en lo variable.", { x: esc(dinero(g.disponible)) })
        : frase("Este mes tus compromisos y gastos fijos suman más de lo que entra.", {})} <button class="enlace" data-vista="presupuesto">Ver el detalle</button></p>` : ""}` : "";
    const listaMes = hay ? `<section class="tarjeta"><div class="tarjeta-cabeza"><h2 data-sin-traducir>${T("En {m}", { m: esc(nombreMes(E.mes)) })}</h2></div>
        ${gastos.length ? ordenar(gastos).map((i) => filaCompromiso(i, true)).join("") : `<p class="texto-suave">Nada que pagar este mes.</p>`}
        ${ingresos.length ? `<h3 class="grupo">Ingresos</h3>${ordenar(ingresos).map((i) => filaCompromiso(i, true)).join("")}` : ""}</section>` : "";
    const avisos = `<section class="tarjeta"><div class="fila sin-borde"><div class="txt"><b>🔔 Avisarme antes de que venza</b>
        <small>Un aviso 3 días antes, el día que vence y si se atrasa. Como máximo uno por compromiso al día.</small></div>
        <label class="interruptor"><input type="checkbox" data-avisos ${E.config.avisos ? "checked" : ""}><span class="visual" aria-hidden="true"></span><span class="oculto-accesible">Avisarme antes de que venza</span></label></div></section>`;
    return `<div class="contenido"><div class="encabezado"><h1>Compromisos</h1>${hay ? selectorMes() : ""}</div>
      <p class="intro-vista">${frase("Lo que pagas o recibes seguido: deudas, cuentas, suscripciones, transferencias y tu sueldo. Alcancía **reconoce el pago en tu cartola** y te recuerda lo que falta, para que no se te olvide nada.", {})}</p>
      ${cuadroContar()}${cifras}${listaMes}${seccionSugerencias()}${hay ? seccionLoQuePagas(e) : ""}${hay ? avisos : ""}</div>`;
  }
  /** Gasto máximo sugerido (en Presupuesto): lo que entra − compromisos − otros fijos, repartido según lo que gastas normalmente. */
  function tarjetaGastoMaximo() {
    const g = gastoMaximo(E.movimientos, listaCompromisos(), E.mes, E.hoy, E.categorias, mesesCompletos(), monedaPrincipal(), per());
    const cab = `<div class="tarjeta-cabeza"><h2>Gasto máximo sugerido</h2></div>`;
    if (g.ingreso == null) return `<section class="tarjeta maximo">${cab}<p class="texto-suave">Cuando sepa cuánto te entra al mes (anota tu sueldo en Compromisos o agrega cartolas con tus ingresos), aquí te digo cuánto puedes gastar en lo variable.</p></section>`;
    const origen = g.fuente === "compromisos" ? tr("Según los ingresos que anotaste en Compromisos.") : tr("Según el promedio de lo que te entró los últimos meses.");
    const desglose = frase("Entra {i} · compromisos {c} · otros gastos fijos {f}", { i: esc(dinero(g.ingreso)), c: esc(dinero(g.compromisos)), f: esc(dinero(g.otros_fijos)) }, "small");
    if (!g.alcanza) {
      return `<section class="tarjeta maximo">${cab}<div class="ritmo ojo">🫶 ${frase("Este mes lo comprometido ({c}) es más de lo que entra ({i}): faltan {x}.", { c: esc(dinero(g.compromisos + g.otros_fijos)), i: esc(dinero(g.ingreso)), x: esc(dinero(-(g.disponible || 0))) })}</div>
        <p class="texto-suave">Respira: tenerlo claro ya es avanzar. Mira si algún compromiso se puede mover de fecha o si algún gasto fijo se puede bajar, y anota en Compromisos lo que tengas claro.</p>
        <p class="pie-maximo">${desglose} <small data-sin-traducir>${esc(origen)}</small></p></section>`;
    }
    const filas = g.por_categoria.filter((x) => x.maximo > 0 || x.gastado > 0).map((x) => {
      const c = cat(x.categoria), pct = x.maximo ? Math.min(100, x.gastado / x.maximo * 100) : 100;
      return `<div class="cat"><span class="emoji" aria-hidden="true">${c.emoji}</span><span class="nombre" data-sin-traducir>${esc(nombreCat(c))}</span>
        <span class="monto" data-sin-traducir>${esc(dinero(x.gastado))} <small>/ ${esc(dinero(x.maximo))}</small></span>
        <span class="barra ${x.gastado > x.maximo ? "pasado" : x.gastado > x.maximo * 0.85 ? "ojo" : ""}"><i style="width:${pct.toFixed(1)}%"></i></span></div>`;
    }).join("");
    return `<section class="tarjeta maximo">${cab}<p class="maximo-cifra">${frase("Este mes puedes gastar hasta **{x}** en lo variable.", { x: esc(dinero(g.disponible)) })}</p>
      <p class="pie-maximo">${desglose} <small data-sin-traducir>${esc(origen)}</small></p>
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
    return "";
  }

  // ───────────── Eventos ─────────────
  const ocupadoImportando = () => ["leyendo", "aprendiendo", "guardando"].includes(E.importar?.paso);
  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-accion],[data-vista],[data-mes],[data-probar],[data-bv],[data-idioma-bv],[data-enlace],[data-respaldo],[data-consejo],[data-conectar],[data-sincronizar],[data-desconectar],[data-mcp],[data-mcp-quitar],[data-historia],[data-comp-pagado],[data-comp-noes],[data-comp-desmarcar],[data-comp-editar],[data-sug-agregar],[data-sug-no],[data-det-agregar],[data-det-no],[data-cifra],[data-cifra-abrir],[data-ir-cat],[data-elegir],[data-pick],[data-nueva-cat],[data-nueva-emoji],[data-nueva-cancelar],[data-nueva-guardar],[data-cerrar-picker],[data-saldo-editar],[data-saldo-cancelar],[data-regla-si],[data-regla-no]");
    if (!el) return;
    const d = el.dataset;
    if (d.enlace) { ev.preventDefault(); return host.enviar("abrirEnlace", { url: d.enlace }); }
    if (d.cerrarPicker != null) { const id = E.picker?.id; E.picker = null; render(); return document.getElementById("chip-" + id)?.focus(); }
    if (d.vista) { E.vista = d.vista; E.presEdit = null; E.picker = null; if (d.vista === "ordenar") E.ordenar = { i: 0, buscar: "", nueva: null }; render(); if (d.vista === "ordenar") $(".vista-ordenar")?.focus(); return; }
    if (d.cifra || d.cifraAbrir) { E.cifra = d.cifraAbrir || d.cifra; E.saldoAviso = null; render(); if (d.cifraAbrir) $("#desglose")?.scrollIntoView?.({ block: "nearest" }); return $(`[data-cifra="${E.cifra}"]`)?.focus(); }
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
    if (d.sincronizar) { E.sincronizando[d.sincronizar] = true; host.enviar("sincronizar", { conector: d.sincronizar }); return render(); }
    if (d.desconectar) { host.enviar("desconectar", { conector: d.desconectar }); E.conexiones[d.desconectar] = { conectado: false }; toast("Desconectado. Tus movimientos siguen aquí."); return render(); }
    if (d.compPagado || d.compDesmarcar || d.compNoes) return marcarCompromiso(d);
    if (d.compEditar) {
      const c = listaCompromisos().find((x) => x.id === d.compEditar);
      if (c) { E.compEdit = { c: borradorDe(c), origen: c.origen, error: "" }; E.vista = "compromisos"; render(); enfocarEditor(); }
      return;
    }
    if (d.sugAgregar || d.sugNo) {
      const s = (E.sugerencias || []).find((x) => x.clave === (d.sugAgregar || d.sugNo));
      if (!s) return;
      if (d.sugNo) { E.compromisos.descartados = [...(E.compromisos.descartados || []), s.clave]; host.enviar("compromiso", { accion: "descartar", clave: s.clave }); toast("Listo: no te lo vuelvo a sugerir"); return render(); }
      editarDesdeSugerencia(s); E.vista = "compromisos"; render(); return enfocarEditor();
    }
    if (d.detAgregar != null || d.detNo != null) {
      const n = Number(d.detAgregar ?? d.detNo), s = E.importar?.resultado?.detectados?.[n];
      if (!s) return;
      if (d.detNo != null) { E.importar.hechos = { ...(E.importar.hechos || {}), [n]: "no" }; host.enviar("compromiso", { accion: "descartar", clave: s.clave }); return render(); }
      editarDesdeSugerencia(s, { detectado: n }); E.importar.paso = "compromiso"; render(); return $("#ce-nombre")?.focus();
    }
    const im = E.importar;
    switch (d.accion) {
      case "ajustes": E.ajustes = true; return render();
      case "cerrar": E.ajustes = false; return render();
      case "importar": E.importar = { paso: "elegir", ia: !!E.config.ia, compartir: false }; return render();
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
      case "comp-nuevo": E.compEdit = { c: borradorDe(), origen: "manual", error: "" }; render(); return enfocarEditor();
      case "comp-entender": {
        const texto = String(E.compTexto || "").trim();
        if (texto.length < 4) { E.compIA = { pidiendo: false, error: tr("Cuéntame qué pagas, cuánto y cuándo.") }; return render(); }
        E.compIA = { pidiendo: true, error: "" }; host.enviar("compromisoIA", { texto, hoy: E.hoy }); return render();
      }
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
      case "ver-todas-cat": E.verTodasCat = !E.verTodasCat; return render();
      case "usar-maximos": {
        const g = gastoMaximo(E.movimientos, listaCompromisos(), E.mes, E.hoy, E.categorias, mesesCompletos(), monedaPrincipal(), per());
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
    if (ds.compTexto != null) { E.compTexto = ev.target.value; return; }
    if (ds.ce && E.compEdit && ev.target.tagName === "INPUT") {
      const numerico = ["monto", "cuotas_total", "cuotas_pagadas", "saldo"].includes(ds.ce);
      E.compEdit.c[ds.ce] = numerico ? Number(ev.target.value.replace(/\D/g, "")) || 0 : ds.ce === "dia" ? Number(ev.target.value) || 0 : ev.target.value;
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
      if (["monto", "cuotas_total", "cuotas_pagadas", "saldo"].includes(ds.ce)) { ev.target.value = numeroPlano(c[ds.ce]); return; }
      if (ev.target.tagName !== "SELECT") return;
      c[ds.ce] = ds.ce === "dia" ? Number(ev.target.value) : ev.target.value;
      if (ds.ce === "frecuencia") c.dia = ev.target.value === "semanal" ? Math.min(7, c.dia || 1) : c.dia || 1;
      if (ds.ce === "tipo" && ev.target.value === "ingreso" && !c.categoria) c.categoria = "sueldo";
      if (ds.ce === "tipo" || ds.ce === "frecuencia") { render(); $(`#ce-${ds.ce}`)?.focus(); }
      return;
    }
    if (ds.ceActivo != null && E.compEdit) { E.compEdit.c.activo = ev.target.checked; return; }
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
      E._per = undefined; E.mes = periodoHoy(); E.presEdit = null; return render();
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
    if (E.vista === "ordenar" && !E.picker && !E.importar && !E.conectar && !E.ajustes && E.bv === null && !E.ordenar.nueva && !t.matches?.("input, textarea, select") && !ev.metaKey && !ev.ctrlKey && !ev.altKey) {
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
    if (E.aprender) { E.aprender = null; return render(); }
    if (E.compEdit) { E.compEdit = null; return render(); }
  });
  document.addEventListener("submit", (ev) => {
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
      ${sueldo ? `<p class="nota-mcp">Si anotas tu sueldo en Compromisos, tu mes parte el día que de verdad llega: si te pagan antes, parte ese día. Los bonos cuentan como ingresos del mes en que caen.</p>` : ""}`;
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

  // ───────────── Lo que manda la app ─────────────
  window.Alcancia = {
    async estado(e) {
      Object.assign(E, { hoy: e.hoy, config: e.config || {}, ias: e.ias || [], movimientos: e.movimientos || [], categorias: e.categorias || [],
        presupuesto: e.presupuesto || { mensual: {} }, reglas: e.reglas || [], consejos: (e.consejos || []).slice().sort((a, b) => b.fecha.localeCompare(a.fecha)),
        cuentas: e.cuentas || [], version: e.version || "", carpeta: e.carpeta || "", actualizacion: e.actualizacion || { hay: false },
        conectores: e.conectores || [], conexiones: e.conexiones || {}, vigilar: e.vigilar || { activo: false, recientes: [] }, iaExterna: e.ia_externa || [],
        compromisos: e.compromisos || { compromisos: [], descartados: [] }, sugerencias: e.sugerencias || [] });
      if (!E.presupuesto.moneda) E.presupuesto.moneda = E.config.moneda || "CLP";
      E._per = undefined;
      if (!E.mes || E.mes > periodoHoy()) E.mes = periodoHoy();
      // Primer uso: la bienvenida parte por el idioma (si ya lo eligió y cerró la app a medio camino, sigue desde el saludo).
      if (!E.config.bienvenida && E.bv === null && !E.bvCerrada) E.bv = E.config.idioma_ui ? 1 : 0;
      await cargarIdioma();
      if (e.aviso) toast(e.aviso);
      render();
    },
    compromisoEntendido(r) {
      E.compIA = { pidiendo: false, error: r.ok ? "" : r.error || tr("No pude entenderlo. Agrégalo a mano.") };
      if (r.ok && r.compromiso) { E.compEdit = { c: borradorDe(r.compromiso), origen: "ia", error: "" }; E.compTexto = ""; }
      render();
      if (r.ok) enfocarEditor();
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
      if (r.ok && (r.detectados || []).length) toast(T(r.detectados.length === 1 ? "Encontré 1 pago que parece un compromiso: revísalo en Compromisos" : "Encontré {n} pagos que parecen compromisos: revísalos en Compromisos", { n: r.detectados.length }));
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
    _pruebas: { resumen, historia, redondearArriba, presupuestoSugerido, reglaPara, estadoCompromisos, gastoMaximo, rango, periodoDe, periodoConfig, loQueTienes, loQueDebes, cargos },
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
      case "compromisoIA": return luego(900, () => A.compromisoEntendido(entenderSimulado(d.texto)));
      case "compromiso": {
        const lista = DEMO.compromisos.compromisos, c = lista.find((x) => x.id === d.id);
        if (d.accion === "guardar") { const i = lista.findIndex((x) => x.id === d.compromiso.id); const n = { pagos: {}, ...(i >= 0 ? lista[i] : {}), ...d.compromiso }; if (i >= 0) lista[i] = n; else lista.push(n); }
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

  /** En la vista previa: entiende lo básico del texto (monto, día, cuotas) para mostrar la tarjeta, como haría tu IA. */
  function entenderSimulado(texto) {
    const t = String(texto || ""), n = normalizar(t);
    const montos = (t.match(/\d[\d.]*/g) || []).map((x) => Number(x.replace(/\./g, ""))).filter((x) => x >= 1000);
    if (!montos.length) return { ok: false, error: "No encontré el monto. Prueba con algo como «el arriendo vence el 5 de cada mes, son 450.000»." };
    const dia = Number((n.match(/(?:DIA|DIAS|LOS|EL)\s+(\d{1,2})\b/) || [])[1]) || 1;
    const cuotas = Number((n.match(/(\d{1,4})\s+CUOTAS/) || [])[1]) || 0;
    const tipo = /CREDITO|DEUDA|CUOTA|DIVIDENDO|PRESTAMO/.test(n) ? "deuda" : /SUELDO|ME PAGAN/.test(n) ? "ingreso" : /NETFLIX|SPOTIFY|SUSCRIP/.test(n) ? "suscripcion" : "cuenta";
    const nombre = primeraMayuscula((t.split(/[,.]/)[0] || "Compromiso").replace(/^(tengo que pagar|pago|me quedan \d+ cuotas del|el|la)\s+/i, "").trim().slice(0, 40));
    const c = { nombre, tipo, signo: tipo === "ingreso" ? "ingreso" : "gasto", monto: Math.max(...montos), moneda: "CLP", frecuencia: "mensual", dia,
      categoria: tipo === "ingreso" ? "sueldo" : /AUTO/.test(n) ? "auto" : /ARRIENDO|HIPOTECARIO|DIVIDENDO/.test(n) ? "casa" : "", buscar: [normalizar(nombre).split(" ")[0]].filter((p) => p.length > 2),
      tolerancia: 5, activo: true, desde: E.hoy, origen: "ia", pagos: {} };
    if (cuotas) { c.cuotas_total = cuotas; c.cuotas_pagadas = 0; }
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
