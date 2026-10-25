"""Importar una cartola. Solo biblioteca estándar. Contrato con la app: el último argumento es la ruta del JSON de salida.

  importar.py vista   <archivo> [receta_id]               <salida.json>   qué receta calza y una muestra, sin guardar nada
  importar.py guardar <archivo> <receta_id> <usar_ia 0|1>  <salida.json>   lee, categoriza y guarda (sin duplicar)

Mientras guarda deja el avance en ~/Alcancia/.alcancia/estado.json ({"paso", "total", "texto"}) para la barra de progreso.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import categorizar  # noqa: E402
import datos  # noqa: E402
import ia  # noqa: E402
import recetas  # noqa: E402


def salir(salida, resultado):
    datos.escribir_json(salida, resultado)
    print(json.dumps(resultado, ensure_ascii=False)[:400])
    sys.exit(0)


def avance(paso, total, texto):
    datos.escribir_json(os.path.join(datos.INTERNO, "estado.json"), {"paso": paso, "total": total, "texto": texto})


def cuenta_de(receta):
    """La cuenta se llama como la institución (una por receta); la persona puede renombrarla en cuentas.json."""
    cid = re.sub(r"[^a-z0-9]+", "-", datos.normalizar(receta["institucion"]).lower()).strip("-") or receta["id"]
    ruta = os.path.join(datos.BASE, "cuentas.json")
    cuentas = datos.leer_json(ruta, [])
    if not any(c.get("id") == cid for c in cuentas):
        cuentas.append({"id": cid, "nombre": receta["institucion"], "receta": receta["id"], "moneda": receta["moneda"]})
        datos.escribir_json(ruta, cuentas)
    return cid


def vista(archivo, receta_id, salida):
    todas = recetas.disponibles()
    receta = todas.get(receta_id) if receta_id else recetas.detectar(archivo, todas)
    if not receta:
        salir(salida, {"ok": False, "sin_receta": True, "archivo": os.path.basename(archivo)})
    movs, avisos = recetas.aplicar(archivo, receta, "vista")
    if not movs:
        salir(salida, {"ok": False, "error": avisos[0] if avisos else "No encontré movimientos en este archivo.",
                       "receta": {"id": receta["id"], "nombre": receta["nombre"]}})
    categorizar.por_reglas(movs, datos.reglas())
    fechas = sorted(m["fecha"] for m in movs)
    salir(salida, {"ok": True, "receta": {"id": receta["id"], "nombre": receta["nombre"], "institucion": receta["institucion"]},
                   "total": len(movs), "desde": fechas[0], "hasta": fechas[-1], "avisos": avisos,
                   "muestra": sorted(movs, key=lambda m: m["fecha"], reverse=True)[:6]})


def guardar(archivo, receta_id, usar_ia, salida):
    receta = recetas.disponibles().get(receta_id)
    if not receta:
        salir(salida, {"ok": False, "error": "No encontré esa receta."})
    total = 3 if usar_ia else 2
    avance(1, total, "Leyendo la cartola…")
    movs, avisos = recetas.aplicar(archivo, receta, cuenta_de(receta))
    categorizar.por_reglas(movs, datos.reglas())
    avance(2, total, "Guardando sin duplicar…")
    nuevos, repetidos = datos.agregar(movs)
    resultado = {"ok": True, "nuevos": nuevos, "repetidos": repetidos, "avisos": avisos, "categorizados_ia": 0, "error_ia": ""}
    if usar_ia and nuevos:
        avance(3, total, f"{ia.nombre()} está poniendo categorías…")
        meses_tocados = {m["fecha"][:7] for m in movs}
        ids_nuevos = {m["id"] for m in movs}
        por_mes = {mes: datos.leer_mes(mes) for mes in meses_tocados}
        pendientes = [m for lista in por_mes.values() for m in lista if m["id"] in ids_nuevos and not m["categoria"]]
        hechos, error = categorizar.por_ia(pendientes, datos.categorias())
        if hechos:
            for mes, lista in por_mes.items():
                datos.escribir_mes(mes, lista)
        resultado.update(categorizados_ia=hechos, error_ia=error)
    resultado["sin_categoria"] = sum(1 for mes in {m["fecha"][:7] for m in movs} for m in datos.leer_mes(mes) if not m["categoria"])
    try:
        os.remove(os.path.join(datos.INTERNO, "estado.json"))
    except OSError:
        pass
    salir(salida, resultado)


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if len(a) >= 3 and a[0] == "vista":
            vista(a[1], a[2] if len(a) == 4 else "", a[-1])
        elif len(a) == 5 and a[0] == "guardar":
            guardar(a[1], a[2], a[3] == "1", a[-1])
        else:
            print(__doc__)
            sys.exit(2)
    except (OSError, ValueError) as e:
        salir(a[-1], {"ok": False, "error": f"No pude leer el archivo: {e}"})
