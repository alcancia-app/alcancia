"""Cuentas del mes: cuánto se gastó, a qué ritmo y qué categorías se pasan del presupuesto. Solo biblioteca estándar.

La misma lógica existe en ui/app.js (para pintar) y aquí (para los consejos de la IA): las dos se prueban con pruebas/casos.json.
"""
import calendar
import math
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


def resumen(movimientos, mes, hoy, presupuesto, categorias):
    """`hoy` en «AAAA-MM-DD». Solo cuenta la moneda del presupuesto; las transferencias entre cuentas propias no cuentan."""
    neutras = {c["id"] for c in categorias if c.get("tipo") == "neutro"}
    fijas = {c["id"] for c in categorias if c.get("fijo")}
    moneda = presupuesto.get("moneda", "CLP")
    del_mes = [m for m in movimientos if m["fecha"].startswith(mes) and m.get("categoria") not in neutras]
    otras = sum(1 for m in del_mes if m.get("moneda", moneda) != moneda)
    del_mes = [m for m in del_mes if m.get("moneda", moneda) == moneda]
    gastos = [m for m in del_mes if m["monto"] < 0]
    por_cat, cuantos = {}, {}
    for m in gastos:
        c = m.get("categoria") or ""
        por_cat[c] = por_cat.get(c, 0) + -m["monto"]
        cuantos[c] = cuantos.get(c, 0) + 1
    gastado = sum(por_cat.values())
    ingresos = sum(m["monto"] for m in del_mes if m["monto"] > 0)
    total_dias = dias_del_mes(mes)
    if hoy[:7] == mes:
        dia = int(hoy[8:10])
    elif hoy[:7] > mes:
        dia = total_dias
    else:
        dia = 0
    en_curso = 0 < dia < total_dias
    # Proyección: lo variable (3 o más gastos en el mes) sigue al mismo ritmo; lo fijo (arriendo, cuentas) y lo esporádico queda como está.
    ritmo = lambda c, g: g / dia * total_dias if c not in fijas and cuantos.get(c, 0) >= 3 else g
    proyeccion = round(sum(ritmo(c, g) for c, g in por_cat.items())) if en_curso and dia >= 3 else None
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
            "dias_mes": total_dias, "proyeccion": proyeccion, "alertas": alertas, "otras_monedas": otras,
            "sin_categoria": cuantos.get("", 0)}


def presupuesto_sugerido(movimientos, meses_completos, categorias, moneda="CLP"):
    """Para cada categoría de gasto: la mediana de lo gastado en los meses completos, redondeada hacia arriba."""
    ids = [c["id"] for c in categorias if c.get("tipo") == "gasto"]
    r = {}
    for c in ids:
        valores = []
        for mes in meses_completos:
            valores.append(sum(-m["monto"] for m in movimientos if m["fecha"].startswith(mes) and m.get("categoria") == c
                               and m["monto"] < 0 and m.get("moneda", moneda) == moneda))
        if valores and median(valores) > 0:
            r[c] = redondear_arriba(median(valores))
    return r
