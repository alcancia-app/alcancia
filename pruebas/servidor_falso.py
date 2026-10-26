"""Servidor HTTP falso para probar los conectores sin internet ni cuentas reales. Solo biblioteca estándar.

Uso en una prueba:
    with ServidorFalso({("GET", "api.ejemplo.com/v1/cosas"): lambda q, cuerpo, cab: (200, {"ok": True})}) as srv:
        os.environ["ALCANCIA_RED_PRUEBA"] = srv.url      # bin/red.py manda ahí todo (https://api.ejemplo.com/... → /api.ejemplo.com/...)
        ...
        srv.pedidos  → [(metodo, "host/ruta", query, cuerpo, cabeceras)] para revisar qué se pidió (p. ej. que la llave vaya en la cabecera)

Cada respuesta es (estado, cuerpo) o (estado, cuerpo, cabeceras): un dict/list se manda como JSON; str o bytes tal cual.
"""
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ServidorFalso:
    def __init__(self, rutas):
        self.rutas, self.pedidos = rutas, []

    def __enter__(self):
        srv = self

        class Manejador(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _responder(self, metodo):
                partes = urllib.parse.urlsplit(self.path)
                ruta = partes.path.lstrip("/")
                q = dict(urllib.parse.parse_qsl(partes.query, keep_blank_values=True))
                largo = int(self.headers.get("Content-Length") or 0)
                cuerpo = self.rfile.read(largo).decode("utf-8", "replace") if largo else ""
                cab = {k.lower(): v for k, v in self.headers.items()}
                srv.pedidos.append((metodo, ruta, q, cuerpo, cab))
                f = srv.rutas.get((metodo, ruta))
                if f is None:  # rutas con comodín al final: ("GET", "host/v1/archivo/*")
                    f = next((v for (m, r), v in srv.rutas.items() if m == metodo and r.endswith("*") and ruta.startswith(r[:-1])), None)
                r = f(q, cuerpo, cab) if f else (404, {"error": "no existe"})
                estado, resp, extra = (r + ({},))[:3]
                datos = resp if isinstance(resp, bytes) else resp.encode() if isinstance(resp, str) else json.dumps(resp).encode()
                self.send_response(estado)
                self.send_header("Content-Type", "application/json" if isinstance(resp, (dict, list)) else "text/plain")
                self.send_header("Content-Length", str(len(datos)))
                for k, v in extra.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(datos)

            def do_GET(self):
                self._responder("GET")

            def do_POST(self):
                self._responder("POST")

            def do_PUT(self):
                self._responder("PUT")

            def do_DELETE(self):
                self._responder("DELETE")

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *a):
        self.http.shutdown()
        self.http.server_close()
