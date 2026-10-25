// Pruebas de la interfaz (ui/) en un navegador real con los datos ficticios de ui/demo.json.
// Uso: node pruebas/interfaz.mjs   (necesita Playwright; PLAYWRIGHT=/ruta/a/playwright si no está instalado aquí)
// Revisa: 1) ninguna vista tira errores de JavaScript (español e inglés, claro y oscuro, escritorio y celular);
// 2) todo texto tiene traducción en ui/idiomas/en.json; 3) los casos compartidos de pruebas/casos.json (misma lógica que Python);
// 4) el contraste del botón principal; 5) nada se sale de la pantalla a ancho de celular. Con CAPTURAS=carpeta guarda capturas.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const CAPTURAS = process.env.CAPTURAS || "";
const errores = [];
const falla = (m) => { errores.push(m); console.log("  ✗ " + m); };
const tipos = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml" };
const servidor = http.createServer((q, r) => {
  const ruta = path.join(RAIZ, "ui", decodeURIComponent(new URL(q.url, "http://x").pathname));
  if (!ruta.startsWith(path.join(RAIZ, "ui")) || !fs.existsSync(ruta) || fs.statSync(ruta).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "Content-Type": tipos[path.extname(ruta)] || "application/octet-stream" });
  fs.createReadStream(ruta).pipe(r);
}).listen(0);
const BASE = `http://localhost:${servidor.address().port}/index.html`;
const demo = fs.readFileSync(path.join(RAIZ, "ui", "demo.json"), "utf8");
const casos = JSON.parse(fs.readFileSync(path.join(RAIZ, "pruebas", "casos.json"), "utf8"));
// Textos que vienen de los datos (descripciones, nombres de IA y de categorías) o que no se traducen.
const esDato = (t) => demo.includes(t) || /^(Alcancía|Claude|ChatGPT \(Codex\)|Gemini|English|Español|CLP|USD)$/.test(t);

const VISTAS = [
  ["resumen", "E=>{E.vista='resumen'}"],
  ["resumen-mes-pasado", "E=>{E.mes='2026-09'}"],
  ["movimientos", "E=>{E.vista='movimientos';E.mes='2026-10'}"],
  ["movimientos-aprender", "E=>{E.aprender={contiene:'PAGO PENDIENTE',categoria:'cuentas'}}"],
  ["movimientos-filtro", "E=>{E.aprender=null;E.filtro={texto:'zzz',categoria:''}}"],
  ["presupuesto", "E=>{E.filtro={texto:'',categoria:''};E.vista='presupuesto'}"],
  ["consejos", "E=>{E.vista='consejos'}"],
  ["consejos-pidiendo", "E=>{E.pidiendoConsejos=true}"],
  ["consejos-vacio", "E=>{E.pidiendoConsejos=false;E.consejos=[];E.errorConsejos='x'}"],
  ["importar", "E=>{E.importar={paso:'elegir',ia:true}}"],
  ["importar-leyendo", "E=>{E.importar={paso:'leyendo',nombre:'cartola.csv',ia:true}}"],
  ["importar-vista", "E=>{E.importar={paso:'vista',ia:true,vista:{total:41,desde:'2026-10-01',hasta:'2026-10-17',avisos:['x'],receta:{id:'cl-x',nombre:'Banco Ejemplo',institucion:'Banco Ejemplo'},muestra:E.movimientos.slice(0,5)}}}"],
  ["importar-sin-receta", "E=>{E.importar={paso:'sin_receta',nombre:'cartola.xlsx',ia:true,error:'x'}}"],
  ["importar-aprendiendo", "E=>{E.importar.paso='aprendiendo'}"],
  ["importar-receta", "E=>{E.importar={paso:'receta',ia:true,compartir:false,receta:{id:'cl-x'},vista:{total:12,muestra:E.movimientos.slice(0,4)}}}"],
  ["importar-guardando", "E=>{E.importar={paso:'guardando',progreso:{paso:2,total:3,texto:'Guardando sin duplicar…'}}}"],
  ["importar-listo", "E=>{E.importar={paso:'listo',resultado:{nuevos:12,repetidos:29,sin_categoria:2,error_ia:'x'}}}"],
  ["importar-listo-uno", "E=>{E.importar={paso:'listo',resultado:{nuevos:1,repetidos:0,sin_categoria:0}}}"],
  ["importar-error", "E=>{E.importar={paso:'error',error:'x'}}"],
  ["ajustes", "E=>{E.importar=null;E.ajustes=true}"],
  ["ajustes-al-dia", "E=>{E.buscando='alDia'}"],
  ["actualizacion", "E=>{E.ajustes=false;E.vista='resumen';E.actualizacion={hay:true,detalle:'Versión 0.2.0'}}"],
  ["actualizando", "E=>{E.act={paso:'2',texto:'Preparando la versión nueva…',pct:40}}"],
  ["actualizacion-error", "E=>{E.act={paso:'error',texto:'x'}}"],
  ["sin-presupuesto", "E=>{E.act=null;E.actualizacion={hay:false};E.presupuesto={moneda:'CLP',mensual:{}}}"],
  ["vacio", "E=>{E.movimientos=[]}"],
];
const navegador = await chromium.launch();

// Lógica compartida con Python (pruebas/casos.json).
{
  const p = await navegador.newPage();
  await p.goto(BASE); await p.waitForFunction(() => window.Alcancia);
  const r = await p.evaluate((c) => {
    const P = window.Alcancia._pruebas, malos = [];
    for (const [v, e] of c.redondear) if (P.redondearArriba(v) !== e) malos.push(`redondear(${v}) = ${P.redondearArriba(v)}`);
    for (const [d, e] of c.regla) if (P.reglaPara(d) !== e) malos.push(`reglaPara(${d}) = ${P.reglaPara(d)}`);
    for (const k of c.resumen) {
      const r = P.resumen(k.movimientos, k.mes, k.hoy, k.presupuesto, c.categorias);
      for (const [campo, esperado] of Object.entries(k.esperado)) if (JSON.stringify(r[campo]) !== JSON.stringify(esperado)) malos.push(`${k.nombre}: ${campo} = ${JSON.stringify(r[campo])}`);
    }
    return malos;
  }, casos);
  r.forEach((m) => falla("lógica distinta a Python: " + m));
  if (!r.length) console.log("  ✓ Misma lógica que Python (pruebas/casos.json)");
  await p.close();
}

for (const [idioma, consulta] of [["español", "idioma=es"], ["inglés", "idioma=en"]]) {
  for (const [modo, opciones] of [["escritorio", { viewport: { width: 1200, height: 820 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "dark" }]]) {
    for (const bv of [false, true]) {
      const p = await navegador.newPage(opciones);
      p.on("pageerror", (e) => falla(`error de JavaScript (${idioma}, ${modo}): ${e.message}`));
      await p.addInitScript(() => { window._faltantes = new Set(); });
      await p.goto(BASE + "?" + [consulta, bv ? "bienvenida" : ""].filter(Boolean).join("&"));
      await p.waitForFunction(() => window.Alcancia && document.querySelector(".app"));
      const pasos = bv ? [0, 1, 2, 3, 4].map((n) => [`bienvenida-${n}`, `E=>{E.bv=${n}}`]) : VISTAS;
      for (const [nombre, f] of pasos) {
        await p.evaluate(`window.Alcancia._probar(${f})`);
        await p.waitForTimeout(60);
        if (modo === "celular") {
          const ancho = await p.evaluate(() => document.documentElement.scrollWidth);
          if (ancho > 392) falla(`se sale de la pantalla a ancho de celular (${ancho}px) en «${nombre}» (${idioma})`);
        }
        if (CAPTURAS && (idioma === "español" || modo === "escritorio")) await p.screenshot({ path: path.join(CAPTURAS, `${idioma}-${modo}-${nombre}.png`) });
      }
      if (idioma === "inglés") {
        const faltan = [...new Set(await p.evaluate(() => [...window._faltantes]))].filter((t) => !esDato(t));
        if (faltan.length) falla(`${faltan.length} textos sin traducción en ui/idiomas/en.json:\n      ` + faltan.map((t) => JSON.stringify(t)).join("\n      "));
      }
      await p.close();
    }
  }
  console.log(`  ✓ Vistas en ${idioma}`);
}

// Contraste del botón principal en modo claro y oscuro (WCAG AA: 4.5).
for (const esquema of ["light", "dark"]) {
  const p = await navegador.newPage({ colorScheme: esquema });
  await p.goto(BASE); await p.waitForSelector(".boton.principal");
  const c = await p.evaluate(() => {
    const lum = (s) => { const [r, g, b] = s.match(/[\d.]+/g).slice(0, 3).map((x) => { x = x / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const cs = getComputedStyle(document.querySelector(".boton.principal")); const a = lum(cs.color), b = lum(cs.backgroundColor);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  });
  if (c < 4.5) falla(`contraste del botón principal en modo ${esquema}: ${c.toFixed(2)} (mínimo 4.5)`);
  else console.log(`  ✓ Contraste en modo ${esquema === "light" ? "claro" : "oscuro"}: ${c.toFixed(2)}`);
  await p.close();
}

await navegador.close();
servidor.close();
if (errores.length) { console.log(`\n✗ ${errores.length} problemas`); process.exit(1); }
console.log("✓ Interfaz OK");
