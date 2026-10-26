"""Compromisos: lo que se paga (o se recibe) seguido — arriendo, créditos, cuentas, suscripciones, transferencias, sueldo.
Solo biblioteca estándar.

~/Alcancia/compromisos.json (formato abierto, ver README «Formato de los datos»):
  {"formato": 1, "compromisos": [{...}], "descartados": ["CLAVE", ...]}

Reconocer el pago, el estado del mes, el avance de las deudas, los montos aproximados y en UF, y el gasto máximo sugerido viven
igual en ui/app.js (`vencimientos`, `coincide`, `asignar`, `valoresUF`, `enMoneda`, `estadoCompromisos`, `gastoMaximo`) y se
prueban juntos con pruebas/casos.json.
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
from resumen import cargos, cuotas_de, dias_del_mes, periodo_de, periodos_con_datos, rango, redondear_arriba, sumar_mes, valor_cuota  # noqa: E402

RUTA = os.path.join(datos.BASE, "compromisos.json")
RUTA_AVISOS = os.path.join(datos.INTERNO, "avisos.json")
CONOCIDOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compromisos_conocidos.json")

TIPOS = ("deuda", "cuenta", "suscripcion", "transferencia", "ingreso", "otro")
FRECUENCIAS = ("mensual", "semanal", "anual", "una_vez")
ORIGENES = ("manual", "detectado", "ia")
#: Un pago se reconoce entre 10 días antes y 7 después del vencimiento, con el monto dentro de ±5 % (configurable).
ANTES, DESPUES, TOLERANCIA = 10, 7, 5
#: Monto aproximado: por defecto ±3 %. Compromisos en UF: el valor en pesos se estima (sin red) y el rango crece ±1,5 % al mes.
VARIACION, UF, UF_MENSUAL = 3, "UF", 1.5
#: Un pago en UF se reconoce por sus palabras y, si hay un valor de la UF escrito en Ajustes, con el monto dentro de ±15 %.
MARGEN_UF = 15
#: Lo que puede venir de la IA (cualquier otro campo hace que la respuesta no sirva).
CAMPOS_IA = {"nombre", "tipo", "signo", "monto", "moneda", "frecuencia", "dia", "fecha", "categoria", "buscar", "cuotas_total",
             "cuotas_pagadas", "cuotas_restantes", "fecha_fin", "saldo", "aproximado"}
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


def redondear3(v, hacia=0):
    """A 3 cifras significativas: hacia abajo (-1), hacia arriba (1) o al más cercano (0). 978.500 → 979.000 · 9.690,3 → 9.690."""
    if v <= 0:
        return 0
    paso = 10 ** max(0, len(str(int(v))) - 3)
    x = v / paso
    return int((math.floor(x) if hacia < 0 else math.ceil(x) if hacia > 0 else math.floor(x + 0.5)) * paso)


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


def _numero(v, lo, hi, decimales=2):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo < v < hi:
        return None
    v = round(float(v), decimales)
    return int(v) if v == int(v) else v


def _aproximado(a, monto, decimales):
    """{"variacion": %} o {"min", "max"} (en la moneda del compromiso). (valor limpio, error). `true` = ±3 %."""
    if a is None or a is False:
        return None, ""
    if a is True:
        return {"variacion": VARIACION}, ""
    if not isinstance(a, dict) or not a or set(a) - {"variacion", "min", "max"}:
        return None, "El monto aproximado no es válido."
    if "variacion" in a:
        v = _numero(a.get("variacion"), 0, 50.01)
        if v is None or "min" in a or "max" in a:
            return None, "La variación tiene que ser un porcentaje entre 0 y 50."
        return {"variacion": v}, ""
    lo, hi = _numero(a.get("min"), 0, 1e12, decimales), _numero(a.get("max"), 0, 1e12, decimales)
    if lo is None or hi is None or lo > hi or (monto is not None and not lo <= monto <= hi):
        return None, "El rango del monto no es válido (mínimo ≤ monto ≤ máximo)."
    return {"min": lo, "max": hi}, ""


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
    r["moneda"] = c.get("moneda") or moneda
    if not re.fullmatch(r"[A-Z]{3}", str(r["moneda"])) and r["moneda"] != UF:
        errores.append("La moneda no es válida.")
    decimales = 4 if r["moneda"] == UF else 2  # 12,3456 UF
    r["monto"] = _numero(c.get("monto"), 0, 1e12, decimales)
    if r["monto"] is None:
        errores.append("El monto tiene que ser un número mayor que cero.")
    aprox, error = _aproximado(c.get("aproximado"), r["monto"], decimales)
    if error:
        errores.append(error)
    elif aprox:
        r["aproximado"] = aprox
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
        r["saldo"] = _numero(c.get("saldo"), 0, 1e13, decimales)
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


def rango_aprox(c):
    """(mínimo, máximo) de un compromiso aproximado que no es en UF, en su moneda; None si el monto es exacto o en UF."""
    a = c.get("aproximado")
    if not a or c["moneda"] == UF:
        return None
    if "min" in a:
        return a["min"], a["max"]
    v = a["variacion"] / 100
    return redondear3(c["monto"] * (1 - v), -1), redondear3(c["monto"] * (1 + v), 1)


def _rango_uf(c, valor, extra):
    """(mínimo, máximo) en pesos de un compromiso en UF con un valor de la UF y una variación extra (en %)."""
    a = c.get("aproximado") or {}
    lo, hi = (a["min"], a["max"]) if "min" in a else (c["monto"], c["monto"])
    v = (extra + a.get("variacion", 0)) / 100
    return lo * valor * (1 - v), hi * valor * (1 + v)


def coincide(m, c, moneda, uf=None):
    """¿Este movimiento puede ser un pago de este compromiso? Signo, moneda, monto y alguna palabra de `buscar` (sin tildes ni
    mayúsculas); sin palabras, el monto exacto. No mira la fecha. El monto calza dentro de ±tolerancia o, si es aproximado, en
    todo su rango (solo con palabras: sin ellas, un rango confundiría cualquier compra parecida). En UF se paga en la moneda principal: calza por las palabras y, si hay un valor de la UF escrito en Ajustes
    (`uf`), con el monto dentro de ±15 % (más la variación del compromiso); sin palabras, solo con ese valor."""
    monto = m["monto"]
    if monto == 0 or (monto < 0) != (c["signo"] == "gasto"):
        return False
    palabras = [datos.normalizar(p) for p in c.get("buscar") or [] if datos.normalizar(p)]
    a = abs(monto)
    if c["moneda"] == UF:
        if (m.get("moneda") or moneda) != moneda or (not palabras and not uf):
            return False
        if uf:
            lo, hi = _rango_uf(c, uf, MARGEN_UF)
            if not lo - 1e-9 <= a <= hi + 1e-9:
                return False
            if not palabras:
                return True
    else:
        if (m.get("moneda") or moneda) != c["moneda"]:
            return False
        dif = abs(a - c["monto"])
        r = rango_aprox(c)
        en_rango = r is not None and r[0] - 1e-9 <= a <= r[1] + 1e-9
        if not palabras:  # sin palabras, solo el monto exacto: un rango confundiría cualquier compra parecida
            return dif < 0.005
        if dif > c["monto"] * c.get("tolerancia", TOLERANCIA) / 100 + 1e-9 and not en_rango:
            return False
    d = datos.normalizar(m.get("descripcion"))
    return any(p in d for p in palabras)


def _pago(m):
    return {"como": "automatico", "fecha": m["fecha"], "monto": abs(m["monto"]), "movimiento": m["id"], "descripcion": m["descripcion"]}


def asignar(compromisos, movimientos, hasta, moneda, uf=None):
    """Para cada vencimiento hasta `hasta`, el pago que le corresponde. Lo marcado a mano manda; después, por orden de
    las parejas que calzan mejor (más cerca de la fecha, luego del monto). Un movimiento cuenta para un solo compromiso.
    `uf`: el valor de la UF escrito en Ajustes (o None), para reconocer pagos de compromisos en UF por el monto.
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
            candidatos[c["id"]] = [(_num(m["fecha"]), m) for m in movimientos if coincide(m, c, moneda, uf)]
        v = _num(o["vence"])
        esperado = c["monto"] * uf if c["moneda"] == UF and uf else 0 if c["moneda"] == UF else c["monto"]
        for n, m in candidatos[c["id"]]:
            # Un vencimiento anterior a `desde` solo se da por pagado con algo de antes de `desde` (ya estaba pagado al agregarlo).
            if v - ANTES <= n <= v + DESPUES and m["id"] not in usados and m["id"] not in no_es and (o["vence"] >= c["desde"] or m["fecha"] < c["desde"]):
                pares.append(((abs(n - v), abs(abs(m["monto"]) - esperado) if esperado else 0, o["vence"] < c["desde"], o["vence"], c["id"], o["periodo"],
                               m["fecha"], m["id"]), c, o, m))
    pares.sort(key=lambda x: x[0])
    for _, c, o, m in pares:
        clave = f"{c['id']}|{o['periodo']}"
        if clave in pagos or m["id"] in usados:
            continue
        usados.add(m["id"])
        pagos[clave] = _pago(m)
    return ocs, pagos, usados


def _mensual(c, monto=None):
    """Lo que el compromiso significa al mes (semanal × 52 / 12, anual / 12; una vez no cuenta)."""
    f, x = c["frecuencia"], c["monto"] if monto is None else monto
    return redondear(x if f == "mensual" else x * 52 / 12 if f == "semanal" else x / 12 if f == "anual" else 0)


def uf_config(cfg=None):
    """El ajuste `uf` validado: {"valor", "fecha", "variacion_mensual"} (valor y fecha pueden faltar). None si no hay nada."""
    u = (cfg if cfg is not None else datos.config()).get("uf")
    if not isinstance(u, dict):
        return None
    r = {}
    v = _numero(u.get("valor"), 0, 1e7)
    if v is not None and _fecha_valida(u.get("fecha")):
        r["valor"], r["fecha"] = v, u["fecha"]
    vm = _numero(u.get("variacion_mensual"), -0.01, 20.01)
    if vm is not None:
        r["variacion_mensual"] = vm
    return r or None


def _meses_entre(a, b):
    """Meses calendario entre dos fechas (al menos 1): desde ahí el rango de la UF se abre ±variación mensual por mes."""
    return max(1, abs((int(b[:4]) * 12 + int(b[5:7])) - (int(a[:4]) * 12 + int(a[5:7]))))


def valores_uf(compromisos, pagos, uf=None):
    """{id: {"valor", "fecha", "fuente"}} para cada compromiso en UF: el valor de la UF que sale de su último pago reconocido
    (pesos pagados / UF); si no tiene, el más reciente entre el escrito en Ajustes y el de otro compromiso en UF ya pagado."""
    propios = {}
    for c in compromisos:
        if c["moneda"] != UF:
            continue
        mios = [(p["fecha"], k, p) for k, p in pagos.items() if k.split("|", 1)[0] == c["id"] and p.get("movimiento")]
        if mios:
            f, _, p = max(mios, key=lambda x: (x[0], x[1]))
            propios[c["id"]] = {"valor": p["monto"] / c["monto"], "fecha": f, "fuente": "pago"}
    otros = [(v["fecha"], k, v) for k, v in propios.items()]
    otro = {**max(otros, key=lambda x: (x[0], x[1]))[2], "fuente": "otro"} if otros else None
    ajustes = {"valor": uf["valor"], "fecha": uf["fecha"], "fuente": "ajustes"} if uf and uf.get("valor") else None
    general = ajustes if ajustes and (not otro or ajustes["fecha"] >= otro["fecha"]) else otro
    return {c["id"]: propios.get(c["id"]) or general for c in compromisos if c["moneda"] == UF and (propios.get(c["id"]) or general)}


def en_moneda(c, vence, valores, moneda, uf_mensual=UF_MENSUAL):
    """El monto de un compromiso para mostrar y sumar: `monto` y `moneda` (en UF se pasa a la moneda principal con el valor
    estimado), `rango` {min, max} si es aproximado o en UF, y `original` (lo anotado en UF, el valor usado y de dónde salió, o
    `sin_valor` si aún no hay cómo estimarlo: entonces queda en UF y no se suma)."""
    if c["moneda"] != UF:
        r = rango_aprox(c)
        return {"monto": c["monto"], "moneda": c["moneda"], "rango": {"min": r[0], "max": r[1]} if r else None, "original": None}
    ref = valores.get(c["id"])
    if not ref:
        return {"monto": c["monto"], "moneda": UF, "rango": None, "original": {"monto": c["monto"], "moneda": UF, "sin_valor": True}}
    lo, hi = _rango_uf(c, ref["valor"], uf_mensual * _meses_entre(ref["fecha"], vence))
    return {"monto": redondear3(c["monto"] * ref["valor"]), "moneda": moneda, "rango": {"min": redondear3(lo, -1), "max": redondear3(hi, 1)},
            "original": {"monto": c["monto"], "moneda": UF, "sin_valor": False, "valor_uf": redondear(ref["valor"] * 100) / 100,
                         "fecha_uf": ref["fecha"], "fuente": ref["fuente"]}}


def _maximo(x):
    return x["rango"]["max"] if x.get("rango") else x["monto"]


def _minimo(x):
    return x["rango"]["min"] if x.get("rango") else x["monto"]


def estado_mes(compromisos, movimientos, mes, hoy, moneda, per=None, uf=None):
    """Estado de cada compromiso activo en el periodo `mes` (ver resumen.rango): pagado (con fecha), pendiente (vence en N días),
    hoy o atrasado (N días). En el periodo en curso también trae lo del anterior que quedó sin pagar (`anterior`). Totales solo
    en `moneda`. `compromisos` trae el avance de cada uno (cuotas, término, cuánto falta) para «Lo que estás pagando».
    `uf`: el ajuste de la UF (uf_config). Los montos aproximados o en UF traen `rango`; los totales `_max` usan su máximo."""
    activos = [c for c in compromisos if c.get("activo", True)]
    inicio, fin = rango(mes, per)
    ocs, pagos, _ = asignar(activos, movimientos, fin, moneda, (uf or {}).get("valor"))
    valores, uf_mes = valores_uf(activos, pagos, uf), (uf or {}).get("variacion_mensual", UF_MENSUAL)
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
        items.append({"id": c["id"], "nombre": c["nombre"], "tipo": c["tipo"], "signo": c["signo"],
                      **en_moneda(c, o["vence"], valores, moneda, uf_mes), "categoria": c["categoria"], "periodo": o["periodo"],
                      "vence": o["vence"], "estado": estado, "dias": 0 if p else abs(d), "pago": p, "cuota": cuota, "anterior": not en_mes})
    items.sort(key=lambda i: (i["vence"], i["id"]))
    g = [i for i in items if i["signo"] == "gasto" and i["moneda"] == moneda]
    ing = [i for i in items if i["signo"] == "ingreso" and i["moneda"] == moneda and not i["anterior"]]
    resumen_ = []
    for c in activos:
        mios = [o for cc, o in ocs if cc is c]
        en = en_moneda(c, hoy, valores, moneda, uf_mes)
        # Un saldo anotado en UF se pasa a pesos con el mismo valor; si aún no hay cómo, todo queda en UF.
        factor = en["monto"] / c["monto"] if c["moneda"] == UF and not en["original"]["sin_valor"] else 1
        saldo = c.get("saldo")
        r = {"id": c["id"], "nombre": c["nombre"], "tipo": c["tipo"], "signo": c["signo"], **en, "frecuencia": c["frecuencia"],
             "categoria": c["categoria"], "mensual": _mensual(c, en["monto"]), "cuotas": None, "saldo": saldo,
             "por_pagar": (redondear(saldo * factor) if factor != 1 else saldo) if saldo is not None else None, "termina": c.get("fecha_fin")}
        if c.get("cuotas_total"):
            pagadas = c.get("cuotas_pagadas", 0) + sum(1 for o in mios if o["n"] and f"{c['id']}|{o['periodo']}" in pagos)
            quedan = max(0, c["cuotas_total"] - pagadas)
            todas = vencimientos(c, "2299-12-31")
            ultima = next((o["vence"] for o in reversed(todas) if o["n"]), None)
            r["cuotas"] = {"pagadas": min(pagadas, c["cuotas_total"]), "total": c["cuotas_total"], "quedan": quedan}
            r["termina"] = min(ultima, c["fecha_fin"]) if ultima and c.get("fecha_fin") else ultima or c.get("fecha_fin")
            if r["por_pagar"] is None:
                r["por_pagar"] = redondear(quedan * en["monto"]) if en["moneda"] != UF else redondear(quedan * en["monto"] * 10000) / 10000
        resumen_.append(r)
    sin_pagar = [i for i in g if i["estado"] != "pagado"]
    return {"mes": mes, "moneda": moneda, "items": items,
            "total": redondear(sum(i["monto"] for i in g if not i["anterior"])),
            "pagado": redondear(sum(i["monto"] for i in g if i["estado"] == "pagado")),
            "pendiente": redondear(sum(i["monto"] for i in sin_pagar)),
            "atrasado": redondear(sum(i["monto"] for i in g if i["estado"] == "atrasado")),
            "arrastre": redondear(sum(i["monto"] for i in g if i["anterior"])),
            "ingresos_esperados": redondear(sum(i["monto"] for i in ing)),
            "ingresos_recibidos": redondear(sum(i["monto"] for i in ing if i["estado"] == "pagado")),
            # Con montos aproximados o en UF: lo más que podría ser (para no quedarse corto) y si hay algo aproximado sin pagar.
            "total_max": redondear(sum(_maximo(i) for i in g if not i["anterior"])),
            "pendiente_max": redondear(sum(_maximo(i) for i in sin_pagar)),
            "arrastre_max": redondear(sum(_maximo(i) for i in g if i["anterior"])),
            "ingresos_esperados_min": redondear(sum(_minimo(i) for i in ing)),
            "aprox": any(i["rango"] for i in sin_pagar),
            "sin_valor": sum(1 for i in items if i["original"] and i["original"]["sin_valor"]),
            "compromisos": resumen_}


def gasto_maximo(movimientos, compromisos, mes, hoy, categorias, meses_completos, moneda, per=None, uf=None):
    """Cuánto se puede gastar en lo variable este mes: ingreso esperado − compromisos − otros gastos fijos de siempre.
    Ingreso esperado: los compromisos de ingreso del mes o, si no hay, el promedio de ingresos de los últimos 3 meses con datos.
    Lo disponible se reparte entre las categorías variables en proporción a lo que se gasta normalmente (mediana de los meses
    completos, sin contar los pagos de compromisos), redondeado hacia abajo para no pasarse. Con montos aproximados o en UF,
    los gastos cuentan por su máximo y los ingresos por su mínimo: así no se queda corto."""
    e = estado_mes(compromisos, movimientos, mes, hoy, moneda, per, uf)
    activos = [c for c in compromisos if c.get("activo", True)]
    inicio, fin = rango(mes, per)
    rangos = [rango(x, per) for x in meses_completos]
    neutras = {c["id"] for c in categorias if c.get("tipo") == "neutro"}
    de_compromiso = {m["id"] for m in movimientos if any(coincide(m, c, moneda, (uf or {}).get("valor")) for c in activos)}
    propios = [m for m in movimientos if (m.get("moneda") or moneda) == moneda and m["id"] not in de_compromiso]
    if e["ingresos_esperados"] > 0:
        ingreso, fuente = e["ingresos_esperados_min"], "compromisos"
    else:
        con_datos = [x for x in periodos_con_datos([m for m in movimientos if (m.get("moneda") or moneda) == moneda], per) if x < mes][-3:]
        dentro = [rango(x, per) for x in con_datos]
        total = sum(m["monto"] for m in movimientos if any(a <= m["fecha"] <= b for a, b in dentro) and m["monto"] > 0
                    and (m.get("moneda") or moneda) == moneda and m.get("categoria") not in neutras)
        ingreso, fuente = (redondear(total / len(con_datos)), "promedio") if con_datos and total > 0 else (None, "")
    comp = e["total_max"] + e["arrastre_max"]
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


# ───────────── Lo que debes (igual que ui/app.js) ─────────────
#: Palabras con que aparece en la cartola el pago de una tarjeta de crédito (sin tildes, en mayúsculas). Desde ese pago, lo
#: comprado con crédito antes ya no se debe.
PAGO_TARJETA = ("PAGO TARJETA", "PAGO DE TARJETA", "PAGO TC", "PAGO T C", "PAGO TARJ", "TARJETA DE CREDITO", "PAGO DE RESUMEN",
                "CREDIT CARD PAYMENT", "PAYMENT THANK YOU")


def es_pago_tarjeta(m):
    d = datos.normalizar(re.sub(r"[.\-_/]", " ", str(m.get("descripcion") or "")))
    d = re.sub(r"\s+", " ", d)
    return m["monto"] < 0 and m.get("medio") != "credito" and any(p in d for p in PAGO_TARJETA)


_ORDEN_ESTADO = {"atrasado": 0, "hoy": 1, "pendiente": 2}


def lo_que_debes(compromisos, movimientos, hoy, moneda, per=None, uf=None):
    """Lo que debes hoy, en palabras simples. Partes:
    - `compromiso`: cuentas, suscripciones y deudas sin saldo conocido que faltan pagar este mes (y lo atrasado de antes);
    - `deuda`: créditos con lo que te queda por pagar (cuotas que faltan × cuota, o el saldo que anotaste), con lo de este mes aparte;
    - `tarjeta`: lo comprado con crédito desde el último pago de tarjeta (las cuotas de este mes y las compras en 1 cuota), nunca
      más atrás que el inicio del mes anterior (lo de antes ya se facturó);
    - `cuotas`: las cuotas que vienen de compras en cuotas («te quedan 5 cuotas de 61.000»).
    `este_mes` es lo que toca pagar en el mes de hoy (compromisos pendientes y atrasados, y la tarjeta); `total`, todo.
    Cada parte trae `max` (lo más que podría ser, si es aproximado o en UF) y `original` (lo anotado en UF); los totales `_max`."""
    mes = periodo_de(hoy, per)
    inicio, fin = rango(mes, per)
    e = estado_mes(compromisos, movimientos, mes, hoy, moneda, per, uf)
    con_saldo = {c["id"]: c for c in e["compromisos"] if c["signo"] == "gasto" and c["tipo"] == "deuda" and c["moneda"] == moneda
                 and c.get("por_pagar")}
    pendientes = [i for i in e["items"] if i["signo"] == "gasto" and i["moneda"] == moneda and i["estado"] != "pagado"]
    pendientes.sort(key=lambda i: (_ORDEN_ESTADO[i["estado"]], i["vence"], i["id"]))
    partes = []
    for i in pendientes:
        if i["id"] not in con_saldo:
            partes.append({"tipo": "compromiso", "nombre": i["nombre"], "monto": redondear(i["monto"]), "este_mes": redondear(i["monto"]),
                           "max": redondear(_maximo(i)), "original": i["original"], "estado": i["estado"], "vence": i["vence"],
                           "dias": i["dias"], "categoria": i["categoria"], "clave": f"{i['id']}|{i['periodo']}"})
    pagos = sorted(m["fecha"] for m in movimientos if m["fecha"] <= hoy and (m.get("moneda") or moneda) == moneda and es_pago_tarjeta(m))
    ultimo = pagos[-1] if pagos else None
    desde = rango(sumar_mes(mes, -1), per)[0]
    tarjeta, compras, cuotas = 0, 0, []
    for m in sorted(movimientos, key=lambda x: (x["fecha"], x.get("id", ""))):
        if m.get("medio") != "credito" or m["monto"] >= 0 or (m.get("moneda") or moneda) != moneda:
            continue
        en_tarjeta = [(f, v) for f, v, _, _ in cargos(m) if f <= fin and f >= desde and (ultimo is None or f > ultimo)]
        if en_tarjeta:
            tarjeta += sum(-v for _, v in en_tarjeta)
            compras += 1
        n = cuotas_de(m)
        quedan = sum(1 for f, _, _, _ in cargos(m) if f > fin) if n else 0
        if quedan:
            c = valor_cuota(m)
            cuotas.append({"tipo": "cuotas", "nombre": m["descripcion"], "monto": redondear(quedan * c), "este_mes": 0, "max": redondear(quedan * c),
                           "original": None,
                           "cuota": redondear(c), "quedan": quedan, "total": n, "categoria": m.get("categoria") or ""})
    if tarjeta:
        partes.append({"tipo": "tarjeta", "nombre": "", "monto": redondear(tarjeta), "este_mes": redondear(tarjeta), "max": redondear(tarjeta),
                       "original": None, "compras": compras, "desde": ultimo})
    for c in sorted(con_saldo.values(), key=lambda c: c["id"]):
        mias = [i for i in pendientes if i["id"] == c["id"]]
        extra = sum(_maximo(i) - i["monto"] for i in mias)
        partes.append({"tipo": "deuda", "nombre": c["nombre"], "monto": redondear(c["por_pagar"]), "este_mes": redondear(sum(i["monto"] for i in mias)),
                       "max": redondear(c["por_pagar"] * c["rango"]["max"] / c["monto"]) if c["rango"] else redondear(c["por_pagar"] + extra),
                       "original": c["original"], "cuotas": c["cuotas"], "categoria": c["categoria"], "termina": c["termina"],
                       "pendientes": [{"estado": i["estado"], "vence": i["vence"], "dias": i["dias"], "monto": redondear(i["monto"]),
                                       "clave": f"{i['id']}|{i['periodo']}"} for i in mias]})
    partes += sorted(cuotas, key=lambda x: (-x["monto"], x["nombre"]))
    este_mes_max = sum(p["max"] if p["tipo"] == "compromiso" else p["este_mes"] for p in partes if p["tipo"] != "deuda") + \
        sum(_maximo(i) for i in pendientes if i["id"] in con_saldo)
    return {"mes": mes, "moneda": moneda, "total": redondear(sum(p["monto"] for p in partes)),
            "este_mes": redondear(sum(p["este_mes"] for p in partes)), "total_max": redondear(sum(p["max"] for p in partes)),
            "este_mes_max": redondear(este_mes_max), "aprox": any(p["max"] != p["monto"] for p in partes),
            "ultimo_pago_tarjeta": ultimo, "partes": partes}


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


def sugerir(movimientos, compromisos, hoy, categorias, moneda, pais="CL", descartados=(), solo_ids=None, uf=None):
    """Pagos (o ingresos) que parecen compromisos y todavía no lo son. Dos señales:
    - se repite: la misma descripción (sin números) una vez al mes en 3 de los últimos 4 meses, monto ±10 % y día ±4;
    - la descripción lo delata (dividendo, crédito, cuota, PAC, seguro, arriendo…: bin/compromisos_conocidos.json), aunque
      aparezca una sola vez en los últimos 4 meses o en este.
    Si se repite con montos distintos (dentro de ±10 %), va como aproximado con la variación observada; si la descripción dice UF
    o es un dividendo o crédito hipotecario, trae `preguntar_uf` (la interfaz pregunta «¿Se paga en UF?», opcional).
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
        if clave in descartados or any(any(coincide(m, c, moneda, uf) for m in movs) for c in compromisos):
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
        if repite and len(set(montos)) > 1:
            medio = _del_medio(montos)
            s["aproximado"] = {"variacion": max(1, math.ceil(max(abs(x - medio) for x in montos) / medio * 100 - 1e-9))}
        if re.search(r"(?<![A-Z0-9])UF(?![A-Z0-9])", d) or (conocida or {}).get("uf"):
            s["preguntar_uf"] = True
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
    return sugerir(movs, validos(raw, hoy, moneda), hoy, datos.categorias(), moneda, cfg.get("pais") or "CL", raw["descartados"], solo_ids,
                   (uf_config(cfg) or {}).get("valor"))


def fijar_automaticos(hoy, movimientos=None):
    """Anota en compromisos.json los pagos reconocidos solos (con el movimiento que calzó), para que no cambien después.
    Nunca toca lo marcado a mano. Escribe solo si hay algo nuevo."""
    raw = leer()
    moneda = datos.presupuesto().get("moneda") or datos.config()["moneda"]
    lista = [c for c in validos(raw, hoy, moneda) if c.get("activo", True)]
    if not lista:
        return 0
    _, pagos, _ = asignar(lista, datos.leer_todos() if movimientos is None else movimientos, hoy, moneda, (uf_config() or {}).get("valor"))
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
    e = estado_mes(lista, movs, mes, hoy, moneda, per, uf_config(cfg))
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
