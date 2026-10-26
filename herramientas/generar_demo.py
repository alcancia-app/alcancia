"""Genera ui/demo.json: seis meses de movimientos FICTICIOS para la vista previa, las pruebas y las capturas de la página.
Uso: python3 herramientas/generar_demo.py   (siempre da lo mismo: semilla fija)
"""
import json
import os
import random
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "bin"))
import compromisos  # noqa: E402
import conectores  # noqa: E402
import datos  # noqa: E402

random.seed(7)
HOY = "2026-10-18"
MESES = ["2026-07", "2026-08", "2026-09", "2026-10"]
# (descripción, categoría, monto mínimo, máximo, veces al mes, cuenta)
VARIABLES = [
    ("SUPERMERCADO DEL BARRIO", "supermercado", 18000, 62000, 5, "banco-ejemplo"),
    ("MINIMARKET DON PEPE", "supermercado", 2500, 9000, 6, "billetera-ejemplo"),
    ("DELIVERY RAPIDITO *PEDIDO", "comida", 9000, 19000, 6, "billetera-ejemplo"),
    ("CAFE LA ESQUINA", "comida", 2800, 4500, 8, "billetera-ejemplo"),
    ("SUSHI DEL PUERTO", "comida", 14000, 26000, 1, "banco-ejemplo"),
    ("VIAJES APP *TRIP", "transporte", 3500, 9500, 5, "billetera-ejemplo"),
    ("CARGA TARJETA TRANSPORTE", "transporte", 10000, 10000, 2, "banco-ejemplo"),
    ("BENCINERA RUTA 5", "auto", 30000, 45000, 2, "banco-ejemplo"),
    ("FARMACIA SALUDABLE", "salud", 4500, 21000, 2, "banco-ejemplo"),
    ("TIENDA ONLINE *COMPRA", "compras", 9000, 39000, 2, "billetera-ejemplo"),
    ("CINE CENTRAL", "ocio", 7000, 16000, 1, "billetera-ejemplo"),
    ("VETERINARIA PATITAS", "mascotas", 12000, 25000, 1, "banco-ejemplo"),
]
FIJOS = [
    (1, "ARRIENDO DEPTO", "casa", -420000, "banco-ejemplo"),
    (5, "REMUNERACION EMPRESA FICTICIA SPA", "sueldo", 1450000, "banco-ejemplo"),
    (6, "STREAMING PELIS", "suscripciones", -9990, "banco-ejemplo"),
    (6, "MUSICA PREMIUM", "suscripciones", -5490, "billetera-ejemplo"),
    (10, "INTERNET Y CELULAR", "cuentas", -27990, "banco-ejemplo"),
    (12, "AGUA POTABLE", "cuentas", -14500, "banco-ejemplo"),
    (15, "TRASPASO A BILLETERA", "transferencia", -150000, "banco-ejemplo"),
    (15, "TRASPASO DESDE BANCO", "transferencia", 150000, "billetera-ejemplo"),
    (20, "JARDIN INFANTIL", "educacion", -95000, "banco-ejemplo"),
]

movs = []
for i, mes in enumerate(MESES):
    ultimo = 18 if mes == HOY[:7] else 28
    for dia, desc, cat, monto, cuenta in FIJOS:
        if dia <= ultimo:
            movs.append((f"{mes}-{dia:02d}", desc, cat, monto, cuenta))
    for desc, cat, lo, hi, veces, cuenta in VARIABLES:
        # En octubre el delivery se dispara: así la demo muestra una alerta real.
        n = veces + (3 if desc.startswith("DELIVERY") and mes == "2026-10" else 0)
        n = round(n * ultimo / 28)
        for _ in range(n):
            dia = random.randint(1, ultimo)
            movs.append((f"{mes}-{dia:02d}", desc, cat, -round(random.randint(lo, hi), -1), cuenta))
# Mayo y junio van aparte (con su propia semilla) para que julio a octubre no cambien. En junio hubo un viaje: ese mes se pasa.
otro = random.Random(5)
for mes in ("2026-05", "2026-06"):
    for dia, desc, cat, monto, cuenta in FIJOS:
        movs.append((f"{mes}-{dia:02d}", desc, cat, monto, cuenta))
    for desc, cat, lo, hi, veces, cuenta in VARIABLES:
        for _ in range(veces):
            movs.append((f"{mes}-{otro.randint(1, 28):02d}", desc, cat, -round(otro.randint(lo, hi), -1), cuenta))
# Compromisos de Ana: el crédito automotriz (cuota N/36, el 20) y el plan de celular (el 10), que en octubre todavía no se paga.
# La luz y los gastos comunes varían un poco cada mes (montos fijos por mes, sin azar: así lo demás no cambia). El seguro de salud
# se paga en UF: lo que se paga en pesos sube con la UF (1,85 UF × un valor ficticio de la UF de cada mes).
LUZ = {"2026-05": 31200, "2026-06": 33800, "2026-07": 30500, "2026-08": 33900, "2026-09": 31800, "2026-10": 32700}
COMUNES = {"2026-05": 59400, "2026-06": 58800, "2026-07": 58200, "2026-08": 61900, "2026-09": 60300, "2026-10": 63100}
UF_MES = {"2026-07": 39200, "2026-08": 39300, "2026-09": 39400}  # el de octubre vence el 22: todavía no se paga
for mes, monto in LUZ.items():
    movs.append((f"{mes}-08", "LUZ DEL SUR", "cuentas", -monto, "banco-ejemplo"))
for mes, monto in COMUNES.items():
    movs.append((f"{mes}-05", "GASTOS COMUNES EDIFICIO", "casa", -monto, "banco-ejemplo"))
for mes, uf in UF_MES.items():
    movs.append((f"{mes}-22", "SEGURO SALUD COMPLEMENTARIO", "salud", -round(1.85 * uf), "banco-ejemplo"))
# Préstamos entre personas (ficticios): Ana le debe a su mamá (8 cuotas de 150.000, el 25) y Matías le devuelve a Ana (3 de 100.000,
# el 5). Van por la billetera y antes de su saldo informado (18 oct), así «Lo que tienes» no cambia.
for mes in ("2026-08", "2026-09"):
    movs.append((f"{mes}-25", "TRANSFERENCIA A MAMA", "otros", -150000, "billetera-ejemplo"))
movs.append(("2026-09-05", "TRANSFERENCIA DE MATIAS SOTO", "otros_ingresos", 100000, "billetera-ejemplo"))
for i, mes in enumerate(("2026-05", "2026-06", "2026-07", "2026-08", "2026-09")):
    movs.append((f"{mes}-20", f"CREDITO AUTOMOTRIZ CUOTA {8 + i}/36", "auto", -189000, "banco-ejemplo"))
    movs.append((f"{mes}-10", "PLAN MOVIL EJEMPLO", "cuentas", -15990, "banco-ejemplo"))
# Lo que Alcancía detecta en la cartola de octubre y pregunta si es un compromiso.
movs.append(("2026-10-09", "CREDITO CONSUMO CUOTA 4/24", "", -64500, "banco-ejemplo"))
movs.append(("2026-10-12", "SEGURO HOGAR EJEMPLO", "", -8990, "banco-ejemplo"))
movs.append(("2026-06-21", "PASAJES AEREOS EJEMPLO", "ocio", -189000, "banco-ejemplo"))
movs.append(("2026-06-24", "HOSTAL VISTA AL MAR", "ocio", -96000, "banco-ejemplo"))
movs.append((f"2026-10-16", "PAGO PENDIENTE 88231", "", -12990, "banco-ejemplo"))
movs.append((f"2026-10-17", "TRANSFERENCIA A MATIAS SOTO", "", -25000, "billetera-ejemplo"))
# Sin categoría para probar el ordenar rápido (el delivery ya se ordenó antes: Alcancía sugiere aprenderlo).
movs.append(("2026-10-14", "ENTRADAS CONCIERTO EJEMPLO", "", -32000, "billetera-ejemplo"))
movs.append(("2026-10-15", "HELADERIA POLO SUR", "", -4500, "billetera-ejemplo"))
movs.append(("2026-10-17", "DELIVERY RAPIDITO *PEDIDO", "", -13990, "billetera-ejemplo"))
# Cómo se pagó (lo que trae el conector): compras con crédito en cuotas, una en 1 cuota, una devolución y el pago de la tarjeta.
COMO = {}
def credito(f, desc, cat, monto, cuotas=0, cuota=0):
    movs.append((f, desc, cat, monto, "billetera-ejemplo"))
    COMO[(f, desc)] = {"medio": "credito", **({"cuotas": str(cuotas), "cuota": str(cuota)} if cuotas else {})}
credito("2026-08-14", "TIENDA ELECTRO *LAVADORA", "casa", -349900, 6, 61000)
credito("2026-10-08", "ZAPATILLAS DEPORTE EJEMPLO", "compras", -89970, 3, 29990)
credito("2026-10-11", "LIBRERIA CENTRAL", "educacion", -15990)
movs.append(("2026-10-05", "PAGO TARJETA BILLETERA EJEMPLO", "transferencia", -137990, "banco-ejemplo"))
movs.append(("2026-10-02", "TIENDA ONLINE *AUDIFONOS", "compras", -24990, "billetera-ejemplo"))
movs.append(("2026-10-13", "Devolución: TIENDA ONLINE *AUDIFONOS", "compras", 24990, "billetera-ejemplo"))
COMO[("2026-10-02", "TIENDA ONLINE *AUDIFONOS")] = COMO[("2026-10-13", "Devolución: TIENDA ONLINE *AUDIFONOS")] = {"medio": "saldo"}

vistos = {}
salida = []
for f, desc, cat, monto, cuenta in sorted(movs):
    k = (f, desc, monto)
    vistos[k] = vistos.get(k, -1) + 1
    salida.append({"id": datos.nuevo_id(cuenta, f, desc, monto, vistos[k]), "fecha": f, "descripcion": desc, "monto": monto,
                   "moneda": "CLP", "categoria": cat, "cuenta": cuenta, "origen": "demo", "nota": "", **COMO.get((f, desc), {})})

def compromiso(**k):
    k.setdefault("nombre", "")
    c, errores = compromisos.validar({**k, "origen": "manual"}, None, HOY)
    assert not errores, errores
    return c


COMPROMISOS = [
    compromiso(id="c-arriendo01", nombre="Arriendo", tipo="cuenta", monto=420000, dia=1, categoria="casa", buscar=["ARRIENDO"], desde="2026-07-01"),
    compromiso(id="c-credito001", nombre="Crédito automotriz", tipo="deuda", monto=189000, dia=20, categoria="auto",
               buscar=["CREDITO AUTOMOTRIZ"], cuotas_total=36, cuotas_pagadas=12, desde="2026-10-01"),
    compromiso(id="c-celular001", nombre="Plan de celular", tipo="cuenta", monto=15990, dia=10, categoria="cuentas", buscar=["PLAN MOVIL"],
               desde="2026-07-01"),
    compromiso(id="c-sueldo0001", nombre="Sueldo", tipo="ingreso", monto=1450000, dia=5, categoria="sueldo", buscar=["REMUNERACION"],
               desde="2026-07-01"),
]
COMPROMISOS += [
    compromiso(id="c-comunes001", nombre="Gastos comunes", tipo="cuenta", monto=60000, dia=5, categoria="casa", buscar=["GASTOS COMUNES"],
               aproximado={"variacion": 10}, desde="2026-07-01"),
    compromiso(id="c-seguro0001", nombre="Seguro de salud", tipo="cuenta", monto=1.85, moneda="UF", dia=22, categoria="salud",
               buscar=["SEGURO SALUD"], desde="2026-07-01"),
]
COMPROMISOS += [
    compromiso(id="c-mama000001", tipo="prestamo", con="Mamá", prestamo={"total": 1200000}, cuotas_total=8, dia=25, buscar=["TRANSFERENCIA A MAMA"],
               desde="2026-08-01"),
    compromiso(id="c-matias0001", tipo="prestamo", signo="ingreso", con="Matías", prestamo={"total": 300000}, cuotas_total=3, dia=5,
               buscar=["MATIAS SOTO"], desde="2026-09-01"),
]
SUGERENCIAS = compromisos.sugerir(salida, COMPROMISOS, HOY, datos.CATEGORIAS_BASE, "CLP")

demo = {
    "hoy": HOY,
    "version": "0.1.0",
    "carpeta": "~/Alcancia",
    "config": {"ia": "claude", "pais": "CL", "moneda": "CLP", "idioma_ui": "", "respaldo": "local"},
    "ias": [{"id": "claude", "nombre": "Claude", "instalada": True}, {"id": "codex", "nombre": "ChatGPT (Codex)", "instalada": True},
            {"id": "gemini", "nombre": "Gemini", "instalada": False}],
    # Ana anotó cuánto tenía en el banco el 30 de septiembre; la billetera informa su saldo (como Mercado Pago).
    "cuentas": [{"id": "banco-ejemplo", "nombre": "Banco Ejemplo", "receta": "cl-banco-ejemplo", "moneda": "CLP",
                 "saldo": {"monto": 612000, "fecha": "2026-09-30", "origen": "persona"}},
                {"id": "billetera-ejemplo", "nombre": "Billetera Ejemplo", "receta": "cl-billetera-ejemplo", "moneda": "CLP",
                 "saldo": {"monto": 84300, "fecha": "2026-10-18", "origen": "conector"}}],
    "categorias": datos.CATEGORIAS_BASE,
    "presupuesto": {"moneda": "CLP", "mensual": {"supermercado": 230000, "comida": 140000, "transporte": 55000, "auto": 80000,
                                                 "casa": 420000, "cuentas": 80000, "salud": 30000, "suscripciones": 16000,
                                                 "compras": 50000, "ocio": 20000, "educacion": 95000, "mascotas": 20000}},
    "reglas": [{"contiene": "CAFE LA ESQUINA", "categoria": "comida"}],
    "consejos": [{"fecha": "2026-10-14", "texto": "### Lo que va bien\n- Tus cuentas básicas y suscripciones están justo en lo presupuestado.\n- Supermercado va en un 46% con el mes a la mitad: bien encaminado.\n\n### Ojo con\n- **Comida fuera y delivery** ya pasó los 100.000 y quedan dos semanas: a este ritmo terminas cerca de 190.000.\n- Hay 2 movimientos sin categoría: ponles una para que el resumen cuadre.\n\n### Para esta semana\n- Cocina 3 noches en vez de pedir delivery: ahorras cerca de 40.000.\n- Lleva café en un termo dos días: son 7.000 menos."}],
    "movimientos": salida,
    "conectores": conectores.info_publica(),
    "conexiones": {"mercadopago": {"conectado": True, "ultima": "2026-10-18T12:40:00+00:00", "error": "", "nuevos": 3, "esperando": False}},
    "ia_externa": [{"id": "claude_desktop", "nombre": "Claude (app de escritorio)", "instalado": True, "conectado": True, "al_dia": True,
                    "nota": "Cierra y vuelve a abrir Claude para que aparezca."},
                   {"id": "claude_code", "nombre": "Claude Code", "instalado": True, "conectado": False, "al_dia": False, "nota": ""},
                   {"id": "codex", "nombre": "ChatGPT (app de escritorio y Codex)", "instalado": True, "conectado": False, "al_dia": False, "nota": ""},
                   {"id": "gemini", "nombre": "Gemini CLI", "instalado": False, "conectado": False, "al_dia": False, "nota": ""},
                   {"id": "antigravity", "nombre": "Antigravity (Gemini)", "instalado": False, "conectado": False, "al_dia": False, "nota": ""}],
    "compromisos": {"formato": 1, "compromisos": COMPROMISOS, "descartados": [], "invalidos": 0},
    "sugerencias": SUGERENCIAS,
    "vigilar": {"activo": True, "recientes": [{"archivo": "cartola-banco-ejemplo-octubre.csv", "resultado": "importado", "institucion": "Banco Ejemplo",
                                               "nuevos": 12, "cuando": 1792332000}]},
}
with open(os.path.join(RAIZ, "ui", "demo.json"), "w", encoding="utf-8") as f:
    json.dump(demo, f, ensure_ascii=False, indent=1)
    f.write("\n")
print(f"{len(salida)} movimientos ficticios, {len(COMPROMISOS)} compromisos y {len(SUGERENCIAS)} sugerencias")
