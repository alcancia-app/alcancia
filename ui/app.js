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
    histCat: null,
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
  function resumen(movimientos, mes, hoy, presupuesto, categorias) {
    const neutras = new Set(categorias.filter((c) => c.tipo === "neutro").map((c) => c.id));
    const fijas = new Set(categorias.filter((c) => c.fijo).map((c) => c.id));
    const moneda = presupuesto.moneda || "CLP";
    let delMes = movimientos.filter((m) => m.fecha.startsWith(mes) && !neutras.has(m.categoria));
    const otras = delMes.filter((m) => (m.moneda || moneda) !== moneda).length;
    delMes = delMes.filter((m) => (m.moneda || moneda) === moneda);
    const porCat = {}, cuantos = {};
    for (const m of delMes) {
      if (m.monto >= 0) continue;
      const c = m.categoria || "";
      porCat[c] = (porCat[c] || 0) - m.monto; cuantos[c] = (cuantos[c] || 0) + 1;
    }
    const gastado = Object.values(porCat).reduce((a, b) => a + b, 0);
    const ingresos = delMes.filter((m) => m.monto > 0).reduce((a, m) => a + m.monto, 0);
    const total = diasDelMes(mes);
    const dia = hoy.slice(0, 7) === mes ? Number(hoy.slice(8, 10)) : hoy.slice(0, 7) > mes ? total : 0;
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
      dias_mes: total, proyeccion, proyeccion_por_categoria: proyeccionPorCategoria, alertas, otras_monedas: otras, sin_categoria: cuantos[""] || 0 };
  }
  /** Los `n` meses que terminan en `mes` (igual que resumen.historia en Python): gasto total o de una categoría, con su tope. */
  function historia(movimientos, mes, hoy, presupuesto, categorias, categoria = null, n = 6) {
    const moneda = presupuesto.moneda || "CLP";
    const conDatos = new Set(movimientos.filter((m) => (m.moneda || moneda) === moneda).map((m) => m.fecha.slice(0, 7)));
    const meses = [];
    let tope = 0;
    for (let i = n - 1; i >= 0; i--) {
      const x = sumarMes(mes, -i);
      const r = resumen(movimientos, x, hoy, presupuesto, categorias);
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
  function presupuestoSugerido(movimientos, mesesCompletos, categorias, moneda = "CLP") {
    const r = {};
    for (const c of categorias.filter((x) => x.tipo === "gasto")) {
      const valores = mesesCompletos.map((mes) => movimientos.filter((m) => m.fecha.startsWith(mes) && m.categoria === c.id && m.monto < 0
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
  const cat = (id) => E.categorias.find((c) => c.id === id) || { id: "", nombre: "Sin categoría", emoji: "🏷️", tipo: "gasto" };
  const nombreCat = (c) => (c.id && cat(c.id) === c ? c.nombre : tr("Sin categoría"));
  const nombreIA = () => E.ias.find((i) => i.id === E.config.ia)?.nombre || tr("tu IA");
  const mesesConDatos = () => [...new Set(E.movimientos.map((m) => mesDe(m.fecha)))].sort();
  const mesesCompletos = () => mesesConDatos().filter((m) => m < mesDe(E.hoy)).slice(-3);

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
    raiz.innerHTML = `<div class="app">${lateral()}<main class="principal-area">${avisoActualizacion()}${principal()}</main></div>${dialogos()}`;
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
  };
  const icono = (id) => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONOS[id]}</svg>`;
  const VISTAS = [["resumen", "Resumen"], ["movimientos", "Movimientos"], ["presupuesto", "Presupuesto"], ["consejos", "Consejos"], ["conexiones", "Conexiones"]];
  function lateral() {
    const sinCat = E.movimientos.filter((m) => !m.categoria).length;
    return `<aside class="lateral">
      <div class="cabeza"><span class="marca">${LOGO}<span>Alcancía</span></span>
        <button class="icono" data-accion="ajustes" title="Ajustes" aria-label="Ajustes">⚙︎</button></div>
      <div class="agregar-caja"><button class="boton principal grande" data-accion="importar"><span aria-hidden="true">＋</span><span>Agregar movimientos</span></button></div>
      <nav class="nav" aria-label="Secciones">${VISTAS.map(([id, nombre]) => `<button data-vista="${id}" ${E.vista === id ? 'aria-current="page"' : ""}>
        <span class="ico">${icono(id)}</span><span>${nombre}</span>${id === "movimientos" && sinCat ? `<span class="contador" title="Sin categoría">${sinCat}</span>` : ""}${id === "conexiones" && conexionesConError() ? `<span class="contador alerta-punto" title="Una conexión necesita atención">!</span>` : ""}</button>`).join("")}</nav>
      <div class="pie-lateral"><span aria-hidden="true">🔒</span><span><b>Tus datos son tuyos.</b> Todo queda en tu computador.</span></div>
    </aside>`;
  }

  function selectorMes() {
    const meses = mesesConDatos();
    const primero = meses[0] || E.mes, ultimo = mesDe(E.hoy);
    return `<div class="selector-mes" role="group" aria-label="Mes">
      <button data-mes="${sumarMes(E.mes, -1)}" ${E.mes <= primero ? "disabled" : ""} aria-label="Mes anterior" title="Mes anterior">‹</button>
      <span data-sin-traducir>${esc(nombreMes(E.mes))}</span>
      <button data-mes="${sumarMes(E.mes, 1)}" ${E.mes >= ultimo ? "disabled" : ""} aria-label="Mes siguiente" title="Mes siguiente">›</button></div>`;
  }

  function principal() {
    if (E.vista === "conexiones") return vistaConexiones();
    if (!E.movimientos.length && E.vista !== "presupuesto") return vacio();
    if (E.vista === "movimientos") return vistaMovimientos();
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

  function vistaResumen() {
    const r = resumen(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias);
    const enCurso = r.dia > 0 && r.dia < r.dias_mes;
    const pct = r.presupuesto ? Math.min(100, r.gastado / r.presupuesto * 100) : 0;
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
    const heroe = `<section class="tarjeta heroe">${ALCANCIA_DIBUJO(r.presupuesto ? 1 - Math.min(1, r.gastado / r.presupuesto) : 0.5)}
      <div class="etiqueta">${enCurso ? "Llevas gastado" : "Gastaste"}</div>
      <div class="cifra" data-sin-traducir>${esc(dinero(r.gastado))}</div>
      ${r.presupuesto ? `<div class="de">${frase("de **{x}** de presupuesto", { x: esc(dinero(r.presupuesto)) })}</div>`
        : `<div class="de"><button class="enlace" data-vista="presupuesto">Arma tu presupuesto</button> <span>para saber si vas bien.</span></div>`}
      ${r.presupuesto ? `<div class="medidor ${r.gastado > r.presupuesto ? "pasado" : ""}" role="img" aria-label="Avance del gasto del mes"><i style="width:${pct.toFixed(1)}%"></i>
        ${enCurso ? `<span class="hoy" style="left:${(r.dia / r.dias_mes * 100).toFixed(1)}%" data-texto="${esc(tr("Hoy"))}"></span>` : ""}</div>` : ""}
      ${ritmo}</section>`;
    const queda = r.ingresos - r.gastado;
    const cifras = `<div class="cifras">
      <div class="tarjeta"><small>Entró</small><b class="ingreso" data-sin-traducir>${esc(dinero(r.ingresos))}</b></div>
      <div class="tarjeta"><small>Salió</small><b data-sin-traducir>${esc(dinero(r.gastado))}</b></div>
      <div class="tarjeta"><small>${queda >= 0 ? "Te queda" : "Te falta"}</small><b class="${queda >= 0 ? "ingreso" : ""}" data-sin-traducir style="${queda < 0 ? "color:var(--rojo)" : ""}">${esc(dinero(Math.abs(queda)))}</b>
        <div class="pista">Lo que entró menos lo que salió</div></div></div>`;
    const alertas = r.alertas.map((a) => {
      const c = cat(a.categoria), n = esc(nombreCat(c));
      return a.tipo === "pasado"
        ? `<div class="alerta pasado"><span class="emoji" aria-hidden="true">${c.emoji}</span><div>${frase("{c}: te pasaste del tope", { c: n }, "b")}
            ${frase("Llevas {g} y el tope es {t}.", { g: esc(dinero(a.gastado)), t: esc(dinero(a.tope)) })}</div></div>`
        : `<div class="alerta ritmo"><span class="emoji" aria-hidden="true">${c.emoji}</span><div>${frase("{c}: vas muy rápido", { c: n }, "b")}
            ${frase("Llevas {g}. A este ritmo llegas a {p} y tu tope es {t}.", { g: esc(dinero(a.gastado)), p: esc(dinero(a.proyeccion)), t: esc(dinero(a.tope)) })}</div></div>`;
    }).join("");
    const sinCat = r.sin_categoria ? `<div class="alerta ritmo"><span class="emoji" aria-hidden="true">🏷️</span><div>${frase(r.sin_categoria === 1 ? "Hay 1 movimiento sin categoría" : "Hay {n} movimientos sin categoría", { n: r.sin_categoria }, "b")}
      <button class="enlace" data-accion="ver-sin-categoria">Ponles una</button> <span>para que el resumen cuadre.</span></div></div>` : "";
    const mensual = E.presupuesto.mensual || {};
    const ids = [...new Set([...Object.keys(r.por_categoria), ...Object.keys(mensual).filter((k) => mensual[k] > 0)])]
      .sort((a, b) => (r.por_categoria[b] || 0) - (r.por_categoria[a] || 0));
    const filas = ids.map((id) => {
      const c = cat(id), g = r.por_categoria[id] || 0, tope = mensual[id] || 0;
      const alerta = r.alertas.find((a) => a.categoria === id);
      const clase = !tope ? "libre" : alerta?.tipo === "pasado" ? "pasado" : alerta ? "ojo" : "";
      const abierta = E.histCat === id;
      const hist = abierta ? `<div class="cat-historia" id="hist-cat">${frase("Últimos 6 meses de {c}", { c: esc(nombreCat(c)) }, "h3")}
          ${bloqueHistoria(historia(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias, id), T("Gasto en {c} de los últimos 6 meses", { c: esc(nombreCat(c)) }), true)}</div>` : "";
      return `<button type="button" class="cat" data-historia="${esc(id)}" aria-expanded="${abierta}" ${abierta ? 'aria-controls="hist-cat"' : ""}><span class="emoji" aria-hidden="true">${c.emoji}</span><span class="nombre" data-sin-traducir>${esc(nombreCat(c))}</span>
        <span class="monto" data-sin-traducir>${esc(dinero(g))}${tope ? ` <small>/ ${esc(dinero(tope))}</small>` : ""}</span>
        <span class="barra ${clase}"><i style="width:${tope ? Math.min(100, g / tope * 100).toFixed(1) : Math.min(100, g / Math.max(1, r.gastado) * 100).toFixed(1)}%"></i></span></button>${hist}`;
    }).join("");
    const comparado = `<section class="tarjeta"><div class="tarjeta-cabeza"><h2>Comparado con los últimos meses</h2></div>
      ${bloqueHistoria(historia(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias), T("Gasto total de los últimos 6 meses"))}</section>`;
    return `<div class="contenido"><div class="encabezado"><h1>Resumen</h1>${selectorMes()}</div>
      ${heroe}${cifras}${alertas || sinCat ? `<section class="tarjeta"><div class="tarjeta-cabeza"><h2>Para tener en cuenta</h2></div>${alertas}${sinCat}</section>` : ""}
      ${comparado}
      <section class="tarjeta"><div class="tarjeta-cabeza"><h2>En qué se fue</h2><button class="boton sutil" data-vista="presupuesto">Editar topes</button></div>
        ${filas ? `<p class="pista-cat">Toca una categoría para ver sus últimos 6 meses.</p>${filas}` : `<p class="texto-suave">Aún no hay gastos este mes.</p>`}</section>
      ${r.otras_monedas ? `<p class="texto-suave">${frase("{n} movimientos en otra moneda no entran en estas cuentas.", { n: r.otras_monedas })}</p>` : ""}</div>`;
  }

  function opcionesCategoria(elegida) {
    return [`<option value="" ${!elegida ? "selected" : ""}>🏷️ ${esc(tr("Sin categoría"))}</option>`,
      ...E.categorias.map((c) => `<option value="${esc(c.id)}" ${c.id === elegida ? "selected" : ""}>${c.emoji} ${esc(c.nombre)}</option>`)].join("");
  }

  function vistaMovimientos() {
    const f = E.filtro, buscado = normalizar(f.texto);
    const lista = E.movimientos.filter((m) => m.fecha.startsWith(E.mes)
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
      const c = cat(m.categoria), neutro = c.tipo === "neutro";
      html += `<div class="mov ${neutro ? "neutro" : ""}">
        <label class="elegir-envoltura" style="position:relative" title="Cambiar categoría">
          <span class="elegir-cat ${m.categoria ? "" : "falta"}" style="display:grid;place-items:center" aria-hidden="true">${c.emoji}</span>
          <select data-categoria="${esc(m.id)}" aria-label="${esc(tr("Categoría"))}" data-sin-traducir style="position:absolute;inset:0;opacity:0;cursor:pointer">${opcionesCategoria(m.categoria)}</select></label>
        <div style="min-width:0"><span class="t" data-sin-traducir>${esc(m.descripcion)}</span>
          <span class="m"><span data-sin-traducir>${esc(cuentas[m.cuenta] || m.cuenta)}</span> · <span data-sin-traducir>${esc(nombreCat(c))}</span></span></div>
        <span class="valor ${m.monto > 0 && !neutro ? "ingreso" : ""}" data-sin-traducir>${esc(dinero(m.monto, m.moneda, true))}</span></div>`;
    }
    const aprender = E.aprender ? `<div class="aprender" role="status">${frase("¿Uso **{c}** para todo lo que diga «{r}», también en lo que agregues después?",
      { c: esc(cat(E.aprender.categoria).emoji + " " + nombreCat(cat(E.aprender.categoria))), r: esc(E.aprender.contiene) }, "p")}
      <button class="boton" data-accion="aprender-no">Solo este</button><button class="boton principal" data-accion="aprender-si">Sí, siempre</button></div>` : "";
    return `<div class="contenido"><div class="encabezado"><h1>Movimientos</h1>${selectorMes()}</div>${aprender}
      <div class="filtros"><input id="buscar" class="texto" type="search" placeholder="Buscar" value="${esc(f.texto)}" data-filtro="texto" aria-label="Buscar" data-sin-traducir>
        <select data-filtro="categoria" aria-label="${esc(tr("Filtrar por categoría"))}" data-sin-traducir><option value="">${esc(tr("Todas las categorías"))}</option>
          <option value="__sin" ${f.categoria === "__sin" ? "selected" : ""}>🏷️ ${esc(tr("Sin categoría"))}</option>
          ${E.categorias.map((c) => `<option value="${esc(c.id)}" ${f.categoria === c.id ? "selected" : ""} data-sin-traducir>${c.emoji} ${esc(c.nombre)}</option>`).join("")}</select></div>
      ${html || `<div class="vacio" style="padding:40px 20px"><p>${f.texto || f.categoria ? "Nada calza con ese filtro." : "No hay movimientos este mes."}</p>
        ${f.texto || f.categoria ? `<button class="boton" data-accion="limpiar-filtro">Ver todos</button>` : ""}</div>`}</div>`;
  }

  function vistaPresupuesto() {
    if (!E.presEdit) E.presEdit = { ...(E.presupuesto.mensual || {}) };
    const r = resumen(E.movimientos, E.mes, E.hoy, E.presupuesto, E.categorias);
    const completos = mesesCompletos();
    const promedio = presupuestoSugerido(E.movimientos, completos, E.categorias, E.presupuesto.moneda);
    const filas = E.categorias.filter((c) => c.tipo === "gasto").map((c) => `<div class="fila-pres"><span class="emoji" aria-hidden="true">${c.emoji}</span>
      <div style="min-width:0"><b data-sin-traducir>${esc(c.nombre)}</b>
        <small>${frase("Este mes: {x}", { x: esc(dinero(r.por_categoria[c.id] || 0)) })}${promedio[c.id] ? " · " + frase("Lo normal: {x}", { x: esc(dinero(promedio[c.id])) }) : ""}</small></div>
      <input class="texto" inputmode="numeric" data-pres="${esc(c.id)}" value="${esc(numeroPlano(E.presEdit[c.id]))}" placeholder="${esc(tr("Sin tope"))}" aria-label="${T("Tope para {c}", { c: esc(c.nombre) })}" data-sin-traducir></div>`).join("");
    const total = Object.values(E.presEdit).filter((v) => v > 0).reduce((a, b) => a + b, 0);
    const cambio = JSON.stringify(limpiarPres(E.presEdit)) !== JSON.stringify(limpiarPres(E.presupuesto.mensual || {}));
    return `<div class="contenido"><div class="encabezado"><h1>Presupuesto mensual</h1>
        <button class="boton" data-accion="sugerir" ${completos.length ? "" : "disabled"} title="${completos.length ? "Usa lo que gastas normalmente en cada categoría" : "Necesito al menos un mes completo de movimientos"}">✨ <span>Sugerir con lo que gastas</span></button></div>
      <p class="texto-suave" style="color:var(--suave);margin:-8px 0 18px;line-height:1.55">Cuánto quieres gastar como máximo cada mes en cada cosa. Alcancía te avisa cuando vas muy rápido, antes de que sea tarde.</p>
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
          <div class="pie-dialogo"><button class="boton" data-accion="importar">Agregar otra</button><button class="boton principal" data-accion="ver-movimientos">Ver movimientos</button></div>`;
      }
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
      ["¿Dónde vives?", `<p>Para mostrar bien la plata y sugerirte las recetas de los bancos de tu país.</p>${camposPais()}`, true],
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
    const el = ev.target.closest("[data-accion],[data-vista],[data-mes],[data-probar],[data-bv],[data-idioma-bv],[data-enlace],[data-respaldo],[data-consejo],[data-conectar],[data-sincronizar],[data-desconectar],[data-mcp],[data-mcp-quitar],[data-historia]");
    if (!el) return;
    const d = el.dataset;
    if (d.enlace) { ev.preventDefault(); return host.enviar("abrirEnlace", { url: d.enlace }); }
    if (d.vista) { E.vista = d.vista; E.presEdit = null; E.aprender = null; return render(); }
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
      case "aprender-si": host.enviar("regla", E.aprender); E.reglas.push(E.aprender); aplicarRegla(E.aprender); toast("Aprendido"); E.aprender = null; return render();
      case "aprender-no": E.aprender = null; return render();
      case "sugerir": {
        const s = presupuestoSugerido(E.movimientos, mesesCompletos(), E.categorias, E.presupuesto.moneda);
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
      case "bv-despues": case "bv-fin": E.bv = null; E.bvCerrada = true; host.enviar("config", { bienvenida: true }); return render();
    }
  });
  document.addEventListener("input", (ev) => {
    const ds = ev.target.dataset || {};
    if (ds.filtro === "texto") { E.filtro.texto = ev.target.value; return render(); }
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
    if (ds.filtro === "categoria") { E.filtro.categoria = ev.target.value; return render(); }
    if (ds.importarIa != null) { E.importar.ia = ev.target.checked; return; }
    if (ds.vigilar != null) { E.vigilar.activo = ev.target.checked; host.enviar("vigilar", { activo: ev.target.checked });
      toast(ev.target.checked ? "Listo: las cartolas que descargues desde ahora se agregan solas" : "Ya no reviso tu carpeta de Descargas"); return render(); }
    if (ds.compartir != null) { E.importar.compartir = ev.target.checked; return; }
    if (ds.categoria) {
      const m = E.movimientos.find((x) => x.id === ds.categoria);
      if (!m) return;
      m.categoria = ev.target.value;
      host.enviar("categoria", { mes: mesDe(m.fecha), id: m.id, categoria: m.categoria });
      const contiene = reglaPara(m.descripcion);
      const parecidos = E.movimientos.filter((x) => x !== m && contiene && normalizar(x.descripcion).includes(contiene) && x.categoria !== m.categoria).length;
      E.aprender = m.categoria && contiene && parecidos ? { contiene, categoria: m.categoria } : null;
      return render();
    }
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
    if (ev.key !== "Escape") return;
    if (E.importar && !ocupadoImportando()) { E.importar = null; return render(); }
    if (E.conectar && !E.conectar.enviando) { E.conectar = null; return render(); }
    if (E.ajustes) { E.ajustes = false; return render(); }
    if (E.aprender) { E.aprender = null; return render(); }
  });
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
        conectores: e.conectores || [], conexiones: e.conexiones || {}, vigilar: e.vigilar || { activo: false, recientes: [] }, iaExterna: e.ia_externa || [] });
      if (!E.presupuesto.moneda) E.presupuesto.moneda = E.config.moneda || "CLP";
      if (!E.mes || E.mes > mesDe(E.hoy)) E.mes = mesDe(E.hoy);
      // Primer uso: la bienvenida parte por el idioma (si ya lo eligió y cerró la app a medio camino, sigue desde el saludo).
      if (!E.config.bienvenida && E.bv === null && !E.bvCerrada) E.bv = E.config.idioma_ui ? 1 : 0;
      await cargarIdioma();
      if (e.aviso) toast(e.aviso);
      render();
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
    _pruebas: { resumen, historia, redondearArriba, presupuestoSugerido, reglaPara },
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
          clearInterval(iv); A.importado({ ok: true, nuevos: 0, repetidos: 41, sin_categoria: 0, categorizados_ia: 0 });
        }, 500);
        return;
      }
      case "categoria": { const m = DEMO.movimientos.find((x) => x.id === d.id); if (m) m.categoria = d.categoria; return; }
      case "regla": DEMO.reglas.push(d); return;
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
      case "mcpConectar": return luego(700, () => { const c = DEMO.ia_externa.find((x) => x.id === d.cliente); if (c) { c.conectado = !d.quitar; c.al_dia = !d.quitar; }
        A.mcpListo({ ok: true, cliente: d.cliente, quitar: d.quitar, nota: c && c.nota, clientes: DEMO.ia_externa }); });
      case "buscarActualizacion": return luego(500, () => A.actualizacionRevisada({ hay: false }));
      case "actualizar": { let n = 1; const iv = setInterval(() => { A.actualizacionProgreso({ paso: String(n), texto: ["", "Descargando la versión nueva…", "Preparando la versión nueva…", "Instalando: Alcancía se cerrará y volverá a abrirse sola"][n], pct: n * 33 }); if (++n > 3) clearInterval(iv); }, 700); return; }
    }
  }

  const LOGO = `<svg class="logo" viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="15" fill="#2b1d16"/><circle cx="30" cy="13.5" r="7" fill="#f2b632"/><rect x="27.5" y="10.5" width="5" height="6" rx="1.2" fill="#d99a1e"/><path d="M42 22.5 47.5 15l1.5 10z" fill="#cf6a3e"/><ellipse cx="30" cy="38" rx="20" ry="15" fill="#d9774b"/><rect x="23" y="23.6" width="14" height="3.4" rx="1.7" fill="#2b1d16"/><ellipse cx="50.5" cy="39" rx="4.6" ry="5.4" fill="#c2603a"/><circle cx="49.6" cy="37.4" r="1" fill="#2b1d16"/><circle cx="49.6" cy="40.8" r="1" fill="#2b1d16"/><circle cx="41.5" cy="33.5" r="1.9" fill="#2b1d16"/><rect x="17" y="49" width="6" height="7" rx="2" fill="#c2603a"/><rect x="34" y="49" width="6" height="7" rx="2" fill="#c2603a"/><path d="M10.5 36c-3 0-4.5-2-3.5-4" fill="none" stroke="#c2603a" stroke-width="2.2" stroke-linecap="round"/></svg>`;
  /** La alcancía del resumen: se llena de monedas con lo que todavía te queda del presupuesto (0 a 1). */
  function ALCANCIA_DIBUJO(lleno) {
    const n = Math.round(Math.max(0, Math.min(1, lleno)) * 5);
    const monedas = Array.from({ length: n }, (_, i) => `<circle cx="${20 + (i % 3) * 10 + (i > 2 ? 5 : 0)}" cy="${44 - (i > 2 ? 9 : 0)}" r="5" fill="var(--oro)" stroke="rgba(0,0,0,.15)"/>`).join("");
    return `<svg class="alcancia-dibujo" viewBox="0 0 64 64" aria-hidden="true"><defs><clipPath id="cuerpo"><ellipse cx="30" cy="38" rx="20" ry="15"/></clipPath></defs>
      <path d="M42 22.5 47.5 15l1.5 10z" fill="var(--acento)" opacity=".85"/><ellipse cx="30" cy="38" rx="20" ry="15" fill="var(--acento-suave)" stroke="var(--acento)" stroke-width="2"/>
      <g clip-path="url(#cuerpo)">${monedas}</g><rect x="23" y="23.6" width="14" height="3.4" rx="1.7" fill="var(--acento)"/>
      <ellipse cx="50.5" cy="39" rx="4.6" ry="5.4" fill="var(--acento)" opacity=".85"/><circle cx="41.5" cy="33.5" r="1.8" fill="var(--texto)"/>
      <rect x="17" y="51" width="6" height="6" rx="2" fill="var(--acento)" opacity=".85"/><rect x="34" y="51" width="6" height="6" rx="2" fill="var(--acento)" opacity=".85"/></svg>`;
  }

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
