// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.
// Pieza «cifrado»: cifrar con una frase que solo conoce la persona, con WebCrypto y sin dependencias. El mismo código cifra en el
// computador (en la interfaz) y abre en el teléfono; en Node se carga con require. Funciona como script clásico (queda en
// window.PiezaCifrado) con una CSP «script-src 'self'».
// - La llave sale de la frase con PBKDF2-SHA256 (600.000 vueltas, sal aleatoria de 16 bytes; la frase normalizada NFC: «canción»
//   escrita en un iPhone y en un Android es la misma). De esos 512 bits, 256 son la llave AES-256-GCM y 256 una llave HMAC-SHA256
//   para los nombres de archivo (la nube no ve ni el nombre de un perfil). Los primeros 256 bits son los mismos que da derivar 256:
//   una llave AES guardada antes (32 bytes) sigue sirviendo.
// - Cada sobre lleva su propio IV aleatorio de 12 bytes; GCM detecta cualquier cambio. Los datos adicionales (AAD) atan cada sobre
//   a su lugar: un archivo cambiado de nombre, de copia o de versión no se abre.
// - Un «verificador» cifrado permite decir «la frase no es la correcta» antes de tocar los datos. La frase nunca se guarda.
// - Un archivo armado con `armar` dice su versión: uno de una versión más nueva da «actualiza la app» (no «está dañado»), y uno
//   más grande que `maximo` ni se intenta leer.
//
//   const c = PiezaCifrado.crear({ app: "Ana", contexto: "ana:copia", marca: "ana", tipo: "copia" });
//   const { cabecera, llaves } = await c.nuevaCabecera(frase);        // cabecera: nada secreto; se guarda junto a los datos
//   const texto = await c.armar(contenido, cabecera, llaves);          // un solo archivo, JSON
//   const { contenido, llaves: l } = await c.abrir(texto, { frase });  // o { raw } con la llave que se guardó (llaves.raw)
//   const nombre = await c.nombreOpaco(llaves, "perfiles/ana.json");  // 32 hex, siempre el mismo para la misma ruta y frase
//   try { … } catch (e) { e.codigo /* frase | danado | version | no_es | sin_cifrado */; Tp(e.plantilla, e.valores) }
(function (raiz, fabrica) {
  const m = fabrica();
  if (typeof module === "object" && module.exports) module.exports = m;
  else raiz.PiezaCifrado = m;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const ITERACIONES = 600000, MIN_ITERACIONES = 100000, MAX_ITERACIONES = 10000000;
  const MAXIMO = 100 * 1024 * 1024;
  /** Frases en español (claves de traducción), con {app}. */
  const MENSAJES = {
    frase: "La frase no es la correcta.",
    danado: "El archivo está dañado o se está copiando todavía. Prueba en un rato.",
    version: "Este archivo viene de una versión más nueva de {app}. Actualiza la app.",
    no_es: "Ese archivo no es una copia de {app}.",
    sin_cifrado: "Este equipo no puede cifrar.",
    corta: "Usa una frase de al menos 12 caracteres (por ejemplo, cuatro palabras).",
  };
  const FUERZA = ["Muy corta", "Aceptable", "Buena", "Muy buena"];

  class ErrorCifrado extends Error {
    constructor(codigo, valores = {}) {
      const plantilla = MENSAJES[codigo] || MENSAJES.danado;
      super(plantilla.replace(/\{(\w+)\}/g, (_, k) => (valores[k] !== undefined ? String(valores[k]) : `{${k}}`)));
      this.codigo = MENSAJES[codigo] ? codigo : "danado";
      this.plantilla = plantilla;
      this.valores = valores;
    }
  }

  const subtle = () => {
    const s = globalThis.crypto && globalThis.crypto.subtle;
    if (!s) throw new ErrorCifrado("sin_cifrado");
    return s;
  };
  const utf8 = new TextEncoder();
  const aBytes = (texto) => utf8.encode(texto);
  const aTexto = (b) => new TextDecoder("utf-8", { fatal: true }).decode(b);
  const azar = (n) => globalThis.crypto.getRandomValues(new Uint8Array(n));
  function aBase64(bytes) {
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s);
  }
  function deBase64(b64) {
    if (typeof b64 !== "string" || b64.length % 4 || !/^[A-Za-z0-9+/]*={0,2}$/.test(b64)) throw new ErrorCifrado("danado");
    let s;
    try { s = atob(b64); } catch { throw new ErrorCifrado("danado"); } // un archivo raro nunca da un error sin explicar
    const r = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) r[i] = s.charCodeAt(i);
    return r;
  }
  const hex = (b) => [...b].map((x) => x.toString(16).padStart(2, "0")).join("");

  /** Una frase sirve si es larga: 12 caracteres o más (mejor cuatro palabras). Devuelve el problema (frase en español) o "". */
  function revisarFrase(frase) {
    return typeof frase !== "string" || [...frase.trim()].length < 12 ? MENSAJES.corta : "";
  }

  /** Qué tan difícil es de adivinar (0 a 3) con su texto («Muy corta»… «Muy buena»). Estimación simple y honesta: palabras
   *  (unos 11 bits cada una, como una lista de 2.000) o caracteres según qué tipos usa; las repeticiones restan. */
  function fuerzaFrase(frase) {
    const f = String(frase || "").normalize("NFC").trim();
    const largo = [...f].length;
    if (largo < 12) return { nivel: 0, texto: FUERZA[0] };
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
    const nivel = bits >= 64 ? 3 : bits >= 50 ? 2 : 1;
    return { nivel, texto: FUERZA[nivel] };
  }

  /**
   * { app, contexto, verificador?, aadVerificador?, marca?, tipo?, formato?, maximo? }
   * - contexto: texto que ata todo a esta app y este uso ("ana:copia"): prefijo de los AAD y de los nombres opacos.
   * - verificador / aadVerificador: lo que se cifra para reconocer la frase (por defecto, contexto y contexto + ":verificador").
   * - marca, tipo, formato: cómo se reconoce un archivo de `armar` ({[marca]: tipo, version: formato, …}).
   */
  function crear(o = {}) {
    const app = String(o.app || "la app");
    const contexto = String(o.contexto || "");
    if (!/^[a-z0-9][a-z0-9:._-]{0,60}$/.test(contexto)) throw new Error("PiezaCifrado.crear: «contexto» como «ana:copia».");
    const VERIFICADOR = String(o.verificador || contexto);
    const AAD_VERIFICADOR = String(o.aadVerificador || contexto + ":verificador");
    const marca = String(o.marca || contexto.split(":")[0]), tipo = String(o.tipo || "copia");
    const FORMATO = Number.isInteger(o.formato) && o.formato > 0 ? o.formato : 1;
    const maximo = Number.isInteger(o.maximo) && o.maximo > 0 ? Math.min(o.maximo, 1024 * 1024 * 1024) : MAXIMO;
    const AAD_DATOS = contexto + ":" + FORMATO;
    const falla = (codigo) => new ErrorCifrado(codigo, { app });

    // ───────────── Llaves ─────────────
    async function desdeBytes(bits) {
      const aes = await subtle().importKey("raw", bits.slice(0, 32), { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
      const hmac = bits.length >= 64 ? await subtle().importKey("raw", bits.slice(32, 64), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]) : null;
      return { aes, hmac, raw: aBase64(bits) };
    }
    /** Las llaves desde la frase: {aes, hmac, raw (64 bytes en base64, para el Llavero), sal, iteraciones}. */
    async function derivar(frase, sal, iteraciones = ITERACIONES) {
      if (typeof frase !== "string" || !frase) throw falla("frase");
      if (!Number.isInteger(iteraciones) || iteraciones < MIN_ITERACIONES || iteraciones > MAX_ITERACIONES) throw falla("danado");
      const base = await subtle().importKey("raw", aBytes(frase.normalize("NFC")), "PBKDF2", false, ["deriveBits"]);
      const bits = new Uint8Array(await subtle().deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: sal, iterations: iteraciones }, base, 512));
      try { return { ...(await desdeBytes(bits)), sal, iteraciones }; } finally { bits.fill(0); }
    }
    /** Una llave guardada (`raw`: 64 bytes, o 32 de una llave solo AES de antes) lista para usar. */
    async function importarLlave(raw) {
      const b = deBase64(raw);
      if (b.length !== 32 && b.length !== 64) throw falla("frase");
      try { return await desdeBytes(b); } finally { b.fill(0); }
    }

    // ───────────── Sobres ─────────────
    /** Un sobre: {iv, datos} en base64. `aad` es un texto que ata el sobre a su lugar. */
    async function cifrar(llaves, bytes, aad) {
      const iv = azar(12);
      const datos = new Uint8Array(await subtle().encrypt({ name: "AES-GCM", iv, additionalData: aBytes(String(aad)), tagLength: 128 }, llaves.aes, bytes));
      return { iv: aBase64(iv), datos: aBase64(datos) };
    }
    async function descifrar(llaves, sobre, aad) {
      if (!sobre || typeof sobre !== "object") throw falla("danado");
      const iv = deBase64(sobre.iv), datos = deBase64(sobre.datos);
      if (iv.length !== 12 || datos.length < 16) throw falla("danado");
      try {
        return new Uint8Array(await subtle().decrypt({ name: "AES-GCM", iv, additionalData: aBytes(String(aad)), tagLength: 128 }, llaves.aes, datos));
      } catch { throw falla("danado"); }
    }
    const cifrarJSON = (llaves, valor, aad) => cifrar(llaves, aBytes(JSON.stringify(valor)), aad);
    async function descifrarJSON(llaves, sobre, aad) {
      try { return JSON.parse(aTexto(await descifrar(llaves, sobre, aad))); } catch (e) { throw e instanceof ErrorCifrado ? e : falla("danado"); }
    }

    /** Nombre de archivo que no dice nada (32 hex) pero siempre es el mismo para la misma ruta y la misma frase. */
    async function nombreOpaco(llaves, ruta) {
      if (!llaves || !llaves.hmac) throw falla("frase");
      const firma = new Uint8Array(await subtle().sign("HMAC", llaves.hmac, aBytes(contexto + ":ruta:" + ruta)));
      return hex(firma.slice(0, 16));
    }

    // ───────────── Cabecera (sal, vueltas y verificador: nada secreto) ─────────────
    /** Cabecera nueva para una frase, con sus llaves. La frase tiene que pasar `revisarFrase` (salvo { revisar: false }). */
    async function nuevaCabecera(frase, { iteraciones = ITERACIONES, revisar = true } = {}) {
      if (revisar && revisarFrase(frase)) throw Object.assign(falla("frase"), { codigo: "corta", plantilla: MENSAJES.corta, message: MENSAJES.corta });
      const sal = azar(16);
      const llaves = await derivar(frase, sal, iteraciones);
      const verificador = await cifrar(llaves, aBytes(VERIFICADOR), AAD_VERIFICADOR);
      return { cabecera: { kdf: { alg: "PBKDF2-SHA256", iteraciones, sal: aBase64(sal) }, cifrado: "AES-256-GCM", verificador }, llaves };
    }
    /** Revisa una cabecera (la de un archivo o la que se guardó): lanza ErrorCifrado si no sirve. Nunca baja de MIN_ITERACIONES. */
    function revisarCabecera(c) {
      const k = c && c.kdf;
      if (!k || k.alg !== "PBKDF2-SHA256" || c.cifrado !== "AES-256-GCM" || !c.verificador) throw falla("danado");
      if (!Number.isInteger(k.iteraciones) || k.iteraciones < MIN_ITERACIONES || k.iteraciones > MAX_ITERACIONES) throw falla("danado");
      if (deBase64(k.sal).length < 16) throw falla("danado");
      return c;
    }
    /** Abre la cabecera con la frase ({frase}) o con una llave ya guardada ({raw}). Devuelve las llaves o lanza «frase». */
    async function abrirCabecera(cabecera, { frase = null, raw = null } = {}) {
      revisarCabecera(cabecera);
      const llaves = raw ? await importarLlave(raw) : await derivar(frase, deBase64(cabecera.kdf.sal), cabecera.kdf.iteraciones);
      let v;
      try { v = aTexto(await descifrar(llaves, cabecera.verificador, AAD_VERIFICADOR)); } catch { throw falla("frase"); }
      if (v !== VERIFICADOR) throw falla("frase");
      return llaves;
    }

    // ───────────── Un archivo entero ─────────────
    /** El texto del archivo: cabecera (nada secreto) + el contenido cifrado, atado a esta versión del formato. */
    async function armar(contenido, cabecera, llaves) {
      revisarCabecera(cabecera);
      const datos = await cifrar(llaves, aBytes(JSON.stringify(contenido)), AAD_DATOS);
      return JSON.stringify({ [marca]: tipo, version: FORMATO, kdf: cabecera.kdf, cifrado: cabecera.cifrado, verificador: cabecera.verificador, datos });
    }
    /** Lee el archivo sin abrirlo: lanza no_es, version o danado. Devuelve el objeto con su cabecera. */
    function leer(texto) {
      if (typeof texto !== "string" || !texto.trim() || texto.length > maximo) throw falla("no_es");
      let a;
      try { a = JSON.parse(texto); } catch { throw falla(texto.trimStart().startsWith(JSON.stringify({ [marca]: tipo }).slice(0, -1)) ? "danado" : "no_es"); }
      if (!a || typeof a !== "object" || a[marca] !== tipo) throw falla("no_es");
      if (!Number.isInteger(a.version) || a.version < 1) throw falla("danado");
      if (a.version > FORMATO) throw falla("version");
      revisarCabecera(a);
      if (!a.datos) throw falla("danado");
      return a;
    }
    const cabeceraDe = (a) => ({ kdf: a.kdf, cifrado: a.cifrado, verificador: a.verificador });
    /** Abre el archivo con la frase o con una llave guardada: {contenido, llaves}. */
    async function abrir(texto, clave) {
      const a = leer(texto);
      const llaves = await abrirCabecera(cabeceraDe(a), clave);
      // Un archivo de una versión anterior se abre con el AAD de su versión.
      const aad = contexto + ":" + a.version;
      let contenido;
      try { contenido = JSON.parse(aTexto(await descifrar(llaves, a.datos, aad))); } catch { throw falla("danado"); }
      return { contenido, llaves, version: a.version };
    }
    /** La sal del archivo: si es la misma de la llave que se recordó, no hace falta pedir la frase. */
    const salDe = (texto) => leer(texto).kdf.sal;

    /** Huella SHA-256 (hex) de un valor JSON, sin la clave `generado`: si no cambió nada, no hace falta volver a escribir. */
    async function huella(valor) {
      const { generado, ...resto } = valor && typeof valor === "object" ? valor : { valor };
      return hex(new Uint8Array(await subtle().digest("SHA-256", aBytes(JSON.stringify(resto)))));
    }

    return Object.freeze({
      FORMATO, ITERACIONES, derivar, importarLlave, cifrar, descifrar, cifrarJSON, descifrarJSON, nombreOpaco,
      nuevaCabecera, revisarCabecera, abrirCabecera, armar, leer, abrir, salDe, huella, revisarFrase, fuerzaFrase,
    });
  }

  return { crear, ErrorCifrado, MENSAJES, FUERZA, ITERACIONES, MIN_ITERACIONES, MAX_ITERACIONES, revisarFrase, fuerzaFrase,
           aBase64, deBase64, aBytes, aTexto };
});
