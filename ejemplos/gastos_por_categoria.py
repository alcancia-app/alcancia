"""Ejemplo: cuánto gastaste por categoría en un mes, leyendo directo el formato abierto de Alcancía.

Uso: python3 ejemplos/gastos_por_categoria.py 2026-10        (carpeta: ~/Alcancia o la variable ALCANCIA_CARPETA)
Solo biblioteca estándar. Sirve de punto de partida para tus propios scripts.
"""
import csv
import os
import sys

carpeta = os.environ.get("ALCANCIA_CARPETA") or os.path.join(os.path.expanduser("~"), "Alcancia")
mes = sys.argv[1] if len(sys.argv) > 1 else ""
if len(mes) != 7:
    sys.exit("Uso: python3 ejemplos/gastos_por_categoria.py AAAA-MM")

totales = {}
with open(os.path.join(carpeta, "movimientos", f"{mes}.csv"), encoding="utf-8", newline="") as f:
    for m in csv.DictReader(f):
        monto = float(m["monto"])
        if monto < 0 and m["categoria"] != "transferencia":
            totales[m["categoria"] or "sin categoría"] = totales.get(m["categoria"] or "sin categoría", 0) - monto

for categoria, total in sorted(totales.items(), key=lambda x: -x[1]):
    print(f"{categoria:<20} {total:>12,.0f}".replace(",", "."))
print(f"{'TOTAL':<20} {sum(totales.values()):>12,.0f}".replace(",", "."))
