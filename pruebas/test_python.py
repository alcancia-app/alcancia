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
import chat  # noqa: E402
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

    def test_xlsx_que_se_infla_al_descomprimir(self):
        """Una «bomba zip»: el .xlsx pesa poco, pero por dentro diría gigas. Se rechaza antes de descomprimir."""
        ruta = os.path.join(TMP, "bomba.xlsx")
        xlsx(ruta, [["Fecha", "Detalle", "Monto"], [46297, "x" * 5000, -1]])
        antes = recetas.MAXIMO_XLSX_PARTE
        recetas.MAXIMO_XLSX_PARTE = 1000
        try:
            with self.assertRaises(recetas.ArchivoNoValido):
                recetas.leer_tabla(ruta)
        finally:
            recetas.MAXIMO_XLSX_PARTE = antes

    def test_xml_con_entidades_no_se_lee(self):
        """«Billion laughs» o XXE en un .xlsx o un CAMT.053: ni siquiera se intenta."""
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ruta = os.path.join(TMP, "entidades.xlsx")
        with zipfile.ZipFile(ruta, "w") as z:
            z.writestr("xl/worksheets/sheet1.xml", '<?xml version="1.0"?><!DOCTYPE w [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
                                                   f'<worksheet {ns}><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>&b;</t></is></c></row>'
                                                   '</sheetData></worksheet>')
        with self.assertRaises(recetas.ArchivoNoValido):
            recetas.leer_tabla(ruta)
        camt = os.path.join(TMP, "camt.xml")
        with open(camt, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0"?><!DOCTYPE Document [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
                    '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><Stmt><Ntry>'
                    '<Amt Ccy="EUR">1.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><BookgDt><Dt>2026-10-02</Dt></BookgDt>'
                    '<AddtlNtryInf>&x;</AddtlNtryInf></Ntry></Stmt></BkToCstmrStmt></Document>')
        r = correr("importar.py", "vista", camt)
        self.assertFalse(r["ok"])
        self.assertIn("definiciones XML", r["error"])

    def test_archivo_enorme(self):
        ruta = os.path.join(TMP, "enorme.csv")
        with open(ruta, "wb") as f:
            f.truncate(recetas.MAXIMO_ARCHIVO + 1)
        with self.assertRaises(recetas.ArchivoNoValido):
            recetas.leer_tabla(ruta)
        os.remove(ruta)

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

    @unittest.skipIf(os.name == "nt", "permisos POSIX")
    def test_carpeta_de_datos_solo_para_la_persona(self):
        os.makedirs(datos.BASE, exist_ok=True)
        os.chmod(datos.BASE, 0o755)
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        self.assertEqual(os.stat(datos.BASE).st_mode & 0o777, 0o700)
        for raiz, _, archivos in os.walk(datos.BASE):
            for a in archivos:
                self.assertEqual(os.stat(os.path.join(raiz, a)).st_mode & 0o077, 0, a)

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
                self.assertEqual(set(e) - {"tipo", "categoria", "preguntar", "palabras", "uf"}, set(), pais)
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
                             ("cuenta 001234567890 y pago 450.000 el 15", "1234567890")]:
            limpio = compromiso_ia.limpiar_texto(texto)
            self.assertNotIn(fuera, limpio, texto)
            self.assertIn("450.000", limpio, "los montos con separador de miles se mantienen")
        self.assertEqual(compromiso_ia.limpiar_texto("son 500.000 o 500000 o 1.250.000, el 15"), "son 500.000 o 500000 o 1.250.000, el 15")
        self.assertEqual(compromisos.limpiar_buscar(["TRANSFERENCIA", "papá"], True), ["PAPA"], "la IA no deja palabras de cualquier movimiento")
        self.assertEqual(compromisos.limpiar_buscar(["TRANSFERENCIA"]), ["TRANSFERENCIA"], "pero si la persona la escribe, se respeta")
        self.assertIn("prestamo", compromiso_ia.prompt("x", "2026-10-26", [], "CLP"), "la IA sabe de préstamos entre personas")
        self.assertEqual(compromiso_ia.limpiar_texto("dividendo $1500000 o 1500000 clp"), "dividendo $1.500.000 o 1.500.000 clp",
                         "un monto grande con $ o moneda es plata y pasa con puntos")

    def entender(self, texto, hoy):
        """Como lo llama la app: el texto en un archivo de entrada, nunca como argumento."""
        ruta = os.path.join(TMP, "entrada-ia.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"texto": texto, "hoy": hoy}, f)
        return correr("compromiso_ia.py", "entender", ruta)

    def test_el_texto_no_va_como_argumento(self):
        with open(os.path.join(RAIZ, "app", "Sources", "Alcancia", "Ventana.swift"), encoding="utf-8") as f:
            swift = f.read()
        # Lo que escribe la persona (la conversación con Alcancía) va en un archivo de entrada; nunca como argumento.
        self.assertIn('conEntrada("chat.py", "enviar"', swift)
        self.assertNotIn('correrJSON("chat.py"', swift)
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


class CuentaleYPrestamos(unittest.TestCase):
    """Cuéntale a Alcancía con montos grandes y préstamos entre personas (casos de pruebas/casos.json, «prestamos»)."""

    def setUp(self):
        limpiar()

    def entender(self, texto):
        ruta = os.path.join(TMP, "entrada-ia.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"texto": texto, "hoy": "2026-10-26"}, f)
        return correr("compromiso_ia.py", "entender", ruta)

    def test_montos_grandes_pasan_y_los_rut_no(self):
        # El caso real (con nombres y montos cambiados): un monto de 7 dígitos sin puntos llegaba borrado a la IA.
        for texto in ("mi tia me presto 1800000 en 12 meses, le pago los 25", "son 1500000 o 15000000 o 123456789", "son 2000000 en 10 cuotas"):
            self.assertEqual(compromiso_ia.limpiar_texto(texto), texto, "los montos de 7 a 9 dígitos pasan")
        # RUT ficticios, armados por partes (ningún RUT entero queda escrito en el repo).
        cuerpo = "1111111" + "1"
        dv = compromiso_ia.digito_verificador(cuerpo)
        for texto in (f"mi rut es {cuerpo}-{dv} ok", f"mi rut es {cuerpo}{dv} ok", f"es {cuerpo}{dv} ok", f"es {cuerpo}k ok",
                      f"es {cuerpo[:2]}.{cuerpo[2:5]}.{cuerpo[5:]}-{dv} ok"):
            self.assertNotIn(cuerpo, compromiso_ia.limpiar_texto(texto).replace(".", ""), texto)
        for texto, fuera in (("mi cuentarut 12345678 y le pago 2000000", "12345678"), ("cuenta corriente 00123456 y 2000000", "00123456"),
                             ("tarjeta 4111 1111 1111 1111 y 2000000", "4111"), ("nro. 123456 y 2000000", "123456"),
                             ("cta 98765432 y 2000000", "98765432"), ("número 1234567890 y 2000000", "1234567890")):
            limpio = compromiso_ia.limpiar_texto(texto)
            self.assertNotIn(fuera, limpio, texto)
            self.assertIn("2000000", limpio, "el monto se mantiene")
        self.assertEqual(dv, "1", "módulo 11 del cuerpo ficticio")

    def test_casos_compartidos(self):
        pr = CASOS["prestamos"]
        for t, n, i, m, esperado in pr["calcular"]:
            self.assertEqual(compromisos.calcular_prestamo(t, n, i, m), esperado, (t, n, i, m))
        for t, n, i, m, cuota, esperado in pr["calcular_cuota"]:
            self.assertEqual(compromisos.calcular_prestamo(t, n, i, m, cuota), esperado, (t, n, i, m, cuota))
        # Una cuota fija solo si calza: 130.000 en 12 cuotas de 1.500.000 deja la última en 70.000; 120.000 no alcanza y 140.000
        # pagaría todo antes de la última: se calcula como siempre.
        porCuota = {(r[0], r[1], r[4]): r[5] for r in pr["calcular_cuota"]}
        self.assertEqual((porCuota[(1500000, 12, 130000)]["cuota"], porCuota[(1500000, 12, 130000)]["ultima"]), (130000, 70000))
        self.assertEqual(porCuota[(1500000, 12, 120000)]["cuota"], 125000)
        self.assertEqual(porCuota[(1500000, 12, 140000)]["cuota"], 125000)
        c, e = compromisos.validar({"tipo": "prestamo", "con": "Mamá", "prestamo": {"total": 1500000, "cuota": 130000}, "cuotas_total": 12, "dia": 26},
                                   None, "2026-10-30")
        self.assertEqual((e, c["monto"], c["prestamo"]["ultima"]), ([], 130000, 70000), "validar respeta la cuota fija que calza")
        self.assertEqual(compromisos.estado_mes(pr["compromisos"], pr["movimientos"], pr["estado"]["mes"], pr["estado"]["hoy"], "CLP"), pr["estado"]["esperado"])
        d = compromisos.lo_que_debes(pr["compromisos"], pr["movimientos"], pr["debes"]["hoy"], "CLP")
        self.assertEqual(d, pr["debes"]["esperado"])
        # En palabras: la última cuota ajusta el redondeo, lo que te deben va aparte y no se resta.
        items = {(i["nombre"], i["vence"]): i for i in pr["estado"]["esperado"]["items"]}
        self.assertEqual(items[("Préstamo de Amigo", "2026-10-10")]["monto"], 333334)
        self.assertEqual((d["te_deben_total"], d["total"]), (400000, 333334 + 1500000))
        tia = next(c for c in pr["estado"]["esperado"]["compromisos"] if c["con"] == "Tía Ana")
        self.assertEqual((tia["cuotas"]["quedan"], tia["por_pagar"], tia["termina"]), (10, 1500000, "2027-07-25"))

    def test_validar_prestamo(self):
        hoy = "2026-10-26"
        c, e = compromisos.validar({"tipo": "prestamo", "con": "Tía 12345", "prestamo": {"total": 1800000}, "cuotas_total": 12, "dia": 25}, None, hoy)
        self.assertEqual(e, [])
        self.assertEqual((c["nombre"], c["con"], c["monto"], c["cuotas_pagadas"], c["fecha_fin"]), ("Préstamo de Tía", "Tía", 150000, 0, "2027-10-25"),
                         "sin números en «con»; cuota y término calculados (la primera, el próximo 25)")
        for malo, texto in (({"con": ""}, "con quién"), ({"prestamo": {}}, "total"), ({"cuotas_total": None}, "cuotas"),
                            ({"prestamo": {"total": 1, "otro": 2}}, "préstamo")):
            base = {"tipo": "prestamo", "con": "Tía", "prestamo": {"total": 1800000}, "cuotas_total": 12, "dia": 25}
            c, e = compromisos.validar({**base, **malo}, None, hoy)
            self.assertIsNone(c, malo)
            self.assertIn(texto, " ".join(e).lower(), malo)
        self.assertEqual(compromisos.completar_prestamo({"tipo": "prestamo"}, {"inicio_mes": {"modo": "sueldo", "dia": 28}})["dia"], 28,
                         "la primera cuota, el día del sueldo")
        self.assertEqual(compromisos.completar_prestamo({"tipo": "prestamo"}, {})["dia"], 25)

    def test_cuentale_prestamos_y_nunca_sin_salida(self):
        r = self.entender("mi tía me prestó 1,8 millones en 12 meses")
        self.assertTrue(r["ok"], r)
        c = r["compromiso"]
        self.assertEqual((c["tipo"], c["con"], c["monto"], c["dia"], c["signo"]), ("prestamo", "Tía", 150000, 25, "gasto"))
        r = self.entender("le presté 850 lucas a Matías en 5 meses")
        self.assertEqual((r["compromiso"]["signo"], r["compromiso"]["nombre"], r["compromiso"]["monto"]), ("ingreso", "Préstamo a Matías", 170000))
        # La IA falla o algo no cumple: igual se abre la tarjeta con lo que sí se entendió.
        r = self.entender("SINMONTO el gimnasio los 3")
        self.assertFalse(r["ok"])
        self.assertEqual(r["parcial"], {"nombre": "Gimnasio", "tipo": "suscripcion", "frecuencia": "mensual", "dia": 3, "buscar": ["GIMNASIO"]})
        self.assertIn("Corrígelo aquí", r["error"])
        r = self.entender("NADA que ver")
        self.assertEqual((r["ok"], r["parcial"]), (False, {}))
        self.assertIn("Complétalo aquí", r["error"])
        r = self.entender("ROMPER todo")
        self.assertEqual(r["parcial"], {"nombre": "Algo", "monto": 1000, "dia": 5}, "lo que vino bien se aprovecha; el campo raro no")

    def test_consejos_incluyen_prestamos(self):
        pr = CASOS["prestamos"]
        datos.escribir_json(os.path.join(datos.BASE, "cuentas.json"), [])
        linea = consejos.linea_tres_cifras("2026-10-12", pr["movimientos"], {"moneda": "CLP", "mensual": {}}, pr["compromisos"])
        self.assertIn("1833334", linea, "los préstamos están en lo que debe")
        self.assertIn("Le deben 400000", linea)
        self.assertNotIn("Tía", linea, "solo totales")


class Aproximados(unittest.TestCase):
    """Montos que varían («aprox.») y compromisos en UF: los mismos casos que ui/app.js (pruebas/casos.json, «aproximados»)."""

    def setUp(self):
        limpiar()

    def sec(self, caso=None):
        sec = CASOS["aproximados"]
        comps = [c for c in sec["compromisos"] if not caso or "compromisos_ids" not in caso or c["id"] in caso["compromisos_ids"]]
        return sec, comps, sec["movimientos"]

    def test_casos(self):
        sec = CASOS["aproximados"]
        for k in sec["estado"]:
            _, comps, movs = self.sec(k)
            self.assertEqual(compromisos.estado_mes(comps, movs, k["mes"], k["hoy"], k["moneda"], None, k["uf"]), k["esperado"], k["nombre"])
        _, comps, movs = self.sec()
        for k in sec["gasto_maximo"]:
            r = compromisos.gasto_maximo(movs, comps, k["mes"], k["hoy"], sec["categorias"], k["meses_completos"], k["moneda"], None, k["uf"])
            self.assertEqual(r, k["esperado"], k["nombre"])
        for k in sec["debes"]:
            self.assertEqual(compromisos.lo_que_debes(comps, movs, k["hoy"], k["moneda"], None, k["uf"]), k["esperado"], k["nombre"])

    def test_reglas_a_mano(self):
        """Lo mismo que los casos, dicho en palabras (los casos los genera Python: esto revisa que tengan sentido)."""
        sec = CASOS["aproximados"]
        sin, con = ({i["nombre"]: i for i in k["esperado"]["items"] if not i["anterior"]} for k in sec["estado"][:2])
        self.assertEqual(sin["Luz"]["rango"], {"min": 27200, "max": 36800}, "±15 % de 32.000, redondeado hacia afuera")
        self.assertEqual(sin["Gastos comunes"]["rango"], {"min": 80000, "max": 110000}, "el rango escrito se respeta tal cual")
        div = sin["Dividendo"]
        self.assertEqual((div["moneda"], div["original"]["monto"], div["original"]["fuente"], div["original"]["valor_uf"]), ("CLP", 12.75, "pago", 39058.82),
                         "la UF sale del último pago: 498.000 / 12,75")
        self.assertEqual((div["monto"], div["rango"]), (498000, {"min": 490000, "max": 506000}), "±1,5 % por un mes desde el pago")
        self.assertEqual(sin["Seguro"]["original"]["fuente"], "otro", "sin pagos ni Ajustes: la UF de otro compromiso ya pagado")
        self.assertEqual(con["Seguro"]["original"]["fuente"], "ajustes", "el valor de Ajustes es más reciente")
        self.assertEqual(sin["Bodega"]["estado"], "atrasado", "en UF y sin palabras: sin el valor de Ajustes no se reconoce por el monto")
        self.assertEqual(con["Bodega"]["estado"], "pagado", "con el valor de Ajustes, sí: 12 × 39.500 = 474.000")
        e = sec["estado"][0]["esperado"]
        self.assertGreater(e["pendiente_max"], e["pendiente"])
        self.assertTrue(e["aprox"])
        sin_valor = sec["estado"][2]["esperado"]
        self.assertEqual((sin_valor["sin_valor"], sin_valor["total"], sin_valor["items"][0]["moneda"]), (1, 0, "UF"),
                         "sin forma de estimarlo queda en UF y no se suma")
        g = sec["gasto_maximo"][0]["esperado"]
        self.assertEqual((g["ingreso"], g["fuente"], g["compromisos"]), (900000, "compromisos", e["total_max"] + e["arrastre_max"]),
                         "ingresos por su mínimo y compromisos por su máximo")
        # Septiembre: la luz (36.000, 12,5 % sobre 32.000, con la palabra LUZ) se reconoce por estar en su rango; los gastos comunes no
        # tienen palabras, así que solo calzaría el monto exacto (un rango sin palabras confundiría cualquier compra parecida).
        _, comps, movs = self.sec()
        sept = {i["nombre"]: i for i in compromisos.estado_mes(comps, movs, "2026-09", "2026-10-05", "CLP")["items"]}
        self.assertEqual((sept["Luz"]["estado"], sept["Luz"]["pago"]["monto"]), ("pagado", 36000))
        self.assertEqual(sept["Gastos comunes"]["estado"], "atrasado")

    def test_validar(self):
        hoy, ids = "2026-10-26", {"casa", "cuentas"}
        base = {"nombre": "Luz", "monto": 32000, "dia": 8, "categoria": "cuentas"}
        c, e = compromisos.validar(base, ids, hoy)
        self.assertNotIn("aproximado", c, "los que ya existían siguen igual")
        self.assertEqual(compromisos.validar({**base, "aproximado": True}, ids, hoy)[0]["aproximado"], {"variacion": 3})
        self.assertEqual(compromisos.validar({**base, "aproximado": {"variacion": 15}}, ids, hoy)[0]["aproximado"], {"variacion": 15})
        self.assertEqual(compromisos.validar({**base, "aproximado": {"min": 28000, "max": 36000}}, ids, hoy)[0]["aproximado"], {"min": 28000, "max": 36000})
        for malo in ({"variacion": 80}, {"min": 36000, "max": 28000}, {"min": 33000, "max": 36000}, {"variacion": 3, "min": 1, "max": 2},
                     {"otro": 1}, "mucho"):
            self.assertIsNone(compromisos.validar({**base, "aproximado": malo}, ids, hoy)[0], malo)
        uf, e = compromisos.validar({**base, "nombre": "Dividendo", "moneda": "UF", "monto": 12.3456, "saldo": 1850.5}, ids, hoy)
        self.assertEqual((e, uf["moneda"], uf["monto"], uf["saldo"]), ([], "UF", 12.3456, 1850.5), "en UF con 4 decimales")
        self.assertIsNone(compromisos.validar({**base, "moneda": "uf"}, ids, hoy)[0], "solo «UF» o un código de 3 letras")
        self.assertIsNone(compromisos.validar({**base, "aproximado": {"variacion": 3}, "otro": 1}, ids, hoy, estricto=True)[0])
        self.assertEqual(compromisos.uf_config({"uf": {"valor": 39512.34, "fecha": "2026-10-26"}}), {"valor": 39512.34, "fecha": "2026-10-26"})
        self.assertIsNone(compromisos.uf_config({"uf": {"valor": "mucho"}}))

    def test_sugerir_aproximado_y_uf(self):
        hoy, cats, movs = "2026-10-26", datos.CATEGORIAS_BASE, []
        for i, (mes, monto) in enumerate([("2026-06", 30500), ("2026-07", 33900), ("2026-08", 31800), ("2026-09", 32700)]):
            movs.append({"id": f"l{i}", "fecha": f"{mes}-08", "descripcion": "LUZ DEL SUR", "monto": -monto, "moneda": "CLP", "categoria": "cuentas"})
            movs.append({"id": f"a{i}", "fecha": f"{mes}-01", "descripcion": "ARRIENDO DEPTO", "monto": -400000, "moneda": "CLP", "categoria": "casa"})
        movs.append({"id": "d1", "fecha": "2026-10-15", "descripcion": "PAGO DIVIDENDO", "monto": -980000, "moneda": "CLP", "categoria": ""})
        movs.append({"id": "u1", "fecha": "2026-10-12", "descripcion": "SEGURO COMPLEMENTARIO UF", "monto": -47000, "moneda": "CLP", "categoria": ""})
        r = {s["clave"]: s for s in compromisos.sugerir(movs, [], hoy, cats, "CLP")}
        self.assertEqual(r["LUZ DEL SUR"]["aproximado"], {"variacion": 7}, "varía mes a mes: aproximado con lo observado (2.100 / 31.800)")
        self.assertNotIn("aproximado", r["ARRIENDO DEPTO"], "siempre lo mismo: exacto")
        self.assertTrue(r["PAGO DIVIDENDO"]["preguntar_uf"], "un dividendo: se pregunta si es en UF")
        self.assertTrue(r["SEGURO COMPLEMENTARIO UF"]["preguntar_uf"], "la descripción dice UF")
        self.assertNotIn("preguntar_uf", r["LUZ DEL SUR"])

    def entender(self, texto):
        ruta = os.path.join(TMP, "entrada-ia.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"texto": texto, "hoy": "2026-10-26"}, f)
        return correr("compromiso_ia.py", "entender", ruta)

    def test_cuentale_aprox_y_uf(self):
        r = self.entender("el dividendo son 12,75 UF los 15, más o menos")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["compromiso"]["moneda"], r["compromiso"]["monto"], r["compromiso"]["aproximado"]), ("UF", 12.75, {"variacion": 2}))
        r = self.entender("los gastos comunes son entre 80.000 y 110.000, el 10")
        self.assertEqual(r["compromiso"]["aproximado"], {"min": 80000, "max": 110000})
        self.assertEqual(self.entender("la luz es aprox 30.000 el 8")["compromiso"]["aproximado"], {"variacion": 3})
        malo = self.entender("MALAPROX la luz")
        self.assertFalse(malo["ok"])
        self.assertIn("rango", malo["error"])
        self.assertIn("12,75 UF", compromiso_ia.limpiar_texto("son 12,75 UF el 15"))

    def test_consejos_y_mcp_solo_totales(self):
        sec, comps, movs = self.sec()
        cats = [{**c, "nombre": c["id"]} for c in sec["categorias"]]
        texto = consejos.prompt("2026-10-05", movs, {"moneda": "CLP", "mensual": {}}, cats, comps)
        self.assertIn("cerca de", texto)
        self.assertNotIn("Dividendo", texto, "a la IA solo le llegan totales")
        datos.escribir_json(compromisos.RUTA, {"formato": 1, "compromisos": comps, "descartados": []})
        for m in movs:
            datos.agregar([{**m, "cuenta": "x", "origen": "prueba", "nota": "", "id": m["id"]}])
        p = subprocess.run([sys.executable, os.path.join(RAIZ, "bin", "mcp_servidor.py")], capture_output=True, text=True, timeout=30,
                           input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "compromisos", "arguments": {"mes": "2026-10"}}}) + "\n")
        r = json.loads(p.stdout.splitlines()[0])["result"]["structuredContent"]
        div = next(x for x in r["compromisos"] if x["nombre"] == "Dividendo")
        self.assertEqual(div["en_uf"], 12.75)
        self.assertIn("aproximado", div)
        self.assertGreaterEqual(r["pendiente_hasta"], r["pendiente"])
        self.assertNotIn("c-dividuf001", json.dumps(r), "sin ids internos")


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

    def test_claude_responde_sin_herramientas_ni_mcp(self):
        """Lo que va a la IA trae texto de afuera (descripciones de la cartola): Claude Code corre sin herramientas ni MCP."""
        import ia
        datos.escribir_json(os.path.join(datos.INTERNO, "config.json"), {"ia": "claude"})
        r = ia.ejecutar("Clasifica cada movimiento\nMovimientos (número|descripción|monto):\n1|X|-1", timeout=30)
        i = r.args.index("--disallowedTools")
        self.assertEqual(r.args[i + 1], "*")
        self.assertIn("--strict-mcp-config", r.args)

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
                r = ia.ejecutar(pedido, timeout=30)
                self.assertNotIn("SECRETO", " ".join(r.args), proveedor)
                continue
            r = ia.ejecutar(pedido, timeout=30)
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
        """Un pago a ti mismo sale en las dos búsquedas (pagador y cobrador): va una sola vez. Una carga de saldo es plata que entra."""
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
        datos.escribir_mes("2026-08", [{"id": "a4", "fecha": "2026-08-10", "descripcion": "Carga de saldo: Ejemplo", "monto": 50000, "moneda": "CLP",
                                        "categoria": "transferencia", "cuenta": "mercadopago", "origen": "conector:mercadopago", "nota": ""}])
        with ServidorFalso(rutas) as srv:
            self.sinc(srv, "probar", "mercadopago", {"token": "APP_USR-123"})
            r = self.sinc(srv, "traer", "mercadopago", {"token": "APP_USR-123"})
            self.assertEqual((r["ok"], r["nuevos"], r["reparados"]), (True, 2, 2), r)  # el espejo de septiembre y la carga de agosto
            octubre = [(m["monto"], m["categoria"]) for m in datos.leer_mes("2026-10")]
            cargas = [c for m, c in octubre if m == 300000]
            self.assertEqual(len(cargas), 1, "una carga de saldo va una sola vez")
            self.assertNotEqual(cargas[0], "transferencia", "y como plata que entra, no entre tus cuentas")
            self.assertNotIn(-300000, [m for m, _ in octubre], "no queda como gasto")
            self.assertIn(-5990, [m for m, _ in octubre])
            self.assertEqual(sorted((m["monto"], m["categoria"]) for m in datos.leer_mes("2026-09")), [(-2500, "comida"), (200000, "")],
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
            self.assertFalse(any(k.startswith("ALCANCIA_") for k in ia._entorno()))
        finally:
            del os.environ["ALCANCIA_RED_PRUEBA"]

    def test_esperar_y_error_quedan_en_estado(self):
        from servidor_falso import ServidorFalso
        with ServidorFalso({("GET", "api.mercadopago.com/users/me"): lambda q, b, h: (429, {})}) as srv:
            r = self.sinc(srv, "traer", "mercadopago", {"token": "x"})
        self.assertFalse(r["ok"])
        e = datos.leer_json(os.path.join(datos.INTERNO, "conexiones.json"), None)["mercadopago"]
        self.assertIn("esperar", e["error"])
        # Pieza «red»: el error trae su código y su plantilla (la interfaz lo traduce) y la plantilla está en inglés.
        self.assertEqual((r["codigo"], r["valores"]["servicio"]), ("esperar", "Mercado Pago"))
        self.assertEqual(e["plantilla"], r["plantilla"])
        en = datos.leer_json(os.path.join(RAIZ, "ui", "idiomas", "en.json"), {})["textos"]
        import red
        self.assertTrue(all(f in en for f in red.ERRORES.values()), "cada error de la red tiene su traducción")
        self.assertTrue(all("{servicio}" in en[f] for f in red.ERRORES.values() if "{servicio}" in f))

    def test_red_agente_y_tope(self):
        """User-Agent con el repo de app.json, y una respuesta más grande que el tope no se lee entera."""
        from red import ErrorRed, Red
        from servidor_falso import ServidorFalso
        rutas = {("GET", "api.ejemplo.com/chico"): lambda q, b, h: (200, {"ok": True}),
                 ("GET", "api.ejemplo.com/grande"): lambda q, b, h: (200, "x" * 5000)}
        with ServidorFalso(rutas) as srv:
            os.environ["ALCANCIA_RED_PRUEBA"] = srv.url
            try:
                red = Red(["api.ejemplo.com"], "Ejemplo", maximo=1000)
                self.assertEqual(red.get("https://api.ejemplo.com/chico"), {"ok": True})
                with self.assertRaises(ErrorRed) as e:
                    red.get("https://api.ejemplo.com/grande", crudo=True)
                self.assertEqual(e.exception.codigo, "grande")
            finally:
                del os.environ["ALCANCIA_RED_PRUEBA"]
        self.assertIn("alcancia-app/alcancia", srv.pedidos[0][4]["user-agent"])


    def test_mercadopago_como_se_pago_devolucion_y_saldo(self):
        """Crédito en cuotas, débito, saldo y una devolución; lo ya guardado se completa por id (reparación) sin duplicar; el saldo
        disponible queda en cuentas.json. Si el saldo no existe para la cuenta (404), no pasa nada."""
        from servidor_falso import ServidorFalso
        hoy = date.today()
        f = lambda dias: (hoy - timedelta(days=dias)).isoformat() + "T12:00:00.000-03:00"
        pagos = [
            {"id": 31, "status": "approved", "transaction_amount": 349900, "currency_id": "CLP", "date_approved": f(40), "description": "Lavadora Ejemplo",
             "operation_type": "regular_payment", "payment_type_id": "credit_card", "payment_method_id": "master", "installments": 6,
             "transaction_details": {"installment_amount": 61000}, "collector_id": 555, "payer": {"id": 999}},
            {"id": 32, "status": "approved", "transaction_amount": 5990, "currency_id": "CLP", "date_approved": f(3), "description": "Panadería Ejemplo",
             "operation_type": "regular_payment", "payment_type_id": "account_money", "installments": 1, "collector_id": 555, "payer": {"id": 999}},
            {"id": 33, "status": "refunded", "transaction_amount": 24990, "transaction_amount_refunded": 24990, "currency_id": "CLP", "date_approved": f(5),
             "description": "Audífonos Ejemplo", "operation_type": "regular_payment", "payment_type_id": "debit_card", "installments": 1,
             "refunds": [{"date_created": f(2)}], "collector_id": 555, "payer": {"id": 999}},
            {"id": 34, "status": "approved", "transaction_amount": 15990, "currency_id": "CLP", "date_approved": f(300), "description": "Librería Ejemplo",
             "operation_type": "regular_payment", "payment_type_id": "credit_card", "installments": 1, "collector_id": 555, "payer": {"id": 999}},
        ]
        saldo = {"estado": 200}
        def buscar(q, b, h):
            return 200, {"paging": {"total": len(pagos) if "payer.id" in q else 0}, "results": pagos if "payer.id" in q else []}
        rutas = {("GET", "api.mercadopago.com/users/me"): lambda q, b, h: (200, {"id": 999, "site_id": "MLC"}),
                 ("GET", "api.mercadopago.com/v1/payments/search"): buscar,
                 ("GET", "api.mercadopago.com/users/999/mercadopago_account/balance"):
                     lambda q, b, h: (saldo["estado"], {"available_balance": 84300, "unavailable_balance": 1000, "currency_id": "CLP"} if saldo["estado"] == 200 else {"message": "not found"})}
        # Lo que dejó la versión anterior: la compra de hace 300 días guardada sin saber cómo se pagó (mismo id que la de ahora).
        import sincronizar
        viejo = {"id": sincronizar.id_movimiento("mercadopago", "mercadopago", "34|pagado"), "fecha": f(300)[:10], "descripcion": "Pago: Librería Ejemplo",
                 "monto": -15990, "moneda": "CLP", "categoria": "educacion", "cuenta": "mercadopago", "origen": "conector:mercadopago", "nota": "mía"}
        datos.agregar([viejo])
        datos.escribir_json(os.path.join(datos.INTERNO, "conexiones.json"), {"mercadopago": {"conectado": True, "hasta": hoy.isoformat(), "reparado": 2}})
        with ServidorFalso(rutas) as srv:
            p = self.sinc(srv, "probar", "mercadopago", {"token": "APP_USR-123"})
            self.assertTrue(p["ok"])
            cuenta = next(c for c in datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), []) if c["id"] == "mercadopago")
            self.assertEqual(cuenta["saldo"], {"monto": 84300, "fecha": hoy.isoformat(), "origen": "conector"}, "el saldo disponible que muestra la app")
            r = self.sinc(srv, "traer", "mercadopago", {"token": "APP_USR-123"})
            self.assertTrue(r["ok"], r)
            inicio = min(x[2]["begin_date"][:10] for x in srv.pedidos if x[1].endswith("payments/search"))
            self.assertLessEqual(inicio, (hoy - timedelta(days=360)).isoformat(), "con la reparación pendiente se pide el año completo")
            movs = {m["descripcion"]: m for m in self.movs("mercadopago")}
            self.assertEqual((movs["Pago: Lavadora Ejemplo"]["medio"], movs["Pago: Lavadora Ejemplo"]["cuotas"], float(movs["Pago: Lavadora Ejemplo"]["cuota"])), ("credito", "6", 61000.0))
            self.assertEqual(movs["Pago: Panadería Ejemplo"]["medio"], "saldo")
            self.assertEqual((movs["Pago: Audífonos Ejemplo"]["monto"], movs["Pago: Audífonos Ejemplo"]["medio"]), (-24990, "debito"))
            dev = movs["Devolución: Pago: Audífonos Ejemplo"]
            self.assertEqual((dev["monto"], dev["fecha"]), (24990, f(2)[:10]), "lo devuelto queda aparte, positivo y en su fecha")
            lib = [m for m in self.movs("mercadopago") if m["descripcion"] == "Pago: Librería Ejemplo"]
            self.assertEqual(len(lib), 1, "la reparación no duplica")
            self.assertEqual((lib[0]["medio"], lib[0]["categoria"], lib[0]["nota"]), ("credito", "educacion", "mía"), "completa cómo se pagó sin tocar lo de la persona")
            self.assertGreaterEqual(r["reparados"], 1)
            self.assertEqual(datos.leer_json(os.path.join(datos.INTERNO, "conexiones.json"), {})["mercadopago"]["reparado"], sincronizar.REPARACIONES)
            # Sin reparación pendiente, la próxima vez se pide desde la última menos 10 días.
            antes = len(srv.pedidos)
            saldo["estado"] = 404
            r2 = self.sinc(srv, "traer", "mercadopago", {"token": "APP_USR-123"})
            self.assertEqual((r2["ok"], r2["nuevos"]), (True, 0), "no duplica")
            inicio2 = min(x[2]["begin_date"][:10] for x in srv.pedidos[antes:] if x[1].endswith("payments/search"))
            self.assertGreater(inicio2, (hoy - timedelta(days=30)).isoformat())
        cuenta = next(c for c in datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), []) if c["id"] == "mercadopago")
        self.assertEqual(cuenta["saldo"]["monto"], 84300, "si el saldo falla (404), queda el último conocido y la sincronización sigue bien")

    def test_saldo_de_otros_conectores(self):
        from servidor_falso import ServidorFalso
        rutas = {("GET", "api.up.com.au/api/v1/accounts"): lambda q, b, h: (200, {"data": [{"id": "acc", "attributes": {"displayName": "Gastos",
                                                                                           "balance": {"currencyCode": "AUD", "value": "1234.56"}}}]})}
        with ServidorFalso(rutas) as srv:
            self.assertTrue(self.sinc(srv, "probar", "up", {"token": "up:yeah:x"})["ok"])
        c = next(c for c in datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), []) if c["id"] == "up-acc")
        self.assertEqual((c["saldo"]["monto"], c["saldo"]["origen"]), (1234.56, "conector"))


class TresCifras(unittest.TestCase):
    """Lo que tienes, lo que gastaste y lo que debes: los mismos casos que ui/app.js (pruebas/casos.json)."""

    def test_casos(self):
        tc = CASOS["tres_cifras"]
        for k in tc["casos"]:
            g = resumen.resumen(tc["movimientos"], k["mes"], k["hoy"], tc["presupuesto"], tc["categorias"])
            for campo, v in k["esperado"]["resumen"].items():
                self.assertEqual(g[campo], v, f"{k['nombre']}: {campo}")
            self.assertEqual(resumen.lo_que_tienes(tc["cuentas"], tc["movimientos"], "CLP"), k["esperado"]["tienes"], k["nombre"])
            self.assertEqual(compromisos.lo_que_debes(tc["compromisos"], tc["movimientos"], k["hoy"], "CLP"), k["esperado"]["debes"], k["nombre"])

    def test_cargos_en_cuotas(self):
        m = {"fecha": "2026-01-31", "monto": -300000, "medio": "credito", "cuotas": "3", "cuota": ""}
        self.assertEqual(resumen.cargos(m), [("2026-01-31", -100000, 1, 3), ("2026-02-28", -100000, 2, 3), ("2026-03-31", -100000, 3, 3)])
        self.assertEqual(resumen.cargos({**m, "medio": "debito"}), [("2026-01-31", -300000, 0, 0)], "solo el crédito va en cuotas")
        self.assertTrue(compromisos.es_pago_tarjeta({"descripcion": "Pago T.C. Visa", "monto": -1}))
        self.assertFalse(compromisos.es_pago_tarjeta({"descripcion": "PAGO TARJETA", "monto": 1}))

    def setUp(self):
        limpiar()

    def test_csv_compatible(self):
        """Las columnas nuevas (medio, cuotas, cuota) van al final y solo si algún movimiento del mes las usa."""
        base = {"id": "a1", "fecha": "2026-10-01", "descripcion": "X", "monto": -1000, "moneda": "CLP", "categoria": "", "cuenta": "b", "origen": "o", "nota": ""}
        datos.escribir_mes("2026-10", [base])
        with open(datos.ruta_mes("2026-10"), encoding="utf-8") as f:
            self.assertEqual(f.readline().strip(), ",".join(datos.CAMPOS), "sin medio no cambia el archivo")
        datos.escribir_mes("2026-10", [base, {**base, "id": "a2", "medio": "credito", "cuotas": 3, "cuota": 333.5}])
        with open(datos.ruta_mes("2026-10"), encoding="utf-8") as f:
            self.assertEqual(f.readline().strip(), ",".join(datos.CAMPOS + datos.CAMPOS_EXTRA))
        leidos = {m["id"]: m for m in datos.leer_mes("2026-10")}
        self.assertEqual((leidos["a1"]["medio"], leidos["a2"]["cuotas"], leidos["a2"]["cuota"]), ("", "3", "333.50"))
        # El ejemplo del README sigue funcionando con las columnas nuevas.
        p = subprocess.run([sys.executable, os.path.join(RAIZ, "ejemplos", "gastos_por_categoria.py"), "2026-10"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("TOTAL", p.stdout)

    def test_saldo_de_la_cartola(self):
        receta = {**RECETA, "columnas": {**RECETA["columnas"], "saldo": "Saldo"}}
        self.assertEqual(recetas.validar(receta), [])
        info = {}
        recetas.aplicar(CARTOLA, receta, "banco-ejemplo", info)
        self.assertEqual(info["saldo"], {"monto": 1953419.5, "fecha": "2026-10-10"})
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", "cl-banco-ejemplo.json"), receta)
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        c = datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), [])[0]
        self.assertEqual(c["saldo"], {"monto": 1953419.5, "fecha": "2026-10-10", "origen": "cartola"})
        t = resumen.lo_que_tienes([c], datos.leer_todos(), "CLP")
        self.assertEqual(t["total"], 1953419.5, "el saldo de la cartola ya incluye sus movimientos")

    def guardar(self, accion, entrada):
        ruta = os.path.join(TMP, "entrada.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(entrada, f)
        return correr("guardar.py", accion, ruta)

    def test_categoria_nueva_y_saldo(self):
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", "cl-banco-ejemplo.json"), RECETA)
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        m = next(x for x in datos.leer_mes("2026-10") if x["descripcion"] == "NETFLIX.COM")
        r = self.guardar("categoriaNueva", {"categoria": {"id": "cine", "nombre": "Cine <b>", "emoji": "🎬", "tipo": "gasto"}, "mes": "2026-10", "id": m["id"]})
        self.assertTrue(r["ok"], r)
        cats = datos.leer_json(os.path.join(datos.BASE, "categorias.json"), [])
        self.assertEqual(cats[-1], {"id": "cine", "nombre": "Cine b", "emoji": "🎬", "tipo": "gasto"}, "sin HTML")
        self.assertEqual(len(cats), len(datos.CATEGORIAS_BASE) + 1, "parte de las de siempre")
        self.assertEqual(next(x for x in datos.leer_mes("2026-10") if x["id"] == m["id"])["categoria"], "cine")
        self.assertFalse(self.guardar("categoriaNueva", {"categoria": {"id": "cine", "nombre": "Otra", "emoji": "🎬"}})["ok"], "no repite ids")
        self.assertFalse(self.guardar("categoriaNueva", {"categoria": {"id": "Mal Id", "nombre": "x", "emoji": "🎬"}})["ok"])
        self.assertFalse(self.guardar("categoriaNueva", {"categoria": {"id": "letras", "nombre": "x", "emoji": "abc"}})["ok"], "el emoji no es texto")
        # Saldo: la primera vez no hay con qué comparar; después dice la diferencia con lo que calculaba.
        r = self.guardar("saldo", {"cuenta": "banco-ejemplo", "monto": 900000, "fecha": "2026-10-05"})
        self.assertEqual((r["ok"], r["diferencia"]), (True, None))
        r = self.guardar("saldo", {"cuenta": "banco-ejemplo", "monto": 840000, "fecha": "2026-10-10"})
        self.assertEqual(r["calculado"], 900000 - 9990 - 35000 - 50000 - 8750.5)
        self.assertEqual(r["diferencia"], round(840000 - r["calculado"], 2))
        self.assertFalse(self.guardar("saldo", {"cuenta": "../x", "monto": 1})["ok"])
        self.assertFalse(self.guardar("saldo", {"cuenta": "banco-ejemplo", "monto": "mucho"})["ok"])

    def test_mcp_y_consejos_usan_las_tres_cifras(self):
        datos.escribir_json(os.path.join(datos.INTERNO, "recetas", "cl-banco-ejemplo.json"), RECETA)
        correr("importar.py", "guardar", CARTOLA, "cl-banco-ejemplo", "0")
        datos.anotar_saldo("banco-ejemplo", 500000, "2026-10-31", "persona")
        texto = consejos.prompt("2026-10-12", datos.leer_todos(), datos.presupuesto(), datos.categorias())
        self.assertIn("tiene 500000 en sus cuentas", texto)
        self.assertIn("debe 0 en total", texto)
        entrada = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "resumen_del_mes", "arguments": {}}}) + "\n"
        p = subprocess.run([sys.executable, os.path.join(RAIZ, "bin", "mcp_servidor.py")], input=entrada, capture_output=True, text=True, timeout=30)
        t = json.loads(p.stdout.splitlines()[0])["result"]["structuredContent"]["tres_cifras"]
        self.assertEqual((t["lo_que_tienes"], t["cuentas_con_saldo"], t["lo_que_debes"]), (500000, 1, 0))
        self.assertNotIn("banco-ejemplo", json.dumps(t), "solo totales")


class Sueldo(unittest.TestCase):
    """Detectar el sueldo, aplicarlo solo si la persona nunca eligió, días hábiles y el próximo sueldo (casos «sueldo»)."""

    def setUp(self):
        limpiar()

    def test_casos_compartidos(self):
        sec = CASOS["sueldo"]
        self.assertEqual(sec["feriados_cl"], compromisos.feriados("CL"))
        for c in sec["detectar"]:
            self.assertEqual(compromisos.detectar_sueldo(c["movimientos"], c["hoy"], sec["categorias"], "CLP"), c["esperado"], c["nombre"])
        for c in sec["proximo"]:
            fer = sec["feriados_cl"] if c["pais"] == "CL" else []
            self.assertEqual(compromisos.proximo_sueldo(c["per"], c["hoy"], fer), c["esperado"], c["nombre"])
        for c in sec["rango"]:
            self.assertEqual(list(resumen.rango(c["mes"], c["per"])), c["esperado"], c["nombre"])
        for c in sec["periodo_de"]:
            self.assertEqual(resumen.periodo_de(c["fecha"], c["per"]), c["esperado"])
        for c in sec["regla"]:
            self.assertEqual(compromisos.regla_habil(c["dia"], c["llegadas"], sec["feriados_cl"]), c["esperado"])

    def test_feriados_de_chile(self):
        fer = compromisos.feriados("CL")
        for anio in ("2025", "2026", "2027", "2028"):
            self.assertIn(f"{anio}-09-18", fer)
            self.assertIn(f"{anio}-12-25", fer)
        self.assertIn("2026-04-03", fer)  # Viernes Santo
        self.assertIn("2028-06-26", fer)  # San Pedro y San Pablo (jueves 29) se corre al lunes de esa semana
        self.assertIn("2028-10-27", fer)  # Iglesias Evangélicas (martes 31) se corre al viernes anterior
        self.assertEqual(compromisos.feriados("US"), [])
        self.assertTrue(compromisos.es_habil("2026-09-17", fer))
        self.assertFalse(compromisos.es_habil("2026-09-18", fer))
        self.assertEqual(compromisos.correr_habil("2026-09-19", "anterior", fer), "2026-09-17")
        self.assertEqual(compromisos.correr_habil("2026-09-19", "siguiente", fer), "2026-09-21")

    def guardar(self, nombre):
        movs = next(c for c in CASOS["sueldo"]["detectar"] if c["nombre"].startswith(nombre))["movimientos"]
        datos.agregar([dict(m) for m in movs])
        return movs

    def test_se_aplica_solo_y_se_guarda(self):
        self.guardar("llega como «Carga de saldo»")
        hoy = "2026-10-26"
        per, mes = compromisos.periodo_actual(hoy)  # antes de guardarlo, MCP y consejos ya usan el sueldo detectado
        self.assertEqual((per["dia"], mes, resumen.rango(mes, per)[0]), (19, "2026-11", "2026-10-22"))
        d = compromisos.aplicar_sueldo(hoy)
        self.assertEqual(d["dia"], 19)
        self.assertEqual(datos.config()["inicio_mes"], {"modo": "sueldo", "dia": 19, "auto": True})
        lista = compromisos.validos(None, hoy, "CLP")
        self.assertEqual(len(lista), 1)
        c = lista[0]
        self.assertEqual((c["tipo"], c["categoria"], c["origen"], c["buscar"], c["aproximado"]),
                         ("ingreso", "sueldo", "detectado", ["CARGA DE SALDO"], {"variacion": 1}))
        # «Carga de saldo» también es cuando carga ella: sin regla, solo las dos llegadas quedan como Sueldo.
        self.assertEqual(datos.reglas(), [])
        cats = {m["descripcion"] + m["fecha"]: m["categoria"] for m in datos.leer_todos()}
        self.assertEqual(cats["Carga de saldo: Empresa Ejemplo SpA2026-10-22"], "sueldo")
        self.assertEqual(cats["Carga de saldo: desde mi banco2026-10-05"], "")
        per, mes = compromisos.periodo_actual(hoy)
        self.assertEqual(per["llegadas"], ["2026-09-15", "2026-10-22"])
        r = resumen.resumen(datos.leer_todos(), mes, hoy, {"mensual": {}}, datos.categorias(), per)
        self.assertEqual(r["gastado"], 45000)  # lo que llevas gastado: desde que llegó el sueldo (22 oct)
        self.assertIsNone(compromisos.aplicar_sueldo(hoy))  # nada nuevo: no reescribe
        self.assertEqual(len(compromisos.validos(None, hoy, "CLP")), 1)

    def test_con_palabra_crea_la_regla(self):
        self.guardar("dice REMUNERACION")
        compromisos.aplicar_sueldo("2026-10-26")
        self.assertEqual(datos.reglas(), [{"contiene": "REMUNERACION EMPRESA FICTICIA", "categoria": "sueldo"}])
        self.assertEqual(datos.config()["inicio_mes"]["dia"], 5)

    def test_lo_que_eligio_la_persona_no_se_toca(self):
        self.guardar("llega como «Carga de saldo»")
        datos.escribir_json(os.path.join(datos.INTERNO, "config.json"), {"inicio_mes": {"modo": "dia", "dia": 1}})
        self.assertIsNone(compromisos.aplicar_sueldo("2026-10-26"))
        self.assertEqual(datos.config()["inicio_mes"], {"modo": "dia", "dia": 1})
        self.assertEqual(compromisos.validos(None, "2026-10-26", "CLP"), [])
        self.assertIsNone(compromisos.periodo_actual("2026-10-26")[0])

    def test_sin_sueldo_claro_no_se_inventa(self):
        self.guardar("sin palabra y no es lo principal")
        self.assertIsNone(compromisos.aplicar_sueldo("2026-10-26"))
        self.assertNotIn("inicio_mes", datos.config())
        self.assertEqual(compromisos.periodo_actual("2026-10-26"), (None, "2026-10"))

    def test_estado_manda_los_feriados(self):
        e = correr("estado.py")
        self.assertIn("2026-09-18", e["feriados"])


class Mora(unittest.TestCase):
    """Interés por mora de un pago atrasado (casos «mora»)."""

    def setUp(self):
        limpiar()

    def test_casos_compartidos(self):
        k = CASOS["mora"]
        self.assertEqual(k["palabras"], compromisos.palabras_mora("CL"))
        for e in k["estado"]:
            r = compromisos.estado_mes(k["compromisos"], k["movimientos"], e["mes"], e["hoy"], "CLP", None, None, k["palabras"])
            self.assertEqual(r, e["esperado"], e["nombre"])
        self.assertEqual(compromisos.mora_del_anio(k["compromisos"], k["movimientos"], k["anio"]["hoy"], "CLP", None, k["palabras"]),
                         k["anio"]["esperado"])
        # En palabras: pagó 8 días tarde y 8.000 de más; otro, 4 días tarde con un cargo aparte; a tiempo o dentro del rango, nada.
        pagos = {(i["nombre"], e["mes"]): (i["pago"] or {}).get("mora") for e in k["estado"] for i in e["esperado"]["items"] if i["pago"]}
        self.assertEqual(pagos[("Crédito Ejemplo", "2026-09")], {"monto": 8000, "dias": 8})
        self.assertEqual(pagos[("Dividendo Ejemplo", "2026-10")], {"monto": 4320, "dias": 4, "movimiento": "m007"})
        self.assertIsNone(pagos[("Colegio Ejemplo", "2026-10")])
        self.assertIsNone(pagos[("Luz Ejemplo", "2026-10")])

    def test_se_anota_y_categoriza(self):
        k = CASOS["mora"]
        datos.agregar([dict(m) for m in k["movimientos"]])
        compromisos.escribir({"formato": 1, "compromisos": k["compromisos"], "descartados": []})
        compromisos.fijar_automaticos("2026-10-26")
        lista = {c["id"]: c for c in compromisos.leer()["compromisos"]}
        self.assertEqual(lista["c-credito0001"]["pagos"]["2026-09"]["mora"], {"monto": 8000, "dias": 8})
        self.assertEqual(lista["c-dividendo01"]["pagos"]["2026-10"]["mora"]["monto"], 4320)
        cats = {m["descripcion"]: m["categoria"] for m in datos.leer_todos()}
        self.assertEqual(cats["INT. MORA DIVIDENDO"], "intereses")
        self.assertEqual(cats["INTERESES LINEA DE CREDITO"], "")  # el colegio se pagó a tiempo: ese cargo no es mora
        self.assertIn("12320 en intereses por atraso", consejos.linea_compromisos("2026-10-26", datos.leer_todos(), {"moneda": "CLP"},
                                                                                datos.categorias(), compromisos.validos(None, "2026-10-26", "CLP")))

    def test_categoria_nueva_en_un_categorias_json_de_antes(self):
        datos.escribir_json(os.path.join(datos.BASE, "categorias.json"), [{"id": "comida", "nombre": "Comida", "emoji": "🍔", "tipo": "gasto"}])
        ids = [c["id"] for c in datos.categorias()]
        self.assertEqual(ids, ["comida", "intereses"])
        self.assertEqual(next(c for c in datos.categorias() if c["id"] == "intereses")["emoji"], "🧾")


class SePagaSolo(unittest.TestCase):
    """Lo que se paga solo (PAC, suscripciones digitales) y lo que pagas tú (casos «pago»)."""

    def setUp(self):
        limpiar()

    def test_casos_compartidos(self):
        k = CASOS["pago"]
        auto = compromisos.palabras_automatico("CL")
        self.assertTrue(set(k["palabras"]) <= set(auto), "las palabras del caso salen de compromisos_conocidos.json")
        for c, esperado in k["modo"]:
            self.assertEqual(compromisos.modo_pago(c, k["palabras"]), esperado, c["nombre"])
        for e in k["estado"]:
            self.assertEqual(compromisos.estado_mes(k["compromisos"], k["movimientos"], e["mes"], e["hoy"], "CLP", None, None, None, k["palabras"]),
                             e["esperado"], e["nombre"])
        for e in k["debes"]:
            self.assertEqual(compromisos.lo_que_debes(k["compromisos"], k["movimientos"], e["hoy"], "CLP", None, None, k["palabras"]), e["esperado"])
        # En palabras: Netflix y Meli+ se pagan solos; un plan funerario y una asesoría de deudores (suscripciones) los pagas tú.
        est = {i["nombre"]: i for i in k["estado"][0]["esperado"]["items"]}
        self.assertEqual((est["Meli+"]["modo_pago"], est["Meli+"]["estado"]), ("automatico", "esperando"))
        self.assertEqual((est["Plan funerario Parque Ejemplo"]["modo_pago"], est["Plan funerario Parque Ejemplo"]["estado"]), ("manual", "atrasado"))
        self.assertEqual(est["Asesoría deudores Ejemplo"]["modo_pago"], "manual")
        self.assertEqual({i["nombre"]: i["estado"] for i in k["estado"][1]["esperado"]["items"]}["Meli+"], "atrasado", "pasada la gracia: no vimos el cargo")
        # Lo que falta pagar sigue contando los dos (la plata sale igual).
        self.assertIn("Meli+", [p["nombre"] for p in k["debes"][0]["esperado"]["partes"]])

    def test_palabras_son_datos(self):
        j = datos.leer_json(os.path.join(RAIZ, "bin", "compromisos_conocidos.json"), {})
        for pais, lista in j["automatico"].items():
            self.assertTrue(lista and all(p == datos.normalizar(p) for p in lista), pais)
        auto = compromisos.palabras_automatico("CL")
        for p in ("PAC", "NETFLIX", "MELI+", "SPOTIFY"):
            self.assertIn(p, auto)
        self.assertNotIn("MELI+", compromisos.palabras_automatico("US"))

    def test_validar(self):
        hoy = "2026-10-26"
        base = {"nombre": "Streaming", "tipo": "suscripcion", "monto": 7990, "dia": 12}
        c, e = compromisos.validar({**base, "pago": "automatico"}, None, hoy, estricto=True)
        self.assertEqual((e, c["pago"]), ([], "automatico"))
        c, e = compromisos.validar({**base, "pago": "a veces"}, None, hoy, estricto=True)
        self.assertIsNone(c)
        self.assertTrue(any("forma de pago" in x for x in e), e)
        c, e = compromisos.validar({**base, "pago": "a veces"}, None, hoy)
        self.assertEqual(e, [], "al leer el archivo, un valor raro se ignora")
        self.assertNotIn("pago", c)
        c, e = compromisos.validar(base, None, hoy)
        self.assertNotIn("pago", c, "sin el campo, se guarda sin el campo (se infiere al usarlo)")
        self.assertEqual(compromisos.parcial({**base, "pago": "manual"}, None)["pago"], "manual")
        self.assertNotIn("pago", compromisos.parcial({**base, "pago": "x"}, None))

    def test_avisos(self):
        k = CASOS["pago"]
        datos.agregar([dict(m) for m in k["movimientos"]])
        compromisos.escribir({"formato": 1, "compromisos": k["compromisos"], "descartados": []})
        datos.escribir_json(os.path.join(datos.INTERNO, "config.json"), {"avisos": True, "pais": "CL"})
        tipos = lambda hoy: [(a["nombre"], a["tipo"]) for a in compromisos.avisos(hoy)["avisos"]]
        # Meli+ e iCloud se pagan solos: nunca «por vencer» ni «vence hoy»; los que pagas tú, igual que siempre.
        self.assertEqual(tipos("2026-10-18"), [("Gimnasio", "atrasado"), ("Plan funerario Parque Ejemplo", "pronto")])
        self.assertEqual(tipos("2026-10-20"), [("Plan funerario Parque Ejemplo", "hoy")], "Meli+ vence hoy, pero se cobra solo")
        self.assertEqual(tipos("2026-10-22"), [("Plan funerario Parque Ejemplo", "atrasado"), ("Spotify", "pronto")], "Meli+ aún en la gracia")
        a = compromisos.avisos("2026-10-24")["avisos"]
        self.assertEqual([(x["nombre"], x["tipo"]) for x in a], [("Meli+", "sin_cargo"), ("Spotify", "hoy")])
        self.assertNotIn("monto", a[0], "sin montos")
        self.assertNotIn("Meli+", [n for n, _ in tipos("2026-10-25")], "«no vimos el cargo» se avisa una vez por vencimiento")

    def test_sugerir_trae_pago(self):
        hoy, cats = "2026-10-26", datos.CATEGORIAS_BASE
        movs = [{"id": "a1", "fecha": "2026-10-10", "descripcion": "PAC SEGURO EJEMPLO", "monto": -12500, "moneda": "CLP", "categoria": ""},
                {"id": "a2", "fecha": "2026-10-12", "descripcion": "ARRIENDO DEPTO EJEMPLO", "monto": -450000, "moneda": "CLP", "categoria": ""}]
        r = {s["clave"]: s for s in compromisos.sugerir(movs, [], hoy, cats, "CLP")}
        self.assertEqual(r["PAC SEGURO EJEMPLO"]["pago"], "automatico")
        self.assertEqual(r["ARRIENDO DEPTO EJEMPLO"]["pago"], "manual")

    def entender(self, texto):
        ruta = os.path.join(TMP, "entrada-ia.json")
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump({"texto": texto, "hoy": "2026-10-26"}, f)
        return correr("compromiso_ia.py", "entender", ruta)

    def test_cuentale(self):
        self.assertIn("pago", compromiso_ia.prompt("x", "2026-10-26", [], "CLP"))
        r = self.entender("el streaming se cobra solo los 12, son 7.990")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["compromiso"]["pago"], "automatico")
        malo = self.entender("PAGORARO el plan funerario")
        self.assertFalse(malo["ok"])
        self.assertIn("forma de pago", malo["error"])
        self.assertNotIn("pago", malo["parcial"])


class Chat(unittest.TestCase):
    """Conversar con Alcancía (bin/chat.py): lo que ve la IA, el plan de dos préstamos, «ese pago era del mes pasado», respuestas
    inválidas y sin IA. Los casos compartidos con ui/app.js están en pruebas/casos.json, «chat». Todo ficticio."""
    HOY = "2026-10-30"

    def setUp(self):
        limpiar()
        k = CASOS["chat"]
        datos.agregar([dict(m) for m in k["movimientos"]])
        compromisos.escribir({"formato": 1, "compromisos": [dict(c) for c in k["compromisos"]], "descartados": []})
        datos.escribir_json(os.path.join(datos.INTERNO, "config.json"),
                            {"ia": "claude", "pais": "CL", "moneda": "CLP", "inicio_mes": {"modo": "sueldo", "dia": 25}})

    def decir(self, texto, antes=()):
        return chat.enviar({"hoy": self.HOY, "mensajes": [*antes, {"rol": "persona", "texto": texto}]})

    def test_casos_compartidos(self):
        k = CASOS["chat"]
        de = lambda ids: [c for c in k["compromisos"] if ids is None or c["id"] in ids]
        for c in k["margen"]:
            self.assertEqual(compromisos.margen_mensual(de(c["compromisos_ids"]), k["movimientos"], c["hoy"], k["categorias"], "CLP", c["per"]),
                             c["esperado"], c["nombre"])
        for c in k["plan"]:
            self.assertEqual(compromisos.plan_prestamos(c["deudas"], c["margen"], "CLP"), c["esperado"], c["nombre"])
        for c in k["inicio"]:
            self.assertEqual(compromisos.inicio_plan(c["per"], c["hoy"], k["feriados"]), c["esperado"], c["nombre"])
        for c in k["reasignable"]:
            self.assertEqual(compromisos.pago_reasignable(k["compromisos"], k["movimientos"], c["id"], c["hoy"], "CLP", c["per"]), c["esperado"], c["nombre"])
        for c in k["mover"]:
            x = json.loads(json.dumps(c["compromiso"]))
            self.assertEqual(compromisos.reasignar_pago(x, c["de"], c["a"], c["movimiento"]), c["error"], c["nombre"])
            self.assertEqual(x.get("pagos", {}), c["pagos"], c["nombre"])
        pa = k["parecido"]
        lista = k["compromisos"] + pa["extra"]
        e = compromisos.estado_mes(lista, k["movimientos"], compromisos.periodo_de(pa["hoy"], pa["per"]), pa["hoy"], "CLP", pa["per"])
        for t, esperado in pa["claves"]:
            self.assertEqual(compromisos.claves_persona(t), esperado, t)
        for c in pa["casos"]:
            self.assertEqual(compromisos.prestamos_parecidos(c["propuestas"], lista, e, pa["hoy"]), c["esperado"], c["nombre"])
        for c in pa["variantes"]:
            self.assertEqual(compromisos.plan_variante(c["deudas"], c["mismos"], lista, k["movimientos"], pa["hoy"], k["categorias"], "CLP", pa["per"]),
                             c["esperado"], c["nombre"])
        for c in pa["actualizado"]:
            actual = next(x for x in lista if x["id"] == c["id"])
            self.assertEqual(compromisos.prestamo_actualizado(actual, c["deuda"], c["inicio"]), c["esperado"], c["nombre"])
        # En palabras: «es el mismo» devuelve su cuota al margen y planifica lo que falta (no el total de nuevo).
        v0, v1 = pa["variantes"][0]["esperado"], pa["variantes"][1]["esperado"]
        self.assertEqual(v1["margen"] - v0["margen"], 150000, "la cuota de «Préstamo de Mamá» ya no se resta")
        self.assertEqual(v1["deudas"][0]["total"], 1200000, "quedan 8 de 10 cuotas de 150.000")
        self.assertLess(v1["meses"], v0["meses"])
        self.assertEqual(pa["casos"][0]["esperado"][0]["cuotas"]["quedan"], 8)
        bu = k["buscar"]
        for t, esperado in bu["palabras"]:
            self.assertEqual(compromisos.palabras_busqueda(t), esperado, t)
        for c in bu["casos"]:
            self.assertEqual(compromisos.buscar_serie(c["textos"], bu["movimientos"], bu["hoy"], "CLP", c["signo"]), c["esperado"], c["nombre"])
        # En palabras: el precio de ahora (no el de antes), el día típico y la palabra que distingue; nunca PAGO ni COM.
        s = bu["casos"][0]["esperado"]
        self.assertEqual((s["monto"], s["dia"], s["buscar"], s["meses"], s["desde"]), (12990, 12, ["STREAMING"], 7, "2026-04-12"))
        self.assertEqual(bu["casos"][1]["esperado"], s, "«Pago: …com» busca lo mismo")
        self.assertEqual(bu["casos"][4]["esperado"]["aproximado"], {"variacion": 4})
        self.assertEqual([c["nombre"] for c in bu["casos"] if c["esperado"] is None][:2],
                         ["Solo gastos: buscar un ingreso con ese nombre no encuentra nada", "Palabras completas: un comercio frecuente no es un cobro"])
        d = k["despues"]
        lista = [d["compromiso"] if c["id"] == d["compromiso"]["id"] else c for c in k["compromisos"]]
        self.assertEqual(compromisos.estado_mes(lista, k["movimientos"], d["mes"], d["hoy"], "CLP", d["per"]), d["esperado"])
        # En palabras: el margen es ingreso − gasto típico − compromisos; el plan usa como máximo el 75 % y la cuota es redonda.
        m = k["margen"][0]["esperado"]
        self.assertEqual(m["margen"], m["ingreso"] - m["gasto"] - m["compromisos"])
        self.assertEqual(m["compromisos"], 450000 + 16500 + 25000, "dividendo + agua por su máximo + gimnasio; el pasaje (una vez) no")
        p = k["plan"][0]["esperado"]
        self.assertLessEqual(p["al_mes"], p["disponible"])
        self.assertEqual(p["disponible"], 650000 * 75 // 100)
        self.assertTrue(all(x["cuota"] % 5000 == 0 for x in p["deudas"]))
        self.assertFalse(k["plan"][2]["esperado"]["alcanza"])
        self.assertIsNone(k["plan"][4]["esperado"]["alcanza"])
        items = {(i["nombre"], i["vence"]): i["estado"] for i in d["esperado"]["items"]}
        self.assertEqual(items[("Dividendo", "2026-11-05")], "pendiente", "después de moverlo, el de este mes queda pendiente")
        self.assertEqual(k["reasignable"][0]["esperado"]["a"]["vence"], "2026-10-05")

    def test_lo_que_ve_la_ia(self):
        cuerpo = "1111111" + "1"  # un RUT ficticio armado por partes
        x = chat.Ctx(self.HOY)
        p = chat.prompt(x, [{"rol": "persona", "texto": "hola"}])
        for no in ("SUPERMERCADO DEL BARRIO", "DELIVERY", "EMPRESA EJEMPLO", "DIVIDENDO HIPOTECARIO", "AGUA POTABLE", "c-dividend01", "m031",
                   "banco-ejemplo"):
            self.assertNotIn(no, p, "nunca descripciones de movimientos, ids internos ni cuentas")
        for si in ("Margen mensual (ingreso típico − gasto típico − compromisos): 608.540", "C2 · «Dividendo»", "en la cartola dice: DIVIDENDO",
                   "pagado el 2026-10-28", "propone reasignar_pago", "Ingreso típico al mes: 1.500.000"):
            self.assertIn(si, p)
        r = self.decir(f"mi rut es {cuerpo}-{compromiso_ia.digito_verificador(cuerpo)} y la cuenta 12345678, ya pagué el agua")
        self.assertNotIn(cuerpo, json.dumps(chat.historial()), "lo guardado ya va limpio")
        self.assertNotIn("12345678", r["persona"]["texto"])

    def test_plan_de_dos_prestamos(self):
        r = self.decir("mi mamá me prestó 1,5 millones y mi tío Matías 4 millones, ¿cuánto puedo pagar al mes sin salirme de mis gastos?")
        self.assertTrue(r["ok"], r)
        a = r["mensaje"]["acciones"][0]
        self.assertEqual(a["tipo"], "plan_prestamos")
        plan = a["plan"]
        self.assertTrue(plan["alcanza"])
        self.assertEqual(plan["margen"], 608540)
        self.assertLessEqual(plan["al_mes"], plan["disponible"])
        self.assertEqual(len(a["propuestas"]), 2)
        ini = compromisos.inicio_plan(chat.Ctx(self.HOY).per, self.HOY, compromisos.feriados("CL"))
        for c, d in zip(a["propuestas"], plan["deudas"]):
            self.assertEqual((c["tipo"], c["signo"], c["pago"], c["frecuencia"]), ("prestamo", "gasto", "manual", "mensual"))
            self.assertEqual((c["monto"], c["cuotas_total"], c["prestamo"]["ultima"]), (d["cuota"], d["cuotas"], d["ultima"]))
            self.assertEqual((c["desde"], c["dia"]), (ini["desde"], ini["dia"]), "la primera cuota, el día después del sueldo")
            limpio, e = compromisos.validar(c, None, self.HOY)
            self.assertEqual(e, [])
        self.assertEqual([c["con"] for c in a["propuestas"]], ["Mamá", "Tío Matías"])
        # Agregarlas: el mismo camino que «Agregar» en la interfaz (guardar.py compromiso).
        import guardar
        for c in a["propuestas"]:
            self.assertTrue(guardar.compromiso({"accion": "guardar", "hoy": self.HOY, "compromiso": c})["ok"])
        self.assertEqual(sum(1 for c in compromisos.leer()["compromisos"] if c["tipo"] == "prestamo"), 2)
        self.assertEqual(len(chat.historial()), 2, "la pregunta y la respuesta quedan guardadas")

    def test_prestamo_parecido(self):
        """«Si detecta algún préstamo similar, que pregunte»: el plan y el préstamo suelto traen el parecido y, ya calculado, lo que
        cambia si la persona dice «es el mismo» (sin contar dos veces la cuota que ya estaba)."""
        import guardar
        mama = next(c for c in CASOS["chat"]["parecido"]["extra"] if c["id"] == "c-mama000001")
        lista = compromisos.leer()
        lista["compromisos"].append(dict(mama))
        compromisos.escribir(lista)
        r = self.decir("mi mamá me prestó 1,5 millones y mi tío Matías 4 millones, ¿cuánto puedo pagar al mes?")
        a = r["mensaje"]["acciones"][0]
        self.assertEqual([p and p["id"] for p in a["parecidos"]], ["c-mama000001", None], "Mamá ya está anotada; Tío Matías no")
        self.assertEqual((a["parecidos"][0]["motivo"], a["parecidos"][0]["cuotas"]["quedan"], a["parecidos"][0]["monto"]), ("persona", 8, 150000))
        self.assertEqual(list(a["variantes"]), ["0"])
        v = a["variantes"]["0"]
        self.assertEqual(v["plan"]["margen"] - a["plan"]["margen"], 150000, "«es el mismo»: su cuota vuelve al margen")
        self.assertEqual(v["plan"]["deudas"][0]["total"], 1200000, "se planifica lo que falta, no el total otra vez")
        self.assertNotEqual(v["plan"]["deudas"][1]["cuota"], a["plan"]["deudas"][1]["cuota"], "la otra deuda también se recalcula")
        act = v["propuestas"][0]
        self.assertEqual((act["id"], act["nombre"], act["buscar"], act["cuotas_pagadas"]), ("c-mama000001", "Préstamo de Mamá", ["TRANSFERENCIA MAMA"], 0))
        self.assertEqual((act["monto"], act["cuotas_total"]), (v["plan"]["deudas"][0]["cuota"], v["plan"]["deudas"][0]["cuotas"]))
        # La respuesta queda guardada: «Es el mismo» solo donde hay un parecido.
        mid = r["mensaje"]["id"]
        self.assertFalse(chat.marcar({"id": mid, "i": 0, "j": 1, "estado": "mismo"})["ok"], "Tío Matías no tiene a quién parecerse")
        self.assertTrue(chat.marcar({"id": mid, "i": 0, "j": 0, "estado": "mismo"})["ok"])
        self.assertEqual(chat.historial()[-1]["estados"], {"es:0.0": "mismo"})
        # «Actualizar»: el préstamo que ya estaba toma el plan nuevo (también desde cuándo); no se crea otro.
        for malo in ({**act, "id": "c-otro000001"}, {**act, "tipo": "deuda"}):
            self.assertFalse(guardar.compromiso({"accion": "actualizar_prestamo", "id": "c-mama000001", "hoy": self.HOY, "compromiso": malo})["ok"])
        ok = guardar.compromiso({"accion": "actualizar_prestamo", "id": "c-mama000001", "hoy": self.HOY, "compromiso": act})
        self.assertTrue(ok["ok"], ok)
        guardados = [c for c in compromisos.leer()["compromisos"] if c["tipo"] == "prestamo"]
        self.assertEqual(len(guardados), 1)
        self.assertEqual((guardados[0]["desde"], guardados[0]["monto"], guardados[0]["prestamo"]["total"]), (act["desde"], act["monto"], 1200000))
        # Ya actualizado, la misma pregunta: el margen ya cuenta la cuota nueva y sigue preguntando (la persona decide).
        r = self.decir("mi mamá me prestó 1,5 millones y mi tío Matías 4 millones")
        self.assertEqual(r["mensaje"]["acciones"][0]["parecidos"][0]["id"], "c-mama000001")
        # Un préstamo suelto parecido: «Es el mismo» propone actualizar el que ya estaba (mismo id, desde y pagos).
        r = self.decir("mi mamá OTRACUOTA")
        a = r["mensaje"]["acciones"][0]
        self.assertEqual((a["tipo"], a["parecido"]["id"]), ("crear_compromiso", "c-mama000001"))
        self.assertEqual((a["actualizar"]["id"], a["actualizar"]["cuotas_total"], a["actualizar"]["prestamo"]["total"], a["actualizar"]["desde"]),
                         ("c-mama000001", 12, 1500000, act["desde"]))
        self.assertNotEqual(a["compromiso"]["id"], "c-mama000001", "«Es otro»: la propuesta de siempre, un préstamo nuevo")
        self.assertIn("Préstamo de Mamá", chat.prompt(chat.Ctx(self.HOY), [{"rol": "persona", "texto": "hola"}]))
        self.assertIn("préstamo de 1.200.000 en total", chat.prompt(chat.Ctx(self.HOY), [{"rol": "persona", "texto": "hola"}]))
        # Sin parecido no hay pregunta (el plan de dos préstamos de siempre).
        compromisos.escribir({"formato": 1, "compromisos": [dict(c) for c in CASOS["chat"]["compromisos"]], "descartados": []})
        a = self.decir("mi mamá me prestó 1,5 millones")["mensaje"]["acciones"][0]
        self.assertNotIn("parecidos", a)

    def test_buscar_en_movimientos(self):
        """«No tenemos el cobro mensual? podrías buscarlo?»: el código busca en los movimientos (los de un conector también) y completa
        la propuesta; la IA nunca ve las descripciones. Netflix es un comercio público; montos y fechas, inventados."""
        import guardar
        movs = [{"id": f"nf{i:02d}", "fecha": f, "descripcion": "Pago: Netflix.com", "monto": -12990, "moneda": "CLP",
                 "categoria": "suscripciones" if f >= "2026-08" else "", "cuenta": "billetera-ejemplo"}
                for i, f in enumerate(["2026-04-12", "2026-05-12", "2026-06-11", "2026-07-14", "2026-08-12", "2026-09-12", "2026-10-13"])]
        datos.agregar(movs)
        x = chat.Ctx(self.HOY)
        p = chat.prompt(x, [{"rol": "persona", "texto": "hola"}])
        self.assertNotIn("Netflix.com", p, "la IA nunca ve las descripciones de los movimientos")
        for si in ('"tipo": "buscar_pago"', "Mercado Pago", "Nunca digas que no puedes buscarlo"):
            self.assertIn(si, p)
        # 1) La propuesta llega sin monto ni día y se completa sola con lo que hay en los movimientos.
        r = self.decir("creo q tengo un pago de netflix q tengo q pagar automáticamente también")
        a = r["mensaje"]["acciones"][0]
        self.assertEqual(a["tipo"], "crear_compromiso")
        self.assertNotIn("incompleto", a)
        c = a["compromiso"]
        self.assertEqual((c["nombre"], c["monto"], c["dia"], c["frecuencia"], c["buscar"], c["categoria"], c["pago"], c["desde"]),
                         ("Netflix", 12990, 12, "mensual", ["NETFLIX"], "suscripciones", "automatico", "2026-04-12"))
        self.assertEqual(a["encontrado"], {"monto": 12990, "dia": 12, "meses": 7, "veces": 7, "ultimas": ["2026-10-13", "2026-09-12", "2026-08-12"]})
        self.assertEqual(r["mensaje"]["busqueda"], {"resultado": "encontre", "nombre": "Netflix", "monto": 12990, "dia": 12, "aproximado": False})
        self.assertEqual(r["mensaje"]["texto"], "Lo encontré en tus movimientos: Netflix, $12.990 el día 12. ¿Lo agrego?", "la respuesta la arma el código")
        self.assertNotIn("nf0", json.dumps(r), "sin ids de movimientos")
        # «Agregar»: el camino de siempre; los cobros que ya pasaron quedan reconocidos con su movimiento.
        self.assertTrue(guardar.compromiso({"accion": "guardar", "hoy": self.HOY, "compromiso": c})["ok"])
        lista = compromisos.validos(None, self.HOY)
        _, pagos, _ = compromisos.asignar(lista, datos.leer_todos(), self.HOY, "CLP")
        self.assertEqual(sorted(p["movimiento"] for k, p in pagos.items() if k.startswith(c["id"])), [m["id"] for m in movs])
        # 2) buscar_pago de algo que ya está anotado: «Ya lo tienes anotado», con su último pago reconocido. Igual si la IA lo propone de nuevo.
        for texto in ("¿cuánto me cobra Netflix? búscalo", "anota netflix"):
            r = self.decir(texto)
            self.assertEqual(r["mensaje"]["acciones"], [{"tipo": "buscar_pago", "anotado": {"nombre": "Netflix", "tipo": "suscripcion", "categoria": "suscripciones", "monto": 12990, "moneda": "CLP",
                             "frecuencia": "mensual", "dia": 12, "fecha": None, "ultimo": {"fecha": "2026-10-13", "monto": 12990}}}], texto)
            self.assertEqual(r["mensaje"]["busqueda"]["resultado"], "anotado")
        r = self.decir("busca el gimnasio")  # anotado a mano, por su nombre (sin palabras para la cartola)
        self.assertEqual(r["mensaje"]["acciones"][0]["anotado"]["ultimo"], {"fecha": "2026-10-04", "monto": 25000})
        # 3) buscar_pago sin nada: se dice con honestidad, sin tarjeta.
        r = self.decir("busca el colegio")
        self.assertEqual((r["mensaje"]["acciones"], r["mensaje"]["notas"], r["mensaje"]["busqueda"]), ([], ["no_encontre_movimientos"], {"resultado": "nada"}))
        self.assertIn("No lo vi en tus movimientos de los últimos 12 meses", r["mensaje"]["texto"])
        # 4) Una propuesta sin monto que no está en los movimientos: sigue incompleta como antes, con la nota.
        r = self.decir("el colegio de los niños")
        a = r["mensaje"]["acciones"][0]
        self.assertTrue(a["incompleto"])
        self.assertEqual((r["mensaje"]["notas"], r["mensaje"]["texto"]), (["no_encontre_movimientos"], "Lo anoto, pero me falta el monto."))
        self.assertNotIn("busqueda", r["mensaje"])
        # El texto que se busca pasa por limpiar_texto (un número de cuenta no llega a ninguna parte) y las raras no buscan.
        x = chat.Ctx(self.HOY)
        self.assertEqual(chat.buscar_pago("cuenta 123456789 netflix", x)[0]["anotado"]["nombre"], "Netflix")
        self.assertEqual(chat.buscar_pago("pago mensual", x), (None, "no_aplica"))
        self.assertEqual(chat.buscar_pago(["netflix"], x), (None, "no_aplica"))

    def test_reasignar_pago_del_mes_pasado(self):
        import guardar
        r = self.decir("aún no pago el dividendo de este mes")
        a = r["mensaje"]["acciones"][0]
        self.assertEqual((a["tipo"], a["id"], a["de"]["periodo"], a["a"]["periodo"]), ("reasignar_pago", "c-dividend01", "2026-11", "2026-10"))
        # Aunque la IA proponga «dejar pendiente», si hay un vencimiento anterior sin pago se corrige moviéndolo.
        x = chat.Ctx(self.HOY)
        self.assertEqual(chat.resolver({"tipo": "marcar_pendiente", "compromiso": "C2"}, x)[0]["tipo"], "reasignar_pago")
        self.assertEqual(chat.resolver({"tipo": "reasignar_pago", "compromiso": "C9"}, x), (None, "no_encontre"))
        for malo in ({"de": "nov", "a": "2026-10"}, {"movimiento": "no-existe"}):
            self.assertFalse(guardar.compromiso({"accion": "reasignar", "id": a["id"], "de": "2026-11", "a": "2026-10", **malo})["ok"], malo)
        ok = guardar.compromiso({"accion": "reasignar", "id": a["id"], "de": a["de"]["periodo"], "a": a["a"]["periodo"], "movimiento": a["pago"]["movimiento"]})
        self.assertTrue(ok["ok"], ok)
        lista = compromisos.validos(None, self.HOY)
        per, mes = compromisos.periodo_actual(self.HOY, datos.leer_todos(), lista)
        e = compromisos.estado_mes(lista, datos.leer_todos(), mes, self.HOY, "CLP", per)
        div = [(i["vence"], i["estado"]) for i in e["items"] if i["id"] == "c-dividend01"]
        self.assertEqual(div, [("2026-11-05", "pendiente")], "octubre quedó pagado (no aparece) y noviembre pendiente")
        compromisos.fijar_automaticos(self.HOY)
        self.assertNotIn("como", compromisos.leer()["compromisos"][1]["pagos"]["2026-11"], "no se vuelve a reconocer solo")
        r = self.decir("aún no pago el dividendo de este mes")
        self.assertEqual((r["mensaje"]["acciones"], r["mensaje"]["notas"]), ([], ["sin_pago_para_mover"]))
        r = self.decir("ya pagué el dividendo")
        self.assertEqual(r["mensaje"]["notas"], ["no_encontre"], "la IA falsa busca «ARRIENDO»: no hay, y se dice")

    def test_respuesta_invalida_y_acciones_raras(self):
        r = self.decir("INVALIDA")
        self.assertFalse(r["ok"])
        self.assertIn("no respondió como esperaba", r["error"])
        self.assertTrue(chat.historial()[-1]["error"], "el mensaje honesto también queda en la conversación")
        r = self.decir("RARA", antes=[{"rol": "persona", "texto": "hola"}, {"rol": "alcancia", "texto": "¡Hola!"}])
        self.assertTrue(r["ok"])
        self.assertEqual([a["tipo"] for a in r["mensaje"]["acciones"]], ["crear_compromiso"], "solo pasa la acción válida")
        self.assertEqual(r["mensaje"]["notas"], ["descartadas"])
        r = self.decir("SINMONTO las clases de yoga")
        a = r["mensaje"]["acciones"][0]
        self.assertTrue(a["incompleto"])
        self.assertEqual(a["compromiso"]["nombre"], "Clases de yoga", "nunca sin salida: lo que se entendió va a la tarjeta")
        self.assertEqual(r["mensaje"]["notas"], ["no_encontre_movimientos"], "lo buscó en los movimientos y no estaba")
        for malo in ('{"respuesta": "hola", "extra": 1}', '{"acciones": []}', '{"respuesta": "", "acciones": []}', '{"respuesta": "x", "acciones": {}}'):
            self.assertIsNone(chat.validar_respuesta(malo)[0], malo)
        self.assertEqual(chat.validar_respuesta('{"respuesta": "Listo"}'), ("Listo", [], 0))
        self.assertFalse(self.decir("x")["ok"], "un mensaje de una letra no se manda")

    def test_sin_ia(self):
        datos.escribir_json(os.path.join(datos.INTERNO, "config.json"), {"ia": "gemini"})
        antes = os.environ["PATH"]
        os.environ["PATH"] = BIN_FALSO  # sin agy ni gemini
        try:
            r = self.decir("hola")
        finally:
            os.environ["PATH"] = antes
        self.assertEqual((r["ok"], r.get("sin_ia")), (False, True))
        self.assertIn("Ajustes", r["error"])
        self.assertEqual(chat.historial(), [], "sin IA no se guarda nada")

    def test_marcar_borrar_y_cli(self):
        entrada = os.path.join(TMP, "entrada-chat.json")
        datos.escribir_json(entrada, {"hoy": self.HOY, "mensajes": [{"rol": "persona", "texto": "mi mamá me prestó 1,5 millones y mi tío Matías 4 millones"}]})
        r = correr("chat.py", "enviar", entrada)
        self.assertTrue(r["ok"], r)
        mid = r["mensaje"]["id"]
        datos.escribir_json(entrada, {"id": mid, "i": 0, "j": 1, "estado": "hecha"})
        self.assertTrue(correr("chat.py", "marcar", entrada)["ok"])
        self.assertEqual(chat.historial()[-1]["estados"], {"0.1": "hecha"})
        for malo in ({"id": mid, "i": 3, "estado": "hecha"}, {"id": mid, "i": 0, "j": 5, "estado": "hecha"}, {"id": mid, "i": 0, "estado": "rm"},
                     {"id": "otro", "i": 0, "estado": "no"}):
            self.assertFalse(chat.marcar(malo)["ok"], malo)
        self.assertTrue(correr("chat.py", "borrar", entrada)["ok"])
        self.assertEqual(chat.historial(), [])
        self.assertEqual(json.loads(json.dumps(__import__("estado").estado()["chat"])), [])


AYUDA_CLAUDE = "Usage: claude [options]\n  --strict-mcp-config\n  --disallowedTools <tools...>"


class SeguridadIA(unittest.TestCase):
    """Cómo se llama a Claude: sin memoria de la persona y con --safe-mode solo si su versión lo conoce; y T() escapa."""

    def _con_claude(self, ayuda):
        import ia
        carpeta = tempfile.mkdtemp(dir=TMP)
        anotado = os.path.join(carpeta, "anotado.json")
        ruta = os.path.join(carpeta, "claude")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("#!" + sys.executable + "\nimport json, os, sys\n"
                    f"if '--help' in sys.argv: print({ayuda!r}); sys.exit(0)\n"
                    f"json.dump({{'argv': sys.argv[1:], 'env': dict(os.environ)}}, open({anotado!r}, 'w'))\n"
                    "print('listo')\n")
        os.chmod(ruta, 0o755)
        antes_path, antes_elegida = os.environ["PATH"], ia.elegida
        os.environ["PATH"] = carpeta + os.pathsep + antes_path
        ia.elegida = lambda: "claude"
        ia._ayuda.clear()
        try:
            r = ia.ejecutar("hola", timeout=60)
        finally:
            os.environ["PATH"], ia.elegida = antes_path, antes_elegida
            ia._ayuda.clear()
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(anotado, encoding="utf-8") as f:
            return json.load(f)

    def test_claude_sin_memoria_y_safe_mode_si_existe(self):
        x = self._con_claude(AYUDA_CLAUDE + "\n  --safe-mode  Sin extensiones")
        self.assertEqual((x["env"].get("CLAUDE_CODE_DISABLE_CLAUDE_MDS"), x["env"].get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")), ("1", "1"))
        self.assertIn("--safe-mode", x["argv"])
        self.assertEqual(x["argv"][x["argv"].index("--disallowedTools") + 1], "*")
        self.assertFalse([k for k in x["env"] if k.startswith("ALCANCIA_")])

    def test_claude_viejo_sin_safe_mode(self):
        x = self._con_claude(AYUDA_CLAUDE)
        self.assertNotIn("--safe-mode", x["argv"], "una versión que no la conoce fallaría con la opción")

    def test_claude_sin_las_protecciones_no_corre(self):
        """Un CLI que no conoce --strict-mcp-config o --disallowedTools nunca corre sin ellas: se pide actualizarlo."""
        import ia
        with self.assertRaises(ia.VersionVieja):
            self._con_claude("Usage: claude [options]\n  --disallowedTools <tools...>")
        antes = ia.ejecutar
        ia.ejecutar = lambda *a, **k: (_ for _ in ()).throw(ia.VersionVieja("--strict-mcp-config"))
        try:
            texto, error = ia.preguntar("hola")
        finally:
            ia.ejecutar = antes
        self.assertEqual((texto, error["codigo"]), ("", "actualizar"))

    def test_T_escapa_los_valores(self):
        import re
        if not shutil.which("node"):
            self.skipTest("falta node")
        js = open(os.path.join(RAIZ, "ui", "app.js"), encoding="utf-8").read()
        # T, Thtml y Tp son de la pieza «i18n» (ui/i18n.js): se prueban tal como los usa app.js.
        prueba = (f"const {{ T, Thtml, Tp }} = require({os.path.join(RAIZ, 'ui', 'i18n.js')!r}).crear();\n"
                  "console.log(T('Pagaste **{x}** ({m})', { x: '$1.000', m: '<img src=x onerror=alert(1)>' }));"
                  "console.log(Thtml('Te faltan {m} al mes', { m: '<span class=\"monto-chat\">$5</span>' }));"
                  "console.log(Tp('Creé «{c}»', { c: '<b>' }));")
        self.assertIn("const { tr, T, Thtml, Tp, frase, traducirDOM } = i18n;", js, "app.js usa los de la pieza")
        r = subprocess.run(["node", "-e", prueba], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip().splitlines(), ["Pagaste <b>$1.000</b> (&lt;img src=x onerror=alert(1)&gt;)",
                                                         'Te faltan <span class="monto-chat">$5</span> al mes', "Creé «<b>»"])
        self.assertNotRegex(js, r"esc\((T|Thtml|frase)\(", "T ya escapa: no escapar dos veces")
        self.assertNotRegex(js, r"toast\((T|Thtml|frase)\(", "el aviso es texto plano (textContent): va con Tp")


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read()


class Piezas(unittest.TestCase):
    """Las piezas de Pieza (nucleo, ia, i18n): la carpeta de siempre, la config validada por app.json y la IA probada con entrada."""

    def setUp(self):
        limpiar()

    def test_app_json_apunta_a_la_carpeta_de_siempre(self):
        """Sin variables, la carpeta de datos de nucleo es ~/Alcancia/.alcancia: la de siempre (nadie pierde ni mueve datos)."""
        casa = tempfile.mkdtemp(dir=TMP)
        env = {k: v for k, v in os.environ.items() if not k.startswith("ALCANCIA_")}
        env["HOME"] = casa
        codigo = "import sys; sys.path.insert(0, 'bin'); import nucleo, datos; print(nucleo.carpeta_datos()); print(datos.INTERNO)"
        r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), [os.path.join(casa, "Alcancia", ".alcancia")] * 2)
        self.assertFalse(os.path.exists(os.path.join(casa, "Alcancia")), "solo leer no crea carpetas")
        import nucleo
        self.assertEqual(nucleo.carpeta_datos(), datos.INTERNO, "con ALCANCIA_CARPETA (pruebas), nucleo la sigue")

    def test_config_validada_por_app_json(self):
        datos.escribir_json(os.path.join(datos.INTERNO, "config.json"), {
            "ia": "otra", "idioma_ui": "fr", "pais": "AR", "moneda": "ARS", "vigilar": "sí", "avisos": True, "clave_rara": 1,
            "inicio_mes": {"modo": "dia", "dia": 5}, "uf": {"valor": 39000, "fecha": "2026-10-01"}})
        c = datos.config()
        self.assertEqual((c["ia"], c["idioma_ui"], c["pais"], c["moneda"], c["avisos"]), ("claude", "", "AR", "ARS", True))
        self.assertNotIn("vigilar", c)
        self.assertNotIn("clave_rara", c)
        self.assertEqual(c["inicio_mes"], {"modo": "dia", "dia": 5})
        self.assertEqual(compromisos.uf_config(c)["valor"], 39000)

    def test_las_claves_de_config_son_las_mismas_en_el_mac(self):
        import re
        app = json.loads(_leer(os.path.join(RAIZ, "app.json")))
        swift = _leer(os.path.join(RAIZ, "app", "Sources", "Alcancia", "Servicios.swift"))
        permitidas = set(re.findall(r'"(\w+)"', re.search(r"static let permitidas: Set<String> = \[(.*?)\]", swift).group(1)))
        self.assertEqual(permitidas, set(app["config"]), "Config.permitidas (Swift) = claves simples de app.json")
        self.assertFalse(set(datos.CONFIG_OBJETOS) & set(app["config"]))
        self.assertEqual(app["id"], "alcancia")
        self.assertEqual((app["nombre"], app["datos"], app["privado"]), ("Alcancía", {"carpeta": "~/Alcancia/.alcancia"}, True))

    def test_app_json_va_dentro_de_la_app(self):
        sh = _leer(os.path.join(RAIZ, "herramientas", "empaquetar.sh"))
        self.assertIn('cp "$RAIZ/app.json" "$APP/Contents/Resources/alcancia/app.json"', sh)
        ventana = _leer(os.path.join(RAIZ, "app", "Sources", "Alcancia", "Ventana.swift"))
        self.assertIn('Procesador.conEntrada("ia.py", "probar", ["ia": id])', ventana, "la IA se prueba con la pieza, con entrada")
        self.assertNotIn("IA.probar(", ventana)

    def test_escribir_siempre_privado(self):
        ruta = os.path.join(datos.BASE, "reglas.json")
        datos.escribir_json(ruta, [])
        os.chmod(ruta, 0o644)
        datos.escribir_json(ruta, [{"contiene": "X", "categoria": "otros"}])
        if os.name != "nt":
            self.assertEqual(os.stat(ruta).st_mode & 0o777, 0o600, "datos financieros: siempre 0600")
        self.assertFalse([f for f in os.listdir(datos.BASE) if f.startswith(".alcancia-")], "sin temporales huérfanos")

    def test_probar_la_ia_con_entrada(self):
        entrada = os.path.join(TMP, "entrada-ia.json")
        with open(entrada, "w", encoding="utf-8") as f:
            json.dump({"ia": "claude"}, f)
        r = correr("ia.py", "probar", entrada)
        self.assertEqual((r["ia"], r["ok"]), ("claude", True), r)
        with open(entrada, "w", encoding="utf-8") as f:
            json.dump({"ia": "otra"}, f)
        r = correr("ia.py", "probar", entrada)
        self.assertEqual((r["ok"], r["codigo"]), (False, "desconocida"))

    def test_error_de_la_ia_en_palabras_y_con_codigo(self):
        import ia
        antes = ia.comando
        ia.comando = lambda _ia: None
        try:
            self.assertEqual(categorizar.por_ia([{"descripcion": "X", "monto": -1, "categoria": ""}], datos.categorias())[1],
                             f"No encontré {ia.nombre()} en este computador. Revisa en Ajustes → Tu IA.")
        finally:
            ia.comando = antes


if __name__ == "__main__":
    try:
        unittest.main(verbosity=1)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
