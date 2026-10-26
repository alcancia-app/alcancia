"""Buda.com (Chile, Perú, Colombia): depósitos y retiros de pesos/soles en tu cuenta, con una API key de solo lectura.
Firma HMAC-SHA384 de «MÉTODO RUTA NONCE» (sin cuerpo en los GET) con tu secreto; cabeceras X-SBTC-APIKEY/NONCE/SIGNATURE.
La API no filtra por fecha: se pagina (300 por página, lo más nuevo primero) hasta pasar la fecha pedida.
Las compras y ventas de cripto no se traen: son inversiones, no gastos."""
import hashlib
import hmac
import time

from conectores import Error
from conectores._util import fecha_local, numero

BASE = "https://www.buda.com"
INFO = {
    "id": "buda", "nombre": "Buda.com", "paises": ["CL", "PE", "CO"], "hosts": ["www.buda.com"],
    "campos": [{"id": "llave", "etiqueta": "API Key", "secreto": False}, {"id": "secreto", "etiqueta": "API Secret", "secreto": True}],
    "enlace": "https://www.buda.com/",
    "pasos": [
        "En **buda.com** ve a **Configuración → API Keys** y crea una llave nueva.",
        "Dale permiso **solo de lectura** (sin operar ni retirar) y la fecha de vencimiento que quieras.",
        "Copia la **API Key** y el **API Secret** y pégalos aquí.",
    ],
    "dias_inicio": 365, "estado": "beta",
}
FIAT = ("clp", "pen", "cop")
_ultimo_nonce = [0]


def _get(cred, red, ruta):
    nonce = max(int(time.time() * 1_000_000), _ultimo_nonce[0] + 1)
    _ultimo_nonce[0] = nonce
    firma = hmac.new(cred.get("secreto", "").strip().encode(), f"GET {ruta} {nonce}".encode(), hashlib.sha384).hexdigest()
    return red.get(BASE + ruta, cabeceras={"X-SBTC-APIKEY": cred.get("llave", "").strip(), "X-SBTC-NONCE": str(nonce), "X-SBTC-SIGNATURE": firma})


def probar(cred, red):
    r = _get(cred, red, "/api/v2/balances")
    if not isinstance(r, dict) or "balances" not in r:
        raise Error("Buda no aceptó la llave.")
    return None, [{"id": "", "nombre": "Buda.com", "moneda": ""}]


def movimientos(cred, desde, hasta, memoria, red):
    movs, limite = [], desde.isoformat()
    for moneda in FIAT:
        for tipo, signo, nombre in (("deposits", 1, "Depósito en Buda"), ("withdrawals", -1, "Retiro de Buda")):
            pagina = 1
            while True:
                r = _get(cred, red, f"/api/v2/currencies/{moneda}/{tipo}?per=300&page={pagina}&state=confirmed")
                lista = r.get(tipo) or []
                viejos = 0
                for x in lista:
                    f = fecha_local(x.get("created_at"))
                    if not f or x.get("state") != "confirmed":
                        continue
                    if f < limite:
                        viejos += 1
                        continue
                    if f > hasta.isoformat():
                        continue
                    monto = numero((x.get("amount") or [None])[0])
                    if monto is None:
                        continue
                    movs.append({"cuenta": "", "id_externo": f"{tipo}|{x.get('id')}", "fecha": f, "descripcion": nombre,
                                 "monto": signo * abs(monto), "moneda": moneda.upper()})
                total = int((r.get("meta") or {}).get("total_pages") or 1)
                if not lista or viejos or pagina >= total:
                    break
                pagina += 1
    return movs, {}, None
