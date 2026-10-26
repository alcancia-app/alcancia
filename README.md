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
- **Lee la cartola de cualquier banco o billetera del mundo** (CSV o Excel). Cada banco tiene una *receta*: un archivo corto que dice
  cómo leer su cartola. Si tu banco aún no está, **tu IA aprende a leerlo** y puedes compartir la receta con la comunidad.
- **No duplica nada:** puedes subir la misma cartola dos veces, o cartolas que se traslapan.
- **Pone las categorías sola:** primero lo que tú le enseñaste, después comercios conocidos y al final tu IA.
- **Te dice si vas bien:** cuánto llevas gastado, a qué ritmo vas y qué categoría se te está pasando, antes de que termine el mes.
- **Te da consejos concretos:** tu IA mira tus números y te deja lo que va bien, a qué ponerle ojo y algo para hacer esta semana.

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
cartola.csv / .xlsx ──► receta del banco ──► movimientos/AAAA-MM.csv ──► reglas + comercios + tu IA ──► resumen y consejos
                       (o tu IA crea una)        (sin duplicar)              (categorías)
```

## Formato de los datos
Todo vive en `~/Alcancia/` (en Windows, `C:\Users\<tú>\Alcancia`). Es un formato abierto: puedes armar tus propios scripts encima
(ver [`ejemplos/`](ejemplos/)). Si lo cambiamos, será de forma compatible y avisando.

| Archivo | Qué guarda |
|---|---|
| `movimientos/AAAA-MM.csv` | Un archivo por mes. Columnas: `id, fecha, descripcion, monto, moneda, categoria, cuenta, origen, nota`. `monto` negativo = gasto, positivo = ingreso, con punto decimal. `id` identifica el movimiento para no duplicarlo. |
| `categorias.json` | `[{"id", "nombre", "emoji", "tipo": "gasto" \| "ingreso" \| "neutro", "fijo"}]`. `neutro` = entre tus cuentas (no cuenta como gasto); `fijo` = se paga una vez al mes. |
| `presupuesto.json` | `{"moneda": "CLP", "mensual": {"<categoria>": tope}}` |
| `reglas.json` | `[{"contiene": "TEXTO", "categoria": "<id>"}]`: lo que Alcancía aprende cuando corriges una categoría. |
| `cuentas.json` | `[{"id", "nombre", "receta", "moneda"}]` |
| `consejos/AAAA-MM-DD.md` | Los consejos de tu IA. |
| `.alcancia/` | Ajustes de la app y recetas descargadas o creadas por ti. |

## Recetas: cada banco del mundo
Una receta es un JSON de **solo datos** (nunca código), así que cualquiera puede agregar su banco sin programar. El formato está en
[`recetas/README.md`](recetas/README.md) y el catálogo comunitario vive en
[alcancia-app/alcancia-catalogo](https://github.com/alcancia-app/alcancia-catalogo). ¿Tu banco no está? Abre la app, agrega la cartola
y deja que tu IA aprenda a leerla: al final te ofrece compartir **solo la receta**, nunca tus movimientos.

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
statements from any bank or wallet in the world (CSV or Excel); Alcancía sorts them without duplicates, your own AI (Claude Code,
Codex or Gemini, with your account) fills in categories and gives you concrete tips, and you see in time when a category is running
over budget. Your data stays on your computer in open files: no servers, no accounts, no ads, and it never asks for your bank
password. Each bank is supported through a data-only *recipe*; if yours is missing, your AI learns it and you can share just the
recipe with the community. Spanish-first, English included. Licensed under AGPL-3.0.
