"""SimpleFIN Bridge (Estados Unidos y Canadá): miles de bancos a través de un servicio que la persona contrata (US$1,50 al mes).

1) La persona crea un «Setup Token» en beta-bridge.simplefin.org. 2) Alcancía lo canjea UNA vez por una «Access URL» (POST a la URL
que va codificada en el token) y guarda esa URL en el Llavero en vez del token. 3) GET {access}/accounts?start-date&end-date
(máximo 90 días por pedido, máximo 24 pedidos al día). Las pendientes no vienen por defecto.
Protocolo: https://www.simplefin.org/protocol-v1.html
"""
import base64
import binascii
import urllib.parse
from datetime import timedelta

from conectores import Error
from conectores._util import fecha_unix, numero, unix

INFO = {
    "id": "simplefin", "nombre": "SimpleFIN (bancos de EE. UU. y Canadá)", "paises": ["US", "CA"],
    "hosts": ["beta-bridge.simplefin.org", "bridge.simplefin.org"],
    "campos": [{"id": "token", "etiqueta": "Setup Token", "secreto": True}],
    "enlace": "https://beta-bridge.simplefin.org/",
    "pasos": [
        "Crea una cuenta en **SimpleFIN Bridge** (cuesta US$1,50 al mes) y conecta ahí tus bancos.",
        "Toca **New connection** para una app nueva y copia el **Setup Token**.",
        "Pégalo aquí. Alcancía lo canjea una sola vez por una llave que guarda cifrada.",
    ],
    "nota": "SimpleFIN es un servicio aparte que se conecta con tus bancos; Alcancía solo habla con SimpleFIN.",
    "dias_inicio": 90, "estado": "beta",
}


def _acceso(cred, red):
    """Devuelve (base, cabeceras, credencial_nueva). Si viene un Setup Token, lo canjea."""
    acceso = cred.get("acceso")
    nueva = None
    if not acceso:
        try:
            url = base64.b64decode(str(cred.get("token", "")).strip(), validate=True).decode().strip()
        except (binascii.Error, UnicodeDecodeError):
            raise Error("Ese no parece un Setup Token de SimpleFIN.")
        acceso = red.post(url, crudo=True).decode().strip()
        nueva = {"acceso": acceso}
    p = urllib.parse.urlsplit(acceso)
    if p.scheme != "https" or not p.username:
        raise Error("SimpleFIN entregó una dirección inesperada.")
    base = f"https://{p.hostname}{p.path.rstrip('/')}"
    par = f"{urllib.parse.unquote(p.username)}:{urllib.parse.unquote(p.password or '')}"
    return base, {"Authorization": "Basic " + base64.b64encode(par.encode()).decode()}, nueva


def probar(cred, red):
    base, cab, nueva = _acceso(cred, red)
    r = red.get(f"{base}/accounts?balances-only=1", cabeceras=cab)
    cuentas = [{"id": str(a.get("id")), "nombre": str(a.get("name") or a.get("id"))[:60], "moneda": str(a.get("currency", ""))[:3]}
               for a in r.get("accounts") or []]
    return nueva, cuentas


def movimientos(cred, desde, hasta, memoria, red):
    base, cab, nueva = _acceso(cred, red)
    movs, inicio, avisos = [], max(desde, hasta - timedelta(days=89)), []
    r = red.get(f"{base}/accounts?start-date={unix(inicio)}&end-date={unix(hasta + timedelta(days=1))}", cabeceras=cab)
    for e in (r.get("errors") or []) + [x.get("message", "") for x in r.get("errlist") or [] if isinstance(x, dict)]:
        avisos.append(str(e)[:200])
    for a in r.get("accounts") or []:
        moneda = str(a.get("currency", ""))[:3] if len(str(a.get("currency", ""))) == 3 else ""
        for t in a.get("transactions") or []:
            if t.get("pending"):
                continue
            monto, f = numero(t.get("amount")), fecha_unix(t.get("posted"))
            if monto is None or not f or not t.get("posted"):
                continue
            movs.append({"cuenta": str(a.get("id")), "id_externo": str(t.get("id")), "fecha": f, "descripcion": t.get("description") or "",
                         "monto": monto, "moneda": moneda})
    if avisos and not movs:
        raise Error("SimpleFIN avisó: " + "; ".join(avisos)[:300])
    return movs, {}, nueva


def saldo(cred, red):
    """El saldo de cada cuenta como lo informa el banco a SimpleFIN (`balance`, al día de `balance-date`)."""
    base, cab, _ = _acceso(cred, red)
    r = red.get(f"{base}/accounts?balances-only=1", cabeceras=cab)
    out = []
    for a in r.get("accounts") or []:
        monto = numero(a.get("balance"))
        if monto is not None:
            out.append({"cuenta": str(a.get("id")), "monto": monto, "moneda": str(a.get("currency", ""))[:3] if len(str(a.get("currency", ""))) == 3 else "",
                        "fecha": fecha_unix(a.get("balance-date")) if a.get("balance-date") else None})
    return out
