"""Guardar lo que la persona cambia en la interfaz. Lo llaman las apps de escritorio. Solo biblioteca estándar.

  guardar.py <accion> <entrada.json> <salida.json>

  categoria    {"mes", "id", "categoria"}           cambia la categoría de un movimiento
  regla        {"contiene", "categoria"}            aprende una regla y la aplica a todos los movimientos que calzan
  presupuesto  {"mensual": {"<categoria>": tope}}   guarda los topes del mes
  receta       {"receta": {...}}                    guarda una receta nueva (validada) en ~/Alcancia/.alcancia/recetas/
  desconectar  {"conector"}                         olvida el estado de una conexión (la llave la borra la app del Llavero)
  categoriaNueva {"categoria": {"id", "nombre", "emoji", "tipo"}, "mes"?, "id"?}
                                                    crea una categoría (en categorias.json) y, si viene, se la pone a ese movimiento
  saldo        {"cuenta", "monto", "fecha"}         lo que la persona tiene hoy en una cuenta (cuentas.json, origen «persona»)
  compromiso   {"accion", ...}                      compromisos.json: guardar {"compromiso"}, borrar {"id"},
                                                    pagado / desmarcar {"id", "periodo"}, no_es {"id", "periodo", "movimiento"},
                                                    descartar {"clave"} (una sugerencia que no es compromiso),
                                                    reasignar {"id", "de", "a", "movimiento"?} (ese pago era del vencimiento anterior)

Todo lo que llega se valida: categorías que existen, montos positivos, recetas con recetas.validar.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datos  # noqa: E402
import recetas  # noqa: E402


def ids_categorias():
    return {c["id"] for c in datos.categorias()}


def categoria(e):
    mes, cat = str(e.get("mes", "")), str(e.get("categoria", ""))
    if cat and cat not in ids_categorias():
        return {"ok": False, "error": "Esa categoría no existe."}
    if not datos.cambiar(mes, str(e.get("id", "")), {"categoria": cat}):
        return {"ok": False, "error": "No encontré ese movimiento."}
    return {"ok": True}


def regla(e):
    contiene, cat = datos.normalizar(e.get("contiene", "")), str(e.get("categoria", ""))
    if len(contiene) < 2 or cat not in ids_categorias():
        return {"ok": False, "error": "Regla inválida."}
    ruta = os.path.join(datos.BASE, "reglas.json")
    lista = [r for r in datos.reglas() if datos.normalizar(r.get("contiene", "")) != contiene]
    lista.append({"contiene": contiene, "categoria": cat})
    datos.escribir_json(ruta, lista)
    cambiados = 0
    for mes in datos.meses():
        movs = datos.leer_mes(mes)
        tocado = False
        for m in movs:
            if contiene in datos.normalizar(m["descripcion"]) and m["categoria"] != cat:
                m["categoria"] = cat
                tocado = True
                cambiados += 1
        if tocado:
            datos.escribir_mes(mes, movs)
    return {"ok": True, "cambiados": cambiados}


def categoria_nueva(e):
    """Una categoría creada al vuelo («Comida atípica», «Cine»). Si categorias.json aún no existe, parte de las de siempre."""
    import re
    c = e.get("categoria")
    if not isinstance(c, dict):
        return {"ok": False, "error": "Categoría inválida."}
    cid = str(c.get("id") or "")
    nombre = re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f<>]", " ", str(c.get("nombre") or ""))).strip()[:40].strip()
    emoji = str(c.get("emoji") or "🏷️").strip()
    tipo = c.get("tipo") if c.get("tipo") in ("gasto", "ingreso", "neutro") else "gasto"
    if not re.fullmatch(r"[a-z0-9_]{2,40}", cid) or not nombre or not 1 <= len(emoji) <= 8 or re.search(r"[\w<>&\s]", emoji):
        return {"ok": False, "error": "Categoría inválida."}
    lista = [dict(x) for x in datos.categorias()]
    if any(x["id"] == cid for x in lista):
        return {"ok": False, "error": "Ya existe una categoría con ese nombre."}
    lista.append({"id": cid, "nombre": nombre, "emoji": emoji, "tipo": tipo})
    datos.escribir_json(os.path.join(datos.BASE, "categorias.json"), lista)
    if e.get("id"):
        r = categoria({"mes": e.get("mes"), "id": e.get("id"), "categoria": cid})
        if not r["ok"]:
            return r
    return {"ok": True, "id": cid}


def saldo(e):
    """Lo que la persona dice que tiene hoy en una cuenta. Pasa a ser la base: desde ahí se suman los movimientos que lleguen.
    Devuelve lo que Alcancía calculaba antes, para decir si había una diferencia."""
    import re
    from datetime import date
    import resumen
    cuenta, fecha = str(e.get("cuenta") or ""), str(e.get("fecha") or date.today().isoformat())
    monto = e.get("monto")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,60}", cuenta) or isinstance(monto, bool) or not isinstance(monto, (int, float)) \
            or not -1e13 < monto < 1e13 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        return {"ok": False, "error": "Saldo inválido."}
    cuentas = datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), [])
    moneda = datos.presupuesto().get("moneda") or datos.config()["moneda"]
    antes = next((c["saldo"] for c in resumen.lo_que_tienes(cuentas, datos.leer_todos(), moneda)["cuentas"] if c["id"] == cuenta), None)
    datos.anotar_saldo(cuenta, monto, fecha, "persona")
    return {"ok": True, "calculado": antes, "diferencia": None if antes is None else round(monto - antes, 2)}


def presupuesto(e):
    mensual = e.get("mensual")
    if not isinstance(mensual, dict):
        return {"ok": False, "error": "Presupuesto inválido."}
    ids = ids_categorias()
    limpio = {k: int(v) for k, v in mensual.items() if k in ids and isinstance(v, (int, float)) and 0 < v < 1e12}
    actual = datos.presupuesto()
    datos.escribir_json(os.path.join(datos.BASE, "presupuesto.json"), {"moneda": actual.get("moneda") or datos.config()["moneda"], "mensual": limpio})
    return {"ok": True}


def receta(e):
    r = e.get("receta")
    try:
        recetas.guardar(r)
    except ValueError as err:
        return {"ok": False, "error": str(err)}
    return {"ok": True, "id": r["id"]}


def desconectar(e):
    """Olvida el estado de una conexión (la app ya borró la llave del Llavero). Los movimientos que trajo se quedan."""
    import re
    cid = str(e.get("conector", ""))
    if not re.fullmatch(r"[a-z0-9_]{2,40}", cid):
        return {"ok": False, "error": "Conector inválido."}
    ruta = os.path.join(datos.INTERNO, "conexiones.json")
    todo = datos.leer_json(ruta, {})
    todo[cid] = {"conectado": False}
    datos.escribir_json(ruta, todo)
    return {"ok": True}


def compromiso(e):
    """Compromisos: guardar (validado), borrar, marcar «ya lo pagué», desmarcar, «no es este», «ese pago era del mes pasado»
    (reasignar) y descartar una sugerencia."""
    import re
    from datetime import date
    import compromisos as K
    accion = e.get("accion")
    hoy = e["hoy"] if K._fecha_valida(e.get("hoy")) else date.today().isoformat()
    raw = K.leer()
    lista = raw["compromisos"]
    cid = str(e.get("id") or "")
    actual = next((c for c in lista if isinstance(c, dict) and c.get("id") == cid), None)
    if accion == "guardar":
        nuevo = e.get("compromiso")
        moneda = datos.presupuesto().get("moneda") or datos.config()["moneda"]
        limpio, errores = K.validar(nuevo, ids_categorias(), hoy, moneda)
        if errores:
            return {"ok": False, "error": " ".join(errores)}
        previo = next((c for c in lista if isinstance(c, dict) and c.get("id") == limpio["id"]), None)
        if previo:  # lo marcado y desde cuándo se mantienen: la interfaz edita lo demás
            limpio["pagos"] = K._pagos(previo.get("pagos"))
            if K._fecha_valida(previo.get("desde")):
                limpio["desde"] = previo["desde"]
            lista[lista.index(previo)] = limpio
        elif len(lista) >= 300:
            return {"ok": False, "error": "Ya hay demasiados compromisos."}
        else:
            lista.append(limpio)
        K.escribir(raw)
        return {"ok": True, "id": limpio["id"], "primero": not previo and len(lista) == 1}
    if accion == "descartar":
        clave = K.limpiar_clave(e.get("clave"))  # como las palabras de `buscar`: nunca números largos
        if not 2 <= len(clave) <= 60:
            return {"ok": False, "error": "Sugerencia inválida."}
        if clave not in raw["descartados"]:
            raw["descartados"] = (raw["descartados"] + [clave])[-300:]
        K.escribir(raw)
        return {"ok": True}
    if not actual:
        return {"ok": False, "error": "No encontré ese compromiso."}
    if accion == "borrar":
        lista.remove(actual)
        K.escribir(raw)
        return {"ok": True}
    if accion == "reasignar":
        # «Ese pago era del mes pasado» (lo propone la conversación con Alcancía y la persona lo confirma): el pago del vencimiento
        # `de` pasa al anterior `a`. El movimiento se busca en los movimientos guardados (nada se inventa).
        de, a, mov = str(e.get("de") or ""), str(e.get("a") or ""), str(e.get("movimiento") or "")
        if not K.PERIODO.fullmatch(de) or not K.PERIODO.fullmatch(a) or (mov and not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", mov)):
            return {"ok": False, "error": "Acción inválida."}
        m = next((x for x in datos.leer_todos() if x["id"] == mov), None) if mov else None
        if mov and not m:
            return {"ok": False, "error": "No encontré ese pago en tus movimientos."}
        problema = K.reasignar_pago(actual, de, a, m)
        if problema:
            return {"ok": False, "error": problema}
        K.escribir(raw)
        return {"ok": True}
    periodo = str(e.get("periodo") or "")
    if accion not in ("pagado", "desmarcar", "no_es") or not K.PERIODO.fullmatch(periodo):
        return {"ok": False, "error": "Acción inválida."}
    if not isinstance(actual.get("pagos"), dict):
        actual["pagos"] = {}
    p = actual["pagos"].setdefault(periodo, {})
    if accion == "pagado":
        for k in ("movimiento", "monto"):
            p.pop(k, None)
        p.update({"como": "manual", "fecha": hoy})
    elif accion == "desmarcar":
        for k in ("como", "fecha", "movimiento", "monto"):
            p.pop(k, None)
    else:
        mov = str(e.get("movimiento") or "")
        if not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", mov):
            return {"ok": False, "error": "Movimiento inválido."}
        if mov not in p.setdefault("no_es", []):
            p["no_es"] = (p["no_es"] + [mov])[-20:]
        if p.get("movimiento") == mov:
            for k in ("como", "fecha", "movimiento", "monto"):
                p.pop(k, None)
    if not p:
        del actual["pagos"][periodo]
    K.escribir(raw)
    return {"ok": True}


ACCIONES = {"categoria": categoria, "regla": regla, "presupuesto": presupuesto, "receta": receta, "desconectar": desconectar,
            "compromiso": compromiso, "categoriaNueva": categoria_nueva, "saldo": saldo}

if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ACCIONES:
        print(__doc__)
        sys.exit(2)
    try:
        with open(sys.argv[2], encoding="utf-8") as f:
            entrada = json.load(f)
        resultado = ACCIONES[sys.argv[1]](entrada if isinstance(entrada, dict) else {})
    except (OSError, ValueError) as err:
        resultado = {"ok": False, "error": str(err)}
    datos.escribir_json(sys.argv[3], resultado)
    print(json.dumps(resultado, ensure_ascii=False))
