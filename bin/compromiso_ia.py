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


def limpiar_texto(texto):
    """Lo que la persona escribió, sin caracteres de control, sin RUT (con o sin puntos y guion), sin corridas de 7 o más dígitos
    seguidos (un RUT o una cuenta sin separadores) y sin números de 10 o más dígitos con espacios o guiones (cuentas, tarjetas).
    Los montos con separador de miles («500.000», «1.250.000») y los de hasta 6 dígitos («500000») se mantienen."""
    t = re.sub(r"[\x00-\x1f\x7f]", " ", str(texto or ""))
    # Un monto grande escrito sin puntos pero con «$» o la moneda al lado («$1500000», «1500000 clp») es plata, no una cuenta:
    # se escribe con separador de miles para que pase.
    miles = lambda n: f"{int(n):,}".replace(",", ".")
    t = re.sub(r"(\$\s?)(\d{7,9})(?!\d)", lambda m: m.group(1) + miles(m.group(2)), t)
    t = re.sub(r"(?<![\d.])(\d{7,9})(\s?(?:clp|pesos|usd|ars|mxn|cop|pen|brl|uyu)\b)", lambda m: miles(m.group(1)) + m.group(2), t, flags=re.I)
    t = re.sub(r"(?<![\d.])\d{1,2}\.?\d{3}\.?\d{3}-[\dkK](?![\dA-Za-z])", " ", t)
    t = re.sub(r"(?<!\d)\d{7,8}[kK](?![A-Za-z\d])", " ", t)
    t = re.sub(r"(?<!\d)\d{7,}(?!\d)", " ", t)
    t = re.sub(r"\d(?:[\s\-]?\d){9,}", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:LARGO_MAXIMO]


def prompt(texto, hoy, categorias, moneda):
    lista = "\n".join(f"{c['id']}: {c['nombre']} ({c.get('tipo', 'gasto')})" for c in categorias)
    return f"""Eres parte de una app de finanzas personales. La persona describe con sus palabras algo que paga o recibe seguido
(una deuda, una cuenta, una suscripción, una transferencia frecuente o un ingreso). Conviértelo en UN objeto JSON.

Hoy es {hoy}. Moneda por defecto: {moneda}.

Campos (usa solo estos; los que no sepas, déjalos fuera):
- nombre: corto y claro (máximo 60 caracteres), p. ej. «Crédito hipotecario».
- tipo: «deuda», «cuenta», «suscripcion», «transferencia», «ingreso» u «otro».
- signo: «gasto» o «ingreso».
- monto: número positivo, sin puntos de miles ni símbolos (450.000 → 450000).
- moneda: código de 3 letras.
- frecuencia: «mensual», «semanal», «anual» o «una_vez».
- dia: número; en mensual el día del mes (1 a 31); en semanal 1 = lunes … 7 = domingo.
- fecha: AAAA-MM-DD, solo en anual o una_vez.
- categoria: el id de una de estas categorías:
{lista}
- buscar: lista de 1 a 3 palabras que seguramente aparecen en la cartola cuando se paga (p. ej. ["DIVIDENDO"]).
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
    if not compromisos._fecha_valida(hoy):
        return {"ok": False, "error": "Fecha inválida."}
    texto = limpiar_texto(texto)
    if len(texto) < 4:
        return {"ok": False, "error": "Cuéntame qué pagas, cuánto y cuándo."}
    moneda = datos.presupuesto().get("moneda") or datos.config()["moneda"]
    categorias = datos.categorias()
    respuesta, error = ia.preguntar(prompt(texto, hoy, categorias, moneda), timeout=180)
    if error:
        return {"ok": False, "error": error}
    propuesta = leer_json(respuesta)
    if propuesta is None:
        return {"ok": False, "error": f"{ia.nombre()} no respondió con un compromiso. Inténtalo de nuevo o agrégalo a mano."}
    limpio, problemas = compromisos.validar(propuesta, {c["id"] for c in categorias}, hoy, moneda, estricto=True)
    if problemas:
        return {"ok": False, "error": f"No entendí bien lo que propuso {ia.nombre()}: " + " ".join(problemas[:3]) + " Revísalo o agrégalo a mano."}
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
