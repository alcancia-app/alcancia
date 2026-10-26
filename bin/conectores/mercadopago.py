"""Mercado Pago (Argentina, Brasil, Chile, Colombia, México, Perú, Uruguay): pagos que hiciste y recibiste.

API: GET https://api.mercadopago.com/v1/payments/search (pagos de los últimos 12 meses: `approved`, y también `refunded` y
`charged_back` para anotar la devolución) con el filtro `payer.id` (lo que pagaste: gasto) y `collector.id` (lo que te pagaron:
ingreso). El id de la persona sale de GET /users/me.

Cómo se pagó (columnas `medio`, `cuotas`, `cuota` de los movimientos): `payment_type_id` account_money → saldo, debit_card y
prepaid_card → débito, credit_card (y los créditos de Mercado Pago, `consumer_credits`) → crédito; `installments` y
`transaction_details.installment_amount` dan las cuotas. Lo devuelto (`transaction_amount_refunded`, o todo si el estado es
`refunded`/`charged_back`) queda como un movimiento aparte, «Devolución: …», del signo contrario y con id «<pago>|devolucion».

Saldo: GET /users/{id}/mercadopago_account/balance → `available_balance` (el disponible que muestra la app; si no viene,
`total_amount`). Si Mercado Pago no lo entrega para cuentas de personas, no pasa nada: se usa el saldo que anota la persona.

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


#: Al subir REPARACIONES en sincronizar.py, se vuelve a pedir este rango (el máximo que deja la búsqueda) para completar lo guardado.
RELEER_DIAS = 364
MEDIOS = {"account_money": "saldo", "debit_card": "debito", "prepaid_card": "debito", "credit_card": "credito",
          "digital_currency": "credito", "ticket": "otro", "atm": "otro", "bank_transfer": "otro"}
ESTADOS = ("approved", "refunded", "charged_back")


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
            if p.get("status") not in ESTADOS or p.get("id") is None:
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
        # Un pago tuyo a ti mismo aparece en las dos búsquedas: queda una sola vez. Si la plata se mueve dentro de Mercado Pago
        # (a una reserva, al fondo que rinde) es «Entre mis cuentas». Una carga de saldo, en cambio, es plata que entra a Mercado
        # Pago desde afuera (muchas veces el sueldo): queda como ingreso sin categoría para que la persona, sus reglas o su IA digan qué es.
        propio = len(signos) == 2 or (p.get("collector_id") == yo and (p.get("payer") or {}).get("id") == yo)
        signo = 1 if propio else next(iter(signos))
        m = {"cuenta": "", "id_externo": f"{pid}|{'pagado' if signo < 0 else 'recibido'}", "fecha": f,
             "descripcion": desc, "monto": signo * abs(monto), "moneda": p.get("currency_id") or ""}
        if propio and p.get("operation_type") != "account_fund":
            m["categoria"] = "transferencia"
        if signo < 0 and not propio:
            m.update(_como_se_pago(p))
        movs.append(m)
        devuelto = abs(monto) if p.get("status") in ("refunded", "charged_back") else numero(p.get("transaction_amount_refunded")) or 0
        if devuelto > 0 and not propio:
            fechas = [fecha_local(r.get("date_created")) for r in p.get("refunds") or [] if isinstance(r, dict)]
            fd = max([x for x in fechas if x] or [fecha_local(p.get("date_last_updated")) or f])
            movs.append({"cuenta": "", "id_externo": f"{pid}|devolucion", "fecha": max(fd, f), "descripcion": f"Devolución: {desc}",
                         "monto": -signo * min(abs(devuelto), abs(monto)), "moneda": m["moneda"],
                         **({"medio": m["medio"]} if m.get("medio") else {})})
    return movs, {}, None


def _como_se_pago(p):
    """{"medio", "cuotas", "cuota"} de un pago tuyo (solo lo que Mercado Pago dice)."""
    tipo = p.get("payment_type_id") or ""
    medio = "credito" if p.get("payment_method_id") == "consumer_credits" else MEDIOS.get(tipo, "")
    r = {"medio": medio} if medio else {}
    n = p.get("installments")
    if medio == "credito" and isinstance(n, int) and not isinstance(n, bool) and 2 <= n <= 72:
        r["cuotas"] = n
        c = numero((p.get("transaction_details") or {}).get("installment_amount"))
        if c and c > 0:
            r["cuota"] = round(c, 2)
    return r


def saldo(cred, red):
    """El saldo disponible de la cuenta de Mercado Pago, como lo muestra la app."""
    yo = _yo(cred, red)
    b = red.get(f"{BASE}/users/{int(yo['id'])}/mercadopago_account/balance", cabeceras=_cab(cred))
    if not isinstance(b, dict):
        return []
    monto = next((numero(b[k]) for k in ("available_balance", "availableBalance", "total_amount", "totalAmount", "balance")
                  if k in b and numero(b[k]) is not None), None)
    if monto is None:
        return []
    moneda = str(b.get("currency_id") or b.get("currency") or "").upper()[:3]
    return [{"cuenta": "", "monto": monto, "moneda": moneda}]


def reparar(lista):
    """Arregla lo guardado por la versión anterior, que anotaba cada pago a ti mismo dos veces (un gasto y un ingreso iguales).
    Quita el gasto espejo y deja el ingreso como «Entre mis cuentas» (si no le habías puesto otra categoría), salvo las cargas de saldo,
    que quedan como ingreso sin categoría. Devuelve cuántos movimientos cambió."""
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
                if not par.get("categoria") and not par["descripcion"].lower().startswith("carga de saldo"):
                    par["categoria"] = "transferencia"
    lista[:] = [m for m in lista if m["id"] not in quitar]
    # La reparación anterior dejó las cargas de saldo como «Entre mis cuentas»; son plata que entra (p. ej. el sueldo).
    cargas = 0
    for m in lista:
        if (m.get("origen") == "conector:mercadopago" and m.get("categoria") == "transferencia" and float(m["monto"] or 0) > 0
                and m["descripcion"].lower().startswith("carga de saldo")):
            m["categoria"] = ""
            cargas += 1
    return len(quitar) + cargas
