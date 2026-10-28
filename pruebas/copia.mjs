// Pruebas de la «copia para el celular» (ui/copia.js) en Node, sin navegador: el mismo archivo que corre en el Mac y en el teléfono.
// Uso: node pruebas/copia.mjs
// Revisa: el Mac cifra y el teléfono abre (con la frase o con la llave recordada); que el formato sea AES-256-GCM + PBKDF2 estándar
// (se abre con node:crypto, otra implementación); frase incorrecta; archivo dañado, cortado, de otra versión o que no es una copia;
// cabecera con menos vueltas; IV distinto en cada escritura; lo que viaja (sin llaves, rutas del Mac, IA ni chat); la frase.
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
vm.runInThisContext(fs.readFileSync(path.join(RAIZ, "ui", "copia.js"), "utf8"), { filename: "ui/copia.js" });
const C = globalThis.AlcanciaCopia;
const demo = JSON.parse(fs.readFileSync(path.join(RAIZ, "ui", "demo.json"), "utf8"));
const errores = [];
const falla = (m) => { errores.push(m); console.log("  ✗ " + m); };
async function paso(nombre, f) {
  const antes = errores.length;
  try { await f(); } catch (e) { falla(`${nombre}: ${e.stack || e.message}`); }
  if (errores.length === antes) console.log("  ✓ " + nombre);
}
async function lanza(f, codigo, que) {
  try { await f(); } catch (e) {
    if (e.codigo !== codigo) falla(`${que}: esperaba «${codigo}» y fue «${e.codigo || e.message}»`);
    return e;
  }
  falla(`${que}: esperaba un error «${codigo}»`);
}
const FRASE = "caballo pila grapa correcta";
const RUTA_MAC = (...partes) => ["", "Users", "ana", ...partes].join("/"); // una ruta de un Mac ficticio (armada así para no parecer una real)
// Un estado como el que arma el Mac (bin/estado.py + lo de la app), con cosas que nunca deben llegar al teléfono.
const ESTADO_MAC = {
  ...demo, carpeta: "~/Alcancia", version: "0.1.0",
  config: { ...demo.config, ia: "claude", vigilar: true, respaldo: "local", avisos: true, idioma_ui: "es" },
  vigilar: { activo: true, recientes: [{ archivo: RUTA_MAC("Downloads", "cartola-octubre.csv"), resultado: "importado" }] },
  ia_externa: [{ id: "claude-desktop", ruta: RUTA_MAC("Library", "Application Support", "Claude", "claude_desktop_config.json") }],
  conexiones: { mercadopago: { conectado: true, ultima: "2026-10-18T12:40:00+00:00", error: "", nuevos: 3, esperando: false, memoria: { token: "APP_USR-secreto" } } },
  chat: [{ id: "m-1", rol: "persona", texto: "mi rut es " + ["11", "111", "111-1"].join(".") }],
  celular: { activo: true, nombre: "Alcancía", nube: "iCloud Drive" }, credencial: { access_token: "secreto" },
  cuentas: demo.cuentas.map((c) => ({ ...c, numero: "000123456789", receta: "cl-banco-ejemplo" })),
};

await paso("El Mac cifra y el teléfono abre con la frase (y después con la llave recordada)", async () => {
  const { cabecera, llave, raw } = await C.nuevaCabecera(FRASE);
  const contenido = C.paraCelular(ESTADO_MAC, { generado: "2026-10-18T12:00:00.000Z", version: "0.1.0" });
  const texto = await C.armar(contenido, cabecera, llave);
  const a = JSON.parse(texto);
  if (a.alcancia !== "copia-celular" || a.version !== 1 || a.kdf.iteraciones !== 600000 || a.kdf.alg !== "PBKDF2-SHA256" || a.cifrado !== "AES-256-GCM") falla("cabecera: " + texto.slice(0, 200));
  if (C._interno.deBase64(a.kdf.sal).length !== 16 || C._interno.deBase64(a.datos.iv).length !== 12) falla("sal o IV de largo incorrecto");
  if (texto.includes("ARRIENDO") || texto.includes("Banco Ejemplo")) falla("el archivo trae texto sin cifrar");
  const abierto = await C.abrir(texto, { frase: FRASE });
  if (JSON.stringify(abierto.contenido) !== JSON.stringify(contenido)) falla("lo que abre el teléfono no es lo que cifró el Mac");
  if (abierto.raw !== raw) falla("la llave derivada en el teléfono no es la del Mac");
  if (C.salDe(texto) !== a.kdf.sal) falla("salDe");
  const conLlave = await C.abrir(texto, { raw });
  if (conLlave.contenido.estado.movimientos.length !== demo.movimientos.length) falla("con la llave recordada no abre todo");
  // La frase se normaliza: «canción» compuesta o descompuesta es la misma.
  const tilde = "canción del mar en la noche";
  const k = await C.nuevaCabecera(tilde);
  const t2 = await C.armar({ formato: 1, estado: {} }, k.cabecera, k.llave);
  await C.abrir(t2, { frase: tilde.normalize("NFD") });
});

await paso("Formato estándar: otra implementación (node:crypto) lo abre", async () => {
  const { cabecera, llave } = await C.nuevaCabecera(FRASE);
  const contenido = C.paraCelular(ESTADO_MAC, { generado: "2026-10-18T12:00:00.000Z" });
  const a = JSON.parse(await C.armar(contenido, cabecera, llave));
  const clave = crypto.pbkdf2Sync(Buffer.from(FRASE.normalize("NFC"), "utf8"), Buffer.from(a.kdf.sal, "base64"), a.kdf.iteraciones, 32, "sha256");
  const abrirCon = (sobre, aad) => {
    const d = Buffer.from(sobre.datos, "base64");
    const x = crypto.createDecipheriv("aes-256-gcm", clave, Buffer.from(sobre.iv, "base64"));
    x.setAAD(Buffer.from(aad, "utf8"));
    x.setAuthTag(d.subarray(d.length - 16));
    return Buffer.concat([x.update(d.subarray(0, d.length - 16)), x.final()]).toString("utf8");
  };
  if (abrirCon(a.verificador, "alcancia:celular:verificador") !== "alcancia") falla("el verificador no es «alcancia»");
  if (abrirCon(a.datos, "alcancia:celular:1") !== JSON.stringify(contenido)) falla("node:crypto no abre los datos igual");
  // Y al revés: un archivo armado con node:crypto (vector fijo) lo abre el teléfono.
  const sal = Buffer.alloc(16, 7), iv = Buffer.alloc(12, 9);
  const k2 = crypto.pbkdf2Sync("frase de prueba larga", sal, 100000, 32, "sha256");
  const sellar = (texto, aad, ivx) => { const c = crypto.createCipheriv("aes-256-gcm", k2, ivx); c.setAAD(Buffer.from(aad)); const d = Buffer.concat([c.update(texto, "utf8"), c.final(), c.getAuthTag()]); return { iv: ivx.toString("base64"), datos: d.toString("base64") }; };
  const vector = JSON.stringify({ alcancia: "copia-celular", version: 1, kdf: { alg: "PBKDF2-SHA256", iteraciones: 100000, sal: sal.toString("base64") }, cifrado: "AES-256-GCM",
    verificador: sellar("alcancia", "alcancia:celular:verificador", Buffer.alloc(12, 3)), datos: sellar(JSON.stringify({ formato: 1, estado: { movimientos: [] } }), "alcancia:celular:1", iv) });
  if (sellar("alcancia", "alcancia:celular:verificador", Buffer.alloc(12, 3)).datos !== "1TAjC7CzOsxwVoQjTB+qJi9jKXsCl/Jz") falla("el vector fijo cambió: " + sellar("alcancia", "alcancia:celular:verificador", Buffer.alloc(12, 3)).datos);
  const r = await C.abrir(vector, { frase: "frase de prueba larga" });
  if (!Array.isArray(r.contenido.estado.movimientos)) falla("el vector fijo no abre");
});

await paso("Frase incorrecta, archivo dañado o cortado, otra versión y lo que no es una copia", async () => {
  const { cabecera, llave } = await C.nuevaCabecera(FRASE);
  const texto = await C.armar(C.paraCelular(ESTADO_MAC), cabecera, llave);
  await lanza(() => C.abrir(texto, { frase: "caballo pila grapa correcto" }), "frase", "frase incorrecta");
  await lanza(() => C.abrir(texto, { frase: "" }), "frase", "frase vacía");
  const otra = await C.nuevaCabecera("otra frase cualquiera larga");
  await lanza(() => C.abrir(texto, { raw: otra.raw }), "frase", "llave recordada de otra frase");
  const a = JSON.parse(texto);
  const bytes = C._interno.deBase64(a.datos.datos);
  bytes[40] ^= 1;
  await lanza(() => C.abrir(JSON.stringify({ ...a, datos: { ...a.datos, datos: C._interno.aBase64(bytes) } }), { frase: FRASE }), "danado", "un bit cambiado");
  await lanza(() => C.abrir(texto.slice(0, Math.floor(texto.length * 0.7)), { frase: FRASE }), "danado", "archivo cortado a medio subir");
  await lanza(() => C.abrir(JSON.stringify({ ...a, datos: { ...a.datos, iv: "AAAA" } }), { frase: FRASE }), "danado", "IV inválido");
  await lanza(() => C.abrir(JSON.stringify({ ...a, datos: { ...a.datos, datos: "no-es-base64!" } }), { frase: FRASE }), "danado", "datos que no son base64");
  // Los datos de otra copia (otra versión del formato en el AAD) no se abren aunque la llave sea la misma.
  const sobre = await C._interno.cifrar(llave, new TextEncoder().encode(JSON.stringify({ formato: 1, estado: {} })), "alcancia:celular:2");
  await lanza(() => C.abrir(JSON.stringify({ ...a, datos: sobre }), { frase: FRASE }), "danado", "datos atados a otra versión");
  await lanza(() => C.abrir(JSON.stringify({ ...a, version: 2 }), { frase: FRASE }), "version", "versión futura");
  await lanza(() => C.abrir(JSON.stringify({ ...a, version: 0 }), { frase: FRASE }), "danado", "versión 0");
  await lanza(() => C.abrir(JSON.stringify({ ...a, kdf: { ...a.kdf, iteraciones: 1000 } }), { frase: FRASE }), "danado", "menos vueltas (bajar la seguridad)");
  await lanza(() => C.abrir(JSON.stringify({ ...a, kdf: { ...a.kdf, alg: "MD5" } }), { frase: FRASE }), "danado", "otro algoritmo");
  await lanza(() => C.abrir("hola", { frase: FRASE }), "no_es", "texto cualquiera");
  await lanza(() => C.abrir(JSON.stringify({ alcancia: "otra-cosa" }), { frase: FRASE }), "no_es", "otro JSON");
  await lanza(() => C.abrir(fs.readFileSync(path.join(RAIZ, "ui", "demo.json"), "utf8"), { frase: FRASE }), "no_es", "demo.json");
  if (C.MENSAJES.version.includes("undefined")) falla("mensaje");
});

await paso("Cada escritura lleva su propio IV; la huella no cambia si no cambió nada", async () => {
  const { cabecera, llave } = await C.nuevaCabecera(FRASE);
  const c1 = C.paraCelular(ESTADO_MAC, { generado: "2026-10-18T12:00:00.000Z" }), c2 = C.paraCelular(ESTADO_MAC, { generado: "2026-10-18T18:00:00.000Z" });
  const [t1, t2] = [await C.armar(c1, cabecera, llave), await C.armar(c1, cabecera, llave)];
  if (JSON.parse(t1).datos.iv === JSON.parse(t2).datos.iv) falla("dos escrituras con el mismo IV");
  if (await C.huella(c1) !== await C.huella(c2)) falla("la hora cambia la huella");
  const c3 = C.paraCelular({ ...ESTADO_MAC, movimientos: ESTADO_MAC.movimientos.slice(1) });
  if (await C.huella(c1) === await C.huella(c3)) falla("la huella no ve un movimiento menos");
  if (!/^[0-9a-f]{64}$/.test(await C.huella(c1))) falla("huella");
});

await paso("Lo que viaja: lo que pinta la interfaz, nunca llaves, rutas del Mac, IA, chat ni números de cuenta", async () => {
  const c = C.paraCelular(ESTADO_MAC, { generado: "2026-10-18T12:00:00.000Z", version: "0.1.0" });
  const json = JSON.stringify(c);
  for (const prohibido of ["/Users/", "~/", "secreto", "APP_USR", "token", "claude_desktop", "rut es", "000123456789", "vigilar", "ia_externa", "\"chat\"", "\"celular\"", "\"carpeta\"", "respaldo", "cl-banco-ejemplo\"" ]) {
    if (json.includes(prohibido)) falla(`viaja «${prohibido}»`);
  }
  const e = c.estado;
  if (Object.keys(e.config).sort().join() !== "inicio_mes,moneda,pais") falla("config: " + JSON.stringify(e.config));
  if (e.movimientos.length !== demo.movimientos.length || e.movimientos[0].descripcion !== demo.movimientos[0].descripcion) falla("movimientos");
  if (e.compromisos.compromisos.length !== demo.compromisos.compromisos.length) falla("compromisos");
  if (e.conexiones.mercadopago.nombre !== "Mercado Pago" || e.conexiones.mercadopago.memoria) falla("conexiones: " + JSON.stringify(e.conexiones));
  if (!e.feriados.length || !e.palabras_automatico.length || !e.categorias.length || !e.cuentas[0].saldo) falla("faltan datos para pintar");
  if (c.formato !== 1 || c.hoy !== demo.hoy || c.version !== "0.1.0") falla("encabezado del contenido");
  if (Object.keys(e).some((k) => !["config", "movimientos", "categorias", "presupuesto", "cuentas", "consejos", "compromisos", "conexiones", "feriados", "palabras_mora", "palabras_automatico"].includes(k))) falla("claves de más: " + Object.keys(e));
});

await paso("La frase: al menos 12 caracteres, y cuánto cuesta adivinarla", async () => {
  if (!C.revisarFrase("corta")) falla("acepta una frase corta");
  if (C.revisarFrase(FRASE)) falla("rechaza una buena frase");
  await lanza(() => C.nuevaCabecera("corta"), "frase", "nuevaCabecera con frase corta");
  const n = (f) => C.fuerzaFrase(f).nivel;
  if (n("abc") !== 0) falla("«abc» no es muy corta");
  if (n("aaaaaaaaaaaa") !== 1) falla("«aaaaaaaaaaaa» debería ser solo aceptable: " + JSON.stringify(C.fuerzaFrase("aaaaaaaaaaaa")));
  if (n("perro gato casa") >= 3) falla("tres palabras no es muy buena");
  if (n(FRASE) < 2) falla("cuatro palabras debería ser al menos buena: " + JSON.stringify(C.fuerzaFrase(FRASE)));
  if (n("el kiltro Firulais come 3 sopaipillas!") !== 3) falla("una frase larga y variada debería ser muy buena");
});

console.log(errores.length ? `✗ Copia para el celular: ${errores.length} problemas` : "✓ Copia para el celular OK");
process.exit(errores.length ? 1 : 0);
