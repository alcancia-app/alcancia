"""Todo lo que la interfaz necesita para pintarse, leído de ~/Alcancia. Lo llaman las apps de escritorio. Solo biblioteca estándar.

  estado.py <salida.json>

Devuelve config, movimientos, categorías, presupuesto, reglas, cuentas, consejos, conectores, conexiones y carpeta vigilada. La app agrega lo suyo (IA instaladas, versión,
carpeta, actualizaciones). Si ~/Alcancia aún no existe, devuelve todo vacío: la interfaz muestra la bienvenida.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conectores  # noqa: E402
import datos  # noqa: E402


def consejos():
    r = []
    try:
        nombres = sorted(os.listdir(datos.CONSEJOS), reverse=True)
    except OSError:
        return r
    for n in nombres[:30]:
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.md", n)
        if not m:
            continue
        try:
            with open(os.path.join(datos.CONSEJOS, n), encoding="utf-8") as f:
                texto = f.read()
        except OSError:
            continue
        if texto.startswith("---\n"):
            fin = texto.find("\n---\n", 4)
            texto = texto[fin + 5:] if fin > 0 else texto
        r.append({"fecha": m.group(1), "texto": texto.strip()})
    return r


def conexiones():
    """Estado de cada conexión para la interfaz (sin la memoria interna de los conectores; secretos nunca hay aquí)."""
    todo = datos.leer_json(os.path.join(datos.INTERNO, "conexiones.json"), {})
    claves = ("conectado", "ultima", "error", "nuevos", "cuentas")
    return {cid: {**{k: v for k, v in e.items() if k in claves}, "esperando": bool(e.get("memoria", {}).get("esperando"))}
            for cid, e in todo.items() if isinstance(e, dict)}


def vigilar(cfg):
    m = datos.leer_json(os.path.join(datos.INTERNO, "vigilar.json"), {})
    recientes = sorted((v for v in m.get("vistos", {}).values() if v.get("resultado") != "ignorado"),  # PDFs que no son cartolas
                       key=lambda v: -v.get("cuando", 0))[:6]
    return {"activo": bool(cfg.get("vigilar")), "recientes": recientes}


def ia_externa():
    """Con qué IA de este computador se puede conectar el servidor MCP de Alcancía (y con cuáles ya está)."""
    try:
        import mcp_conectar
        return mcp_conectar.estado()["clientes"]
    except Exception:  # nunca debe impedir que la app se abra
        return []


def estado():
    cfg = datos.config()
    return {"config": cfg, "movimientos": datos.leer_todos(), "categorias": datos.categorias(), "presupuesto": datos.presupuesto(),
            "reglas": datos.reglas(), "cuentas": datos.leer_json(os.path.join(datos.BASE, "cuentas.json"), []), "consejos": consejos(),
            "conectores": conectores.info_publica(), "conexiones": conexiones(), "vigilar": vigilar(cfg), "ia_externa": ia_externa()}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    datos.escribir_json(sys.argv[1], estado())
    print("ok")
