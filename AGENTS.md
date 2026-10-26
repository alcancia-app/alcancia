# Alcancía — guía para trabajar en el proyecto

> Para personas y para cualquier IA de programación (Claude Code, Codex, Gemini/Antigravity…). `CLAUDE.md` y `GEMINI.md` solo
> importan este archivo: la guía es una sola.

Alcancía es una app de control de gastos personal. La persona agrega las cartolas de sus bancos y billeteras (CSV o Excel); Alcancía
las lee con una **receta** por banco, las guarda sin duplicar, las categoriza (reglas aprendidas → comercios conocidos → la IA del
usuario) y muestra cuánto lleva gastado, a qué ritmo va y qué categoría se pasa del presupuesto. La IA del usuario (Claude Code, Codex
o Gemini, con su propia cuenta) también da consejos. Interfaz web única; app de escritorio para Mac, Windows y Linux en camino.

**Principios que no se negocian**
1. **Los datos son del usuario.** Viven en su computador (`~/Alcancia`), en formato abierto. No hay servidores propios ni telemetría.
2. **Nunca pedimos la clave del banco** ni entramos al sitio de un banco con el usuario y la clave de la persona (nada de "scraping").
   Lo automático va por dos caminos: **conectores** a APIs oficiales con una llave que la persona crea ella misma en el servicio
   (guardada en el Llavero, solo lectura) y la **carpeta vigilada** (las cartolas que descarga se agregan solas). Las finanzas
   abiertas oficiales de cada país se suman cuando existan y no exijan un servidor nuestro (Chile: CMF, desde julio de 2027).
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
| `bin/conectores/` | Un módulo por servicio con API oficial (`INFO`, `probar`, `movimientos`). `bin/red.py` hace los pedidos HTTPS (solo a los dominios de cada conector). `bin/sincronizar.py probar|traer <conector>` los usa; `bin/vigilar.py` es la carpeta vigilada. |
| `bin/mcp_servidor.py`, `bin/mcp_conectar.py` | Servidor MCP de solo lectura (stdio, JSON-RPC, sin dependencias) para que la IA de la persona consulte sus finanzas, y el script que lo registra en Claude Desktop, Claude Code, Codex/ChatGPT, Gemini CLI y Antigravity (con su comando oficial o editando su JSON con respaldo). |
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
- **Conectores:** la app guarda la llave en el Llavero y se la pasa a `sincronizar.py` por la **entrada estándar** (nunca en un
  archivo, un argumento ni el entorno); una llave nueva vuelve por la salida estándar (`CREDENCIAL {json}`). `red.py` no sigue
  redirecciones (se llevarían la llave a otro dominio) y la IA corre sin variables `ALCANCIA_*`. Al revisar cambios, mirar justo eso. `probar` revisa la llave y registra las cuentas en `cuentas.json` (campo `conector`);
  `traer` pide desde la última vez menos 10 días (o `dias_inicio` la primera vez), guarda sin duplicar con
  `id = sha1(conector|cuenta|id del servicio)` y categoriza igual que una cartola. El estado sin secretos queda en
  `.alcancia/conexiones.json`. La app revisa sola al abrir y cada 6 horas.
- **Carpeta vigilada:** `vigilar.py activar` marca desde cuándo; `vigilar.py <carpeta>` importa los CSV/XLSX/OFX nuevos que reconozca
  una receta, una sola vez cada uno (por huella), y anota los que no sabe leer. Nunca borra ni mueve nada. En Mac la llama un
  `DispatchSource` sobre `~/Downloads` cuando la carpeta queda quieta 5 segundos.
- **Formatos estándar:** `recetas.py` lee sin receta OFX/QFX (`xx-ofx`, `FITID` como id), CAMT.053 (`xx-camt053`, `CdtDbtInd` da el
  signo, solo `BOOK`) y QIF (`xx-qif`, el orden día/mes se deduce de las fechas o del país).
- **MCP:** las herramientas (`resumen_del_mes`, `gastos_por_categoria`, `buscar_movimientos`, `principales_comercios`, `comparar_meses`,
  `presupuesto`, `cuentas_y_datos`) solo leen ~/Alcancia y nunca devuelven ids internos. Agregar una herramienta: función + entrada en
  `HERRAMIENTAS` con su esquema y `readOnlyHint`, prueba en `test_python.py` (clase `Mcp`). La app corre `mcp_conectar.py reparar` al
  abrirse para que las IA conectadas sigan apuntando a la ruta actual de la app.
- **docs/conectar.html** se genera con `herramientas/generar_conectar.py` desde `bin/conectores` (las pruebas revisan que esté al día).
- **Consejos:** `consejos.py <hoy>` arma un prompt con totales y exige las tres secciones (`### Lo que va bien`, `### Ojo con`,
  `### Para esta semana`). Si no vienen, no se guarda nada.

## Puente interfaz ↔ app
La UI llama `host.enviar(accion, datos)` y la app responde con `window.Alcancia.<funcion>(json)`. En el navegador, `simular()` responde
con datos ficticios. Acciones: `listo, config, probarIA, elegirCartola, vistaCartola, aprenderReceta, guardarReceta, importar,
categoria, regla, presupuesto, pedirConsejos, abrirEnlace, abrirCarpeta, conectar, sincronizar, desconectar, vigilar, mcpConectar,
buscarActualizacion, actualizar`. Respuestas: `estado, iaProbada, cartolaElegida, vistaLista, recetaAprendida, importarProgreso,
importado, consejosListos, conectado, sincronizado, importadoSolo, mcpListo, actualizacionRevisada, actualizacionProgreso`. `pruebas/contrato.py` revisa que cada acción exista en `Ventana.swift` (y en Windows/Linux cuando exista), que cada
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
nuevas se validan con `recetas.validar` y se prueban con una cartola **ficticia** que imite el formato. Un **conector nuevo** es
código con red: solo API oficial documentada, llave creada por la persona, solo lectura, solo sus dominios en `INFO["hosts"]`, sin
dependencias, con prueba contra el servidor falso (`pruebas/servidor_falso.py`) y entra como `beta` hasta que alguien lo use con su
cuenta real. Detalle en `CONTRIBUTING.md`.
