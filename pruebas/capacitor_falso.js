// Capacitor falso para probar la app del celular en un navegador (pruebas/movil.mjs). Imita el puente nativo
// (window.Capacitor.nativePromise y addListener) y los plugins que usa movil/host/host.js: Carpeta (el archivo de la nube, la última
// copia, la llave recordada y los ajustes, todo en memoria) y LocalNotifications (los avisos programados). Nunca toca archivos
// reales ni la red. `window._celular` (opcional, puesto antes por la prueba) es lo que «el teléfono» ya tenía guardado:
// {nube: {nombre, texto}, elegido, cache, llave, ajustes, permiso, sinConexion, pendientes}.
(() => {
  const g = (window._celular = window._celular || {});
  g.pendientes = g.pendientes || [];
  g.permiso = g.permiso || "granted";
  g.llamadas = [];
  const falla = (message, code) => Promise.reject(Object.assign(new Error(message), { code }));
  const P = {
    Carpeta: {
      elegir() { if (!g.nube) return falla("cancelado", "CANCELADO"); g.elegido = true; return { nombre: g.nube.nombre, texto: g.nube.texto }; },
      leer() {
        if (!g.elegido) return falla("Todavía no eliges el archivo.", "SIN_ARCHIVO");
        if (g.sinConexion || !g.nube) return falla("No pude leer el archivo.", "ARCHIVO");
        return { nombre: g.nube.nombre, texto: g.nube.texto };
      },
      olvidar() { g.elegido = false; delete g.cache; delete g.llave; return {}; },
      guardarCache({ texto }) { g.cache = texto; return {}; },
      leerCache() { return g.cache ? { texto: g.cache } : {}; },
      guardarLlave({ valor }) { g.llave = valor; return {}; },
      leerLlave() { return g.llave ? { valor: g.llave } : {}; },
      borrarLlave() { delete g.llave; return {}; },
      guardarAjustes({ texto }) { g.ajustes = texto; return {}; },
      leerAjustes() { return g.ajustes ? { texto: g.ajustes } : {}; },
    },
    LocalNotifications: {
      requestPermissions() { return { display: g.permiso }; },
      checkPermissions() { return { display: g.permiso }; },
      getPending() { return { notifications: g.pendientes.map((n) => ({ id: n.id, title: n.title, body: n.body })) }; },
      cancel({ notifications }) { const ids = new Set(notifications.map((n) => n.id)); g.pendientes = g.pendientes.filter((n) => !ids.has(n.id)); return {}; },
      schedule({ notifications }) {
        // Como el puente de verdad: la fecha llega como Date (iOS la recibe como NSDate; Android, como texto ISO).
        for (const n of notifications) {
          if (!(n.schedule && n.schedule.at instanceof Date)) return falla("schedule.at tiene que ser una fecha", "FECHA");
          g.pendientes.push({ ...n, schedule: { ...n.schedule, at: n.schedule.at.toISOString(), hora: n.schedule.at.getHours(), minuto: n.schedule.at.getMinutes() } });
        }
        return { notifications: notifications.map((n) => ({ id: n.id })) };
      },
      registerActionTypes({ types }) { g.tipos = types; return {}; },
    },
  };
  window.Capacitor = {
    isNativePlatform: () => true,
    getPlatform: () => "ios",
    nativePromise(plugin, metodo, opciones) {
      g.llamadas.push(`${plugin}.${metodo}`);
      const f = P[plugin]?.[metodo];
      if (!f) return Promise.reject(Object.assign(new Error(`${plugin}.${metodo} no está implementado`), { code: "UNIMPLEMENTED" }));
      // Asíncrono como el puente de verdad (las respuestas llegan después).
      return new Promise((ok, mal) => setTimeout(() => Promise.resolve().then(() => f(opciones || {})).then(ok, mal), 5));
    },
    addListener(plugin, evento, callback) { (g.oyentes = g.oyentes || []).push({ plugin, evento, callback }); return { remove() {} }; },
  };
})();
