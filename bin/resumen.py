"""Cuentas del mes: cuánto se gastó, a qué ritmo y qué categorías se pasan del presupuesto. Solo biblioteca estándar.

La misma lógica existe en ui/app.js (para pintar) y aquí (para los consejos de la IA): las dos se prueban con pruebas/casos.json.

El «mes» puede ser el calendario (por defecto) o el periodo que va de sueldo a sueldo (config `inicio_mes`). Un periodo se llama
«AAAA-MM» por el mes donde cae la mayor parte: si te pagan el 25, «2026-11» va del 25 de octubre al 24 de noviembre; si te pagan
el 5, «2026-10» va del 5 de octubre al 4 de noviembre. `per` = {"modo": "dia" | "sueldo", "dia": 25, "llegadas": ["2026-09-25",
"2026-10-15"]}: `llegadas` son los días en que llegó de verdad el sueldo (lo calcula compromisos.periodo); si uno llegó entre 12 días
antes y 7 después del día de siempre, el periodo parte ese día (si te pagaron el 15 en vez del 25, parte el 15). Sin `per` (o con modo «dia»), todo es por mes calendario. Los archivos de movimientos no cambian.
"""
import calendar
import math
from datetime import date, timedelta
from statistics import median


def dias_del_mes(mes):
    a, m = map(int, mes.split("-"))
    return calendar.monthrange(a, m)[1]


def redondear_arriba(v):
    """Un número fácil de recordar: 243.567 → 250.000 · 18.900 → 19.000 · 840 → 840."""
    if v <= 0:
        return 0
    paso = 10 ** max(0, len(str(int(v))) - 2)
    return int(math.ceil(v / paso) * paso)


# ───────────── Periodos: mes calendario o de sueldo a sueldo (igual que ui/app.js) ─────────────
def _dia_sueldo(per):
    if not per or per.get("modo") != "sueldo":
        return None
    d = per.get("dia")
    return d if isinstance(d, int) and not isinstance(d, bool) and 1 <= d <= 31 else None


def inicio_nominal(mes, per):
    """Dónde parte el periodo `mes` si el sueldo llega el día de siempre (sin mirar cuándo llegó de verdad)."""
    d = _dia_sueldo(per)
    if not d or d == 1:
        return f"{mes}-01"
    base = sumar_mes(mes, -1) if d >= 16 else mes
    return f"{base}-{min(d, dias_del_mes(base)):02d}"


#: Una llegada del sueldo mueve el inicio del periodo si cae entre 12 días antes y 7 después del día de siempre.
LLEGADA_ANTES, LLEGADA_DESPUES = 12, 7


def inicio_periodo(mes, per):
    """Dónde parte el periodo: el día que llegó el sueldo (la llegada más cercana al día de siempre, dentro de la ventana) o el nominal."""
    nominal = inicio_nominal(mes, per)
    if not _dia_sueldo(per):
        return nominal
    mejor = None
    for f in per.get("llegadas") or []:
        d = _dias(nominal, f)
        if -LLEGADA_ANTES <= d <= LLEGADA_DESPUES and (mejor is None or (abs(d), f) < mejor):
            mejor = (abs(d), f)
    return mejor[1] if mejor else nominal


def rango(mes, per=None):
    """(primer día, último día) del periodo `mes`, en «AAAA-MM-DD»."""
    if not _dia_sueldo(per):
        return f"{mes}-01", f"{mes}-{dias_del_mes(mes):02d}"
    inicio = inicio_periodo(mes, per)
    fin = (date.fromisoformat(inicio_periodo(sumar_mes(mes, 1), per)) - timedelta(days=1)).isoformat()
    return inicio, max(inicio, fin)


def periodo_de(fecha, per=None):
    """El periodo («AAAA-MM») donde cae una fecha."""
    m = fecha[:7]
    if not _dia_sueldo(per):
        return m
    for x in (m, sumar_mes(m, 1), sumar_mes(m, -1)):
        a, b = rango(x, per)
        if a <= fecha <= b:
            return x
    return m


def periodos_con_datos(movimientos, per=None, moneda=None):
    """Los periodos que tienen movimientos (de la moneda dada, si se pide), ordenados."""
    fechas = {m["fecha"] for m in movimientos if moneda is None or m.get("moneda", moneda) == moneda}
    return sorted({periodo_de(f, per) for f in fechas})


def _dias(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


# ───────────── Cómo se pagó: compras en cuotas con crédito (igual que ui/app.js) ─────────────
def _entero_texto(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0
    return int(f) if f == int(f) else 0


def cuotas_de(m):
    """En cuántas cuotas se compró (solo compras con crédito en 2 o más cuotas; si no, 0)."""
    n = _entero_texto(m.get("cuotas"))
    return n if m.get("medio") == "credito" and 2 <= n <= 72 and m["monto"] < 0 else 0


def valor_cuota(m):
    """Cuánto es cada cuota: la que informó el servicio (con intereses) o, si no la dijo, el monto dividido en las cuotas."""
    try:
        c = float(m.get("cuota") or 0)
    except (TypeError, ValueError):
        c = 0
    return c if c > 0 else abs(m["monto"]) / cuotas_de(m)


def fecha_mas_meses(fecha, n):
    """«2026-01-31» + 1 mes → «2026-02-28» (si el mes es más corto, el último día)."""
    mes = sumar_mes(fecha[:7], n)
    return f"{mes}-{min(int(fecha[8:10]), dias_del_mes(mes)):02d}"


def cargos(m):
    """Lo que una compra le carga a tu bolsillo, con su fecha: la compra en cuotas con crédito es una cuota cada mes (la primera el
    día de la compra); todo lo demás, el movimiento tal cual. [(fecha, monto negativo, número de cuota, total de cuotas)]."""
    n = cuotas_de(m)
    if not n:
        return [(m["fecha"], m["monto"], 0, 0)]
    c = valor_cuota(m)
    return [(fecha_mas_meses(m["fecha"], k), -c, k + 1, n) for k in range(n)]


def resumen(movimientos, mes, hoy, presupuesto, categorias, per=None):
    """`hoy` en «AAAA-MM-DD». Solo cuenta la moneda del presupuesto; las transferencias entre cuentas propias no cuentan.
    `mes` es el periodo (ver `rango`): `dia` y `dias_mes` son el día del periodo y cuántos días tiene.
    «Lo que gastaste»: una compra en cuotas con crédito cuenta por la cuota de cada mes, y una devolución (un monto positivo con
    categoría de gasto) descuenta de esa categoría en vez de contar como ingreso."""
    neutras = {c["id"] for c in categorias if c.get("tipo") == "neutro"}
    de_gasto = {c["id"] for c in categorias if c.get("tipo") == "gasto"}
    fijas = {c["id"] for c in categorias if c.get("fijo")}
    moneda = presupuesto.get("moneda", "CLP")
    inicio, fin = rango(mes, per)
    del_mes = []
    for m in movimientos:
        if m.get("categoria") in neutras:
            continue
        for f, monto, _, _ in cargos(m):
            if inicio <= f <= fin:
                del_mes.append({**m, "fecha": f, "monto": monto})
    otras = sum(1 for m in del_mes if m.get("moneda", moneda) != moneda)
    del_mes = [m for m in del_mes if m.get("moneda", moneda) == moneda]
    por_cat, cuantos, devuelto = {}, {}, {}
    for m in del_mes:
        c = m.get("categoria") or ""
        if m["monto"] < 0:
            por_cat[c] = por_cat.get(c, 0) + -m["monto"]
            cuantos[c] = cuantos.get(c, 0) + 1
        elif m["monto"] > 0 and c in de_gasto:
            devuelto[c] = devuelto.get(c, 0) + m["monto"]
    for c, v in devuelto.items():  # lo devuelto descuenta, sin dejar la categoría bajo cero
        por_cat[c] = max(0, por_cat.get(c, 0) - v)
        if not por_cat[c] and not cuantos.get(c):
            del por_cat[c]
    gastado = sum(por_cat.values())
    ingresos = sum(m["monto"] for m in del_mes if m["monto"] > 0 and m.get("categoria") not in de_gasto)
    total_dias = _dias(inicio, fin) + 1
    if hoy < inicio:
        dia = 0
    elif hoy > fin:
        dia = total_dias
    else:
        dia = _dias(inicio, hoy) + 1
    en_curso = 0 < dia < total_dias
    # Proyección: lo variable (3 o más gastos en el mes) sigue al mismo ritmo; lo fijo (arriendo, cuentas) y lo esporádico queda como está.
    ritmo = lambda c, g: g / dia * total_dias if c not in fijas and cuantos.get(c, 0) >= 3 else g
    proyectar = en_curso and dia >= 3
    proyeccion = round(sum(ritmo(c, g) for c, g in por_cat.items())) if proyectar else None
    limite = sum(v for v in presupuesto.get("mensual", {}).values() if v > 0)
    alertas = []
    for c, tope in presupuesto.get("mensual", {}).items():
        if tope <= 0:
            continue
        g = por_cat.get(c, 0)
        if g > tope:
            alertas.append({"categoria": c, "tipo": "pasado", "gastado": round(g), "tope": tope})
        elif en_curso and dia >= 5 and c not in fijas and cuantos.get(c, 0) >= 3 and g / dia * total_dias > tope * 1.1:
            alertas.append({"categoria": c, "tipo": "ritmo", "gastado": round(g), "tope": tope, "proyeccion": round(g / dia * total_dias)})
    return {"mes": mes, "moneda": moneda, "gastado": round(gastado), "ingresos": round(ingresos), "presupuesto": limite,
            "por_categoria": {k: round(v) for k, v in sorted(por_cat.items(), key=lambda x: -x[1])}, "dia": dia,
            "dias_mes": total_dias, "desde": inicio, "hasta": fin, "proyeccion": proyeccion,
            # Redondeo «desde ,5 hacia arriba» (como Math.round en JavaScript): así las dos versiones dan lo mismo.
            "proyeccion_por_categoria": {c: math.floor(ritmo(c, g) + 0.5) for c, g in por_cat.items()} if proyectar else {},
            "alertas": alertas, "otras_monedas": otras, "sin_categoria": cuantos.get("", 0)}


def sumar_mes(mes, n):
    """«2026-01» + -2 → «2025-11»."""
    a, m = map(int, mes.split("-"))
    total = a * 12 + (m - 1) + n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def historia(movimientos, mes, hoy, presupuesto, categorias, categoria=None, n=6, per=None):
    """Los `n` meses que terminan en `mes`, con las mismas reglas que `resumen` (sin neutras, solo la moneda del presupuesto).

    Con `categoria`, la historia de esa categoría y su tope; sin ella, el gasto total y el presupuesto total. El mes en curso trae
    su proyección (si ya se puede calcular). `promedio` es el de los meses anteriores que tienen movimientos (sin el mes elegido).
    """
    moneda = presupuesto.get("moneda", "CLP")
    con_datos = set(periodos_con_datos(movimientos, per, moneda))
    meses, tope = [], 0
    for i in range(n - 1, -1, -1):
        x = sumar_mes(mes, -i)
        r = resumen(movimientos, x, hoy, presupuesto, categorias, per)
        en_curso = 0 < r["dia"] < r["dias_mes"]
        if categoria is None:
            gastado, proyeccion, tope = r["gastado"], r["proyeccion"], r["presupuesto"]
        else:
            gastado = r["por_categoria"].get(categoria, 0)
            proyeccion = r["proyeccion_por_categoria"].get(categoria, 0) if r["proyeccion"] is not None else None
            t = presupuesto.get("mensual", {}).get(categoria, 0)
            tope = t if t > 0 else 0
        meses.append({"mes": x, "gastado": gastado, "proyeccion": proyeccion if en_curso else None, "en_curso": en_curso,
                      "con_datos": x in con_datos})
    anteriores = [m["gastado"] for m in meses[:-1] if m["con_datos"]]
    # Redondeo «hacia arriba desde ,5» (como Math.round en JavaScript), no el de banquero de Python.
    promedio = math.floor(sum(anteriores) / len(anteriores) + 0.5) if anteriores else None
    return {"categoria": categoria or "", "moneda": presupuesto.get("moneda", "CLP"), "tope": tope, "promedio": promedio,
            "meses": meses}


def presupuesto_sugerido(movimientos, meses_completos, categorias, moneda="CLP", per=None):
    """Para cada categoría de gasto: la mediana de lo gastado en los meses (periodos) completos, redondeada hacia arriba."""
    ids = [c["id"] for c in categorias if c.get("tipo") == "gasto"]
    rangos = [rango(mes, per) for mes in meses_completos]
    r = {}
    for c in ids:
        valores = []
        for a, b in rangos:
            valores.append(sum(-m["monto"] for m in movimientos if a <= m["fecha"] <= b and m.get("categoria") == c
                               and m["monto"] < 0 and m.get("moneda", moneda) == moneda))
        if valores and median(valores) > 0:
            r[c] = redondear_arriba(median(valores))
    return r


# ───────────── Lo que tienes: el saldo de tus cuentas hoy (igual que ui/app.js) ─────────────
def _saldo_base(c):
    s = c.get("saldo") if isinstance(c, dict) else None
    if not isinstance(s, dict) or isinstance(s.get("monto"), bool) or not isinstance(s.get("monto"), (int, float)):
        return None
    f = str(s.get("fecha") or "")
    if len(f) != 10 or f[4] != "-" or f[7] != "-":
        return None
    return {"monto": s["monto"], "fecha": f, "origen": s.get("origen") if s.get("origen") in ("persona", "cartola", "conector") else "persona"}


def lo_que_tienes(cuentas, movimientos, moneda):
    """El saldo de cada cuenta: el último que se conoce (el que informa el servicio conectado, el de la última fila de una cartola
    con columna de saldo o el que anotó la persona) más los movimientos de los días siguientes. Las compras con crédito no salen de
    la cuenta (van a la tarjeta), así que no la mueven. `total` suma solo las cuentas con saldo en `moneda` (None si ninguna tiene)."""
    lista, vistas = [], set()
    for c in cuentas:
        if isinstance(c, dict) and c.get("id") and c["id"] not in vistas:
            vistas.add(c["id"])
            lista.append(c)
    for m in movimientos:  # cuentas que solo aparecen en los movimientos (p. ej. un archivo editado a mano)
        if m.get("cuenta") and m["cuenta"] not in vistas:
            vistas.add(m["cuenta"])
            lista.append({"id": m["cuenta"], "nombre": m["cuenta"]})
    r, total, con = [], 0, 0
    for c in lista:
        mon = c.get("moneda") or moneda
        base = _saldo_base(c)
        saldo, despues = None, 0
        if base:
            mios = [m for m in movimientos if m.get("cuenta") == c["id"] and m["fecha"] > base["fecha"]
                    and m.get("medio") != "credito" and (m.get("moneda") or mon) == mon]
            despues = len(mios)
            saldo = round(base["monto"] + sum(m["monto"] for m in mios), 2)
            saldo = int(saldo) if saldo == int(saldo) else saldo
            if mon == moneda:
                total += saldo
                con += 1
        r.append({"id": c["id"], "nombre": c.get("nombre") or c["id"], "moneda": mon, "saldo": saldo, "base": base,
                  "movimientos_despues": despues})
    total = round(total, 2)
    return {"moneda": moneda, "total": (int(total) if total == int(total) else total) if con else None, "con_saldo": con,
            "sin_saldo": sum(1 for x in r if x["saldo"] is None and x["moneda"] == moneda), "cuentas": r}
