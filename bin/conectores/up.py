"""Up (Australia): token personal desde la app de Up, solo lectura.
API: GET https://api.up.com.au/api/v1/transactions?filter[since]&filter[until]&page[size]=100, paginando con links.next.
Se guardan solo las SETTLED (las HELD todavía pueden cambiar)."""
import urllib.parse

from conectores._util import fecha_local, numero, rfc3339

BASE = "https://api.up.com.au/api/v1"
INFO = {
    "id": "up", "nombre": "Up", "paises": ["AU"], "hosts": ["api.up.com.au"],
    "campos": [{"id": "token", "etiqueta": "Personal Access Token", "secreto": True}],
    "enlace": "https://api.up.com.au/getting_started",
    "pasos": [
        "En la app de **Up**, desliza a la derecha y abre **Data sharing → Personal Access Token**.",
        "Toca **Generate a token**, elige cuánto tiempo dura y cópialo (empieza con `up:yeah:`).",
        "Pégalo aquí. Es de solo lectura: no puede mover dinero.",
    ],
    "dias_inicio": 180, "estado": "beta",
}


def _cab(cred):
    return {"Authorization": "Bearer " + cred.get("token", "").strip()}


def probar(cred, red):
    r = red.get(f"{BASE}/accounts?page[size]=100".replace("[", "%5B").replace("]", "%5D"), cabeceras=_cab(cred))
    return None, [{"id": a["id"], "nombre": (a.get("attributes") or {}).get("displayName", "Up")[:60],
                   "moneda": ((a.get("attributes") or {}).get("balance") or {}).get("currencyCode", "AUD")} for a in r.get("data") or []]


def movimientos(cred, desde, hasta, memoria, red):
    q = urllib.parse.urlencode({"filter[since]": rfc3339(desde), "filter[until]": rfc3339(hasta, True), "filter[status]": "SETTLED",
                                "page[size]": 100})
    url, movs = f"{BASE}/transactions?{q}", []
    while url:
        r = red.get(url, cabeceras=_cab(cred))
        for t in r.get("data") or []:
            a = t.get("attributes") or {}
            if a.get("status") != "SETTLED":
                continue
            monto = numero((a.get("amount") or {}).get("value"))
            f = fecha_local(a.get("settledAt") or a.get("createdAt"))
            if monto is None or not f:
                continue
            cuenta = (((t.get("relationships") or {}).get("account") or {}).get("data") or {}).get("id", "")
            movs.append({"cuenta": cuenta, "id_externo": t.get("id"), "fecha": f, "descripcion": a.get("description") or a.get("rawText") or "",
                         "monto": monto, "moneda": (a.get("amount") or {}).get("currencyCode", "AUD")})
        url = (r.get("links") or {}).get("next")
    return movs, {}, None
