// Alcancía en el celular: se carga ANTES que la interfaz (ui/copia.js y ui/app.js, scripts clásicos) para que sepa desde el primer
// momento que corre en el teléfono (solo para mirar). Lo que la interfaz mande mientras carga el anfitrión (host/host.js) queda en
// cola y se atiende apenas esté listo. La versión la pone movil/armar.mjs.
(() => {
  "use strict";
  window.ALCANCIA_HOST = "movil";
  window.ALCANCIA_VERSION = "__VERSION__";
  const cola = [];
  window.alcanciaMovil = { cola, enviar(msg) { cola.push(msg); } };
})();
