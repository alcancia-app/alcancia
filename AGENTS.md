# Alcancía — guía para trabajar en el proyecto

> Para personas y para cualquier IA de programación (Claude Code, Codex, Gemini/Antigravity…). `CLAUDE.md` y `GEMINI.md` solo
> importan este archivo: la guía es una sola.

Alcancía es una app de control de gastos personal. La persona agrega las cartolas de sus bancos y billeteras (CSV, Excel o PDF con texto); Alcancía
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
| `bin/` | Python **solo biblioteca estándar**. `datos.py` (formato en disco, ids, escritura atómica), `recetas.py` (validar, detectar y aplicar recetas; lee CSV y .xlsx sin librerías), `pdf.py` (texto de un PDF con posiciones → tabla), `categorizar.py` (reglas, comercios conocidos, IA), `resumen.py` (cuentas del mes, proyección, alertas, presupuesto sugerido, historia de 6 meses, periodos de sueldo a sueldo), `compromisos.py` (validar, reconocer pagos, estado del mes, avance de deudas, gasto máximo, sugerir, avisos; palabras en `compromisos_conocidos.json`), `ia.py` (`preguntar()` con la IA del usuario). Scripts que llama la app: `estado.py` (todo lo que pinta la interfaz), `importar.py`, `receta_ia.py`, `compromiso_ia.py`, `consejos.py`, `compromisos.py avisos` y `guardar.py` (categoría, regla, presupuesto, receta, compromiso; lo de la interfaz llega en un archivo JSON de entrada). El último argumento siempre es la ruta del JSON de salida. |
| `bin/conectores/` | Un módulo por servicio con API oficial (`INFO`, `probar`, `movimientos`). `bin/red.py` hace los pedidos HTTPS (solo a los dominios de cada conector). `bin/sincronizar.py probar|traer <conector>` los usa; `bin/vigilar.py` es la carpeta vigilada. |
| `bin/mcp_servidor.py`, `bin/mcp_conectar.py` | Servidor MCP de solo lectura (stdio, JSON-RPC, sin dependencias) para que la IA de la persona consulte sus finanzas, y el script que lo registra en Claude Desktop, Claude Code, Codex/ChatGPT, Gemini CLI y Antigravity (con su comando oficial o editando su JSON con respaldo). |
| `recetas/` | Recetas incluidas en la app (solo las probadas con una cartola real) y `README.md` con el formato. |
| `ui/` | Interfaz web única (`app.js`, `app.css`), `demo.json` (ficticio, se genera con `herramientas/generar_demo.py`) e `idiomas/en.json`. |
| `docs/` | Página pública (GitHub Pages). `pagina.yml` la publica junto a `ui/` en `/demo/`. |
| `pruebas/` | `correr.sh` (todo), `test_python.py`, `interfaz.mjs` (Playwright), `casos.json` (casos compartidos Python ↔ JS), `ia_falsa.py`, `datos/` (cartola ficticia). |
| `herramientas/` | `revisar_privacidad.sh`, `generar_demo.py`, `generar_pdf_prueba.py` (las cartolas PDF ficticias de `pruebas/datos/`). |
| `ejemplos/` | Scripts para construir encima del formato abierto. |
| `app/` | App de Mac (SwiftPM, macOS 15, sin proyecto de Xcode). `AlcanciaApp.swift` (arranque y barra de menú), `Ventana.swift` (WKWebView + puente: un `case` por acción), `Servicios.swift` (rutas, config, idioma, IA del usuario, `Procesador.correrJSON`), `Actualizaciones.swift` (GitHub Releases o `git pull` en un checkout de desarrollo), `Avisos.swift` (notificaciones de compromisos). |
| `build.sh`, `herramientas/empaquetar.sh` | Arman `dist/Alcancia.app` (con Python portátil verificado por SHA-256 y bin/, ui/, recetas/ adentro) + zip + `.sha256`; `build.sh` la instala en `~/Applications`. |

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
  `{"ok": false, "error", "parcial"}` (`parcial`: solo los campos válidos) y la interfaz abre el editor con eso: nunca sin salida.
  Un movimiento con categoría `transferencia` solo paga compromisos de tipo `transferencia`.
  Avisos (Mac): `compromisos.py avisos <hoy>` decide (3 días antes, el día, atrasado; uno por compromiso al día, registro en
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
  (cuota hacia abajo, la última ajusta; interés simple % sobre el total), `completar_prestamo` (día del sueldo o 25). `estado_mes`
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
  lateral con «+ Agregar» arriba. Abre una hoja con: una cartola (`importar`), un pago que se repite («Cuéntale a Alcancía», `E.agregar =
  "contar"`) y conectar una cuenta. El editor de compromisos es un diálogo (`#editor-comp`). En celular los diálogos salen desde abajo.
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

## Puente interfaz ↔ app
La UI llama `host.enviar(accion, datos)` y la app responde con `window.Alcancia.<funcion>(json)`. En el navegador, `simular()` responde
con datos ficticios. Acciones: `listo, config, probarIA, elegirCartola, vistaCartola, aprenderReceta, guardarReceta, importar,
categoria, categoriaNueva, saldo, regla, presupuesto, pedirConsejos, abrirEnlace, abrirCarpeta, conectar, sincronizar, desconectar, vigilar, mcpConectar,
buscarActualizacion, actualizar, compromisoIA, compromiso, avisos`. Respuestas: `estado, iaProbada, cartolaElegida, vistaLista,
recetaAprendida, importarProgreso, importado, consejosListos, conectado, sincronizado, importadoSolo, mcpListo, actualizacionRevisada,
actualizacionProgreso, compromisoEntendido`. `pruebas/contrato.py` revisa que cada acción exista en `Ventana.swift` (y en Windows/Linux cuando exista), que cada
función que llama la app exista en `window.Alcancia` y que los scripts que llama existan. Una acción nueva va en `ui/app.js`, en `Ventana.swift`
y simulada en `simular()`.

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
