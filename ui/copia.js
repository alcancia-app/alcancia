// «Copia para el celular»: lo que el Mac deja en la nube de la persona para que el teléfono la muestre. El cifrado es la pieza
// «cifrado» (ui/cifrado.js, se carga antes): PBKDF2-SHA256 600.000 vueltas → AES-256-GCM con AAD y un verificador de la frase. Aquí
// queda lo propio de Alcancía: cómo se reconoce el archivo (los mismos nombres de siempre, así lo que ya está en la nube se abre
// igual) y qué viaja (paraCelular, lista blanca). Las frases de los errores son las de la pieza (con {app}) menos la de versión. El mismo archivo corre en el
// Mac (dentro de la interfaz), en el teléfono y en Node (pruebas/copia.mjs). Formato en el README («Copia para el celular»).
// - La frase nunca se guarda: el Mac guarda la llave derivada (`llaves.raw`) en su Llavero y el teléfono, si la persona lo pide, en
//   su Llavero o Keystore. Una llave guardada antes (32 bytes, solo AES) sigue sirviendo; las nuevas son de 64.
// - El contenido es una lista blanca de lo que la interfaz necesita para pintar (paraCelular): nunca llaves de conectores, tokens,
//   rutas del Mac, la conversación con la IA ni lo que solo sirve para cambiar cosas.
(() => {
  "use strict";
  const P = globalThis.PiezaCifrado;
  const FORMATO = 1, TIPO = "copia-celular", ARCHIVO = "Alcancia-celular.alcancia";
  // La versión nueva siempre se ve en el teléfono: hay que decir qué app actualizar. Lo demás, con las frases de la pieza.
  const C = P.crear({
    app: "Alcancía", contexto: "alcancia:celular", verificador: "alcancia", marca: "alcancia", tipo: TIPO, formato: FORMATO,
    mensajes: { version: "Esta copia viene de una versión más nueva de Alcancía. Actualiza la app del celular." },
  });
  const MENSAJES = C.MENSAJES;
  /** La frase de un error para mostrar (ya armada, con «Alcancía»; tr la traduce): la de la pieza o el mensaje tal cual. */
  const mensaje = (e) => (e && (e.frase || e.message)) || C.error("danado").frase;

  /** Abre el archivo con la frase o con una llave guardada ({raw}): {contenido, llaves}. Revisa además que sea una copia completa. */
  async function abrir(texto, clave) {
    const { contenido, llaves, version } = await C.abrir(texto, clave);
    if (!contenido || typeof contenido !== "object" || contenido.formato !== version || !contenido.estado || typeof contenido.estado !== "object") {
      throw C.error("danado");
    }
    return { contenido, llaves };
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
    for (const [id, c] of Object.entries(e.conexiones || {})) if (c && typeof c === "object") conexiones[String(id)] = elegir(c, ["conectado", "ultima", "error", "plantilla", "valores"]);
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

  globalThis.AlcanciaCopia = Object.freeze({
    FORMATO, TIPO, ARCHIVO, MENSAJES, ErrorCifrado: P.ErrorCifrado, mensaje,
    nuevaCabecera: C.nuevaCabecera, abrirCabecera: C.abrirCabecera, revisarCabecera: C.revisarCabecera, importarLlave: C.importarLlave,
    armar: C.armar, leer: C.leer, abrir, salDe: C.salDe, huella: C.huella, revisarFrase: C.revisarFrase, fuerzaFrase: C.fuerzaFrase,
    paraCelular,
    _interno: { aBase64: P.aBase64, deBase64: P.deBase64, cifrar: C.cifrar, descifrar: C.descifrar },
  });
})();
