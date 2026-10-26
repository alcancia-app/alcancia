"""Carpeta vigilada: importa sola las cartolas nuevas que la persona descarga (normalmente en Descargas). Solo biblioteca estándar.

  vigilar.py activar <salida.json>        empieza a vigilar desde ahora (lo que ya estaba no se toca)
  vigilar.py <carpeta> <salida.json>       importa lo nuevo

Revisa los .csv, .xlsx, .pdf, .ofx, .qfx, .qif y .xml (CAMT.053) de la carpeta (sin entrar a subcarpetas) que aparecieron después de activar la función y que no
se han revisado antes. Si una receta los reconoce, los importa (sin duplicar, con categorías); si no, los anota para que la app
ofrezca enseñarle a la IA a leerlos (salvo los PDF: en Descargas hay de todo, así que un PDF que ninguna receta reconoce se
anota en silencio, sin avisar). Nunca borra ni mueve archivos. La app la llama cuando cambia algo en la carpeta.

Lo revisado queda en ~/Alcancia/.alcancia/vigilar.json ({"desde": marca de tiempo, "vistos": {huella: resultado}}).
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import categorizar  # noqa: E402
import datos  # noqa: E402
import recetas  # noqa: E402

RUTA = os.path.join(datos.INTERNO, "vigilar.json")
EXTENSIONES = (".csv", ".xlsx", ".pdf", ".ofx", ".qfx", ".xml", ".qif")
MAXIMO = 20 * 1024 * 1024  # una cartola no pesa más que esto; lo más grande no es una cartola
QUIETO = 3  # segundos sin cambios: así no leemos un archivo que todavía se está descargando


def memoria():
    m = datos.leer_json(RUTA, {})
    return {"desde": m.get("desde", 0), "vistos": m.get("vistos", {})}


def activar():
    """Desde ahora: lo que ya estaba en la carpeta no se importa (podrían ser cartolas viejas o de otra persona)."""
    datos.escribir_json(RUTA, {"desde": time.time(), "vistos": {}})


def huella(ruta):
    h = hashlib.sha1()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()[:16]


def revisar(carpeta, ahora=None):
    import importar
    ahora = ahora or time.time()
    m = memoria()
    if not m["desde"]:
        return {"ok": False, "error": "La carpeta vigilada no está activada."}
    if not os.path.isdir(carpeta):
        return {"ok": False, "error": "No encontré la carpeta."}
    importados, sin_receta = [], []
    for nombre in sorted(os.listdir(carpeta)):
        ruta = os.path.join(carpeta, nombre)
        if nombre.startswith(".") or not nombre.lower().endswith(EXTENSIONES) or not os.path.isfile(ruta):
            continue
        st = os.stat(ruta)
        if st.st_mtime < m["desde"] or st.st_size > MAXIMO or ahora - st.st_mtime < QUIETO:
            continue
        try:
            h = huella(ruta)
        except OSError:
            continue
        if h in m["vistos"]:
            continue
        try:
            receta = recetas.detectar(ruta)
        except (OSError, ValueError):
            receta = None
        if not receta:
            if nombre.lower().endswith(".pdf"):  # boletas, pasajes, contratos…: no es tarea de Alcancía avisar por cada uno
                m["vistos"][h] = {"archivo": nombre, "resultado": "ignorado", "cuando": int(ahora)}
                continue
            m["vistos"][h] = {"archivo": nombre, "resultado": "sin_receta", "cuando": int(ahora)}
            sin_receta.append(nombre)
            continue
        try:
            movs, avisos = recetas.aplicar(ruta, receta, importar.cuenta_de(receta))
        except (OSError, ValueError):
            movs = []
        categorizar.por_reglas(movs, datos.reglas())
        nuevos, repetidos = datos.agregar(movs) if movs else (0, 0)
        if nuevos and datos.config().get("ia_en_conexiones", True):
            importar.completar_con_ia(movs)
        m["vistos"][h] = {"archivo": nombre, "resultado": "importado", "institucion": receta["institucion"], "nuevos": nuevos,
                          "cuando": int(ahora)}
        importados.append({"archivo": nombre, "institucion": receta["institucion"], "nuevos": nuevos, "repetidos": repetidos})
    # Solo se recuerdan los últimos 500 archivos revisados.
    m["vistos"] = dict(sorted(m["vistos"].items(), key=lambda kv: kv[1].get("cuando", 0))[-500:])
    datos.escribir_json(RUTA, m)
    return {"ok": True, "importados": importados, "sin_receta": sin_receta}


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "activar":
        activar()
        datos.escribir_json(a[1], {"ok": True})
    elif len(a) == 2:
        res = revisar(os.path.abspath(os.path.expanduser(a[0])))
        datos.escribir_json(a[1], res)
        print(json.dumps(res, ensure_ascii=False)[:400])
    else:
        print(__doc__)
        sys.exit(2)
