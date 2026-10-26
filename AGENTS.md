# Alcancía — guía para trabajar en el proyecto

> Para personas y para cualquier IA de programación (Claude Code, Codex, Gemini/Antigravity…). `CLAUDE.md` y `GEMINI.md` solo
> importan este archivo: la guía es una sola.

Alcancía es una app de control de gastos personal. La persona agrega las cartolas de sus bancos y billeteras (CSV o Excel); Alcancía
las lee con una **receta** por banco, las guarda sin duplicar, las categoriza (reglas aprendidas → comercios conocidos → la IA del
usuario) y muestra cuánto lleva gastado, a qué ritmo va y qué categoría se pasa del presupuesto. La IA del usuario (Claude Code, Codex
o Gemini, con su propia cuenta) también da consejos. Interfaz web única; app de escritorio para Mac, Windows y Linux en camino.

**Principios que no se negocian**
1. **Los datos son del usuario.** Viven en su computador (`~/Alcancia`), en formato abierto. No hay servidores propios ni telemetría.
2. **Nunca pedimos la clave del banco** ni nos conectamos a bancos con credenciales de la persona. Las cartolas las descarga ella.
   Las conexiones oficiales (banca abierta) se evaluarán cuando existan y no exijan un servidor nuestro.
3. **La IA es la del usuario** y ve lo mínimo: descripción y monto para categorizar; totales por categoría y principales comercios
   para los consejos. Nunca números de cuenta, RUT ni claves.
4. **Recetas = solo datos.** Una receta nunca ejecuta código. Todo lo que viene de afuera (recetas, traducciones, respuestas de la
   IA) se valida antes de usarse y se escapa antes de mostrarse.
5. **Gratis y abierto** (AGPL-3.0). Sin cuentas, sin publicidad, sin recomendar productos financieros.
6. **Nada personal en el código.** Ejemplos, pruebas y `ui/demo.json` solo con datos ficticios (Ana Pérez, Matías Soto, Banco Ejemplo).

## Mapa del repo

| Ruta | Qué es |
|---|---|
| `bin/` | Python **solo biblioteca estándar**. `datos.py` (formato en disco, ids, escritura atómica), `recetas.py` (validar, detectar y aplicar recetas; lee CSV y .xlsx sin librerías), `categorizar.py` (reglas, comercios conocidos, IA), `resumen.py` (cuentas del mes, proyección, alertas, presupuesto sugerido), `ia.py` (`preguntar()` con la IA del usuario). Scripts que llama la app: `estado.py` (todo lo que pinta la interfaz), `importar.py`, `receta_ia.py`, `consejos.py` y `guardar.py` (categoría, regla, presupuesto, receta; lo de la interfaz llega en un archivo JSON de entrada). El último argumento siempre es la ruta del JSON de salida. |
| `recetas/` | Recetas incluidas en la app (solo las probadas con una cartola real) y `README.md` con el formato. |
| `ui/` | Interfaz web única (`app.js`, `app.css`), `demo.json` (ficticio, se genera con `herramientas/generar_demo.py`) e `idiomas/en.json`. |
| `docs/` | Página pública (GitHub Pages). `pagina.yml` la publica junto a `ui/` en `/demo/`. |
| `pruebas/` | `correr.sh` (todo), `test_python.py`, `interfaz.mjs` (Playwright), `casos.json` (casos compartidos Python ↔ JS), `ia_falsa.py`, `datos/` (cartola ficticia). |
| `herramientas/` | `revisar_privacidad.sh`, `generar_demo.py`. |
| `ejemplos/` | Scripts para construir encima del formato abierto. |
| `app/` | App de Mac (SwiftPM, macOS 15, sin proyecto de Xcode). `AlcanciaApp.swift` (arranque y barra de menú), `Ventana.swift` (WKWebView + puente: un `case` por acción), `Servicios.swift` (rutas, config, idioma, IA del usuario, `Procesador.correrJSON`), `Actualizaciones.swift` (GitHub Releases o `git pull` en un checkout de desarrollo). |
| `build.sh`, `herramientas/empaquetar.sh` | Arman `dist/Alcancia.app` (con Python portátil verificado por SHA-256 y bin/, ui/, recetas/ adentro) + zip + `.sha256`; `build.sh` la instala en `~/Applications`. |

## Cómo funciona
- **Importar:** `importar.py vista <archivo> [receta]` detecta la receta (la que reconoce más encabezados) y devuelve una muestra sin
  guardar nada. `importar.py guardar <archivo> <receta> <ia 0|1>` aplica la receta, categoriza con reglas y comercios, guarda con
  `datos.agregar` (por id: `sha1(cuenta|fecha|descripción normalizada|monto|ocurrencia)`) y, si se pidió, completa categorías con la IA.
  El avance queda en `~/Alcancia/.alcancia/estado.json`.
- **Sin receta:** `receta_ia.py <archivo> <país>` muestra a la IA las primeras 25 filas, valida la receta que propone y la prueba con el
  mismo archivo. No guarda nada: la app la guarda (`.alcancia/recetas/`) cuando la persona confirma que los movimientos se ven bien.
  Compartir es opcional y abre un issue prellenado en el catálogo con **solo la receta**.
- **Resumen:** la misma lógica en `bin/resumen.py` y en `ui/app.js` (`resumen`, `presupuestoSugerido`, `reglaPara`), probada con
  `pruebas/casos.json`. Si cambias una regla, cambia los dos lados y el caso. La proyección sigue el ritmo solo de lo variable
  (3+ gastos en el mes, categoría no `fijo`); lo fijo y lo esporádico queda como está.
- **Consejos:** `consejos.py <hoy>` arma un prompt con totales y exige las tres secciones (`### Lo que va bien`, `### Ojo con`,
  `### Para esta semana`). Si no vienen, no se guarda nada.

## Puente interfaz ↔ app
La UI llama `host.enviar(accion, datos)` y la app responde con `window.Alcancia.<funcion>(json)`. En el navegador, `simular()` responde
con datos ficticios. Acciones: `listo, config, probarIA, elegirCartola, vistaCartola, aprenderReceta, guardarReceta, importar,
categoria, regla, presupuesto, pedirConsejos, abrirEnlace, abrirCarpeta, buscarActualizacion, actualizar`. Respuestas: `estado,
iaProbada, cartolaElegida, vistaLista, recetaAprendida, importarProgreso, importado, consejosListos, actualizacionRevisada,
actualizacionProgreso`. `pruebas/contrato.py` revisa que cada acción exista en `Ventana.swift` (y en Windows/Linux cuando exista), que cada
función que llama la app exista en `window.Alcancia` y que los scripts que llama existan. Una acción nueva va en `ui/app.js`, en `Ventana.swift`
y simulada en `simular()`.

## App de Mac
- Datos en `~/Alcancia`; el código va dentro de la app (`Contents/Resources/alcancia`) y los scripts corren con el Python portátil incluido
  (`ALCANCIA_RECURSOS` apunta ahí). La app nunca usa `ui/demo.json` (se quita al empaquetar).
- Lo que manda la interfaz no arma comandos: rutas de archivo se revisan, ids se filtran y los datos van en un JSON de entrada.
- Desarrollo en el Mac: `~/Developer/alcancia` es el checkout; `bash build.sh` (se niega si hay una importación en curso) e instala en
  `~/Applications/Alcancia.app`. Compilar solo: `cd app && swift build -c release`. Swift solo compila en un Mac (o en el job `mac` de GitHub).

## Reglas al cambiar cosas
- Código, comentarios, commits y textos en **español** (de Chile neutro). Todo texto nuevo visible va con su traducción en
  `ui/idiomas/en.json` en el mismo cambio, como frase completa con marcadores (`T("Llevas {g}…", {g})`), nunca pedazos pegados.
- Contenido del usuario y dinero con `esc()` y `data-sin-traducir`.
- No cambies el formato de los datos (README, "Formato de los datos") sin compatibilidad. Hay gente con scripts que dependen de él.
- Antes de cerrar un cambio: `bash pruebas/correr.sh` y mirar la interfaz (`cd ui && python3 -m http.server 8765`, `?idioma=en`,
  `?bienvenida`, `?vacio`, `window.Alcancia._probar(E => …)`), también a ancho de celular.
- Privacidad: `bash herramientas/revisar_privacidad.sh` antes de cada commit (usa `.terminos-privados`, local y nunca versionado).
  Jamás subas una cartola real, ni siquiera "para probar": las pruebas usan `pruebas/datos/cartola_ejemplo.csv`.
- Commits con autor `@users.noreply.github.com`. El repo es público: cada commit se ve al tiro.

## Revisar aportes
Todo entra por pull request y lo junta quien mantiene el proyecto, solo con su aprobación. Leer todo el diff antes de correr nada
(alerta roja: workflows, scripts de instalación, red nueva, dependencias nuevas, binarios, cualquier cosa que lea claves). Las recetas
nuevas se validan con `recetas.validar` y se prueban con una cartola **ficticia** que imite el formato. Detalle en `CONTRIBUTING.md`.
