"""Conectar el servidor MCP de Alcancía (bin/mcp_servidor.py) con la IA de la persona, en un clic. Solo biblioteca estándar.

  mcp_conectar.py estado <salida.json>                 qué IA hay instaladas y cuáles ya tienen a Alcancía
  mcp_conectar.py conectar <cliente> <salida.json>     agrega a Alcancía en esa IA
  mcp_conectar.py quitar <cliente> <salida.json>       la quita (no toca nada más de su configuración)
  mcp_conectar.py reparar <salida.json>                si la app cambió de lugar, actualiza la ruta donde ya estaba conectada

Cuando la IA tiene un comando para esto (claude/codex/gemini mcp add) se usa ese comando; si no, se edita su archivo de
configuración con cuidado: se lee entero, se cambia solo la entrada "alcancia", se guarda una copia de respaldo la primera vez
(<archivo>.antes-de-alcancia) y se escribe de forma atómica. Nunca se borra otra entrada.
"""
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datos  # noqa: E402
import ia  # noqa: E402  (al importarlo, agrega al PATH las carpetas donde suelen quedar los CLI de IA)

NOMBRE = "alcancia"
HOME = os.path.expanduser("~")
SERVIDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_servidor.py")


def comando():
    """El Python que corre este script (en la app, el portátil que viene adentro) y la ruta del servidor."""
    return os.environ.get("ALCANCIA_PYTHON") or sys.executable, [SERVIDOR]


def _ruta_claude_desktop():
    if sys.platform == "darwin":
        return os.path.join(HOME, "Library", "Application Support", "Claude", "claude_desktop_config.json")
    if os.name == "nt":
        return os.path.join(os.environ.get("APPDATA", HOME), "Claude", "claude_desktop_config.json")
    return os.path.join(HOME, ".config", "Claude", "claude_desktop_config.json")


def _claude_desktop_instalado():
    rutas = ["/Applications/Claude.app", os.path.join(HOME, "Applications", "Claude.app"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "AnthropicClaude")]
    return any(os.path.exists(r) for r in rutas) or os.path.isdir(os.path.dirname(_ruta_claude_desktop()))


#: id → (nombre visible, archivo donde queda la entrada, cómo se agrega)
CLIENTES = {
    "claude_desktop": {"nombre": "Claude (app de escritorio)", "archivo": _ruta_claude_desktop, "tipo": "json",
                       "instalado": _claude_desktop_instalado, "nota": "Cierra y vuelve a abrir Claude para que aparezca."},
    "claude_code": {"nombre": "Claude Code", "archivo": lambda: os.path.join(HOME, ".claude.json"), "tipo": "cli", "cli": "claude",
                    "agregar": lambda py, a: ["mcp", "add", "--scope", "user", NOMBRE, "--", py, *a],
                    "quitar": ["mcp", "remove", "--scope", "user", NOMBRE]},
    "codex": {"nombre": "ChatGPT (app de escritorio y Codex)", "archivo": lambda: os.path.join(HOME, ".codex", "config.toml"), "tipo": "cli",
              "cli": "codex", "agregar": lambda py, a: ["mcp", "add", NOMBRE, "--", py, *a], "quitar": ["mcp", "remove", NOMBRE]},
    "gemini": {"nombre": "Gemini CLI", "archivo": lambda: os.path.join(HOME, ".gemini", "settings.json"), "tipo": "cli", "cli": "gemini",
               "agregar": lambda py, a: ["mcp", "add", "-s", "user", NOMBRE, py, *a], "quitar": ["mcp", "remove", "-s", "user", NOMBRE]},
    "antigravity": {"nombre": "Antigravity (Gemini)", "archivo": lambda: os.path.join(HOME, ".gemini", "config", "mcp_config.json"),
                    "tipo": "json", "instalado": lambda: bool(shutil.which("agy")) or os.path.isdir(os.path.join(HOME, ".gemini", "config"))},
}


# ───────────── Leer y escribir configuraciones sin romper nada ─────────────
def _leer_json(ruta):
    """{} si no existe; None si existe pero no es JSON válido (en ese caso no lo tocamos)."""
    if not os.path.exists(ruta):
        return {}
    try:
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
        return json.loads(texto) if texto.strip() else {}
    except (OSError, ValueError):
        return None


def _respaldar(ruta):
    copia = ruta + ".antes-de-alcancia"
    if os.path.exists(ruta) and not os.path.exists(copia):
        shutil.copy2(ruta, copia)


def _entrada_json(cid):
    d = _leer_json(CLIENTES[cid]["archivo"]())
    return (d or {}).get("mcpServers", {}).get(NOMBRE) if isinstance(d, dict) else None


def _entrada_toml(ruta):
    """Solo lo necesario para saber si está y con qué ruta: [mcp_servers.alcancia] y su línea args."""
    try:
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return None
    m = re.search(r"^\[mcp_servers\.(?:alcancia|\"alcancia\")\]\s*$(.*?)(?=^\[|\Z)", texto, re.M | re.S)
    if not m:
        return None
    a = re.search(r"^args\s*=\s*(\[.*?\])", m.group(1), re.M | re.S)
    c = re.search(r"^command\s*=\s*\"(.*?)\"", m.group(1), re.M)
    try:
        args = json.loads(a.group(1)) if a else []
    except ValueError:
        args = []
    return {"command": c.group(1) if c else "", "args": args}


def entrada(cid):
    c = CLIENTES[cid]
    ruta = c["archivo"]()
    if ruta.endswith(".toml"):
        return _entrada_toml(ruta)
    return _entrada_json(cid)


def instalado(cid):
    c = CLIENTES[cid]
    if c["tipo"] == "cli":
        return bool(shutil.which(c["cli"]))
    return c["instalado"]()


def estado():
    py, args = comando()
    r = []
    for cid, c in CLIENTES.items():
        e = entrada(cid)
        conectado = bool(e)
        al_dia = conectado and SERVIDOR in (e.get("args") or [])
        r.append({"id": cid, "nombre": c["nombre"], "instalado": instalado(cid), "conectado": conectado, "al_dia": al_dia,
                  "nota": c.get("nota", "")})
    return {"ok": True, "clientes": r}


def _correr(cli, args):
    try:
        p = subprocess.run([shutil.which(cli) or cli, *args], capture_output=True, text=True, timeout=60, cwd=HOME)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    return p.returncode == 0, (p.stderr or p.stdout or "").strip()[-300:]


def _escribir_json(cid, valor):
    ruta = os.path.realpath(CLIENTES[cid]["archivo"]())  # si es un enlace (dotfiles), se escribe el archivo real
    d = _leer_json(ruta)
    if d is None:
        return False, "Su archivo de configuración tiene un error y no lo quise tocar. Revísalo o conéctalo a mano."
    if not isinstance(d, dict) or not isinstance(d.get("mcpServers", {}), dict):
        return False, "Su archivo de configuración tiene un formato inesperado y no lo quise tocar."
    _respaldar(ruta)
    servidores = d.setdefault("mcpServers", {})
    if valor is None:
        servidores.pop(NOMBRE, None)
    else:
        servidores[NOMBRE] = valor
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    datos.escribir_atomico(ruta, json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    return True, ""


def conectar(cid):
    c = CLIENTES.get(cid)
    if not c:
        return {"ok": False, "error": "No conozco esa IA."}
    if not instalado(cid):
        return {"ok": False, "error": f"No encontré {c['nombre']} en este computador."}
    py, args = comando()
    if c["tipo"] == "json":
        ok, error = _escribir_json(cid, {"command": py, "args": args})
    else:
        estaba = bool(entrada(cid))
        if estaba:  # ya estaba (quizás con otra ruta): se quita y se vuelve a agregar
            _correr(c["cli"], c["quitar"])
        ok, error = _correr(c["cli"], c["agregar"](py, args))
        if not ok and estaba:
            error = (error + " " if error else "") + "La conexión anterior se quitó: vuelve a intentarlo."
    if not ok:
        return {"ok": False, "error": error or f"{c['nombre']} no aceptó la conexión."}
    return {"ok": True, "nota": c.get("nota", ""), **estado()}


def quitar(cid):
    c = CLIENTES.get(cid)
    if not c:
        return {"ok": False, "error": "No conozco esa IA."}
    if c["tipo"] == "json":
        ok, error = _escribir_json(cid, None)
    else:
        ok, error = _correr(c["cli"], c["quitar"]) if entrada(cid) else (True, "")
    return {"ok": ok, "error": error, **estado()}


def reparar():
    """Si la persona movió la app (o se actualizó a otra carpeta), las conexiones viejas apuntan a una ruta que ya no existe."""
    arreglados = []
    for x in estado()["clientes"]:
        if x["conectado"] and not x["al_dia"] and x["instalado"]:
            if conectar(x["id"]).get("ok"):
                arreglados.append(x["id"])
    return {"ok": True, "arreglados": arreglados, **estado()}


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] in ("estado", "reparar"):
        res = estado() if a[0] == "estado" else reparar()
    elif len(a) == 3 and a[0] in ("conectar", "quitar"):
        res = (conectar if a[0] == "conectar" else quitar)(a[1])
    else:
        print(__doc__)
        sys.exit(2)
    datos.escribir_json(a[-1], res)
    print(json.dumps(res, ensure_ascii=False)[:400])
