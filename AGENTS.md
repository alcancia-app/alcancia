# Alcancía — guía para trabajar en el proyecto

> Para personas y para cualquier IA de programación (Claude Code, Codex, Gemini/Antigravity…). `CLAUDE.md` y `GEMINI.md` solo
> importan este archivo: la guía es una sola.

Alcancía es una app de control de gastos personal. La persona agrega las cartolas de sus bancos y billeteras (CSV, Excel o PDF con texto); Alcancía
las lee con una **receta** por banco, las guarda sin duplicar, las categoriza (reglas aprendidas → comercios conocidos → la IA del
usuario) y muestra cuánto lleva gastado, a qué ritmo va y qué categoría se pasa del presupuesto. La IA del usuario (Claude Code, Codex
o Gemini, con su propia cuenta) también da consejos. Interfaz web única; app de escritorio para Mac (Windows y Linux en camino) y
app del celular (iPhone y Android, `movil/`, fase 1: para mirar, con la copia cifrada que deja el Mac en la nube de la persona).

**Principios que no se negocian**
1. **Los datos son del usuario.** Viven en su computador (`~/Alcancia`), en formato abierto. No hay servidores propios ni telemetría.
   Al celular llegan como una copia cifrada con una frase de la persona, en su propia nube (nunca por un servidor nuestro).
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
| `bin/` | Python **solo biblioteca estándar**. `nucleo.py` (pieza «nucleo»: `app.json`, carpeta de datos, config validada, escritura atómica), `datos.py` (formato en disco, ids y config de Alcancía sobre `nucleo`), `recetas.py` (validar, detectar y aplicar recetas; lee CSV y .xlsx sin librerías), `pdf.py` (texto de un PDF con posiciones → tabla), `categorizar.py` (reglas, comercios conocidos, IA), `resumen.py` (cuentas del mes, proyección, alertas, presupuesto sugerido, historia de 6 meses, periodos de sueldo a sueldo), `compromisos.py` (validar, reconocer pagos, estado del mes, avance de deudas, gasto máximo, sugerir, avisos; palabras en `compromisos_conocidos.json`), `ia.py` (pieza «ia»: `preguntar()` con la IA del usuario, `probar`, `frase()`), `tu_ia.py` (los errores de la IA en palabras, con dónde se elige en Alcancía), `compromiso_ia.py` (`limpiar_texto` y los campos de un compromiso explicados para la IA). Scripts que llama la app: `estado.py` (todo lo que pinta la interfaz), `importar.py`, `receta_ia.py`, `chat.py` (conversar con Alcancía), `consejos.py`, `compromisos.py avisos` y `guardar.py` (categoría, regla, presupuesto, receta, compromiso; lo de la interfaz llega en un archivo JSON de entrada). El último argumento siempre es la ruta del JSON de salida. |
| `bin/conectores/` | Un módulo por servicio con API oficial (`INFO`, `probar`, `movimientos`). `bin/red.py` hace los pedidos HTTPS (solo a los dominios de cada conector). `bin/sincronizar.py probar|traer <conector>` los usa; `bin/vigilar.py` es la carpeta vigilada. |
| `bin/mcp_servidor.py`, `bin/mcp_conectar.py` | Servidor MCP de solo lectura (stdio, JSON-RPC, sin dependencias) para que la IA de la persona consulte sus finanzas, y el script que lo registra en Claude Desktop, Claude Code, Codex/ChatGPT, Gemini CLI y Antigravity (con su comando oficial o editando su JSON con respaldo). |
| `recetas/` | Recetas incluidas en la app (solo las probadas con una cartola real) y `README.md` con el formato. |
| `ui/` | Interfaz web única (`app.js`, `app.css`), `i18n.js` (pieza «i18n»: `T`, `Thtml`, `Tp`, `tr`, `traducirDOM`, paquetes de idioma validados), `host.js`, `tema.css`/`tema.js` y `componentes.css`/`componentes.js` (piezas de interfaz, ver «Piezas»), `copia.js` (la copia cifrada para el celular: el mismo código cifra en el Mac y abre en el teléfono), `demo.json` (ficticio, se genera con `herramientas/generar_demo.py`) e `idiomas/en.json`. |
| `docs/` | Página pública (GitHub Pages). `pagina.yml` la publica junto a `ui/` en `/demo/`. |
| `CHANGELOG.md` | Lo que cambia para quien usa la app, en palabras simples (ver «Lo que rodea a un cambio»). |
| `pruebas/` | `correr.sh` (todo), `test_python.py`, `interfaz.mjs` (Playwright), `copia.mjs` (cifrado de la copia para el celular, en Node), `movil.mjs` (la app del celular de punta a punta con `capacitor_falso.js`), `contrato.py`, `casos.json` (casos compartidos Python ↔ JS), `ia_falsa.py`, `datos/` (cartola ficticia). |
| `herramientas/` | `revisar_privacidad.sh`, `generar_demo.py`, `generar_pdf_prueba.py` (las cartolas PDF ficticias de `pruebas/datos/`). |
| `ejemplos/` | Scripts para construir encima del formato abierto. |
| `app/` | App de Mac (SwiftPM, macOS 15, sin proyecto de Xcode). `AlcanciaApp.swift` (arranque y barra de menú), `Ventana.swift` (WKWebView + puente: un `case` por acción), `Servicios.swift` (rutas, config, idioma, IA del usuario, `Procesador.correrJSON`), `Actualizaciones.swift` (GitHub Releases o `git pull` en un checkout de desarrollo), `Avisos.swift` (notificaciones de compromisos), `Celular.swift` (la copia para el celular: carpeta de la nube, llave en el Llavero y cuándo escribir). |
| `app.json`, `piezas.json` | **Pieza** (ver «Piezas» abajo): `app.json` describe la app para las piezas (id, carpeta de datos, plataformas, claves de config); `piezas.json` lo escribe `pieza.py`. |
| `movil/` | App del celular (Capacitor 7, iOS + Android, `app.alcancia.movil`): `armar.mjs` (arma `www/` con `ui/` y `host/`), `host/` (el anfitrión del teléfono), `plugins/carpeta/` (Swift + Kotlin), `ios/`, `android/`, `README.md` (compilar y probar). Ver «App del celular». |
| `build.sh`, `herramientas/empaquetar.sh` | Arman `dist/Alcancia.app` (con Python portátil verificado por SHA-256 y bin/, ui/, recetas/ adentro) + zip + `.sha256`; `build.sh` la instala en `~/Applications`. |

## Piezas (de [Pieza](https://github.com/pieza-app/pieza))
Alcancía usa piezas de Pieza, la base de la familia de apps: código probado que se copia a la app (modelo «copiar y adueñarse»).

| Pieza | Archivos | Qué usa Alcancía |
|---|---|---|
| `nucleo` | `bin/nucleo.py` | `app.json`, carpeta de datos, config validada por `app.json` (`limpiar_config`), escritura atómica, `recursos()`. `datos.py` lo envuelve con lo propio: `~/Alcancia` 0700, archivos **siempre** 0600 (`nucleo.PRIVADO`), `CONFIG_INICIAL` y los ajustes con forma propia (`CONFIG_OBJETOS`: `inicio_mes`, `uf`, que valida quien los usa). |
| `ia` | `bin/ia.py` | La IA de la persona (`preguntar`, `probar`, `comando`, `elegida`, `nombre`, `frase`). Los errores son `{codigo, plantilla, valores}`: los scripts responden con `tu_ia.respuesta(error)` / `tu_ia.frase(error)` (`bin/tu_ia.py`: la frase de la pieza más dónde se elige la IA en Alcancía) y el código. Un CLI que no conoce `--strict-mcp-config` o `--disallowedTools` no corre (error `actualizar`). Lo propio (prompts, `limpiar_texto`, validar respuestas) sigue en `categorizar.py`, `consejos.py`, `chat.py`, `compromiso_ia.py` y `receta_ia.py`. El Mac prueba la IA con `ia.py probar <entrada {ia}> <salida>` (`Procesador.conEntrada`). |
| `i18n` | `ui/i18n.js` | `T`, `Thtml`, `Tp`, `tr`, `frase`, `traducirDOM` (`app.js` crea la instancia; `E.idioma` es un espejo de `i18n.idioma`). `ui/index.html` la carga antes de `app.js`; `movil/armar.mjs` copia `ui/` entera y revisa que esté. `ui/idiomas/en.json` lleva `codigo` y `nombre`. |
| `host-ui` | `ui/host.js` | El puente: `host = PiezaHost.crearHost({nombre: "alcancia", global: "Alcancia", simular})`, `HOST = host.plataforma` (de `window.ALCANCIA_HOST`, queda en `<html data-host>`). Las respuestas van con `host.responder({…})` (quedan en `window.Alcancia`); `_pruebas` (no es función) va aparte. Mensaje `{accion, datos}`; en la vista previa los datos llegan a `simular()` como copia JSON. |
| `tema` | `ui/tema.css`, `ui/tema.js` | Tokens con `light-dark()`: `app.css` solo define los pares de Alcancía (`--fondo-claro`/`--fondo-oscuro`…, la tabla está en el README de la pieza). `--texto-suave` (antes `--suave`), `--panel-2` (antes `--lateral`); `--acento-suave`, `--rojo-suave` y `--hover` son derivados. «Apariencia» en Ajustes (`config.tema`: sistema, claro u oscuro; en el celular es un ajuste del teléfono) y `?tema=` en la vista previa. |
| `componentes` | `ui/componentes.css`, `ui/componentes.js` | `ui = PiezaComponentes.crear({…})`: diálogos (`caja()` → `ui.dialogo`; la pantalla de idioma y el chat usan el mismo marco con su cabeza, `cajaPropia()`), Esc/velo/✕ → `cerrarDialogo()`, foco con `ui.despuesDePintar()` en cada `render()`, avisos en cola (`toast(frase, {valores})` = `ui.aviso`, sobre la barra inferior con `--pz-toast-abajo`; los que llegan antes de elegir el idioma esperan), «Tu IA» (`ui.filasIA`, `probarIA {ia}`), actualizaciones (`ui.filaActualizacion` en Ajustes y en el aviso de arriba) y «Acerca de» con «Enviar comentarios». Clases `pz-boton`, `pz-principal`, `pz-plano`, `pz-peligro`, `pz-pie`, `pz-izq`; `app.css` solo ajusta (botones de 44 px, un solo botón naranjo: probar una IA es secundario). En el celular (`LECTURA`) no se pintan «Tu IA» ni actualizaciones. |

- **La carpeta de siempre:** `app.json` dice `"datos": {"carpeta": "~/Alcancia/.alcancia"}` (donde siempre estuvo `config.json`) y
  `"privado": true` (todo archivo 0600). Con `ALCANCIA_CARPETA` (pruebas, desarrollo) `datos.py` le pasa la misma carpeta a
  `nucleo` (`ALCANCIA_DATOS`). Nunca cambies `id` ni `datos` sin migrar.
- Las claves simples de config son las de `app.json` y las mismas de `Config.permitidas` en `Servicios.swift` (la prueba `Piezas`
  lo revisa); `inicio_mes` y `uf` las valida el Mac al guardarlas y Python al usarlas.
- `app.json` va dentro de la app (`herramientas/empaquetar.sh`): `bin/nucleo.py` lo busca junto a `bin/`.
- **No edites a mano los archivos de una pieza.** Se actualizan con «Pieza al día» (`.github/workflows/pieza-al-dia.yml`, una vez por
  semana abre un PR o un issue) o con `python3 <pieza>/herramientas/pieza.py actualizar .`. Si hay que cambiar algo, el cambio va
  primero a Pieza (`pieza.py diferencias . <pieza>` lo muestra) y vuelve desde allá; `pieza.py estado .` dice si algo quedó distinto.
- No adoptadas todavía: `bienvenida` (la de Alcancía tiene el camino del celular, «Trae tus datos», y pruebas propias) y
  `actualizaciones` (en Mac pide un target propio de SwiftPM y no es para el celular).

## Cómo funciona
- **Importar:** `importar.py vista <archivo> [receta]` detecta la receta (la que reconoce más encabezados) y devuelve una muestra sin
  guardar nada. `importar.py guardar <archivo> <receta> <ia 0|1>` aplica la receta, categoriza con reglas y comercios, guarda con
  `datos.agregar` (por id: `sha1(cuenta|fecha|descripción normalizada|monto|ocurrencia)`) y, si se pidió, completa categorías con la IA.
  El avance queda en `~/Alcancia/.alcancia/estado.json`.
- **Sin receta:** `receta_ia.py <archivo> <país>` muestra a la IA las primeras 25 filas, valida la receta que propone y la prueba con el
  mismo archivo. No guarda nada: la app la guarda (`.alcancia/recetas/`) cuando la persona confirma que los movimientos se ven bien.
  Compartir es opcional y abre un issue prellenado en el catálogo con **solo la receta**.
- **Resumen:** la misma lógica en `bin/resumen.py` y en `ui/app.js` (`resumen`, `historia`, `presupuestoSugerido`, `reglaPara`), probada con
  `pruebas/casos.json`. Si cambias una regla, cambia los dos lados y el caso. La proyección sigue el ritmo solo de lo variable
  (3+ gastos en el mes, categoría no `fijo`); lo fijo y lo esporádico queda como está. `historia` (Python) / `historia` (JS) da los
  6 meses que terminan en el mes elegido (total o una categoría, con su tope y el promedio de los meses anteriores con datos): el
  desglose de «Lo que gastaste» en el Inicio y la historia de una categoría (en Movimientos, al filtrar por ella).
  `consejos.py` le pasa a la IA solo esos totales.
- **Inicio (resumen):** arriba a la izquierda, una sola cifra protagonista (`heroe`/`cuantoQueda`): «Te quedan $X hasta tu sueldo»
  (o «hasta fin de mes»), con «N días · ~$Y por día», la escala de días del periodo y el ritmo en una línea (`lineaRitmo`). Es
  **Lo que tienes** − lo que falta pagar este periodo (`estado_mes.pendiente_max`); sin saldo conocido, lo que entró − lo gastado − lo
  que falta pagar. Solo presentación: usa `loQueTienes`, `resumen`, `estadoCompromisos` y `proximoSueldo`. Al tocarla se explica el
  cálculo (`desgloseQueda`, con lo que detecté de tu sueldo). Debajo, `lineaAlDia` (lo que falta pagar, una línea; rojo solo si está
  atrasado) y la fila compacta de **Lo que tienes** (`resumen.lo_que_tienes` / `loQueTienes`), **Lo que gastaste** (`resumen` con
  `cargos`: compras con crédito en cuotas cuentan por la cuota del mes; las devoluciones descuentan) y **Lo que debes** este mes
  (`compromisos.lo_que_debes` / `loQueDebes`: compromisos pendientes y atrasados, créditos con lo que queda, tarjeta desde el último
  pago —`PAGO_TARJETA`, igual en los dos lados— y cuotas futuras; el total y «Te deben» van en el desglose). Tocar una cifra abre (y
  cierra) su desglose; «Lo que gastaste» abre la comparación con los últimos 6 meses. Probado con `pruebas/casos.json` (sección
  `tres_cifras`). Después, «En qué se fue» (5 categorías con su tope sutil; todas con «Ver las N») y **una** tarjeta «Pendientes»
  (`pendientesHTML`) con lo que pide algo: el sueldo que no llega o «¿Cuándo te pagan?», los sin categoría (a «Por ordenar»), «Aprendí
  esto de tus movimientos» (reglas sugeridas con `reglasSugeridas`: un comercio que siempre tuvo la misma categoría y tiene movimientos
  sin ella, y sugerencias de compromisos), la invitación a anotar pagos y lo pagado en intereses por atraso. Los consejos, una fila al
  final. MCP `resumen_del_mes` trae `tres_cifras` y `consejos.py` una línea con ellas: solo totales.
- **Categorizar:** cada movimiento tiene un chip; el panel (`pickerHTML`/`elegidor`) pone primero la categoría que ese comercio suele
  tener (`categoriaSugerida`), luego las del tipo correcto y las más usadas, con búsqueda y «Crear «X»» (emoji sugerido; acción
  `categoriaNueva`, que crea y asigna en una sola llamada). Al elegir, aviso discreto «¿Siempre … para «X»?» (acción `regla`).
  «Por ordenar» (`vistaOrdenar`) muestra los sin categoría uno a uno: 1–9 elige, → salta, ← vuelve, / busca. Se llega desde el chip
  «Por ordenar N» de Movimientos (filtra los sin categoría) y desde «Pendientes» en el Inicio.
- **Compromisos:** `~/Alcancia/compromisos.json` (formato en el README). La misma lógica en `bin/compromisos.py` y `ui/app.js`
  (`vencimientos`, `coincide`, `asignar`, `estado_mes`/`estadoCompromisos`, `gasto_maximo`/`gastoMaximo`, `llegadas_sueldo`), probada
  con `pruebas/casos.json` (sección `compromisos`). Un pago se reconoce con signo, moneda, monto ±tolerancia y una palabra de `buscar`
  (o monto exacto), entre 10 días antes y 7 después (hasta 20 si es mensual o anual: pago atrasado); un movimiento cuenta para un solo compromiso (lo marcado a mano primero, luego
  las parejas más cercanas en fecha y monto); un vencimiento anterior a `desde` solo con un pago anterior a `desde`. `estado.py`
  anota los reconocidos (`fijar_automaticos`) y manda las sugerencias; `importar.py` y `sincronizar.py` devuelven `detectados` (solo
  lo nuevo). Sugerir (solo Python): 3 de los últimos 4 meses con monto ±10 % y día ±4, o una palabra de `compromisos_conocidos.json`;
  la cuota «N/M» sale de la descripción. Nunca se agregan solos. `compromiso_ia.py entender <entrada.json>` (el texto llega en un archivo, nunca como argumento) le pasa a la IA solo el texto
  (`limpiar_texto` quita RUT con guion o K, 8–9 dígitos con dígito verificador válido que no terminan en «000», lo que va después
  de rut/cuenta/cta/tarjeta/n°/nro/número/cuentarut/vista y 10+ dígitos; los montos como «2000000» pasan), la fecha y las
  categorías, y valida estricto (`validar(..., estricto=True)`); no guarda nada. Si la IA falla o su respuesta no pasa, devuelve
  `{"ok": false, "error", "parcial"}` (`parcial`: solo los campos válidos): nunca sin salida. La app ya no lo llama (lo de
  «Cuéntale» va por `chat.py`, que usa sus mismas piezas); queda para scripts.
  Un movimiento con categoría `transferencia` solo paga compromisos de tipo `transferencia`.
  **Se paga solo:** `pago` (`automatico`/`manual`, opcional) y `modo_pago`/`modoPago`: lo dicho manda; si no, palabras de
  `compromisos_conocidos.json` (`automatico`, llegan a la interfaz en el estado, `palabras_automatico`) en el nombre o `buscar` →
  automático; deuda, préstamo, cuenta, suscripción y transferencia → manual; `otro` e ingresos → null (se recuerda, sin etiqueta).
  `estado_mes` da a cada ítem `modo_pago` y, a un automático vencido, `esperando` los primeros `GRACIA_AUTO` (3) días y después
  `atrasado` («No vimos el cargo»). Los automáticos no llevan «Ya lo pagué» (`seCobraSolo`) ni avisos salvo `sin_cargo`; los totales
  los cuentan igual. `sugerir` y `compromiso_ia.py` traen `pago`. Casos en `pruebas/casos.json` (sección `pago`).
  Avisos (Mac): `compromisos.py avisos <hoy>` decide (3 días antes, el día, atrasado; lo automático solo `sin_cargo`; uno por compromiso al día, registro en
  `.alcancia/avisos.json`) y `Avisos.swift` muestra, sin montos y con título genérico (con la pantalla bloqueada solo «Tienes un pago por vencer»). El permiso se pide al agregar el primer compromiso o al activar los avisos.
- **Aproximados y UF:** `aproximado` ({variacion} o {min, max}) y `moneda: "UF"`. `en_moneda`/`enMoneda` da a cada ítem `monto` y
  `moneda` para sumar (en UF, pasado a la moneda principal), `rango` y `original` (lo anotado en UF, el valor usado y de dónde salió,
  o `sin_valor`: queda en UF y no se suma). El valor de la UF (`valores_uf`/`valoresUF`) sale del último pago reconocido de ese
  compromiso; si no hay, el más reciente entre `config.uf` (Ajustes) y otro compromiso en UF pagado. Nunca hay red para esto. El
  rango en UF se abre `uf.variacion_mensual` (1,5 %) por mes desde ese valor, más la variación del compromiso. Reconocer: un
  aproximado calza en su rango solo si trae una palabra de `buscar` (sin palabras, monto exacto); uno en UF calza por sus palabras y,
  con un valor en Ajustes, por el monto ±15 %. Totales `_max` (gasto máximo y «Lo que debes» usan el máximo; los ingresos, el mínimo).
  Casos en `pruebas/casos.json` (sección `aproximados`).
- **Interés por mora:** `asignar` reconoce pagos mensuales/anuales hasta `ATRASO_MAX` (20) días tarde y, ya vencidos, más altos
  que el tope (`coincide_tarde`/`coincideTarde`, hasta +30 %, con palabras). Con `palabras_mora` (de `compromisos_conocidos.json`,
  llegan a la interfaz en el estado) `_moras`/`moras` anotan `pago.mora` {monto, dias, movimiento?}; `fijar_automaticos` lo guarda y
  deja el cargo en la categoría `intereses` (nueva predeterminada; `datos.NUEVAS` la suma a un categorias.json de antes).
  `mora_del_anio`/`moraDelAnio` para el Resumen y los consejos. Casos en `pruebas/casos.json` (sección `mora`).
- **Préstamos:** tipo `prestamo` con `con` y `prestamo` {total, interes, cuota, ultima}. `calcular_prestamo`/`calcularPrestamo`
  (cuota hacia abajo, la última ajusta; interés simple % sobre el total; una `cuota` fija se respeta si calza y la última es lo que falta), `completar_prestamo` (día del sueldo o 25). `estado_mes`
  usa `ultima` en la última cuota; `lo_que_debes`/`loQueDebes` suman lo que debes y aparte `te_deben` (signo `ingreso`), que nunca se
  resta. Consejos y MCP reciben solo esos totales. Casos en `pruebas/casos.json` (sección `prestamos`). Compromisos y sugerencias se
  agrupan por tipo (`GRUPOS_COMP`); Movimientos puede agrupar por comercio (`reglaPara`, `E.agruparMov`).
- **Tu mes (periodos):** `config.inicio_mes` = `{"modo": "dia" | "sueldo", "dia"}`. `resumen.rango(mes, per)` da los días de un
  periodo «AAAA-MM» (se llama por el mes donde cae la mayor parte); `per` lleva las `llegadas` del sueldo (compromisos.periodo).
  `resumen`, `historia`, `presupuesto_sugerido`, `estado_mes` y `gasto_maximo` reciben `per` (sin él, mes calendario, igual que
  antes). En la interfaz, `per()` se calcula una vez por pintada; selector, resumen, movimientos, presupuesto, compromisos y
  consejos/MCP usan el periodo. Los CSV de movimientos siguen por mes calendario.
- **Sueldo detectado:** `detectar_sueldo`/`detectarSueldo` (casos «sueldo»). Si `inicio_mes` no existe en config,
  `compromisos.aplicar_sueldo` (desde `estado.py`) guarda `{"modo": "sueldo", "dia", "auto": true}`, crea el compromiso de sueldo
  (`origen: "detectado"`, `desde` = primera llegada) y categoriza las llegadas (regla solo si su clave no calza con otros
  movimientos). Con `auto`, sigue el día típico; lo que la persona elige en Ajustes (sin `auto`) nunca se toca. `periodo_actual`
  hace lo mismo en memoria (MCP, consejos); `sueldoSolo()` en la interfaz, para el navegador. Con llegadas, `per.hoy` activa la
  espera: pasado el día de siempre sin llegada, el mes anterior sigue hasta 7 días (`inicio_periodo`/`inicioPeriodo`).
  Días hábiles: `bin/feriados.json` (datos, se actualiza cada año; llega a la interfaz en el estado, `feriados`), `regla_habil`
  (anterior por defecto; «siguiente» si las llegadas lo muestran) y `proximo_sueldo`/`proximoSueldo` (`atrasado` = pasó un día
  hábil sin llegar → «¿Aún no te pagan?» en el Resumen, que se cierra por ese día).
- **Conectores:** la app guarda la llave en el Llavero y se la pasa a `sincronizar.py` por la **entrada estándar** (nunca en un
  archivo, un argumento ni el entorno); una llave nueva vuelve por la salida estándar (`CREDENCIAL {json}`). `red.py` no sigue
  redirecciones (se llevarían la llave a otro dominio) y la IA corre sin variables `ALCANCIA_*`. Al revisar cambios, mirar justo eso. `probar` revisa la llave y registra las cuentas en `cuentas.json` (campo `conector`);
  `traer` pide desde la última vez menos 10 días (o `dias_inicio` la primera vez), guarda sin duplicar con
  `id = sha1(conector|cuenta|id del servicio)` y categoriza igual que una cartola. El estado sin secretos queda en
  `.alcancia/conexiones.json`. La app revisa sola al abrir y cada 6 horas. Opcional por conector: `saldo(cred, red)` (Mercado Pago,
  Up, Akahu, SimpleFIN) → `cuentas.json` `saldo` con `origen: "conector"` en `probar` y `traer`; si falla, no rompe nada. Un
  movimiento puede traer `medio`/`cuotas`/`cuota` (columnas opcionales del CSV) y `datos.completar` los agrega a lo ya guardado por id.
  Al subir `REPARACIONES` (hoy 3), un conector con `RELEER_DIAS` vuelve a pedir ese rango una vez para completar lo guardado.
- **Carpeta vigilada:** `vigilar.py activar` marca desde cuándo; `vigilar.py <carpeta>` importa los CSV/XLSX/PDF/OFX nuevos que reconozca
  una receta, una sola vez cada uno (por huella), y anota los que no sabe leer. Nunca borra ni mueve nada. En Mac la llama un
  `DispatchSource` sobre `~/Downloads` cuando la carpeta queda quieta 5 segundos.
- **PDF:** `bin/pdf.py` (solo biblioteca estándar) recorre los objetos del PDF sin confiar en la xref, abre `/ObjStm`, descomprime
  FlateDecode/ASCIIHex/ASCII85, interpreta los operadores de texto (Tm, Td, TD, T*, Tj, TJ, ', ", cm, q/Q, Do) y decodifica con
  WinAnsi/MacRoman (+ `/Differences`) o el CMap `/ToUnicode` (Type0/Identity-H). Agrupa el texto en filas por `y` y celdas por la
  distancia en `x`, y alinea las filas con la fila de encabezados (la de la receta, si se la pasan). `recetas.leer_tabla` lo usa
  cuando la extensión es `.pdf`, así detectar, aplicar, `receta_ia.py` y la carpeta vigilada funcionan igual que con un CSV. Un PDF
  cifrado, escaneado o roto da un `pdf.PdfError` con un mensaje listo para mostrar. En la carpeta vigilada, un PDF que ninguna receta
  reconoce queda como `ignorado` (en Descargas hay boletas y pasajes; no se avisa por cada uno). Pruebas con
  `pruebas/datos/cartola_ejemplo*.pdf` (ficticias, salen de `herramientas/generar_pdf_prueba.py`).
- **Formatos estándar:** `recetas.py` lee sin receta OFX/QFX (`xx-ofx`, `FITID` como id), CAMT.053 (`xx-camt053`, `CdtDbtInd` da el
  signo, solo `BOOK`) y QIF (`xx-qif`, el orden día/mes se deduce de las fechas o del país).
- **MCP:** las herramientas (`resumen_del_mes`, `gastos_por_categoria`, `buscar_movimientos`, `principales_comercios`, `comparar_meses`,
  `presupuesto`, `compromisos`, `cuentas_y_datos`) solo leen ~/Alcancia y nunca devuelven ids internos. Agregar una herramienta: función + entrada en
  `HERRAMIENTAS` con su esquema y `readOnlyHint`, prueba en `test_python.py` (clase `Mcp`). La app corre `mcp_conectar.py reparar` al
  abrirse para que las IA conectadas sigan apuntando a la ruta actual de la app.
- **docs/conectar.html** se genera con `herramientas/generar_conectar.py` desde `bin/conectores` (las pruebas revisan que esté al día).
- **Primer uso:** lo primero es el idioma. El paso 0 de `bienvenida()` (`pasoIdioma`) ofrece «Español» y «English», cada uno en su
  idioma, con el del equipo sugerido y enfocado; elegir guarda `idioma_ui` por el mismo `config` que Ajustes y sigue la bienvenida ya
  traducida. Quien hizo la bienvenida antes (`bienvenida: true`) no la repite; quien eligió idioma y la dejó a medias sigue desde el
  saludo. Nada pregunta ni avisa antes de esa pantalla (ver «App de Mac»).
- **Conversar con Alcancía (chat):** `chat.py enviar|marcar|borrar <entrada.json>`. «Cuéntale a Alcancía» (`E.agregar = "contar"`,
  `dialogoChat`) se abre desde «+» («Un pago que se repite»), «Anotar un pago» en Pagos y la fila «Pregúntale a Alcancía» del Inicio.
  La interfaz manda los últimos 10 mensajes (`{hoy, mensajes: [{rol, texto}]}`); `chat.py` los pasa por `limpiar_texto` y arma un
  contexto **calculado por código** (`contexto`): periodo y días que quedan, `margen_mensual` (ingreso típico − gasto típico sin pagos
  de compromisos − compromisos vigentes al mes por su máximo), las tres cifras en totales y cada compromiso con una referencia opaca
  (C1, C2…), nombre, tipo, monto o rango, día, `modo_pago`, `buscar`, cuotas, estado del periodo y sus últimos 3 pagos con el
  vencimiento al que se asignaron. **Nunca** descripciones de movimientos, ids ni números de cuenta (en ellos busca el código,
  abajo). La IA responde `{"respuesta", "acciones"}`; se valida estricto y cada acción (lista blanca `ACCIONES`) se resuelve con código: `crear_compromiso`
  (`validar(estricto)`; si no pasa, `parcial` con `incompleto`), `plan_prestamos` (la IA solo da `{con, total, interes}`;
  `plan_prestamos` usa como máximo `USO_MARGEN` (75 %) del margen, busca los menos meses en que las cuotas redondeadas hacia arriba
  (`paso_cuota`) caben, y `inicio_plan` pone la primera el día después del próximo sueldo; las propuestas son préstamos con
  `prestamo.cuota` fija y `pago: "manual"`), `reasignar_pago` (`pago_reasignable`: el último vencimiento del periodo tiene pago y el
  anterior no; también si la IA dijo `marcar_pendiente`), `marcar_pagado`, `marcar_pendiente`, `editar_compromiso` (monto, día,
  pago, fecha_fin) y `buscar_pago` (abajo). Lo que no se pudo preparar vuelve como código en `notas` (la interfaz lo explica).
  **Nada se aplica solo:** cada acción es una tarjeta («Agregar», «Sí, corrígelo», «Cambiar» abre `#editor-comp`, «No») que usa la acción `compromiso` de siempre
  (nueva subacción `reasignar` en `guardar.py`: `reasignar_pago` mueve el pago con el formato de `pagos` de siempre y deja el
  movimiento en `no_es`). Sin IA instalada (`ia.comando(ia.elegida())`) devuelve `sin_ia` y la interfaz lleva a Ajustes. La conversación se
  guarda solo en `~/Alcancia/.alcancia/chat.json` (últimos 50, ya limpios, con lo que se hizo con cada acción en `estados`) y llega
  en el estado (`chat`). `margen_mensual`, `plan_prestamos`, `inicio_plan`, `pago_reasignable`, `reasignar_pago` y la cuota fija de
  `calcular_prestamo` viven igual en `ui/app.js` (`margenMensual`, `planPrestamos`, `inicioPlan`, `pagoReasignable`, `reasignarPago`,
  `calcularPrestamo`): casos en `pruebas/casos.json` (secciones `chat` y `prestamos.calcular_cuota`). En el navegador, `chatSimulado`
  responde con esa misma lógica.
  **¿Es el mismo préstamo?** Para que una deuda que ya está anotada no se cuente dos veces, `prestamos_parecidos`/`prestamosParecidos`
  busca, por cada préstamo propuesto (del plan o de `crear_compromiso`), un compromiso activo y vigente de tipo `prestamo` o `deuda`
  con el mismo signo y moneda: primero **la persona** (`claves_persona`: sin tildes, mayúsculas, «mi», «préstamo de», «don»…, con
  apodos juntados —«mami» = «mamá»—; calza si las claves de uno están todas en las del `con` del otro, «Tío Matías» ~ «Matías», o
  en el nombre del compromiso, «Crédito con papá»); si alguno de los dos no dice quién, un **préstamo** con el total anotado o lo que
  falta pagar a ±15 % (`PARECIDO`). Dos personas distintas nunca son la misma deuda. Un compromiso sirve para una sola propuesta.
  Si hay parecido, la acción trae `parecidos` (plan; uno por propuesta o null) o `parecido` (crear) y la tarjeta pregunta
  «Ya tienes anotado «X» ($ al mes, quedan N cuotas). ¿Es el mismo?» con «Es el mismo» / «Es otro» antes de ofrecer «Agregar»
  (en un plan, el resto espera sin botones: sus cifras pueden cambiar). «Es otro» → la propuesta de siempre. «Es el mismo» →
  «Actualizar» / «Cambiar» / «No» sobre el compromiso que ya estaba: en el plan, `plan_variante`/`planVariante` devuelve su cuota al
  margen (`margen_mensual(..., sin=ids)`), planifica lo que falta pagar (`por_pagar`, si el total dicho es parecido al anotado; si
  no, el total dicho) y recalcula **todas** las deudas; `prestamo_actualizado`/`prestamoActualizado` deja ese compromiso con su id,
  nombre, palabras y categoría, como préstamo que parte de nuevo desde `inicio_plan` (cuotas nuevas, sin cuotas pagadas). `chat.py`
  calcula **al responder** cada combinación de «es el mismo» (`variantes`, clave «0», «0,1»…; como mucho 2⁴) y la interfaz solo
  elige (`planElegido`): determinista, sin otra llamada y al reabrir se ve igual. En `crear_compromiso`, `actualizar` es el que ya
  estaba con el total, el interés y las cuotas de la propuesta (y día, cuotas pagadas o forma de pago solo si la IA los dijo; desde
  y pagos se mantienen), o null si no cambia nada o venía incompleto («Ya lo tienes anotado: no agrego otro»). La respuesta va en
  `estados` con la clave `es:<i>` o `es:<i>.<j>` («mismo»/«otro»; `chat.py marcar` solo la acepta donde hay parecido). «Actualizar»
  usa la subacción `actualizar_prestamo` de `guardar.py` (mismo id, solo a préstamo, validado, mantiene `pagos` y sí cambia
  `desde`); el editor también, si se abrió desde una actualización. El prompt pide a la IA que lo diga en `respuesta`, pero la
  detección es del código. Casos en `pruebas/casos.json` (`chat.parecido`).
  **Buscar un cobro en sus movimientos** (la IA nunca ve los movimientos: busca el código, solo en el computador). `palabras_busqueda`/
  `palabrasBusqueda` (palabras completas de 3+ letras, sin tildes, sin números sueltos, sin `GENERICAS` —PAGO, COMPRA…— ni
  `BUSCAR_VACIAS` —«de», «cobro», «mensual», «com»…) y `buscar_serie`/`buscarSerie` (casos `chat.buscar`): en los últimos 365 días,
  en la moneda principal (cartolas y conectores, p. ej. «Pago: Netflix.com» de Mercado Pago), los movimientos que traen alguna palabra
  (si alguno las trae todas, solo esos); la serie se arma desde el más reciente con el mismo signo y montos a ±10 %, al menos 2 meses
  distintos y no mucho más de uno al mes (un comercio frecuente no es un cobro); si hay varias, la activa (último cobro ≤ 45 días),
  luego la de más meses, luego la más reciente. Da monto (el último), día (el típico), `buscar` (la palabra que más calzó; empate, la
  más larga), categoría (la más usada), `desde` (el primer cobro) y `aproximado` si los montos variaron. Dos caminos en `chat.py`:
  (1) un `crear_compromiso` que no valida (sin monto o día), mensual, en la moneda principal y que no es préstamo se busca con su
  nombre y palabras (si dijo un monto, la serie tiene que estar a ±10 % de él) y se completa (`_desde_serie`: lo que la IA dijo bien se
  mantiene; `pago` con `modo_pago`) con `encontrado` {monto, dia, meses, veces, ultimas, aproximado?}; (2) la acción **`buscar_pago`**
  `{texto}` (pasa por `limpiar_texto`). Si ya hay un compromiso activo que es ese cobro (todas las palabras buscadas en su nombre o
  `buscar`, o `coincide` con un movimiento de la serie), la acción es `{"tipo": "buscar_pago", "anotado": {…, "ultimo"}}` (sin
  botones, con su último pago reconocido); si no hay nada, la nota `no_encontre_movimientos`. Cuando la búsqueda decide, la respuesta
  la arma el código sin otra llamada (`mensaje.busqueda` {resultado: «encontre»|«anotado»|«nada», nombre, monto, dia}; la interfaz la
  pinta en su idioma con `textoBusqueda` y `texto` queda en español para la conversación). Lo que vuelve a la IA en los turnos
  siguientes es solo esa frase (nombre, monto, día); nunca descripciones ni ids. El prompt le dice que la app puede buscar en sus
  movimientos (también los de Mercado Pago) y que nunca diga que no puede. La misma serie no se propone dos veces en un mensaje. En el
  navegador, `buscadoSimulado` usa `buscarSerie` con la demo («¿cuánto me cobran de internet? búscalo»).
- **Alcancía en tu celular (Mac):** Ajustes → «Alcancía en tu celular» (`seccionCelular`, asistente `dialogoCelular`): carpeta de
  la nube (acción `celular` {accion: «carpeta»} → `NSOpenPanel` → `celularCarpeta`), frase (`AlcanciaCopia.fuerzaFrase`, 12+
  caracteres y «Entiendo que sin esta frase…»). La interfaz deriva la llave (`nuevaCabecera`, WebCrypto) y manda `{accion:
  «activar», llave, cabecera}`: `Celular.swift` guarda **la llave, no la frase**, en el Llavero y el marcador de la carpeta en
  `UserDefaults` (nada de esto va a `config.json` ni al estado). Después de cada `estado`, `Celular.despuesDelEstado` llama
  `copiaCelular({llave, cabecera, forzar, anterior})`; la interfaz arma el contenido con lo que acaba de llegar (`E._crudo` →
  `AlcanciaCopia.paraCelular`, lista blanca), compara la huella y, si cambió (o `forzar`: 6 horas, «Copiar ahora», recién activada),
  lo cifra y devuelve `{accion: «escribir», texto, huella}`; Swift lo escribe de una vez (`.atomic`) y responde `celularEscrito`.
  Formato en el README («Copia para el celular»); pruebas en `pruebas/copia.mjs` y, del Mac (vista previa) al teléfono, en
  `pruebas/movil.mjs`. Si cambias lo que viaja, cambia `paraCelular`, el README y la prueba de «lo que viaja».
- **Consejos:** `consejos.py <hoy>` arma un prompt con totales y exige las tres secciones (`### Lo que va bien`, `### Ojo con`,
  `### Para esta semana`). Si no vienen, no se guarda nada.

## Interfaz: navegación, jerarquía y color
Diseño mobile first (la misma interfaz va a ir en una app de celular): pensar primero en 390 px y en el pulgar.
- **Cuatro secciones** (`SECCIONES`): **Inicio** (`resumen`), **Movimientos** (con «Por ordenar» como chip con contador; la vista
  `ordenar` cuelga de aquí), **Pagos** (la vista sigue llamándose `compromisos`: la app de Mac abre `E.vista = 'compromisos'` desde un
  aviso) y **Más** (`mas`: Conexiones, Presupuesto, Consejos, Ajustes y «Acerca de»). `SECCION_DE` dice qué sección queda marcada en
  las pantallas de segundo nivel, que llevan «‹ Más» o «‹ Movimientos» (`volver`).
- **Una sola acción para agregar** (`.nav-agregar`, `E.agregar`): en celular es el botón central de la **barra inferior fija** (zona
  del pulgar, 64 px de alto, respeta `env(safe-area-inset-bottom)`, objetivos de 44 px o más); en escritorio la barra pasa a ser
  lateral con «+ Agregar» arriba. Abre una hoja con: una cartola (`importar`), un pago que se repite (el chat «Cuéntale a Alcancía», `E.agregar =
  "contar"`, en celular a pantalla completa con el campo abajo) y conectar una cuenta. El editor de compromisos es un diálogo (`#editor-comp`). En celular los diálogos salen desde abajo.
- **Jerarquía:** una cifra protagonista por pantalla cuando la hay, tres niveles de texto como máximo (cifra · título · texto/detalle),
  cifras con `tabular-nums` y alineadas a la derecha, espacios en múltiplos de 4/8, líneas de ~70 caracteres como máximo, sin sombras
  ni bordes que no digan algo. Los textos que explican van al tocar (desgloses), no en la pantalla.
- **Regla de color:** base neutra (fondo, texto y un gris). Un solo color de acción, el naranjo de la marca (`--acento`): la acción
  principal y lo seleccionado (sección actual, cifra abierta, opción elegida, interruptor encendido). **Rojo** (`--rojo`) solo para lo
  atrasado o excedido; **verde** (`--verde`) solo para «al día» y lo que entra. Sin fondos rosados o ámbar. Las barras van en gris; la
  que se pasa del tope, en rojo. `pruebas/interfaz.mjs` revisa el contraste AA (4,5) del botón principal, el gris, el rojo y el verde
  en claro y oscuro.
- **Ruido fuera:** la moneda (`CLP`) solo aparece si hay movimientos en más de una moneda (`variasMonedas`). Los comercios se muestran
  legibles con `nombreComercio` (solo presentación: «DELIVERY RAPIDITO *PEDIDO» → «Delivery Rapidito»; lo guardado no cambia y la
  descripción original se ve al tocar la fila). Un movimiento sin categoría muestra un «+» gris discreto.

## App del celular (`movil/`)
- **El Mac es la fuente.** El celular (fase 1) solo mira: lee la copia cifrada (`ui/copia.js`) de la carpeta de la nube, la abre con
  la frase y pinta la misma interfaz con `ALCANCIA_HOST = "movil"` (`LECTURA` en `ui/app.js`). Nunca llaves de conectores, IA ni
  red: el manifiesto quita INTERNET y la CSP de `ui/index.html` no cambia (`armar.mjs` lo revisa).
- **Lo que cambia datos no se ofrece** en `LECTURA`: sin «+», chat, categorizar (el chip es un `span`), «Ya lo pagué», editar
  compromisos, saldo, presupuesto (solo lectura), consejos nuevos, conexiones ni importar; `app.css` oculta lo que quede
  (`html[data-host="movil"] …`) y un toque que igual llegue (`SOLO_MAC` en `ui/app.js`) solo muestra «Esto se hace en tu Mac por
  ahora». El anfitrión responde lo mismo a esas acciones (`SOLO_MAC` en `movil/host/host.js`). Al agregar algo que cambie datos,
  súmalo a los dos `SOLO_MAC` y a `app.css`; `pruebas/movil.mjs` revisa que nada así quede a la vista en ninguna pantalla.
- **Primer uso:** idioma (el mismo `pasoIdioma`), saludo y «Trae tus datos» (`vistaTraer`, `bv-traer`). Acción `traer`
  {accion: elegir | abrir {frase, recordar} | releer | olvidar | desconectar} → `traerRespuesta` y el estado (con `celular`:
  {estado: nuevo | frase | listo, archivo, generado, recordada, desactualizada, error}). Los ajustes del teléfono son solo
  `idioma_ui`, `bienvenida`, `avisos` y `tema` (plugin, no `localStorage`); el resto de `config` llega del Mac.
- **Avisos:** `avisosPagos` (lógica pura, en `_pruebas`) y `window.Alcancia.avisosCelular` (con el texto en el idioma elegido);
  el anfitrión los programa con `@capacitor/local-notifications` (ids de 31 bits, 9:00, máximo 60, `registerActionTypes` con el
  texto genérico de la pantalla bloqueada). El permiso se pide al activar «Avisarme antes de que venza un pago».
- **Plugin `Carpeta`** (`movil/plugins/carpeta`, Swift + Kotlin): `elegir`, `leer`, `olvidar`, `guardarCache`, `leerCache`,
  `guardarLlave`, `leerLlave`, `borrarLlave`, `guardarAjustes`, `leerAjustes`. Un método nuevo va en los dos lenguajes y en
  `pruebas/capacitor_falso.js` (el contrato lo revisa). Swift y Kotlin no compilan aquí: imita lo que ya compila y avisa.
- `armar.mjs` → `npx cap sync`; los proyectos `ios/` y `android/` se versionan (AndroidManifest, `data_extraction_rules.xml`,
  `variables.gradle`, Info.plist). Dependencias con versión exacta, `package-lock.json` y `.npmrc` con `ignore-scripts=true`; el
  workflow hace `npm ci`, `npm audit --audit-level=high` y `cap sync`.

## Puente interfaz ↔ app
La UI llama `host.enviar(accion, datos)` (pieza «host-ui») y la app responde con `window.Alcancia.<funcion>(json)`. En el navegador, `simular()` responde
con datos ficticios. Acciones: `listo, config, probarIA, elegirCartola, vistaCartola, aprenderReceta, guardarReceta, importar,
categoria, categoriaNueva, saldo, regla, presupuesto, pedirConsejos, abrirEnlace, abrirCarpeta, conectar, sincronizar, desconectar, vigilar, mcpConectar,
buscarActualizacion, actualizar, chat, compromiso, avisos, celular` (Mac) y `traer` (solo celular). `probarIA {ia}` → `iaProbada {ia, ok,
codigo, plantilla, valores, ayuda, texto}` y `actualizacionRevisada` lleva `notas` (forma de la pieza «componentes», que manda
`probarIA`, `buscarActualizacion`, `actualizar` y `abrirEnlace` por su cuenta; el contrato también lee `ui/componentes.js`). Respuestas: `estado, iaProbada,
cartolaElegida, vistaLista, recetaAprendida, importarProgreso, importado, consejosListos, conectado, sincronizado, importadoSolo, mcpListo,
actualizacionRevisada, actualizacionProgreso, chatRespuesta, copiaCelular, celularCarpeta, celularEscrito` y, del celular,
`traerRespuesta, avisosRespuesta, avisosCelular, soloEnMac`. Solo el marco principal cargado desde `ui/` puede usar el puente (`Ventana.swift`
revisa el origen) y la ventana nunca navega fuera de `ui/` (un enlace https se abre en el navegador). `pruebas/contrato.py` revisa que cada acción exista en `Ventana.swift` (y en Windows/Linux cuando exista), en
`movil/host/host.js` (`ACCIONES` o `SOLO_MAC`) y simulada en `simular()`; que cada función que llaman las apps exista en
`window.Alcancia`; que los scripts y los métodos nativos que llaman existan (plugins de iOS y Android y el Capacitor falso), y la
seguridad de la app del celular. Una acción nueva va en `ui/app.js`, en `Ventana.swift`, en `movil/host/host.js` y simulada en `simular()`.

## App de Mac
- Datos en `~/Alcancia`; el código va dentro de la app (`Contents/Resources/alcancia`) y los scripts corren con el Python portátil incluido
  (`ALCANCIA_RECURSOS` apunta ahí). La app nunca usa `ui/demo.json` (se quita al empaquetar).
- Arranque: menús y ventana de inmediato (en el idioma del sistema hasta que la persona elija). Lo que corre solo y puede mostrar algo
  o pedir un permiso del sistema (actualizaciones, conexiones con el Llavero, carpeta vigilada en Descargas, `mcp_conectar.py reparar`)
  parte en `AlcanciaApp.iniciarTareas()` solo cuando `Idioma.elegido` (los avisos de compromisos también, y su permiso se pide recién al
  agregar el primer compromiso o activarlos); en el primer uso, al guardarse `idioma_ui`. Cambiar el idioma
  rearma los menús y vuelve a mandar el estado.
- Lo que manda la interfaz no arma comandos: rutas de archivo se revisan, ids se filtran y los datos van en un JSON de entrada.
- Desarrollo en el Mac: `~/Developer/alcancia` es el checkout; `bash build.sh` (se niega si hay una importación en curso) e instala en
  `~/Applications/Alcancia.app`. Compilar solo: `cd app && swift build -c release`. Swift solo compila en un Mac (o en el job `mac` de GitHub).

## Reglas al cambiar cosas
- Código, comentarios, commits y textos en **español** (de Chile neutro). Todo texto nuevo visible va con su traducción en
  `ui/idiomas/en.json` en el mismo cambio, como frase completa con marcadores (`T("Llevas {g}…", {g})`), nunca pedazos pegados.
- Contenido del usuario y dinero con `esc()` y `data-sin-traducir`. `T()` ya escapa sus valores (no les pongas `esc()`); `Thtml()`
  es solo para HTML que arma el código (un monto en `<span>`, una cifra en `<b>`) con lo de la persona ya escapado, y `Tp()` es
  texto plano (avisos con `toast`, que usa `textContent`).
- Archivos de piezas (`bin/nucleo.py`, `bin/ia.py`, `ui/i18n.js`, `ui/host.js`, `ui/tema.*`, `ui/componentes.*`): no se editan aquí; ver «Piezas».
- No cambies el formato de los datos (README, "Formato de los datos") sin compatibilidad. Hay gente con scripts que dependen de él.
- Antes de cerrar un cambio: `bash pruebas/correr.sh` y mirar la interfaz (`cd ui && python3 -m http.server 8765`, `?idioma=en`,
  `?bienvenida`, `?vacio`, `window.Alcancia._probar(E => …)`), también a ancho de celular.
- Seguridad (detalle en `SECURITY.md`): lo que viene de afuera se escapa con `esc()` (también emojis e ids de categorías), sin
  scripts ni manejadores en línea (la CSP de `ui/index.html` los bloquea: `script-src 'self'`). Archivos importados con límites
  (`recetas.MAXIMO_ARCHIVO`, partes de un .xlsx, XML sin DTD ni entidades → `recetas.ArchivoNoValido`). La IA corre sin
  herramientas ni MCP (`claude --disallowedTools "*" --strict-mcp-config`, `codex -s read-only`), sin variables `ALCANCIA_*` y Claude
  sin la memoria de la persona (`SIN_MEMORIA_CLAUDE`) y con `--safe-mode` si su versión lo conoce (`ia._soporta`); sin `--strict-mcp-config` o `--disallowedTools` no corre. `~/Alcancia` queda 0700 y
  los archivos 0600 (`datos.carpeta_privada`, `nucleo.PRIVADO`). En los guiones que arma Swift, todo lo variable va con `comillas()`.
  Workflows: actions fijadas por SHA con su versión en un comentario (Dependabot con `cooldown`), `permissions` mínimos,
  `persist-credentials: false`, nunca `pull_request_target` ni `${{ github.event.* }}` dentro de `run:` (va por `env:`).
- Privacidad: `bash herramientas/revisar_privacidad.sh` antes de cada commit (usa `.terminos-privados`, local y nunca versionado).
  Jamás subas una cartola real, ni siquiera "para probar": las pruebas usan `pruebas/datos/cartola_ejemplo.csv`.
- Commits con autor `@users.noreply.github.com`. El repo es público: cada commit se ve al tiro.

## Lo que rodea a un cambio
Un cambio está listo cuando la app **y lo que la cuenta** dicen lo mismo. Antes de empezar, anota qué tipo de cambio es; al terminar,
revisa cada fila ("no aplica" se decide, no se supone):

| Si el cambio… | Deja al día |
|---|---|
| agrega o cambia una función | la página (`docs/`: funciones, «cómo funciona», comparación, preguntas frecuentes), el README y la guía si la hay |
| cambia lo que se ve | capturas de la página y del README (datos ficticios, español e inglés, normal y celular) e imagen para compartir si sale esa vista |
| cambia un flujo o un paso | instrucciones paso a paso, preguntas frecuentes, textos de la bienvenida e instalación si la toca |
| quita algo | bórralo de la página, el README y las guías: nada que prometa lo que ya no hace |
| cambia el formato de datos o el puente | la documentación del formato, `ejemplos/` si existe y esta guía |
| cambia carpetas, reglas o pruebas | esta guía (`AGENTS.md`) y `CONTRIBUTING.md` |
| actualiza o agrega una pieza | `piezas.json` (lo escribe `pieza.py`), la tabla «Piezas» de esta guía y `app.json` si pide config |
| resuelve un issue | ciérralo con «Resuelto en …» dando crédito y abre issues para lo que quedó pendiente |
| lo nota quien usa Alcancía | `CHANGELOG.md`: una línea en «Sin publicar», en lenguaje de persona («Ahora puedes…»), en español e inglés |

Todo texto nuevo de la página y del README va en los dos idiomas, sin nada inventado. Antes de cerrar, busca con `grep` en `docs/` y el
README el nombre o el texto viejo de lo que cambió. Al publicar una versión, las líneas de «Sin publicar» pasan a su número.
Los issues que abrimos para una tarea traen una sección «Qué actualizar alrededor» con las filas de esta tabla que le tocan.

## Revisar aportes
Todo entra por pull request y lo junta quien mantiene el proyecto, solo con su aprobación. Leer todo el diff antes de correr nada
(alerta roja: workflows, scripts de instalación, red nueva, dependencias nuevas, binarios, cualquier cosa que lea claves). Las recetas
nuevas se validan con `recetas.validar` y se prueban con una cartola **ficticia** que imite el formato. Un **conector nuevo** es
código con red: solo API oficial documentada, llave creada por la persona, solo lectura, solo sus dominios en `INFO["hosts"]`, sin
dependencias, con prueba contra el servidor falso (`pruebas/servidor_falso.py`) y entra como `beta` hasta que alguien lo use con su
cuenta real. Detalle en `CONTRIBUTING.md`.
