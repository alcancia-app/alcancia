"""PayPal (todo el mundo): movimientos de una cuenta **Business** con la API Transaction Search.

Token: POST https://api-m.paypal.com/v1/oauth2/token (client credentials con Client ID y Secret de una app Live).
Movimientos: GET /v1/reporting/transactions en ventanas de 31 días como máximo, 500 por página, solo estado S (exitosas).
PayPal tarda hasta 3 horas en mostrar un movimiento: por eso cada sincronización vuelve a pedir los últimos días.
"""
import base64
from datetime import timedelta

from conectores import Error
from conectores._util import fecha_local, numero, rfc3339

BASE = "https://api-m.paypal.com"
INFO = {
    "id": "paypal", "nombre": "PayPal", "paises": ["*"], "hosts": ["api-m.paypal.com"],
    "campos": [{"id": "client_id", "etiqueta": "Client ID", "secreto": False}, {"id": "secret", "etiqueta": "Secret", "secreto": True}],
    "enlace": "https://developer.paypal.com/dashboard/applications/live",
    "pasos": [
        "Necesitas una cuenta **PayPal Business** (las cuentas personales no tienen acceso a esta API).",
        "Entra a **developer.paypal.com → Apps & Credentials**, elige **Live** y toca **Create App** («Alcancía»).",
        "En la app, marca **Transaction Search** en las funciones y guarda. PayPal puede tardar unas horas en activarlo.",
        "Copia el **Client ID** y el **Secret** y pégalos aquí.",
    ],
    "dias_inicio": 180, "estado": "beta",
}


def _token(cred, red):
    par = f"{cred.get('client_id', '').strip()}:{cred.get('secret', '').strip()}"
    r = red.post(f"{BASE}/v1/oauth2/token", cabeceras={"Authorization": "Basic " + base64.b64encode(par.encode()).decode()},
                 formulario={"grant_type": "client_credentials"})
    if not isinstance(r, dict) or not r.get("access_token"):
        raise Error("PayPal no entregó un permiso. Revisa el Client ID y el Secret (de la pestaña Live).")
    if "reporting/search/read" not in str(r.get("scope", "")):
        raise Error("Falta activar «Transaction Search» en tu app de PayPal (puede tardar unas horas en activarse).")
    return {"Authorization": "Bearer " + r["access_token"]}


def probar(cred, red):
    _token(cred, red)
    return None, [{"id": "", "nombre": "PayPal", "moneda": ""}]


def movimientos(cred, desde, hasta, memoria, red):
    cab = _token(cred, red)
    desde = max(desde, hasta - timedelta(days=3 * 365 - 1))
    movs, inicio = [], desde
    while inicio <= hasta:
        fin = min(inicio + timedelta(days=30), hasta)
        pagina, total = 1, 1
        while pagina <= total:
            r = red.get(f"{BASE}/v1/reporting/transactions?start_date={rfc3339(inicio)}&end_date={rfc3339(fin, True)}"
                        f"&fields=transaction_info,payer_info,cart_info&transaction_status=S&page_size=500&page={pagina}".replace("+", "%2B"),
                        cabeceras=cab)
            total = int(r.get("total_pages") or 0)
            for d in r.get("transaction_details") or []:
                t = d.get("transaction_info") or {}
                monto = numero((t.get("transaction_amount") or {}).get("value"))
                f = fecha_local(t.get("transaction_initiation_date"))
                if monto is None or not f or t.get("transaction_status", "S") != "S":
                    continue
                cuenta_otro = (d.get("payer_info") or {}).get("payer_name", {}).get("alternate_full_name") or ""
                items = ", ".join(i.get("item_name", "") for i in (d.get("cart_info") or {}).get("item_details") or [] if i.get("item_name"))
                desc = t.get("transaction_subject") or items or cuenta_otro or t.get("transaction_note") or "PayPal"
                movs.append({"cuenta": "", "id_externo": f"{t.get('transaction_id')}|{t.get('transaction_event_code', '')}", "fecha": f,
                             "descripcion": desc, "monto": monto, "moneda": (t.get("transaction_amount") or {}).get("currency_code", "")})
            pagina += 1
        inicio = fin + timedelta(days=1)
    return movs, {}, None
