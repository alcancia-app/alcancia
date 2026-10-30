"""Conversar con Alcancía: un chat con la alcancía (la IA de la persona) para contarle lo que pasa con sus pagos y pedirle consejos.
Solo biblioteca estándar.

  chat.py enviar <entrada.json> <salida.json>   entrada: {"hoy": "AAAA-MM-DD", "mensajes": [{"rol": "persona"|"alcancia", "texto"}]}
  chat.py borrar <entrada.json> <salida.json>   borra la conversación guardada
  chat.py marcar <entrada.json> <salida.json>   {"id": "<mensaje>", "i": <n° de acción>, "j"?: <propuesta>,
                                                 "estado": "hecha"|"no"|"mismo"|"otro"}

Lo que escribe la persona llega en un archivo de entrada, nunca como argumento (los argumentos de un proceso los puede ver
cualquier programa del computador). Los últimos 10 mensajes pasan por `limpiar_texto` (sin RUT ni números de cuenta).

**Lo que ve la IA** (lo arma `contexto`, calculado por código, nunca la cartola): el periodo y los días que quedan, el ingreso típico,
el gasto típico sin compromisos, el total de compromisos al mes y el margen (`compromisos.margen_mensual`), las tres cifras en totales,
y por cada compromiso: una referencia opaca (C1, C2…), su nombre, tipo, monto o rango, frecuencia y día, si se paga solo, sus
palabras para reconocerlo, cuotas, el estado de este periodo y sus últimos 3 pagos (fecha, monto y a qué vencimiento se asignaron).
Nunca descripciones de movimientos, ids internos ni números de cuenta.

La IA responde {"respuesta", "acciones"}; se valida estricto y cada acción se resuelve con código (lista blanca): crear_compromiso,
plan_prestamos (cuotas y meses los calcula compromisos.plan_prestamos), reasignar_pago, marcar_pagado, marcar_pendiente,
editar_compromiso y buscar_pago. **Nada se aplica solo:** la interfaz muestra cada acción para que la persona la confirme.

**Buscar un cobro en sus movimientos** (la IA nunca ve los movimientos: busca el código, compromisos.buscar_serie, en los últimos
12 meses, incluidos los que trajeron los conectores como Mercado Pago):
- crear_compromiso incompleto (sin monto o sin día, mensual, que no es un préstamo): se busca con su nombre y sus palabras y, si hay
  una serie, la propuesta se completa (monto, día, palabra, categoría, desde y forma de pago) y trae `encontrado`
  {monto, dia, meses, veces, ultimas, aproximado?}. Si no hay nada, sigue incompleta y la nota «no_encontre_movimientos» lo dice.
- buscar_pago {texto}: si ya hay un compromiso que es ese cobro (sus palabras o reconoce los movimientos encontrados), una acción
  `anotado` sin botones con su último pago reconocido; si no, una propuesta de crear_compromiso completa con `encontrado`; si no hay
  nada, la nota «no_encontre_movimientos».
Cuando la búsqueda decide lo que pasó, la respuesta la escribe el código (`busqueda`: «encontre», «anotado» o «nada»; la interfaz la
muestra en su idioma), sin otra llamada a la IA: la IA no podía saber qué se iba a encontrar.

**¿Es el mismo préstamo?** Si un préstamo propuesto (en el plan o uno nuevo) se parece a uno que ya está anotado
(compromisos.prestamos_parecidos: primero la persona, después el total ±15 %), la acción trae `parecido` (crear) o `parecidos`
(plan, uno por propuesta o null) y la interfaz pregunta «¿Es el mismo?» antes de ofrecer «Agregar»:
- «Es otro»: la propuesta de siempre.
- «Es el mismo» (crear): `actualizar`, el compromiso que ya estaba con el total, las cuotas (y el día o la forma de pago, si la IA
  los dijo) de la propuesta; null si no hay nada que cambiar o la propuesta está incompleta.
- «Es el mismo» (plan): `variantes`, ya calculadas aquí con compromisos.plan_variante para cada combinación de «es el mismo»
  (clave: los índices de las propuestas, «0», «0,1»…): la cuota de ese compromiso vuelve al margen, se planifica lo que falta
  pagar y todas las deudas se recalculan; esa propuesta es el compromiso que ya estaba, actualizado (prestamo_actualizado).
  Se calcula todo al responder (determinista, sin otra llamada) y la interfaz solo elige: al reabrir se ve igual.
La elección queda en `estados` con la clave «es:<i>» o «es:<i>.<j>» («mismo» u «otro»).

La conversación se guarda solo en el computador: ~/Alcancia/.alcancia/chat.json (los últimos 50 mensajes, ya limpios).
"""
import json
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compromiso_ia  # noqa: E402
import compromisos as K  # noqa: E402
import consejos  # noqa: E402
import datos  # noqa: E402
import ia  # noqa: E402
import tu_ia  # noqa: E402
import resumen  # noqa: E402

RUTA = os.path.join(datos.INTERNO, "chat.json")
#: Mensajes que se guardan, turnos que ve la IA y largos máximos.
GUARDADOS, TURNOS, LARGO_PERSONA, LARGO_RESPUESTA = 50, 10, 500, 1200
#: Acciones que puede proponer la IA y los campos de cada una (cualquier otro campo hace que esa acción no sirva).
ACCIONES = {"crear_compromiso": {"tipo", "compromiso"}, "plan_prestamos": {"tipo", "deudas"}, "reasignar_pago": {"tipo", "compromiso"},
            "marcar_pagado": {"tipo", "compromiso"}, "marcar_pendiente": {"tipo", "compromiso"},
            "editar_compromiso": {"tipo", "compromiso", "cambios"}, "buscar_pago": {"tipo", "texto"}}
MAX_ACCIONES, MAX_DEUDAS, MAX_COMPROMISOS = 4, 4, 30
CAMBIOS = ("monto", "dia", "pago", "fecha_fin")


# ───────────── Conversación guardada (solo en este computador) ─────────────
def historial():
    h = datos.leer_json(RUTA, {})
    lista = h.get("mensajes") if isinstance(h, dict) else None
    return [m for m in lista if isinstance(m, dict) and m.get("rol") in ("persona", "alcancia")][-GUARDADOS:] if isinstance(lista, list) else []


def guardar(lista):
    datos.escribir_json(RUTA, {"formato": 1, "mensajes": lista[-GUARDADOS:]})


def nuevo_id():
    return "m-" + uuid.uuid4().hex[:10]


# ───────────── Lo que ve la IA ─────────────
def _n(x):
    """Un monto para la IA: con punto de miles («450.000»); con decimales, con coma («12,75»)."""
    if isinstance(x, float) and x != int(x):
        return f"{x:.4f}".rstrip("0").replace(".", ",")
    return f"{int(round(x)):,}".replace(",", ".")


def _monto(r):
    if r.get("original") and r["original"]["sin_valor"]:
        return f"{_n(r['original']['monto'])} UF (aún sin valor en pesos)"
    texto = _n(r["monto"])
    if r.get("rango"):
        texto = f"cerca de {texto} (entre {_n(r['rango']['min'])} y {_n(r['rango']['max'])})"
    if r.get("original"):
        texto = f"{_n(r['original']['monto'])} UF ≈ {texto}"
    return texto


def _frecuencia(c):
    f = c["frecuencia"]
    return {"mensual": f"cada mes, el día {c.get('dia')}", "semanal": f"cada semana (día {c.get('dia')}, 1 = lunes)",
            "anual": f"cada año, el {str(c.get('fecha'))[5:]}", "una_vez": f"una vez, el {c.get('fecha')}"}[f]


def _estado(i):
    if i["estado"] == "pagado":
        return f"pagado el {i['pago']['fecha']} ({_n(i['pago']['monto'])})"
    if i["estado"] == "pendiente":
        return f"pendiente (faltan {i['dias']} días)"
    if i["estado"] == "hoy":
        return "vence hoy, sin pago"
    if i["estado"] == "esperando":
        return "se paga solo; aún no aparece el cargo"
    return f"atrasado {i['dias']} días, sin pago"


class Ctx:
    """Todo lo que se calcula una vez por mensaje: sirve para armar el contexto y para resolver las acciones."""

    def __init__(self, hoy):
        self.hoy = hoy
        self.cfg = datos.config()
        pais = self.cfg.get("pais") or "CL"
        self.moneda = datos.presupuesto().get("moneda") or self.cfg["moneda"]
        self.movs = datos.leer_todos()
        self.categorias = datos.categorias()
        self.ids_cat = {c["id"] for c in self.categorias}
        self.lista = K.validos(None, hoy, self.moneda)
        self.activos = [c for c in self.lista if c.get("activo", True)][:MAX_COMPROMISOS]
        self.per, self.mes = K.periodo_actual(hoy, self.movs, self.lista)
        self.desde, self.hasta = resumen.rango(self.mes, self.per)
        self.uf, self.auto, self.mora = K.uf_config(self.cfg), K.palabras_automatico(pais), K.palabras_mora(pais)
        self.feriados = K.feriados(pais)
        self.estado = K.estado_mes(self.lista, self.movs, self.mes, hoy, self.moneda, self.per, self.uf, self.mora, self.auto)
        self.ocs, self.pagos, _ = K.asignar(self.activos, self.movs, self.hasta, self.moneda, (self.uf or {}).get("valor"), self.mora)
        self.margen = K.margen_mensual(self.lista, self.movs, hoy, self.categorias, self.moneda, self.per, self.uf, self.auto)
        self.refs = {f"C{n + 1}": c["id"] for n, c in enumerate(self.activos)}

    def reasignable(self, cid):
        return K.pago_reasignable(self.lista, self.movs, cid, self.hoy, self.moneda, self.per, self.uf, self.mora)


def contexto(x):
    """El texto con lo mínimo que la IA necesita para conversar (ver el docstring del módulo). Solo totales y compromisos."""
    m = x.margen
    quedan = max(0, resumen._dias(x.hoy, x.hasta) + 1) if x.desde <= x.hoy <= x.hasta else 0
    lineas = [f"Hoy es {x.hoy}. Moneda: {x.moneda} (montos con punto de miles).",
              f"Su mes va del {x.desde} al {x.hasta}" + (" (de sueldo a sueldo)" if x.per else " (mes calendario)") + f"; quedan {quedan} días."]
    ps = K.proximo_sueldo(x.per, x.hoy, x.feriados)
    if ps:
        lineas.append(f"Próximo sueldo: cerca del {ps['fecha']}.")
    lineas.append(f"Ingreso típico al mes: {_n(m['ingreso'])} ({'lo que tiene anotado como ingresos' if m['fuente'] == 'compromisos' else 'promedio de lo que entró'})."
                  if m["ingreso"] is not None else "Ingreso típico al mes: aún no lo sé (no hay sueldo anotado ni meses completos).")
    lineas.append(f"Gasto típico al mes, sin contar sus compromisos: {_n(m['gasto'])} (promedio de {m['meses']} meses)."
                  if m["gasto"] is not None else "Gasto típico al mes: aún no lo sé (no hay meses completos).")
    lineas.append(f"Compromisos al mes (lo que paga seguido, lo más que podría ser): {_n(m['compromisos'])}."
                  + (f" Hay {m['sin_valor']} en UF sin valor en pesos (no están sumados)." if m["sin_valor"] else ""))
    lineas.append(f"Margen mensual (ingreso típico − gasto típico − compromisos): {_n(m['margen'])}." if m["margen"] is not None
                  else "Margen mensual: aún no se puede calcular.")
    r = resumen.resumen(x.movs, x.mes, x.hoy, {"moneda": x.moneda, "mensual": {}}, x.categorias, x.per)
    lineas.append(consejos.linea_tres_cifras(x.hoy, x.movs, {"moneda": x.moneda}, x.lista, x.per)
                  + f" En este mes lleva gastado {_n(r['gastado'])}.")
    nombres_cat = {c["id"]: c["nombre"] for c in x.categorias}
    resumenes = {r_["id"]: r_ for r_ in x.estado["compromisos"]}
    comp = []
    for ref, cid in x.refs.items():
        c = next(cc for cc in x.activos if cc["id"] == cid)
        r_ = resumenes.get(cid) or {"monto": c["monto"], "rango": None, "original": None, "cuotas": None}
        modo = K.modo_pago(c, x.auto)
        partes = [f"{ref} · «{c['nombre']}»", c["tipo"] + (" (le pagan)" if c["signo"] == "ingreso" else ""), _monto(r_), _frecuencia(c)]
        if modo:
            partes.append("se paga solo" if modo == "automatico" else "lo paga la persona")
        if c.get("con"):
            partes.append(f"le debe a {c['con']}" if c["signo"] == "gasto" else f"{c['con']} le debe")
        if c.get("prestamo"):
            partes.append(f"préstamo de {_n(c['prestamo']['total'])} en total")
        if r_.get("cuotas"):
            partes.append(f"quedan {r_['cuotas']['quedan']} de {r_['cuotas']['total']} cuotas")
        if c.get("buscar"):
            partes.append("en la cartola dice: " + ", ".join(c["buscar"][:3]))
        if c.get("categoria") in nombres_cat:
            partes.append(f"categoría {nombres_cat[c['categoria']]}")
        comp.append(" · ".join(partes))
        for i in x.estado["items"]:
            if i["id"] == cid:
                comp.append(f"   {'mes anterior' if i['anterior'] else 'este mes'}: vence {i['vence']}, {_estado(i)}")
        venc = {o["periodo"]: o["vence"] for cc, o in x.ocs if cc["id"] == cid}
        pagos = sorted(((p["fecha"], venc.get(k.split("|", 1)[1], ""), p["monto"]) for k, p in x.pagos.items() if k.split("|", 1)[0] == cid), reverse=True)[:3]
        if pagos:
            comp.append("   últimos pagos: " + "; ".join(f"{f} ({_n(mo)}) → vencimiento del {v}" for f, v, mo in pagos))
        mover = x.reasignable(cid)
        if mover:
            comp.append(f"   ojo: si dice que el de este mes aún no lo paga, el pago del {mover['pago']['fecha']} era del vencimiento del "
                        f"{mover['a']['vence']} (que no tiene pago): propone reasignar_pago.")
    lineas += ["", "Sus compromisos (pagos que se repiten):"] + (comp or ["- (no ha anotado ninguno)"])
    lineas += ["", "Sus movimientos (cartolas y conexiones como Mercado Pago) no los ves uno por uno, pero la app puede buscar un cobro "
                   "en ellos: usa buscar_pago."]
    return "\n".join(lineas)


def prompt(x, mensajes):
    conversacion = "\n".join(("Persona" if m["rol"] == "persona" else "Alcancía") + f": «{m['texto']}»" for m in mensajes[:-1])
    return f"""Eres Alcancía, la alcancía (un chanchito) de una app de finanzas personales. Conversas con la persona dueña de la app:
cercana, cálida, honesta y práctica, con frases cortas y sin sermones. Responde en el idioma en que te escribe. No inventes datos:
usa solo lo de abajo y, si algo no está, dilo. No recomiendes productos financieros, bancos ni inversiones.

Lo que sé de sus finanzas (lo calculó la app):
{contexto(x)}

Conversación anterior:
{conversacion or '(es el primer mensaje)'}

Último mensaje de la persona: «{mensajes[-1]['texto']}»

Responde SOLO con un objeto JSON, sin nada antes ni después: {{"respuesta": "...", "acciones": [...]}}
- respuesta: de 1 a 4 frases cortas para la persona.
- acciones: de 0 a 3 de esta lista. Nada se aplica solo: la app le muestra cada una para que la confirme. Para referirte a un
  compromiso usa su referencia (C1, C2…), nunca otra cosa.
  1. {{"tipo": "crear_compromiso", "compromiso": {{...}}}}: cuando cuenta algo que paga o recibe seguido y no está en la lista.
     Si no sabe el monto o el día, propónlo igual con lo que sepas (el nombre y cómo aparece en la cartola): la app lo busca en
     sus movimientos y lo completa.
     Si es un préstamo y crees que ya está en la lista (la misma persona o un total parecido), propónlo igual y dile en la
     respuesta que ya tiene uno anotado: la app le pregunta si es el mismo.
     Campos del compromiso (usa solo estos; los que no sepas, déjalos fuera):
{compromiso_ia.campos(x.categorias, x.moneda)}
  2. {{"tipo": "plan_prestamos", "deudas": [{{"con": "Mamá", "total": 1500000, "interes": 0}}]}}: cuando le prestaron plata
     personas (familia, amigos) y pregunta cuánto puede pagar al mes o en cuántos meses. Una deuda por persona; «interes» solo si lo
     dice. No calcules cuotas ni meses ni los pongas en la respuesta: la app los calcula con su margen y le muestra la propuesta.
     Si una deuda parece estar ya en sus compromisos (por ejemplo «Préstamo de Mamá»), inclúyela igual y dile en la respuesta
     que ya tiene algo anotado con esa persona: la app le pregunta si es el mismo y, si lo es, recalcula sin contarlo dos veces.
  3. {{"tipo": "reasignar_pago", "compromiso": "C1"}}: cuando dice que algo de este mes aún no lo paga (o que un pago era del mes
     pasado) y ese compromiso aparece pagado este mes. Entiende sinónimos: dividendo = hipoteca = crédito hipotecario; luz =
     electricidad; arriendo = alquiler.
  4. {{"tipo": "marcar_pagado", "compromiso": "C1"}}: cuando dice que ya pagó algo que aparece pendiente o atrasado.
  5. {{"tipo": "marcar_pendiente", "compromiso": "C1"}}: cuando algo aparece pagado y dice que no lo ha pagado, y no hay un
     vencimiento anterior sin pago (si lo hay, usa reasignar_pago).
  6. {{"tipo": "editar_compromiso", "compromiso": "C1", "cambios": {{"monto": 0, "dia": 0, "pago": "manual", "fecha_fin": "AAAA-MM-DD"}}}}:
     cuando cambia algo de un compromiso (solo los campos que cambian).
  7. {{"tipo": "buscar_pago", "texto": "Netflix"}}: cuando pide buscar un cobro, pregunta cuánto o cuándo le cobran (o le pagan)
     algo, o no sabe el monto de algo que paga seguido. texto: solo el nombre del comercio o del cobro, corto. Tú no ves sus
     movimientos, pero la app sí: busca con código en los de los últimos 12 meses (sus cartolas y lo que trajeron sus conexiones,
     como Mercado Pago) y le muestra lo que encontró. Nunca digas que no puedes buscarlo: propón buscar_pago. En la respuesta
     dile solo que lo vas a buscar; no inventes montos ni fechas.
  Si se atrasó con algo, dile con calma qué falta y cuándo vence; si hay interés por mora, menciónalo."""


# ───────────── Validar lo que responde la IA y resolver las acciones con código ─────────────
def validar_respuesta(texto):
    """(respuesta o None si no sirve, acciones válidas, cuántas se descartaron). Estricto: un objeto con «respuesta» (texto) y
    «acciones» (lista, opcional), nada más. Las acciones que no están en la lista blanca o traen campos de más se descartan."""
    j = compromiso_ia.leer_json(texto)
    if j is None or set(j) - {"respuesta", "acciones"} or not isinstance(j.get("respuesta"), str):
        return None, [], 0
    respuesta = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", j["respuesta"]).strip()[:LARGO_RESPUESTA]
    if not respuesta:
        return None, [], 0
    crudas = j.get("acciones", [])
    if not isinstance(crudas, list):
        return None, [], 0
    buenas, malas = [], 0
    for a in crudas[:MAX_ACCIONES]:
        if isinstance(a, dict) and a.get("tipo") in ACCIONES and set(a) == ACCIONES[a["tipo"]]:
            buenas.append(a)
        else:
            malas += 1
    return respuesta, buenas, malas + max(0, len(crudas) - MAX_ACCIONES)


def _sin_pagos(c):
    return {k: v for k, v in c.items() if k != "pagos"}


def _variante(deudas, mismos, x, ini):
    """{"plan", "propuestas"} con las deudas que la persona dijo que «son el mismo» (`mismos`: {j: id}); None si algo no valida.
    Las propuestas van en el orden de las deudas: un préstamo nuevo o, en las de `mismos`, el compromiso que ya estaba actualizado."""
    plan = K.plan_variante(deudas, mismos, x.lista, x.movs, x.hoy, x.categorias, x.moneda, x.per, x.uf, x.auto)
    actuales = {c["id"]: c for c in x.lista}
    propuestas = []
    for j, d in enumerate(plan["deudas"]):
        if j in mismos:
            bruto = K.prestamo_actualizado(actuales[mismos[j]], d, ini)
        else:
            bruto = {"tipo": "prestamo", "con": d["con"], "signo": "gasto", "prestamo": {"total": d["total"], "interes": d["interes"], "cuota": d["cuota"]},
                     "cuotas_total": d["cuotas"], "frecuencia": "mensual", "dia": ini["dia"], "desde": ini["desde"], "pago": "manual", "origen": "ia"}
        c, _ = K.validar(bruto, x.ids_cat, x.hoy, x.moneda)
        if not c:
            return None
        propuestas.append(_sin_pagos(c))
    return {"plan": plan, "propuestas": propuestas}


#: Lo que se compara para saber si «actualizar» cambia algo.
COMPARAR = ("tipo", "con", "monto", "cuotas_total", "cuotas_pagadas", "dia", "prestamo", "pago", "fecha_fin")


def _parecido_al_crear(dicho, completo, propuesto, x):
    """Un préstamo nuevo que se parece a uno anotado: {"parecido", "actualizar"} (o {} si no hay parecido). `actualizar` es el que
    ya estaba con el total, el interés y las cuotas de la propuesta (y el día, las cuotas pagadas o la forma de pago solo si la IA
    los dijo); su id, nombre, palabras, categoría, desde y pagos se mantienen. None si la propuesta está incompleta o no cambia nada."""
    p = K.prestamos_parecidos([propuesto], x.lista, x.estado, x.hoy)[0]
    if not p:
        return {}
    actual = next(c for c in x.lista if c["id"] == p["id"])
    nuevo = None
    if completo:
        cambios = {"tipo": "prestamo", "con": actual.get("con") or completo["con"], "cuotas_total": completo["cuotas_total"],
                   "prestamo": {k: completo["prestamo"][k] for k in ("total", "interes", "cuota")}}
        cambios.update({k: completo[k] for k in ("dia", "cuotas_pagadas", "pago") if k in dicho and k in completo})
        base = {k: v for k, v in actual.items() if k not in ("fecha", "fecha_fin", "saldo", "aproximado", "cuotas_restantes")}
        limpio, _ = K.validar({**base, **cambios}, x.ids_cat, x.hoy, x.moneda)
        if limpio and any(limpio.get(k) != actual.get(k) for k in COMPARAR):
            nuevo = _sin_pagos(limpio)
    return {"parecido": p, "actualizar": nuevo}


# ───────────── Buscar un cobro en los movimientos (con código: la IA nunca los ve) ─────────────
def _textos(p):
    """Con qué se busca una propuesta: su nombre y sus palabras para la cartola."""
    b = p.get("buscar")
    b = b.split(",") if isinstance(b, str) else b if isinstance(b, list) else []
    return [str(p.get("nombre") or "")] + [v for v in b if isinstance(v, str)]


def _ultimo_pago(x, cid):
    ps = [p for k, p in x.pagos.items() if k.split("|", 1)[0] == cid and p.get("fecha")]
    p = max(ps, key=lambda p: p["fecha"], default=None)
    return {"fecha": p["fecha"], "monto": p["monto"]} if p else None


def _ya_anotado(pal, serie, x):
    """El compromiso activo que ya es ese cobro: todas las palabras buscadas están en su nombre o en sus palabras, o reconoce
    alguno de los movimientos encontrados (compromisos.coincide). None si no hay."""
    por_id = {m["id"]: m for m in x.movs} if serie else {}
    for c in x.activos:
        if set(pal) <= set(K.palabras_busqueda([c["nombre"]] + list(c.get("buscar") or []))):
            return c
        if serie and any(K.coincide(por_id[i], c, x.moneda, (x.uf or {}).get("valor")) for i in serie["ids"] if i in por_id):
            return c
    return None


def _anotado(c, x):
    return {"nombre": c["nombre"], "tipo": c["tipo"], "categoria": c.get("categoria") or "", "monto": c["monto"], "moneda": c["moneda"],
            "frecuencia": c["frecuencia"], "dia": c.get("dia"), "fecha": c.get("fecha"), "ultimo": _ultimo_pago(x, c["id"])}


def _encontrado(serie):
    """Lo que la tarjeta muestra de dónde salió la propuesta (solo cifras y fechas: ni descripciones ni ids)."""
    return {k: serie[k] for k in ("monto", "dia", "meses", "veces", "ultimas", "aproximado") if k in serie}


def _desde_serie(p, serie, x):
    """La propuesta `p` completada con la serie encontrada: lo que la IA dijo bien se mantiene; el monto, el día, la frecuencia, la
    palabra, la categoría, desde (el primer cobro) y la forma de pago salen de los movimientos. (compromiso limpio o None, problemas)."""
    c = {k: v for k, v in p.items() if k in K.CAMPOS_IA and k not in ("fecha", "cuotas_restantes")}
    c["frecuencia"], c["signo"] = "mensual", serie["signo"]
    if K._numero(c.get("monto"), 0, 1e12) is None:
        c["monto"] = serie["monto"]
        if serie.get("aproximado") and not c.get("aproximado"):
            c["aproximado"] = serie["aproximado"]
    if K._entero(c.get("dia"), 1, 31) is None:
        c["dia"] = serie["dia"]
    c["buscar"] = serie["buscar"] + [b for b in K.limpiar_buscar(c.get("buscar"), True) if b != serie["buscar"][0]]
    if c.get("categoria") not in x.ids_cat:
        c["categoria"] = serie["categoria"] if serie["categoria"] in x.ids_cat else ""
    if not K.limpiar_nombre(c.get("nombre")):
        c["nombre"] = serie["buscar"][0].capitalize()
    if c.get("tipo") not in K.TIPOS or (c["tipo"] == "ingreso") != (serie["signo"] == "ingreso"):
        cat = c["categoria"]
        c["tipo"] = ("ingreso" if serie["signo"] == "ingreso" else "suscripcion" if cat == "suscripciones"
                     else "cuenta" if cat in ("cuentas", "casa", "educacion") else "otro")
    if c.get("pago") not in K.PAGOS:
        c.pop("pago", None)
        modo = K.modo_pago(c, x.auto)
        if modo:
            c["pago"] = modo
    limpio, problemas = K.validar(c, x.ids_cat, x.hoy, x.moneda, estricto=True)
    if limpio:
        limpio["desde"] = serie["desde"]  # desde el primer cobro: los que ya pasaron quedan pagados con su movimiento
    return limpio, problemas


def _completar(p, x):
    """Una propuesta incompleta (sin monto o sin día, mensual, en la moneda principal y que no es un préstamo): (acción, nota) si se
    buscó en los movimientos, o None si no corresponde buscar."""
    if not isinstance(p, dict) or p.get("tipo") == "prestamo" or p.get("frecuencia") not in (None, "mensual") or p.get("moneda") not in (None, x.moneda):
        return None
    pal = K.palabras_busqueda(_textos(p))
    if not pal:
        return None
    signo = p.get("signo") if p.get("signo") in ("gasto", "ingreso") else "ingreso" if p.get("tipo") == "ingreso" else "gasto"
    serie = K.buscar_serie(_textos(p), x.movs, x.hoy, x.moneda, signo)
    dicho = K._numero(p.get("monto"), 0, 1e12)
    if serie and dicho and abs(serie["monto"] - dicho) > dicho * K.BUSCAR_VARIACION / 100:
        serie = None  # dijo un monto y lo encontrado es otra cosa («arriendo de la bodega» no es el arriendo del depto)
    ya = _ya_anotado(pal, serie, x)
    if ya:
        return {"tipo": "buscar_pago", "anotado": _anotado(ya, x)}, None
    if not serie:
        return None, "no_encontre_movimientos"
    limpio, _ = _desde_serie(p, serie, x)
    if not limpio:
        return None
    return {"tipo": "crear_compromiso", "compromiso": {**_sin_pagos(limpio), "origen": "ia"}, "encontrado": _encontrado(serie)}, None


def buscar_pago(texto, x):
    """La acción buscar_pago: (acción, nota). Ya anotado → `anotado`; una serie → una propuesta completa con `encontrado`; nada →
    nota «no_encontre_movimientos». El texto pasa por limpiar_texto (sin RUT ni números de cuenta)."""
    texto = compromiso_ia.limpiar_texto(texto, 80) if isinstance(texto, str) else ""
    pal = K.palabras_busqueda(texto)
    if not pal:
        return None, "no_aplica"
    serie = K.buscar_serie([texto], x.movs, x.hoy, x.moneda)
    ya = _ya_anotado(pal, serie, x)
    if ya:
        return {"tipo": "buscar_pago", "anotado": _anotado(ya, x)}, None
    if not serie:
        return None, "no_encontre_movimientos"
    corto = re.sub(r"\s+", " ", texto).strip()
    nombre = corto[:1].upper() + corto[1:] if len(corto) <= 40 and len(corto.split()) <= 4 else serie["buscar"][0].capitalize()
    limpio, _ = _desde_serie({"nombre": nombre}, serie, x)
    if not limpio:
        return None, "no_aplica"
    return {"tipo": "crear_compromiso", "compromiso": {**_sin_pagos(limpio), "origen": "ia"}, "encontrado": _encontrado(serie)}, None


def resolver(a, x):
    """(acción para la interfaz, nota). La nota es un código que la interfaz explica («no_aplica», «sin_pago_para_mover»…)."""
    t = a["tipo"]
    if t == "crear_compromiso":
        if not isinstance(a["compromiso"], dict):
            return None, "no_aplica"
        p = K.completar_prestamo(a["compromiso"], x.cfg)
        limpio, problemas = K.validar(p, x.ids_cat, x.hoy, x.moneda, estricto=True)
        if limpio:
            r = {"tipo": t, "compromiso": {**_sin_pagos(limpio), "origen": "ia"}}
        else:
            completo = _completar(p, x)  # ¿Está en sus movimientos? Se busca con código y se completa (monto, día, palabra…).
            if completo and completo[0]:
                return completo
            # Nunca sin salida: lo que sí se entendió va a la tarjeta, para completarlo en el editor.
            r = {"tipo": t, "compromiso": {**K.parcial(p, x.ids_cat, x.moneda, x.cfg), "origen": "ia"}, "incompleto": True,
                 "error": " ".join(problemas[:3])}
            if completo:
                return r, completo[1]
        if r["compromiso"].get("tipo") == "prestamo":
            r.update(_parecido_al_crear(a["compromiso"], r["compromiso"] if limpio else None, r["compromiso"], x))
        return r, None
    if t == "buscar_pago":
        return buscar_pago(a["texto"], x)
    if t == "plan_prestamos":
        deudas = []
        for d in a["deudas"] if isinstance(a["deudas"], list) else []:
            if not isinstance(d, dict) or set(d) - {"con", "total", "interes"}:
                continue
            con, total = K.limpiar_con(d.get("con")), K._numero(d.get("total"), 0, 1e12)
            interes = K._numero(d.get("interes", 0) or 0, -0.01, 100.01)
            if con and total and interes is not None:
                deudas.append({"con": con, "total": total, "interes": interes})
        deudas = deudas[:MAX_DEUDAS]
        if not deudas:
            return None, "no_aplica"
        ini = K.inicio_plan(x.per, x.hoy, x.feriados)
        base = _variante(deudas, {}, x, ini)
        if not base:
            return None, "no_aplica"
        r = {"tipo": t, **base}
        parecidos = K.prestamos_parecidos([{"con": d["con"], "signo": "gasto", "moneda": x.moneda, "total": d["total"]} for d in deudas],
                                          x.lista, x.estado, x.hoy)
        con = [j for j, p in enumerate(parecidos) if p]
        if con:  # «¿Es el mismo?»: cada combinación de respuestas, ya calculada (como mucho 2^MAX_DEUDAS planes chicos)
            variantes = {}
            for n in range(1, 2 ** len(con)):
                js = [j for k, j in enumerate(con) if n >> k & 1]
                v = _variante(deudas, {j: parecidos[j]["id"] for j in js}, x, ini)
                if v:
                    variantes[",".join(map(str, js))] = v
            r.update({"parecidos": parecidos, "variantes": variantes})
        return r, None
    cid = x.refs.get(str(a["compromiso"]).strip().upper())
    c = next((cc for cc in x.activos if cc["id"] == cid), None)
    if not c:
        return None, "no_encontre"
    mover = x.reasignable(cid) if t in ("reasignar_pago", "marcar_pendiente") else None
    if mover:  # «aún no la pago» con un pago este mes y el anterior sin pago: era del mes pasado (aunque la IA dijera otra cosa)
        return {"tipo": "reasignar_pago", **mover}, None
    if t == "reasignar_pago":
        t = "marcar_pendiente"  # no hay un vencimiento anterior sin pago: lo que queda es dejar este pendiente (si está pagado)
    items = [i for i in x.estado["items"] if i["id"] == cid]
    if t == "marcar_pagado":
        i = next((i for i in items if i["estado"] != "pagado"), None)
        if not i:
            return None, "ya_pagado"
        return {"tipo": t, "id": cid, "nombre": c["nombre"], "periodo": i["periodo"], "vence": i["vence"], "signo": c["signo"]}, None
    if t == "marcar_pendiente":
        i = next((i for i in reversed(items) if i["estado"] == "pagado" and not i["anterior"]), None)
        if not i:
            return None, "sin_pago_para_mover" if a["tipo"] == "reasignar_pago" else "ya_pendiente"
        return {"tipo": t, "id": cid, "nombre": c["nombre"], "periodo": i["periodo"], "vence": i["vence"],
                "pago": {k: i["pago"][k] for k in ("como", "fecha", "monto", "movimiento") if k in i["pago"]}}, None
    # editar_compromiso: cambios acotados sobre lo guardado (sus pagos y desde se mantienen al guardar).
    cambios = a["cambios"] if isinstance(a["cambios"], dict) else {}
    cambios = {k: v for k, v in cambios.items() if k in CAMBIOS and not (k == "monto" and c["tipo"] == "prestamo")}
    if not cambios:
        return None, "no_aplica"
    limpio, _ = K.validar({**c, **cambios}, x.ids_cat, x.hoy, x.moneda)
    if not limpio:
        return None, "no_aplica"
    antes = {k: c.get(k) for k in cambios}
    nuevos = {k: limpio.get(k) for k in cambios}
    if antes == nuevos:
        return None, "sin_cambios"
    return {"tipo": t, "id": cid, "nombre": c["nombre"], "antes": antes, "cambios": nuevos, "compromiso": _sin_pagos(limpio)}, None


def _busqueda(a, r, nota):
    """Si esta acción buscó en los movimientos y eso decide la respuesta: {"resultado", ...cifras, "texto"} («encontre», «anotado» o
    «nada»). La interfaz la muestra en su idioma; `texto` (en español) es lo que queda en la conversación y ve la IA después:
    solo el nombre, el monto y el día."""
    if r and r.get("encontrado"):
        c = r["compromiso"]
        return {"resultado": "encontre", "nombre": c["nombre"], "monto": c["monto"], "dia": c["dia"], "aproximado": bool(c.get("aproximado")),
                "texto": f"Lo encontré en tus movimientos: {c['nombre']}, {'cerca de ' if c.get('aproximado') else ''}${_n(c['monto'])} "
                         f"el día {c['dia']}. ¿Lo agrego?"}
    if r and r.get("anotado"):
        return {"resultado": "anotado", "nombre": r["anotado"]["nombre"], "texto": f"Ya lo tienes anotado: «{r['anotado']['nombre']}»."}
    if nota == "no_encontre_movimientos" and a.get("tipo") == "buscar_pago":
        return {"resultado": "nada", "texto": "No lo vi en tus movimientos de los últimos 12 meses. Si me dices cuánto es y qué día, lo anoto."}
    return None


def enviar(entrada):
    """Un mensaje de la persona → la respuesta de Alcancía. Nunca deja a la persona sin respuesta: si la IA falla o responde mal,
    devuelve un mensaje honesto (y lo guarda) en vez de nada."""
    hoy = str(entrada.get("hoy") or "")
    if not K._fecha_valida(hoy):
        return {"ok": False, "error": "Fecha inválida."}
    crudos = entrada.get("mensajes") if isinstance(entrada.get("mensajes"), list) else []
    mensajes = []
    for m in crudos[-TURNOS:]:
        if isinstance(m, dict) and m.get("rol") in ("persona", "alcancia") and isinstance(m.get("texto"), str):
            largo = LARGO_PERSONA if m["rol"] == "persona" else LARGO_RESPUESTA
            texto = compromiso_ia.limpiar_texto(m["texto"], largo)
            if texto:
                mensajes.append({"rol": m["rol"], "texto": texto})
    if not mensajes or mensajes[-1]["rol"] != "persona" or len(mensajes[-1]["texto"]) < 2:
        return {"ok": False, "error": "Escríbeme algo y te respondo."}
    if not ia.comando(ia.elegida()):
        return {"ok": False, "sin_ia": True, "error": f"Para conversar necesito tu IA y no encontré {ia.nombre()} en este computador. "
                                                       "Revisa en Ajustes → Tu IA."}
    lista = historial()
    persona = {"id": nuevo_id(), "rol": "persona", "texto": mensajes[-1]["texto"], "fecha": hoy}
    x = Ctx(hoy)
    respuesta, fallo = ia.preguntar(prompt(x, mensajes), timeout=240)
    error = tu_ia.frase(fallo)
    acciones, notas, busqueda = [], [], None
    if not error:
        texto, crudas, descartadas = validar_respuesta(respuesta)
        if texto is None:
            error = f"{ia.nombre()} no respondió como esperaba. Inténtalo de nuevo con otras palabras."
        else:
            vistas = set()
            for a in crudas:
                r, nota = resolver(a, x)
                # La misma serie (o el mismo compromiso anotado) una sola vez, aunque la IA haya pedido crear y buscar lo mismo.
                k = (("serie", tuple(r["encontrado"]["ultimas"])) if r and r.get("encontrado") else ("anotado", r["anotado"]["nombre"])
                     if r and r.get("anotado") else None)
                if k in vistas:
                    continue
                if k:
                    vistas.add(k)
                if r:
                    acciones.append(r)
                if nota and nota not in notas:
                    notas.append(nota)
                if busqueda is None:
                    busqueda = _busqueda(a, r, nota)
            if descartadas:
                notas.append("descartadas")
            if busqueda:  # la IA no podía saber qué se iba a encontrar: la respuesta la arma el código
                texto = busqueda.pop("texto")
    if error:
        mensaje = {"id": nuevo_id(), "rol": "alcancia", "texto": error, "error": True, "fecha": hoy}
        guardar(lista + [persona, mensaje])
        return {"ok": False, "error": error, "persona": persona, "mensaje": mensaje}
    mensaje = {"id": nuevo_id(), "rol": "alcancia", "texto": texto, "acciones": acciones, "notas": notas, "estados": {}, "fecha": hoy}
    if busqueda:
        mensaje["busqueda"] = busqueda
    guardar(lista + [persona, mensaje])
    return {"ok": True, "persona": persona, "mensaje": mensaje}


def marcar(entrada):
    """La persona confirmó («hecha») o descartó («no») una acción (`i`; en un plan, también la propuesta `j`): se recuerda para no
    volver a ofrecerla. «mismo» u «otro» es lo que respondió a «¿Es el mismo?» (solo donde hay un préstamo parecido); se guarda
    aparte, con la clave «es:<i>» o «es:<i>.<j>»."""
    lista = historial()
    m = next((m for m in lista if m.get("id") == entrada.get("id") and m.get("rol") == "alcancia"), None)
    acciones = (m.get("acciones") or []) if m else []
    i, j = entrada.get("i"), entrada.get("j")
    entero = lambda v, n: not isinstance(v, bool) and isinstance(v, int) and 0 <= v < n
    if not entero(i, len(acciones)) or entrada.get("estado") not in ("hecha", "no", "mismo", "otro"):
        return {"ok": False, "error": "No encontré esa acción."}
    if j is not None and not entero(j, len(acciones[i].get("propuestas") or [])):
        return {"ok": False, "error": "No encontré esa acción."}
    clave = f"{i}.{j}" if j is not None else str(i)
    if entrada["estado"] in ("mismo", "otro"):
        a = acciones[i]
        if not (a.get("parecido") if j is None else (a.get("parecidos") or [None] * (j + 1))[j]):
            return {"ok": False, "error": "No encontré esa acción."}
        clave = "es:" + clave
    m["estados"] = {**(m.get("estados") if isinstance(m.get("estados"), dict) else {}), clave: entrada["estado"]}
    guardar(lista)
    return {"ok": True}


def borrar(_entrada=None):
    try:
        os.remove(RUTA)
    except FileNotFoundError:
        pass
    return {"ok": True}


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("enviar", "borrar", "marcar"):
        print(__doc__)
        sys.exit(2)
    e = datos.leer_json(sys.argv[2], {})
    e = e if isinstance(e, dict) else {}
    r = {"enviar": enviar, "borrar": borrar, "marcar": marcar}[sys.argv[1]](e)
    datos.escribir_json(sys.argv[3], r)
    print(json.dumps(r, ensure_ascii=False)[:400])
