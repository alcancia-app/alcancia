# Recetas: cómo leer la cartola de cada banco

Una **receta** le explica a Alcancía cómo leer la cartola de un banco o billetera: qué columna es la fecha, cuál la descripción,
cuál el monto y cómo vienen escritos los números. Es un JSON de **solo datos**: nunca ejecuta código. Así cualquiera puede agregar
su banco sin programar, de cualquier país.

Las recetas de esta carpeta vienen incluidas en la app y **solo se agregan después de probarlas con una cartola real**. Las demás
viven en el catálogo comunitario [alcancia-app/alcancia-catalogo](https://github.com/alcancia-app/alcancia-catalogo).

## Ejemplo (banco ficticio)
```json
{
  "formato": 1,
  "id": "cl-banco-ejemplo",
  "nombre": "Banco Ejemplo — cuenta corriente",
  "institucion": "Banco Ejemplo",
  "pais": "CL",
  "moneda": "CLP",
  "tipo": "cartola",
  "archivo": {"extension": ["csv"], "separador": ";"},
  "reconocer": {"encabezados": ["Fecha", "Descripción", "Cargos", "Abonos"]},
  "columnas": {"fecha": "Fecha", "descripcion": "Descripción", "cargo": "Cargos", "abono": "Abonos"},
  "fecha": "%d/%m/%Y",
  "numeros": {"decimal": ",", "miles": "."},
  "signo": "normal",
  "ignorar_si_contiene": ["SALDO INICIAL"]
}
```

## Campos
| Campo | Qué es |
|---|---|
| `formato` | Siempre `1`. |
| `id` | `pais-institucion-producto`, en minúsculas y con guiones (`cl-banco-ejemplo`, `mx-billetera-ejemplo-credito`). El archivo se llama `<id>.json`. |
| `nombre`, `institucion` | Cómo se muestra. Texto corto, sin HTML. |
| `pais`, `moneda` | Código de 2 letras (ISO 3166) y de 3 letras (ISO 4217). |
| `tipo` | `cartola` (por ahora el único). |
| `archivo` | `extension` (lista: `csv`, `xlsx`, `pdf`), y opcionalmente `separador`, `codificacion` y `hoja` (número de hoja de Excel). |
| `reconocer.encabezados` | Los nombres de columna que identifican el archivo. Alcancía busca la fila de encabezados en las primeras 40 filas (no importan mayúsculas, tildes ni espacios). |
| `columnas` | Une `fecha`, `descripcion` y `monto` — o `cargo` y `abono` si vienen separados — con el nombre de su columna. Opcionales: `detalle` (se suma a la descripción), `moneda` y `saldo` (la columna de saldo: el de la fila más reciente pasa a ser el saldo de la cuenta en «Lo que tienes»). |
| `fecha` | Formato de [strptime](https://docs.python.org/3/library/datetime.html#format-codes) o una lista. Las fechas de Excel (números) se entienden solas. |
| `numeros` | `decimal` (`,` o `.`) y `miles` (`.`, `,`, espacio o vacío). |
| `signo` | `normal`: los gastos vienen negativos o en la columna de cargos. `invertido`: los gastos vienen positivos en una sola columna de monto. |
| `ignorar_si_contiene` | Filas que no son movimientos (saldos, totales). |

## Cartolas en PDF
Una receta de PDF es igual a una de CSV: solo cambia `"archivo": {"extension": ["pdf"]}` (sin `separador`). Alcancía saca el texto
del PDF y lo arma como tabla: cada línea de la página es una fila y las celdas se alinean con las columnas de la fila de
encabezados (la que dice `reconocer.encabezados`). Así un monto que viene solo en «Abonos» no cae en «Cargos». Una descripción
que sigue en la línea de abajo (sin fecha) se junta con su fila. Para ver la tabla tal como la ve la receta:
```bash
python3 -c "import sys; sys.path.insert(0, 'bin'); import pdf; [print(f) for f in pdf.tabla('mi-cartola.pdf', ['Fecha', 'Descripción'])]"
```
Solo sirven los PDF **con texto** (los que genera el banco). Los escaneados y los protegidos con clave no se pueden leer.

## Probar una receta
```bash
cp mi-receta.json ~/Alcancia/.alcancia/recetas/
python3 bin/importar.py vista mi-cartola.csv /tmp/vista.json && cat /tmp/vista.json
```
`vista` no guarda nada. Si los movimientos se ven bien, la receta está lista para compartir.

**Nunca subas tu cartola real** a GitHub, ni en un issue ni en un pull request. Si hace falta un ejemplo, haz una copia con datos
inventados que respete las columnas y el formato.
