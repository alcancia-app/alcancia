"""Compromisos: lo que se paga (o se recibe) seguido — arriendo, créditos, cuentas, suscripciones, transferencias, sueldo.
Solo biblioteca estándar.

~/Alcancia/compromisos.json (formato abierto, ver README «Formato de los datos»):
  {"formato": 1, "compromisos": [{...}], "descartados": ["CLAVE", ...]}

Reconocer el pago, el estado del mes, el avance de las deudas, los montos aproximados y en UF, y el gasto máximo sugerido viven
igual en ui/app.js (`vencimientos`, `coincide`, `asignar`, `valoresUF`, `enMoneda`, `modoPago`, `estadoCompromisos`, `gastoMaximo`) y se
prueban juntos con pruebas/casos.json.
Si cambias una regla, cambia los dos lados y el caso. Validar y sugerir (detectar en la cartola) solo viven aquí.
Lo que usa la conversación con Alcancía (bin/chat.py) también vive en los dos lados: `margen_mensual`, `plan_prestamos`,
`inicio_plan`, `pago_reasignable`, `reasignar_pago` y, para «¿es el mismo préstamo?», `claves_persona`, `prestamos_parecidos`,
`plan_variante` y `prestamo_actualizado` (casos en «chat»), y para buscar un cobro en los movimientos, `palabras_busqueda` y
`buscar_serie` (casos en «chat.buscar»).

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
from resumen import cargos, cuotas_de, dias_del_mes, inicio_nominal, periodo_de, periodos_con_datos, rango, redondear_arriba, sumar_mes, valor_cuota  # noqa: E402
from resumen import resumen as resumen_periodo  # noqa: E402

RUTA = os.path.join(datos.BASE, "compromisos.json")
RUTA_AVISOS = os.path.join(datos.INTERNO, "avisos.json")
CONOCIDOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compromisos_conocidos.json")

TIPOS = ("deuda", "prestamo", "cuenta", "suscripcion", "transferencia", "ingreso", "otro")
FRECUENCIAS = ("mensual", "semanal", "anual", "una_vez")
ORIGENES = ("manual", "detectado", "ia")
#: Un pago se reconoce entre 10 días antes y 7 después del vencimiento, con el monto dentro de ±5 % (configurable).
ANTES, DESPUES, TOLERANCIA = 10, 7, 5
#: Monto aproximado: por defecto ±3 %. Compromisos en UF: el valor en pesos se estima (sin red) y el rango crece ±1,5 % al mes.
VARIACION, UF, UF_MENSUAL = 3, "UF", 1.5
#: Un pago en UF se reconoce por sus palabras y, si hay un valor de la UF escrito en Ajustes, con el monto dentro de ±15 %.
MARGEN_UF = 15
#: Cómo se paga: «automatico» (se cobra solo: PAC, PAT, una suscripción digital con tarjeta) o «manual» (lo pagas tú).
PAGOS = ("automatico", "manual")
#: Sin `pago` ni palabras de algo automático, estos tipos se pagan a mano (los «otro» quedan sin saber: se recuerdan igual).
MANUAL_POR_TIPO = ("deuda", "prestamo", "cuenta", "suscripcion", "transferencia")
#: Un pago automático no se recuerda: solo se avisa si pasaron estos días desde el vencimiento y el cargo no aparece.
GRACIA_AUTO = 3
#: Lo que puede venir de la IA (cualquier otro campo hace que la respuesta no sirva).
CAMPOS_IA = {"nombre", "tipo", "signo", "monto", "moneda", "frecuencia", "dia", "fecha", "categoria", "buscar", "cuotas_total",
             "cuotas_pagadas", "cuotas_restantes", "fecha_fin", "saldo", "aproximado", "con", "prestamo", "pago"}
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


GENERICAS = {"TRANSFERENCIA", "TRANSFERENCIAS", "TRANSF", "TEF", "PAGO", "PAGOS", "COMPRA", "COMPRAS", "ABONO", "CARGO", "CUOTA",
              "CUOTAS", "DEBITO", "CREDITO"}


def limpiar_buscar(lista, sin_genericas=False):
    if isinstance(lista, str):
        lista = lista.split(",")
    r = []
    for p in lista if isinstance(lista, list) else []:
        p = limpiar_clave(p)
        if sin_genericas and p in GENERICAS:
            continue  # aparecen en cualquier movimiento: reconocerían pagos que no son
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


def limpiar_con(t):
    """Con quién es un préstamo («Papá», «Matías»): corto y sin números."""
    return re.sub(r"\s+", " ", re.sub(r"\d", " ", limpiar_nombre(t))).strip()[:30].strip()


def calcular_prestamo(total, cuotas, interes=0, moneda="CLP", cuota=None):
    """Un préstamo entre personas: lo que se paga en total (con interés simple opcional, % sobre el total), la cuota de cada mes
    y la última, que ajusta el redondeo. Igual que calcularPrestamo en ui/app.js. 1.000.000 en 3 → 333.333, 333.333 y 333.334.
    `cuota`: una cuota fija y redonda (la que propone el plan de préstamos, p. ej. 170.000) si calza con las cuotas: al menos lo
    justo (total ÷ cuotas, hacia abajo), no más que el total y sin que las cuotas anteriores a la última ya lo paguen todo. Entonces
    la última es lo que falta (1.500.000 en 12 de 130.000 → la última de 70.000). Si no calza, se calcula como siempre."""
    escala = 10000 if moneda == UF else 1
    pagar = redondear(total * (1 + interes / 100) * escala)
    fija = redondear(cuota * escala) if isinstance(cuota, (int, float)) and not isinstance(cuota, bool) and cuota > 0 else None
    cuota = fija if fija is not None and pagar // cuotas <= fija <= pagar and fija * (cuotas - 1) < pagar else pagar // cuotas
    ultima = pagar - cuota * (cuotas - 1)
    a = (lambda x: x / escala) if escala > 1 else (lambda x: int(x))
    return {"total": total, "interes": interes, "pagar": a(pagar), "cuota": a(cuota), "ultima": a(ultima)}


def completar_prestamo(c, cfg=None):
    """Un préstamo sin día ni frecuencia: se paga cada mes el día del sueldo (si «Tu mes» parte con el sueldo) o el 25."""
    if not isinstance(c, dict) or c.get("tipo") != "prestamo":
        return c
    c = dict(c)
    c.setdefault("frecuencia", "mensual")
    if c.get("dia") is None and c["frecuencia"] == "mensual":
        im = (cfg if cfg is not None else datos.config()).get("inicio_mes") or {}
        c["dia"] = im.get("dia") if isinstance(im, dict) and im.get("modo") == "sueldo" and _entero(im.get("dia"), 1, 31) else 25
    return c


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
    prestamo = c.get("tipo") == "prestamo"
    if prestamo:
        r["con"] = limpiar_con(c.get("con"))
        if not r["con"]:
            errores.append("Falta con quién es el préstamo.")
        elif not r["nombre"]:
            r["nombre"] = limpiar_nombre(("Préstamo a " if c.get("signo") == "ingreso" else "Préstamo de ") + r["con"])
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
    if r["monto"] is None and not prestamo:
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
    r["buscar"] = limpiar_buscar(c.get("buscar"), sin_genericas=estricto)  # lo que propone la IA, sin palabras de cualquier movimiento
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
    if prestamo:
        pr = c.get("prestamo") if isinstance(c.get("prestamo"), dict) else {}
        total = _numero(pr.get("total"), 0, 1e12, decimales)
        interes = _numero(pr.get("interes", 0) or 0, -0.01, 100.01)
        if set(pr) - {"total", "interes", "cuota", "ultima", "pagar"}:
            errores.append("El préstamo no es válido.")
        if total is None:
            errores.append("Falta cuánto es el préstamo en total.")
        if not r.get("cuotas_total"):
            errores.append("Falta en cuántas cuotas se paga.")
        if interes is None:
            errores.append("El interés tiene que ser un porcentaje entre 0 y 100.")
        if total is not None and r.get("cuotas_total") and interes is not None:
            calc = calcular_prestamo(total, r["cuotas_total"], interes, r["moneda"], _numero(pr.get("cuota"), 0, 1e12, decimales))
            r["prestamo"] = {k: calc[k] for k in ("total", "interes", "cuota", "ultima")}
            r["monto"] = calc["cuota"]
    if c.get("fecha_fin") is not None and not prestamo:
        if _fecha_valida(c.get("fecha_fin")):
            r["fecha_fin"] = c["fecha_fin"]
        else:
            errores.append("La fecha de término no es válida.")
    if c.get("saldo") is not None:
        r["saldo"] = _numero(c.get("saldo"), 0, 1e13, decimales)
        if r["saldo"] is None:
            errores.append("El saldo tiene que ser un número mayor que cero.")
            del r["saldo"]
    if c.get("pago") in PAGOS:
        r["pago"] = c["pago"]
    elif c.get("pago") is not None and estricto:
        errores.append("La forma de pago no es válida (se paga solo o lo pagas tú).")
    r["activo"] = c.get("activo", True) is not False
    r["desde"] = c["desde"] if _fecha_valida(c.get("desde")) else hoy
    if r.get("fecha") and r["frecuencia"] == "una_vez" and r["fecha"] < r["desde"]:
        r["desde"] = r["fecha"]
    r["origen"] = c.get("origen") if c.get("origen") in ORIGENES else "manual"
    r["pagos"] = {} if estricto else _pagos(c.get("pagos"))
    if prestamo and not errores and r["frecuencia"] != "una_vez":
        # Termina con la última cuota (desde `desde`): se calcula, no se escribe.
        ultima = next((o["vence"] for o in reversed(vencimientos({**r, "fecha_fin": None}, "2299-12-31")) if o["n"]), None)
        if ultima:
            r["fecha_fin"] = ultima
    return (None, errores) if errores else (r, [])


def parcial(p, ids_categorias, moneda="CLP", cfg=None):
    """Lo que sí se entendió de una propuesta que no pasó la validación (campo por campo), para abrir la tarjeta con eso y que la
    persona complete el resto. Nunca trae ids ni pagos."""
    if not isinstance(p, dict):
        return {}
    p = completar_prestamo(p, cfg)
    r = {}
    if limpiar_nombre(p.get("nombre")):
        r["nombre"] = limpiar_nombre(p.get("nombre"))
    for k, ok in (("tipo", TIPOS), ("signo", ("gasto", "ingreso")), ("frecuencia", FRECUENCIAS), ("pago", PAGOS)):
        if p.get(k) in ok:
            r[k] = p[k]
    if p.get("moneda") == UF or re.fullmatch(r"[A-Z]{3}", str(p.get("moneda") or "")):
        r["moneda"] = p["moneda"]
    dec = 4 if r.get("moneda") == UF else 2
    if _numero(p.get("monto"), 0, 1e12, dec) is not None:
        r["monto"] = _numero(p.get("monto"), 0, 1e12, dec)
    if _entero(p.get("dia"), 1, 31) is not None:
        r["dia"] = _entero(p.get("dia"), 1, 31)
    for k in ("fecha", "fecha_fin"):
        if _fecha_valida(p.get(k)):
            r[k] = p[k]
    if p.get("categoria") in (ids_categorias or ()):
        r["categoria"] = p["categoria"]
    if limpiar_buscar(p.get("buscar"), True):
        r["buscar"] = limpiar_buscar(p.get("buscar"), True)
    for k in ("cuotas_total", "cuotas_pagadas"):
        if _entero(p.get(k), 1 if k == "cuotas_total" else 0, 1200) is not None:
            r[k] = _entero(p.get(k), 0, 1200)
    if _entero(p.get("cuotas_restantes"), 1, 1200) is not None and "cuotas_total" not in r:
        r["cuotas_total"], r["cuotas_pagadas"] = _entero(p.get("cuotas_restantes"), 1, 1200), 0
    if _numero(p.get("saldo"), 0, 1e13, dec) is not None:
        r["saldo"] = _numero(p.get("saldo"), 0, 1e13, dec)
    aprox, error = _aproximado(p.get("aproximado"), r.get("monto"), dec)
    if aprox and not error:
        r["aproximado"] = aprox
    if limpiar_con(p.get("con")):
        r["con"] = limpiar_con(p.get("con"))
    pr = p.get("prestamo") if isinstance(p.get("prestamo"), dict) else {}
    if _numero(pr.get("total"), 0, 1e12, dec) is not None:
        r["prestamo"] = {"total": _numero(pr.get("total"), 0, 1e12, dec), "interes": _numero(pr.get("interes", 0) or 0, -0.01, 100.01) or 0}
    return r


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


# ───────────── Se paga solo o lo pagas tú (igual que ui/app.js) ─────────────
def palabras_automatico(pais="*"):
    """Las palabras de algo que se cobra solo (bin/compromisos_conocidos.json, «automatico»): las de todos y las del país."""
    j = datos.leer_json(CONOCIDOS, {}).get("automatico", {})
    j = j if isinstance(j, dict) else {}
    return [p for p in (j.get("*", []) + (j.get(pais, []) if pais != "*" else [])) if isinstance(p, str) and p.strip()]


def modo_pago(c, palabras=()):
    """«automatico», «manual» o None (no se sabe: se recuerda igual que uno manual, sin etiqueta). Igual que modoPago en ui/app.js.
    Lo que dijo la persona (`pago`) manda. Si no lo dijo: «automatico» si el nombre o las palabras para reconocerlo traen una de
    `palabras` (PAC, PAT, cargo automático, Netflix, Spotify…, como palabras completas); si no, «manual» para deudas, préstamos,
    cuentas, suscripciones y transferencias (más vale recordar de más que dejar pasar un pago). Los ingresos no tienen."""
    if c.get("signo") == "ingreso" or c.get("tipo") == "ingreso":
        return None
    if c.get("pago") in PAGOS:
        return c["pago"]
    texto = " | ".join(datos.normalizar(x) for x in [c.get("nombre") or ""] + [str(b) for b in c.get("buscar") or []])
    for p in palabras:
        p = datos.normalizar(p)
        if p and re.search(r"(?<![A-Z0-9])" + re.escape(p) + r"(?![A-Z0-9])", texto):
            return "automatico"
    return "manual" if c.get("tipo") in MANUAL_POR_TIPO else None


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
    if m.get("categoria") == "transferencia" and c["tipo"] != "transferencia":
        return False  # entre tus propias cuentas: nunca es el pago de un compromiso
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


#: Un pago atrasado se reconoce aunque venga hasta 30 % más alto que lo esperado (por el interés por mora), solo con sus palabras.
MORA_MAX = 30
#: Un pago mensual o anual se reconoce hasta 20 días después del vencimiento (más de 7 es un pago atrasado; a veces con mora).
ATRASO_MAX = 20


def _tope(c, uf):
    """(lo esperado, lo más alto que se reconoce sin mora) en la moneda del pago; None si no hay cómo saberlo (UF sin valor)."""
    if c["moneda"] == UF:
        if not uf:
            return None
        hi = _rango_uf(c, uf, MARGEN_UF)[1]
        return hi, hi
    r = rango_aprox(c)
    esperado = r[1] if r else c["monto"]
    return esperado, max(esperado, c["monto"] * (1 + c.get("tolerancia", TOLERANCIA) / 100))


def coincide_tarde(m, c, moneda, uf=None):
    """¿Puede ser el pago atrasado de este compromiso, con interés por mora encima? Como coincide, pero el monto pasa del tope
    (hasta +30 %) y siempre con alguna palabra de `buscar`. Solo se usa para pagos después del vencimiento."""
    monto = m["monto"]
    if monto >= 0 or c["signo"] != "gasto" or m.get("categoria") == "transferencia" and c["tipo"] != "transferencia":
        return False
    palabras = [datos.normalizar(p) for p in c.get("buscar") or [] if datos.normalizar(p)]
    t = _tope(c, uf)
    if not palabras or not t or (m.get("moneda") or moneda) != (moneda if c["moneda"] == UF else c["moneda"]):
        return False
    if not t[1] + 1e-9 < -monto <= t[1] * (1 + MORA_MAX / 100) + 1e-9:
        return False
    d = datos.normalizar(m.get("descripcion"))
    return any(p in d for p in palabras)


def palabras_mora(pais="*"):
    """Las palabras de un cargo por atraso (INTERES, MORA, RECARGO, COBRANZA, LATE FEE…): solo datos, en compromisos_conocidos.json."""
    j = datos.leer_json(CONOCIDOS, {}).get("mora", {})
    return [p for k in ("*", pais) for p in j.get(k, []) if isinstance(p, str) and p.strip()]


def _es_mora(m, palabras):
    d = re.sub(r"\s+", " ", datos.normalizar(re.sub(r"[.\-_/]", " ", str(m.get("descripcion") or ""))))
    return any(re.search(r"(?<![A-Z0-9])" + re.escape(re.sub(r"\s+", " ", re.sub(r"[.\-_/]", " ", datos.normalizar(p))).strip()) + r"(?![A-Z0-9])", d)
               for p in palabras)


def _moras(ocs, pagos, movimientos, moneda, uf, palabras, usados):
    """El interés por mora de cada pago atrasado: lo que pagó de más (sobre el tope) y un cargo aparte (INTERES, MORA, COBRANZA…)
    hasta 7 días antes o después del pago. Lo anota en el pago: {"monto", "dias", "movimiento"?}."""
    por_id = {m["id"]: m for m in movimientos}
    cargos = sorted((m for m in movimientos if m["monto"] < 0 and m["id"] not in usados and palabras and _es_mora(m, palabras)),
                    key=lambda m: (m["fecha"], m["id"]))
    tomados = set()
    for c, o in ocs:
        p = pagos.get(f"{c['id']}|{o['periodo']}")
        if not p or p["como"] != "automatico" or c["signo"] != "gasto":
            continue
        dias = _num(p["fecha"]) - _num(o["vence"])
        if dias <= 0:
            continue
        m = por_id.get(p["movimiento"])
        extra = 0
        t = _tope(c, uf)
        if t and m and -m["monto"] > t[1] + 1e-9:
            extra = -m["monto"] - t[0]
        cerca = [x for x in cargos if x["id"] not in tomados and abs(_num(x["fecha"]) - _num(p["fecha"])) <= 7
                 and (x.get("moneda") or moneda) == (m.get("moneda") or moneda if m else moneda)]
        cargo = min(cerca, key=lambda x: (abs(_num(x["fecha"]) - _num(p["fecha"])), x["fecha"], x["id"])) if cerca else None
        if cargo:
            tomados.add(cargo["id"])
            extra += -cargo["monto"]
        if extra > 0:
            p["mora"] = {"monto": redondear(extra), "dias": dias, **({"movimiento": cargo["id"]} if cargo else {})}


def _pago(m):
    return {"como": "automatico", "fecha": m["fecha"], "monto": abs(m["monto"]), "movimiento": m["id"], "descripcion": m["descripcion"]}


def asignar(compromisos, movimientos, hasta, moneda, uf=None, mora=None):
    """Para cada vencimiento hasta `hasta`, el pago que le corresponde. Lo marcado a mano manda; después, por orden de
    las parejas que calzan mejor (más cerca de la fecha, luego del monto). Un movimiento cuenta para un solo compromiso.
    `uf`: el valor de la UF escrito en Ajustes (o None), para reconocer pagos de compromisos en UF por el monto.
    `mora`: las palabras de un cargo por atraso (palabras_mora); con ellas, un pago atrasado trae `mora` (ver _moras).
    Un pago atrasado también se reconoce si viene más alto que el tope (interés por mora, coincide_tarde).
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
            candidatos[c["id"]] = [(_num(m["fecha"]), m, False) for m in movimientos if coincide(m, c, moneda, uf)] + \
                [(_num(m["fecha"]), m, True) for m in movimientos if coincide_tarde(m, c, moneda, uf)]
        v = _num(o["vence"])
        esperado = c["monto"] * uf if c["moneda"] == UF and uf else 0 if c["moneda"] == UF else c["monto"]
        for n, m, tarde in candidatos[c["id"]]:
            # Un vencimiento anterior a `desde` solo se da por pagado con algo de antes de `desde` (ya estaba pagado al agregarlo).
            hasta_ = v + (ATRASO_MAX if c["frecuencia"] in ("mensual", "anual") else DESPUES)
            if (not tarde or n > v) and v - ANTES <= n <= hasta_ and m["id"] not in usados and m["id"] not in no_es and (o["vence"] >= c["desde"] or m["fecha"] < c["desde"]):
                pares.append(((abs(n - v), abs(abs(m["monto"]) - esperado) if esperado else 0, o["vence"] < c["desde"], o["vence"], c["id"], o["periodo"],
                               m["fecha"], m["id"]), c, o, m))
    pares.sort(key=lambda x: x[0])
    for _, c, o, m in pares:
        clave = f"{c['id']}|{o['periodo']}"
        if clave in pagos or m["id"] in usados:
            continue
        usados.add(m["id"])
        pagos[clave] = _pago(m)
    _moras(ocs, pagos, movimientos, moneda, uf, mora or [], usados)
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


def estado_mes(compromisos, movimientos, mes, hoy, moneda, per=None, uf=None, mora=None, auto=None):
    """Estado de cada compromiso activo en el periodo `mes` (ver resumen.rango): pagado (con fecha), pendiente (vence en N días),
    hoy o atrasado (N días). Uno que se paga solo (`modo_pago`, con las palabras `auto`) y ya venció queda «esperando» los primeros
    GRACIA_AUTO días (el cargo puede tardar en aparecer) y recién después «atrasado» (no vimos el cargo). En el periodo en curso también trae lo del anterior que quedó sin pagar (`anterior`). Totales solo
    en `moneda`. `compromisos` trae el avance de cada uno (cuotas, término, cuánto falta) para «Lo que estás pagando».
    `uf`: el ajuste de la UF (uf_config). Los montos aproximados o en UF traen `rango`; los totales `_max` usan su máximo."""
    activos = [c for c in compromisos if c.get("activo", True)]
    inicio, fin = rango(mes, per)
    ocs, pagos, _ = asignar(activos, movimientos, fin, moneda, (uf or {}).get("valor"), mora)
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
        modo = modo_pago(c, auto or ())
        estado = ("pagado" if p else "pendiente" if d > 0 else "hoy" if d == 0
                  else "esperando" if modo == "automatico" and -d <= GRACIA_AUTO else "atrasado")
        if not en_mes and estado not in ("atrasado", "esperando"):
            continue
        cuota = {"numero": c.get("cuotas_pagadas", 0) + o["n"], "total": c["cuotas_total"]} if c.get("cuotas_total") and o["n"] else None
        en = en_moneda(c, o["vence"], valores, moneda, uf_mes)
        if c.get("prestamo") and cuota and cuota["numero"] == c["cuotas_total"] and c["moneda"] != UF:
            en["monto"] = c["prestamo"]["ultima"]  # la última cuota de un préstamo ajusta el redondeo
        items.append({"id": c["id"], "nombre": c["nombre"], "tipo": c["tipo"], "signo": c["signo"],
                      **en, "categoria": c["categoria"], "periodo": o["periodo"],
                      "vence": o["vence"], "estado": estado, "dias": 0 if p else abs(d), "pago": p, "cuota": cuota, "anterior": not en_mes,
                      "modo_pago": modo})
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
             "por_pagar": (redondear(saldo * factor) if factor != 1 else saldo) if saldo is not None else None, "termina": c.get("fecha_fin"),
             "con": c.get("con"), "modo_pago": modo_pago(c, auto or ())}
        if c.get("cuotas_total"):
            pagadas = c.get("cuotas_pagadas", 0) + sum(1 for o in mios if o["n"] and f"{c['id']}|{o['periodo']}" in pagos)
            quedan = max(0, c["cuotas_total"] - pagadas)
            todas = vencimientos(c, "2299-12-31")
            ultima = next((o["vence"] for o in reversed(todas) if o["n"]), None)
            r["cuotas"] = {"pagadas": min(pagadas, c["cuotas_total"]), "total": c["cuotas_total"], "quedan": quedan}
            r["termina"] = min(ultima, c["fecha_fin"]) if ultima and c.get("fecha_fin") else ultima or c.get("fecha_fin")
            if r["por_pagar"] is None:
                r["por_pagar"] = redondear(quedan * en["monto"]) if en["moneda"] != UF else redondear(quedan * en["monto"] * 10000) / 10000
                if c.get("prestamo") and quedan and en["moneda"] != UF:
                    r["por_pagar"] += c["prestamo"]["ultima"] - c["monto"]
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


_ORDEN_ESTADO = {"atrasado": 0, "hoy": 1, "esperando": 2, "pendiente": 3}


def lo_que_debes(compromisos, movimientos, hoy, moneda, per=None, uf=None, auto=None):
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
    e = estado_mes(compromisos, movimientos, mes, hoy, moneda, per, uf, None, auto)
    con_saldo = {c["id"]: c for c in e["compromisos"] if c["signo"] == "gasto" and c["tipo"] in ("deuda", "prestamo") and c["moneda"] == moneda
                 and c.get("por_pagar")}
    pendientes = [i for i in e["items"] if i["signo"] == "gasto" and i["moneda"] == moneda and i["estado"] != "pagado"]
    pendientes.sort(key=lambda i: (_ORDEN_ESTADO[i["estado"]], i["vence"], i["id"]))
    partes = []
    for i in pendientes:
        if i["id"] not in con_saldo:
            partes.append({"tipo": "compromiso", "nombre": i["nombre"], "monto": redondear(i["monto"]), "este_mes": redondear(i["monto"]),
                           "max": redondear(_maximo(i)), "original": i["original"], "estado": i["estado"], "vence": i["vence"],
                           "dias": i["dias"], "categoria": i["categoria"], "clave": f"{i['id']}|{i['periodo']}",
                           "modo_pago": i["modo_pago"]})
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
                       "original": c["original"], "con": c["con"], "cuotas": c["cuotas"], "categoria": c["categoria"], "termina": c["termina"],
                       "pendientes": [{"estado": i["estado"], "vence": i["vence"], "dias": i["dias"], "monto": redondear(i["monto"]),
                                       "clave": f"{i['id']}|{i['periodo']}", "modo_pago": i["modo_pago"]} for i in mias]})
    partes += sorted(cuotas, key=lambda x: (-x["monto"], x["nombre"]))
    este_mes_max = sum(p["max"] if p["tipo"] == "compromiso" else p["este_mes"] for p in partes if p["tipo"] != "deuda") + \
        sum(_maximo(i) for i in pendientes if i["id"] in con_saldo)
    # Te deben: préstamos que hiciste tú. Van aparte y nunca se restan de lo que debes.
    te_deben = []
    for c in sorted((c for c in e["compromisos"] if c["tipo"] == "prestamo" and c["signo"] == "ingreso" and c["moneda"] == moneda
                     and c.get("por_pagar")), key=lambda c: c["id"]):
        mias = [i for i in e["items"] if i["id"] == c["id"] and i["estado"] != "pagado"]
        te_deben.append({"nombre": c["nombre"], "con": c["con"], "monto": redondear(c["por_pagar"]), "este_mes": redondear(sum(i["monto"] for i in mias)),
                         "cuotas": c["cuotas"], "termina": c["termina"]})
    return {"mes": mes, "moneda": moneda, "total": redondear(sum(p["monto"] for p in partes)),
            "te_deben": te_deben, "te_deben_total": redondear(sum(t["monto"] for t in te_deben)),
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


#: Palabras que dicen «esto es un sueldo» (sin tildes ni mayúsculas).
PALABRAS_SUELDO = ("REMUNERACION", "SUELDO", "NOMINA", "PAYROLL", "SALARIO", "SALARY")
#: El sueldo se repite con un monto parecido (± este %) y, si la descripción no lo dice, es al menos esta parte de lo que entró ese mes.
SUELDO_PARECIDO, SUELDO_PRINCIPAL = 25, 50


def detectar_sueldo(movimientos, hoy, categorias, moneda):
    """El sueldo, si se ve claro en los movimientos (igual que detectarSueldo en ui/app.js): el ingreso más grande que se repite en
    al menos 2 de los últimos 3 meses (o 3 de 4), una vez por mes y con monto parecido (±25 %), que no es entre tus cuentas. Si la
    descripción no dice sueldo (REMUNERACION, SUELDO, NOMINA, PAYROLL…), cada llegada tiene que ser al menos la mitad de lo que
    entró ese mes. Devuelve {"dia" (la mediana del día de llegada), "monto", "variacion", "llegadas", "clave", "meses"} o None."""
    mes = hoy[:7]
    meses4 = [sumar_mes(mes, -i) for i in (3, 2, 1, 0)]
    neutras = {c["id"] for c in categorias if c.get("tipo") == "neutro"} | {"transferencia"}
    # Lo que la persona ya marcó como Sueldo alguna vez manda: un movimiento con la misma descripción cuenta aunque haya quedado
    # «Entre mis cuentas» (en Mercado Pago el sueldo llega como «Carga de saldo»).
    sueldo_claves = {categorizar.regla_para(m["descripcion"]) for m in movimientos if m.get("categoria") == "sueldo" and m["monto"] > 0}
    ingresos = [m for m in movimientos if m["monto"] > 0 and m["fecha"] <= hoy and m["fecha"][:7] in meses4
                and (m.get("categoria") not in neutras or categorizar.regla_para(m["descripcion"]) in sueldo_claves)
                and (m.get("moneda") or moneda) == moneda]
    total_mes = {}
    for m in ingresos:
        total_mes[m["fecha"][:7]] = total_mes.get(m["fecha"][:7], 0) + m["monto"]
    clave_de = {m["id"]: categorizar.regla_para(m["descripcion"]) for m in ingresos}
    # Primero lo que se parece a lo que la persona ya marcó como Sueldo; y entonces solo con esa misma descripción (que un ingreso
    # grande y suelto, como una devolución de impuestos, no se cuele en las llegadas).
    for ancla in sorted(ingresos, key=lambda m: (clave_de[m["id"]] not in sueldo_claves, -m["monto"], m["fecha"], m["id"])):
        miembros = []
        mismo = clave_de[ancla["id"]] in sueldo_claves
        for x in meses4:
            cerca = [m for m in ingresos if m["fecha"][:7] == x and abs(m["monto"] - ancla["monto"]) <= ancla["monto"] * SUELDO_PARECIDO / 100 + 1e-9
                     and (not mismo or clave_de[m["id"]] == clave_de[ancla["id"]])]
            if cerca:
                miembros.append(min(cerca, key=lambda m: (abs(m["monto"] - ancla["monto"]), m["fecha"], m["id"])))
        en3 = sum(1 for m in miembros if m["fecha"][:7] in meses4[1:])
        if en3 < 2 and len(miembros) < 3:
            continue
        dice = any(m.get("categoria") == "sueldo" or any(p in datos.normalizar(m["descripcion"]) for p in PALABRAS_SUELDO) for m in miembros)
        if not dice and any(m["monto"] < total_mes[m["fecha"][:7]] * SUELDO_PRINCIPAL / 100 - 1e-9 for m in miembros):
            continue
        dias = sorted(int(m["fecha"][8:10]) for m in miembros)
        k = len(dias) // 2
        dia = dias[k] if len(dias) % 2 else (dias[k - 1] + dias[k] + 1) // 2
        montos = [m["monto"] for m in miembros]
        medio = _del_medio(montos)
        variacion = min(50, max(1, math.ceil(max(abs(x - medio) for x in montos) / medio * 100 - 1e-9)))
        claves = {re.sub(r"[^A-Z0-9]+$", "", categorizar.regla_para(m["descripcion"])) for m in miembros}
        clave = claves.pop() if len(claves) == 1 else ""
        return {"dia": dia, "monto": medio, "variacion": variacion, "llegadas": sorted(m["fecha"] for m in miembros),
                "clave": clave if len(clave) >= 3 else "", "meses": len(miembros)}
    return None


def compromiso_sueldo(d, hoy, moneda):
    """El compromiso de sueldo que sale de lo detectado (sin validar)."""
    return {"nombre": "Sueldo", "tipo": "ingreso", "signo": "ingreso", "monto": d["monto"], "moneda": moneda, "frecuencia": "mensual",
            "dia": d["dia"], "categoria": "sueldo", "buscar": [d["clave"]] if d["clave"] else [], "aproximado": {"variacion": d["variacion"]},
            "origen": "detectado", "desde": min(d["llegadas"] + [hoy]), "activo": True}  # desde la primera llegada: así cuenta la historia


def aplicar_sueldo(hoy, movimientos=None):
    """Si la persona nunca eligió cuándo empieza su mes (`inicio_mes` no está en config) y el sueldo se ve claro, Alcancía lo usa
    sola y lo guarda: config `inicio_mes` = {"modo": "sueldo", "dia", "auto": true}, el compromiso de sueldo (si no hay uno) y que
    esas llegadas queden como Sueldo (con una regla si su descripción no calza con otros movimientos; si no, solo esas). Con `auto`,
    si el día típico cambia, lo sigue. Lo que la persona eligió nunca se toca. Devuelve lo detectado si cambió algo; si no, None."""
    ruta = os.path.join(datos.INTERNO, "config.json")
    cfg = datos.leer_json(ruta, {})
    im = cfg.get("inicio_mes")
    if im is not None and not (isinstance(im, dict) and im.get("auto") is True):
        return None
    moneda = datos.presupuesto().get("moneda") or datos.config()["moneda"]
    movs = datos.leer_todos() if movimientos is None else movimientos
    cats = datos.categorias()
    d = detectar_sueldo(movs, hoy, cats, moneda)
    if not d:
        return None
    cambio = im is None or im.get("dia") != d["dia"]
    if cambio:
        cfg["inicio_mes"] = {"modo": "sueldo", "dia": d["dia"], "auto": True}
        datos.escribir_json(ruta, cfg)
    raw = leer()
    sueldo = next((c for c in validos(raw, hoy, moneda) if c.get("activo", True) and c["tipo"] == "ingreso"
                   and c["frecuencia"] == "mensual" and c.get("categoria") == "sueldo"), None)
    if sueldo is None and any(c["id"] == "sueldo" for c in cats):
        c, error = validar(compromiso_sueldo(d, hoy, moneda), {c["id"] for c in cats}, hoy, moneda)
        if not error:
            raw["compromisos"].append(c)
            escribir(raw)
            _marcar_sueldo(d, movs, cats)
            cambio = True
    elif sueldo is not None and sueldo.get("origen") == "detectado" and sueldo["dia"] != d["dia"]:
        for c in raw["compromisos"]:
            if isinstance(c, dict) and c.get("id") == sueldo["id"]:
                c["dia"] = d["dia"]
        escribir(raw)
    return d if cambio else None


def _marcar_sueldo(d, movimientos, categorias):
    """Las llegadas del sueldo quedan con categoría Sueldo: con una regla si su descripción no calza con ningún otro movimiento
    (así las que lleguen después también), o solo esas si es algo común («Carga de saldo» también es cuando cargas tú)."""
    import guardar
    llegadas = set(d["llegadas"])
    miembros = [m for m in movimientos if m["fecha"] in llegadas and m["monto"] > 0 and abs(m["monto"] - d["monto"]) <= d["monto"] * 0.5]
    clave = d["clave"]
    otros = [m for m in movimientos if clave and clave in datos.normalizar(m["descripcion"]) and m not in miembros]
    if clave and not otros and not any(datos.normalizar(r.get("contiene", "")) == clave for r in datos.reglas()):
        guardar.regla({"contiene": clave, "categoria": "sueldo"})
        return
    for m in miembros:
        if m.get("categoria") != "sueldo":
            datos.cambiar(m["fecha"][:7], m["id"], {"categoria": "sueldo"})


def periodo(inicio_mes, compromisos, movimientos, hoy, moneda):
    """`per` para resumen.rango a partir del ajuste `inicio_mes` ({"modo": "dia" | "sueldo", "dia": 25}). None = mes calendario."""
    if not isinstance(inicio_mes, dict) or inicio_mes.get("modo") != "sueldo":
        return None
    d = inicio_mes.get("dia")
    if isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 31:
        return None
    hasta = _fecha(_num(hoy) + 62)
    llegadas = llegadas_sueldo(compromisos, movimientos, hasta, moneda)
    per = {"modo": "sueldo", "dia": d, "llegadas": llegadas}
    if llegadas:
        per["hoy"] = hoy  # con historia de llegadas, si el sueldo se atrasa el mes anterior sigue (resumen.inicio_periodo)
    return per


# ───────────── Días hábiles y el próximo sueldo (igual que ui/app.js) ─────────────
FERIADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feriados.json")


def feriados(pais):
    """Los feriados nacionales del país («AAAA-MM-DD», de bin/feriados.json). Un país que no está ahí: ninguno (solo fines de semana)."""
    por_anio = datos.leer_json(FERIADOS, {}).get(str(pais or "").upper(), {})
    return sorted(f["fecha"] for lista in por_anio.values() if isinstance(lista, list) for f in lista
                  if isinstance(f, dict) and _fecha_valida(f.get("fecha")))


def es_habil(f, feriados_):
    return date.fromisoformat(f).weekday() < 5 and f not in feriados_


def correr_habil(f, regla, feriados_):
    """El día hábil más cercano: el mismo si es hábil; si no, el anterior (o el siguiente, si `regla` es «siguiente»)."""
    paso = 1 if regla == "siguiente" else -1
    n = 0
    while not es_habil(f, feriados_) and n < 15:
        f, n = _fecha(_num(f) + paso), n + 1
    return f


def _nominal_cerca(dia, llegada):
    """El día de siempre (en el mes de la llegada, el anterior o el siguiente) más cercano a una llegada."""
    m = llegada[:7]
    opciones = [f"{x}-{min(dia, dias_del_mes(x)):02d}" for x in (sumar_mes(m, -1), m, sumar_mes(m, 1))]
    return min(opciones, key=lambda f: (abs(_num(f) - _num(llegada)), f))


def regla_habil(dia, llegadas, feriados_):
    """Si el día de pago cae en fin de semana o feriado, ¿te pagan el hábil anterior o el siguiente? Lo que se vio en las llegadas
    (cuando el día de siempre no fue hábil); sin señales, «anterior» (lo común en Chile)."""
    antes = despues = 0
    for f in llegadas:
        n = _nominal_cerca(dia, f)
        if not es_habil(n, feriados_):
            antes, despues = antes + (f < n), despues + (f > n)
    return "siguiente" if despues > antes else "anterior"


def proximo_sueldo(per, hoy, feriados_):
    """Cuándo debería llegar el próximo sueldo: el día de siempre del periodo siguiente, corrido a un día hábil según la regla
    aprendida. `atrasado`: ya pasó un día hábil después de esa fecha y no llegó. None si el mes no va de sueldo a sueldo."""
    if not per or per.get("modo") != "sueldo" or not isinstance(per.get("dia"), int):
        return None
    siguiente = sumar_mes(periodo_de(hoy, per), 1)
    nominal = inicio_nominal(siguiente, per)
    regla = regla_habil(per["dia"], per.get("llegadas") or [], feriados_)
    fecha = correr_habil(nominal, regla, feriados_)
    plazo = correr_habil(_fecha(_num(fecha) + 1), "siguiente", feriados_)
    return {"fecha": fecha, "nominal": nominal, "regla": regla, "periodo": siguiente, "atrasado": hoy > plazo}


def periodo_actual(hoy=None, movimientos=None, lista=None):
    """(per, periodo de hoy) con lo que hay en ~/Alcancia. Lo usan consejos, avisos y el servidor MCP."""
    hoy = hoy or date.today().isoformat()
    cfg = datos.config()
    moneda = datos.presupuesto().get("moneda") or cfg["moneda"]
    movs = datos.leer_todos() if movimientos is None else movimientos
    im = cfg.get("inicio_mes")
    if im is None:  # nunca eligió: lo mismo que haría la app al abrirse (aplicar_sueldo), sin escribir nada
        d = detectar_sueldo(movs, hoy, datos.categorias(), moneda)
        im = {"modo": "sueldo", "dia": d["dia"]} if d else None
    per = periodo(im, validos(None, hoy, moneda) if lista is None else lista, movs, hoy, moneda)
    if per and not per["llegadas"] and cfg.get("inicio_mes") is None:
        per["llegadas"] = d["llegadas"]
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


def sugerir(movimientos, compromisos, hoy, categorias, moneda, pais="CL", descartados=(), solo_ids=None, uf=None, auto=None):
    """Pagos (o ingresos) que parecen compromisos y todavía no lo son. Dos señales:
    - se repite: la misma descripción (sin números) una vez al mes en 3 de los últimos 4 meses, monto ±10 % y día ±4;
    - la descripción lo delata (dividendo, crédito, cuota, PAC, seguro, arriendo…: bin/compromisos_conocidos.json), aunque
      aparezca una sola vez en los últimos 4 meses o en este.
    Si se repite con montos distintos (dentro de ±10 %), va como aproximado con la variación observada; si la descripción dice UF
    o es un dividendo o crédito hipotecario, trae `preguntar_uf` (la interfaz pregunta «¿Se paga en UF?», opcional).
    Nunca se agregan solos: la interfaz pregunta. `solo_ids`: solo los que incluyen alguno de estos movimientos (lo recién importado).
    Cada gasto trae `pago` («automatico» o «manual», ver modo_pago con las palabras `auto`; por defecto las del país)."""
    auto = palabras_automatico(pais) if auto is None else auto
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
        modo = modo_pago({"nombre": ultimo["descripcion"], "buscar": [clave], "tipo": tipo, "signo": signo}, auto)
        if modo:
            s["pago"] = modo
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


# ───────────── Buscar un cobro en los movimientos (la conversación con Alcancía; igual que buscarSerie en ui/app.js) ─────────────
#: Hasta cuántos días atrás se busca, cuánto pueden variar los montos de una misma serie (%), cuántos meses distintos la hacen
#: serie y hasta cuántos días desde el último cobro sigue «activa».
BUSCAR_DIAS, BUSCAR_VARIACION, BUSCAR_MESES, BUSCAR_ACTIVA = 365, 10, 2, 45
#: Palabras que no distinguen un cobro (además de GENERICAS): artículos, «cobro», «mensual», pedazos de dominios.
BUSCAR_VACIAS = {"DE", "DEL", "LA", "EL", "LOS", "LAS", "MI", "MIS", "TU", "SU", "UN", "UNA", "AL", "Y", "CON", "POR", "PARA", "EN", "QUE",
                 "MES", "MENSUAL", "COBRO", "COBROS", "CARGOS", "COM", "WWW", "NET", "ORG", "SPA", "LTDA", "INC", "LLC"}


def _palabras(texto):
    """Las palabras de un texto, sin tildes y en mayúsculas («Pago: Netflix.com» → PAGO, NETFLIX, COM)."""
    return [p for p in re.split(r"[^A-Z0-9]+", datos.normalizar(texto)) if p]


def palabras_busqueda(textos):
    """Las palabras con que se busca un cobro: completas, de 3 letras o más, sin números sueltos ni palabras que aparecen en
    cualquier movimiento (PAGO, COMPRA…: GENERICAS y BUSCAR_VACIAS). Como mucho 8."""
    r = []
    for t in textos if isinstance(textos, list) else [textos]:
        for p in _palabras(t):
            if len(p) >= 3 and not p.isdigit() and p not in GENERICAS and p not in BUSCAR_VACIAS and p not in r:
                r.append(p)
    return r[:8]


def buscar_serie(textos, movimientos, hoy, moneda, signo=None):
    """Un cobro (o ingreso) que se repite, buscado en los movimientos de los últimos BUSCAR_DIAS días. Solo corre en el computador.
    - Calza un movimiento que trae alguna de las palabras de `textos` (palabras_busqueda) como palabra completa, en la moneda
      principal y con el `signo` pedido (si se pide); si alguno las trae todas, solo los que las traen todas.
    - Serie: desde el más reciente hacia atrás, los del mismo signo con un monto a ±BUSCAR_VARIACION % de él; al menos
      BUSCAR_MESES meses distintos y no mucho más de uno al mes (si no, es un comercio frecuente, no un cobro).
    - Si hay varias, la que sigue activa (último cobro hace ≤ BUSCAR_ACTIVA días), después la de más meses, después la más reciente.
    Devuelve {signo, monto (el último), dia (el típico), frecuencia, buscar (la palabra que más calzó; empate, la más larga), categoria (la más usada),
    desde (el primer cobro), meses, veces, ultimas (3 fechas), ids, aproximado (si los montos variaron)} o None."""
    pal = palabras_busqueda(textos)
    if not pal:
        return None
    desde = _fecha(_num(hoy) - BUSCAR_DIAS)
    calzan = []
    for m in movimientos:
        if not desde < m["fecha"] <= hoy or not m["monto"] or (m.get("moneda") or moneda) != moneda:
            continue
        s = "gasto" if m["monto"] < 0 else "ingreso"
        palabras = set(_palabras(m.get("descripcion")))
        tiene = [p for p in pal if p in palabras]
        if tiene and (not signo or s == signo):
            calzan.append((m, tiene, s))
    if any(len(x[1]) == len(pal) for x in calzan):  # si alguno trae todas las palabras («Aguas Andinas»), solo esos
        calzan = [x for x in calzan if len(x[1]) == len(pal)]
    calzan.sort(key=lambda x: (x[0]["fecha"], x[0]["id"]), reverse=True)
    series, usados = [], set()
    for m, _, s in calzan:
        if m["id"] in usados:
            continue
        base = abs(m["monto"])
        miembros = [x for x in calzan if x[0]["id"] not in usados and x[2] == s and abs(abs(x[0]["monto"]) - base) <= base * BUSCAR_VARIACION / 100 + 1e-9]
        usados.update(x[0]["id"] for x in miembros)
        meses = {x[0]["fecha"][:7] for x in miembros}
        if len(meses) >= BUSCAR_MESES and len(miembros) * 2 <= len(meses) * 3:
            series.append((_num(miembros[0][0]["fecha"]) >= _num(hoy) - BUSCAR_ACTIVA, len(meses), miembros[0][0]["fecha"], s, miembros))
    if not series:
        return None
    _, n, _, s, miembros = max(series, key=lambda x: x[:3])
    movs = [x[0] for x in miembros]
    monto = abs(movs[0]["monto"])
    cuenta = {}
    for _, tiene, _ in miembros:
        for p in tiene:
            cuenta[p] = cuenta.get(p, 0) + 1
    palabra = sorted(cuenta, key=lambda p: (-cuenta[p], -len(p), p))[0]
    cats = {}
    for m in movs:
        if m.get("categoria"):
            cats[m["categoria"]] = cats.get(m["categoria"], 0) + 1
    categoria = max(cats, key=lambda c: (cats[c], -next(i for i, m in enumerate(movs) if m.get("categoria") == c))) if cats else ""
    r = {"signo": s, "monto": monto, "dia": _del_medio([int(m["fecha"][8:10]) for m in movs]), "frecuencia": "mensual", "buscar": [palabra],
         "categoria": categoria, "desde": movs[-1]["fecha"], "meses": n, "veces": len(movs), "ultimas": [m["fecha"] for m in movs[:3]],
         "ids": [m["id"] for m in movs]}
    if any(abs(m["monto"]) != monto for m in movs):
        r["aproximado"] = {"variacion": max(1, math.ceil(max(abs(abs(m["monto"]) - monto) for m in movs) / monto * 100 - 1e-9))}
    return r


def fijar_automaticos(hoy, movimientos=None):
    """Anota en compromisos.json los pagos reconocidos solos (con el movimiento que calzó), para que no cambien después.
    Nunca toca lo marcado a mano. Escribe solo si hay algo nuevo."""
    raw = leer()
    moneda = datos.presupuesto().get("moneda") or datos.config()["moneda"]
    lista = [c for c in validos(raw, hoy, moneda) if c.get("activo", True)]
    if not lista:
        return 0
    movs = datos.leer_todos() if movimientos is None else movimientos
    _, pagos, _ = asignar(lista, movs, hoy, moneda, (uf_config() or {}).get("valor"), palabras_mora(datos.config().get("pais") or "CL"))
    nuevos = 0
    _categorizar_mora(pagos, movs)
    for c in raw["compromisos"]:
        if not isinstance(c, dict):
            continue
        for clave, p in pagos.items():
            cid, periodo = clave.split("|", 1)
            if cid != c.get("id") or p["como"] != "automatico":
                continue
            e = c.setdefault("pagos", {}).setdefault(periodo, {}) if isinstance(c.get("pagos", {}), dict) else None
            if e is None:
                continue
            if e.get("como") == "automatico" and e.get("movimiento") == p["movimiento"] and e.get("mora") != p.get("mora"):
                if p.get("mora"):
                    e["mora"] = p["mora"]  # el interés por mora de ese pago (lo pagado de más y el cargo aparte)
                else:
                    e.pop("mora", None)
                nuevos += 1
            if e.get("como"):
                continue
            e.update({"como": "automatico", "fecha": p["fecha"], "movimiento": p["movimiento"], "monto": p["monto"],
                      **({"mora": p["mora"]} if p.get("mora") else {})})
            nuevos += 1
    if nuevos:
        escribir(raw)
    return nuevos


def _categorizar_mora(pagos, movimientos):
    """El cargo aparte por atraso queda en «Intereses y cargos» (si no tenía categoría; lo que eligió la persona no se toca)."""
    if not any(c["id"] == "intereses" for c in datos.categorias()):
        return
    por_id = {m["id"]: m for m in movimientos}
    for p in pagos.values():
        m = por_id.get((p.get("mora") or {}).get("movimiento"))
        if m and not m.get("categoria"):
            datos.cambiar(m["fecha"][:7], m["id"], {"categoria": "intereses"})
            m["categoria"] = "intereses"


def mora_del_anio(compromisos, movimientos, hoy, moneda, uf=None, mora=None):
    """Lo que se pagó este año (por la fecha del pago) en intereses por atraso: la suma de `mora` de cada pago (igual que moraDelAnio)."""
    activos = [c for c in compromisos if c.get("activo", True)]
    _, pagos, _ = asignar(activos, movimientos, hoy, moneda, (uf or {}).get("valor"), mora)
    return redondear(sum(p["mora"]["monto"] for p in pagos.values() if p.get("mora") and p["fecha"][:4] == hoy[:4] and p["fecha"] <= hoy))


# ───────────── Para conversar con Alcancía: margen, plan de préstamos y «ese pago era del mes pasado» (igual que ui/app.js) ─────────────
#: El plan de préstamos usa como máximo este % del margen mensual: el resto queda de colchón para imprevistos.
USO_MARGEN = 75
#: Ningún plan pasa de estos meses; sin datos para calcular el margen, se propone a MESES_SIN_DATOS.
MESES_MAX, MESES_SIN_DATOS = 60, 12


def _vigente(r, hoy):
    """Un compromiso (de estado_mes()["compromisos"]) que sigue pagándose cada mes: no es de una sola vez ni terminó."""
    if r["frecuencia"] == "una_vez" or (r.get("cuotas") and r["cuotas"]["quedan"] == 0):
        return False
    return not r.get("termina") or r["termina"] >= hoy


def margen_mensual(compromisos, movimientos, hoy, categorias, moneda, per=None, uf=None, auto=None, sin=()):
    """Cuánto queda libre en un mes normal: margen = ingreso típico − gasto típico − compromisos al mes. Igual que margenMensual.
    - Ingreso típico: los compromisos de tipo `ingreso` (el sueldo anotado o detectado) al mes, por su mínimo si varían; si no hay,
      el promedio de lo que entró en los últimos 3 periodos completos (sin lo de «Entre mis cuentas»). Lo que te deben no cuenta.
    - Gasto típico: el promedio de «Lo que gastaste» en esos mismos periodos, sin los movimientos que son pagos de un compromiso
      (los que calzan con alguno: `coincide`), para no contarlos dos veces.
    - Compromisos al mes: los gastos que siguen vigentes (no los de una vez ni los ya terminados), por su máximo si varían; en UF
      con el valor estimado (los que aún no se pueden estimar no entran y se cuentan en `sin_valor`).
    Sin periodos completos o sin ingreso conocido, `margen` es None.
    `sin`: ids de compromisos que no se restan (la persona dijo que una deuda del plan «es la misma» que ese compromiso: su cuota
    vuelve al margen para pagar el plan nuevo). Sus pagos siguen fuera del gasto típico, para no contarlos como gasto."""
    mes = periodo_de(hoy, per)
    en_moneda_ = [m for m in movimientos if (m.get("moneda") or moneda) == moneda]
    completos = [x for x in periodos_con_datos(en_moneda_, per) if x < mes][-3:]
    e = estado_mes(compromisos, movimientos, mes, hoy, moneda, per, uf, None, auto)
    vig = [r for r in e["compromisos"] if r["moneda"] == moneda and _vigente(r, hoy)]
    pres = {"moneda": moneda, "mensual": {}}
    ingreso, fuente = sum(_mensual(r, _minimo(r)) for r in vig if r["signo"] == "ingreso" and r["tipo"] == "ingreso"), "compromisos"
    if ingreso <= 0:
        ingreso, fuente = None, ""
        if completos:
            v = redondear(sum(resumen_periodo(en_moneda_, x, hoy, pres, categorias, per)["ingresos"] for x in completos) / len(completos))
            ingreso, fuente = (v, "promedio") if v > 0 else (None, "")
    activos = [c for c in compromisos if c.get("activo", True)]
    uv = (uf or {}).get("valor")
    propios = [m for m in en_moneda_ if not any(coincide(m, c, moneda, uv) for c in activos)]
    gasto = redondear(sum(resumen_periodo(propios, x, hoy, pres, categorias, per)["gastado"] for x in completos) / len(completos)) if completos else None
    comp = sum(_mensual(r, _maximo(r)) for r in vig if r["signo"] == "gasto" and r["id"] not in sin)
    margen = ingreso - gasto - comp if ingreso is not None and gasto is not None else None
    return {"ingreso": ingreso, "fuente": fuente, "gasto": gasto, "meses": len(completos), "compromisos": comp,
            "sin_valor": sum(1 for r in e["compromisos"] if r["original"] and r["original"]["sin_valor"]), "margen": margen}


def paso_cuota(v):
    """Una cuota fácil de recordar: a 10.000 desde 500.000, a 5.000 desde 50.000, a 1.000 desde 5.000 (y a 100, 10 o 1 más abajo)."""
    for tope, paso in ((500000, 10000), (50000, 5000), (5000, 1000), (500, 100), (50, 10)):
        if v >= tope:
            return paso
    return 1


def plan_prestamos(deudas, margen, moneda="CLP"):
    """Cuánto pagar al mes, y en cuántos meses, a cada persona que te prestó (igual que planPrestamos en ui/app.js).
    `deudas`: [{"con", "total", "interes"?}]. Se usa como máximo USO_MARGEN % del margen mensual (`disponible`; el resto es colchón).
    Se busca el menor número de meses N (hasta MESES_MAX) en que las cuotas, cada una redondeada hacia arriba (paso_cuota) desde
    lo que se debe ÷ N, caben en lo disponible: así todas terminan más o menos juntas y cada una pesa según lo que se debe.
    Cada deuda va en ⌈lo que se debe ÷ su cuota⌉ meses, con la última más chica (calcular_prestamo con la cuota fija).
    Si no cabe ni en MESES_MAX meses (o el margen no alcanza), `alcanza` es False, se propone a MESES_MAX meses (la cuota más chica)
    y `falta` dice cuánto se pasa al mes. Sin margen conocido, `alcanza` es None y se propone a MESES_SIN_DATOS meses."""
    pagar = [calcular_prestamo(d["total"], 1, d.get("interes") or 0, moneda)["pagar"] for d in deudas]
    disponible = None if margen is None else max(0, margen * USO_MARGEN // 100)

    def cuotas(n):
        return [math.ceil(p / (n * paso_cuota(p / n))) * paso_cuota(p / n) for p in pagar]
    elegido = None
    if disponible:
        elegido = next((n for n in range(1, MESES_MAX + 1) if sum(cuotas(n)) <= disponible), None)
    alcanza = None if margen is None else elegido is not None
    cs = cuotas(elegido or (MESES_SIN_DATOS if margen is None else MESES_MAX))
    detalle = []
    for d, p, c in zip(deudas, pagar, cs):
        n = max(1, math.ceil(p / c))
        k = calcular_prestamo(d["total"], n, d.get("interes") or 0, moneda, c)
        detalle.append({"con": d["con"], "total": d["total"], "interes": d.get("interes") or 0, "pagar": k["pagar"], "cuota": k["cuota"],
                        "ultima": k["ultima"], "cuotas": n})
    al_mes = sum(x["cuota"] for x in detalle)
    return {"margen": margen, "uso": USO_MARGEN, "disponible": disponible, "alcanza": alcanza, "al_mes": al_mes,
            "meses": max(x["cuotas"] for x in detalle), "falta": max(0, al_mes - (disponible or 0)) if alcanza is False else 0, "deudas": detalle}


def inicio_plan(per, hoy, feriados_):
    """Desde cuándo y qué día se pagan las cuotas de un plan: el día después del próximo sueldo (si el mes va de sueldo a sueldo);
    si no, el 1 del mes que viene. {"desde": "AAAA-MM-DD", "dia": 1–31}. Igual que inicioPlan en ui/app.js."""
    ps = proximo_sueldo(per, hoy, feriados_)
    if ps:
        return {"desde": _fecha(_num(ps["fecha"]) + 1), "dia": per["dia"] % 31 + 1}
    return {"desde": sumar_mes(hoy[:7], 1) + "-01", "dia": 1}


# ───────────── ¿Esa deuda ya está anotada? (préstamo parecido; igual que ui/app.js) ─────────────
#: Palabras que no dicen quién es la persona («mi», «préstamo de», «don»…) y apodos que dicen lo mismo («mami» = «mamá»).
VACIAS_PERSONA = {"MI", "MIS", "TU", "SU", "EL", "LA", "LOS", "LAS", "LO", "DE", "DEL", "AL", "CON", "Y", "PARA", "POR", "ME", "LE", "QUE",
                  "DON", "DONA", "SR", "SRA", "SENOR", "SENORA", "PRESTAMO", "PRESTAMOS", "DEUDA", "DEUDAS", "CREDITO", "PAGO", "CUOTA",
                  "CUOTAS", "PRESTO", "PRESTE", "MY", "THE", "LOAN", "DEBT", "FROM", "TO"}
APODOS = {"MAMI": "MAMA", "MAMITA": "MAMA", "MADRE": "MAMA", "MOM": "MAMA", "MOTHER": "MAMA", "PAPI": "PAPA", "PAPITO": "PAPA",
          "PADRE": "PAPA", "DAD": "PAPA", "FATHER": "PAPA", "ABUELITA": "ABUELA", "ABUELITO": "ABUELO", "TIITA": "TIA", "TIITO": "TIO"}
#: Un total es parecido a otro si la diferencia es a lo más este % del mayor.
PARECIDO = 15


def claves_persona(t):
    """Quién es la persona, para comparar: las palabras sin tildes ni mayúsculas, sin «mi», «préstamo de»… y con los apodos
    juntados («Mi mamá» → ["MAMA"]; «Préstamo de Tío Matías» → ["MATIAS", "TIO"]). Igual que clavesPersona."""
    return sorted({APODOS.get(p, p) for p in re.findall(r"[A-Z]+", datos.normalizar(t)) if len(p) > 1 and p not in VACIAS_PERSONA})


def total_parecido(a, b):
    """¿Dos totales parecidos (±PARECIDO % del mayor)? Sin uno de los dos, no."""
    return bool(a) and bool(b) and abs(a - b) * 100 <= PARECIDO * max(a, b)


def prestamos_parecidos(propuestas, compromisos, estado, hoy):
    """Para cada préstamo propuesto (del plan o uno nuevo: {"con", "nombre"?, "signo", "moneda"?, "total" o "prestamo": {"total"}}),
    el compromiso que ya está anotado y parece ser la misma deuda, o None. Igual que prestamosParecidos en ui/app.js.
    `estado` es estado_mes(...) del periodo (por las cuotas que quedan y lo que falta pagar).
    Candidatos: compromisos activos y vigentes de tipo préstamo o deuda, con el mismo signo (le debes / te deben) y la misma moneda.
    1. **La persona manda:** las claves de quién es (claves_persona) de la propuesta están todas en las del `con` del compromiso o al
       revés («Tío Matías» ~ «Matías»), o están todas en su nombre («Crédito con papá»). Sirve para préstamos y deudas.
    2. **Si no se sabe la persona** (la propuesta o el compromiso no dicen quién): un préstamo con el total anotado o lo que falta
       pagar parecido (±15 %). Si los dos dicen quién y no es la misma persona, no es la misma deuda aunque el monto calce.
    Entre varios, primero por persona, después el total más cercano y el id. Un compromiso sirve para una sola propuesta.
    Devuelve {"id", "nombre", "con", "tipo", "monto" (la cuota), "cuotas" ({"pagadas", "total", "quedan"} o None), "por_pagar",
    "total" (el del préstamo anotado o None), "motivo": "persona" | "monto"}."""
    raw = {c["id"]: c for c in compromisos if isinstance(c, dict)}
    tomados, r = set(), []
    for p in propuestas:
        pers = set(claves_persona(p.get("con") or p.get("nombre")))
        total = p.get("total") or (p.get("prestamo") or {}).get("total")
        moneda, signo = p.get("moneda") or estado["moneda"], p.get("signo") or "gasto"
        mejor = None
        for x in estado["compromisos"]:
            c = raw.get(x["id"])
            if (not c or x["id"] in tomados or x["tipo"] not in ("prestamo", "deuda") or x["signo"] != signo or x["moneda"] != moneda
                    or not _vigente(x, hoy)):
                continue
            con, nom = set(claves_persona(c.get("con"))), set(claves_persona(c.get("nombre")))
            persona = bool(pers) and ((bool(con) and (pers <= con or con <= pers)) or pers <= nom)
            original = (c.get("prestamo") or {}).get("total")
            cerca = [abs(v - total) for v in (original, x["por_pagar"]) if total_parecido(v, total)]
            if persona:
                rango_ = 0
            elif x["tipo"] == "prestamo" and cerca and not (pers and con):
                rango_ = 1
            else:
                continue
            clave = (rango_, min(cerca) if cerca else float("inf"), x["id"])
            if mejor is None or clave < mejor[0]:
                mejor = (clave, x, c)
        if not mejor:
            r.append(None)
            continue
        _, x, c = mejor
        tomados.add(x["id"])
        r.append({"id": x["id"], "nombre": x["nombre"], "con": c.get("con") or None, "tipo": x["tipo"], "monto": x["monto"],
                  "cuotas": x["cuotas"], "por_pagar": x["por_pagar"], "total": (c.get("prestamo") or {}).get("total"),
                  "motivo": "persona" if mejor[0][0] == 0 else "monto"})
    return r


def plan_variante(deudas, mismos, compromisos, movimientos, hoy, categorias, moneda, per=None, uf=None, auto=None):
    """El plan de préstamos cuando la persona dijo «es el mismo» (`mismos`: {índice de la deuda: id del compromiso}). Igual que
    planVariante en ui/app.js. Sin `mismos`, es el plan de siempre.
    - La cuota de esos compromisos vuelve al margen (margen_mensual con `sin`): ya no se cuenta dos veces.
    - Lo que se debe de esa deuda: si el total que dijo es parecido (±15 %) al total anotado (o, en una deuda sin total, a lo que
      falta), está hablando del mismo préstamo y se planifica **lo que falta pagar** (`por_pagar`, sin interés: ya lo incluye); si
      dijo otro total, ese es lo que debe ahora.
    - Todas las deudas del plan se recalculan con el margen corregido (plan_prestamos).
    Devuelve el plan con `base` (ingreso, gasto, meses y compromisos que se usaron)."""
    mismos = {int(j): cid for j, cid in mismos.items()}
    mg = margen_mensual(compromisos, movimientos, hoy, categorias, moneda, per, uf, auto, sin=set(mismos.values()))
    e = estado_mes(compromisos, movimientos, periodo_de(hoy, per), hoy, moneda, per, uf, None, auto) if mismos else {"compromisos": []}
    por_id = {r["id"]: r for r in e["compromisos"]}
    raw = {c["id"]: c for c in compromisos if isinstance(c, dict)}
    efectivas = []
    for j, d in enumerate(deudas):
        x, c = por_id.get(mismos.get(j)), raw.get(mismos.get(j)) or {}
        base = (c.get("prestamo") or {}).get("total") or (x or {}).get("por_pagar")
        if x and x["por_pagar"] and total_parecido(base, d["total"]):
            efectivas.append({"con": d["con"], "total": x["por_pagar"], "interes": 0})
        else:
            efectivas.append({"con": d["con"], "total": d["total"], "interes": d.get("interes") or 0})
    plan = plan_prestamos(efectivas, mg["margen"], moneda)
    plan["base"] = {k: mg[k] for k in ("ingreso", "fuente", "gasto", "meses", "compromisos")}
    return plan


def prestamo_actualizado(c, d, ini):
    """«Es el mismo»: el compromiso que ya estaba (`c`, tal como está en el archivo) con la deuda `d` del plan (con, total, interes,
    cuota, cuotas) desde `ini` (inicio_plan). Mantiene su id, nombre, palabras, categoría y forma de pago; pasa a ser un préstamo
    (si era una deuda) que parte de nuevo: lo que falta, en cuotas nuevas, sin cuotas pagadas. Sin validar (se valida al usarlo).
    Igual que prestamoActualizado en ui/app.js."""
    nuevo = {k: v for k, v in c.items() if k not in ("pagos", "fecha", "fecha_fin", "saldo", "aproximado", "cuotas_restantes")}
    nuevo.update({"tipo": "prestamo", "con": c.get("con") or d["con"], "prestamo": {"total": d["total"], "interes": d["interes"], "cuota": d["cuota"]},
                  "monto": d["cuota"], "cuotas_total": d["cuotas"], "cuotas_pagadas": 0, "frecuencia": "mensual", "dia": ini["dia"],
                  "desde": ini["desde"]})
    return nuevo


def pago_reasignable(compromisos, movimientos, cid, hoy, moneda, per=None, uf=None, mora=None):
    """«La hipoteca de este mes aún no la pago», pero aparece pagada: ese pago era del vencimiento anterior. Devuelve qué mover si
    el último vencimiento de este periodo tiene pago y el anterior no; si no, None. Igual que pagoReasignable en ui/app.js.
    {"id", "nombre", "de": {"periodo", "vence"}, "a": {"periodo", "vence"}, "pago": {"como", "fecha", "monto", "movimiento"?}}"""
    activos = [c for c in compromisos if c.get("activo", True)]
    c = next((x for x in activos if x["id"] == cid), None)
    if not c:
        return None
    inicio, fin = rango(periodo_de(hoy, per), per)
    ocs, pagos, _ = asignar(activos, movimientos, fin, moneda, (uf or {}).get("valor"), mora)
    mios = [o for cc, o in ocs if cc is c]
    pagados = [i for i, o in enumerate(mios) if inicio <= o["vence"] <= fin and f"{cid}|{o['periodo']}" in pagos]
    if not pagados or pagados[-1] == 0:
        return None
    de, a = mios[pagados[-1]], mios[pagados[-1] - 1]
    if f"{cid}|{a['periodo']}" in pagos:
        return None
    p = pagos[f"{cid}|{de['periodo']}"]
    return {"id": cid, "nombre": c["nombre"], "de": {"periodo": de["periodo"], "vence": de["vence"]},
            "a": {"periodo": a["periodo"], "vence": a["vence"]},
            "pago": {"como": p["como"], "fecha": p["fecha"], "monto": p["monto"], **({"movimiento": p["movimiento"]} if p.get("movimiento") else {})}}


def reasignar_pago(c, de, a, mov=None):
    """Mueve el pago del vencimiento `de` al anterior `a` en un compromiso tal como está en el archivo (lo cambia ahí mismo).
    Con un movimiento (`mov`, el de la cartola): `a` queda pagado con ese movimiento y `de` sin pago, con el movimiento en `no_es`
    (así no se vuelve a reconocer ahí). Sin movimiento, lo marcado a mano («ya lo pagué») pasa a `a`. Usa el formato de siempre
    de `pagos` (README): lo marcado así manda sobre lo que se reconoce solo. Devuelve "" o el problema. Igual que reasignarPago."""
    pagos = c.get("pagos") if isinstance(c.get("pagos"), dict) else {}
    d, x = dict(pagos.get(de) or {}), dict(pagos.get(a) or {})
    if not a < de:
        return "Solo se puede mover a un vencimiento anterior."
    if x.get("como"):
        return "Ese vencimiento ya tiene un pago."
    if mov:
        x["no_es"] = [i for i in x.get("no_es") or [] if i != mov["id"]]
        x.update({"como": "automatico", "fecha": mov["fecha"], "movimiento": mov["id"], "monto": abs(mov["monto"])})
        for k in ("como", "fecha", "movimiento", "monto", "mora"):
            d.pop(k, None)
        d["no_es"] = ([i for i in d.get("no_es") or [] if i != mov["id"]] + [mov["id"]])[-20:]
    elif d.get("como") == "manual":
        x.update({"como": "manual", **({"fecha": d["fecha"]} if d.get("fecha") else {})})
        for k in ("como", "fecha", "movimiento", "monto", "mora"):
            d.pop(k, None)
    else:
        return "No hay un pago que mover."
    for clave, v in ((a, x), (de, d)):
        if not v.get("no_es"):
            v.pop("no_es", None)
        if v:
            pagos[clave] = v
        else:
            pagos.pop(clave, None)
    c["pagos"] = pagos
    return ""


# ───────────── Avisos (la app de Mac los muestra como notificaciones del sistema) ─────────────
def avisos(hoy):
    """Lo que hay que avisar hoy: 3 días antes (o menos, si la app no estaba abierta), el día del vencimiento y si quedó
    atrasado. Una vez cada cosa por vencimiento y como máximo un aviso por compromiso al día. Solo gastos.
    Lo que se paga solo (modo_pago) no se recuerda: solo avisa `sin_cargo` si pasaron GRACIA_AUTO días y el cargo no aparece."""
    cfg = datos.config()
    if not cfg.get("avisos"):
        return {"ok": True, "avisos": []}
    moneda = datos.presupuesto().get("moneda") or cfg["moneda"]
    lista, movs = validos(None, hoy, moneda), datos.leer_todos()
    per, mes = periodo_actual(hoy, movs, lista)
    e = estado_mes(lista, movs, mes, hoy, moneda, per, uf_config(cfg), None, palabras_automatico(cfg.get("pais") or "CL"))
    reg = datos.leer_json(RUTA_AVISOS, {})
    enviados = reg.get("enviados", {}) if isinstance(reg.get("enviados"), dict) else {}
    por_dia = reg.get("por_dia", {}) if isinstance(reg.get("por_dia"), dict) else {}
    r = []
    for i in e["items"]:
        if i["signo"] != "gasto" or i["estado"] == "pagado":
            continue
        if i["modo_pago"] == "automatico":
            tipo = "sin_cargo" if i["estado"] == "atrasado" else None  # «atrasado» ya trae los días de gracia
        else:
            tipo = ("atrasado" if i["estado"] == "atrasado" else "hoy" if i["estado"] == "hoy"
                    else "pronto" if i["estado"] == "pendiente" and i["dias"] <= 3 else None)
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
