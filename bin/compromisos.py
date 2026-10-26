"""Compromisos: lo que se paga (o se recibe) seguido — arriendo, créditos, cuentas, suscripciones, transferencias, sueldo.
Solo biblioteca estándar.

~/Alcancia/compromisos.json (formato abierto, ver README «Formato de los datos»):
  {"formato": 1, "compromisos": [{...}], "descartados": ["CLAVE", ...]}

Reconocer el pago, el estado del mes, el avance de las deudas y el gasto máximo sugerido viven igual en ui/app.js
(`vencimientos`, `coincide`, `asignar`, `estadoCompromisos`, `gastoMaximo`) y se prueban juntos con pruebas/casos.json.
Si cambias una regla, cambia los dos lados y el caso. Validar y sugerir (detectar en la cartola) solo viven aquí.

  compromisos.py avisos <hoy AAAA-MM-DD> <salida.json>   lo que hay que avisar hoy (la app de Mac manda el aviso del sistema)
"""
import json
import math
import os
import re
import sys
import uuid
from datetime import date
from statistics import median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import categorizar  # noqa: E402
import datos  # noqa: E402
from resumen import dias_del_mes, periodo_de, periodos_con_datos, rango, redondear_arriba, sumar_mes  # noqa: E402

RUTA = os.path.join(datos.BASE, "compromisos.json")
RUTA_AVISOS = os.path.join(datos.INTERNO, "avisos.json")
CONOCIDOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compromisos_conocidos.json")

TIPOS = ("deuda", "cuenta", "suscripcion", "transferencia", "ingreso", "otro")
FRECUENCIAS = ("mensual", "semanal", "anual", "una_vez")
ORIGENES = ("manual", "detectado", "ia")
#: Un pago se reconoce entre 10 días antes y 7 después del vencimiento, con el monto dentro de ±5 % (configurable).
ANTES, DESPUES, TOLERANCIA = 10, 7, 5
#: Lo que puede venir de la IA (cualquier otro campo hace que la respuesta no sirva).
CAMPOS_IA = {"nombre", "tipo", "signo", "monto", "moneda", "frecuencia", "dia", "fecha", "categoria", "buscar", "cuotas_total",
             "cuotas_pagadas", "cuotas_restantes", "fecha_fin", "saldo"}
CAMPOS = CAMPOS_IA | {"id", "tolerancia", "activo", "desde", "origen", "pagos"}
ID_MOV = re.compile(r"[A-Za-z0-9_\-]{1,64}")
PERIODO = re.compile(r"\d{4}(-\d{2}(-\d{2})?)?")


# ───────────── Fechas (días como número: así se suma y resta igual en Python y en JavaScript) ─────────────
def _num(f):
    return date.fromisoformat(f).toordinal()


def _fecha(n):
    return date.fromordinal(n).isoformat()


def _fecha_valida(f):
    try:
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(f))) and bool(date.fromisoformat(f))
    except ValueError:
        return False


def redondear(v):
    """«Desde ,5 hacia arriba» (como Math.round en JavaScript)."""
    return math.floor(v + 0.5)


def redondear_abajo(v):
    """Como resumen.redondear_arriba, pero hacia abajo (para no pasarse de lo disponible): 243.567 → 240.000."""
    if v <= 0:
        return 0
    paso = 10 ** max(0, len(str(int(v))) - 2)
    return int(math.floor(v / paso) * paso)


# ───────────── Validar (todo lo que llega: la interfaz, la IA o el archivo editado a mano) ─────────────
def limpiar_nombre(t):
    """Sin caracteres de control ni secuencias de 6 o más dígitos (un número de cuenta nunca se guarda), máximo 60 caracteres."""
    t = re.sub(r"[\x00-\x1f\x7f]", " ", str(t or ""))
    t = re.sub(r"\d(?:[\s.\-/]?\d){5,}", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:60].strip()


def limpiar_clave(t):
    """Una palabra o clave para buscar en la cartola: sin tildes ni mayúsculas y sin secuencias de 6 o más dígitos."""
    return datos.normalizar(re.sub(r"\d(?:[\s.\-/]?\d){5,}", " ", str(t or "")))


def limpiar_buscar(lista):
    if isinstance(lista, str):
        lista = lista.split(",")
    r = []
    for p in lista if isinstance(lista, list) else []:
        p = limpiar_clave(p)
        if 2 <= len(p) <= 40 and p not in r:
            r.append(p)
    return r[:6]


def _entero(v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v) or not lo <= v <= hi:
        return None
    return int(v)


def _numero(v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo < v < hi:
        return None
    v = round(float(v), 2)
    return int(v) if v == int(v) else v


def nuevo_id():
    return "c-" + uuid.uuid4().hex[:10]


def _pagos(p):
    r = {}
    if not isinstance(p, dict):
        return r
    for per, e in list(p.items())[:600]:
        if not PERIODO.fullmatch(str(per)) or not isinstance(e, dict):
            continue
        x = {}
        if e.get("como") in ("automatico", "manual"):
            x["como"] = e["como"]
            if _fecha_valida(e.get("fecha")):
                x["fecha"] = e["fecha"]
            if e["como"] == "automatico" and ID_MOV.fullmatch(str(e.get("movimiento") or "")):
                x["movimiento"] = e["movimiento"]
            if _numero(e.get("monto"), 0, 1e12) is not None:
                x["monto"] = _numero(e.get("monto"), 0, 1e12)
        no_es = [str(i) for i in (e.get("no_es") or []) if ID_MOV.fullmatch(str(i))][:20] if isinstance(e.get("no_es"), list) else []
        if no_es:
            x["no_es"] = no_es
        if x:
            r[str(per)] = x
    return r


def validar(c, ids_categorias, hoy, moneda="CLP", estricto=False):
    """(compromiso limpio, []) o (None, [problemas]). `estricto`: lo que propone la IA (solo CAMPOS_IA, sin ids ni pagos).
    `ids_categorias` None = no revisar la categoría (al leer el archivo)."""
    if not isinstance(c, dict):
        return None, ["No es un compromiso."]
    errores = []
    raros = sorted(set(c) - (CAMPOS_IA if estricto else CAMPOS))
    if raros:
        errores.append("Campos desconocidos: " + ", ".join(raros[:5]) + ".")
    r = {"id": c["id"] if not estricto and re.fullmatch(r"c-[a-z0-9]{6,24}", str(c.get("id") or "")) else nuevo_id()}
    r["nombre"] = limpiar_nombre(c.get("nombre"))
    if not r["nombre"]:
        errores.append("Falta el nombre.")
    r["tipo"] = c.get("tipo") or "otro"
    if r["tipo"] not in TIPOS:
        errores.append("El tipo no es válido.")
    r["signo"] = c.get("signo") or ("ingreso" if r["tipo"] == "ingreso" else "gasto")
    if r["signo"] not in ("gasto", "ingreso"):
        errores.append("El signo no es válido.")
    r["monto"] = _numero(c.get("monto"), 0, 1e12)
    if r["monto"] is None:
        errores.append("El monto tiene que ser un número mayor que cero.")
    r["moneda"] = c.get("moneda") or moneda
    if not re.fullmatch(r"[A-Z]{3}", str(r["moneda"])):
        errores.append("La moneda no es válida.")
    r["frecuencia"] = c.get("frecuencia") or "mensual"
    if r["frecuencia"] not in FRECUENCIAS:
        errores.append("La frecuencia no es válida.")
    elif r["frecuencia"] in ("mensual", "semanal"):
        r["dia"] = _entero(c.get("dia"), 1, 31 if r["frecuencia"] == "mensual" else 7)
        if r["dia"] is None:
            errores.append("Falta el día (1 a 31 en mensual; 1 = lunes a 7 = domingo en semanal).")
    elif not _fecha_valida(c.get("fecha")):
        errores.append("Falta la fecha (AAAA-MM-DD).")
    else:
        r["fecha"] = c["fecha"]
    r["categoria"] = str(c.get("categoria") or "")
    if r["categoria"] and ids_categorias is not None and r["categoria"] not in ids_categorias:
        errores.append("Esa categoría no existe.")
    r["buscar"] = limpiar_buscar(c.get("buscar"))
    t = _numero(c.get("tolerancia", TOLERANCIA), -1, 50.01)
    r["tolerancia"] = TOLERANCIA if t is None or t < 0 else t
    # Cuotas: total y pagadas (o restantes, que se convierten). Todo opcional.
    total, pagadas, restantes = (_entero(c.get(k), 0, 1200) if c.get(k) is not None else None
                                 for k in ("cuotas_total", "cuotas_pagadas", "cuotas_restantes"))
    for k, v in (("cuotas_total", total), ("cuotas_pagadas", pagadas), ("cuotas_restantes", restantes)):
        if c.get(k) is not None and v is None:
            errores.append(f"{k} tiene que ser un número entero.")
    if restantes is not None:
        if total is None:
            total = (pagadas or 0) + restantes
        else:
            pagadas = max(0, total - restantes)
    if total:
        r["cuotas_total"] = total
        r["cuotas_pagadas"] = min(pagadas or 0, total)
    if c.get("fecha_fin") is not None:
        if _fecha_valida(c.get("fecha_fin")):
            r["fecha_fin"] = c["fecha_fin"]
        else:
            errores.append("La fecha de término no es válida.")
    if c.get("saldo") is not None:
        r["saldo"] = _numero(c.get("saldo"), 0, 1e13)
        if r["saldo"] is None:
            errores.append("El saldo tiene que ser un número mayor que cero.")
            del r["saldo"]
    r["activo"] = c.get("activo", True) is not False
    r["desde"] = c["desde"] if _fecha_valida(c.get("desde")) else hoy
    if r.get("fecha") and r["frecuencia"] == "una_vez" and r["fecha"] < r["desde"]:
        r["desde"] = r["fecha"]
    r["origen"] = c.get("origen") if c.get("origen") in ORIGENES else "manual"
    r["pagos"] = {} if estricto else _pagos(c.get("pagos"))
    return (None, errores) if errores else (r, [])


# ───────────── Archivo ─────────────
def leer():
    """El archivo tal cual (para escribirlo sin perder lo que la persona editó a mano)."""
    raw = datos.leer_json(RUTA, {})
    if not isinstance(raw, dict):
        raw = {}
    lista = raw.get("compromisos") if isinstance(raw.get("compromisos"), list) else []
    desc = [d for d in raw.get("descartados") or [] if isinstance(d, str)] if isinstance(raw.get("descartados"), list) else []
    return {**raw, "formato": 1, "compromisos": lista, "descartados": desc}


def escribir(raw):
    datos.escribir_json(RUTA, {"formato": 1, "compromisos": raw["compromisos"], "descartados": raw.get("descartados", [])})


def validos(raw=None, hoy=None, moneda=None):
    """Los compromisos que se pueden usar (uno roto a mano se salta, no rompe la app)."""
    raw = raw or leer()
    hoy = hoy or date.today().isoformat()
    moneda = moneda or datos.config()["moneda"]
    r = []
    for c in raw["compromisos"]:
        limpio, errores = validar(c, None, hoy, moneda)
        if limpio and not errores and not any(x["id"] == limpio["id"] for x in r):
            r.append(limpio)
    return r


# ───────────── Vencimientos y reconocer el pago (igual que ui/app.js) ─────────────
def _fechas(c, inicio, fin):
    """(periodo, vencimiento) entre los días `inicio` y `fin` (números), en orden."""
    f = c["frecuencia"]
    if f == "mensual":
        a, m = map(int, _fecha(inicio)[:7].split("-"))
        while True:
            mes = f"{a:04d}-{m:02d}"
            v = f"{mes}-{min(c['dia'], dias_del_mes(mes)):02d}"
            if _num(v) > fin:
                return
            if _num(v) >= inicio:
                yield mes, v
            a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    elif f == "semanal":
        primero = inicio + (c["dia"] - date.fromordinal(inicio).isoweekday()) % 7
        for n in range(primero, fin + 1, 7):
            yield _fecha(n), _fecha(n)
    elif f == "anual":
        for a in range(date.fromordinal(inicio).year, date.fromordinal(fin).year + 1):
            mes = f"{a:04d}-{c['fecha'][5:7]}"
            v = f"{mes}-{min(int(c['fecha'][8:10]), dias_del_mes(mes)):02d}"
            if inicio <= _num(v) <= fin:
                yield str(a), v
    elif inicio <= _num(c["fecha"]) <= fin:
        yield c["fecha"], c["fecha"]


def vencimientos(c, hasta):
    """Vencimientos desde un mes antes de `desde` (por si ya estaba pagado al agregarlo) hasta `hasta`, sin pasar de
    `fecha_fin` ni de las cuotas que faltan. `n` = número de vencimiento desde `desde` (0 = anterior a `desde`)."""
    fin = _num(hasta)
    if c.get("fecha_fin"):
        fin = min(fin, _num(c["fecha_fin"]))
    maximo = c["cuotas_total"] - c.get("cuotas_pagadas", 0) if c.get("cuotas_total") else None
    r, n = [], 0
    for periodo, v in _fechas(c, _num(c["desde"]) - 31, fin):
        if v >= c["desde"]:
            if maximo is not None and n >= maximo:
                break
            n += 1
        r.append({"periodo": periodo, "vence": v, "n": n if v >= c["desde"] else 0})
    return r


def coincide(m, c, moneda):
    """¿Este movimiento puede ser un pago de este compromiso? Signo, moneda, monto (±tolerancia) y alguna palabra de `buscar`
    (sin tildes ni mayúsculas); sin palabras, el monto exacto. No mira la fecha."""
    monto = m["monto"]
    if monto == 0 or (monto < 0) != (c["signo"] == "gasto") or (m.get("moneda") or moneda) != c["moneda"]:
        return False
    dif = abs(abs(monto) - c["monto"])
    palabras = [datos.normalizar(p) for p in c.get("buscar") or [] if datos.normalizar(p)]
    if not palabras:
        return dif < 0.005
    if dif > c["monto"] * c.get("tolerancia", TOLERANCIA) / 100 + 1e-9:
        return False
    d = datos.normalizar(m.get("descripcion"))
    return any(p in d for p in palabras)


def _pago(m):
    return {"como": "automatico", "fecha": m["fecha"], "monto": abs(m["monto"]), "movimiento": m["id"], "descripcion": m["descripcion"]}


def asignar(compromisos, movimientos, hasta, moneda):
    """Para cada vencimiento hasta `hasta`, el pago que le corresponde. Lo marcado a mano manda; después, por orden de
    las parejas que calzan mejor (más cerca de la fecha, luego del monto). Un movimiento cuenta para un solo compromiso.
    Devuelve (vencimientos [(compromiso, v)], {"id|periodo": pago}, ids usados)."""
    ocs = [(c, o) for c in compromisos for o in vencimientos(c, hasta)]
    por_id = {m["id"]: m for m in movimientos}
    pagos, usados, pendientes = {}, set(), []
    for c, o in ocs:
        e = (c.get("pagos") or {}).get(o["periodo"]) or {}
        clave = f"{c['id']}|{o['periodo']}"
        if e.get("como") == "manual":
            pagos[clave] = {"como": "manual", "fecha": e.get("fecha") or o["vence"], "monto": c["monto"]}
        elif e.get("como") == "automatico" and e.get("movimiento") in por_id and e["movimiento"] not in usados:
            usados.add(e["movimiento"])
            pagos[clave] = _pago(por_id[e["movimiento"]])
        else:
            pendientes.append((c, o, set(e.get("no_es") or [])))
    # Todas las parejas posibles (vencimiento, movimiento) y se toman de la mejor a la peor: la más cerca de la fecha, luego del
    # monto, y los vencimientos desde `desde` antes que los anteriores. Así un vencimiento no le quita el pago justo a otro.
    candidatos, pares = {}, []
    for c, o, no_es in pendientes:
        if c["id"] not in candidatos:
            candidatos[c["id"]] = [(_num(m["fecha"]), m) for m in movimientos if coincide(m, c, moneda)]
        v = _num(o["vence"])
        for n, m in candidatos[c["id"]]:
            # Un vencimiento anterior a `desde` solo se da por pagado con algo de antes de `desde` (ya estaba pagado al agregarlo).
            if v - ANTES <= n <= v + DESPUES and m["id"] not in usados and m["id"] not in no_es and (o["vence"] >= c["desde"] or m["fecha"] < c["desde"]):
                pares.append(((abs(n - v), abs(abs(m["monto"]) - c["monto"]), o["vence"] < c["desde"], o["vence"], c["id"], o["periodo"],
                               m["fecha"], m["id"]), c, o, m))
    pares.sort(key=lambda x: x[0])
    for _, c, o, m in pares:
        clave = f"{c['id']}|{o['periodo']}"
        if clave in pagos or m["id"] in usados:
            continue
        usados.add(m["id"])
        pagos[clave] = _pago(m)
    return ocs, pagos, usados


def _mensual(c):
    """Lo que el compromiso significa al mes (semanal × 52 / 12, anual / 12; una vez no cuenta)."""
    f = c["frecuencia"]
    return redondear(c["monto"] if f == "mensual" else c["monto"] * 52 / 12 if f == "semanal" else c["monto"] / 12 if f == "anual" else 0)


def estado_mes(compromisos, movimientos, mes, hoy, moneda, per=None):
    """Estado de cada compromiso activo en el periodo `mes` (ver resumen.rango): pagado (con fecha), pendiente (vence en N días),
    hoy o atrasado (N días). En el periodo en curso también trae lo del anterior que quedó sin pagar (`anterior`). Totales solo
    en `moneda`. `compromisos` trae el avance de cada uno (cuotas, término, cuánto falta) para «Lo que estás pagando»."""
    activos = [c for c in compromisos if c.get("activo", True)]
    inicio, fin = rango(mes, per)
    ocs, pagos, _ = asignar(activos, movimientos, fin, moneda)
    antes = rango(sumar_mes(mes, -1), per) if inicio <= hoy <= fin else None
    h = _num(hoy)
    items = []
    for c, o in ocs:
        en_mes = inicio <= o["vence"] <= fin
        if not en_mes and not (antes and antes[0] <= o["vence"] <= antes[1]):
            continue
        p = pagos.get(f"{c['id']}|{o['periodo']}")
        if not p and o["vence"] < c["desde"]:
            continue
        d = _num(o["vence"]) - h
        estado = "pagado" if p else "pendiente" if d > 0 else "hoy" if d == 0 else "atrasado"
        if not en_mes and estado != "atrasado":
            continue
        cuota = {"numero": c.get("cuotas_pagadas", 0) + o["n"], "total": c["cuotas_total"]} if c.get("cuotas_total") and o["n"] else None
        items.append({"id": c["id"], "nombre": c["nombre"], "tipo": c["tipo"], "signo": c["signo"], "monto": c["monto"],
                      "moneda": c["moneda"], "categoria": c["categoria"], "periodo": o["periodo"], "vence": o["vence"],
                      "estado": estado, "dias": 0 if p else abs(d), "pago": p, "cuota": cuota, "anterior": not en_mes})
    items.sort(key=lambda i: (i["vence"], i["id"]))
    g = [i for i in items if i["signo"] == "gasto" and i["moneda"] == moneda]
    ing = [i for i in items if i["signo"] == "ingreso" and i["moneda"] == moneda and not i["anterior"]]
    resumen_ = []
    for c in activos:
        mios = [o for cc, o in ocs if cc is c]
        r = {"id": c["id"], "nombre": c["nombre"], "tipo": c["tipo"], "signo": c["signo"], "monto": c["monto"], "moneda": c["moneda"],
             "frecuencia": c["frecuencia"], "categoria": c["categoria"], "mensual": _mensual(c), "cuotas": None,
             "saldo": c.get("saldo"), "por_pagar": c.get("saldo"), "termina": c.get("fecha_fin")}
        if c.get("cuotas_total"):
            pagadas = c.get("cuotas_pagadas", 0) + sum(1 for o in mios if o["n"] and f"{c['id']}|{o['periodo']}" in pagos)
            quedan = max(0, c["cuotas_total"] - pagadas)
            todas = vencimientos(c, "2299-12-31")
            ultima = next((o["vence"] for o in reversed(todas) if o["n"]), None)
            r["cuotas"] = {"pagadas": min(pagadas, c["cuotas_total"]), "total": c["cuotas_total"], "quedan": quedan}
            r["termina"] = min(ultima, c["fecha_fin"]) if ultima and c.get("fecha_fin") else ultima or c.get("fecha_fin")
            if r["por_pagar"] is None:
                r["por_pagar"] = redondear(quedan * c["monto"])
        resumen_.append(r)
    return {"mes": mes, "moneda": moneda, "items": items,
            "total": redondear(sum(i["monto"] for i in g if not i["anterior"])),
            "pagado": redondear(sum(i["monto"] for i in g if i["estado"] == "pagado")),
            "pendiente": redondear(sum(i["monto"] for i in g if i["estado"] != "pagado")),
            "atrasado": redondear(sum(i["monto"] for i in g if i["estado"] == "atrasado")),
            "arrastre": redondear(sum(i["monto"] for i in g if i["anterior"])),
            "ingresos_esperados": redondear(sum(i["monto"] for i in ing)),
            "ingresos_recibidos": redondear(sum(i["monto"] for i in ing if i["estado"] == "pagado")),
            "compromisos": resumen_}


def gasto_maximo(movimientos, compromisos, mes, hoy, categorias, meses_completos, moneda, per=None):
    """Cuánto se puede gastar en lo variable este mes: ingreso esperado − compromisos − otros gastos fijos de siempre.
    Ingreso esperado: los compromisos de ingreso del mes o, si no hay, el promedio de ingresos de los últimos 3 meses con datos.
    Lo disponible se reparte entre las categorías variables en proporción a lo que se gasta normalmente (mediana de los meses
    completos, sin contar los pagos de compromisos), redondeado hacia abajo para no pasarse."""
    e = estado_mes(compromisos, movimientos, mes, hoy, moneda, per)
    activos = [c for c in compromisos if c.get("activo", True)]
    inicio, fin = rango(mes, per)
    rangos = [rango(x, per) for x in meses_completos]
    neutras = {c["id"] for c in categorias if c.get("tipo") == "neutro"}
    de_compromiso = {m["id"] for m in movimientos if any(coincide(m, c, moneda) for c in activos)}
    propios = [m for m in movimientos if (m.get("moneda") or moneda) == moneda and m["id"] not in de_compromiso]
    if e["ingresos_esperados"] > 0:
        ingreso, fuente = e["ingresos_esperados"], "compromisos"
    else:
        con_datos = [x for x in periodos_con_datos([m for m in movimientos if (m.get("moneda") or moneda) == moneda], per) if x < mes][-3:]
        dentro = [rango(x, per) for x in con_datos]
        total = sum(m["monto"] for m in movimientos if any(a <= m["fecha"] <= b for a, b in dentro) and m["monto"] > 0
                    and (m.get("moneda") or moneda) == moneda and m.get("categoria") not in neutras)
        ingreso, fuente = (redondear(total / len(con_datos)), "promedio") if con_datos and total > 0 else (None, "")
    comp = e["total"] + e["arrastre"]
    normal, gastado = {}, {}
    for c in categorias:
        if c.get("tipo") != "gasto":
            continue
        valores = [sum(-m["monto"] for m in propios if a <= m["fecha"] <= b and m.get("categoria") == c["id"] and m["monto"] < 0)
                   for a, b in rangos]
        normal[c["id"]] = redondear_arriba(median(valores)) if valores and median(valores) > 0 else 0
        gastado[c["id"]] = redondear(sum(-m["monto"] for m in propios if inicio <= m["fecha"] <= fin and m.get("categoria") == c["id"]
                                         and m["monto"] < 0))
    fijas = {c["id"] for c in categorias if c.get("tipo") == "gasto" and c.get("fijo")}
    otros_fijos = sum(v for k, v in normal.items() if k in fijas)
    disponible = ingreso - comp - otros_fijos if ingreso is not None else None
    variables = [c["id"] for c in categorias if c.get("tipo") == "gasto" and c["id"] not in fijas]
    habitual = sum(normal[k] for k in variables)
    por = []
    for k in variables:
        if not normal[k] and not gastado[k]:
            continue
        maximo = redondear_abajo(disponible * normal[k] / habitual) if disponible is not None and disponible > 0 and habitual > 0 else 0
        por.append({"categoria": k, "normal": normal[k], "maximo": maximo, "gastado": gastado[k]})
    por.sort(key=lambda x: (-x["maximo"], -x["gastado"], x["categoria"]))
    return {"mes": mes, "moneda": moneda, "ingreso": ingreso, "fuente": fuente, "compromisos": comp, "otros_fijos": otros_fijos,
            "disponible": disponible, "alcanza": disponible is not None and disponible > 0, "por_categoria": por}


# ───────────── El mes que parte con el sueldo (igual que ui/app.js) ─────────────
def llegadas_sueldo(compromisos, movimientos, hasta, moneda):
    """Los días en que llegó el sueldo (ordenados): el primer compromiso activo de tipo ingreso, mensual y con categoría «sueldo».
    Los bonos y otros ingresos no mueven el inicio del periodo: solo cuentan como ingresos del periodo en que caen."""
    sueldo = next((c for c in compromisos if c.get("activo", True) and c["tipo"] == "ingreso" and c["frecuencia"] == "mensual"
                   and c.get("categoria") == "sueldo"), None)
    if not sueldo:
        return []
    ocs, pagos, _ = asignar([sueldo], movimientos, hasta, moneda)
    return sorted(pagos[f"{c['id']}|{o['periodo']}"]["fecha"] for c, o in ocs if f"{c['id']}|{o['periodo']}" in pagos)


def periodo(inicio_mes, compromisos, movimientos, hoy, moneda):
    """`per` para resumen.rango a partir del ajuste `inicio_mes` ({"modo": "dia" | "sueldo", "dia": 25}). None = mes calendario."""
    if not isinstance(inicio_mes, dict) or inicio_mes.get("modo") != "sueldo":
        return None
    d = inicio_mes.get("dia")
    if isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 31:
        return None
    hasta = _fecha(_num(hoy) + 62)
    return {"modo": "sueldo", "dia": d, "llegadas": llegadas_sueldo(compromisos, movimientos, hasta, moneda)}


def periodo_actual(hoy=None, movimientos=None, lista=None):
    """(per, periodo de hoy) con lo que hay en ~/Alcancia. Lo usan consejos, avisos y el servidor MCP."""
    hoy = hoy or date.today().isoformat()
    cfg = datos.config()
    moneda = datos.presupuesto().get("moneda") or cfg["moneda"]
    movs = datos.leer_todos() if movimientos is None else movimientos
    per = periodo(cfg.get("inicio_mes"), validos(None, hoy, moneda) if lista is None else lista, movs, hoy, moneda)
    return per, periodo_de(hoy, per)


# ───────────── Detectar en la cartola (solo Python) ─────────────
def palabras_conocidas(pais):
    j = datos.leer_json(CONOCIDOS, {}).get("paises", {})
    lista = [e for e in (j.get("*", []) + j.get(pais, [])) if isinstance(e, dict)]
    r = []
    for e in lista:
        for p in e.get("palabras", []):
            p = datos.normalizar(p)
            if p:
                r.append((re.compile(r"(?<![A-Z0-9])" + re.escape(p) + r"(?![A-Z0-9])"), p, e))
    return sorted(r, key=lambda x: -len(x[1]))


def extraer_cuotas(descripcion):
    """«DIVIDENDO CUOTA 53/240» → (53, 240). También «CUOTA 4 DE 24», «INSTALLMENT 3 OF 12». Si no hay, None."""
    d = datos.normalizar(descripcion)
    m = re.search(r"(?<![A-Z])(?:CUOTAS?|CTA|INSTALL?MENT)\s*(?:N[O]?\.?\s*)?(\d{1,4})\s*(?:/|DE|OF)\s*(\d{1,4})(?!\d)", d)
    if not m:
        return None
    n, total = int(m.group(1)), int(m.group(2))
    return (n, total) if 0 < n <= total <= 1200 else None


def _del_medio(valores):
    """La mediana sin promedios: la del medio (o la menor de las dos del medio)."""
    v = sorted(valores)
    return v[(len(v) - 1) // 2]


def sugerir(movimientos, compromisos, hoy, categorias, moneda, pais="CL", descartados=(), solo_ids=None):
    """Pagos (o ingresos) que parecen compromisos y todavía no lo son. Dos señales:
    - se repite: la misma descripción (sin números) una vez al mes en 3 de los últimos 4 meses, monto ±10 % y día ±4;
    - la descripción lo delata (dividendo, crédito, cuota, PAC, seguro, arriendo…: bin/compromisos_conocidos.json), aunque
      aparezca una sola vez en los últimos 4 meses o en este.
    Nunca se agregan solos: la interfaz pregunta. `solo_ids`: solo los que incluyen alguno de estos movimientos (lo recién importado)."""
    mes = hoy[:7]
    meses4 = [sumar_mes(mes, -i) for i in (4, 3, 2, 1)]
    ventana = set(meses4 + [mes])
    neutras = {c["id"] for c in categorias if c.get("tipo") == "neutro"}
    descartados = {datos.normalizar(d) for d in descartados}
    palabras = palabras_conocidas(pais)
    grupos = {}
    for m in movimientos:
        if m["fecha"][:7] not in ventana or m["monto"] == 0 or m.get("categoria") in neutras or (m.get("moneda") or moneda) != moneda:
            continue
        clave = categorizar.regla_para(m["descripcion"])
        if len(clave) < 3:
            continue
        grupos.setdefault((clave, "gasto" if m["monto"] < 0 else "ingreso"), []).append(m)
    r = []
    for (clave, signo), movs in sorted(grupos.items()):
        if clave in descartados or any(any(coincide(m, c, moneda) for m in movs) for c in compromisos):
            continue
        if any(p and (p in clave or clave in p) for c in compromisos for p in c.get("buscar") or []):
            continue
        por_mes = {}
        for m in movs:
            por_mes.setdefault(m["fecha"][:7], []).append(m)
        if any(len(v) > 1 for v in por_mes.values()):
            continue  # varias veces al mes: es un comercio frecuente (el café), no un compromiso
        movs.sort(key=lambda m: m["fecha"])
        ultimo = movs[-1]
        en4 = [por_mes[x][0] for x in meses4 if x in por_mes]
        montos, dias = [abs(m["monto"]) for m in en4], [int(m["fecha"][8:10]) for m in en4]
        repite = (len(en4) >= 3 and all(abs(x - _del_medio(montos)) <= _del_medio(montos) * 0.10 for x in montos)
                  and all(abs(x - _del_medio(dias)) <= 4 for x in dias))
        d = datos.normalizar(ultimo["descripcion"])
        conocida = next((e for rx, _, e in palabras if rx.search(d)), None)
        if not repite and not conocida:
            continue
        if solo_ids is not None and not any(m["id"] in solo_ids for m in movs):
            continue
        categoria = ultimo.get("categoria") or (conocida or {}).get("categoria") or ""
        cuotas = extraer_cuotas(ultimo["descripcion"])
        if signo == "ingreso":
            tipo = "ingreso"
        elif cuotas:
            tipo = "deuda"
        elif conocida:
            tipo = conocida.get("tipo") if conocida.get("tipo") in TIPOS else "otro"
        else:
            tipo = "suscripcion" if categoria == "suscripciones" else "cuenta" if categoria in ("cuentas", "casa", "educacion") else "otro"
        s = {"clave": clave, "nombre": clave[0] + clave[1:].lower(), "tipo": tipo, "signo": signo,
             "monto": _del_medio(montos) if repite else abs(ultimo["monto"]), "moneda": moneda, "frecuencia": "mensual",
             "dia": _del_medio(dias) if repite else int(ultimo["fecha"][8:10]), "categoria": categoria, "buscar": [clave],
             "origen": "detectado", "motivo": "repite" if repite else "palabra", "meses": len(en4) if repite else 1,
             "preguntar": "cuotas" if tipo == "deuda" else "frecuencia"}
        if cuotas:
            s["cuotas_pagadas"], s["cuotas_total"] = cuotas
            s["preguntar"] = "saldo"
        r.append(s)
    r.sort(key=lambda s: (s["motivo"] != "palabra" or s["tipo"] != "deuda", -s["monto"], s["clave"]))
    return r


def sugerencias(movimientos=None, hoy=None, solo_ids=None):
    """sugerir() con lo que hay en ~/Alcancia."""
    hoy = hoy or date.today().isoformat()
    cfg = datos.config()
    moneda = datos.presupuesto().get("moneda") or cfg["moneda"]
    raw = leer()
    movs = datos.leer_todos() if movimientos is None else movimientos
    return sugerir(movs, validos(raw, hoy, moneda), hoy, datos.categorias(), moneda, cfg.get("pais") or "CL", raw["descartados"], solo_ids)


def fijar_automaticos(hoy, movimientos=None):
    """Anota en compromisos.json los pagos reconocidos solos (con el movimiento que calzó), para que no cambien después.
    Nunca toca lo marcado a mano. Escribe solo si hay algo nuevo."""
    raw = leer()
    moneda = datos.presupuesto().get("moneda") or datos.config()["moneda"]
    lista = [c for c in validos(raw, hoy, moneda) if c.get("activo", True)]
    if not lista:
        return 0
    _, pagos, _ = asignar(lista, datos.leer_todos() if movimientos is None else movimientos, hoy, moneda)
    nuevos = 0
    for c in raw["compromisos"]:
        if not isinstance(c, dict):
            continue
        for clave, p in pagos.items():
            cid, periodo = clave.split("|", 1)
            if cid != c.get("id") or p["como"] != "automatico":
                continue
            e = c.setdefault("pagos", {}).setdefault(periodo, {}) if isinstance(c.get("pagos", {}), dict) else None
            if e is None or e.get("como"):
                continue
            e.update({"como": "automatico", "fecha": p["fecha"], "movimiento": p["movimiento"], "monto": p["monto"]})
            nuevos += 1
    if nuevos:
        escribir(raw)
    return nuevos


# ───────────── Avisos (la app de Mac los muestra como notificaciones del sistema) ─────────────
def avisos(hoy):
    """Lo que hay que avisar hoy: 3 días antes (o menos, si la app no estaba abierta), el día del vencimiento y si quedó
    atrasado. Una vez cada cosa por vencimiento y como máximo un aviso por compromiso al día. Solo gastos."""
    cfg = datos.config()
    if not cfg.get("avisos"):
        return {"ok": True, "avisos": []}
    moneda = datos.presupuesto().get("moneda") or cfg["moneda"]
    lista, movs = validos(None, hoy, moneda), datos.leer_todos()
    per, mes = periodo_actual(hoy, movs, lista)
    e = estado_mes(lista, movs, mes, hoy, moneda, per)
    reg = datos.leer_json(RUTA_AVISOS, {})
    enviados = reg.get("enviados", {}) if isinstance(reg.get("enviados"), dict) else {}
    por_dia = reg.get("por_dia", {}) if isinstance(reg.get("por_dia"), dict) else {}
    r = []
    for i in e["items"]:
        if i["signo"] != "gasto" or i["estado"] == "pagado":
            continue
        tipo = "atrasado" if i["estado"] == "atrasado" else "hoy" if i["estado"] == "hoy" else "pronto" if i["dias"] <= 3 else None
        k = f"{i['id']}|{i['periodo']}|{tipo}"
        if not tipo or k in enviados or por_dia.get(i["id"]) == hoy:
            continue
        enviados[k], por_dia[i["id"]] = hoy, hoy
        # Sin monto: el aviso del sistema puede verse con la pantalla bloqueada.
        r.append({"id": i["id"], "nombre": i["nombre"], "tipo": tipo, "dias": i["dias"], "vence": i["vence"]})
    if r:
        limite = _fecha(_num(hoy) - 120)
        datos.escribir_json(RUTA_AVISOS, {"enviados": {k: v for k, v in enviados.items() if v >= limite},
                                          "por_dia": {k: v for k, v in por_dia.items() if v >= limite}})
    return {"ok": True, "avisos": r}


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "avisos" or not _fecha_valida(sys.argv[2]):
        print(__doc__)
        sys.exit(2)
    res = avisos(sys.argv[2])
    datos.escribir_json(sys.argv[3], res)
    print(json.dumps(res, ensure_ascii=False)[:400])
