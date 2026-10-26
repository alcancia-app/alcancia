"""Stripe (todo el mundo, para quienes venden): lo que entra y sale de tu saldo de Stripe, con una llave restringida de solo lectura.
API: GET https://api.stripe.com/v1/balance_transactions?created[gte]&created[lte]&limit=100&starting_after. Se usa `net`
(monto menos comisión). Los montos vienen en la unidad mínima (centavos), salvo las monedas sin decimales (CLP, JPY…)."""
import urllib.parse

from conectores import Error
from conectores._util import fecha_unix, unix

INFO = {
    "id": "stripe", "nombre": "Stripe", "paises": ["*"], "hosts": ["api.stripe.com"],
    "campos": [{"id": "llave", "etiqueta": "Llave restringida (rk_live_…)", "secreto": True}],
    "enlace": "https://dashboard.stripe.com/apikeys",
    "pasos": [
        "En el **Dashboard de Stripe** (modo real, no de prueba) ve a **Desarrolladores → Claves de API**.",
        "Toca **Crear clave restringida**, ponle «Alcancía» y deja todo en **Ninguno** salvo **Balance** en **Lectura**.",
        "Crea la clave, cópiala (empieza con `rk_live_`) y pégala aquí. Stripe no la vuelve a mostrar.",
    ],
    "dias_inicio": 180, "estado": "beta",
}
SIN_DECIMALES = {"bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf"}
NOMBRES = {"charge": "Cobro", "payment": "Cobro", "payout": "Transferencia a tu banco", "refund": "Devolución", "stripe_fee": "Comisión de Stripe",
           "adjustment": "Ajuste", "transfer": "Transferencia"}


def _cab(cred):
    llave = cred.get("llave", "").strip()
    if llave.startswith("sk_"):
        raise Error("Esa es tu clave secreta completa. Por seguridad crea una clave restringida de solo lectura (rk_live_…).")
    return {"Authorization": "Bearer " + llave}


def probar(cred, red):
    red.get("https://api.stripe.com/v1/balance_transactions?limit=1", cabeceras=_cab(cred))
    return None, [{"id": "", "nombre": "Stripe", "moneda": ""}]


def movimientos(cred, desde, hasta, memoria, red):
    cab, movs, despues = _cab(cred), [], None
    while True:
        q = {"created[gte]": unix(desde), "created[lte]": unix(hasta, True), "limit": 100, **({"starting_after": despues} if despues else {})}
        r = red.get("https://api.stripe.com/v1/balance_transactions?" + urllib.parse.urlencode(q), cabeceras=cab)
        datos = r.get("data") or []
        for t in datos:
            moneda = str(t.get("currency", "")).lower()
            neto = t.get("net")
            f = fecha_unix(t.get("created"))
            if not isinstance(neto, (int, float)) or not f:
                continue
            monto = neto if moneda in SIN_DECIMALES else neto / 100
            desc = t.get("description") or NOMBRES.get(t.get("type"), t.get("type") or "Stripe")
            movs.append({"cuenta": "", "id_externo": t.get("id"), "fecha": f, "descripcion": desc, "monto": monto, "moneda": moneda.upper()})
        if not r.get("has_more") or not datos:
            return movs, {}, None
        despues = datos[-1].get("id")
