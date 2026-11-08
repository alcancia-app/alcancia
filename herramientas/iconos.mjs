// Íconos de la app de escritorio (escritorio/iconos/) a partir del logo (ui/favicon.svg): icon.icns para el Mac (el de
// siempre está en git; este lo vuelve a armar con su cuadrícula: el dibujo ocupa 824 de 1024 px, centrado), icon.ico para Windows y los PNG que pide Tauri. El
// .icns y el .ico se arman aquí mismo (PNG por tamaño), sin herramientas de Apple ni de Microsoft.
// Uso (solo cuando cambia el logo): PLAYWRIGHT=/ruta/a/playwright node herramientas/iconos.mjs
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const logo = fs.readFileSync(path.join(RAIZ, "ui", "favicon.svg"), "utf8").replace("<svg ", '<svg width="100%" height="100%" ');

const navegador = await chromium.launch();
const pagina = await navegador.newPage();
async function png(lado, mac = true) {
  const dibujo = mac ? Math.round(lado * 824 / 1024) : lado, margen = (lado - dibujo) / 2;
  await pagina.setViewportSize({ width: lado, height: lado });
  await pagina.setContent(`<html><body style="margin:0;width:${lado}px;height:${lado}px;overflow:hidden;background:transparent">
    <div style="position:absolute;left:${margen}px;top:${margen}px;width:${dibujo}px;height:${dibujo}px">${logo}</div></body></html>`);
  return pagina.screenshot({ omitBackground: true });
}
// Tipos del formato ICNS (cada uno guarda un PNG): 16, 32, 64, 128, 256, 512 y 1024 px (los @2x reusan los tamaños).
const TIPOS = [["icp4", 16], ["icp5", 32], ["ic11", 32], ["icp6", 64], ["ic12", 64], ["ic07", 128], ["ic13", 256], ["ic08", 256], ["ic14", 512], ["ic09", 512], ["ic10", 1024]];
const hechos = {};
const partes = [];
for (const [tipo, lado] of TIPOS) {
  hechos[lado] ??= await png(lado);
  const cabeza = Buffer.alloc(8);
  cabeza.write(tipo, 0, "ascii");
  cabeza.writeUInt32BE(hechos[lado].length + 8, 4);
  partes.push(cabeza, hechos[lado]);
}
const cuerpo = Buffer.concat(partes), cabeza = Buffer.alloc(8);
cabeza.write("icns", 0, "ascii");
cabeza.writeUInt32BE(cuerpo.length + 8, 4);
const DIR = path.join(RAIZ, "escritorio", "iconos");
fs.mkdirSync(DIR, { recursive: true });
fs.writeFileSync(path.join(DIR, "icon.icns"), Buffer.concat([cabeza, cuerpo]));
// Windows y Linux: el logo entero, sin el margen del Mac.
const planos = {};
for (const lado of [16, 24, 32, 48, 64, 128, 256, 512]) planos[lado] = await png(lado, false);
for (const [lado, nombre] of [[32, "32x32.png"], [128, "128x128.png"], [256, "128x128@2x.png"], [512, "icono.png"]]) fs.writeFileSync(path.join(DIR, nombre), planos[lado]);
// ICO con PNG adentro (Windows Vista en adelante): cabecera, una entrada de 16 bytes por tamaño y los PNG.
const ladosIco = [16, 24, 32, 48, 64, 128, 256];
const ico = [Buffer.from([0, 0, 1, 0, ladosIco.length, 0])];
let lugar = 6 + 16 * ladosIco.length;
for (const lado of ladosIco) {
  const e = Buffer.alloc(16);
  e.writeUInt8(lado % 256, 0); e.writeUInt8(lado % 256, 1); e.writeUInt16LE(1, 4); e.writeUInt16LE(32, 6);
  e.writeUInt32LE(planos[lado].length, 8); e.writeUInt32LE(lugar, 12);
  ico.push(e); lugar += planos[lado].length;
}
fs.writeFileSync(path.join(DIR, "icon.ico"), Buffer.concat([...ico, ...ladosIco.map((l) => planos[l])]));
await navegador.close();
console.log(`✓ escritorio/iconos/ (icon.icns con ${TIPOS.length} tamaños, icon.ico y PNG)`);
