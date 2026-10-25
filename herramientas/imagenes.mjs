// Genera las imágenes de la página (docs/img y docs/) con la interfaz y datos ficticios de ui/demo.json.
// Uso: PLAYWRIGHT=/ruta/a/playwright node herramientas/imagenes.mjs
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const tipos = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png" };
const servidor = http.createServer((q, r) => {
  const ruta = path.join(RAIZ, decodeURIComponent(new URL(q.url, "http://x").pathname));
  if (!ruta.startsWith(RAIZ) || !fs.existsSync(ruta) || fs.statSync(ruta).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "Content-Type": tipos[path.extname(ruta)] || "application/octet-stream" });
  fs.createReadStream(ruta).pipe(r);
}).listen(0);
const URL_BASE = `http://localhost:${servidor.address().port}`;
const IMG = path.join(RAIZ, "docs", "img");
fs.mkdirSync(IMG, { recursive: true });
const navegador = await chromium.launch();

for (const [esquema, nombre] of [["light", "claro"], ["dark", "oscuro"]]) {
  const p = await navegador.newPage({ viewport: { width: 1280, height: 820 }, colorScheme: esquema, deviceScaleFactor: 1 });
  await p.goto(`${URL_BASE}/ui/index.html?idioma=es`);
  await p.waitForSelector(".heroe");
  await p.waitForTimeout(300);
  await p.screenshot({ path: path.join(IMG, `app-resumen-${nombre}.png`) });
  await p.close();
}

const svg = fs.readFileSync(path.join(RAIZ, "ui", "favicon.svg"), "utf8");
for (const [lado, destino] of [[512, path.join(IMG, "logo.png")], [180, path.join(RAIZ, "docs", "apple-touch-icon.png")]]) {
  const p = await navegador.newPage({ viewport: { width: lado, height: lado } });
  await p.setContent(`<style>html,body{margin:0;background:#2b1d16}svg{width:${lado}px;height:${lado}px;display:block}</style>${svg.replace('rx="15"', 'rx="0"')}`);
  await p.screenshot({ path: destino });
  await p.close();
}

// Imagen para compartir (1200×630): nombre, frase y una captura con datos ficticios.
const captura = fs.readFileSync(path.join(IMG, "app-resumen-claro.png")).toString("base64");
const p = await navegador.newPage({ viewport: { width: 1200, height: 630 } });
await p.setContent(`<style>
  body{margin:0;width:1200px;height:630px;background:radial-gradient(60% 80% at 85% 10%,#5a2a14 0%,transparent 60%),#15100c;color:#f6eee7;font-family:-apple-system,"Segoe UI",system-ui,sans-serif;overflow:hidden;position:relative}
  .txt{position:absolute;left:64px;top:70px;width:470px}
  .marca{display:flex;align-items:center;gap:14px;font-size:34px;font-weight:800}
  .marca svg{width:58px;height:58px}
  h1{font-size:50px;line-height:1.04;margin:36px 0 18px;letter-spacing:-.02em}
  h1 em{font-style:normal;color:#f2b632}
  p{font-size:22px;color:#b6a79a;margin:0;line-height:1.4}
  .chips{margin-top:28px;display:flex;gap:10px;flex-wrap:wrap}
  .chips span{font-size:16px;padding:7px 14px;border-radius:99px;border:1px solid #3a2e24;color:#f6eee7}
  img{position:absolute;left:580px;top:60px;width:760px;border-radius:18px;box-shadow:0 30px 90px rgba(0,0,0,.7);border:1px solid #3a2e24}
</style>
<div class="txt"><div class="marca">${svg}<span>Alcancía</span></div>
<h1>Control de gastos para quienes nos cuesta <em>medirnos</em></h1>
<p>Cualquier banco del mundo. Tu propia IA. Tus datos en tu computador.</p>
<div class="chips"><span>Gratis</span><span>Código abierto</span><span>Sin clave del banco</span></div></div>
<img src="data:image/png;base64,${captura}">`);
await p.screenshot({ path: path.join(IMG, "compartir.png") });
await navegador.close();
servidor.close();
console.log("✓ Imágenes en docs/img y docs/apple-touch-icon.png");
