"""Poner categoría a cada movimiento: primero lo que la persona enseñó (reglas), después palabras conocidas y al final su IA.
Solo biblioteca estándar.
"""
import re

import datos
import ia

#: Comercios muy comunes por categoría (en mayúsculas y sin tildes). La comunidad los amplía por país.
#: Lo más largo se revisa primero: «UBER EATS» es comida antes de que «UBER» sea transporte.
CONOCIDOS = {
    "comida": ["UBER EATS", "RAPPI", "PEDIDOSYA", "PEDIDOS YA", "DIDI FOOD", "JUSTO", "MCDONALD", "BURGER KING", "STARBUCKS",
               "DOMINO", "PAPA JOHN", "KFC", "SUBWAY", "TELEPIZZA", "DOGGIS", "JUAN MAESTRO"],
    "supermercado": ["LIDER", "JUMBO", "UNIMARC", "SANTA ISABEL", "TOTTUS", "ACUENTA", "MAYORISTA 10", "ALVI", "OK MARKET",
                     "CARREFOUR", "MERCADONA", "WALMART", "COSTCO"],
    "transporte": ["UBER", "CABIFY", "DIDI", "METRO", "BIP", "RED MOVILIDAD", "TURBUS", "PULLMAN", "LATAM", "SKY AIRLINE", "JETSMART"],
    "auto": ["COPEC", "SHELL", "PETROBRAS", "ARAMCO", "ENEX", "AUTOPISTA", "COSTANERA NORTE", "VESPUCIO", "TAG ", "ESTACIONAMIENTO"],
    "suscripciones": ["NETFLIX", "SPOTIFY", "DISNEY", "YOUTUBE PREMIUM", "APPLE.COM", "ICLOUD", "GOOGLE ONE", "AMAZON PRIME",
                      "PRIME VIDEO", "HBO", "MAX.COM", "PARAMOUNT", "CHATGPT", "OPENAI", "ANTHROPIC", "CLAUDE.AI"],
    "salud": ["FARMACIA", "CRUZ VERDE", "SALCOBRAND", "AHUMADA", "DR SIMI", "CLINICA", "ISAPRE", "FONASA", "INTEGRAMEDICA", "REDSALUD"],
    "cuentas": ["ENEL", "AGUAS ANDINAS", "ESVAL", "ESSBIO", "METROGAS", "ABASTIBLE", "LIPIGAS", "GASCO", "ENTEL", "MOVISTAR",
                "CLARO", "WOM", "VTR", "GTD", "MUNDO PACIFICO", "CGE"],
    "compras": ["FALABELLA", "PARIS", "RIPLEY", "MERCADOLIBRE", "MERCADO LIBRE", "ALIEXPRESS", "SHEIN", "TEMU", "AMAZON",
                "SODIMAC", "EASY", "HITES", "LA POLAR", "IKEA", "H&M", "ZARA"],
    "ocio": ["CINEMARK", "CINEPOLIS", "CINE HOYTS", "PUNTOTICKET", "TICKETMASTER", "STEAM", "PLAYSTATION", "NINTENDO", "XBOX"],
    "mascotas": ["SUPERZOO", "PET HAPPY", "VETERINARI"],
}
_ORDEN = sorted(((p, c) for c, ps in CONOCIDOS.items() for p in ps), key=lambda x: -len(x[0]))


def por_reglas(movimientos, reglas):
    """Aplica lo aprendido (la regla más larga gana) y luego los comercios conocidos. Solo toca los que no tienen categoría."""
    reglas = sorted(((datos.normalizar(r["contiene"]), r["categoria"]) for r in reglas if r.get("contiene")), key=lambda x: -len(x[0]))
    for m in movimientos:
        if m.get("categoria"):
            continue
        d = datos.normalizar(m["descripcion"])
        for patron, cat in reglas + _ORDEN:
            if patron and patron in d:
                m["categoria"] = cat
                break
        else:
            if m["monto"] > 0 and re.search(r"\b(REMUNERACION|SUELDO|NOMINA|PAYROLL|SALARY)\b", d):
                m["categoria"] = "sueldo"
    return movimientos


def regla_para(descripcion):
    """Lo estable de una descripción para aprender de una corrección: sin números, fechas ni códigos («UBER *TRIP 8F2K» → «UBER TRIP»)."""
    d = datos.normalizar(descripcion)
    d = re.sub(r"[*#/\\_\-]", " ", d)
    palabras = [p for p in d.split() if not re.search(r"\d", p) and len(p) > 1]
    return " ".join(palabras[:3])


def prompt_ia(movimientos, categorias):
    lista = "\n".join(f"{c['id']}: {c['nombre']} ({c['tipo']})" for c in categorias)
    filas = "\n".join(f"{i}|{m['descripcion'][:80]}|{m['monto']:.0f}" for i, m in enumerate(movimientos))
    return f"""Eres el asistente de una app de finanzas personales. Clasifica cada movimiento bancario en UNA de estas categorías
(usa solo el id de la izquierda):

{lista}

Monto negativo = gasto, positivo = ingreso. Si no sabes, usa «otros» para gastos y «otros_ingresos» para ingresos.
Transferencias entre cuentas propias de la persona van en «transferencia».

Responde SOLO con una línea por movimiento, con el formato número|id_categoria, sin nada más. Ejemplo:
0|supermercado
1|comida

Movimientos (número|descripción|monto):
{filas}
"""


def leer_respuesta(texto, n, ids):
    """{índice: categoría} solo con líneas válidas (número existente y categoría conocida). Lo demás se ignora."""
    r = {}
    for linea in (texto or "").splitlines():
        m = re.fullmatch(r"\s*(\d+)\s*\|\s*([a-z_0-9]+)\s*", linea)
        if m and int(m.group(1)) < n and m.group(2) in ids:
            r[int(m.group(1))] = m.group(2)
    return r


def por_ia(movimientos, categorias, lote=120):
    """Le pide a la IA de la persona las categorías que faltan, de a lotes. Devuelve (cuántos categorizó, error)."""
    faltan = [m for m in movimientos if not m.get("categoria")]
    ids = {c["id"] for c in categorias}
    hechos, error = 0, ""
    for i in range(0, len(faltan), lote):
        parte = faltan[i:i + lote]
        texto, fallo = ia.preguntar(prompt_ia(parte, categorias))
        if fallo:
            error = ia.frase(fallo)
            break
        for j, cat in leer_respuesta(texto, len(parte), ids).items():
            parte[j]["categoria"] = cat
            hechos += 1
    return hechos, error
