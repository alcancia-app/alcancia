"""Mercado Pago (Argentina, Brasil, Chile, Colombia, México, Perú, Uruguay): pagos que hiciste y recibiste.

API: GET https://api.mercadopago.com/v1/payments/search (pagos de los últimos 12 meses, solo `approved`) con el filtro
`payer.id` (lo que pagaste: gasto) y `collector.id` (lo que te pagaron: ingreso). El id de la persona sale de GET /users/me.

Beta: la documentación muestra esos filtros pero no los describe, así que falta confirmar con una cuenta real que aparecen todas las
compras y transferencias. La llave de Mercado Pago da acceso completo a la cuenta (no existe una de solo lectura): Alcancía solo la
usa para leer y la guarda cifrada en el Llavero.
"""
from datetime import timedelta

from conectores import Error
from conectores._util import fecha_local, numero

BASE = "https://api.mercadopago.com"
INFO = {
    "id": "mercadopago", "nombre": "Mercado Pago", "paises": ["AR", "BR", "CL", "CO", "MX", "PE", "UY"], "hosts": ["api.mercadopago.com"],
    "campos": [{"id": "token", "etiqueta": "Access Token de producción", "secreto": True}],
    "enlace": "https://www.mercadopago.cl/developers/panel/app",
    "pasos": [
        "Entra a **Mercado Pago Developers** con tu cuenta, abre **Tus integraciones** y toca **Crear aplicación**.",
        "En «Elige una solución para integrar» deja **Checkout Pro** (da lo mismo cuál: Alcancía solo lee tus pagos y no cobra nada).",
        "En **Otros datos**, cambia el nombre por **Alcancia**, marca la casilla de autorización y toca **Crear aplicación**.",
        "Dentro de la aplicación, abre **Credenciales de producción** (en el menú de la izquierda). Si te pide activarlas, elige la industria «Otros» y como sitio web https://alcancia-app.github.io/alcancia/.",
        "Copia el **Access Token** (empieza con `APP_USR-`; no la Public Key) y pégalo aquí.",
    ],
    "nota": "Ojo: la llave de Mercado Pago da acceso completo a tu cuenta (Mercado Pago no ofrece una de solo lectura). Alcancía solo la usa para leer tus pagos, la guarda cifrada en tu computador y nunca sale de ahí salvo hacia Mercado Pago.",
    "dias_inicio": 180, "estado": "beta",
}
TIPOS = {"money_transfer": "Transferencia", "regular_payment": "Pago", "account_fund": "Carga de saldo", "recurring_payment": "Suscripción",
         "pos_payment": "Pago en tienda", "investment": "Inversión", "cellphone_recharge": "Recarga de celular"}


def _cab(cred):
    return {"Authorization": "Bearer " + str(cred.get("token", "")).strip()}


def _yo(cred, red):
    u = red.get(f"{BASE}/users/me", cabeceras=_cab(cred))
    if not isinstance(u, dict) or not u.get("id"):
        raise Error("Mercado Pago no me dijo de quién es la cuenta. Revisa que copiaste el Access Token de producción.")
    return u


def probar(cred, red):
    u = _yo(cred, red)
    return None, [{"id": "", "nombre": "Mercado Pago", "moneda": {"MLC": "CLP", "MLA": "ARS", "MLB": "BRL", "MLM": "MXN", "MCO": "COP",
                                                                   "MPE": "PEN", "MLU": "UYU"}.get(u.get("site_id"), "")}]


def _fecha_mp(d, fin=False):
    return d.strftime("%Y-%m-%dT23:59:59.999-00:00" if fin else "%Y-%m-%dT00:00:00.000-00:00")


def _buscar(cred, red, filtro, yo, desde, hasta):
    r, offset = [], 0
    while True:
        q = (f"{BASE}/v1/payments/search?sort=date_created&criteria=desc&range=date_created&begin_date={_fecha_mp(desde)}"
             f"&end_date={_fecha_mp(hasta, True)}&{filtro}={yo}&limit=50&offset={offset}")
        resp = red.get(q, cabeceras=_cab(cred))
        lote = resp.get("results") or []
        r += lote
        total = (resp.get("paging") or {}).get("total", 0)
        offset += len(lote)
        if not lote or offset >= total or offset >= 1000:  # la API no deja pasar de ~1000 filas por búsqueda
            return r


def movimientos(cred, desde, hasta, memoria, red):
    desde = max(desde, hasta - timedelta(days=364))  # la búsqueda acepta rangos de menos de un año
    yo = _yo(cred, red)["id"]
    vistos = {}  # id del pago → (pago, signos en que apareció)
    for filtro, signo in (("payer.id", -1), ("collector.id", 1)):
        for p in _buscar(cred, red, filtro, yo, desde, hasta):
            if p.get("status") != "approved" or p.get("id") is None:
                continue
            vistos.setdefault(p["id"], [p, set()])[1].add(signo)
    movs = []
    for pid, (p, signos) in vistos.items():
        monto = numero(p.get("transaction_amount"))
        f = fecha_local(p.get("date_approved") or p.get("date_created"))
        if monto is None or not f:
            continue
        tipo = TIPOS.get(p.get("operation_type"), "")
        desc = p.get("description") or tipo or "Mercado Pago"
        if tipo and tipo.lower() not in desc.lower():
            desc = f"{tipo}: {desc}"
        # Un pago tuyo a ti mismo (cargar saldo, mover a una reserva, comprar el fondo que rinde) aparece en las dos búsquedas:
        # no es gasto ni ingreso, es plata que se mueve entre tus cuentas. Queda una sola vez y como «Entre mis cuentas».
        propio = len(signos) == 2 or (p.get("collector_id") == yo and (p.get("payer") or {}).get("id") == yo)
        signo = 1 if propio else next(iter(signos))
        m = {"cuenta": "", "id_externo": f"{pid}|{'pagado' if signo < 0 else 'recibido'}", "fecha": f,
             "descripcion": desc, "monto": signo * abs(monto), "moneda": p.get("currency_id") or ""}
        if propio:
            m["categoria"] = "transferencia"
        movs.append(m)
    return movs, {}, None


def reparar(lista):
    """Arregla lo guardado por la versión anterior, que anotaba cada pago a ti mismo dos veces (un gasto y un ingreso iguales).
    Quita el gasto espejo y deja el ingreso como «Entre mis cuentas» (si no le habías puesto otra categoría). Devuelve cuántos quitó."""
    clave = lambda m: (m["fecha"][:10], abs(float(m["monto"] or 0)), m["descripcion"], m["cuenta"])
    positivos = {}
    for m in lista:
        if m.get("origen") == "conector:mercadopago" and float(m["monto"] or 0) > 0:
            positivos.setdefault(clave(m), []).append(m)
    quitar = set()
    for m in lista:
        if m.get("origen") == "conector:mercadopago" and float(m["monto"] or 0) < 0:
            pares = positivos.get(clave(m))
            if pares:
                par = pares.pop()
                quitar.add(m["id"])
                if not par.get("categoria"):
                    par["categoria"] = "transferencia"
    lista[:] = [m for m in lista if m["id"] not in quitar]
    return len(quitar)
