<p align="center"><img src="docs/img/logo.png" width="96" alt="Alcancía"></p>

<h1 align="center">Alcancía</h1>

<p align="center"><b>Control de gastos para quienes nos cuesta medirnos.</b><br>
Juntas las cartolas de tus bancos y billeteras, Alcancía las ordena y tu propia IA te avisa a tiempo cuando algo se está pasando.<br>
Gratis, de código abierto y con tus datos en tu computador.</p>

<p align="center"><a href="https://alcancia-app.github.io/alcancia/">Sitio</a> ·
<a href="https://alcancia-app.github.io/alcancia/demo/">Vista previa</a> ·
<a href="https://github.com/alcancia-app/alcancia/discussions">Comunidad</a> ·
<a href="CONTRIBUTING.md">Cómo aportar</a> ·
<a href="#english">English</a></p>

---

## Qué hace
- **Lee la cartola de cualquier banco o billetera del mundo** (CSV, Excel, PDF con texto, OFX/QFX, QIF o CAMT.053). Cada banco tiene una *receta*: un archivo corto que dice
  cómo leer su cartola. Si tu banco aún no está, **tu IA aprende a leerlo** y puedes compartir la receta con la comunidad.
- **Movimientos que llegan solos:** conexiones oficiales con una llave que creas tú (Mercado Pago, PayPal, Stripe, Buda.com, bancos
  de EE. UU. y Canadá con SimpleFIN, Up en Australia, Akahu en Nueva Zelanda… y las que sume la comunidad), y la **carpeta vigilada**:
  descargas la cartola de cualquier banco y Alcancía la agrega sola. Nunca con la clave de tu banco.
- **Pregúntale a tu propia IA:** Alcancía trae un servidor MCP, así que Claude, ChatGPT (app y Codex) o Gemini en tu computador pueden
  consultar tus finanzas («¿cuánto gasté en delivery este mes?»). Se conecta con un clic en Conexiones.
- **No duplica nada:** puedes subir la misma cartola dos veces, o cartolas que se traslapan.
- **Pone las categorías sola:** primero lo que tú le enseñaste, después comercios conocidos y al final tu IA.
- **Te dice si vas bien:** cuánto llevas gastado, a qué ritmo vas y qué categoría se te está pasando, antes de que termine el mes,
  y cómo vas comparado con tus últimos 6 meses (en total y por categoría).
- **Te da consejos concretos:** tu IA mira tus números y te deja lo que va bien, a qué ponerle ojo y algo para hacer esta semana.
- **Compromisos: que no se te olvide nada.** Anota lo que pagas o recibes seguido (dividendo, arriendo, créditos, cuentas,
  suscripciones, transferencias, tu sueldo) escribiéndolo con tus palabras («el arriendo vence el 5, son 450.000») o a mano.
  Alcancía **reconoce el pago en tu cartola**, te muestra lo que falta pagar este mes (y lo atrasado primero), el avance de tus
  deudas («te quedan 187 de 240 cuotas») y, en Mac, te avisa antes de que venza. Al agregar una cartola detecta lo que parece un
  compromiso (se repite cada mes o la descripción lo delata: dividendo, cuota 53/240, PAC, seguro…) y te pregunta; nunca lo agrega solo.
- **Montos que varían y en UF:** marca un compromiso como aproximado («≈ $480.000, entre $465.000 y $495.000») o anótalo en UF
  (un dividendo): Alcancía estima cuánto es en pesos con lo que pagaste antes, sin conectarse a ningún lado.
- **Préstamos entre personas:** «mi tía me prestó 1.800.000 en 12 cuotas» o «le presté 850 lucas a Matías en 5»: Alcancía calcula
  la cuota (la última ajusta el redondeo), cuándo terminas y lo que te queda. Lo que te deben se muestra aparte («Te deben») y no se
  resta de lo que debes. Si tu IA no entiende algo, se abre el editor con lo que sí entendió para que lo completes.
- **Todo más ordenado:** compromisos y sugerencias agrupados por tipo con su subtotal mensual, y en Movimientos puedes agrupar por
  comercio (total y cuántas veces, con el detalle al abrirlo).
- **Gasto máximo sugerido:** lo que entra − tus compromisos − tus otros gastos fijos = lo que puedes gastar en lo variable,
  repartido por categoría según lo que gastas normalmente.
- **Tu mes empieza cuando te pagan** (si quieres): el mes puede ir de sueldo a sueldo; si te pagan antes, parte ese día.

## Tus datos son tuyos
- Todo queda en tu computador, en una carpeta con archivos abiertos (CSV y JSON) que puedes abrir con Excel o llevarte adonde quieras.
- **No hay servidores de Alcancía**, ni cuentas, ni publicidad, ni telemetría.
- La IA es **la tuya** (Claude Code, Codex o Gemini), con tu propia cuenta, y solo ve lo necesario: descripciones y montos para
  categorizar, y totales por categoría para los consejos. Nunca tus claves ni tus números de cuenta.
- Alcancía **nunca te pide la clave de tu banco**. Las cartolas las descargas tú.
- *Muy pronto:* respaldo **con candado** en tu nube (iCloud Drive, Google Drive, OneDrive, Dropbox) o en tu GitHub/GitLab: cifrado
  en tu computador, con una llave que solo tú tienes.

## Estado
Versión 0.1, recién nacida. Ya funcionan el motor (leer cartolas, recetas, categorías, resumen y consejos), la interfaz y la app de
Mac (todavía sin versión publicada: por ahora se compila desde el código, ver abajo). Windows y Linux vienen en camino. Puedes [ver la interfaz con datos ficticios](https://alcancia-app.github.io/alcancia/demo/).

## Cómo funciona
```
cartola.csv / .xlsx / .pdf ──► receta del banco ──► movimientos/AAAA-MM.csv ──► reglas + comercios + tu IA ──► resumen y consejos
                            (o tu IA crea una)        (sin duplicar)              (categorías)
```

## Formato de los datos
Todo vive en `~/Alcancia/` (en Windows, `C:\Users\<tú>\Alcancia`). Es un formato abierto: puedes armar tus propios scripts encima
(ver [`ejemplos/`](ejemplos/)). Si lo cambiamos, será de forma compatible y avisando.

| Archivo | Qué guarda |
|---|---|
| `movimientos/AAAA-MM.csv` | Un archivo por mes. Columnas: `id, fecha, descripcion, monto, moneda, categoria, cuenta, origen, nota`. `monto` negativo = gasto, positivo = ingreso, con punto decimal. `id` identifica el movimiento para no duplicarlo. Opcionales, **al final y solo si algún movimiento del mes las usa**: `medio` (`saldo`, `debito`, `credito` u `otro`: cómo se pagó, lo dice el conector), `cuotas` (en cuántas cuotas, 2 o más) y `cuota` (cuánto es cada una, con intereses; vacío = monto / cuotas). Lee las columnas por nombre (como `csv.DictReader`) y tus scripts siguen funcionando. |
| `categorias.json` | `[{"id", "nombre", "emoji", "tipo": "gasto" \| "ingreso" \| "neutro", "fijo"}]`. `neutro` = entre tus cuentas (no cuenta como gasto); `fijo` = se paga una vez al mes. |
| `presupuesto.json` | `{"moneda": "CLP", "mensual": {"<categoria>": tope}}` |
| `reglas.json` | `[{"contiene": "TEXTO", "categoria": "<id>"}]`: lo que Alcancía aprende cuando corriges una categoría. |
| `cuentas.json` | `[{"id", "nombre", "receta", "moneda", "saldo"}]`. `saldo` es opcional: `{"monto", "fecha", "origen"}`, el último saldo que se conoce de la cuenta. `origen` = `conector` (lo informa el servicio, p. ej. el disponible de Mercado Pago), `cartola` (la columna de saldo de la última fila) o `persona` (lo anotaste tú). Ver [Las tres cifras](#tres-cifras). |
| `consejos/AAAA-MM-DD.md` | Los consejos de tu IA. |
| `compromisos.json` | Lo que pagas o recibes seguido. Ver [Compromisos](#compromisos-formato). |
| `cuentas.json` (cont.) | Las cuentas que vienen de una conexión llevan `"conector"` en vez de `"receta"`. |
| `.alcancia/config.json` | Ajustes. Entre ellos `inicio_mes`: `{"modo": "dia" \| "sueldo", "dia": 25}` (tu mes parte el día 1 o cuando llega tu sueldo), `avisos` (`true` si quieres avisos de tus compromisos) y `uf`: `{"valor": 39500, "fecha": "AAAA-MM-DD", "variacion_mensual": 1.5}` (el valor de la UF que escribiste y cuánto puede variar al mes). |
| `.alcancia/` | Ajustes de la app, `avisos.json` (qué avisos ya se mostraron), recetas descargadas o creadas por ti, `conexiones.json` (estado de cada conexión, sin llaves) y `vigilar.json` (cartolas ya revisadas en Descargas). Las llaves de las conexiones viven en el Llavero de tu sistema, nunca en esta carpeta. |

### Las tres cifras del Resumen
<a id="tres-cifras"></a>
- **Lo que tienes** (hoy): la suma de los saldos de tus cuentas. Para cada cuenta se usa el último saldo conocido (`cuentas.json`,
  campo `saldo`) más los movimientos de los días siguientes. Si un conector sabe pedir el saldo a su API oficial, se guarda en cada
  sincronización (`origen: "conector"`): en **Mercado Pago** es el saldo disponible que muestra su app (`available_balance` de
  `/users/{id}/mercadopago_account/balance`); también Up, Akahu y SimpleFIN. Si no, la persona lo anota una vez y Alcancía sigue con
  los movimientos; cuando lo corrige, dice si había una diferencia con lo que calculaba y parte desde el saldo corregido. Las compras
  con crédito no mueven el saldo (van a la tarjeta). Sin ningún saldo, la app invita a anotarlo: nunca muestra un cero inventado.
- **Lo que gastaste** (en tu mes): los gastos, sin lo de «Entre mis cuentas». Una compra con crédito en cuotas cuenta por la cuota de
  cada mes (la primera, el día de la compra); una devolución (un monto positivo con categoría de gasto) descuenta de esa categoría.
- **Lo que debes** (hoy): lo que falta pagar de tus compromisos este mes (y lo atrasado), lo que te queda de cada crédito (cuotas
  que faltan × cuota, o el saldo que anotaste), lo comprado con crédito desde el último pago de tarjeta (un movimiento que diga
  «PAGO TARJETA», «PAGO TC»…; nunca más atrás que el mes anterior) y las cuotas que vienen de compras en cuotas. Muestra aparte lo
  que toca pagar este mes.

**Devoluciones de Mercado Pago:** lo devuelto queda como un movimiento aparte, «Devolución: …», positivo, en la fecha de la
devolución y con la categoría de la compra (si ya la tenía); su id sale de «<pago>|devolucion», así nunca se duplica.

### Compromisos (formato)
<a id="compromisos-formato"></a>
`compromisos.json` = `{"formato": 1, "compromisos": [...], "descartados": ["CLAVE", ...]}`. Cada compromiso:

| Campo | Qué es |
|---|---|
| `id` | `c-` + letras y números. |
| `nombre` | Hasta 60 caracteres. Nunca un número de cuenta: las secuencias de 6 o más dígitos se quitan al guardar. |
| `tipo` | `deuda`, `cuenta`, `suscripcion`, `transferencia`, `prestamo`, `ingreso` u `otro`. |
| `con`, `prestamo` | Solo en `prestamo`: con quién (un nombre, sin números) y `{"total", "interes", "cuota", "ultima"}`: lo prestado, el interés simple en % sobre el total (0 si no hay), la cuota y la última cuota (ajusta el redondeo). `monto` = `cuota`; `cuotas_total` es obligatorio y `fecha_fin` se calcula. `signo: "gasto"` = te prestaron; `"ingreso"` = tú prestaste (te deben). |
| `signo` | `gasto` o `ingreso`. |
| `monto`, `moneda` | Monto positivo y código de 3 letras, o `"UF"` con el monto en UF (hasta 4 decimales, p. ej. `12.75`). |
| `aproximado` | Opcional, para montos que varían: `{"variacion": 3}` (± ese porcentaje) o `{"min": 465000, "max": 495000}` (en la moneda del compromiso; el monto va entre los dos). Se muestra «≈ $480.000 (entre $465.000 y $495.000)» y el pago se reconoce en todo el rango. |
| `frecuencia` | `mensual` (con `dia` 1–31; si el mes es más corto, el último día), `semanal` (`dia` 1 = lunes … 7 = domingo), `anual` o `una_vez` (con `fecha` AAAA-MM-DD). |
| `categoria` | Id de una categoría (o vacío). |
| `buscar` | Palabras para reconocer el pago en la cartola (sin tildes ni mayúsculas). Sin palabras, se reconoce por el monto exacto. |
| `tolerancia` | Cuánto puede variar el monto, en % (por defecto 5). |
| `cuotas_total`, `cuotas_pagadas` | Opcionales. Las pagadas son las de antes de `desde`; cada pago reconocido después suma una. |
| `fecha_fin`, `saldo` | Opcionales: cuándo termina y lo que te queda por pagar (como lo anotaste). |
| `activo` | `false` = en pausa (ni se recuerda ni se busca). |
| `desde` | Desde qué día cuenta (AAAA-MM-DD). Un vencimiento anterior solo se da por pagado si ya estaba pagado. |
| `origen` | `manual`, `detectado` (salió de tu cartola) o `ia` (lo entendió tu IA). |
| `pagos` | Por periodo (`AAAA-MM` en mensual, `AAAA` en anual, la fecha en semanal y una vez): `{"como": "automatico", "fecha", "movimiento", "monto"}` cuando se reconoció en la cartola, `{"como": "manual", "fecha"}` cuando marcaste «ya lo pagué», y `"no_es": ["<id de movimiento>"]` cuando dijiste «no es este». |

`descartados` son las sugerencias que dijiste que no son compromisos. **Cómo se reconoce un pago:** el movimiento del signo
correcto, en la moneda del compromiso, con el monto dentro de la tolerancia y alguna palabra de `buscar`, entre 10 días antes y 7
después del vencimiento. Un movimiento cuenta para un solo compromiso: primero lo marcado a mano y después las parejas que calzan
mejor (más cerca de la fecha, luego del monto). La lista de palabras que delatan un compromiso (dividendo, crédito, cuota, PAC,
seguro, arriendo, colegio, plan celular…) es solo datos: [`bin/compromisos_conocidos.json`](bin/compromisos_conocidos.json), por país.

Un movimiento con categoría `transferencia` (entre tus cuentas) solo puede pagar un compromiso de tipo `transferencia`.

### Préstamos
Con `total` y `cuotas_total`, la cuota es `total × (1 + interes/100) ÷ cuotas` redondeada hacia abajo y la última se lleva la
diferencia, así la suma da justo. Si no dices el día, el primer pago cae el día de tu sueldo (`inicio_mes` en modo sueldo) o el 25.
Lo que queda se calcula con las cuotas pagadas. Los préstamos que hiciste suman en «Te deben», aparte de «Lo que debes».

### Montos aproximados y en UF
Un compromiso con `aproximado` muestra un rango y su pago se reconoce si cae dentro de él (o dentro de la tolerancia de siempre) y trae alguna de sus palabras; sin palabras, solo el monto exacto.
Uno en **UF** (`moneda: "UF"`) se paga en pesos, así que Alcancía **estima** cuánto es, sin conectarse a ningún lado: usa el valor
de la UF que sale del último pago reconocido de ese compromiso (pesos pagados ÷ UF); si aún no hay pagos, el más reciente entre el
que escribiste en Ajustes («Valor de la UF hoy») y el que sale del pago de otro compromiso en UF. Como la UF sube de a poco, el rango
se abre ±1,5 % por cada mes desde ese valor (configurable en Ajustes) más la variación del compromiso: «12,75 UF ≈ $490.000 –
$506.000». **Es una estimación, no el valor oficial.** Si no hay cómo estimarlo, se muestra «12,75 UF (aún no sé cuánto es en
pesos)» y no entra en los totales. Un pago en UF se reconoce por sus palabras (`buscar`) y, si escribiste el valor de la UF, también
por el monto (±15 %). En «Lo que debes» y el gasto máximo sugerido, lo aproximado cuenta por su máximo (y los ingresos por su
mínimo), para no quedarte corto. Al detectar un pago que varía mes a mes, se propone como aproximado; si parece un dividendo o la
descripción dice UF, se pregunta «¿Se paga en UF?».

### Tu mes: de sueldo a sueldo
Con `inicio_mes` en modo `sueldo` y el día en que te pagan (p. ej. 25), cada «mes» va de sueldo a sueldo y se llama como el mes
donde cae la mayor parte (si te pagan del 16 en adelante, el mes en que termina: «noviembre» = 25 oct – 24 nov; si te pagan del 2
al 15, el mes en que parte). Si anotaste tu sueldo como compromiso (tipo `ingreso`, categoría `sueldo`), el mes parte el día que
de verdad llegó, si llegó entre 12 días antes y 7 después del día de siempre. Los bonos e ingresos extra cuentan en el mes en que
caen. Los archivos `movimientos/AAAA-MM.csv` no cambian: siguen por mes calendario.

## Cartolas en PDF
Algunos bancos solo entregan la cartola en PDF. Alcancía lee los PDF **con texto** (los que genera el banco, no los escaneados) sin
librerías: saca el texto con su posición, lo arma como tabla (filas por altura, columnas alineadas con la fila de encabezados) y lo
pasa por la receta del banco, igual que un CSV. Si tu banco no tiene receta, tu IA ve las primeras filas de esa tabla y aprende a
leerla. Un PDF escaneado (una foto) o protegido con clave no se puede leer: Alcancía te lo dice y te sugiere descargar la cartola
en CSV o Excel, o guardar el PDF sin clave.

## Recetas: cada banco del mundo
Una receta es un JSON de **solo datos** (nunca código), así que cualquiera puede agregar su banco sin programar. El formato está en
[`recetas/README.md`](recetas/README.md) y el catálogo comunitario vive en
[alcancia-app/alcancia-catalogo](https://github.com/alcancia-app/alcancia-catalogo). ¿Tu banco no está? Abre la app, agrega la cartola
y deja que tu IA aprenda a leerla: al final te ofrece compartir **solo la receta**, nunca tus movimientos.

## Conexiones automáticas
Casi ningún banco deja que una persona use su propia API todavía, así que Alcancía junta todo lo que sí existe, siempre con
**conexiones oficiales y una llave que creas tú** (nunca tu usuario y clave del banco):

| Servicio | Dónde | Qué trae | Ojo |
|---|---|---|---|
| Mercado Pago | AR, BR, CL, CO, MX, PE, UY | Pagos hechos y recibidos (últimos 12 meses) | La llave da acceso completo a la cuenta (no existe una de solo lectura). Beta. |
| PayPal | Todo el mundo | Movimientos de 3 años | Solo cuentas Business. Beta. |
| Stripe | Todo el mundo | Cobros, comisiones y transferencias | Llave restringida de solo lectura. Beta. |
| Buda.com | CL, PE, CO | Depósitos y retiros en pesos/soles | Llave de solo lectura. Beta. |
| SimpleFIN | EE. UU. y Canadá | Miles de bancos | Servicio aparte, US$1,50 al mes. Beta. |
| Up | Australia | Todas tus cuentas | Token personal de solo lectura. Beta. |
| Akahu | Nueva Zelanda | Casi todos los bancos | App personal gratuita. Beta. |

*Beta* = funciona con la API oficial y pasa las pruebas, pero falta que alguien lo use con su cuenta real. Si lo pruebas, cuéntanos.
Para todo lo demás está la **carpeta vigilada**: descargas la cartola como siempre y Alcancía la agrega sola. Cuando tu país tenga
finanzas abiertas oficiales (en Chile, la CMF parte en julio de 2027), las sumamos. Guía paso a paso:
[alcancia-app.github.io/alcancia/conectar.html](https://alcancia-app.github.io/alcancia/conectar.html). ¿Conoces otra API oficial?
Mira [Agregar un conector](CONTRIBUTING.md#agregar-un-conector-conexión-automática).

## Tu IA, fuera de Alcancía (MCP)
`bin/mcp_servidor.py` es un servidor [MCP](https://modelcontextprotocol.io) de **solo lectura**: corre en tu computador, lo abre tu
IA cuando lo necesita y no tiene servidores ni puertos abiertos. Herramientas: `resumen_del_mes`, `gastos_por_categoria`,
`buscar_movimientos`, `principales_comercios`, `comparar_meses`, `presupuesto`, `compromisos` (qué está pagado, pendiente o
atrasado este mes) y `cuentas_y_datos`. En la app: **Conexiones → Tu IA,
fuera de Alcancía → Conectar** (Claude Desktop, Claude Code, ChatGPT/Codex, Gemini CLI y Antigravity). A mano:
```bash
claude mcp add --scope user alcancia -- python3 ~/Developer/alcancia/bin/mcp_servidor.py
codex mcp add alcancia -- python3 ~/Developer/alcancia/bin/mcp_servidor.py
gemini mcp add -s user alcancia python3 ~/Developer/alcancia/bin/mcp_servidor.py
```
Lo que tu IA consulta viaja a tu proveedor de IA con tu cuenta, igual que si se lo escribieras.

## Instalar en Mac (desde el código)
Necesitas macOS 15 y las herramientas de Xcode (`xcode-select --install`).
```bash
git clone https://github.com/alcancia-app/alcancia ~/Developer/alcancia
cd ~/Developer/alcancia && bash build.sh      # compila, arma la app con su propio Python y la instala en ~/Applications
open ~/Applications/Alcancia.app
```
La app no está firmada por Apple todavía: si macOS avisa, ve a Ajustes del Sistema → Privacidad y seguridad → «Abrir igualmente».

## Desarrollo
Necesitas Python 3 (solo biblioteca estándar) y Node para las pruebas de la interfaz.
```bash
cd ui && python3 -m http.server 8765        # interfaz con datos ficticios: http://localhost:8765 (?idioma=en, ?bienvenida, ?vacio)
python3 bin/importar.py vista cartola.csv /tmp/salida.json   # probar una cartola (no guarda nada)
bash pruebas/correr.sh                      # todas las pruebas
```
Lee [`AGENTS.md`](AGENTS.md) antes de cambiar algo: sirve igual para personas y para tu IA.

## Licencia
[AGPL-3.0](LICENSE). Puedes usar, estudiar, cambiar y compartir Alcancía. Si la ofreces como servicio o la distribuyes modificada,
tienes que publicar tu código con la misma licencia: así nadie puede tomarla y venderla cerrada.

---

## English
**Alcancía** ("piggy bank") is a free, open-source spending tracker for people who struggle to keep their spending in check. Add
statements from any bank or wallet in the world (CSV, Excel or text-based PDF); Alcancía sorts them without duplicates, your own AI (Claude Code,
Codex or Gemini, with your account) fills in categories and gives you concrete tips, and you see in time when a category is running
over budget. Commitments (rent, loans, bills, subscriptions, salary) can be added in your own words; Alcancía spots each payment in
your statements, shows what's still due (overdue first), tracks loan installments, suggests a spending limit for day-to-day
expenses and, on Mac, reminds you before things are due. Your month can run from payday to payday. Your data stays on your computer in open files: no servers, no accounts, no ads, and it never asks for your bank
password. Each bank is supported through a data-only *recipe* (plus OFX, QIF and CAMT.053 out of the box); if yours is missing, your AI
learns it and you can share just the recipe with the community. Transactions can also arrive automatically: official APIs with a key
you create (Mercado Pago, PayPal, Stripe, Buda.com, SimpleFIN for US/Canada banks, Up, Akahu) and a watched Downloads folder. A
read-only local MCP server lets your own AI (Claude, ChatGPT/Codex, Gemini) answer questions about your finances. Spanish-first, English included. Licensed under AGPL-3.0.
