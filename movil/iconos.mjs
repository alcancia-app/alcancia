// Íconos y pantallas de carga de la app del celular a partir del logo (ui/favicon.svg), para no mostrar los de Capacitor, y el
// ícono chico de los avisos en Android (la silueta del chanchito en blanco, como pide el sistema).
// Uso (solo cuando cambia el logo): PLAYWRIGHT=/ruta/a/playwright node movil/iconos.mjs
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const logo = fs.readFileSync(path.join(AQUI, "..", "ui", "favicon.svg"), "utf8");
const dibujo = logo.replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "").replace(/<rect[^>]*\/>/, ""); // el chanchito, sin el fondo
const silueta = dibujo.replace(/fill="#[0-9a-f]{6}"/gi, 'fill="#fff"').replace(/stroke="#[0-9a-f]{6}"/gi, 'stroke="#fff"')
  .replace(/<rect x="23"[^>]*\/>|<circle cx="(49\.6|41\.5)"[^>]*\/>|<rect x="27\.5"[^>]*\/>/g, ""); // sin ojo, nariz ni ranura
const FONDO = "#2b1d16", PAPEL = "#f5f4f2";
const svg = (contenido, fondo = "") => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="100%" height="100%">${fondo}${contenido}</svg>`;

const navegador = await chromium.launch();
const pagina = await navegador.newPage();
async function png(destino, ancho, alto, html, transparente = false) {
  fs.mkdirSync(path.dirname(path.join(AQUI, destino)), { recursive: true });
  await pagina.setViewportSize({ width: ancho, height: alto });
  await pagina.setContent(`<html><body style="margin:0;width:${ancho}px;height:${alto}px;overflow:hidden;background:${transparente ? "transparent" : PAPEL}">${html}</body></html>`);
  await pagina.screenshot({ path: path.join(AQUI, destino), omitBackground: transparente });
}
const centrado = (lado, ancho, alto, contenido) => `<div style="position:absolute;left:${(ancho - lado) / 2}px;top:${(alto - lado) / 2}px;width:${lado}px;height:${lado}px">${contenido}</div>`;

// iOS: un cuadrado sin esquinas (el sistema las redondea) y la pantalla de carga.
await png("ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png", 1024, 1024, svg(dibujo, `<rect width="64" height="64" fill="${FONDO}"/>`));
for (const n of ["splash-2732x2732.png", "splash-2732x2732-1.png", "splash-2732x2732-2.png"])
  await png(`ios/App/App/Assets.xcassets/Splash.imageset/${n}`, 2732, 2732, centrado(420, 2732, 2732, logo));

// Android: ícono adaptable (dibujo en la zona segura de 66/108) + ícono clásico y redondo, pantallas de carga y el ícono de los avisos.
const DENSIDADES = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 };
for (const [d, f] of Object.entries(DENSIDADES)) {
  const lado = Math.round(108 * f), base = Math.round(48 * f), aviso = Math.round(24 * f);
  await png(`android/app/src/main/res/mipmap-${d}/ic_launcher_foreground.png`, lado, lado, centrado(Math.round(lado * 0.62), lado, lado, svg(dibujo)), true);
  await png(`android/app/src/main/res/mipmap-${d}/ic_launcher.png`, base, base, logo.replace("<svg ", '<svg width="100%" height="100%" '), true);
  await png(`android/app/src/main/res/mipmap-${d}/ic_launcher_round.png`, base, base, svg(dibujo, `<circle cx="32" cy="32" r="32" fill="${FONDO}"/>`), true);
  await png(`android/app/src/main/res/drawable-${d}/ic_stat_alcancia.png`, aviso, aviso, svg(silueta), true);
}
const PANTALLAS = { "drawable/splash.png": [480, 320], ...Object.fromEntries(Object.entries({ mdpi: [320, 480], hdpi: [480, 800], xhdpi: [720, 1280], xxhdpi: [960, 1600], xxxhdpi: [1280, 1920] })
  .flatMap(([d, [a, b]]) => [[`drawable-port-${d}/splash.png`, [a, b]], [`drawable-land-${d}/splash.png`, [b, a]]])) };
for (const [ruta, [a, b]] of Object.entries(PANTALLAS)) await png(`android/app/src/main/res/${ruta}`, a, b, centrado(Math.round(Math.min(a, b) * 0.28), a, b, logo));
fs.writeFileSync(path.join(AQUI, "android/app/src/main/res/values/ic_launcher_background.xml"),
  `<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">${FONDO.toUpperCase()}</color>\n</resources>\n`);
await navegador.close();
console.log("✓ Íconos, pantallas de carga e ícono de los avisos");
