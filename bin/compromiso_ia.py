"""«Cuéntale a Alcancía»: tu IA convierte lo que escribes («tengo que pagar el dividendo los 15, son 500.000») en un compromiso.
Solo biblioteca estándar.

  compromiso_ia.py entender <entrada.json> <salida.json>     entrada: {"texto": "...", "hoy": "AAAA-MM-DD"}

El texto llega en un archivo de entrada, nunca como argumento (los argumentos de un proceso los puede ver cualquier programa del
computador). A la IA le llega SOLO tu texto (sin RUT ni números largos, que se borran antes), la fecha de hoy y la lista de categorías.
Lo que devuelve se valida estrictamente (compromisos.validar); si no cumple, no se guarda nada y se avisa. Tampoco se guarda nada
si cumple: la interfaz muestra la tarjeta para que la persona la revise y confirme.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compromisos  # noqa: E402
import datos  # noqa: E402
import ia  # noqa: E402

LARGO_MAXIMO = 500


#: Palabras que anuncian un número de identificación: lo que viene después (6 o más dígitos) se borra.
PALABRAS_ID = (r"cuenta\s*rut|cuentarut|rut|cta\.?\s*cte\.?|cuenta\s+(?:corriente|vista)|cuenta|cta\.?|tarjeta|n[°º]\.?|nro\.?"
               r"|n[uú]mero|vista")


def digito_verificador(cuerpo):
    """El dígito verificador de un RUT (módulo 11): «0»–«9» o «K»."""
    s, f = 0, 2
    for d in reversed(cuerpo):
        s += int(d) * f
        f = 2 if f == 7 else f + 1
    r = 11 - s % 11
    return "0" if r == 11 else "K" if r == 10 else str(r)


def limpiar_texto(texto):
    """Lo que la persona escribió, sin caracteres de control y sin números que identifiquen a alguien:
    - un RUT con guion o con K (con o sin puntos: dígitos, guion y dígito verificador o K), y uno de 8–9 dígitos pegados cuyo dígito
      verificador calza (si no termina en «000», que es un monto redondo);
    - lo que va después de rut, cuenta, cta., tarjeta, n°, nro., número o vista (6 o más dígitos);
    - números de 10 o más dígitos (cuentas, tarjetas), aunque vengan con espacios o guiones.
    Los montos pasan: «2000000», «1500000», «500.000», «1.250.000», «$1500000»."""
    t = re.sub(r"[\x00-\x1f\x7f]", " ", str(texto or ""))
    # Un monto grande escrito sin puntos pero con «$» o la moneda al lado («$1500000», «1500000 clp») va con separador de miles.
    miles = lambda n: f"{int(n):,}".replace(",", ".")
    t = re.sub(r"(\$\s?)(\d{7,9})(?!\d)", lambda m: m.group(1) + miles(m.group(2)), t)
    t = re.sub(r"(?<![\d.])(\d{7,9})(\s?(?:clp|pesos|usd|ars|mxn|cop|pen|brl|uyu)\b)", lambda m: miles(m.group(1)) + m.group(2), t, flags=re.I)
    # Lo que viene después de una palabra de identificación.
    def sin_id(m):
        return m.group(1) + " " if len(re.sub(r"\D", "", m.group(2))) >= 6 else m.group(0)
    t = re.sub(rf"(?i)(\b(?:{PALABRAS_ID})\s*(?:de\s+|:\s*|#\s*)?)(\d(?:[\d.\s-]*\d)?[kK]?)(?![\dA-Za-z])", sin_id, t)
    # RUT con guion o con K.
    t = re.sub(r"(?<![\d.])\d{1,2}\.?\d{3}\.?\d{3}-[\dkK](?![\dA-Za-z])", " ", t)
    t = re.sub(r"(?<![\d.])\d{7,8}[kK](?![A-Za-z\d])", " ", t)
    # RUT sin puntos ni guion: 8–9 dígitos cuyo último es el verificador del resto (y no un monto redondo).
    t = re.sub(r"(?<![\d.,])(\d{7,8})(\d)(?![\d.,]?\d)",
               lambda m: " " if digito_verificador(m.group(1)) == m.group(2) and not (m.group(1) + m.group(2)).endswith("000") else m.group(0), t)
    t = re.sub(r"\d(?:[\s\-]?\d){9,}", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:LARGO_MAXIMO]


def prompt(texto, hoy, categorias, moneda):
    lista = "\n".join(f"{c['id']}: {c['nombre']} ({c.get('tipo', 'gasto')})" for c in categorias)
    return f"""Eres parte de una app de finanzas personales. La persona describe con sus palabras algo que paga o recibe seguido
(una deuda, una cuenta, una suscripción, una transferencia frecuente o un ingreso). Conviértelo en UN objeto JSON.

Hoy es {hoy}. Moneda por defecto: {moneda}.

Campos (usa solo estos; los que no sepas, déjalos fuera):
- nombre: corto y claro (máximo 60 caracteres), p. ej. «Crédito hipotecario».
- tipo: «deuda», «prestamo», «cuenta», «suscripcion», «transferencia», «ingreso» u «otro». Usa «prestamo» cuando la plata la
  prestó o la debe una persona (papá, mamá, un amigo, un hermano: «mi papá me prestó…», «le presté a…»); «deuda» es con un banco o
  una empresa (crédito hipotecario, de consumo, automotriz, tarjeta).
- con (solo en «prestamo»): con quién, corto y sin apellidos ni números (p. ej. «Papá», «Matías»).
- prestamo (solo en «prestamo»): {{"total": lo prestado, "interes": % simple sobre el total si lo dice (si no, 0)}}. Pon además
  cuotas_total (en cuántas cuotas o meses) y signo «gasto» si la persona debe o «ingreso» si le deben. No pongas monto: la app
  calcula la cuota. Si no dice el día, no pongas dia (la app usa su día de pago).
- signo: «gasto» o «ingreso».
- monto: número positivo, sin puntos de miles ni símbolos (450.000 → 450000). Montos dichos con palabras: «3M», «3 millones» o
  «3 palos» = 3000000; «800 lucas» u «800 mil» = 800000; «1,5 millones» = 1500000. En UF, con decimales con punto (12,75 UF → 12.75).
- moneda: código de 3 letras, o «UF» si dice que se paga en UF (unidad de fomento); entonces el monto va en UF, no en pesos.
- aproximado: solo si dice que el monto varía («aprox.», «más o menos», «alrededor de», «entre X e Y»): {{"variacion": N}}
  con el porcentaje que varía (si no lo dice, 3), o {{"min": X, "max": Y}} si da un rango (en la misma moneda que el monto, y el
  monto entre los dos, p. ej. el del medio).
- frecuencia: «mensual», «semanal», «anual» o «una_vez».
- dia: número; en mensual el día del mes (1 a 31); en semanal 1 = lunes … 7 = domingo.
- fecha: AAAA-MM-DD, solo en anual o una_vez.
- categoria: el id de una de estas categorías:
{lista}
- buscar: lista de 1 a 3 palabras que seguramente aparecen en la cartola cuando se paga (p. ej. ["DIVIDENDO"]). Nunca palabras
  genéricas que aparecen en cualquier movimiento (TRANSFERENCIA, PAGO, COMPRA, ABONO, CARGO, CUOTA); si no sabes, déjalo fuera.
- cuotas_total, cuotas_pagadas o cuotas_restantes: números enteros, solo si la persona los dice.
- fecha_fin: AAAA-MM-DD, si dice cuándo termina.
- saldo: número, si dice cuánto le queda por pagar en total.

Texto de la persona: «{texto}»

Responde SOLO con el JSON, sin explicaciones."""


def leer_json(texto):
    """El primer objeto JSON de la respuesta (puede venir dentro de ```json … ```). None si no hay."""
    i, j = (texto or "").find("{"), (texto or "").rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        v = json.loads(texto[i:j + 1])
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def main(texto, hoy):
    """Nunca deja a la persona sin salida: si la IA no responde o algo no cumple, devuelve `parcial` (lo que sí se entendió) y el
    error en simple, y la interfaz abre igual la tarjeta para corregirlo y guardar."""
    if not compromisos._fecha_valida(hoy):
        return {"ok": False, "error": "Fecha inválida.", "parcial": {}}
    texto = limpiar_texto(texto)
    if len(texto) < 4:
        return {"ok": False, "error": "Cuéntame qué pagas, cuánto y cuándo.", "parcial": {}}
    cfg = datos.config()
    moneda = datos.presupuesto().get("moneda") or cfg["moneda"]
    categorias = datos.categorias()
    ids = {c["id"] for c in categorias}
    respuesta, error = ia.preguntar(prompt(texto, hoy, categorias, moneda), timeout=180)
    if error:
        return {"ok": False, "error": error + " Mientras, puedes completarlo aquí.", "parcial": {}}
    propuesta = leer_json(respuesta)
    if propuesta is None:
        return {"ok": False, "error": f"{ia.nombre()} no respondió con un compromiso. Complétalo aquí y guárdalo.", "parcial": {}}
    propuesta = compromisos.completar_prestamo(propuesta, cfg)
    limpio, problemas = compromisos.validar(propuesta, ids, hoy, moneda, estricto=True)
    if problemas:
        return {"ok": False, "parcial": compromisos.parcial(propuesta, ids, moneda, cfg),
                "error": "No entendí todo: " + " ".join(problemas[:3]) + " Corrígelo aquí y guárdalo."}
    limpio["origen"] = "ia"
    return {"ok": True, "compromiso": limpio}


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "entender":
        print(__doc__)
        sys.exit(2)
    entrada = datos.leer_json(sys.argv[2], {})
    entrada = entrada if isinstance(entrada, dict) else {}
    r = main(str(entrada.get("texto") or ""), str(entrada.get("hoy") or ""))
    datos.escribir_json(sys.argv[3], r)
    print(json.dumps(r, ensure_ascii=False)[:400])
