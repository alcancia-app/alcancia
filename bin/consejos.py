"""Los consejos de tu IA: qué va bien, a qué ponerle ojo y qué hacer esta semana. Solo biblioteca estándar.

  consejos.py <hoy AAAA-MM-DD> <salida.json>

Le pasa a la IA de la persona solo números agrupados (por categoría y los comercios donde más gastó). Guarda el resultado en
~/Alcancia/consejos/AAAA-MM-DD.md. Si la respuesta no trae las tres secciones, no se guarda nada.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datos  # noqa: E402
import ia  # noqa: E402
import resumen  # noqa: E402

SECCIONES = ["Lo que va bien", "Ojo con", "Para esta semana"]


def mes_anterior(mes, n=1):
    a, m = map(int, mes.split("-"))
    m -= n
    while m < 1:
        a, m = a - 1, m + 12
    return f"{a:04d}-{m:02d}"


def prompt(hoy, movimientos, presupuesto, categorias):
    mes = hoy[:7]
    nombres = {c["id"]: c["nombre"] for c in categorias}
    r = resumen.resumen(movimientos, mes, hoy, presupuesto, categorias)
    lineas = [f"- {nombres.get(c, 'Sin categoría')}: {v} (presupuesto: {presupuesto.get('mensual', {}).get(c, 'sin definir')})"
              for c, v in r["por_categoria"].items()]
    historia = []
    for n in (1, 2, 3):
        anterior = mes_anterior(mes, n)
        ra = resumen.resumen(movimientos, anterior, hoy, presupuesto, categorias)
        if ra["gastado"]:
            top = ", ".join(f"{nombres.get(c, c)} {v}" for c, v in list(ra["por_categoria"].items())[:5])
            historia.append(f"- {anterior}: gastó {ra['gastado']} e ingresó {ra['ingresos']} ({top})")
    # Tendencia: solo el gasto total de cada mes (nada de movimientos ni comercios).
    h = resumen.historia(movimientos, mes, hoy, presupuesto, categorias)
    tendencia = [f"{m['mes']}: {m['gastado']}" + (f" (en curso; proyección {m['proyeccion']})" if m["proyeccion"] is not None else
                                                     " (en curso)" if m["en_curso"] else "") for m in h["meses"] if m["con_datos"]]
    if h["promedio"] is not None:
        tendencia.append(f"promedio de los meses anteriores: {h['promedio']}")
    comercios = {}
    for m in movimientos:
        if m["fecha"].startswith(mes) and m["monto"] < 0:
            clave = datos.normalizar(m["descripcion"])[:30]
            comercios[clave] = comercios.get(clave, 0) + -m["monto"]
    top = "\n".join(f"- {k}: {round(v)}" for k, v in sorted(comercios.items(), key=lambda x: -x[1])[:10])
    return f"""Eres un coach de finanzas personales cercano, honesto y práctico (nada de sermones). La persona usa una app para
controlar sus gastos porque le cuesta medirse. Hoy es {hoy} (día {r['dia']} de {r['dias_mes']}). Moneda: {r['moneda']}.

Este mes lleva gastado {r['gastado']} e ingresado {r['ingresos']}. Presupuesto total: {r['presupuesto'] or 'sin definir'}.
Proyección a fin de mes a este ritmo: {r['proyeccion'] if r['proyeccion'] is not None else 'aún no se puede calcular'}.

Por categoría este mes:
{chr(10).join(lineas) or '- (sin gastos aún)'}

Meses anteriores:
{chr(10).join(historia) or '- (sin historia aún)'}

Gasto total de los últimos 6 meses (del más antiguo al más reciente):
{chr(10).join("- " + t for t in tendencia) or '- (sin historia aún)'}

Donde más gastó este mes:
{top or '- (nada aún)'}

Escribe en español, en segunda persona, con frases cortas y montos concretos. Usa EXACTAMENTE estas tres secciones, con 1 a 3
viñetas cada una, y nada antes ni después:

### Lo que va bien
### Ojo con
### Para esta semana

En «Para esta semana» da acciones concretas y alcanzables (p. ej. «cocina 3 noches en vez de pedir delivery: ahorras cerca de 18.000»).
No recomiendes productos financieros, bancos ni inversiones."""


def validar(texto):
    """El texto desde la primera sección, si trae las tres en orden; si no, None."""
    pos = [texto.find(f"### {s}") for s in SECCIONES]
    if any(p < 0 for p in pos) or pos != sorted(pos):
        return None
    return texto[pos[0]:].strip()


def main(hoy, salida):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", hoy):
        return {"ok": False, "error": "Fecha inválida."}
    movimientos = datos.leer_todos()
    if not movimientos:
        return {"ok": False, "error": "Primero agrega movimientos: tu IA necesita algo que mirar."}
    texto, error = ia.preguntar(prompt(hoy, movimientos, datos.presupuesto(), datos.categorias()))
    if error:
        return {"ok": False, "error": error}
    limpio = validar(texto)
    if not limpio:
        return {"ok": False, "error": f"La respuesta de {ia.nombre()} no vino con el formato esperado. Inténtalo de nuevo."}
    ruta = os.path.join(datos.CONSEJOS, f"{hoy}.md")
    datos.escribir_atomico(ruta, f"---\nfecha: {hoy}\nia: {ia.elegida()}\n---\n\n{limpio}\n")
    return {"ok": True, "fecha": hoy, "texto": limpio}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    r = main(sys.argv[1], sys.argv[2])
    datos.escribir_json(sys.argv[2], r)
    print(json.dumps(r, ensure_ascii=False)[:400])
