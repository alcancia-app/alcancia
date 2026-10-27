"""Alcancía como servidor MCP: tu propia IA (Claude, ChatGPT/Codex, Gemini…) puede consultar tus finanzas. Solo biblioteca estándar.

Corre en tu computador, lo arranca tu IA cuando lo necesita y habla por la entrada y salida estándar (MCP sobre stdio, JSON-RPC 2.0).
No abre puertos, no sale a internet y **solo lee**: no puede cambiar, borrar ni mover nada de ~/Alcancia.

Lo que tu IA consulta viaja a tu proveedor de IA con tu cuenta, igual que si se lo pegaras en el chat. Nunca hay números de cuenta,
RUT ni claves en los datos de Alcancía, así que tampoco aquí.

Conectarlo: Alcancía → Conexiones → «Tu IA, fuera de Alcancía» lo hace por ti. A mano (ruta de tu Python y de este archivo):
  claude mcp add --scope user alcancia -- python3 /ruta/a/bin/mcp_servidor.py
  codex mcp add alcancia -- python3 /ruta/a/bin/mcp_servidor.py
  gemini mcp add -s user alcancia python3 /ruta/a/bin/mcp_servidor.py
  Claude Desktop: "mcpServers": {"alcancia": {"command": "python3", "args": ["/ruta/a/bin/mcp_servidor.py"]}}
"""
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import categorizar  # noqa: E402
import compromisos as K  # noqa: E402
import datos  # noqa: E402
import resumen as resumen_mod  # noqa: E402

VERSIONES = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
LIMITE_FILAS = 200
INSTRUCCIONES = """Alcancía guarda los movimientos bancarios de la persona (sus cartolas y cuentas conectadas) en su computador.
Montos: negativo = gasto, positivo = ingreso, en la moneda indicada. Las transferencias entre cuentas propias (categoría de tipo
"neutro") no son gasto ni ingreso. Fechas en AAAA-MM-DD. Si falta un mes o un rango, usa el mes actual.
Para preguntas de totales usa gastos_por_categoria o resumen_del_mes; para detalles, buscar_movimientos; para lo que falta pagar
(cuentas, créditos, suscripciones), compromisos. Responde en el idioma de
la persona, con cifras redondeadas y sin juzgar. No recomiendes productos financieros específicos."""


# ───────────── Datos ─────────────
def _mes_actual():
    return date.today().isoformat()[:7]


def _cats():
    return {c["id"]: c for c in datos.categorias()}


def _nombre_cat(cid, cats):
    c = cats.get(cid)
    return f"{c.get('emoji', '')} {c['nombre']}".strip() if c else ("Sin categoría" if not cid else cid)


def _rango(args):
    hoy = date.today()
    desde = str(args.get("desde") or f"{_mes_actual()}-01")[:10]
    hasta = str(args.get("hasta") or hoy.isoformat())[:10]
    for f in (desde, hasta):
        date.fromisoformat(f)  # ValueError si viene mal: se responde como error de la herramienta
    return desde, hasta


def _movs(desde="0000-00-00", hasta="9999-99-99"):
    return [m for m in datos.leer_todos() if desde <= m["fecha"] <= hasta]


def _moneda():
    return datos.presupuesto().get("moneda") or datos.config()["moneda"]


def _fila(m, cats, cuentas, con_notas=False):
    return {"fecha": m["fecha"], "descripcion": m["descripcion"], "monto": m["monto"], "moneda": m.get("moneda") or "",
            "categoria": _nombre_cat(m.get("categoria"), cats), "cuenta": cuentas.get(m.get("cuenta"), m.get("cuenta") or ""),
            **({"nota": m["nota"]} if con_notas and m.get("nota") else {})}


def _cuentas():
    return {c["id"]: c.get("nombre", c["id"]) for c in datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), [])}


# ───────────── Herramientas (todas de solo lectura) ─────────────
def _periodo(args):
    """(per, mes): el mes pedido o el actual, de sueldo a sueldo si la persona lo eligió en Ajustes (ver resumen.rango)."""
    per, actual = K.periodo_actual()
    mes = str(args.get("mes") or actual)[:7]
    datos.ruta_mes(mes)  # valida el formato
    return per, mes


def resumen_del_mes(args):
    per, mes = _periodo(args)
    cats = _cats()
    r = resumen_mod.resumen(datos.leer_todos(), mes, date.today().isoformat(), datos.presupuesto(), list(cats.values()), per)
    r["por_categoria"] = {_nombre_cat(k, cats): v for k, v in r["por_categoria"].items()}
    for a in r["alertas"]:
        a["categoria"] = _nombre_cat(a["categoria"], cats)
    r["tres_cifras"] = tres_cifras(per)
    prox = K.proximo_sueldo(per, date.today().isoformat(), K.feriados(datos.config().get("pais")))
    if prox:
        r["proximo_sueldo"] = {"fecha": prox["fecha"], "atrasado": prox["atrasado"]}
    r["nota"] = ("proyeccion = cómo terminaría el mes si sigue el ritmo de los gastos variables; null si el mes no está en curso. "
                 "desde/hasta = días que abarca el mes (puede ir de sueldo a sueldo). gastado = lo que gastaste: las compras en cuotas "
                 "con crédito cuentan por la cuota del mes y las devoluciones descuentan. tres_cifras = hoy: lo_que_tienes (suma de "
                 "los saldos conocidos; null si la persona aún no anotó ninguno), lo_que_debes (total y lo que toca este mes), te_deben "
                 "(préstamos que la persona hizo; no se resta de lo_que_debes). proximo_sueldo = cuándo debería llegar (día hábil; "
                 "atrasado si ya pasó un día hábil sin llegar).")
    return r


def tres_cifras(per=None):
    """Lo que tienes, lo que gastaste este mes y lo que debes: solo totales (sin cuentas, nombres ni ids)."""
    hoy = date.today().isoformat()
    moneda, movs = _moneda(), datos.leer_todos()
    t = resumen_mod.lo_que_tienes(datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), []), movs, moneda)
    mes = resumen_mod.periodo_de(hoy, per)
    g = resumen_mod.resumen(movs, mes, hoy, datos.presupuesto(), datos.categorias(), per)
    d = K.lo_que_debes(K.validos(None, hoy, moneda), movs, hoy, moneda, per, K.uf_config(), K.palabras_automatico(datos.config().get("pais") or "CL"))
    return {"moneda": moneda, "lo_que_tienes": t["total"], "cuentas_con_saldo": t["con_saldo"], "cuentas_sin_saldo": t["sin_saldo"],
            "lo_que_gastaste_este_mes": g["gastado"], "lo_que_debes": d["total"], "debes_este_mes": d["este_mes"],
            "lo_que_debes_hasta": d["total_max"], "debes_este_mes_hasta": d["este_mes_max"], "hay_montos_aproximados": d["aprox"],
            "te_deben": d.get("te_deben_total", 0),
            "atrasado": sum(p["monto"] for p in d["partes"] if p.get("estado") == "atrasado")}


def gastos_por_categoria(args):
    desde, hasta = _rango(args)
    cats, moneda = _cats(), _moneda()
    neutras = {k for k, c in cats.items() if c.get("tipo") == "neutro"}
    tot, n, ingresos = {}, {}, 0.0
    for m in _movs(desde, hasta):
        if m.get("categoria") in neutras or (m.get("moneda") or moneda) != moneda:
            continue
        if m["monto"] < 0:
            k = _nombre_cat(m.get("categoria"), cats)
            tot[k] = tot.get(k, 0) - m["monto"]
            n[k] = n.get(k, 0) + 1
        else:
            ingresos += m["monto"]
    filas = [{"categoria": k, "gastado": round(v), "movimientos": n[k]} for k, v in sorted(tot.items(), key=lambda x: -x[1])]
    return {"desde": desde, "hasta": hasta, "moneda": moneda, "total_gastado": round(sum(tot.values())), "total_ingresos": round(ingresos),
            "por_categoria": filas}


def buscar_movimientos(args):
    # Por defecto, los últimos 90 días: para más atrás, la IA tiene que pedirlo (así no se lleva la cartola entera sin querer).
    from datetime import timedelta
    desde, hasta = _rango({"desde": args.get("desde") or (date.today() - timedelta(days=90)).isoformat(), "hasta": args.get("hasta")})
    texto = datos.normalizar(args.get("texto") or "")
    cat = datos.normalizar(args.get("categoria") or "")
    tipo = args.get("tipo") or "todos"
    limite = max(1, min(int(args.get("limite") or 30), LIMITE_FILAS))
    cats, cuentas = _cats(), _cuentas()
    r = []
    for m in sorted(_movs(desde, hasta), key=lambda m: m["fecha"], reverse=True):
        if texto and texto not in datos.normalizar(m["descripcion"]):
            continue
        if cat and cat != datos.normalizar(m.get("categoria")) and cat not in datos.normalizar(_nombre_cat(m.get("categoria"), cats)):
            continue
        if (tipo == "gastos" and m["monto"] >= 0) or (tipo == "ingresos" and m["monto"] <= 0):
            continue
        r.append(m)
    total = round(sum(m["monto"] for m in r), 2)
    return {"desde": desde, "hasta": hasta, "encontrados": len(r), "suma_montos": total, "mostrando": min(len(r), limite),
            "movimientos": [_fila(m, cats, cuentas, bool(args.get("con_notas"))) for m in r[:limite]]}


def principales_comercios(args):
    desde, hasta = _rango(args)
    limite = max(1, min(int(args.get("limite") or 15), 100))
    moneda, grupos = _moneda(), {}
    for m in _movs(desde, hasta):
        if m["monto"] >= 0 or (m.get("moneda") or moneda) != moneda:
            continue
        k = categorizar.regla_para(m["descripcion"]) or datos.normalizar(m["descripcion"])[:30]
        g = grupos.setdefault(k, {"comercio": k, "gastado": 0.0, "veces": 0})
        g["gastado"] -= m["monto"]
        g["veces"] += 1
    filas = sorted(grupos.values(), key=lambda g: -g["gastado"])[:limite]
    for g in filas:
        g["gastado"] = round(g["gastado"])
    return {"desde": desde, "hasta": hasta, "moneda": moneda, "comercios": filas}


def comparar_meses(args):
    n = max(2, min(int(args.get("meses") or 6), 24))
    cats, moneda = _cats(), _moneda()
    neutras = {k for k, c in cats.items() if c.get("tipo") == "neutro"}
    meses = sorted(datos.meses())[-n:]
    r = []
    for mes in meses:
        por, ingresos = {}, 0.0
        for m in datos.leer_mes(mes):
            if m.get("categoria") in neutras or (m.get("moneda") or moneda) != moneda:
                continue
            if m["monto"] < 0:
                k = _nombre_cat(m.get("categoria"), cats)
                por[k] = por.get(k, 0) - m["monto"]
            else:
                ingresos += m["monto"]
        r.append({"mes": mes, "gastado": round(sum(por.values())), "ingresos": round(ingresos),
                  "por_categoria": {k: round(v) for k, v in sorted(por.items(), key=lambda x: -x[1])}})
    return {"moneda": moneda, "meses": r}


def presupuesto(args):
    per, mes = _periodo(args)
    cats = _cats()
    p = datos.presupuesto()
    r = resumen_mod.resumen(datos.leer_todos(), mes, date.today().isoformat(), p, list(cats.values()), per)
    filas = []
    for cid, tope in sorted(p.get("mensual", {}).items(), key=lambda x: -x[1]):
        g = r["por_categoria"].get(cid, 0)
        filas.append({"categoria": _nombre_cat(cid, cats), "tope": tope, "gastado": g, "queda": tope - g, "porcentaje": round(g / tope * 100) if tope else None})
    return {"mes": mes, "desde": r["desde"], "hasta": r["hasta"], "moneda": p.get("moneda"), "dia": r["dia"], "dias_mes": r["dias_mes"], "categorias": filas,
            "sin_presupuesto": not filas}


def cuentas_y_datos(args):
    meses = datos.meses()
    cons = datos.leer_json(os.path.join(datos.INTERNO, "conexiones.json"), {})
    return {"cuentas": [{"nombre": c.get("nombre"), "moneda": c.get("moneda"), "origen": "conexión automática" if c.get("conector") else "cartola"}
                        for c in datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), [])],
            "conexiones": {k: {"conectado": v.get("conectado", False), "ultima_revision": v.get("ultima")} for k, v in cons.items()},
            "meses_con_datos": sorted(meses), "categorias": [{"id": k, "nombre": c["nombre"], "tipo": c["tipo"]} for k, c in _cats().items()],
            "moneda_principal": _moneda(), "pais": datos.config().get("pais")}


def compromisos(args):
    """Estado de los compromisos del mes (pagos y cobros que se repiten), sin ids internos."""
    per, mes = _periodo(args)
    hoy, moneda, cats = date.today().isoformat(), _moneda(), _cats()
    lista = K.validos(None, hoy, moneda)
    e = K.estado_mes(lista, datos.leer_todos(), mes, hoy, moneda, per, K.uf_config(), None, K.palabras_automatico(datos.config().get("pais") or "CL"))
    def fila(i):
        r = {"nombre": i["nombre"], "tipo": i["tipo"], "es": i["signo"], "monto": i["monto"], "moneda": i["moneda"],
             "categoria": _nombre_cat(i["categoria"], cats), "vence": i["vence"], "estado": i["estado"]}
        if i["modo_pago"]:
            r["pago"] = i["modo_pago"]
        if i["rango"]:
            r["aproximado"] = {"entre": i["rango"]["min"], "y": i["rango"]["max"]}
        if i["original"]:
            r["en_uf"] = i["original"]["monto"]
            if i["original"]["sin_valor"]:
                r["nota"] = "en UF; aún no se sabe cuánto es en pesos (no está en los totales)"
            else:
                r["valor_uf_usado"] = i["original"]["valor_uf"]
        if i["estado"] == "pagado":
            r["pagado_el"] = i["pago"]["fecha"]
            r["como"] = "reconocido en la cartola" if i["pago"]["como"] == "automatico" else "marcado a mano"
        elif i["estado"] == "pendiente":
            r["vence_en_dias"] = i["dias"]
        elif i["estado"] == "esperando":
            r["dias_desde_el_vencimiento"] = i["dias"]
        elif i["estado"] == "atrasado":
            r["dias_de_atraso"] = i["dias"]
        if i["cuota"]:
            r["cuota"] = f"{i['cuota']['numero']} de {i['cuota']['total']}"
        if i["anterior"]:
            r["del_mes_anterior"] = True
        return r
    deudas = [{"nombre": c["nombre"], "cuotas_pagadas": c["cuotas"]["pagadas"], "cuotas_total": c["cuotas"]["total"],
               "quedan": c["cuotas"]["quedan"], "termina": c["termina"], "por_pagar": c["por_pagar"]}
              for c in e["compromisos"] if c["cuotas"]]
    desde, hasta = resumen_mod.rango(mes, per)
    return {"mes": mes, "desde": desde, "hasta": hasta, "moneda": moneda, "compromisos": [fila(i) for i in e["items"]], "total_del_mes": e["total"],
            "pagado": e["pagado"], "pendiente": e["pendiente"], "atrasado": e["atrasado"], "pendiente_hasta": e["pendiente_max"],
            "hay_montos_aproximados": e["aprox"], "en_uf_sin_estimar": e["sin_valor"],
            "ingresos_esperados": e["ingresos_esperados"], "ingresos_recibidos": e["ingresos_recibidos"], "deudas_con_cuotas": deudas,
            "sin_compromisos": not lista,
            "nota": "estado: pagado, pendiente (aún no vence), hoy (vence hoy), esperando (se paga solo, venció hace poco y el cargo "
                    "aún no aparece) o atrasado (en uno que se paga solo: no apareció el cargo). pago: automatico (se cobra solo: PAC, "
                    "suscripción con tarjeta) o manual (lo paga la persona). Los montos de gasto e ingreso van en positivo. "
                    "Un monto aproximado o en UF es una estimación: `aproximado` da el rango y `pendiente_hasta` el máximo posible."}


def _esquema(props, requeridos=()):
    return {"type": "object", "properties": props, "required": list(requeridos), "additionalProperties": False}


FECHA = {"type": "string", "description": "AAAA-MM-DD", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
MES = {"type": "string", "description": "AAAA-MM (por defecto, el mes actual)", "pattern": r"^\d{4}-\d{2}$"}
HERRAMIENTAS = {
    "resumen_del_mes": (resumen_del_mes, "Resumen de un mes: gastado, ingresos, gasto por categoría, proyección a fin de mes y "
                        "alertas de presupuesto. Úsala para «¿cómo voy este mes?».", _esquema({"mes": MES})),
    "gastos_por_categoria": (gastos_por_categoria, "Total gastado por categoría (y total de ingresos) entre dos fechas.",
                             _esquema({"desde": FECHA, "hasta": FECHA})),
    "buscar_movimientos": (buscar_movimientos, "Busca movimientos por texto en la descripción (p. ej. «uber»), categoría, tipo y "
                           "fechas (por defecto, los últimos 90 días). Devuelve la suma y hasta 30 filas (o `limite`, máximo 200), los más recientes primero. Pide solo lo necesario para responder.",
                           _esquema({"texto": {"type": "string"}, "categoria": {"type": "string", "description": "id o nombre"},
                                     "tipo": {"type": "string", "enum": ["todos", "gastos", "ingresos"]}, "desde": FECHA, "hasta": FECHA,
                                     "limite": {"type": "integer", "minimum": 1, "maximum": LIMITE_FILAS},
                                     "con_notas": {"type": "boolean", "description": "incluir las notas que la persona escribió"}})),
    "principales_comercios": (principales_comercios, "Dónde se gasta más: comercios agrupados con total y número de compras.",
                              _esquema({"desde": FECHA, "hasta": FECHA, "limite": {"type": "integer", "minimum": 1, "maximum": 100}})),
    "comparar_meses": (comparar_meses, "Gasto e ingresos de los últimos N meses, por categoría, para ver tendencias.",
                       _esquema({"meses": {"type": "integer", "minimum": 2, "maximum": 24}})),
    "presupuesto": (presupuesto, "El presupuesto mensual de cada categoría y cuánto se lleva gastado y cuánto queda.", _esquema({"mes": MES})),
    "compromisos": (compromisos, "Pagos y cobros que se repiten (arriendo, créditos, cuentas, suscripciones, sueldo) y su estado en "
                    "el mes: qué está pagado, qué está pendiente o atrasado, el total y cuánto falta. Úsala para «¿qué me falta pagar?».",
                    _esquema({"mes": MES})),
    "cuentas_y_datos": (cuentas_y_datos, "Qué cuentas hay, de dónde vienen los datos, qué meses tienen movimientos, las categorías y "
                        "la moneda. Úsala primero si no sabes qué datos existen.", _esquema({})),
}


# ───────────── Protocolo (JSON-RPC 2.0 sobre stdio, una línea por mensaje) ─────────────
def responder(id_, resultado=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    msg.update({"error": error} if error else {"result": resultado})
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def atender(msg):
    metodo, id_ = msg.get("method"), msg.get("id")
    if id_ is None:  # notificación (p. ej. notifications/initialized): no lleva respuesta
        return
    if metodo == "initialize":
        pedida = (msg.get("params") or {}).get("protocolVersion")
        return responder(id_, {"protocolVersion": pedida if pedida in VERSIONES else VERSIONES[0],
                               "capabilities": {"tools": {"listChanged": False}},
                               "serverInfo": {"name": "alcancia", "title": "Alcancía", "version": "0.2.0"},
                               "instructions": INSTRUCCIONES})
    if metodo == "ping":
        return responder(id_, {})
    if metodo == "tools/list":
        return responder(id_, {"tools": [{"name": n, "title": n.replace("_", " ").capitalize(), "description": d, "inputSchema": e,
                                          "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}}
                                         for n, (_, d, e) in HERRAMIENTAS.items()]})
    if metodo == "tools/call":
        p = msg.get("params") or {}
        h = HERRAMIENTAS.get(p.get("name"))
        if not h:
            return responder(id_, error={"code": -32602, "message": f"Herramienta desconocida: {p.get('name')}"})
        try:
            r = h[0](p.get("arguments") or {})
            return responder(id_, {"content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False)}], "structuredContent": r,
                                   "isError": False})
        except (ValueError, TypeError) as e:
            return responder(id_, {"content": [{"type": "text", "text": f"Argumentos inválidos: {e}"}], "isError": True})
    if metodo in ("resources/list", "prompts/list"):
        return responder(id_, {"resources": []} if metodo == "resources/list" else {"prompts": []})
    responder(id_, error={"code": -32601, "message": f"Método no soportado: {metodo}"})


def main():
    for linea in sys.stdin:
        linea = linea.strip()
        if not linea:
            continue
        try:
            msg = json.loads(linea)
        except ValueError:
            responder(None, error={"code": -32700, "message": "JSON inválido"})
            continue
        for m in msg if isinstance(msg, list) else [msg]:
            if not isinstance(m, dict):
                responder(None, error={"code": -32600, "message": "Pedido inválido"})
                continue
            try:
                atender(m)
            except Exception as e:  # nunca se cae: la IA recibe el error y sigue
                responder(m.get("id"), error={"code": -32603, "message": f"Error interno: {type(e).__name__}"})


if __name__ == "__main__":
    main()
