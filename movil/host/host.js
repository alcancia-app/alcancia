// El anfitrión de Alcancía en el celular: atiende las acciones del puente (host.enviar en ui/app.js) igual que Ventana.swift en el Mac,
// pero solo para mirar. Los datos llegan desde el Mac en la «copia para el celular» (ui/copia.js): un archivo cifrado en la nube de
// la persona que el teléfono lee con el selector de archivos del sistema y abre con su frase. No hay red ni servidores: ni llaves de
// conectores, ni IA, ni telemetría. Lo que cambia datos (SOLO_MAC) responde «Esto se hace en tu Mac por ahora».
//
// Plugins (por el puente de Capacitor, sin empaquetador): Carpeta (propio, movil/plugins/carpeta: el archivo con permiso para
// volver a leerlo, la última copia que se abrió bien, la llave recordada en el Llavero/Keystore y los ajustes del teléfono) y
// LocalNotifications (oficial: los avisos de pagos). `window.Capacitor.nativePromise` lo pone el puente nativo en la página.
(() => {
  "use strict";
  const CAP = window.Capacitor;
  const C = window.AlcanciaCopia;
  const llamar = (plugin, metodo, opciones = {}) => CAP.nativePromise(plugin, metodo, opciones);
  const A = () => window.Alcancia; // las funciones de la interfaz
  const ahora = () => window.ALCANCIA_AHORA || Date.now(); // las pruebas fijan el reloj (pruebas/movil.mjs)
  const hoy = () => window.ALCANCIA_HOY || new Date(ahora() - new Date(ahora()).getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const cancelado = (e) => e?.code === "CANCELADO" || /cancel/i.test(String(e?.message || e));
  const AJUSTES = ["idioma_ui", "bienvenida", "avisos"]; // lo único que se guarda en el teléfono (lo demás viene del Mac)
  const HORA_AVISO = 9, DIAS_AVISOS = 35, MAX_AVISOS = 60; // iOS guarda hasta 64 avisos programados por app

  let ajustes = {};
  let archivo = "";          // nombre del archivo elegido
  let pendiente = null;      // un archivo leído que espera la frase
  let contenido = null;      // la copia abierta (paraCelular)
  let llave = null;          // {raw, sal} de esta sesión (en memoria)
  let recordada = false;     // hay una llave en el Llavero/Keystore
  let desactualizada = false, error = "", aviso = "";

  // ───────────── Ajustes del teléfono ─────────────
  async function leerAjustes() {
    try { const a = JSON.parse((await llamar("Carpeta", "leerAjustes")).texto || "{}"); ajustes = a && typeof a === "object" ? a : {}; } catch { ajustes = {}; }
  }
  async function guardarAjustes(cambios) {
    for (const k of AJUSTES) if (typeof cambios[k] === "string" || typeof cambios[k] === "boolean") ajustes[k] = cambios[k];
    try { await llamar("Carpeta", "guardarAjustes", { texto: JSON.stringify(ajustes) }); } catch { /* sigue: solo por esta vez */ }
  }

  // ───────────── La llave ─────────────
  async function llaveRecordada(sal) {
    try {
      const v = (await llamar("Carpeta", "leerLlave")).valor;
      if (!v) { recordada = false; return null; }
      recordada = true;
      const k = JSON.parse(v);
      return k && k.sal === sal && typeof k.raw === "string" ? k : null;
    } catch { return null; }
  }

  // ───────────── Abrir la copia ─────────────
  function aceptar(texto, r, sal, guardar) {
    contenido = r.contenido; llave = { raw: r.raw, sal }; pendiente = null;
    if (guardar) llamar("Carpeta", "guardarCache", { texto }).catch(() => {});
  }
  /** Intenta abrir un archivo con la llave de la sesión o la recordada. {ok} si se abrió o si espera la frase; {ok:false, error} si no sirve. */
  async function intentar(texto, guardar) {
    let sal;
    try { sal = C.salDe(texto); } catch (e) { return { ok: false, error: e.message }; }
    const k = (llave && llave.sal === sal && llave) || (await llaveRecordada(sal));
    if (!k) { pendiente = texto; contenido = null; return { ok: true, frase: true }; }
    try { aceptar(texto, await C.abrir(texto, { raw: k.raw }), sal, guardar); return { ok: true }; }
    catch (e) {
      if (e.codigo === "frase") { pendiente = texto; contenido = null; return { ok: true, frase: true }; }
      return { ok: false, error: e.message };
    }
  }
  /** Lee el archivo de la nube; si no se puede (sin conexión, a medio subir, de una versión más nueva), queda lo último que se abrió bien. */
  async function cargar() {
    let nuevo = null, problema = "";
    aviso = "";
    try {
      const r = await llamar("Carpeta", "leer");
      nuevo = String(r.texto || ""); archivo = r.nombre || archivo || C.ARCHIVO;
    } catch (e) {
      if (e?.code === "SIN_ARCHIVO") { archivo = ""; return; }
      archivo = archivo || C.ARCHIVO;
      problema = "No pude leer el archivo en tu nube. Te muestro la última copia que abrí.";
    }
    if (nuevo != null) {
      const r = await intentar(nuevo, true);
      if (r.ok) { desactualizada = false; error = ""; return; }
      problema = r.error;
    }
    if (!contenido && !pendiente) {
      let guardada = null;
      try { guardada = (await llamar("Carpeta", "leerCache")).texto || null; } catch { /* no hay */ }
      if (guardada && (await intentar(guardada, false)).ok) { desactualizada = true; error = ""; aviso = problema; return; }
      error = problema;
      return;
    }
    desactualizada = true; aviso = problema; // lo que ya está en pantalla se queda
  }

  // ───────────── Estado para la interfaz ─────────────
  function estadoCelular() {
    return { estado: contenido ? "listo" : pendiente ? "frase" : "nuevo", archivo, generado: contenido?.generado || "", recordada, desactualizada, error };
  }
  function enviarEstado() {
    const e = (contenido && contenido.estado) || {};
    A().estado({
      movimientos: [], categorias: [], presupuesto: { mensual: {} }, cuentas: [], consejos: [], compromisos: { formato: 1, compromisos: [], descartados: [] },
      feriados: [], palabras_mora: [], palabras_automatico: [], ...e,
      hoy: hoy(), config: { ...(e.config || {}), ...ajustes }, ias: [], version: window.ALCANCIA_VERSION || "", carpeta: "", actualizacion: { hay: false },
      conectores: [], conexiones: {}, vigilar: { activo: false, recientes: [] }, ia_externa: [], sugerencias: [], reglas: [], chat: [], celular: estadoCelular(),
    });
  }

  // ───────────── Avisos de pagos ─────────────
  /** Id numérico estable para cada aviso (FNV-1a de 31 bits: Android usa int). */
  function idDe(clave) {
    let h = 2166136261;
    for (const ch of clave) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619); }
    return (h >>> 1) || 1;
  }
  /** Borra los avisos programados y, si están activos, programa los de los próximos días (la lógica es la de la interfaz). */
  async function programarAvisos() {
    try {
      const pendientes = (await llamar("LocalNotifications", "getPending")).notifications || [];
      if (pendientes.length) await llamar("LocalNotifications", "cancel", { notifications: pendientes.map((n) => ({ id: n.id })) });
      if (!ajustes.avisos || !contenido) return;
      const ya = ahora();
      const lista = A().avisosCelular({ hoy: hoy(), dias: DIAS_AVISOS })
        .map((a) => ({ ...a, at: new Date(+a.fecha.slice(0, 4), +a.fecha.slice(5, 7) - 1, +a.fecha.slice(8, 10), HORA_AVISO, 0, 0) }))
        .filter((a) => a.at.getTime() > ya).slice(0, MAX_AVISOS);
      if (!lista.length) return;
      // Con la pantalla bloqueada y las vistas previas ocultas, iOS muestra solo este texto genérico.
      await llamar("LocalNotifications", "registerActionTypes", { types: [{ id: "compromiso", actions: [], iosHiddenPreviewsBodyPlaceholder: lista[0].oculto }] });
      await llamar("LocalNotifications", "schedule", {
        notifications: lista.map((a) => ({ id: idDe(a.clave), title: a.titulo, body: a.cuerpo, schedule: { at: a.at, allowWhileIdle: true },
          actionTypeId: "compromiso", extra: { alcancia: "compromisos" } })),
      });
    } catch (e) { console.error("Alcancía: avisos", e); }
  }

  // ───────────── Acciones del puente ─────────────
  const SOLO_MAC = ["probarIA", "elegirCartola", "vistaCartola", "aprenderReceta", "guardarReceta", "importar", "categoria", "categoriaNueva", "saldo", "regla",
    "presupuesto", "pedirConsejos", "abrirCarpeta", "conectar", "sincronizar", "desconectar", "vigilar", "mcpConectar", "actualizar", "chat", "compromiso", "celular"];
  const ACCIONES = {
    listo: () => enviarEstado(),
    async config(d) {
      const idioma = ajustes.idioma_ui;
      await guardarAjustes(d);
      if (d.idioma_ui && d.idioma_ui !== idioma) await programarAvisos(); // los textos de los avisos, en el idioma nuevo
    },
    async avisos(d) {
      if (!d.activo) { await guardarAjustes({ avisos: false }); return programarAvisos(); }
      let p = {};
      try { p = await llamar("LocalNotifications", "requestPermissions"); } catch { /* sin permiso */ }
      if (p.display !== "granted") {
        await guardarAjustes({ avisos: false });
        return A().avisosRespuesta({ activo: false, error: "Para avisarte, permite las notificaciones de Alcancía en los ajustes del teléfono." });
      }
      await guardarAjustes({ avisos: true });
      await programarAvisos();
      A().avisosRespuesta({ activo: true });
    },
    async traer(d) {
      switch (d.accion) {
        case "elegir": {
          let r;
          try { r = await llamar("Carpeta", "elegir"); }
          catch (e) { return A().traerRespuesta(cancelado(e) ? { ok: false, cancelado: true } : { ok: false, error: "No pude abrir ese archivo." }); }
          archivo = r.nombre || C.ARCHIVO; contenido = null; pendiente = null; desactualizada = false; error = "";
          const x = await intentar(String(r.texto || ""), true);
          if (!x.ok) error = x.error;
          A().traerRespuesta(x.ok ? { ok: true } : { ok: false, error: x.error });
          enviarEstado();
          return programarAvisos();
        }
        case "abrir": {
          if (!pendiente) return A().traerRespuesta({ ok: false, error: "Elige primero el archivo." });
          try {
            const sal = C.salDe(pendiente), texto = pendiente;
            const r = await C.abrir(texto, { frase: String(d.frase || "") });
            aceptar(texto, r, sal, true);
            if (d.recordar) {
              try { await llamar("Carpeta", "guardarLlave", { valor: JSON.stringify({ raw: r.raw, sal }) }); recordada = true; }
              catch { aviso = "No pude guardar la frase en este teléfono: te la pido la próxima vez."; }
            }
            error = ""; desactualizada = false;
            A().traerRespuesta({ ok: true, aviso });
            enviarEstado();
            return programarAvisos();
          } catch (e) { return A().traerRespuesta({ ok: false, error: e.message }); }
        }
        case "releer":
          await cargar();
          enviarEstado();
          A().traerRespuesta({ ok: true, aviso: aviso || (contenido && !desactualizada ? "Listo: tienes la copia más nueva" : "") });
          return programarAvisos();
        case "olvidar":
          try { await llamar("Carpeta", "borrarLlave"); } catch { /* no estaba */ }
          recordada = false;
          return enviarEstado();
        case "desconectar":
          try { await llamar("Carpeta", "olvidar"); } catch { /* sigue */ }
          archivo = ""; pendiente = null; contenido = null; llave = null; recordada = false; desactualizada = false; error = "";
          await programarAvisos(); // sin copia no queda ningún aviso programado
          return enviarEstado();
      }
    },
    abrirEnlace(d) {
      // Solo los enlaces de Alcancía (Acerca de); Capacitor abre lo externo en el navegador del sistema.
      if (/^https:\/\/(alcancia-app\.github\.io\/alcancia\/|github\.com\/alcancia-app\/)/.test(d.url || "")) window.location.href = d.url;
    },
    buscarActualizacion: () => A().actualizacionRevisada({ hay: false }),
  };
  for (const a of SOLO_MAC) ACCIONES[a] = () => A().soloEnMac();

  // Una cosa a la vez: leer el archivo, abrirlo y programar avisos no se pisan (el selector de archivos sí puede esperar a la persona).
  let fila = Promise.resolve();
  const enOrden = (f) => (fila = fila.then(f, f));
  async function atender(msg) {
    const f = ACCIONES[msg?.accion];
    if (!f) return;
    return enOrden(async () => { try { await f(msg.datos || {}); } catch (e) { console.error("Alcancía:", msg.accion, e); } });
  }

  // Al volver a primer plano: la copia más nueva (el Mac la pudo actualizar mientras tanto). Como mucho una vez por minuto.
  let ultimaLectura = 0;
  function alVolver() {
    if (document.visibilityState === "hidden" || !archivo || ahora() - ultimaLectura < 60000) return;
    ultimaLectura = ahora();
    enOrden(async () => { await cargar(); enviarEstado(); await programarAvisos(); });
  }

  async function iniciar() {
    await leerAjustes();
    ultimaLectura = ahora();
    await cargar();
    const cola = window.alcanciaMovil.cola.splice(0);
    window.alcanciaMovil = { enviar: (msg) => { atender(msg); } };
    for (const m of cola) await atender(m);
    if (aviso) A().traerRespuesta({ ok: true, aviso });
    await enOrden(programarAvisos);
    document.addEventListener("visibilitychange", alVolver);
    document.addEventListener("resume", alVolver);
    // Tocar un aviso abre Pagos.
    try { CAP.addListener("LocalNotifications", "localNotificationActionPerformed", () => A()._probar((E) => { E.vista = "compromisos"; E.ajustes = false; })); } catch { /* sin avisos */ }
  }
  iniciar();

  window._alcanciaMovil = { ACCIONES, SOLO_MAC, idDe }; // para las pruebas
})();
