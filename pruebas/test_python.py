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
from datetime import date, timedelta

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
import compromiso_ia  # noqa: E402
import compromisos  # noqa: E402
import consejos  # noqa: E402
import datos  # noqa: E402
import pdf  # noqa: E402
import recetas  # noqa: E402
import resumen  # noqa: E402

CARTOLA = os.path.join(DATOS_PRUEBA, "cartola_ejemplo.csv")
with open(os.path.join(DATOS_PRUEBA, "recetas_prueba.json"), encoding="utf-8") as _f:
    RECETA = json.load(_f)
with open(os.path.join(RAIZ, "pruebas", "casos.json"), encoding="utf-8") as _f:
    CASOS = json.load(_f)


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

    def test_historia(self):
        for c in CASOS["historia"]:
            r = resumen.historia(c["movimientos"], c["mes"], c["hoy"], c["presupuesto"], CASOS["categorias"], c.get("categoria"), c.get("n", 6))
            self.assertEqual(r, c["esperado"], c["nombre"])

    def test_periodos(self):
        sec = CASOS["periodos"]
        for c in sec["rango"]:
            self.assertEqual(list(resumen.rango(c["mes"], c["per"])), c["esperado"], c["nombre"])
        for c in sec["periodo_de"]:
            self.assertEqual(resumen.periodo_de(c["fecha"], c["per"]), c["esperado"], c["fecha"])
        k = sec["sueldo"]
        per = compromisos.periodo(k["inicio_mes"], [k["compromiso"]], k["movimientos"], k["hoy"], "CLP")
        self.assertEqual(per, k["esperado_per"])
        mes = resumen.periodo_de(k["hoy"], per)
        self.assertEqual(mes, k["esperado_periodo"])
        r = resumen.resumen(k["movimientos"], mes, k["hoy"], k["presupuesto"], k["categorias"], per)
        self.assertEqual({x: r[x] for x in k["esperado_resumen"]}, k["esperado_resumen"])
        self.assertEqual(resumen.historia(k["movimientos"], mes, k["hoy"], k["presupuesto"], k["categorias"], None, 3, per), k["esperado_historia"])
        e = compromisos.estado_mes([k["compromiso"]], k["movimientos"], mes, k["hoy"], "CLP", per)
        self.assertEqual({x: v for x, v in e.items() if x != "compromisos"}, k["esperado_compromisos"])
        # En palabras: el sueldo llegó el 15 (antes del 25) y el periodo parte ese día; el bono no mueve nada pero cuenta como ingreso.
        self.assertEqual((r["desde"], r["hasta"], r["ingresos"]), ("2026-10-15", "2026-11-24", 1650000))
        self.assertIsNone(compromisos.periodo({"modo": "dia", "dia": 25}, [], [], "2026-10-26", "CLP"))
        self.assertIsNone(compromisos.periodo({"modo": "sueldo", "dia": 40}, [], [], "2026-10-26", "CLP"))

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
        texto = consejos.prompt("2026-10-12", datos.leer_todos(), datos.presupuesto(), datos.categorias())
        self.assertIn("Gasto total de los últimos 6 meses", texto)
        self.assertIn("2026-10: ", texto)
        self.assertNotIn("Ana Pérez", texto)
        self.assertIsNone(consejos.validar("### Ojo con\nx\n### Lo que va bien\ny\n### Para esta semana\nz"), "orden distinto = no sirve")

    def test_cambiar_categoria(self):
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        m = datos.leer_mes("2026-10")[0]
        self.assertTrue(datos.cambiar("2026-10", m["id"], {"categoria": "casa", "monto": 1}))
        nuevo = next(x for x in datos.leer_mes("2026-10") if x["id"] == m["id"])
        self.assertEqual((nuevo["categoria"], nuevo["monto"]), ("casa", m["monto"]), "solo cambia lo permitido")

    def test_estado_vacio_y_con_datos(self):
        limpiar()
        e = correr("estado.py")
        self.assertEqual((e["movimientos"], e["consejos"], e["cuentas"]), ([], [], []), "sin ~/Alcancia la app muestra la bienvenida")
        self.assertTrue(e["categorias"])
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", "cl-banco-ejemplo.json"), RECETA)
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        correr("consejos.py", "2026-10-12")
        e = correr("estado.py")
        self.assertEqual(len(e["movimientos"]), 9)
        self.assertEqual(e["consejos"][0]["fecha"], "2026-10-12")
        self.assertTrue(e["consejos"][0]["texto"].startswith("### Lo que va bien"), "sin el encabezado del archivo")

    def guardar(self, accion, entrada):
        ruta = os.path.join(TMP, "entrada.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(entrada, f)
        return correr("guardar.py", accion, ruta)

    def test_guardar(self):
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        m = next(x for x in datos.leer_mes("2026-10") if x["descripcion"] == "CAFE LA ESQUINA")
        self.assertTrue(self.guardar("categoria", {"mes": "2026-10", "id": m["id"], "categoria": "comida"})["ok"])
        self.assertFalse(self.guardar("categoria", {"mes": "2026-10", "id": m["id"], "categoria": "inventada"})["ok"])
        r = self.guardar("regla", {"contiene": "cafe la esquina", "categoria": "ocio"})
        self.assertEqual((r["ok"], r["cambiados"]), (True, 2), "la regla se aplica a los dos cafés")
        self.assertEqual(datos.reglas()[-1], {"contiene": "CAFE LA ESQUINA", "categoria": "ocio"})
        self.assertTrue(self.guardar("presupuesto", {"mensual": {"comida": 90000, "inventada": 5, "ocio": -1}})["ok"])
        self.assertEqual(datos.presupuesto()["mensual"], {"comida": 90000})
        self.assertFalse(self.guardar("receta", {"receta": {**RECETA, "id": "MAL"}})["ok"])
        self.assertTrue(self.guardar("receta", {"receta": {**RECETA, "id": "cl-otro-banco"}})["ok"])


def casos_compromisos(caso):
    """Compromisos y movimientos de un caso de pruebas/casos.json (los de la sección, o solo algunos, más los extra)."""
    sec = CASOS["compromisos"]
    comps = [c for c in sec["compromisos"] if "compromisos_ids" not in caso or c["id"] in caso["compromisos_ids"]] + caso.get("extra", [])
    movs = [m for m in sec["movimientos"] if "movimientos_ids" not in caso or m["id"] in caso["movimientos_ids"]]
    return comps, movs


def un_compromiso(**k):
    base = {"nombre": "Arriendo", "tipo": "cuenta", "monto": 420000, "frecuencia": "mensual", "dia": 1, "categoria": "casa",
            "buscar": ["ARRIENDO"]}
    return {**base, **k}


class Compromisos(unittest.TestCase):
    def setUp(self):
        limpiar()

    def test_casos(self):
        sec = CASOS["compromisos"]
        for c in sec["estado"]:
            comps, movs = casos_compromisos(c)
            self.assertEqual(compromisos.estado_mes(comps, movs, c["mes"], c["hoy"], c["moneda"]), c["esperado"], c["nombre"])
        for c in sec["gasto_maximo"]:
            comps, movs = casos_compromisos(c)
            r = compromisos.gasto_maximo(movs, comps, c["mes"], c["hoy"], sec["categorias"], c["meses_completos"], c["moneda"])
            self.assertEqual(r, c["esperado"], c["nombre"])

    def test_reglas_a_mano(self):
        """Lo mismo que los casos, pero dicho en palabras (los casos los genera Python; esto revisa que tengan sentido)."""
        e = CASOS["compromisos"]["estado"][0]["esperado"]
        por = {(i["nombre"], i["vence"]): i for i in e["items"]}
        self.assertEqual(por[("Arriendo", "2026-10-01")]["pago"]["fecha"], "2026-09-30", "pagado un día antes del vencimiento")
        self.assertEqual(por[("Clases", "2026-10-07")]["estado"], "pagado", "el pago justo del día no se lo lleva un vencimiento anterior")
        self.assertEqual(por[("Plan de celular", "2026-10-10")]["estado"], "atrasado")
        self.assertEqual(por[("Cuota A", "2026-10-10")]["estado"], "pagado")
        self.assertEqual(por[("Cuota B", "2026-10-12")]["estado"], "atrasado", "un movimiento cuenta para un solo compromiso")
        self.assertEqual(por[("Seguro", "2026-10-12")]["estado"], "atrasado", "«no es este» se respeta")
        self.assertEqual(por[("Permiso de circulación", "2026-10-15")]["pago"]["como"], "manual")
        self.assertTrue(por[("Streaming", "2026-09-28")]["anterior"], "lo del mes anterior sin pagar sigue apareciendo")
        self.assertEqual(por[("Crédito automotriz", "2026-10-20")]["cuota"], {"numero": 13, "total": 36})
        self.assertNotIn("Ya no", {i["nombre"] for i in e["items"]}, "los inactivos no cuentan")
        credito = next(c for c in e["compromisos"] if c["nombre"] == "Crédito automotriz")
        self.assertEqual((credito["cuotas"]["quedan"], credito["termina"], credito["por_pagar"]), (24, "2028-09-20", 24 * 189000))
        g = CASOS["compromisos"]["gasto_maximo"]
        self.assertTrue(g[0]["esperado"]["disponible"] == 1450000 - g[0]["esperado"]["compromisos"] - g[0]["esperado"]["otros_fijos"])
        self.assertLessEqual(sum(x["maximo"] for x in g[0]["esperado"]["por_categoria"]), g[0]["esperado"]["disponible"])
        self.assertEqual(g[1]["esperado"]["fuente"], "promedio")
        self.assertFalse(g[2]["esperado"]["alcanza"])
        self.assertTrue(all(x["maximo"] == 0 for x in g[2]["esperado"]["por_categoria"]))

    def test_validar(self):
        hoy = "2026-10-26"
        c, e = compromisos.validar(un_compromiso(nombre="Crédito cuenta 0012-3456-78 del banco " + "x" * 80), {"casa"}, hoy)
        self.assertEqual(e, [])
        self.assertNotIn("3456", c["nombre"], "nunca números de cuenta en el nombre")
        self.assertLessEqual(len(c["nombre"]), 60)
        self.assertEqual((c["signo"], c["desde"], c["tolerancia"], c["activo"], c["origen"]), ("gasto", hoy, 5, True, "manual"))
        self.assertRegex(c["id"], r"^c-[a-z0-9]{10}$")
        c, e = compromisos.validar(un_compromiso(tipo="deuda", cuotas_restantes=120), {"casa"}, hoy)
        self.assertEqual((c["cuotas_total"], c["cuotas_pagadas"]), (120, 0))
        c, e = compromisos.validar(un_compromiso(tipo="deuda", cuotas_total=240, cuotas_restantes=187), {"casa"}, hoy)
        self.assertEqual((c["cuotas_total"], c["cuotas_pagadas"]), (240, 53))
        c, e = compromisos.validar(un_compromiso(tipo="ingreso", buscar="remuneracion, Sueldo 12345678"), {"casa"}, hoy)
        self.assertEqual((c["signo"], c["buscar"]), ("ingreso", ["REMUNERACION", "SUELDO"]))
        for malo, texto in [({"monto": -5}, "monto"), ({"dia": 40}, "día"), ({"tipo": "raro"}, "tipo"), ({"categoria": "inventada"}, "categoría"),
                            ({"frecuencia": "anual"}, "fecha"), ({"nombre": "123456789"}, "nombre"), ({"saldo": "mucho"}, "saldo")]:
            c, e = compromisos.validar(un_compromiso(**malo), {"casa"}, hoy)
            self.assertIsNone(c, malo)
            self.assertIn(texto, " ".join(e).lower(), malo)
        c, e = compromisos.validar({**un_compromiso(), "id": "c-abcdef1234", "pagos": {}}, {"casa"}, hoy, estricto=True)
        self.assertIn("Campos desconocidos", " ".join(e), "la IA no puede poner ids ni pagos")
        c, e = compromisos.validar(un_compromiso(frecuencia="una_vez", fecha="2026-03-01"), {"casa"}, hoy)
        self.assertEqual(c["desde"], "2026-03-01")

    def test_extraer_cuotas(self):
        for d, esperado in [("PAGO DIVIDENDO CUOTA 53/240", (53, 240)), ("Crédito consumo cuota 4 de 24", (4, 24)), ("CTA 07/36 AUTO", (7, 36)),
                            ("LOAN INSTALLMENT 3 OF 12", (3, 12)), ("COMPRA 03/10 LIDER", None), ("CUOTA 50/12", None), ("CUOTAS SOCIALES", None)]:
            self.assertEqual(compromisos.extraer_cuotas(d), esperado, d)

    def test_sugerir(self):
        hoy, cats = "2026-10-26", datos.CATEGORIAS_BASE
        movs, n = [], 0
        def m(f, d, monto, cat=""):
            nonlocal n
            n += 1
            movs.append({"id": f"s{n}", "fecha": f, "descripcion": d, "monto": monto, "moneda": "CLP", "categoria": cat})
        for mes, dia, monto in [("2026-06", 14, 31990), ("2026-07", 15, 31990), ("2026-08", 16, 33000), ("2026-09", 15, 31990)]:
            m(f"{mes}-{dia:02d}", f"GIMNASIO EJEMPLO {dia}{mes[-2:]}", -monto, "ocio")
        for mes in ("2026-07", "2026-08", "2026-09"):
            for d in (3, 9, 20):
                m(f"{mes}-{d:02d}", "CAFE LA ESQUINA", -3200, "comida")  # varias veces al mes: no es compromiso
            m(f"{mes}-05", "REMUNERACION EMPRESA FICTICIA SPA", 1250000, "sueldo")
            m(f"{mes}-15", "TRASPASO A BILLETERA", -150000, "transferencia")  # entre cuentas propias: no
        m("2026-10-15", "PAGO DIVIDENDO CUOTA 53/240", -512000)
        m("2026-10-12", "SEGURO HOGAR EJEMPLO", -8990)
        m("2026-10-02", "PACIFICO RESTAURANT", -15000)  # «PAC» como palabra completa, no dentro de otra
        m("2026-02-15", "PAGO DIVIDENDO CUOTA 45/240", -512000)  # fuera de la ventana
        r = compromisos.sugerir(movs, [], hoy, cats, "CLP")
        claves = [s["clave"] for s in r]
        self.assertEqual(claves[0], "PAGO DIVIDENDO CUOTA", "las deudas que delata la descripción van primero")
        self.assertIn("GIMNASIO EJEMPLO", claves)
        self.assertIn("REMUNERACION EMPRESA FICTICIA", claves)
        self.assertIn("SEGURO HOGAR EJEMPLO", claves)
        for no in ("CAFE LA ESQUINA", "TRASPASO A BILLETERA", "PACIFICO RESTAURANT"):
            self.assertNotIn(no, claves)
        div = r[0]
        self.assertEqual((div["tipo"], div["monto"], div["dia"], div["cuotas_pagadas"], div["cuotas_total"], div["preguntar"], div["motivo"]),
                         ("deuda", 512000, 15, 53, 240, "saldo", "palabra"))
        gim = next(s for s in r if s["clave"] == "GIMNASIO EJEMPLO")
        self.assertEqual((gim["monto"], gim["dia"], gim["meses"], gim["motivo"], gim["preguntar"]), (31990, 15, 4, "repite", "frecuencia"))
        sueldo = next(s for s in r if s["clave"] == "REMUNERACION EMPRESA FICTICIA")
        self.assertEqual((sueldo["tipo"], sueldo["signo"]), ("ingreso", "ingreso"))
        # Lo que ya es compromiso o se descartó no se vuelve a sugerir; y solo_ids filtra lo recién importado.
        gimnasio, _ = compromisos.validar({"nombre": "Gimnasio", "monto": 31990, "dia": 15, "buscar": ["GIMNASIO"]}, None, hoy)
        r2 = compromisos.sugerir(movs, [gimnasio], hoy, cats, "CLP", descartados=["seguro hogar ejemplo"])
        self.assertNotIn("GIMNASIO EJEMPLO", [s["clave"] for s in r2])
        self.assertNotIn("SEGURO HOGAR EJEMPLO", [s["clave"] for s in r2])
        solo = compromisos.sugerir(movs, [], hoy, cats, "CLP", solo_ids={movs[-3]["id"]})
        self.assertEqual([s["clave"] for s in solo], ["SEGURO HOGAR EJEMPLO"])

    def test_palabras_conocidas_son_datos(self):
        j = datos.leer_json(os.path.join(RAIZ, "bin", "compromisos_conocidos.json"), {})
        self.assertEqual(j["formato"], 1)
        for pais, lista in j["paises"].items():
            for e in lista:
                self.assertEqual(set(e) - {"tipo", "categoria", "preguntar", "palabras"}, set(), pais)
                self.assertIn(e["tipo"], compromisos.TIPOS)
                self.assertIn(e["categoria"], {c["id"] for c in datos.CATEGORIAS_BASE} | {""})
                self.assertTrue(all(p == datos.normalizar(p) for p in e["palabras"]), "en mayúsculas y sin tildes")

    def test_compromiso_con_ia(self):
        r = self.entender("tengo que pagar el crédito hipotecario los 15, son 500000, me quedan 120 cuotas", "2026-10-26")
        self.assertTrue(r["ok"], r)
        c = r["compromiso"]
        self.assertEqual((c["tipo"], c["monto"], c["dia"], c["cuotas_total"], c["origen"], c["desde"]), ("deuda", 500000, 15, 120, "ia", "2026-10-26"))
        self.assertNotIn("12345678", c["nombre"], "lo que propone la IA también se limpia")
        self.assertFalse(os.path.exists(compromisos.RUTA), "no se guarda nada hasta que la persona confirma")
        malo = self.entender("ROMPER todo", "2026-10-26")
        self.assertFalse(malo["ok"])
        self.assertIn("Campos desconocidos", malo["error"])
        self.assertFalse(self.entender("NADA que ver", "2026-10-26")["ok"])
        self.assertFalse(self.entender("x", "2026-10-26")["ok"])
        # RUT y cuentas ficticios, armados por partes: ningún RUT entero queda escrito en el repo.
        rut = "11.111.111" + "-1"
        sin_puntos = "1111111" + "1"
        for texto, fuera in [(f"mi rut {rut} y pago 450.000 el 15", "111"), (f"mi cuentarut {sin_puntos} y pago 450.000 el 15", sin_puntos),
                             (f"rut {sin_puntos}1 y pago 450.000 el 15", sin_puntos), (f"rut {sin_puntos}k y pago 450.000 el 15", sin_puntos),
                             (f"rut{sin_puntos} y pago 450.000 el 15", sin_puntos), ("cuenta 0012-3456-7890 y pago 450.000 el 15", "3456"),
                             ("cuenta 001234567890 y pago 450.000 el 15", "1234567890"), ("pago 1234567 y 450.000 el 15", "1234567")]:
            limpio = compromiso_ia.limpiar_texto(texto)
            self.assertNotIn(fuera, limpio, texto)
            self.assertIn("450.000", limpio, "los montos con separador de miles se mantienen")
        self.assertEqual(compromiso_ia.limpiar_texto("son 500.000 o 500000 o 1.250.000, el 15"), "son 500.000 o 500000 o 1.250.000, el 15")

    def entender(self, texto, hoy):
        """Como lo llama la app: el texto en un archivo de entrada, nunca como argumento."""
        ruta = os.path.join(TMP, "entrada-ia.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"texto": texto, "hoy": hoy}, f)
        return correr("compromiso_ia.py", "entender", ruta)

    def test_el_texto_no_va_como_argumento(self):
        with open(os.path.join(RAIZ, "app", "Sources", "Alcancia", "Ventana.swift"), encoding="utf-8") as f:
            swift = f.read()
        self.assertIn('conEntrada("compromiso_ia.py", "entender"', swift)
        self.assertNotIn('correrJSON("compromiso_ia.py"', swift)
        p = subprocess.run([sys.executable, os.path.join(RAIZ, "bin", "compromiso_ia.py"), "el arriendo son 450.000", "2026-10-26",
                            os.path.join(TMP, "x.json")], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2, "la firma vieja (texto como argumento) ya no se acepta")

    def guardar(self, entrada):
        ruta = os.path.join(TMP, "entrada.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(entrada, f)
        return correr("guardar.py", "compromiso", ruta)

    def test_guardar_marcar_y_borrar(self):
        r = self.guardar({"accion": "guardar", "hoy": "2026-10-26", "compromiso": un_compromiso()})
        self.assertTrue(r["ok"] and r["primero"], r)
        cid = r["id"]
        self.assertFalse(self.guardar({"accion": "guardar", "compromiso": un_compromiso(monto=0)})["ok"])
        self.assertFalse(self.guardar({"accion": "guardar", "compromiso": un_compromiso(categoria="inventada")})["ok"])
        self.assertTrue(self.guardar({"accion": "pagado", "id": cid, "periodo": "2026-10", "hoy": "2026-10-26"})["ok"])
        self.assertEqual(compromisos.leer()["compromisos"][0]["pagos"]["2026-10"], {"como": "manual", "fecha": "2026-10-26"})
        editado = self.guardar({"accion": "guardar", "compromiso": {**un_compromiso(monto=430000), "id": cid, "pagos": {}, "desde": "2020-01-01"}})
        self.assertFalse(editado["primero"])
        c = compromisos.leer()["compromisos"][0]
        self.assertEqual((c["monto"], c["desde"], c["pagos"]["2026-10"]["como"]), (430000, "2026-10-26", "manual"),
                         "editar no borra lo marcado ni cambia desde cuándo")
        self.assertTrue(self.guardar({"accion": "desmarcar", "id": cid, "periodo": "2026-10"})["ok"])
        self.assertNotIn("2026-10", compromisos.leer()["compromisos"][0]["pagos"])
        self.assertTrue(self.guardar({"accion": "no_es", "id": cid, "periodo": "2026-10", "movimiento": "abc123"})["ok"])
        self.assertEqual(compromisos.leer()["compromisos"][0]["pagos"]["2026-10"], {"no_es": ["abc123"]})
        self.assertFalse(self.guardar({"accion": "no_es", "id": cid, "periodo": "2026-10", "movimiento": "../x"})["ok"])
        self.assertFalse(self.guardar({"accion": "pagado", "id": cid, "periodo": "octubre"})["ok"])
        self.assertFalse(self.guardar({"accion": "pagado", "id": "c-noexiste1", "periodo": "2026-10"})["ok"])
        self.assertTrue(self.guardar({"accion": "descartar", "clave": "seguro hogar"})["ok"])
        self.assertTrue(self.guardar({"accion": "descartar", "clave": "transferencia 0012345678 hogar"})["ok"])
        self.assertEqual(compromisos.leer()["descartados"], ["SEGURO HOGAR", "TRANSFERENCIA HOGAR"], "sin números largos, como buscar")
        self.assertFalse(self.guardar({"accion": "descartar", "clave": "123456789"})["ok"])
        self.assertTrue(self.guardar({"accion": "borrar", "id": cid})["ok"])
        self.assertEqual(compromisos.leer()["compromisos"], [])
        with open(compromisos.RUTA, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["formato"], 1)

    def test_estado_fija_lo_reconocido_y_sugiere(self):
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", "cl-banco-ejemplo.json"), RECETA)
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        hoy = date.today().isoformat()
        sueldo, _ = compromisos.validar({"nombre": "Sueldo", "tipo": "ingreso", "monto": 1250000, "dia": 5, "buscar": ["REMUNERACION"],
                                         "desde": "2026-10-01"}, None, hoy)
        roto = {"id": "c-roto000001", "nombre": "", "monto": "mucho"}
        datos.escribir_json(compromisos.RUTA, {"formato": 1, "compromisos": [sueldo, roto], "descartados": []})
        e = correr("estado.py")
        self.assertEqual([c["nombre"] for c in e["compromisos"]["compromisos"]], ["Sueldo"])
        self.assertEqual(e["compromisos"]["invalidos"], 1, "uno roto a mano se salta, no rompe la app")
        self.assertIsInstance(e["sugerencias"], list)
        guardado = compromisos.leer()["compromisos"]
        self.assertEqual(guardado[1], roto, "lo que la persona escribió a mano no se pierde")
        p = guardado[0]["pagos"]["2026-10"]
        self.assertEqual((p["como"], p["fecha"], p["monto"]), ("automatico", "2026-10-05", 1250000))

    def test_importar_detecta_compromisos(self):
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", "cl-banco-ejemplo.json"), RECETA)
        hoy = date.today()
        f = lambda d: (hoy - timedelta(days=d)).strftime("%d/%m/%Y")
        ruta = os.path.join(TMP, "cartola_compromisos.csv")
        with open(ruta, "w", encoding="utf-8") as out:
            out.write("Banco Ejemplo;;;;\nFecha;Descripción;Cargos;Abonos;Saldo\n"
                      f"{f(3)};PAGO DIVIDENDO CUOTA 53/240;512.000;;1\n{f(4)};SUPERMERCADO DEL BARRIO;20.000;;1\n")
        r = correr("importar.py", "guardar", ruta, "cl-banco-ejemplo", "0")
        self.assertTrue(r["ok"], r)
        self.assertEqual([d["clave"] for d in r["detectados"]], ["PAGO DIVIDENDO CUOTA"])
        d = r["detectados"][0]
        self.assertEqual((d["cuotas_pagadas"], d["cuotas_total"], d["tipo"]), (53, 240, "deuda"))
        otra = correr("importar.py", "guardar", ruta, "cl-banco-ejemplo", "0")
        self.assertEqual(otra["detectados"], [], "si no hay nada nuevo, no se vuelve a preguntar")

    def test_avisos(self):
        hoy = date.today()
        dia = (hoy + timedelta(days=2))
        if dia.month != hoy.month:
            self.skipTest("cerca de fin de mes")
        c, _ = compromisos.validar({"nombre": "Luz", "monto": 30000, "dia": dia.day, "buscar": ["LUZ"], "desde": hoy.replace(day=1).isoformat()}, None, hoy.isoformat())
        datos.escribir_json(compromisos.RUTA, {"formato": 1, "compromisos": [c], "descartados": []})
        self.assertEqual(correr("compromisos.py", "avisos", hoy.isoformat())["avisos"], [], "sin avisos activados, nada")
        datos.escribir_json(os.path.join(datos.INTERNO, "config.json"), {"avisos": True})
        a = correr("compromisos.py", "avisos", hoy.isoformat())["avisos"]
        self.assertEqual([(x["nombre"], x["tipo"], x["dias"]) for x in a], [("Luz", "pronto", 2)])
        self.assertNotIn("monto", a[0], "el aviso puede verse con la pantalla bloqueada: sin montos")
        self.assertEqual(correr("compromisos.py", "avisos", hoy.isoformat())["avisos"], [], "uno por compromiso al día")
        self.assertEqual(compromisos.avisos((hoy + timedelta(days=1)).isoformat())["avisos"], [], "«pronto» se avisa una sola vez")
        self.assertEqual([x["tipo"] for x in compromisos.avisos(dia.isoformat())["avisos"]], ["hoy"])

    def test_consejos_con_compromisos(self):
        movs = CASOS["compromisos"]["movimientos"]
        cats = [{**c, "nombre": c["id"]} for c in CASOS["compromisos"]["categorias"]]
        texto = consejos.prompt("2026-10-18", movs, {"moneda": "CLP", "mensual": {}}, cats, CASOS["compromisos"]["compromisos"])
        self.assertIn("Compromisos del mes", texto)
        self.assertIn("disponible para gastos variables", texto)
        self.assertNotIn("Plan de celular", texto, "a la IA solo le llegan totales")
        self.assertIn("no ha anotado compromisos", consejos.prompt("2026-10-18", movs, {"moneda": "CLP", "mensual": {}}, cats))


class IaSinArgumentos(unittest.TestCase):
    """El pedido a la IA (con datos de la persona) nunca va en los argumentos del comando: se verían en la lista de procesos."""

    def setUp(self):
        limpiar()

    def tearDown(self):
        for n in ("agy", "codex"):
            try:
                os.remove(os.path.join(BIN_FALSO, n))
            except OSError:
                pass

    def falsa(self, nombre, codigo):
        ruta = os.path.join(BIN_FALSO, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("#!" + sys.executable + "\nimport json, os, sys\n" + codigo)
        os.chmod(ruta, 0o755)

    def test_ningun_proveedor_pone_el_pedido_en_argv(self):
        import ia
        pedido = "SECRETO de la persona: arriendo 450000"
        # Antigravity: el pedido en instrucciones.md (aunque sea corto); en -p solo una frase fija.
        self.falsa("agy", "datos = open('instrucciones.md', encoding='utf-8').read() if os.path.exists('instrucciones.md') else ''\n"
                          "print(json.dumps({'argv': sys.argv, 'archivo': datos}))\n")
        # Codex: el pedido por la entrada estándar.
        self.falsa("codex", "entrada = sys.stdin.read()\nsalida = sys.argv[sys.argv.index('-o') + 1]\n"
                            "open(salida, 'w', encoding='utf-8').write(json.dumps({'argv': sys.argv, 'archivo': entrada}))\n")
        for proveedor in ("gemini", "codex", "claude"):
            datos.escribir_json(os.path.join(datos.INTERNO, "config.json"), {"ia": proveedor})
            if proveedor == "claude":  # la IA falsa de siempre: lee la entrada estándar
                r = ia.ejecutar_ia(pedido, timeout=30)
                self.assertNotIn("SECRETO", " ".join(r.args), proveedor)
                continue
            r = ia.ejecutar_ia(pedido, timeout=30)
            visto = json.loads(r.stdout)
            self.assertNotIn("SECRETO", " ".join(visto["argv"]), proveedor)
            self.assertIn("SECRETO", visto["archivo"], f"{proveedor} recibe el pedido por archivo o entrada estándar")


class Ofx(unittest.TestCase):
    def setUp(self):
        limpiar()

    def test_leer_ofx(self):
        ruta = os.path.join(DATOS_PRUEBA, "cartola_ejemplo.ofx")
        r = recetas.detectar(ruta, {})
        self.assertEqual((r["id"], r["institucion"], r["moneda"]), ("xx-ofx", "Banco Ejemplo", "USD"))
        movs, avisos = recetas.aplicar(ruta, r, "banco-ejemplo")
        self.assertEqual([(m["fecha"], m["monto"]) for m in movs], [("2026-10-03", -45.2), ("2026-10-05", -12.0), ("2026-10-15", 1500.0)])
        self.assertEqual(movs[0]["descripcion"], "SUPERMERCADO EJEMPLO Compra con tarjeta")
        self.assertEqual(len({m["id"] for m in movs}), 3)

    def test_importar_ofx_sin_duplicar(self):
        ruta = os.path.join(DATOS_PRUEBA, "cartola_ejemplo.ofx")
        v = correr("importar.py", "vista", ruta)
        self.assertEqual((v["ok"], v["receta"]["id"], v["total"]), (True, "xx-ofx", 3))
        self.assertEqual(correr("importar.py", "guardar", ruta, "xx-ofx", "0")["nuevos"], 3)
        self.assertEqual(correr("importar.py", "guardar", ruta, "xx-ofx", "0")["repetidos"], 3)

    def test_camt053(self):
        ruta = os.path.join(DATOS_PRUEBA, "cartola_ejemplo_camt053.xml")
        r = recetas.detectar(ruta, {})
        self.assertEqual(r["id"], "xx-camt053")
        movs, _ = recetas.aplicar(ruta, r, "banco-europa")
        self.assertEqual([(m["fecha"], m["monto"], m["moneda"]) for m in movs], [("2026-10-02", -42.1, "EUR"), ("2026-10-15", 2100.0, "EUR")],
                         "DBIT es negativo y las pendientes (PDNG) no entran")
        self.assertEqual(movs[0]["descripcion"], "Supermercado Ejemplo Compra con tarjeta")

    def test_qif(self):
        ruta = os.path.join(DATOS_PRUEBA, "cartola_ejemplo.qif")
        r = recetas.detectar(ruta, {})
        self.assertEqual(r["id"], "xx-qif")
        movs, _ = recetas.aplicar(ruta, r, "cuenta-qif")
        self.assertEqual([(m["fecha"], m["monto"]) for m in movs], [("2026-10-25", -15.5), ("2026-10-03", 1200.0)], "25/10 → día/mes")



PDF_SIMPLE = os.path.join(DATOS_PRUEBA, "cartola_ejemplo.pdf")
PDF_COMPRIMIDO = os.path.join(DATOS_PRUEBA, "cartola_ejemplo_comprimida.pdf")
RECETA_PDF = {**RECETA, "id": "cl-banco-ejemplo-pdf", "nombre": "Banco Ejemplo — cartola en PDF", "archivo": {"extension": ["pdf"]}}
RECETA_BILLETERA = {"formato": 1, "id": "cl-billetera-ejemplo-pdf", "nombre": "Billetera Ejemplo (PDF)", "institucion": "Billetera Ejemplo",
                    "pais": "CL", "moneda": "CLP", "tipo": "cartola", "archivo": {"extension": ["pdf"]},
                    "reconocer": {"encabezados": ["Fecha", "Detalle", "Monto", "Saldo"]},
                    "columnas": {"fecha": "Fecha", "descripcion": "Detalle", "monto": "Monto"}, "fecha": "%Y-%m-%d",
                    "numeros": {"decimal": ",", "miles": "."}, "signo": "normal", "ignorar_si_contiene": ["SALDO ANTERIOR"]}


def pdf_minimo(ruta, objetos, trailer_extra=""):
    """Un PDF chico armado a mano (para los casos raros: cifrado, escaneado)."""
    cuerpo = bytearray(b"%PDF-1.4\n")
    for n, o in enumerate(objetos, 1):
        cuerpo += f"{n} 0 obj\n".encode() + o + b"\nendobj\n"
    cuerpo += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R {trailer_extra}>>\n%%EOF\n".encode()
    with open(ruta, "wb") as f:
        f.write(cuerpo)
    return ruta


class Pdf(unittest.TestCase):
    def setUp(self):
        limpiar()

    def test_tabla_simple(self):
        filas = pdf.tabla(PDF_SIMPLE)
        self.assertIn(["Titular: Ana Pérez"], filas, "WinAnsi: la é es un byte")
        self.assertIn(["Fecha", "Descripción", "Cargos", "Abonos", "Saldo"], filas)
        self.assertIn(["05/10/2026", "REMUNERACION EMPRESA FICTICIA SPA", "", "1.250.000", "2.057.160"], filas,
                      "el abono cae en su columna aunque la de cargos venga vacía, y el TJ con ajuste deja los espacios")

    def test_detectar_y_aplicar_igual_que_el_csv(self):
        r = recetas.detectar(PDF_SIMPLE, {RECETA["id"]: RECETA, RECETA_PDF["id"]: RECETA_PDF})
        self.assertEqual(r["id"], RECETA_PDF["id"], "la receta de CSV no se prueba con un PDF")
        movs, avisos = recetas.aplicar(PDF_SIMPLE, RECETA_PDF, "banco-ejemplo")
        del_csv, _ = recetas.aplicar(CARTOLA, RECETA, "banco-ejemplo")
        quitar = lambda lista: [{k: v for k, v in m.items() if k != "origen"} for m in lista]
        self.assertEqual(quitar(movs), quitar(del_csv), "mismo resultado (e ids) que la misma cartola en CSV")
        self.assertTrue(any("Total cargos" in a for a in avisos))

    def test_comprimido_type0_tounicode(self):
        filas = pdf.tabla(PDF_COMPRIMIDO, RECETA_BILLETERA["reconocer"]["encabezados"])
        self.assertIn(["Ana Pérez"], filas, "el título viene de un formulario (Do)")
        movs, _ = recetas.aplicar(PDF_COMPRIMIDO, RECETA_BILLETERA, "billetera-ejemplo")
        self.assertEqual([(m["fecha"], m["descripcion"], m["monto"]) for m in movs], [
            ("2026-10-02", "CAFÉ LA ESQUINA", -3400), ("2026-10-04", "DELIVERY RAPIDITO *PEDIDO", -14990),
            ("2026-10-06", "PAGO SUSCRIPCIÓN MÚSICA PREMIUM", -5490), ("2026-10-09", "CARGA DESDE BANCO EJEMPLO", 50000),
            ("2026-10-12", "VIAJES APP *TRIP", -6200), ("2026-10-15", "DEVOLUCIÓN TIENDA ONLINE", 9990),
            ("2026-10-18", "TRANSFERENCIA DE MATÍAS SOTO", 20000)],
            "dos páginas (la segunda escalada con cm), encabezado repetido y una descripción en dos líneas")

    def test_xref_rota(self):
        with open(PDF_SIMPLE, "rb") as f:
            crudo = f.read()
        roto = crudo.replace(b"startxref\n", b"startxref\n9").replace(b"0000000", b"0000999")
        ruta = os.path.join(TMP, "rota.pdf")
        with open(ruta, "wb") as f:
            f.write(roto)
        self.assertEqual(pdf.tabla(ruta), pdf.tabla(PDF_SIMPLE), "se lee igual aunque la tabla xref mienta")

    def test_cmap(self):
        mapa, largos = pdf.leer_cmap(b"1 begincodespacerange <0000> <FFFF> endcodespacerange 1 beginbfchar <0003> <0020> endbfchar "
                                     b"2 beginbfrange <0010> <0012> <00E1> <0020> <0021> [<0041> <D83DDE00>] endbfrange")
        self.assertEqual(largos, [2])
        self.assertEqual([mapa[bytes.fromhex(h)] for h in ("0003", "0010", "0012", "0020", "0021")], [" ", "á", "ã", "A", "😀"])
        self.assertEqual([pdf.glifo(g) for g in ("aacute", "Ntilde", "uni00F3", "period", "zzz")], ["á", "Ñ", "ó", ".", ""])

    def test_errores_claros(self):
        pagina = b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
        cifrado = pdf_minimo(os.path.join(TMP, "cifrado.pdf"), [*pagina, b"<< /Type /Page /Parent 2 0 R >>", b"<< /Filter /Standard >>"],
                             "/Encrypt 4 0 R ")
        imagen = b"q 500 0 0 700 50 50 cm /Im1 Do Q"
        escaneado = pdf_minimo(os.path.join(TMP, "escaneado.pdf"), [*pagina,
            b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /XObject << /Im1 5 0 R >> >> >>",
            f"<< /Length {len(imagen)} >>\nstream\n".encode() + imagen + b"\nendstream",
            b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /Filter /DCTDecode /Length 1 >>\nstream\nx\nendstream"])
        falso = os.path.join(TMP, "falso.pdf")
        with open(falso, "w") as f:
            f.write("Fecha;Monto\n")
        for ruta, texto in ((cifrado, "protegido con clave"), (escaneado, "imagen escaneada"), (falso, "no parece un PDF")):
            with self.assertRaises(pdf.PdfError) as e:
                pdf.tabla(ruta)
            self.assertIn(texto, str(e.exception))
            v = correr("importar.py", "vista", ruta)
            self.assertEqual((v["ok"], texto in v["error"]), (False, True), v)
            self.assertFalse(v["error"].startswith("No pude leer"), "el mensaje va tal cual, sin prefijos")
        r = correr("receta_ia.py", escaneado, "CL")
        self.assertIn("imagen escaneada", r["error"])

    def test_importar_de_punta_a_punta(self):
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", RECETA_PDF["id"] + ".json"), RECETA_PDF)
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", RECETA["id"] + ".json"), RECETA)
        v = correr("importar.py", "vista", PDF_SIMPLE)
        self.assertEqual((v["ok"], v["receta"]["id"], v["total"]), (True, RECETA_PDF["id"], 9), v)
        self.assertEqual(correr("importar.py", "guardar", PDF_SIMPLE, RECETA_PDF["id"], "1")["nuevos"], 9)
        otra = correr("importar.py", "guardar", CARTOLA, RECETA["id"], "0")
        self.assertEqual((otra["nuevos"], otra["repetidos"]), (0, 9), "el mismo banco en CSV no duplica lo que vino en PDF")

    def test_receta_con_ia_desde_pdf(self):
        r = correr("receta_ia.py", PDF_SIMPLE, "CL")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["total"], 9)
        self.assertIn("pdf", r["receta"]["archivo"]["extension"], "la receta reconoce el archivo con que se probó")
        self.assertNotIn("separador", r["receta"]["archivo"])
        self.assertEqual(recetas.validar(r["receta"]), [])

    def test_carpeta_vigilada(self):
        import time
        import vigilar
        carpeta = os.path.join(TMP, "DescargasPdf")
        shutil.rmtree(carpeta, ignore_errors=True)
        os.makedirs(carpeta)
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", RECETA_PDF["id"] + ".json"), RECETA_PDF)
        vigilar.activar()
        shutil.copy(PDF_SIMPLE, os.path.join(carpeta, "cartola.pdf"))
        shutil.copy(PDF_COMPRIMIDO, os.path.join(carpeta, "boleta.pdf"))
        r = vigilar.revisar(carpeta, ahora=time.time() + 10)
        self.assertEqual([x["archivo"] for x in r["importados"]], ["cartola.pdf"])
        self.assertEqual(r["sin_receta"], [], "un PDF que no es cartola no genera avisos")
        self.assertEqual(correr("estado.py")["vigilar"]["recientes"][0]["archivo"], "cartola.pdf", "lo ignorado no se muestra")

class Vigilar(unittest.TestCase):
    def setUp(self):
        limpiar()
        self.carpeta = os.path.join(TMP, "Descargas")
        shutil.rmtree(self.carpeta, ignore_errors=True)
        os.makedirs(self.carpeta)
        os.makedirs(os.path.join(datos.INTERNO, "recetas"), exist_ok=True)
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", RECETA["id"] + ".json"), RECETA)

    def test_solo_lo_nuevo_y_una_vez(self):
        import time
        import vigilar
        viejo = os.path.join(self.carpeta, "vieja.csv")
        shutil.copy(CARTOLA, viejo)
        os.utime(viejo, (time.time() - 3600, time.time() - 3600))
        self.assertFalse(vigilar.revisar(self.carpeta)["ok"], "sin activar no hace nada")
        vigilar.activar()
        shutil.copy(CARTOLA, os.path.join(self.carpeta, "cartola.csv"))
        for nombre, texto in (("notas.csv", "a,b\n1,2\n"), ("foto.jpg", "x")):
            with open(os.path.join(self.carpeta, nombre), "w") as f:
                f.write(texto)
        r = vigilar.revisar(self.carpeta, ahora=time.time() + 10)
        self.assertEqual([x["archivo"] for x in r["importados"]], ["cartola.csv"], "la vieja (de antes de activar) no se toca")
        self.assertGreater(r["importados"][0]["nuevos"], 0)
        self.assertEqual(r["sin_receta"], ["notas.csv"])
        r = vigilar.revisar(self.carpeta, ahora=time.time() + 20)
        self.assertEqual((r["importados"], r["sin_receta"]), ([], []), "lo revisado no se vuelve a revisar")
        self.assertTrue(os.path.exists(viejo) and os.path.exists(os.path.join(self.carpeta, "cartola.csv")), "nunca borra")

    def test_espera_que_termine_la_descarga(self):
        import vigilar
        vigilar.activar()
        shutil.copy(CARTOLA, os.path.join(self.carpeta, "cartola.csv"))
        self.assertEqual(vigilar.revisar(self.carpeta)["importados"], [], "recién escrito: espera unos segundos")


class Mcp(unittest.TestCase):
    """El servidor MCP como lo usa una IA: initialize, tools/list y tools/call por stdio."""

    def setUp(self):
        limpiar()
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", "cl-banco-ejemplo.json"), RECETA)
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")

    def hablar(self, *mensajes):
        entrada = "\n".join(json.dumps(m) for m in mensajes) + "\n"
        p = subprocess.run([sys.executable, os.path.join(RAIZ, "bin", "mcp_servidor.py")], input=entrada, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        return [json.loads(x) for x in p.stdout.splitlines() if x.strip()]

    def test_protocolo_y_herramientas(self):
        r = self.hablar({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "prueba"}}},
                        {"jsonrpc": "2.0", "method": "notifications/initialized"},
                        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "buscar_movimientos", "arguments": {"texto": "cafe la esquina", "desde": "2026-10-01"}}},
                        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "gastos_por_categoria", "arguments": {"desde": "2026-10-01", "hasta": "2026-10-31"}}},
                        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "borrar_todo", "arguments": {}}},
                        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "buscar_movimientos", "arguments": {"desde": "ayer"}}})
        self.assertEqual(len(r), 6, "la notificación no lleva respuesta")
        self.assertEqual(r[0]["result"]["protocolVersion"], "2025-06-18")
        nombres = {t["name"] for t in r[1]["result"]["tools"]}
        self.assertTrue({"resumen_del_mes", "buscar_movimientos", "gastos_por_categoria", "presupuesto", "cuentas_y_datos"} <= nombres)
        self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in r[1]["result"]["tools"]), "todo es de solo lectura")
        cafe = r[2]["result"]["structuredContent"]
        self.assertEqual(cafe["encontrados"], 2)
        self.assertLess(cafe["suma_montos"], 0)
        self.assertNotIn("id", cafe["movimientos"][0], "no hace falta mostrar ids internos")
        self.assertGreater(r[3]["result"]["structuredContent"]["total_gastado"], 0)
        self.assertIn("error", r[4])
        self.assertTrue(r[5]["result"]["isError"])

    def test_compromisos(self):
        c, _ = compromisos.validar({"nombre": "Sueldo", "tipo": "ingreso", "monto": 1250000, "dia": 5, "buscar": ["REMUNERACION"],
                                    "desde": "2026-10-01"}, None, "2026-10-01")
        datos.escribir_json(compromisos.RUTA, {"formato": 1, "compromisos": [c], "descartados": []})
        r = self.hablar({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "compromisos", "arguments": {"mes": "2026-10"}}})
        s = r[0]["result"]["structuredContent"]
        self.assertEqual(s["ingresos_recibidos"], 1250000)
        self.assertEqual(s["compromisos"][0]["estado"], "pagado")
        self.assertNotIn(c["id"], json.dumps(s), "sin ids internos")
        self.assertNotIn("movimiento", json.dumps(s))

    def test_no_escribe_nada(self):
        antes = {f: os.path.getmtime(os.path.join(datos.MOVIMIENTOS, f)) for f in os.listdir(datos.MOVIMIENTOS)}
        for n in ["resumen_del_mes", "presupuesto", "comparar_meses", "principales_comercios", "cuentas_y_datos", "compromisos"]:
            r = self.hablar({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": n, "arguments": {}}})
            self.assertFalse(r[0]["result"]["isError"], n)
        self.assertEqual(antes, {f: os.path.getmtime(os.path.join(datos.MOVIMIENTOS, f)) for f in os.listdir(datos.MOVIMIENTOS)})


class McpConectar(unittest.TestCase):
    """Conectar con cada IA en un HOME falso, con CLI falsos que anotan lo que se les pide (nunca toca tu configuración real)."""

    def setUp(self):
        self.home = os.path.join(TMP, "home")
        shutil.rmtree(self.home, ignore_errors=True)
        os.makedirs(os.path.join(self.home, "bin"))
        self.registro = os.path.join(self.home, "registro.txt")
        for cli in ("claude", "codex", "gemini"):
            ruta = os.path.join(self.home, "bin", cli)
            with open(ruta, "w") as f:
                f.write(f"#!/bin/sh\necho {cli} \"$@\" >> {self.registro}\n")
            os.chmod(ruta, 0o755)

    def correr(self, *args, extra=None):
        salida = os.path.join(self.home, "salida.json")
        env = {**os.environ, "HOME": self.home, "PATH": os.path.join(self.home, "bin") + os.pathsep + "/usr/bin:/bin", **(extra or {})}
        p = subprocess.run([sys.executable, os.path.join(RAIZ, "bin", "mcp_conectar.py"), *args, salida], capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        with open(salida, encoding="utf-8") as f:
            return json.load(f)

    def test_cli_y_archivos(self):
        e = {c["id"]: c for c in self.correr("estado")["clientes"]}
        self.assertTrue(e["claude_code"]["instalado"] and e["codex"]["instalado"] and e["gemini"]["instalado"])
        self.assertTrue(self.correr("conectar", "claude_code")["ok"])
        self.assertTrue(self.correr("conectar", "codex")["ok"])
        with open(self.registro) as f:
            lineas = f.read().splitlines()
        self.assertTrue(lineas[0].startswith("claude mcp add --scope user alcancia -- "), lineas[0])
        self.assertTrue(lineas[0].endswith("bin/mcp_servidor.py"))
        self.assertTrue(lineas[1].startswith("codex mcp add alcancia -- "))
        # Claude Desktop y Antigravity: se edita su archivo sin tocar lo demás y se guarda una copia
        cfg = os.path.join(self.home, ".config", "Claude", "claude_desktop_config.json") if sys.platform != "darwin" else \
            os.path.join(self.home, "Library", "Application Support", "Claude", "claude_desktop_config.json")
        os.makedirs(os.path.dirname(cfg))
        with open(cfg, "w") as f:
            json.dump({"mcpServers": {"otro": {"command": "x"}}, "tema": "oscuro"}, f)
        r = self.correr("conectar", "claude_desktop")
        self.assertTrue(r["ok"], r)
        with open(cfg) as f:
            d = json.load(f)
        self.assertEqual(d["tema"], "oscuro")
        self.assertEqual(set(d["mcpServers"]), {"otro", "alcancia"})
        self.assertTrue(os.path.exists(cfg + ".antes-de-alcancia"))
        self.assertTrue(next(c for c in r["clientes"] if c["id"] == "claude_desktop")["al_dia"])
        self.assertTrue(self.correr("quitar", "claude_desktop")["ok"])
        with open(cfg) as f:
            self.assertEqual(set(json.load(f)["mcpServers"]), {"otro"})

    def test_archivo_roto_no_se_toca(self):
        cfg = os.path.join(self.home, ".gemini", "config", "mcp_config.json")
        os.makedirs(os.path.dirname(cfg))
        with open(cfg, "w") as f:
            f.write("{ esto no es json")
        r = self.correr("conectar", "antigravity")
        self.assertFalse(r["ok"])
        with open(cfg) as f:
            self.assertEqual(f.read(), "{ esto no es json")

    def test_reparar_ruta_vieja(self):
        cfg = os.path.join(self.home, ".gemini", "config", "mcp_config.json")
        os.makedirs(os.path.dirname(cfg))
        with open(cfg, "w") as f:
            json.dump({"mcpServers": {"alcancia": {"command": "python3", "args": ["/ruta/vieja/mcp_servidor.py"]}}}, f)
        r = self.correr("reparar")
        self.assertEqual(r["arreglados"], ["antigravity"])
        with open(cfg) as f:
            self.assertTrue(json.load(f)["mcpServers"]["alcancia"]["args"][0].endswith("bin/mcp_servidor.py"))


class Conectores(unittest.TestCase):
    """Cada conector contra un servidor falso con respuestas como las de su documentación (datos inventados)."""

    def setUp(self):
        limpiar()
        sys.path.insert(0, os.path.join(RAIZ, "pruebas"))

    def sinc(self, srv, accion, conector, cred):
        salida = os.path.join(TMP, "salida-conector.json")
        env = {**os.environ, "ALCANCIA_RED_PRUEBA": srv.url}
        env.pop("ALCANCIA_RECURSOS", None)
        p = subprocess.run([sys.executable, os.path.join(RAIZ, "bin", "sincronizar.py"), accion, conector, salida], capture_output=True, text=True,
                           env=env, input=json.dumps(cred))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.ultima_salida = p.stdout
        with open(salida, encoding="utf-8") as f:
            r = json.load(f)
        for v in (x for x in cred.values() if len(str(x)) >= 6):  # (las de prueba muy cortas calzarían con cualquier texto)
            self.assertNotIn(str(v), p.stdout + p.stderr + json.dumps(r), "la credencial nunca se imprime ni va al archivo de salida")
        nueva = [x for x in p.stdout.splitlines() if x.startswith("CREDENCIAL ")]
        if nueva:
            r["credencial_stdout"] = json.loads(nueva[-1][len("CREDENCIAL "):])
        return r

    def movs(self, conector):
        return sorted((m for m in datos.leer_todos() if m["origen"] == f"conector:{conector}"), key=lambda m: (m["fecha"], m["monto"]))

    def test_registro_y_red(self):
        import conectores
        from red import ErrorRed, Red
        todos = conectores.todos()
        self.assertTrue({"mercadopago", "paypal", "simplefin", "up", "akahu", "stripe", "buda"} <= set(todos))
        for c in todos.values():
            for k in ("id", "nombre", "paises", "hosts", "campos", "pasos", "estado"):
                self.assertIn(k, c.INFO, f"{c.INFO.get('id')}: falta {k}")
            self.assertTrue(all(h and "/" not in h for h in c.INFO["hosts"]))
        red = Red(["api.ejemplo.com"], "Ejemplo")
        for mala in ("http://api.ejemplo.com/x", "https://otro.com/x", "https://api.ejemplo.com.otro.com/x"):
            with self.assertRaises(ErrorRed):
                red.get(mala)

    def test_textos_traducidos(self):
        import conectores
        en = datos.leer_json(os.path.join(RAIZ, "ui", "idiomas", "en.json"), {})["textos"]
        for c in conectores.todos().values():
            for t in c.INFO["pasos"] + [f["etiqueta"] for f in c.INFO["campos"]] + ([c.INFO["nota"]] if c.INFO.get("nota") else []):
                self.assertIn(t, en, f"{c.INFO['id']}: falta la traducción de «{t[:50]}»")

    def test_conector_desconocido_y_llave_mala(self):
        from servidor_falso import ServidorFalso
        with ServidorFalso({("GET", "api.mercadopago.com/users/me"): lambda q, b, h: (401, {"message": "invalid token"})}) as srv:
            r = self.sinc(srv, "probar", "mercadopago", {"token": "APP_USR-mala"})
            self.assertFalse(r["ok"])
            self.assertIn("no aceptó la llave", r["error"])
            self.assertFalse(self.sinc(srv, "probar", "inventado", {})["ok"])
            self.assertFalse(self.sinc(srv, "probar", "mercadopago", {})["ok"], "sin llave ni siquiera intenta")

    def test_mercadopago(self):
        from servidor_falso import ServidorFalso
        def buscar(q, b, h):
            self.assertEqual(h["authorization"], "Bearer APP_USR-123")
            if "payer.id" in q:
                return 200, {"paging": {"total": 2, "limit": 50, "offset": 0}, "results": [
                    {"id": 11, "status": "approved", "transaction_amount": 12990, "currency_id": "CLP", "date_approved": "2026-10-03T12:10:44.000-03:00",
                     "description": "Pedido Delivery Ejemplo", "operation_type": "regular_payment"},
                    {"id": 12, "status": "rejected", "transaction_amount": 5000, "currency_id": "CLP", "date_created": "2026-10-04T10:00:00.000-03:00"}]}
            return 200, {"paging": {"total": 1}, "results": [{"id": 13, "status": "approved", "transaction_amount": 20000, "currency_id": "CLP",
                                                              "date_approved": "2026-10-05T09:00:00.000-03:00", "description": "", "operation_type": "money_transfer"}]}
        rutas = {("GET", "api.mercadopago.com/users/me"): lambda q, b, h: (200, {"id": 999, "site_id": "MLC"}),
                 ("GET", "api.mercadopago.com/v1/payments/search"): buscar}
        with ServidorFalso(rutas) as srv:
            p = self.sinc(srv, "probar", "mercadopago", {"token": "APP_USR-123"})
            self.assertEqual((p["ok"], p["cuentas"][0]["moneda"]), (True, "CLP"))
            r = self.sinc(srv, "traer", "mercadopago", {"token": "APP_USR-123"})
            self.assertEqual((r["ok"], r["nuevos"]), (True, 2), r)
            self.assertEqual([(m["fecha"], m["monto"], m["descripcion"]) for m in self.movs("mercadopago")],
                             [("2026-10-03", -12990, "Pago: Pedido Delivery Ejemplo"), ("2026-10-05", 20000, "Transferencia")])
            self.assertEqual(self.sinc(srv, "traer", "mercadopago", {"token": "APP_USR-123"})["nuevos"], 0, "no duplica")
        e = datos.leer_json(os.path.join(datos.INTERNO, "conexiones.json"), None)["mercadopago"]
        self.assertTrue(e["conectado"] and e["hasta"])
        self.assertNotIn("APP_USR", json.dumps(e), "el estado no guarda la llave")
        cuentas = datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), None)
        self.assertEqual(cuentas[0]["conector"], "mercadopago")

    def test_mercadopago_pagos_a_ti_mismo(self):
        """Cargar saldo o mover plata a una reserva sale en las dos búsquedas (pagador y cobrador): va una sola vez y entre tus cuentas."""
        from servidor_falso import ServidorFalso
        propio = {"id": 21, "status": "approved", "transaction_amount": 300000, "currency_id": "CLP", "date_approved": "2026-10-22T10:00:00.000-03:00",
                  "description": "", "operation_type": "account_fund", "collector_id": 999, "payer": {"id": 999}}
        compra = {"id": 22, "status": "approved", "transaction_amount": 5990, "currency_id": "CLP", "date_approved": "2026-10-22T13:00:00.000-03:00",
                  "description": "Panadería Ejemplo", "operation_type": "regular_payment", "collector_id": 555, "payer": {"id": 999}}
        def buscar(q, b, h):
            return 200, {"paging": {"total": 2 if "payer.id" in q else 1}, "results": [propio, compra] if "payer.id" in q else [propio]}
        rutas = {("GET", "api.mercadopago.com/users/me"): lambda q, b, h: (200, {"id": 999, "site_id": "MLC"}),
                 ("GET", "api.mercadopago.com/v1/payments/search"): buscar}
        # Lo que dejó la versión anterior: el mismo pago a ti mismo como gasto y como ingreso.
        viejo = [{"id": i, "fecha": "2026-09-15", "descripcion": "Carga de saldo", "monto": m, "moneda": "CLP", "categoria": "", "cuenta": "mercadopago",
                  "origen": "conector:mercadopago", "nota": ""} for i, m in (("a1", -200000), ("a2", 200000))]
        viejo.append({"id": "a3", "fecha": "2026-09-15", "descripcion": "Café Ejemplo", "monto": -2500, "moneda": "CLP", "categoria": "comida",
                      "cuenta": "mercadopago", "origen": "conector:mercadopago", "nota": ""})
        datos.escribir_mes("2026-09", viejo)
        with ServidorFalso(rutas) as srv:
            self.sinc(srv, "probar", "mercadopago", {"token": "APP_USR-123"})
            r = self.sinc(srv, "traer", "mercadopago", {"token": "APP_USR-123"})
            self.assertEqual((r["ok"], r["nuevos"], r["reparados"]), (True, 2, 1), r)
            octubre = [(m["monto"], m["categoria"]) for m in datos.leer_mes("2026-10")]
            self.assertIn((300000, "transferencia"), octubre, "una sola vez y entre tus cuentas")
            self.assertNotIn(-300000, [m for m, _ in octubre], "no queda como gasto")
            self.assertIn(-5990, [m for m, _ in octubre])
            self.assertEqual(sorted((m["monto"], m["categoria"]) for m in datos.leer_mes("2026-09")), [(-2500, "comida"), (200000, "transferencia")],
                             "lo guardado antes se repara: se va el gasto espejo, lo demás queda igual")
            self.assertEqual(self.sinc(srv, "traer", "mercadopago", {"token": "APP_USR-123"})["reparados"], 0, "la reparación corre una sola vez")

    def test_paypal(self):
        from servidor_falso import ServidorFalso
        def token(q, b, h):
            import base64
            self.assertEqual(h["authorization"], "Basic " + base64.b64encode(b"id:sec").decode())
            self.assertIn("grant_type=client_credentials", b)
            return 200, {"access_token": "A21", "scope": "https://uri.paypal.com/services/reporting/search/read openid"}
        def trans(q, b, h):
            self.assertEqual(q["transaction_status"], "S")
            if q["page"] == "1":
                return 200, {"total_pages": 2, "transaction_details": [{"transaction_info": {"transaction_id": "5TY", "transaction_event_code": "T0006",
                    "transaction_initiation_date": "2026-10-05T10:15:00-03:00", "transaction_amount": {"currency_code": "USD", "value": "-25.00"},
                    "transaction_status": "S", "transaction_subject": "Suscripción Ejemplo"}}]}
            return 200, {"total_pages": 2, "transaction_details": [{"transaction_info": {"transaction_id": "6UZ", "transaction_event_code": "T0011",
                    "transaction_initiation_date": "2026-10-06T10:15:00-03:00", "transaction_amount": {"currency_code": "USD", "value": "100.00"},
                    "transaction_status": "S"}, "payer_info": {"payer_name": {"alternate_full_name": "Matías Soto"}}}]}
        with ServidorFalso({("POST", "api-m.paypal.com/v1/oauth2/token"): token, ("GET", "api-m.paypal.com/v1/reporting/transactions"): trans}) as srv:
            self.assertTrue(self.sinc(srv, "probar", "paypal", {"client_id": "id", "secret": "sec"})["ok"])
            self.assertTrue(self.sinc(srv, "traer", "paypal", {"client_id": "id", "secret": "sec"})["ok"])
            ventanas = [x for x in srv.pedidos if x[1].endswith("reporting/transactions")]
            self.assertGreaterEqual(len(ventanas), 2 * 6, "ventanas de 31 días como máximo (180 días = 6+ ventanas, 2 páginas c/u)")
        movs = self.movs("paypal")
        self.assertEqual({(m["descripcion"], m["monto"]) for m in movs}, {("Suscripción Ejemplo", -25.0), ("Matías Soto", 100.0)})

    def test_paypal_sin_transaction_search(self):
        from servidor_falso import ServidorFalso
        with ServidorFalso({("POST", "api-m.paypal.com/v1/oauth2/token"): lambda q, b, h: (200, {"access_token": "A", "scope": "openid"})}) as srv:
            r = self.sinc(srv, "probar", "paypal", {"client_id": "id", "secret": "sec"})
            self.assertIn("Transaction Search", r["error"])

    def test_simplefin_canjea_una_vez(self):
        import base64
        from servidor_falso import ServidorFalso
        rutas = {("POST", "beta-bridge.simplefin.org/simplefin/claim/abc"): lambda q, b, h: (200, "https://usu:cla@beta-bridge.simplefin.org/simplefin"),
                 ("GET", "beta-bridge.simplefin.org/simplefin/accounts"): lambda q, b, h: (200, {"errors": [], "accounts": [{"id": "A1", "name": "Checking",
                    "currency": "USD", "transactions": [
                        {"id": "t1", "posted": 1791460800, "amount": "-33.20", "description": "Grocery Example", "pending": False},
                        {"id": "t2", "posted": 0, "amount": "-5.00", "description": "Pendiente", "pending": True}]}]})}
        token = base64.b64encode(b"https://beta-bridge.simplefin.org/simplefin/claim/abc").decode()
        with ServidorFalso(rutas) as srv:
            r = self.sinc(srv, "probar", "simplefin", {"token": token})
            self.assertNotIn("credencial", r, "la llave nueva nunca va al archivo de salida")
            self.assertEqual(r["credencial_stdout"], {"acceso": "https://usu:cla@beta-bridge.simplefin.org/simplefin"}, "devuelve la llave definitiva por stdout")
            self.assertEqual(r["cuentas"][0]["nombre"], "Checking")
            auth = [x[4]["authorization"] for x in srv.pedidos if x[1].endswith("/accounts")][0]
            self.assertEqual(auth, "Basic " + base64.b64encode(b"usu:cla").decode())
            t = self.sinc(srv, "traer", "simplefin", r["credencial_stdout"])
            self.assertEqual(t["nuevos"], 1, "las pendientes no se guardan")
            self.assertNotIn("credencial_stdout", t, "ya canjeada, no hay llave nueva")

    def test_up_paginado(self):
        from servidor_falso import ServidorFalso
        def tx(q, b, h):
            mov = lambda i, desc, valor, f: {"id": i, "attributes": {"status": "SETTLED", "description": desc, "amount": {"currencyCode": "AUD", "value": valor},
                                                                    "settledAt": f}, "relationships": {"account": {"data": {"id": "acc"}}}}
            if q.get("cursor") == "2":
                return 200, {"data": [mov("u2", "Café Ejemplo", "-4.50", "2026-10-02T09:00:00+10:00")], "links": {"next": None}}
            self.assertEqual(q["filter[status]"], "SETTLED")
            # links.next real apunta a https://api.up.com.au/…; red.py lo manda al servidor falso
            return 200, {"data": [mov("u1", "Sueldo Ejemplo", "2500.00", "2026-10-01T09:00:00+10:00")],
                         "links": {"next": "https://api.up.com.au/api/v1/transactions?cursor=2"}}
        with ServidorFalso({("GET", "api.up.com.au/api/v1/transactions"): tx}) as srv:
            self.assertEqual(self.sinc(srv, "traer", "up", {"token": "up:yeah:x"})["nuevos"], 2)
        self.assertEqual([m["monto"] for m in self.movs("up")], [2500.0, -4.5])

    def test_stripe_monedas(self):
        from servidor_falso import ServidorFalso
        def bt(q, b, h):
            if "starting_after" not in q:
                return 200, {"has_more": True, "data": [{"id": "txn_1", "net": -400, "currency": "usd", "created": 1791460800, "type": "stripe_fee", "description": None}]}
            return 200, {"has_more": False, "data": [{"id": "txn_2", "net": 15000, "currency": "clp", "created": 1791547200, "type": "charge", "description": "Venta Ejemplo"}]}
        with ServidorFalso({("GET", "api.stripe.com/v1/balance_transactions"): bt}) as srv:
            self.assertIn("restringida", self.sinc(srv, "probar", "stripe", {"llave": "sk_live_x"})["error"], "no acepta la clave secreta completa")
            self.assertEqual(self.sinc(srv, "traer", "stripe", {"llave": "rk_live_x"})["nuevos"], 2)
        self.assertEqual({(m["moneda"], m["monto"]) for m in self.movs("stripe")}, {("USD", -4.0), ("CLP", 15000.0)})

    def test_buda_firma(self):
        import hashlib
        import hmac
        from servidor_falso import ServidorFalso
        def dep(q, b, h):
            ruta = "/api/v2/currencies/clp/deposits?" + "&".join(f"{k}={v}" for k, v in q.items())
            esperada = hmac.new(b"sec", f"GET {ruta} {h['x-sbtc-nonce']}".encode(), hashlib.sha384).hexdigest()
            self.assertEqual(h["x-sbtc-signature"], esperada)
            return 200, {"deposits": [{"id": "D1", "created_at": "2026-10-01T15:00:00.000Z", "amount": ["50000.0", "CLP"], "state": "confirmed"},
                                      {"id": "D0", "created_at": "2020-01-01T15:00:00.000Z", "amount": ["1.0", "CLP"], "state": "confirmed"}], "meta": {"total_pages": 9}}
        rutas = {("GET", "www.buda.com/api/v2/currencies/clp/deposits"): dep}
        rutas.update({("GET", f"www.buda.com/api/v2/currencies/{m}/{t}"): (lambda q, b, h, t=t: (200, {t: [], "meta": {"total_pages": 1}}))
                      for m in ("clp", "pen", "cop") for t in ("deposits", "withdrawals") if (m, t) != ("clp", "deposits")})
        with ServidorFalso(rutas) as srv:
            r = self.sinc(srv, "traer", "buda", {"llave": "k", "secreto": "sec"})
            self.assertEqual(r["nuevos"], 1, r)
            self.assertEqual(len([x for x in srv.pedidos if "clp/deposits" in x[1]]), 1, "deja de paginar al pasar la fecha pedida")
        self.assertEqual(self.movs("buda")[0]["monto"], 50000)

    def test_no_sigue_redirecciones(self):
        from servidor_falso import ServidorFalso
        import http.server, threading
        robadas = []

        class Ladron(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                robadas.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()

        ladron = http.server.HTTPServer(("127.0.0.1", 0), Ladron)
        threading.Thread(target=ladron.serve_forever, daemon=True).start()
        destino = f"http://127.0.0.1:{ladron.server_address[1]}/robar"

        with ServidorFalso({("GET", "api.stripe.com/v1/balance_transactions"): lambda q, b, h: (302, "", {"Location": destino})}) as srv:
            r = self.sinc(srv, "probar", "stripe", {"llave": "rk_live_SECRETO_DE_PRUEBA"})
        ladron.shutdown()
        ladron.server_close()
        self.assertFalse(r["ok"])
        self.assertEqual(robadas, [], "la llave nunca viaja a otro dominio")

    def test_la_ia_no_hereda_nada_de_alcancia(self):
        import ia
        os.environ["ALCANCIA_RED_PRUEBA"] = "http://127.0.0.1:1"
        try:
            self.assertFalse(any(k.startswith("ALCANCIA_") for k in ia._entorno_ia()))
        finally:
            del os.environ["ALCANCIA_RED_PRUEBA"]

    def test_esperar_y_error_quedan_en_estado(self):
        from servidor_falso import ServidorFalso
        with ServidorFalso({("GET", "api.mercadopago.com/users/me"): lambda q, b, h: (429, {})}) as srv:
            r = self.sinc(srv, "traer", "mercadopago", {"token": "x"})
        self.assertFalse(r["ok"])
        e = datos.leer_json(os.path.join(datos.INTERNO, "conexiones.json"), None)["mercadopago"]
        self.assertIn("esperar", e["error"])


if __name__ == "__main__":
    try:
        unittest.main(verbosity=1)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
