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
REPARACIONES = 1  # sube cuando un conector trae una reparación nueva para lo ya guardado


def reparar_guardado(mod, cid):
    """Corre una sola vez la reparación del conector (si tiene) sobre todos los meses guardados."""
    if not hasattr(mod, "reparar") or estado_conexiones().get(cid, {}).get("reparado", 0) >= REPARACIONES:
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
        r.append({"id": id_movimiento(mod.INFO["id"], cuenta, str(m["id_externo"])), "fecha": fecha, "descripcion": desc, "monto": monto,
                  "moneda": str(m.get("moneda") or "").upper()[:3], "categoria": m.get("categoria") if m.get("categoria") in CATEGORIAS_CONECTOR else "", "cuenta": cuenta,
                  "origen": f"conector:{mod.INFO['id']}", "nota": ""})
    return r


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
        return {"ok": False, "error": str(e)}
    registrar_cuentas(mod, cuentas)
    _guardar_estado(cid, {"conectado": True, "cuentas": [c["nombre"] for c in cuentas], "error": ""})
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
    red = Red(mod.INFO["hosts"], mod.INFO["nombre"])
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        crudos, memoria, nueva = mod.movimientos(credencial(), desde, hoy, est.get("memoria", {}), red)
    except conectores.Esperar as e:
        _guardar_estado(cid, {"memoria": e.args[1] if len(e.args) > 1 else est.get("memoria", {}), "intento": ahora, "error": ""})
        return {"ok": True, "nombre": mod.INFO["nombre"], "esperando": True, "mensaje": str(e.args[0]) if e.args else "", "nuevos": 0}
    except (conectores.Error, ErrorRed) as e:
        _guardar_estado(cid, {"intento": ahora, "error": str(e)})
        return {"ok": False, "error": str(e)}
    movs = a_movimientos(mod, crudos)
    cuentas = {(m.get("cuenta") or "") for m in crudos}
    registrar_cuentas(mod, [{"id": c, "nombre": c or mod.INFO["nombre"], "moneda": ""} for c in sorted(cuentas)])
    reglas = datos.reglas()
    for m in movs:  # lo que aprendió la persona manda sobre lo que propone el conector (p. ej. una «carga de saldo» que en verdad es su sueldo)
        if m["categoria"] and any(r.get("contiene") and datos.normalizar(r["contiene"]) in datos.normalizar(m["descripcion"]) for r in reglas):
            m["categoria"] = ""
    categorizar.por_reglas(movs, reglas)
    nuevos, repetidos = datos.agregar(movs)
    reparados = reparar_guardado(mod, cid)
    resultado = {"ok": True, "nombre": mod.INFO["nombre"], "nuevos": nuevos, "repetidos": repetidos, "categorizados_ia": 0, "error_ia": "",
                 "reparados": reparados}
    if nuevos and datos.config().get("ia_en_conexiones", True):
        import importar
        resultado.update(importar.completar_con_ia(movs))
    _guardar_estado(cid, {"conectado": True, "hasta": hoy.isoformat(), "ultima": ahora, "intento": ahora, "memoria": memoria or {},
                          "error": "", "nuevos": nuevos})
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
