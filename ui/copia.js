// «Copia para el celular»: lo que el Mac deja en la nube de la persona para que el teléfono la muestre. El mismo código cifra en el
// Mac (dentro de la interfaz, con WebCrypto) y descifra en el teléfono; las pruebas lo cargan igual en Node (pruebas/copia.mjs).
// Sin dependencias. Formato documentado en el README («Copia para el celular»).
// - La llave sale de una frase que elige la persona: PBKDF2-SHA256, 600.000 vueltas, sal aleatoria de 16 bytes. La frase nunca se
//   guarda: el Mac guarda la llave ya derivada en su Llavero (y el teléfono, solo si la persona lo pide, en su Llavero o Keystore).
// - AES-256-GCM con un IV aleatorio de 12 bytes en cada escritura; los datos adicionales (AAD) atan el contenido a la versión del
//   formato. Un «verificador» cifrado permite decir «la frase no es la correcta» antes de tocar los datos.
// - El contenido es una lista blanca de lo que la interfaz necesita para pintar (paraCelular): nunca llaves de conectores, tokens,
//   rutas del Mac, la conversación con la IA ni lo que solo sirve para cambiar cosas.
(() => {
  "use strict";
  const FORMATO = 1, TIPO = "copia-celular", ARCHIVO = "Alcancia-celular.alcancia";
  const ITERACIONES = 600000, MIN_ITERACIONES = 100000, MAX_ITERACIONES = 10000000;
  const AAD_DATOS = "alcancia:celular:" + FORMATO, AAD_VERIFICADOR = "alcancia:celular:verificador", VERIFICADOR = "alcancia";
  const MAXIMO = 100 * 1024 * 1024; // un archivo más grande que esto no es una copia de Alcancía
  const MENSAJES = {
    frase: "La frase no es la correcta.",
    danado: "La copia está dañada o se está copiando todavía. Prueba en un rato.",
    version: "Esta copia viene de una versión más nueva de Alcancía. Actualiza la app del celular.",
    no_es: "Ese archivo no es la copia de Alcancía para el celular.",
    sin_cifrado: "Este equipo no puede cifrar la copia.",
  };
  class ErrorCopia extends Error {
    constructor(codigo) { super(MENSAJES[codigo] || MENSAJES.danado); this.codigo = codigo; }
  }

  const subtle = () => {
    const s = globalThis.crypto && globalThis.crypto.subtle;
    if (!s) throw new ErrorCopia("sin_cifrado");
    return s;
  };
  const utf8 = new TextEncoder();
  const aTexto = (b) => new TextDecoder("utf-8", { fatal: true }).decode(b);
  const azar = (n) => globalThis.crypto.getRandomValues(new Uint8Array(n));
  function aBase64(bytes) {
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }
  function deBase64(b64) {
    if (typeof b64 !== "string" || b64.length % 4 || !/^[A-Za-z0-9+/]*={0,2}$/.test(b64)) throw new ErrorCopia("danado");
    let s;
    try { s = atob(b64); } catch { throw new ErrorCopia("danado"); }
    const r = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) r[i] = s.charCodeAt(i);
    return r;
  }

  // ───────────── Llaves ─────────────
  /** La llave (y sus 32 bytes, para guardarla en el Llavero) desde la frase. La frase se normaliza (NFC): «canción» escrita en el
   *  Mac y en el teléfono es la misma. */
  async function derivar(frase, sal, iteraciones = ITERACIONES) {
    if (typeof frase !== "string" || !frase) throw new ErrorCopia("frase");
    if (!Number.isInteger(iteraciones) || iteraciones < MIN_ITERACIONES || iteraciones > MAX_ITERACIONES) throw new ErrorCopia("danado");
    const base = await subtle().importKey("raw", utf8.encode(frase.normalize("NFC")), "PBKDF2", false, ["deriveBits"]);
    const bits = new Uint8Array(await subtle().deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: sal, iterations: iteraciones }, base, 256));
    const llave = await importarBytes(bits);
    const raw = aBase64(bits);
    bits.fill(0);
    return { llave, raw };
  }
  const importarBytes = (bytes) => subtle().importKey("raw", bytes, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
  /** Una llave guardada (32 bytes en base64) lista para usar. */
  async function importarLlave(raw) {
    const b = deBase64(raw);
    if (b.length !== 32) throw new ErrorCopia("frase");
    return importarBytes(b);
  }

  async function cifrar(llave, bytes, aad) {
    const iv = azar(12);
    const datos = new Uint8Array(await subtle().encrypt({ name: "AES-GCM", iv, additionalData: utf8.encode(aad), tagLength: 128 }, llave, bytes));
    return { iv: aBase64(iv), datos: aBase64(datos) };
  }
  async function descifrar(llave, sobre, aad) {
    if (!sobre || typeof sobre !== "object") throw new ErrorCopia("danado");
    const iv = deBase64(sobre.iv), datos = deBase64(sobre.datos);
    if (iv.length !== 12 || datos.length < 16) throw new ErrorCopia("danado");
    try {
      return new Uint8Array(await subtle().decrypt({ name: "AES-GCM", iv, additionalData: utf8.encode(aad), tagLength: 128 }, llave, datos));
    } catch { throw new ErrorCopia("danado"); }
  }

  /** Cabecera nueva (sal, vueltas y verificador: nada secreto) para una frase, con su llave. Se hace una vez, al elegir la frase. */
  async function nuevaCabecera(frase, iteraciones = ITERACIONES) {
    const problema = revisarFrase(frase);
    if (problema) throw Object.assign(new ErrorCopia("frase"), { message: problema });
    const sal = azar(16);
    const { llave, raw } = await derivar(frase, sal, iteraciones);
    const verificador = await cifrar(llave, utf8.encode(VERIFICADOR), AAD_VERIFICADOR);
    return { cabecera: { kdf: { alg: "PBKDF2-SHA256", iteraciones, sal: aBase64(sal) }, cifrado: "AES-256-GCM", verificador }, llave, raw };
  }
  /** Revisa una cabecera (la del archivo o la que guardó el Mac): lanza ErrorCopia si no sirve. */
  function revisarCabecera(c) {
    const k = c && c.kdf;
    if (!k || k.alg !== "PBKDF2-SHA256" || c.cifrado !== "AES-256-GCM" || !c.verificador) throw new ErrorCopia("danado");
    if (!Number.isInteger(k.iteraciones) || k.iteraciones < MIN_ITERACIONES || k.iteraciones > MAX_ITERACIONES) throw new ErrorCopia("danado");
    if (deBase64(k.sal).length < 16) throw new ErrorCopia("danado");
    return c;
  }
  /** Abre la cabecera con la frase o con una llave ya guardada ({raw}). Devuelve {llave, raw} o lanza ErrorCopia("frase"). */
  async function abrirCabecera(cabecera, { frase = null, raw = null } = {}) {
    revisarCabecera(cabecera);
    const r = raw ? { llave: await importarLlave(raw), raw } : await derivar(frase, deBase64(cabecera.kdf.sal), cabecera.kdf.iteraciones);
    let v;
    try { v = aTexto(await descifrar(r.llave, cabecera.verificador, AAD_VERIFICADOR)); } catch { throw new ErrorCopia("frase"); }
    if (v !== VERIFICADOR) throw new ErrorCopia("frase");
    return r;
  }

  // ───────────── Qué viaja al celular ─────────────
  const CONFIG = ["pais", "moneda", "inicio_mes", "uf"];
  const MOVIMIENTO = ["id", "fecha", "descripcion", "monto", "moneda", "categoria", "cuenta", "origen", "nota", "medio", "cuotas", "cuota"];
  const CUENTA = ["id", "nombre", "moneda", "saldo", "conector"];
  const elegir = (o, claves) => {
    const r = {};
    if (!o || typeof o !== "object") return r;
    for (const k of claves) if (o[k] !== undefined && o[k] !== null) r[k] = o[k];
    return r;
  };
  const lista = (x) => (Array.isArray(x) ? x : []);
  /** Lo que la interfaz necesita para pintar, sacado del estado que arma el Mac (bin/estado.py + lo de la app). Lista blanca:
   *  lo que no está aquí no viaja (llaves, rutas, IA, chat, recetas, carpeta vigilada, sugerencias para agregar…). */
  function paraCelular(estado, { generado = new Date().toISOString(), version = "" } = {}) {
    const e = estado || {};
    const conexiones = {};
    for (const [id, c] of Object.entries(e.conexiones || {})) if (c && typeof c === "object") conexiones[String(id)] = elegir(c, ["conectado", "ultima", "error"]);
    const nombres = Object.fromEntries(lista(e.conectores).map((c) => [c.id, c.nombre]));
    for (const id of Object.keys(conexiones)) if (nombres[id]) conexiones[id].nombre = nombres[id];
    const comp = e.compromisos || {};
    return {
      formato: FORMATO, generado, version: String(version || e.version || ""), hoy: String(e.hoy || ""),
      estado: {
        config: elegir(e.config, CONFIG),
        movimientos: lista(e.movimientos).map((m) => elegir(m, MOVIMIENTO)),
        categorias: lista(e.categorias).map((c) => elegir(c, ["id", "nombre", "emoji", "tipo", "fijo"])),
        presupuesto: elegir(e.presupuesto, ["moneda", "mensual"]),
        cuentas: lista(e.cuentas).map((c) => elegir(c, CUENTA)),
        consejos: lista(e.consejos).map((c) => elegir(c, ["fecha", "texto"])),
        compromisos: { formato: comp.formato || 1, compromisos: lista(comp.compromisos), descartados: [] },
        conexiones,
        feriados: lista(e.feriados), palabras_mora: lista(e.palabras_mora), palabras_automatico: lista(e.palabras_automatico),
      },
    };
  }

  /** Huella del contenido (sin la hora): si no cambió nada, el Mac no vuelve a escribir la copia. */
  async function huella(contenido) {
    const { generado, ...resto } = contenido || {};
    const h = new Uint8Array(await subtle().digest("SHA-256", utf8.encode(JSON.stringify(resto))));
    return [...h].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  // ───────────── El archivo ─────────────
  /** El texto del archivo: cabecera (nada secreto) + el contenido cifrado. */
  async function armar(contenido, cabecera, llave) {
    revisarCabecera(cabecera);
    const datos = await cifrar(llave, utf8.encode(JSON.stringify(contenido)), AAD_DATOS);
    return JSON.stringify({ alcancia: TIPO, version: FORMATO, kdf: cabecera.kdf, cifrado: cabecera.cifrado, verificador: cabecera.verificador, datos });
  }
  /** Lee el archivo sin abrirlo: lanza no_es, version o danado. Devuelve el objeto con su cabecera. */
  function leer(texto) {
    if (typeof texto !== "string" || !texto.trim()) throw new ErrorCopia("no_es");
    if (texto.length > MAXIMO) throw new ErrorCopia("no_es");
    let a;
    try { a = JSON.parse(texto); } catch { throw new ErrorCopia(texto.trimStart().startsWith('{"alcancia":"' + TIPO) ? "danado" : "no_es"); }
    if (!a || typeof a !== "object" || a.alcancia !== TIPO) throw new ErrorCopia("no_es");
    if (!Number.isInteger(a.version) || a.version < 1) throw new ErrorCopia("danado");
    if (a.version > FORMATO) throw new ErrorCopia("version");
    revisarCabecera(a);
    if (!a.datos) throw new ErrorCopia("danado");
    return a;
  }
  const cabeceraDe = (a) => ({ kdf: a.kdf, cifrado: a.cifrado, verificador: a.verificador });
  /** Abre el archivo con la frase o con una llave guardada ({raw}): {contenido, raw}. */
  async function abrir(texto, clave) {
    const a = leer(texto);
    const { llave, raw } = await abrirCabecera(cabeceraDe(a), clave);
    let contenido;
    try { contenido = JSON.parse(aTexto(await descifrar(llave, a.datos, AAD_DATOS))); } catch { throw new ErrorCopia("danado"); }
    if (!contenido || typeof contenido !== "object" || contenido.formato !== a.version || !contenido.estado || typeof contenido.estado !== "object") throw new ErrorCopia("danado");
    return { contenido, raw };
  }
  /** La sal del archivo: si es la misma de la llave que se recordó, no hace falta pedir la frase. */
  const salDe = (texto) => leer(texto).kdf.sal;

  // ───────────── La frase ─────────────
  /** Una frase sirve si es larga: 12 caracteres o más (mejor cuatro palabras). Devuelve el problema o "". */
  function revisarFrase(frase) {
    if (typeof frase !== "string" || [...frase.trim()].length < 12) return "Usa una frase de al menos 12 caracteres (por ejemplo, cuatro palabras).";
    return "";
  }
  /** Qué tan difícil es de adivinar (0 a 3): «Muy corta», «Aceptable», «Buena», «Muy buena». Estimación simple y honesta:
   *  palabras (unos 11 bits cada una, como una lista de 2.000 palabras) o caracteres según qué tipos usa; las repeticiones restan. */
  function fuerzaFrase(frase) {
    const f = String(frase || "").normalize("NFC").trim();
    const largo = [...f].length;
    if (largo < 12) return { nivel: 0, texto: "Muy corta" };
    const palabras = f.split(/\s+/).filter((p) => [...p].length >= 3);
    let tipos = 0;
    if (/[a-zñáéíóúü]/.test(f)) tipos += 26;
    if (/[A-ZÑÁÉÍÓÚÜ]/.test(f)) tipos += 26;
    if (/\d/.test(f)) tipos += 10;
    if (/[^\p{L}\p{N}\s]/u.test(f)) tipos += 20;
    const distintos = new Set([...f.toLowerCase()]).size;
    const porCaracteres = Math.min(largo, distintos * 2) * Math.log2(Math.max(tipos, 10)) * 0.6;
    const porPalabras = palabras.length >= 3 ? new Set(palabras.map((p) => p.toLowerCase())).size * 11 : 0;
    const bits = Math.max(porCaracteres, porPalabras);
    if (bits >= 64) return { nivel: 3, texto: "Muy buena" };
    if (bits >= 50) return { nivel: 2, texto: "Buena" };
    return { nivel: 1, texto: "Aceptable" };
  }

  globalThis.AlcanciaCopia = Object.freeze({
    FORMATO, TIPO, ARCHIVO, ITERACIONES, MIN_ITERACIONES, MENSAJES, ErrorCopia,
    nuevaCabecera, abrirCabecera, revisarCabecera, importarLlave, paraCelular, huella, armar, leer, abrir, salDe, revisarFrase, fuerzaFrase,
    _interno: { aBase64, deBase64, derivar, cifrar, descifrar, AAD_DATOS, AAD_VERIFICADOR },
  });
})();
