"""Traer movimientos con un conector (API oficial + llave de la persona). Solo biblioteca estándar.

  sincronizar.py probar <conector> <salida.json>      revisa la llave y lista las cuentas (lo usa la app antes de guardarla)
  sincronizar.py traer  <conector> <salida.json>      trae lo nuevo, categoriza y guarda sin duplicar

La credencial llega por la entrada estándar (JSON con los campos del conector; la app la guarda en el Llavero) y nunca se escribe en
disco ni queda en el entorno, así la IA que categoriza no la hereda. Si el servicio entrega una credencial nueva (p. ej. al canjear un
código de un solo uso), sale por la salida estándar en una línea «CREDENCIAL {json}» y la app la guarda en el Llavero: nunca va al
archivo de salida.

El estado de cada conexión (sin secretos) queda en ~/Alcancia/.alcancia/conexiones.json.
"""
import hashlib
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import categorizar  # noqa: E402
import conectores  # noqa: E402
import datos  # noqa: E402
from red import ErrorRed, Red  # noqa: E402

RUTA_ESTADO = os.path.join(datos.INTERNO, "conexiones.json")
SOLAPE_DIAS = 10  # se vuelve a pedir un poco hacia atrás: los movimientos que se confirman tarde también llegan (el id evita duplicados)


def estado_conexiones():
    return datos.leer_json(RUTA_ESTADO, {})


def _guardar_estado(cid, cambios):
    todo = estado_conexiones()
    todo[cid] = {**todo.get(cid, {}), **cambios}
    datos.escribir_json(RUTA_ESTADO, todo)


_SIN_ERROR = {"error": "", "plantilla": "", "valores": {}}


def _fallo(e):
    """La respuesta de un error: la frase en español y, si viene de la pieza «red», su plantilla y valores para traducirla."""
    return e.como_dict() if isinstance(e, ErrorRed) else {"ok": False, "error": str(e)}


_CREDENCIAL = {}


def leer_credencial():
    """Una sola vez, al partir, de la entrada estándar."""
    texto = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read(100_000)
    try:
        c = json.loads(texto or "{}")
    except ValueError:
        c = {}
    _CREDENCIAL.clear()
    _CREDENCIAL.update(c if isinstance(c, dict) else {})


def credencial():
    return dict(_CREDENCIAL)


def id_movimiento(conector, cuenta, id_externo):
    """El servicio ya le da un id único a cada movimiento: lo usamos para no duplicar nunca, aunque cambie la descripción."""
    return hashlib.sha1(f"{conector}|{cuenta}|{id_externo}".encode()).hexdigest()[:12]


def cuenta_id(conector, cuenta):
    return f"{conector}-{cuenta}"[:60] if cuenta else conector


def sin_numeros(texto):
    """«Checking 0012345678» → «Checking ••••5678»: los servicios a veces ponen el número de cuenta en el nombre."""
    import re
    return re.sub(r"\d{4,}", lambda m: "••••" + m.group(0)[-4:] if len(m.group(0)) > 4 else "••••", str(texto))


def registrar_cuentas(mod, cuentas):
    """Agrega a cuentas.json las cuentas del servicio (campo "conector"; las de cartolas tienen "receta")."""
    ruta = os.path.join(datos.BASE, "cuentas.json")
    lista = datos.leer_json(ruta, [])
    ids = {c.get("id") for c in lista}
    cambio = False
    for c in cuentas:
        cid = cuenta_id(mod.INFO["id"], c["id"])
        if cid not in ids:
            nombre = mod.INFO["nombre"] if len(cuentas) == 1 else f"{mod.INFO['nombre']} · {sin_numeros(c['nombre'])}"
            lista.append({"id": cid, "nombre": nombre[:80], "receta": "", "conector": mod.INFO["id"], "moneda": c.get("moneda", "")})
            cambio = True
    if cambio:
        datos.escribir_json(ruta, lista)


# Las únicas categorías que un conector puede proponer (el resto lo decide Alcancía con reglas, comercios conocidos o la IA).
CATEGORIAS_CONECTOR = {"transferencia"}
REPARACIONES = 3  # sube cuando un conector trae una reparación nueva para lo ya guardado
# 3: Mercado Pago vuelve a pedir el año completo para anotar cómo se pagó (medio, cuotas) y las devoluciones de lo ya guardado.
#: Lo que un conector puede completar en lo ya guardado (por id): cómo se pagó y el monto de una devolución que creció.
COMPLETAR = ("medio", "cuotas", "cuota")


def reparacion_pendiente(cid):
    return estado_conexiones().get(cid, {}).get("reparado", 0) < REPARACIONES


def reparar_guardado(mod, cid):
    """Corre una sola vez la reparación del conector (si tiene) sobre todos los meses guardados."""
    if not reparacion_pendiente(cid):
        return 0
    if not hasattr(mod, "reparar"):
        _guardar_estado(cid, {"reparado": REPARACIONES})
        return 0
    total = 0
    for mes in datos.meses():
        lista = datos.leer_mes(mes)
        n = mod.reparar(lista)
        if n:
            datos.escribir_mes(mes, lista)
            total += n
    _guardar_estado(cid, {"reparado": REPARACIONES})
    return total


def a_movimientos(mod, crudos):
    r = []
    for m in crudos:
        try:
            monto = round(float(m["monto"]), 2)
            fecha = date.fromisoformat(str(m["fecha"])[:10]).isoformat()
        except (KeyError, ValueError, TypeError):
            continue
        desc = " ".join(str(m.get("descripcion") or "").split())[:200] or mod.INFO["nombre"]
        cuenta = cuenta_id(mod.INFO["id"], str(m.get("cuenta") or ""))
        x = {"id": id_movimiento(mod.INFO["id"], cuenta, str(m["id_externo"])), "fecha": fecha, "descripcion": desc, "monto": monto,
             "moneda": str(m.get("moneda") or "").upper()[:3], "categoria": m.get("categoria") if m.get("categoria") in CATEGORIAS_CONECTOR else "", "cuenta": cuenta,
             "origen": f"conector:{mod.INFO['id']}", "nota": ""}
        if m.get("medio") in datos.MEDIOS:
            x["medio"] = m["medio"]
        n = m.get("cuotas")
        if x.get("medio") == "credito" and isinstance(n, int) and not isinstance(n, bool) and 2 <= n <= 72:
            x["cuotas"] = n
            try:
                c = round(float(m.get("cuota") or 0), 2)
            except (TypeError, ValueError):
                c = 0
            if 0 < c < 1e12:
                x["cuota"] = int(c) if c == int(c) else c
        r.append(x)
    return r


def guardar_saldos(mod, cred, red, hoy):
    """El saldo que informa el servicio (si el conector sabe pedirlo) queda en cuentas.json con origen «conector». Si el servicio no
    lo entrega, no pasa nada: la persona lo anota en la app. Devuelve cuántas cuentas quedaron con saldo."""
    if not hasattr(mod, "saldo"):
        return 0
    try:
        lista = mod.saldo(cred, red) or []
    except (conectores.Error, ErrorRed, KeyError, TypeError, ValueError, AttributeError):
        return 0
    n = 0
    for s in lista if isinstance(lista, list) else []:
        try:
            monto = float(s["monto"])
        except (KeyError, TypeError, ValueError):
            continue
        fecha = str(s.get("fecha") or hoy)[:10]
        cid = cuenta_id(mod.INFO["id"], str(s.get("cuenta") or ""))
        datos.anotar_saldo(cid, monto, fecha, "conector", nombre=mod.INFO["nombre"], moneda=str(s.get("moneda") or "").upper()[:3])
        n += 1
    return n


def categoria_de_devoluciones(movs):
    """Una devolución nueva toma la categoría de la compra devuelta (si ya la tenía): así descuenta de esa categoría."""
    por_id = {}
    for m in movs:
        if m["descripcion"].startswith("Devolución: ") and not m["categoria"]:
            por_id[m["id"]] = m
    if not por_id:
        return
    guardados = {(x["cuenta"], x["descripcion"]): x.get("categoria") for x in datos.leer_todos() if x.get("categoria")}
    for m in movs:
        if m["descripcion"].startswith("Devolución: ") and not m["categoria"]:
            m["categoria"] = guardados.get((m["cuenta"], m["descripcion"][len("Devolución: "):]), "") or ""


def probar(cid, salida):
    mod = conectores.todos().get(cid)
    if not mod:
        return {"ok": False, "error": "No conozco ese conector."}
    red = Red(mod.INFO["hosts"], mod.INFO["nombre"])
    cred = credencial()
    faltan = [c["etiqueta"] for c in mod.INFO["campos"] if not str(cred.get(c["id"], "")).strip()]
    if faltan:
        return {"ok": False, "error": "Falta: " + ", ".join(faltan) + "."}
    try:
        nueva, cuentas = mod.probar(cred, red)
    except (conectores.Error, ErrorRed) as e:
        return _fallo(e)
    registrar_cuentas(mod, cuentas)
    guardar_saldos(mod, cred, red, date.today().isoformat())
    _guardar_estado(cid, {"conectado": True, "cuentas": [c["nombre"] for c in cuentas], **_SIN_ERROR})
    r = {"ok": True, "cuentas": [{**c, "nombre": sin_numeros(c["nombre"])} for c in cuentas]}
    if nueva:
        r["credencial"] = nueva
    return r


def traer(cid, salida, hoy=None):
    mod = conectores.todos().get(cid)
    if not mod:
        return {"ok": False, "error": "No conozco ese conector."}
    hoy = hoy or date.today()
    est = estado_conexiones().get(cid, {})
    ultima = est.get("hasta")
    desde = (date.fromisoformat(ultima) - timedelta(days=SOLAPE_DIAS)) if ultima else hoy - timedelta(days=mod.INFO.get("dias_inicio", 90))
    releer = ultima and reparacion_pendiente(cid) and getattr(mod, "RELEER_DIAS", 0)
    if releer:  # una reparación nueva: se vuelve a pedir todo lo que deja el servicio para completar lo ya guardado (por id)
        desde = min(desde, hoy - timedelta(days=releer))
    red = Red(mod.INFO["hosts"], mod.INFO["nombre"])
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        crudos, memoria, nueva = mod.movimientos(credencial(), desde, hoy, est.get("memoria", {}), red)
    except conectores.Esperar as e:
        _guardar_estado(cid, {"memoria": e.args[1] if len(e.args) > 1 else est.get("memoria", {}), "intento": ahora, **_SIN_ERROR})
        return {"ok": True, "nombre": mod.INFO["nombre"], "esperando": True, "mensaje": str(e.args[0]) if e.args else "", "nuevos": 0}
    except (conectores.Error, ErrorRed) as e:
        r = _fallo(e)
        _guardar_estado(cid, {"intento": ahora, "error": r["error"], "plantilla": r.get("plantilla", ""), "valores": r.get("valores", {})})
        return r
    movs = a_movimientos(mod, crudos)
    cuentas = {(m.get("cuenta") or "") for m in crudos}
    registrar_cuentas(mod, [{"id": c, "nombre": c or mod.INFO["nombre"], "moneda": ""} for c in sorted(cuentas)])
    reglas = datos.reglas()
    for m in movs:  # lo que aprendió la persona manda sobre lo que propone el conector (p. ej. una «carga de saldo» que en verdad es su sueldo)
        if m["categoria"] and any(r.get("contiene") and datos.normalizar(r["contiene"]) in datos.normalizar(m["descripcion"]) for r in reglas):
            m["categoria"] = ""
    categorizar.por_reglas(movs, reglas)
    categoria_de_devoluciones(movs)
    import importar
    ya = importar.ids_guardados(movs)
    nuevos, repetidos = datos.agregar(movs)
    # Lo ya guardado se completa con lo que el servicio dice ahora (cómo se pagó; una devolución que creció). Nunca la categoría.
    completados = datos.completar(movs, COMPLETAR) + datos.completar([m for m in movs if m["descripcion"].startswith("Devolución: ")], ("monto",))
    reparados = reparar_guardado(mod, cid) + completados
    guardar_saldos(mod, credencial(), red, hoy.isoformat())
    resultado = {"ok": True, "nombre": mod.INFO["nombre"], "nuevos": nuevos, "repetidos": repetidos, "categorizados_ia": 0, "error_ia": "",
                 "reparados": reparados}
    if nuevos and datos.config().get("ia_en_conexiones", True):
        resultado.update(importar.completar_con_ia(movs))
    if nuevos:
        resultado["detectados"] = importar.detectados({m["id"] for m in movs} - ya)
    _guardar_estado(cid, {"conectado": True, "hasta": hoy.isoformat(), "ultima": ahora, "intento": ahora, "memoria": memoria or {},
                          **_SIN_ERROR, "nuevos": nuevos})
    if nueva:
        resultado["credencial"] = nueva
    return resultado


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) != 3 or a[0] not in ("probar", "traer"):
        print(__doc__)
        sys.exit(2)
    leer_credencial()
    try:
        res = (probar if a[0] == "probar" else traer)(a[1], a[2])
    except Exception as e:  # un error inesperado no debe dejar a la app sin respuesta (y nunca muestra la credencial)
        res = {"ok": False, "error": f"Algo falló en el conector: {type(e).__name__}."}
    nueva = res.pop("credencial", None)
    datos.escribir_json(a[2], res)
    if nueva:
        print("CREDENCIAL " + json.dumps(nueva, ensure_ascii=False), flush=True)
