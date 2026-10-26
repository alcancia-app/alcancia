"""Pedidos HTTPS para los conectores. Solo biblioteca estándar.

Nunca se siguen redirecciones (urllib las seguiría a cualquier dominio con la llave en la cabecera).

Cada conector declara los dominios oficiales a los que puede hablar (INFO["hosts"]); cualquier otro se rechaza, igual que http://.
Las credenciales viajan solo en las cabeceras de esos pedidos: nunca se escriben en disco ni en los mensajes de error.

Para las pruebas, ALCANCIA_RED_PRUEBA=http://127.0.0.1:<puerto> manda todo a un servidor falso local (solo se acepta 127.0.0.1).
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

AGENTE = "Alcancia (https://github.com/alcancia-app/alcancia)"


class ErrorRed(Exception):
    """Algo falló al hablar con el servicio. El mensaje es para la persona (nunca incluye la credencial)."""

    def __init__(self, mensaje, estado=0, cuerpo=""):
        super().__init__(mensaje)
        self.estado, self.cuerpo = estado, cuerpo


class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
    """urllib sigue los 30x a cualquier dominio llevándose la llave en la cabecera: aquí no se sigue ninguno."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirección rechazada", headers, fp)


_ABRIR = urllib.request.build_opener(_SinRedirecciones()).open


class Red:
    def __init__(self, hosts, nombre):
        self.hosts, self.nombre = set(hosts), nombre
        prueba = os.environ.get("ALCANCIA_RED_PRUEBA", "")
        # Solo para las pruebas: dentro de la app (que define ALCANCIA_RECURSOS) nunca se acepta.
        en_app = bool(os.environ.get("ALCANCIA_RECURSOS"))
        self.prueba = prueba if not en_app and re.fullmatch(r"http://127\.0\.0\.1:\d+", prueba) else ""

    def _url(self, url):
        p = urllib.parse.urlsplit(url)
        if p.scheme != "https" or p.hostname not in self.hosts:
            raise ErrorRed(f"Dirección no permitida para {self.nombre}.")
        if self.prueba:
            return f"{self.prueba}/{p.hostname}{p.path}" + (f"?{p.query}" if p.query else "")
        return url

    def pedir(self, metodo, url, cabeceras=None, json_=None, formulario=None, crudo=False, timeout=60):
        """Devuelve el JSON de la respuesta (o los bytes si crudo=True). Lanza ErrorRed con un mensaje claro si algo falla."""
        cuerpo, cab = None, {"User-Agent": AGENTE, "Accept": "application/json", **(cabeceras or {})}
        if json_ is not None:
            cuerpo, cab["Content-Type"] = json.dumps(json_).encode(), "application/json"
        elif formulario is not None:
            cuerpo, cab["Content-Type"] = urllib.parse.urlencode(formulario).encode(), "application/x-www-form-urlencoded"
        pedido = urllib.request.Request(self._url(url), data=cuerpo, headers=cab, method=metodo)
        try:
            with _ABRIR(pedido, timeout=timeout) as r:
                datos = r.read()
                self.ultimo_estado = r.status
        except urllib.error.HTTPError as e:
            texto = e.read()[:2000].decode("utf-8", "replace")
            if 300 <= e.code < 400:
                raise ErrorRed(f"{self.nombre} quiso mandarme a otra dirección y no la seguí (por seguridad).", e.code)
            if e.code in (401, 403):
                raise ErrorRed(f"{self.nombre} no aceptó la llave (puede estar vencida o sin permiso de lectura).", e.code, texto)
            if e.code == 429:
                raise ErrorRed(f"{self.nombre} pidió esperar un rato antes de volver a consultar.", e.code, texto)
            raise ErrorRed(f"{self.nombre} respondió con un error ({e.code}).", e.code, texto)
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ErrorRed(f"No pude conectarme con {self.nombre}. ¿Hay internet?")
        if crudo:
            return datos
        try:
            return json.loads(datos or b"null")
        except ValueError:
            raise ErrorRed(f"{self.nombre} respondió algo que no entendí.")

    def get(self, url, **kw):
        return self.pedir("GET", url, **kw)

    def post(self, url, **kw):
        return self.pedir("POST", url, **kw)
