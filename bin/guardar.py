"""Guardar lo que la persona cambia en la interfaz. Lo llaman las apps de escritorio. Solo biblioteca estándar.

  guardar.py <accion> <entrada.json> <salida.json>

  categoria    {"mes", "id", "categoria"}           cambia la categoría de un movimiento
  regla        {"contiene", "categoria"}            aprende una regla y la aplica a todos los movimientos que calzan
  presupuesto  {"mensual": {"<categoria>": tope}}   guarda los topes del mes
  receta       {"receta": {...}}                    guarda una receta nueva (validada) en ~/Alcancia/.alcancia/recetas/
  desconectar  {"conector"}                         olvida el estado de una conexión (la llave la borra la app del Llavero)

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


ACCIONES = {"categoria": categoria, "regla": regla, "presupuesto": presupuesto, "receta": receta, "desconectar": desconectar}

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
