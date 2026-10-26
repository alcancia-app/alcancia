"""Genera ui/demo.json: cuatro meses de movimientos FICTICIOS para la vista previa, las pruebas y las capturas de la página.
Uso: python3 herramientas/generar_demo.py   (siempre da lo mismo: semilla fija)
"""
import json
import os
import random
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "bin"))
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
    (8, "LUZ DEL SUR", "cuentas", -32000, "banco-ejemplo"),
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
movs.append((f"2026-10-16", "PAGO PENDIENTE 88231", "", -12990, "banco-ejemplo"))
movs.append((f"2026-10-17", "TRANSFERENCIA A MATIAS SOTO", "", -25000, "billetera-ejemplo"))

vistos = {}
salida = []
for f, desc, cat, monto, cuenta in sorted(movs):
    k = (f, desc, monto)
    vistos[k] = vistos.get(k, -1) + 1
    salida.append({"id": datos.nuevo_id(cuenta, f, desc, monto, vistos[k]), "fecha": f, "descripcion": desc, "monto": monto,
                   "moneda": "CLP", "categoria": cat, "cuenta": cuenta, "origen": "demo", "nota": ""})

demo = {
    "hoy": HOY,
    "version": "0.1.0",
    "carpeta": "~/Alcancia",
    "config": {"ia": "claude", "pais": "CL", "moneda": "CLP", "idioma_ui": "", "respaldo": "local"},
    "ias": [{"id": "claude", "nombre": "Claude", "instalada": True}, {"id": "codex", "nombre": "ChatGPT (Codex)", "instalada": True},
            {"id": "gemini", "nombre": "Gemini", "instalada": False}],
    "cuentas": [{"id": "banco-ejemplo", "nombre": "Banco Ejemplo", "receta": "cl-banco-ejemplo", "moneda": "CLP"},
                {"id": "billetera-ejemplo", "nombre": "Billetera Ejemplo", "receta": "cl-billetera-ejemplo", "moneda": "CLP"}],
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
    "vigilar": {"activo": True, "recientes": [{"archivo": "cartola-banco-ejemplo-octubre.csv", "resultado": "importado", "institucion": "Banco Ejemplo",
                                               "nuevos": 12, "cuando": 1792332000}]},
}
with open(os.path.join(RAIZ, "ui", "demo.json"), "w", encoding="utf-8") as f:
    json.dump(demo, f, ensure_ascii=False, indent=1)
    f.write("\n")
print(f"{len(salida)} movimientos ficticios")
