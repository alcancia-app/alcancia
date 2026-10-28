// Arma la carpeta web de la app del celular (www/) sin copiar nada a mano: la misma interfaz de ui/ y el anfitrión del teléfono
// (host/). Después: npx cap sync. Uso: node armar.mjs [--salida carpeta]
// - index.html carga host/arranque.js antes que la interfaz y host/host.js después; viewport-fit=cover (notch). La CSP no cambia.
// - Sin la vista previa (demo.json): en el teléfono los datos son los que llegan cifrados desde el Mac.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url)), RAIZ = path.resolve(AQUI, "..");
const i = process.argv.indexOf("--salida");
const SALIDA = path.resolve(i > 0 ? process.argv[i + 1] : path.join(AQUI, "www"));
const version = JSON.parse(fs.readFileSync(path.join(AQUI, "package.json"), "utf8")).version;

fs.rmSync(SALIDA, { recursive: true, force: true });
fs.mkdirSync(SALIDA, { recursive: true });
fs.cpSync(path.join(RAIZ, "ui"), SALIDA, { recursive: true, filter: (f) => path.relative(path.join(RAIZ, "ui"), f) !== "demo.json" });
fs.cpSync(path.join(AQUI, "host"), path.join(SALIDA, "host"), { recursive: true });
fs.writeFileSync(path.join(SALIDA, "host", "arranque.js"), fs.readFileSync(path.join(AQUI, "host", "arranque.js"), "utf8").replace("__VERSION__", version));

let html = fs.readFileSync(path.join(SALIDA, "index.html"), "utf8");
const cambios = [
  ['<script src="copia.js"></script>', '<script src="host/arranque.js"></script>\n  <script src="copia.js"></script>'],
  ['<script src="app.js"></script>', '<script src="app.js"></script>\n  <script src="host/host.js"></script>'],
];
for (const [a, b] of cambios) {
  if (!html.includes(a)) throw new Error("ui/index.html cambió: no encuentro " + a);
  html = html.replace(a, b);
}
if (!html.includes("script-src 'self'")) throw new Error("ui/index.html: la Content-Security-Policy tiene que seguir con script-src 'self'.");
fs.writeFileSync(path.join(SALIDA, "index.html"), html);
console.log(`✓ ${path.relative(process.cwd(), SALIDA) || "."}: ui + host (versión ${version})`);
