"""Akahu (Nueva Zelanda): «personal app» gratuita para leer tus propias cuentas de casi todos los bancos neozelandeses.
Credenciales: App ID Token (cabecera X-Akahu-Id) y User Token (Bearer), desde my.akahu.nz → Developers.
API: GET https://api.akahu.io/v1/transactions?start&end (100 por página, cursor.next). Las pendientes van aparte y no se guardan."""
import urllib.parse
from datetime import timedelta

from conectores._util import fecha_local, numero

BASE = "https://api.akahu.io/v1"
INFO = {
    "id": "akahu", "nombre": "Akahu (bancos de Nueva Zelanda)", "paises": ["NZ"], "hosts": ["api.akahu.io"],
    "campos": [{"id": "app", "etiqueta": "App ID Token", "secreto": True}, {"id": "usuario", "etiqueta": "User Token", "secreto": True}],
    "enlace": "https://my.akahu.nz/developers",
    "pasos": [
        "Entra a **my.akahu.nz**, conecta tus bancos y abre **Developers**.",
        "Crea una **personal app** y copia el **App ID Token** y el **User Token**.",
        "Pégalos aquí.",
    ],
    "dias_inicio": 180, "estado": "beta",
}


def _cab(cred):
    return {"X-Akahu-Id": cred.get("app", "").strip(), "Authorization": "Bearer " + cred.get("usuario", "").strip()}


def probar(cred, red):
    r = red.get(f"{BASE}/accounts", cabeceras=_cab(cred))
    return None, [{"id": a.get("_id", ""), "nombre": str(a.get("name", "Akahu"))[:60], "moneda": "NZD"} for a in r.get("items") or []]


def movimientos(cred, desde, hasta, memoria, red):
    params = {"start": f"{desde.isoformat()}T00:00:00Z", "end": f"{(hasta + timedelta(days=1)).isoformat()}T00:00:00Z"}
    movs, cursor = [], None
    while True:
        q = dict(params, **({"cursor": cursor} if cursor else {}))
        r = red.get(f"{BASE}/transactions?{urllib.parse.urlencode(q)}", cabeceras=_cab(cred))
        for t in r.get("items") or []:
            monto, f = numero(t.get("amount")), fecha_local(t.get("date"))
            if monto is None or not f:
                continue
            desc = (t.get("merchant") or {}).get("name") or t.get("description") or ""
            movs.append({"cuenta": t.get("_account", ""), "id_externo": t.get("_id"), "fecha": f, "descripcion": desc, "monto": monto,
                         "moneda": "NZD"})
        cursor = (r.get("cursor") or {}).get("next")
        if not cursor:
            return movs, {}, None
