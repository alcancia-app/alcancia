// La app del celular de punta a punta en un navegador, con el anfitrión del teléfono (movil/host) y un Capacitor falso
// (pruebas/capacitor_falso.js: el archivo de la nube, el llavero y los avisos en memoria). Nada toca archivos reales ni la red.
// Uso: node pruebas/movil.mjs   (necesita Playwright, como pruebas/interfaz.mjs)
// Revisa: teléfono nuevo (idioma primero, elegir el archivo, frase incorrecta y correcta, recordarla); solo para mirar (nada que
// cambie datos a la vista, y un toque igual solo avisa); reabrir con la llave recordada y ver lo nuevo al volver a primer plano;
// sin recordar; nube sin conexión, copia a medias o de una versión nueva; avisos de pagos (permiso al activarlos, solo lo que pagas
// tú, sin montos, a las 9); desconectar; el Mac (vista previa) arma la copia y el teléfono la abre; todo traducido al inglés.
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const WEB = fs.mkdtempSync(path.join(os.tmpdir(), "alcancia-www-"));
execFileSync(process.execPath, [path.join(RAIZ, "movil", "armar.mjs"), "--salida", WEB], { stdio: "ignore" });
const UI = path.join(RAIZ, "ui");
const tipos = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml" };
// /…: la app del celular (www/ armada); /mac/…: la interfaz de ui/ tal cual (vista previa del Mac, con demo.json).
const servidor = http.createServer((q, r) => {
  const p = decodeURIComponent(new URL(q.url, "http://x").pathname);
  const [base, resto] = p.startsWith("/mac/") ? [UI, p.slice(4)] : [WEB, p];
  const ruta = path.join(base, resto);
  if (!ruta.startsWith(base) || !fs.existsSync(ruta) || fs.statSync(ruta).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "Content-Type": tipos[path.extname(ruta)] || "application/octet-stream" }); fs.createReadStream(ruta).pipe(r);
}).listen(0);
const URL_BASE = `http://localhost:${servidor.address().port}`;
const FALSO = fs.readFileSync(path.join(RAIZ, "pruebas", "capacitor_falso.js"), "utf8");
const demo = JSON.parse(fs.readFileSync(path.join(UI, "demo.json"), "utf8"));
const HOY = demo.hoy, AHORA = new Date(`${HOY}T08:00:00`).getTime();
const esDato = (t) => JSON.stringify(demo).includes(t) || /^(Alcancía|English|Español|CLP|USD|iCloud Drive|Alcancia-celular\.alcancia)$/.test(t);

// «El Mac»: la copia armada con los mismos ui/cifrado.js (pieza) y ui/copia.js, en Node.
for (const f of ["cifrado.js", "copia.js"]) vm.runInThisContext(fs.readFileSync(path.join(UI, f), "utf8"), { filename: "ui/" + f });
const C = globalThis.AlcanciaCopia;
const FRASE = "caballo pila grapa correcta";
const mac = await C.nuevaCabecera(FRASE);
const copia = (estado) => C.armar(C.paraCelular(estado, { generado: new Date(AHORA - 3600e3).toISOString(), version: "0.1.0" }), mac.cabecera, mac.llaves);
const COPIA = await copia(demo);
const NUBE = { nombre: "Alcancia-celular.alcancia", texto: COPIA };

const errores = [];
const falla = (m) => { errores.push(m); console.log("  ✗ " + m); };
const navegador = await chromium.launch();
async function paso(nombre, f) {
  const antes = errores.length;
  try { await f(); } catch (e) { falla(`${nombre}: ${e.message.split("\n")[0]}`); }
  if (errores.length === antes) console.log("  ✓ " + nombre);
}

/** Un teléfono. `guardado` = lo que ya tenía (window._celular del Capacitor falso). */
async function telefono({ guardado = {}, consulta = "", ancho = 390 } = {}) {
  const p = await navegador.newPage({ viewport: { width: ancho, height: 844 }, locale: "es-CL" });
  p.on("pageerror", (e) => falla("error de JavaScript: " + e.message));
  p.on("console", (m) => { if (/Content Security Policy/i.test(m.text())) falla("CSP: " + m.text().slice(0, 200)); });
  await p.addInitScript(([g, hoy, ahora]) => { window._celular = g; window.ALCANCIA_HOY = hoy; window.ALCANCIA_AHORA = ahora; window._faltantes = new Set(); }, [guardado, HOY, AHORA]);
  await p.addInitScript(FALSO);
  await p.goto(`${URL_BASE}/index.html${consulta}`);
  await p.waitForFunction(() => window.Alcancia && document.querySelector(".app"));
  return p;
}
/** Lo que el teléfono tiene guardado (para «reabrir» la app en otra página). */
const guardadoDe = (p) => p.evaluate(() => { const { oyentes, llamadas, ...g } = window._celular; return JSON.parse(JSON.stringify(g)); });
const ajustes = (p) => p.evaluate(() => JSON.parse(window._celular.ajustes || "{}"));
const visible = (p, sel) => p.evaluate((s) => [...document.querySelectorAll(s)].filter((e) => e.offsetParent !== null || e.getClientRects().length).length, sel);
const toast = (p) => p.waitForFunction(() => document.querySelector("#toast.visible")?.textContent, null, { timeout: 4000 }).then((h) => h.jsonValue());
const LISTO = { nube: NUBE, elegido: true, ajustes: JSON.stringify({ idioma_ui: "es", bienvenida: true }) };
const CON_LLAVE = { ...LISTO, llave: JSON.stringify({ raw: mac.llaves.raw, sal: mac.cabecera.kdf.sal }) };

await paso("Teléfono nuevo: idioma primero, elegir el archivo y abrirlo con la frase (recordándola)", async () => {
  const p = await telefono({ guardado: { nube: NUBE } });
  await p.waitForSelector("[data-idioma-bv]");
  if (await visible(p, ".tres, #traer-frase")) falla("se ve algo antes de elegir el idioma");
  await p.click('[data-idioma-bv="es"]');
  await p.click('[data-bv="2"]');
  const texto = await p.textContent(".pz-dialogo");
  if (!texto.includes("Alcancia-celular.alcancia") || !texto.includes("Mac")) falla("el paso de traer los datos no explica dónde está el archivo: " + texto.slice(0, 200));
  if (/Claude|Codex|cartola/i.test(texto)) falla("en el teléfono se habla de IA del computador o de cartolas");
  await p.click('[data-accion="bv-traer"]');
  await p.waitForSelector("#traer-frase");
  await p.fill("#traer-frase", "caballo pila grapa incorrecta");
  await p.click('[data-traer-form] [type="submit"]');
  await p.waitForSelector(".traer-frase .error-txt");
  if (!(await p.textContent(".traer-frase .error-txt")).includes("La frase no es la correcta")) falla("frase incorrecta sin el mensaje");
  await p.fill("#traer-frase", FRASE);
  await p.check("[data-traer-recordar]");
  await p.click('[data-traer-form] [type="submit"]');
  await p.waitForSelector(".tres", { timeout: 8000 });
  const g = await guardadoDe(p);
  if (!g.llave || JSON.parse(g.llave).raw !== mac.llaves.raw) falla("no recordó la llave en el llavero");
  if (g.cache !== COPIA) falla("no guardó la última copia");
  const a = await ajustes(p);
  if (a.idioma_ui !== "es" || a.bienvenida !== true) falla("no guardó idioma y bienvenida: " + JSON.stringify(a));
  if (!(await p.textContent(".tres")).includes("Lo que gastaste")) falla("el Inicio no pinta las tres cifras");
  await p.close();
});

await paso("Solo para mirar: nada que cambie datos a la vista, y si llega un toque, solo un aviso", async () => {
  const p = await telefono({ guardado: CON_LLAVE });
  await p.waitForSelector(".tres");
  if (await visible(p, ".nav-agregar")) falla("se ve el «+» de agregar");
  if ((await visible(p, ".nav .nav-item")) !== 4) falla("la barra no tiene 4 secciones");
  const PROHIBIDO = ".nav-agregar, .fila-chat, [data-elegir], [data-comp-pagado], [data-comp-noes], [data-comp-desmarcar], [data-comp-editar], [data-sug-agregar], [data-saldo-editar], [data-sueldo], [data-regla-si], [data-accion=agregar-contar], [data-accion=pedir-consejos], [data-accion=sugerir], [data-accion=guardar-pres], [data-accion=usar-maximos], [data-vista=ordenar], [data-vista=conexiones], [data-pz-probar-ia], [data-pz-act], [data-conectar], [data-accion=importar], [data-config=pais], [data-inicio], [data-uf], input[data-pres]:not([readonly]), form[data-saldo-form]";
  const VISTAS = [["Inicio", "E=>{E.vista='resumen';E.mes='2026-10'}"], ["Lo que tienes", "E=>{E.cifra='tienes'}"], ["Lo que debes", "E=>{E.cifra='debes'}"],
    ["Lo que gastaste", "E=>{E.cifra='gastaste'}"], ["Te quedan", "E=>{E.cifra='queda'}"], ["Movimientos", "E=>{E.cifra=null;E.vista='movimientos'}"],
    ["Movimientos sin categoría", "E=>{E.filtro={texto:'',categoria:'__sin'}}"], ["Movimientos detalle", "E=>{E.filtro={texto:'',categoria:''};E.movVer=E.movimientos.find(m=>m.fecha.startsWith('2026-10')).id}"],
    ["Pagos", "E=>{E.vista='compromisos'}"], ["Más", "E=>{E.vista='mas'}"], ["Presupuesto", "E=>{E.vista='presupuesto'}"], ["Consejos", "E=>{E.vista='consejos'}"],
    ["Consejos vacío", "E=>{E.consejos=[]}"], ["Ajustes", "E=>{E.ajustes=true}"]];
  for (const [nombre, f] of VISTAS) {
    await p.evaluate(`window.Alcancia._probar(${f})`);
    await p.waitForTimeout(40);
    const n = await visible(p, PROHIBIDO);
    if (n) falla(`«${nombre}»: ${n} cosas para cambiar datos a la vista: ` + (await p.evaluate((s) => [...document.querySelectorAll(s)].filter((e) => e.offsetParent !== null).map((e) => e.outerHTML.slice(0, 90)).join(" | "), PROHIBIDO)));
    const ancho = await p.evaluate(() => document.documentElement.scrollWidth);
    if (ancho > 392) falla(`«${nombre}» se sale de la pantalla (${ancho}px)`);
  }
  if (!(await p.textContent(".pz-dialogo")).includes("Alcancia-celular.alcancia")) falla("Ajustes no dice qué archivo se lee");
  await p.evaluate(() => window.Alcancia._probar((E) => { E.ajustes = false; E.vista = "resumen"; }));
  // Un toque que llegue igual (p. ej. un botón que se coló): solo el aviso, nada se manda al Mac ni se cambia.
  const antes = await p.evaluate(() => JSON.stringify(window._celular.llamadas));
  await p.evaluate(() => { const b = document.createElement("button"); b.dataset.compPagado = "c-arriendo01|2026-10"; b.id = "colado"; b.textContent = "Ya lo pagué"; document.querySelector("main").append(b); });
  await p.$eval("#colado", (b) => b.click());
  if (!(await toast(p)).includes("Esto se hace en tu Mac por ahora")) falla("el toque no avisa que se hace en el Mac");
  if (await p.evaluate((a) => JSON.stringify(window._celular.llamadas) !== a, antes)) falla("un toque de solo-Mac llamó al teléfono");
  await p.close();
});

await paso("Reabrir: la llave recordada abre sola, y al volver a primer plano llega lo nuevo del Mac", async () => {
  const p = await telefono({ guardado: CON_LLAVE });
  await p.waitForSelector(".tres");
  if (await visible(p, "#traer-frase, [data-idioma-bv]")) falla("pidió frase o idioma de nuevo");
  const nuevo = await copia({ ...demo, movimientos: [...demo.movimientos, { id: "nuevo00000001", fecha: HOY, descripcion: "CAFETERIA RECIEN LLEGADA", monto: -3500, moneda: "CLP", categoria: "comida", cuenta: "banco-ejemplo", origen: "demo", nota: "" }] });
  await p.evaluate(([t, a]) => { window._celular.nube.texto = t; window.ALCANCIA_AHORA = a; document.dispatchEvent(new Event("visibilitychange")); }, [nuevo, AHORA + 120000]);
  await p.waitForFunction(() => window._celular.cache && window._celular.cache.length > 0 && window._celular.llamadas.filter((x) => x === "Carpeta.leer").length >= 2);
  await p.evaluate(() => window.Alcancia._probar((E) => { E.vista = "movimientos"; E.mes = "2026-10"; E.filtro = { texto: "RECIEN", categoria: "" }; }));
  await p.waitForSelector(".mov", { timeout: 4000 });
  if (!(await p.textContent(".lista-mov")).includes("Cafeteria Recien Llegada")) falla("no se ve el movimiento nuevo después de volver");
  await p.close();
});

await paso("Una copia y una llave recordada de antes de la pieza «cifrado» (32 bytes): abre sola, y el Mac sigue copiando", async () => {
  const v = JSON.parse(fs.readFileSync(path.join(RAIZ, "pruebas", "datos", "copia-antes-de-pieza.json"), "utf8"));
  const antes = { ...LISTO, nube: { ...NUBE, texto: v.texto }, llave: JSON.stringify({ raw: v.raw, sal: v.cabecera.kdf.sal }) };
  const p = await telefono({ guardado: antes });
  await p.waitForSelector(".tres");
  if (await visible(p, "#traer-frase")) falla("con la llave de antes pidió la frase");
  // El Mac con la llave de 32 bytes que tenía en el Llavero arma la copia nueva; el teléfono la abre sola.
  const nueva = await C.armar(C.paraCelular(demo, { generado: new Date(AHORA).toISOString(), version: "0.1.0" }), v.cabecera, await C.importarLlave(v.raw));
  await p.evaluate(([t, a]) => { window._celular.nube.texto = t; window.ALCANCIA_AHORA = a; document.dispatchEvent(new Event("visibilitychange")); }, [nueva, AHORA + 120000]);
  await p.waitForFunction((t) => window._celular.cache === t, nueva, { timeout: 4000 });
  if (await visible(p, "#traer-frase")) falla("la copia nueva con la llave de antes pidió la frase");
  await p.close();
  // Sin llave recordada: con la frase se abre y queda recordada la llave nueva (64 bytes).
  const q = await telefono({ guardado: { ...LISTO, nube: { ...NUBE, texto: v.texto } } });
  await q.waitForSelector("#traer-frase");
  await q.fill("#traer-frase", v.frase);
  await q.check("[data-traer-recordar]");
  await q.click('[data-traer-form] [type="submit"]');
  await q.waitForSelector(".tres", { timeout: 8000 });
  const g = await guardadoDe(q);
  if (!g.llave || Buffer.from(JSON.parse(g.llave).raw, "base64").length !== 64) falla("con la frase no recordó la llave nueva de 64 bytes");
  await q.close();
});

await paso("Sin recordar la frase: se pide al abrir", async () => {
  const p = await telefono({ guardado: LISTO });
  await p.waitForSelector("#traer-frase");
  if (await visible(p, ".tres")) falla("se ven datos sin la frase");
  await p.close();
});

await paso("Nube sin conexión, copia a medias o de una versión nueva: queda la última que se abrió, y se dice", async () => {
  for (const [nombre, cambio, espera] of [["sin conexión", { sinConexion: true }, "No pude leer el archivo en tu nube"],
    ["a medias", { nube: { ...NUBE, texto: COPIA.slice(0, COPIA.length - 400) } }, "se está copiando"],
    ["versión nueva", { nube: { ...NUBE, texto: COPIA.replace('"version":1', '"version":2') } }, "Actualiza la app del celular"]]) {
    const p = await telefono({ guardado: { ...CON_LLAVE, cache: COPIA, ...cambio } });
    await p.waitForSelector(".tres");
    const t = await toast(p);
    if (!t.includes(espera)) falla(`${nombre}: el aviso no dice «${espera}»: ${t}`);
    await p.evaluate(() => window.Alcancia._probar((E) => { E.ajustes = true; }));
    if (!(await p.textContent(".pz-dialogo")).includes("no pude leer la más nueva")) falla(`${nombre}: Ajustes no dice que la copia no es la más nueva`);
    await p.close();
  }
  // Sin nada guardado y un archivo que no es una copia: el error, sin datos.
  const p = await telefono({ guardado: { nube: { nombre: "foto.jpg", texto: "hola" }, ajustes: LISTO.ajustes } });
  await p.click('[data-accion="traer-elegir"]');
  await p.waitForSelector(".vacio .error-txt");
  if (!(await p.textContent(".vacio .error-txt")).includes("no es una copia de Alcancía")) falla("un archivo cualquiera no dice que no es la copia");
  await p.close();
});

await paso("Avisos de pagos: permiso al activarlos, solo lo que pagas tú, sin montos, a las 9 y nada si se apagan", async () => {
  // La lógica: 3 días antes y el día, nada de lo automático, ni ingresos, ni lo ya pagado.
  const p0 = await telefono({ guardado: CON_LLAVE });
  await p0.waitForSelector(".tres");
  const r = await p0.evaluate(() => {
    const base = { tipo: "cuenta", signo: "gasto", moneda: "CLP", frecuencia: "mensual", categoria: "", buscar: [], tolerancia: 5, activo: true, desde: "2026-01-01", pagos: {} };
    const lista = [{ ...base, id: "c-luz", nombre: "Luz", monto: 30000, dia: 21 },
      { ...base, id: "c-netflix", nombre: "Netflix", tipo: "suscripcion", monto: 9990, dia: 20, pago: "automatico" },
      { ...base, id: "c-sueldo", nombre: "Sueldo", tipo: "ingreso", signo: "ingreso", monto: 900000, dia: 25 },
      { ...base, id: "c-agua", nombre: "Agua", monto: 12000, dia: 19, pagos: { "2026-10": { como: "manual", fecha: "2026-10-15" } } }];
    return window.Alcancia._pruebas.avisosPagos(lista, [], "2026-10-18", "CLP", null, [], [], 35).map((a) => `${a.id} ${a.tipo} ${a.fecha} ${a.dias}`);
  });
  const esperado = ["c-luz pronto 2026-10-18 3", "c-luz hoy 2026-10-21 0", "c-agua pronto 2026-11-16 3", "c-luz pronto 2026-11-18 3", "c-agua hoy 2026-11-19 0", "c-luz hoy 2026-11-21 0"];
  if (JSON.stringify(r) !== JSON.stringify(esperado)) falla("avisosPagos = " + JSON.stringify(r));
  await p0.close();

  const p = await telefono({ guardado: CON_LLAVE });
  await p.waitForSelector(".tres");
  await p.evaluate(() => window.Alcancia._probar((E) => { E.vista = "compromisos"; E.mes = "2026-10"; }));
  if (await p.evaluate(() => window._celular.llamadas.includes("LocalNotifications.requestPermissions"))) falla("pidió permiso para avisar antes de activarlos");
  await p.check("[data-avisos]", { force: true });
  await p.waitForFunction(() => window._celular.pendientes.length > 0, null, { timeout: 4000 });
  const g = await guardadoDe(p);
  const auto = await p.evaluate(() => { const E = {}; window.Alcancia._probar((x) => Object.assign(E, { c: x.compromisos.compromisos, pal: x.palabrasAuto })); return E.c.filter((c) => window.Alcancia._pruebas.modoPago(c, E.pal) === "automatico" || c.signo === "ingreso").map((c) => c.nombre); });
  for (const n of g.pendientes) {
    if (!Number.isInteger(n.id) || n.id <= 0 || n.id >= 2 ** 31) falla("id de aviso inválido: " + n.id);
    if (!["Pago por vencer", "Un pago vence hoy"].includes(n.title)) falla("título no genérico: " + n.title);
    if (/\$|\d{4,}|\d\.\d{3}/.test(n.body)) falla("el aviso lleva un monto: " + n.body);
    if (n.schedule.hora !== 9 || n.schedule.minuto !== 0) falla("el aviso no es a las 9: " + n.schedule.at);
    if (n.schedule.at < new Date(AHORA).toISOString()) falla("aviso en el pasado: " + n.schedule.at);
    if (auto.some((x) => n.body.startsWith(x + " "))) falla("aviso de algo que se paga solo o de un ingreso: " + n.body);
  }
  if (new Set(g.pendientes.map((n) => n.id)).size !== g.pendientes.length) falla("dos avisos con el mismo id");
  if (g.tipos?.[0]?.iosHiddenPreviewsBodyPlaceholder !== "Tienes un pago por vencer") falla("sin el texto genérico para la pantalla bloqueada");
  if (!(await ajustes(p)).avisos) falla("no guardó que los avisos están activos");
  await p.uncheck("[data-avisos]", { force: true });
  await p.waitForFunction(() => window._celular.pendientes.length === 0, null, { timeout: 4000 }).catch(() => falla("al apagarlos quedaron avisos programados"));
  await p.close();

  const sin = await telefono({ guardado: { ...CON_LLAVE, permiso: "denied" } });
  await sin.waitForSelector(".tres");
  await sin.evaluate(() => window.Alcancia._probar((E) => { E.ajustes = true; }));
  await sin.click("[data-avisos]", { force: true });
  const t = await sin.waitForFunction(() => [...document.querySelectorAll("#toast")].map((x) => x.textContent).join("").includes("permite las notificaciones"), null, { timeout: 4000 }).then(() => true, () => false);
  if (!t) falla("sin permiso no dice dónde activarlo");
  if (await sin.isChecked("[data-avisos]")) falla("sin permiso el interruptor queda encendido");
  await sin.close();
});

await paso("Desconectar este teléfono: vuelve a «Trae tus datos» sin copia, llave ni avisos", async () => {
  const p = await telefono({ guardado: { ...CON_LLAVE, ajustes: JSON.stringify({ idioma_ui: "es", bienvenida: true, avisos: true }) } });
  await p.waitForSelector(".tres");
  await p.waitForFunction(() => window._celular.pendientes.length > 0, null, { timeout: 4000 });
  await p.evaluate(() => window.Alcancia._probar((E) => { E.ajustes = true; }));
  await p.click('[data-accion="traer-desconectar"]');
  // Pregunta antes (con el foco en «Cancelar»: un Enter apurado no borra nada).
  await p.waitForSelector('[data-pz-confirmar="si"]');
  if ((await p.evaluate(() => document.activeElement?.dataset.pzConfirmar)) !== "no") falla("al desconectar, el foco debe quedar en «Cancelar»");
  await p.keyboard.press("Escape");
  if (!(await p.$('[data-accion="traer-desconectar"]')) || (await guardadoDe(p)).llave === null) falla("«Cancelar» no desconecta");
  await p.click('[data-accion="traer-desconectar"]');
  await p.click('[data-pz-confirmar="si"]');
  await p.waitForSelector('[data-accion="traer-elegir"]');
  await p.waitForFunction(() => !window._celular.pendientes.length, null, { timeout: 3000 }).catch(() => {});
  const g = await guardadoDe(p);
  if (g.elegido || g.llave || g.cache || g.pendientes.length) falla("quedó algo: " + JSON.stringify({ elegido: g.elegido, llave: !!g.llave, cache: !!g.cache, avisos: g.pendientes.length }));
  await p.close();
});

await paso("Del Mac al teléfono: la vista previa del Mac arma la copia y el teléfono la abre", async () => {
  const m = await navegador.newPage({ viewport: { width: 1200, height: 820 }, locale: "es-CL" });
  m.on("pageerror", (e) => falla("error de JavaScript (Mac): " + e.message));
  await m.goto(`${URL_BASE}/mac/index.html`);
  await m.waitForFunction(() => window.Alcancia && document.querySelector(".app"));
  await m.evaluate(() => window.Alcancia._probar((E) => { E.ajustes = true; }));
  await m.click('[data-accion="celular-configurar"]');
  await m.click('[data-accion="celular-carpeta"]');
  await m.waitForSelector("#celular-frase");
  if (!(await m.isDisabled('[data-accion="celular-crear"]'))) falla("deja crear sin frase");
  await m.fill("#celular-frase", "gato");
  if (!(await m.textContent(".fuerza")).includes("Muy corta")) falla("no dice que la frase es muy corta");
  await m.fill("#celular-frase", FRASE);
  if (!(await m.isDisabled('[data-accion="celular-crear"]'))) falla("deja crear sin aceptar que la frase no se recupera");
  await m.check("[data-celular-entiendo]");
  await m.click('[data-accion="celular-crear"]');
  await m.waitForFunction(() => document.querySelector(".pz-dialogo")?.textContent.includes("Listo"), null, { timeout: 8000 });
  const texto = await m.evaluate(() => window._copiaCelular);
  if (!texto || !texto.startsWith('{"alcancia":"copia-celular"')) falla("no se escribió la copia");
  const abierto = await C.abrir(texto, { frase: FRASE });
  const plano = JSON.stringify(abierto.contenido);
  for (const x of ["ia_externa", "\"chat\"", "\"carpeta\"", "vigilar", "/Users/", "\"ias\""]) if (plano.includes(x)) falla(`la copia del Mac lleva «${x}»`);
  if (abierto.contenido.estado.movimientos.length !== demo.movimientos.length) falla("la copia del Mac no trae todos los movimientos");
  await m.click('[data-accion="celular-cerrar"]');
  if (!(await m.textContent(".pz-dialogo")).includes("Última copia")) falla("Ajustes no muestra la última copia");
  // «Copiar ahora» vuelve a escribir (con otro IV).
  await m.click('[data-accion="celular-copiar"]');
  await m.waitForFunction((t) => window._copiaCelular !== t, texto, { timeout: 4000 }).catch(() => falla("«Copiar ahora» no escribió de nuevo"));
  await m.close();
  const p = await telefono({ guardado: { nube: { nombre: "Alcancia-celular.alcancia", texto }, elegido: true, ajustes: LISTO.ajustes } });
  await p.waitForSelector("#traer-frase");
  await p.fill("#traer-frase", FRASE);
  await p.click('[data-traer-form] [type="submit"]');
  await p.waitForSelector(".tres", { timeout: 8000 });
  await p.close();
});

await paso("En inglés: todo lo del celular traducido", async () => {
  const faltan = new Set();
  for (const guardado of [{ nube: NUBE }, LISTO, CON_LLAVE]) {
    const p = await telefono({ guardado, consulta: "?idioma=en" });
    const pasos = guardado === CON_LLAVE
      ? ["E=>{E.vista='resumen'}", "E=>{E.cifra='tienes'}", "E=>{E.cifra='debes'}", "E=>{E.cifra=null;E.vista='movimientos'}", "E=>{E.vista='compromisos'}", "E=>{E.vista='mas'}", "E=>{E.vista='presupuesto'}", "E=>{E.vista='consejos';E.consejos=[]}", "E=>{E.ajustes=true}"]
      : guardado === LISTO ? ["E=>{}", "E=>{E.traer.error='La frase no es la correcta.'}", "E=>{E.ajustes=true}"] : ["E=>{E.bv=0}", "E=>{E.bv=1}", "E=>{E.bv=2}", "E=>{E.bv=null;E.celular.error='Ese archivo no es una copia de Alcancía.'}", "E=>{E.ajustes=true}"];
    await p.waitForTimeout(300);
    for (const f of pasos) { await p.evaluate(`window.Alcancia._probar(${f})`); await p.waitForTimeout(40); }
    for (const t of await p.evaluate(() => [...window._faltantes])) if (!esDato(t)) faltan.add(t);
    await p.close();
  }
  if (faltan.size) falla(`${faltan.size} textos sin traducción en ui/idiomas/en.json:\n      ` + [...faltan].map((t) => JSON.stringify(t)).join("\n      "));
});

await navegador.close();
servidor.close();
fs.rmSync(WEB, { recursive: true, force: true });
console.log(errores.length ? `✗ App del celular: ${errores.length} problemas` : "✓ App del celular OK");
process.exit(errores.length ? 1 : 0);
