# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Pieza «red»: pedidos HTTPS seguros desde los scripts de la app. Solo biblioteca estándar.

    import red
    r = red.Red(["api.ejemplo.com"], "Banco Ejemplo")       # los únicos dominios a los que puede hablar este servicio
    datos = r.get("https://api.ejemplo.com/v1/saldo", cabeceras={"Authorization": "Bearer " + llave})
    # ErrorRed: e.codigo, e.plantilla, e.valores (para traducir), str(e) (la frase en español), e.estado, e.cuerpo

- **Solo https y solo los dominios permitidos** (exactos, sin puerto raro, sin usuario:clave en la URL). Cualquier otro se rechaza
  antes de salir.
- **Nunca se siguen redirecciones**: urllib las seguiría a cualquier dominio llevándose la llave en la cabecera.
- **Límites**: tamaño máximo de la respuesta (se corta al leer, no se confía en Content-Length) y tiempo máximo del pedido entero.
- **Subidas grandes por partes** (`subir`): `Content-Range` por parte, se retoma desde lo que el servicio dice tener (308) y
  avisa el avance.
- **El User-Agent** es «<Nombre> (<repo>)» de app.json, siempre en ASCII (una cabecera con «ñ» o un emoji rompería el pedido).
- **Las credenciales** viajan solo en las cabeceras de esos pedidos: nunca se escriben en disco ni en los mensajes de error.

Para las pruebas, <ID>_RED_PRUEBA=http://127.0.0.1:<puerto> manda todo a un servidor falso local (solo 127.0.0.1, y nunca
dentro de la app: si el host puso <ID>_RECURSOS se ignora). El pedido llega a /<dominio>/<ruta>.
"""
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

import nucleo

MAXIMO = 10 * 1024 * 1024   # bytes de una respuesta, por defecto
TIEMPO = 60                 # segundos de un pedido entero, por defecto
_TROZO = 64 * 1024

#: Frases en español con marcadores (claves de traducción): la interfaz hace Tp(plantilla, valores).
ERRORES = {
    "no_permitida": "Dirección no permitida para {servicio}.",
    "redireccion": "{servicio} quiso mandarme a otra dirección y no la seguí (por seguridad).",
    "llave": "{servicio} no aceptó la llave (puede estar vencida o sin permiso de lectura).",
    "esperar": "{servicio} pidió esperar un rato antes de volver a consultar.",
    "error": "{servicio} respondió con un error ({estado}).",
    "sin_conexion": "No pude conectarme con {servicio}. ¿Hay internet?",
    "demora": "{servicio} se demoró demasiado en responder.",
    "grande": "{servicio} mandó una respuesta demasiado grande.",
    "no_entendi": "{servicio} respondió algo que no entendí.",
}


class ErrorRed(Exception):
    """Algo falló al hablar con el servicio. str(e) es la frase para la persona (nunca incluye la credencial)."""

    def __init__(self, codigo, valores, estado=0, cuerpo=""):
        self.codigo, self.plantilla, self.valores = codigo, ERRORES[codigo], {k: str(v) for k, v in valores.items()}
        texto = self.plantilla
        for k, v in self.valores.items():
            texto = texto.replace("{" + k + "}", v)
        super().__init__(texto)
        self.estado, self.cuerpo = estado, cuerpo

    def como_dict(self):
        """Lo que un script responde a la interfaz: {ok: false, codigo, plantilla, valores, error}."""
        return {"ok": False, "codigo": self.codigo, "plantilla": self.plantilla, "valores": self.valores, "error": str(self)}


class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
    """urllib sigue los 30x a cualquier dominio llevándose la llave en la cabecera: aquí no se sigue ninguno."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirección rechazada", headers, fp)


# Sin proxies del entorno ni otros manejadores raros: solo HTTP(S) directo y sin redirecciones.
_ABRIR = urllib.request.build_opener(_SinRedirecciones()).open

DOMINIO = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def _ascii(texto):
    """Un texto seguro para una cabecera HTTP (que solo admite latin-1): sin tildes ni símbolos raros. «Señal» → «Senal»."""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if 32 <= ord(c) < 127 and c not in '"\\')
    return " ".join(t.split())[:80]


def agente():
    """User-Agent: «<Nombre> (<repo>)» con `repo` de app.json («dueño/repo»), siempre en ASCII."""
    a = nucleo.app()
    nombre = _ascii(a.get("nombre", "")) or _ascii(a["id"]) or "app"
    repo = a.get("repo")
    if isinstance(repo, str) and re.fullmatch(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}", repo):
        return f"{nombre} ({repo})"
    return nombre


class _Parcial:
    """Lo que responde un servicio a una parte de una subida que aún no termina (308 sin Location: «Resume Incomplete»)."""

    def __init__(self, rango):
        self.rango = rango


class Red:
    def __init__(self, hosts, servicio, *, maximo=MAXIMO, tiempo=TIEMPO):
        hosts = {str(h).lower() for h in hosts}
        malos = [h for h in hosts if not DOMINIO.match(h)]
        if malos or not hosts:
            raise ValueError("Red: los dominios permitidos son nombres como «api.ejemplo.com».")
        self.hosts, self.servicio, self.maximo, self.tiempo = hosts, servicio, maximo, tiempo
        self.ultimo_estado = 0
        prueba = nucleo.entorno("RED_PRUEBA", "")
        # Solo para las pruebas: dentro de la app (el host define <ID>_RECURSOS) nunca se acepta.
        self.prueba = prueba if not nucleo.entorno("RECURSOS") and re.fullmatch(r"http://127\.0\.0\.1:\d{1,5}", prueba) else ""

    def _error(self, codigo, estado=0, cuerpo="", **valores):
        return ErrorRed(codigo, {"servicio": self.servicio, "estado": estado, **valores}, estado, cuerpo)

    def permitida(self, url):
        """True si la URL es https a uno de los dominios permitidos (puerto 443 o ninguno, sin usuario ni clave)."""
        try:
            p = urllib.parse.urlsplit(url)
            puerto = p.port
        except (ValueError, TypeError):
            return False
        return (p.scheme == "https" and (p.hostname or "") in self.hosts and puerto in (None, 443) and not p.username
                and not p.password and "\\" not in url and not re.search(r"[\x00-\x20]", url))

    def _url(self, url):
        if not isinstance(url, str) or not self.permitida(url):
            raise self._error("no_permitida")
        if self.prueba:
            p = urllib.parse.urlsplit(url)
            return f"{self.prueba}/{p.hostname}{p.path}" + (f"?{p.query}" if p.query else "")
        return url

    def pedir(self, metodo, url, cabeceras=None, json_=None, formulario=None, crudo=False, timeout=None, maximo=None, datos=None,
              tipo=None, _parcial=False):
        """El JSON de la respuesta (o los bytes si crudo=True). `datos`: bytes tal cual (con `tipo` como Content-Type). Lanza
        ErrorRed con un código y una frase clara si algo falla."""
        if metodo not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
            raise ValueError("Red: método desconocido.")
        tiempo = min(timeout or self.tiempo, 600)
        maximo = min(maximo or self.maximo, 200 * 1024 * 1024)
        cuerpo, cab = None, {"User-Agent": agente(), "Accept": "application/json", **(cabeceras or {})}
        if json_ is not None:
            cuerpo, cab["Content-Type"] = json.dumps(json_).encode(), "application/json"
        elif formulario is not None:
            cuerpo, cab["Content-Type"] = urllib.parse.urlencode(formulario).encode(), "application/x-www-form-urlencoded"
        elif datos is not None:
            if not isinstance(datos, (bytes, bytearray)):
                raise ValueError("Red: «datos» son bytes.")
            cuerpo, cab["Content-Type"] = bytes(datos), tipo or "application/octet-stream"
        pedido = urllib.request.Request(self._url(url), data=cuerpo, headers=cab, method=metodo)
        fin = time.monotonic() + tiempo
        try:
            with _ABRIR(pedido, timeout=tiempo) as r:
                self.ultimo_estado = r.status
                largo = r.headers.get("Content-Length")
                if largo and largo.isdigit() and int(largo) > maximo:
                    raise self._error("grande", r.status)
                partes, total = [], 0
                while True:
                    if time.monotonic() > fin:
                        raise self._error("demora")
                    trozo = r.read(_TROZO)
                    if not trozo:
                        break
                    total += len(trozo)
                    if total > maximo:
                        raise self._error("grande", r.status)
                    partes.append(trozo)
                datos = b"".join(partes)
        except ErrorRed:
            raise
        except urllib.error.HTTPError as e:
            self.ultimo_estado = e.code
            try:
                texto = (e.read(2000) or b"").decode("utf-8", "replace")
            except OSError:
                texto = ""
            if _parcial and e.code == 308 and not e.headers.get("Location"):
                return _Parcial(e.headers.get("Range"))
            if 300 <= e.code < 400:
                raise self._error("redireccion", e.code) from None
            if e.code in (401, 403):
                raise self._error("llave", e.code, texto) from None
            if e.code == 429:
                raise self._error("esperar", e.code, texto) from None
            raise self._error("error", e.code, texto) from None
        except (TimeoutError, OSError) as e:
            demora = isinstance(e, TimeoutError) or "timed out" in str(e)
            raise self._error("demora" if demora else "sin_conexion") from None
        if crudo:
            return datos
        try:
            return json.loads(datos or b"null")
        except ValueError:
            raise self._error("no_entendi", self.ultimo_estado) from None

    def subir(self, url, archivo, *, parte=8 * 1024 * 1024, cabeceras=None, tipo="application/octet-stream", avance=None,
              metodo="PUT", desde=0, timeout=None):
        """Sube un archivo grande por partes a una URL de subida (p. ej. la «resumable» de un servicio): un pedido por parte con
        `Content-Range: bytes a-b/total`. El servicio responde 308 (sin Location) mientras falta, con `Range: bytes=0-n` (lo que
        ya tiene: se sigue desde ahí) y 2xx al final (su JSON es lo que se devuelve). `avance(enviados, total)` después de cada
        parte. `desde`: para retomar una subida cortada. Las mismas reglas de siempre: solo esa URL, sin redirecciones."""
        if not isinstance(parte, int) or not 256 * 1024 <= parte <= 256 * 1024 * 1024:
            raise ValueError("Red: «parte» va entre 256 KB y 256 MB.")
        total = os.path.getsize(archivo)
        pos = max(0, min(int(desde), total))
        with open(archivo, "rb") as f:
            while True:
                f.seek(pos)
                trozo = f.read(parte)
                rango = f"bytes {pos}-{pos + len(trozo) - 1}/{total}" if trozo else f"bytes */{total}"
                r = self.pedir(metodo, url, cabeceras={**(cabeceras or {}), "Content-Range": rango}, datos=trozo, tipo=tipo,
                               timeout=timeout, _parcial=True)
                if not isinstance(r, _Parcial):
                    if avance:
                        avance(total, total)
                    return r
                g = re.fullmatch(r"bytes=0-(\d+)", r.rango or "")
                siguiente = int(g.group(1)) + 1 if g else pos + len(trozo)
                if siguiente <= pos and trozo:
                    raise self._error("no_entendi", 308)  # el servicio no avanza: no se sube lo mismo para siempre
                pos = min(siguiente, total)
                if avance:
                    avance(pos, total)
                if not trozo:
                    raise self._error("no_entendi", 308)

    def get(self, url, **kw):
        return self.pedir("GET", url, **kw)

    def post(self, url, **kw):
        return self.pedir("POST", url, **kw)
