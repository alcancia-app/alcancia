"""Pruebas de la lógica en Python. Nunca tocan datos reales ni llaman a una IA de verdad:
usan una carpeta temporal (ALCANCIA_CARPETA) y una IA falsa en el PATH (pruebas/ia_falsa.py, instalada como «claude»).

Uso: python3 pruebas/test_python.py
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS_PRUEBA = os.path.join(RAIZ, "pruebas", "datos")
TMP = tempfile.mkdtemp(prefix="alcancia-pruebas-")
os.environ["ALCANCIA_CARPETA"] = os.path.join(TMP, "Alcancia")
BIN_FALSO = os.path.join(TMP, "bin")
os.makedirs(BIN_FALSO)
for nombre in ("claude",):
    destino = os.path.join(BIN_FALSO, nombre)
    shutil.copy(os.path.join(RAIZ, "pruebas", "ia_falsa.py"), destino)
    os.chmod(destino, os.stat(destino).st_mode | stat.S_IEXEC)
os.environ["PATH"] = BIN_FALSO + os.pathsep + os.environ["PATH"]
sys.path.insert(0, os.path.join(RAIZ, "bin"))

import categorizar  # noqa: E402
import consejos  # noqa: E402
import datos  # noqa: E402
import recetas  # noqa: E402
import resumen  # noqa: E402

CARTOLA = os.path.join(DATOS_PRUEBA, "cartola_ejemplo.csv")
RECETA = json.load(open(os.path.join(DATOS_PRUEBA, "recetas_prueba.json"), encoding="utf-8"))
CASOS = json.load(open(os.path.join(RAIZ, "pruebas", "casos.json"), encoding="utf-8"))


def correr(script, *args):
    salida = os.path.join(TMP, "salida.json")
    r = subprocess.run([sys.executable, os.path.join(RAIZ, "bin", script), *args, salida], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    with open(salida, encoding="utf-8") as f:
        return json.load(f)


def limpiar():
    shutil.rmtree(datos.BASE, ignore_errors=True)


def xlsx(ruta, filas):
    """Un .xlsx mínimo (textos en sharedStrings, números como número) para probar el lector sin librerías."""
    textos = sorted({c for f in filas for c in f if isinstance(c, str)})
    def celda(c, ref):
        if isinstance(c, str):
            return f'<c r="{ref}" t="s"><v>{textos.index(c)}</v></c>'
        return f'<c r="{ref}"><v>{c}</v></c>'
    hoja = "".join(f'<row r="{i + 1}">' + "".join(celda(c, f"{chr(65 + j)}{i + 1}") for j, c in enumerate(f)) + "</row>" for i, f in enumerate(filas))
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("xl/sharedStrings.xml", f"<sst {ns}>" + "".join(f"<si><t>{t}</t></si>" for t in textos) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet {ns}><sheetData>{hoja}</sheetData></worksheet>")


class Recetas(unittest.TestCase):
    def test_receta_de_prueba_es_valida(self):
        self.assertEqual(recetas.validar(RECETA), [])

    def test_validar_rechaza_lo_raro(self):
        mala = {**RECETA, "id": "Banco!", "nombre": "<script>", "codigo": "import os", "signo": "otro"}
        p = " ".join(recetas.validar(mala))
        for texto in ("id debe", "nombre debe", "Campos desconocidos", "signo"):
            self.assertIn(texto, p)
        self.assertTrue(recetas.validar(None))

    def test_recetas_incluidas_son_validas(self):
        carpeta = os.path.join(RAIZ, "recetas")
        for n in os.listdir(carpeta):
            if n.endswith(".json"):
                r = json.load(open(os.path.join(carpeta, n), encoding="utf-8"))
                self.assertEqual(recetas.validar(r), [], n)
                self.assertEqual(r["id"] + ".json", n, "el archivo se llama como su id")

    def test_numeros(self):
        self.assertEqual(recetas.numero("-$ 12.345,50"), -12345.5)
        self.assertEqual(recetas.numero("(1,200.00)", ".", ","), -1200.0)
        self.assertEqual(recetas.numero("1.250.000"), 1250000)
        self.assertEqual(recetas.numero("15000-"), -15000)
        self.assertIsNone(recetas.numero(""))
        self.assertIsNone(recetas.numero("Total"))

    def test_fechas(self):
        self.assertEqual(recetas.fecha("02/10/2026", "%d/%m/%Y"), "2026-10-02")
        self.assertEqual(recetas.fecha("2026-10-02 14:33:10", ["%d/%m/%Y", "%Y-%m-%d"]), "2026-10-02")
        self.assertEqual(recetas.fecha("46297", "%d/%m/%Y"), "2026-10-02")  # número de serie de Excel
        self.assertIsNone(recetas.fecha("Total cargos", "%d/%m/%Y"))

    def test_detectar_y_aplicar_csv(self):
        self.assertEqual(recetas.detectar(CARTOLA, {RECETA["id"]: RECETA})["id"], RECETA["id"])
        movs, avisos = recetas.aplicar(CARTOLA, RECETA, "banco-ejemplo")
        self.assertEqual(len(movs), 9)  # sin saldo inicial ni la fila de totales
        self.assertTrue(any("Total cargos" in a for a in avisos))
        porDesc = {m["descripcion"]: m for m in movs}
        self.assertEqual(porDesc["COMPRA LIDER EXPRESS 2231"]["monto"], -23450)
        self.assertEqual(porDesc["REMUNERACION EMPRESA FICTICIA SPA"]["monto"], 1250000)
        self.assertEqual(porDesc["FARMACIA CRUZ VERDE"]["monto"], -8750.5)
        cafes = [m["id"] for m in movs if m["descripcion"] == "CAFE LA ESQUINA"]
        self.assertEqual(len(set(cafes)), 2, "dos cafés iguales el mismo día son dos movimientos")

    def test_xlsx(self):
        ruta = os.path.join(TMP, "cartola.xlsx")
        xlsx(ruta, [["Mi banco"], ["Fecha", "Detalle", "Monto"], [46297, "SUPERMERCADO", -15000], [46298, "SUELDO", 900000]])
        receta = {**RECETA, "id": "cl-prueba-xlsx", "archivo": {"extension": ["xlsx"]}, "reconocer": {"encabezados": ["Fecha", "Detalle", "Monto"]},
                  "columnas": {"fecha": "Fecha", "descripcion": "Detalle", "monto": "Monto"}, "numeros": {"decimal": ".", "miles": ""}}
        self.assertEqual(recetas.validar(receta), [])
        movs, _ = recetas.aplicar(ruta, receta, "x")
        self.assertEqual([(m["fecha"], m["monto"]) for m in movs], [("2026-10-02", -15000), ("2026-10-03", 900000)])

    def test_leer_receta_de_la_ia(self):
        self.assertEqual(recetas.leer_receta_texto("Aquí va:\n```json\n{\"a\": 1}\n```")["a"], 1)
        self.assertIsNone(recetas.leer_receta_texto("no sé"))


class Categorias(unittest.TestCase):
    def test_conocidos_y_reglas(self):
        movs = [{"descripcion": d, "monto": m, "categoria": ""} for d, m in
                [("UBER EATS *PEDIDO", -1), ("UBER *TRIP", -1), ("COMPRA LIDER EXPRESS", -1), ("CAFE LA ESQUINA", -1),
                 ("REMUNERACION EMPRESA", 10), ("Pago METROGAS", -1)]]
        categorizar.por_reglas(movs, [{"contiene": "cafe la esquina", "categoria": "comida"}])
        self.assertEqual([m["categoria"] for m in movs], ["comida", "transporte", "supermercado", "comida", "sueldo", "cuentas"])

    def test_regla_para(self):
        for d, esperado in CASOS["regla"]:
            self.assertEqual(categorizar.regla_para(d), esperado, d)

    def test_respuesta_de_la_ia(self):
        r = categorizar.leer_respuesta("0|comida\n1|inventada\n7|otros\nbasura\n 2 | casa ", 3, {"comida", "casa", "otros"})
        self.assertEqual(r, {0: "comida", 2: "casa"})


class Resumen(unittest.TestCase):
    def test_redondear(self):
        for v, esperado in CASOS["redondear"]:
            self.assertEqual(resumen.redondear_arriba(v), esperado, v)

    def test_casos(self):
        for c in CASOS["resumen"]:
            r = resumen.resumen(c["movimientos"], c["mes"], c["hoy"], c["presupuesto"], CASOS["categorias"])
            for k, v in c["esperado"].items():
                self.assertEqual(r[k], v, f"{c['nombre']}: {k}")

    def test_presupuesto_sugerido(self):
        movs = [{"fecha": f"2026-0{m}-05", "monto": -v, "categoria": "comida", "moneda": "CLP"} for m, v in [(7, 40000), (8, 52000), (9, 61000)]]
        self.assertEqual(resumen.presupuesto_sugerido(movs, ["2026-07", "2026-08", "2026-09"], CASOS["categorias"]), {"comida": 52000})


class Flujo(unittest.TestCase):
    """De punta a punta con los scripts, como los llama la app."""

    def setUp(self):
        limpiar()
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", "cl-banco-ejemplo.json"), RECETA)

    def test_vista_guardar_y_no_duplicar(self):
        v = correr("importar.py", "vista", CARTOLA)
        self.assertTrue(v["ok"], v)
        self.assertEqual((v["receta"]["id"], v["total"], v["desde"], v["hasta"]), ("cl-banco-ejemplo", 9, "2026-10-02", "2026-10-10"))
        self.assertFalse(os.path.exists(datos.MOVIMIENTOS), "la vista previa no guarda nada")
        g = correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "1")
        self.assertEqual((g["ok"], g["nuevos"], g["repetidos"]), (True, 9, 0), g)
        self.assertEqual(g["sin_categoria"], 0, "la IA falsa categoriza lo que faltaba")
        self.assertGreater(g["categorizados_ia"], 0)
        otra = correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        self.assertEqual((otra["nuevos"], otra["repetidos"]), (0, 9))
        guardados = datos.leer_mes("2026-10")
        self.assertEqual(len(guardados), 9)
        self.assertEqual(datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), [])[0]["id"], "banco-ejemplo")
        with open(datos.ruta_mes("2026-10"), encoding="utf-8") as f:
            cabecera = f.readline().strip()
        self.assertEqual(cabecera, ",".join(datos.CAMPOS), "el formato documentado no cambia")

    def test_archivo_desconocido(self):
        otro = os.path.join(TMP, "otro.csv")
        with open(otro, "w") as f:
            f.write("A;B\n1;2\n")
        self.assertTrue(correr("importar.py", "vista", otro)["sin_receta"])

    def test_receta_con_ia(self):
        os.remove(os.path.join(datos.INTERNO, "recetas", "cl-banco-ejemplo.json"))
        r = correr("receta_ia.py", CARTOLA, "CL")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["total"], 9)
        self.assertEqual(r["receta"]["autor"], "ia")
        self.assertNotIn("LIDER", json.dumps(r["receta"]), "la receta no lleva datos de la cartola")

    def test_consejos(self):
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        r = correr("consejos.py", "2026-10-12")
        self.assertTrue(r["ok"], r)
        self.assertTrue(os.path.exists(os.path.join(datos.CONSEJOS, "2026-10-12.md")))
        self.assertIsNone(consejos.validar("### Ojo con\nx\n### Lo que va bien\ny\n### Para esta semana\nz"), "orden distinto = no sirve")

    def test_cambiar_categoria(self):
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        m = datos.leer_mes("2026-10")[0]
        self.assertTrue(datos.cambiar("2026-10", m["id"], {"categoria": "casa", "monto": 1}))
        nuevo = next(x for x in datos.leer_mes("2026-10") if x["id"] == m["id"])
        self.assertEqual((nuevo["categoria"], nuevo["monto"]), ("casa", m["monto"]), "solo cambia lo permitido")


if __name__ == "__main__":
    try:
        unittest.main(verbosity=1)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
