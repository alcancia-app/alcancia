"""Los datos de Alcancía en disco: formato abierto y documentado (ver README, "Formato de los datos"). Solo biblioteca estándar.

~/Alcancia/
  movimientos/AAAA-MM.csv   un archivo por mes; columnas CAMPOS; monto negativo = gasto, positivo = ingreso
  categorias.json           [{"id", "nombre", "emoji", "tipo": "gasto"|"ingreso"|"neutro", "fijo": bool}]  fijo = se paga una vez al mes
  presupuesto.json          {"moneda": "CLP", "mensual": {"supermercado": 250000, ...}}
  reglas.json               [{"contiene": "TEXTO", "categoria": "id"}]   lo que la app aprende al corregir
  cuentas.json              [{"id", "nombre", "receta", "moneda"}]
  consejos/AAAA-MM-DD.md    los consejos de tu IA
  .alcancia/config.json     ajustes de la app
  .alcancia/recetas/        recetas descargadas o creadas (ganan sobre las incluidas)

La carpeta ~/Alcancia no distingue mayúsculas de ~/alcancia: el código de desarrollo va en ~/Developer/alcancia.
"""
import csv
import hashlib
import json
import os
import re
import tempfile
import unicodedata

BASE = os.environ.get("ALCANCIA_CARPETA") or os.path.join(os.path.expanduser("~"), "Alcancia")
INTERNO = os.path.join(BASE, ".alcancia")
MOVIMIENTOS = os.path.join(BASE, "movimientos")
CONSEJOS = os.path.join(BASE, "consejos")
RECURSOS = os.environ.get("ALCANCIA_RECURSOS") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CAMPOS = ["id", "fecha", "descripcion", "monto", "moneda", "categoria", "cuenta", "origen", "nota"]

#: Categorías con que parte todo el mundo. La persona puede renombrarlas, borrarlas o agregar las suyas.
CATEGORIAS_BASE = [
    {"id": "supermercado", "nombre": "Supermercado", "emoji": "🛒", "tipo": "gasto"},
    {"id": "comida", "nombre": "Comida fuera y delivery", "emoji": "🍔", "tipo": "gasto"},
    {"id": "transporte", "nombre": "Transporte", "emoji": "🚌", "tipo": "gasto"},
    {"id": "auto", "nombre": "Auto y bencina", "emoji": "⛽", "tipo": "gasto"},
    {"id": "casa", "nombre": "Casa", "emoji": "🏠", "tipo": "gasto", "fijo": True},
    {"id": "cuentas", "nombre": "Cuentas básicas", "emoji": "💡", "tipo": "gasto", "fijo": True},
    {"id": "salud", "nombre": "Salud", "emoji": "💊", "tipo": "gasto"},
    {"id": "educacion", "nombre": "Educación", "emoji": "📚", "tipo": "gasto", "fijo": True},
    {"id": "suscripciones", "nombre": "Suscripciones", "emoji": "📺", "tipo": "gasto", "fijo": True},
    {"id": "compras", "nombre": "Compras", "emoji": "🛍️", "tipo": "gasto"},
    {"id": "ocio", "nombre": "Panoramas", "emoji": "🎉", "tipo": "gasto"},
    {"id": "mascotas", "nombre": "Mascotas", "emoji": "🐾", "tipo": "gasto"},
    {"id": "otros", "nombre": "Otros gastos", "emoji": "📦", "tipo": "gasto"},
    {"id": "sueldo", "nombre": "Sueldo", "emoji": "💼", "tipo": "ingreso"},
    {"id": "otros_ingresos", "nombre": "Otros ingresos", "emoji": "💰", "tipo": "ingreso"},
    {"id": "transferencia", "nombre": "Entre mis cuentas", "emoji": "🔁", "tipo": "neutro"},
]


# ───────────── JSON y escritura segura ─────────────
def leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def escribir_atomico(ruta, texto):
    """Escribe en un temporal y lo renombra: si algo se corta a la mitad, el archivo anterior queda intacto."""
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ruta), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(texto)
    os.replace(tmp, ruta)


def escribir_json(ruta, valor):
    escribir_atomico(ruta, json.dumps(valor, ensure_ascii=False, indent=2) + "\n")


def config():
    return {"ia": "claude", "idioma_ui": "", "pais": "CL", "moneda": "CLP", **leer_json(os.path.join(INTERNO, "config.json"), {})}


#: Nombres de las categorías base en inglés (las de la persona se guardan en su idioma y ella las puede renombrar).
NOMBRES_EN = {"supermercado": "Groceries", "comida": "Eating out & delivery", "transporte": "Transport", "auto": "Car & fuel",
              "casa": "Home", "cuentas": "Utilities", "salud": "Health", "educacion": "Education", "suscripciones": "Subscriptions",
              "compras": "Shopping", "ocio": "Fun", "mascotas": "Pets", "otros": "Other expenses", "sueldo": "Salary",
              "otros_ingresos": "Other income", "transferencia": "Between my accounts"}


def categorias():
    """Las de la persona (categorias.json) o, si aún no existen, las base en el idioma de la app."""
    propias = leer_json(os.path.join(BASE, "categorias.json"), None)
    if propias:
        return propias
    idioma = config().get("idioma_ui") or ""
    if idioma == "en":
        return [{**c, "nombre": NOMBRES_EN.get(c["id"], c["nombre"])} for c in CATEGORIAS_BASE]
    return CATEGORIAS_BASE


def reglas():
    return leer_json(os.path.join(BASE, "reglas.json"), [])


def presupuesto():
    return leer_json(os.path.join(BASE, "presupuesto.json"), {"moneda": config()["moneda"], "mensual": {}})


# ───────────── Movimientos ─────────────
def normalizar(texto):
    """Mayúsculas, sin tildes y con espacios simples: para comparar descripciones sin que importe cómo vienen escritas."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def nuevo_id(cuenta, fecha, descripcion, monto, ocurrencia=0):
    """Mismo movimiento = mismo id, así importar dos veces la misma cartola no duplica nada.
    `ocurrencia` distingue dos compras idénticas el mismo día (dos cafés iguales)."""
    base = f"{cuenta}|{fecha}|{normalizar(descripcion)}|{float(monto):.2f}|{ocurrencia}"
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def ruta_mes(mes):
    if not re.fullmatch(r"\d{4}-\d{2}", mes or ""):
        raise ValueError(f"Mes inválido: {mes!r}")
    return os.path.join(MOVIMIENTOS, f"{mes}.csv")


def meses():
    try:
        return sorted((f[:7] for f in os.listdir(MOVIMIENTOS) if re.fullmatch(r"\d{4}-\d{2}\.csv", f)), reverse=True)
    except OSError:
        return []


def leer_mes(mes):
    try:
        with open(ruta_mes(mes), encoding="utf-8", newline="") as f:
            filas = list(csv.DictReader(f))
    except OSError:
        return []
    for m in filas:
        try:
            m["monto"] = float(m.get("monto") or 0)
        except ValueError:
            m["monto"] = 0.0
        for c in CAMPOS:
            m.setdefault(c, "")
    return filas


def leer_todos():
    return [m for mes in meses() for m in leer_mes(mes)]


def _monto_texto(v):
    v = float(v)
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def escribir_mes(mes, movimientos):
    filas = sorted(movimientos, key=lambda m: (m["fecha"], m["id"]))
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CAMPOS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for m in filas:
        w.writerow({**{c: m.get(c, "") for c in CAMPOS}, "monto": _monto_texto(m["monto"])})
    escribir_atomico(ruta_mes(mes), buf.getvalue())


def agregar(movimientos):
    """Guarda movimientos nuevos (los que ya estaban, por id, no se tocan). Devuelve (nuevos, repetidos)."""
    por_mes = {}
    for m in movimientos:
        por_mes.setdefault(m["fecha"][:7], []).append(m)
    nuevos = repetidos = 0
    for mes, lista in por_mes.items():
        actuales = leer_mes(mes)
        ids = {m["id"] for m in actuales}
        agregar_ = [m for m in lista if m["id"] not in ids]
        repetidos += len(lista) - len(agregar_)
        if agregar_:
            escribir_mes(mes, actuales + agregar_)
            nuevos += len(agregar_)
    return nuevos, repetidos


def cambiar(mes, id_, cambios):
    """Cambia campos de un movimiento (categoría o nota). Solo esos dos: el resto viene del banco."""
    lista = leer_mes(mes)
    for m in lista:
        if m["id"] == id_:
            m.update({k: v for k, v in cambios.items() if k in ("categoria", "nota")})
            escribir_mes(mes, lista)
            return True
    return False
