#!/usr/bin/env python3
"""IA falsa para las pruebas: se instala como «claude» en un PATH temporal y responde según lo que se le pide. Nunca sale a internet."""
import json
import re
import sys

pedido = sys.stdin.read()
if "Clasifica cada movimiento" in pedido:
    filas = re.findall(r"^(\d+)\|", pedido.split("Movimientos (número|descripción|monto):")[-1], re.M)
    print("\n".join(f"{n}|otros" for n in filas))
elif "Necesito una «receta»" in pedido:
    print("Claro, aquí está:\n```json\n" + json.dumps({
        "formato": 1, "id": "cl-banco-ejemplo", "nombre": "Banco Ejemplo — cuenta corriente", "institucion": "Banco Ejemplo",
        "pais": "CL", "moneda": "CLP", "tipo": "cartola", "archivo": {"extension": ["csv"], "separador": ";"},
        "reconocer": {"encabezados": ["Fecha", "Descripción", "Cargos", "Abonos"]},
        "columnas": {"fecha": "Fecha", "descripcion": "Descripción", "cargo": "Cargos", "abono": "Abonos"},
        "fecha": "%d/%m/%Y", "numeros": {"decimal": ",", "miles": "."}, "signo": "normal", "ignorar_si_contiene": ["SALDO INICIAL"],
    }, ensure_ascii=False) + "\n```")
elif "coach de finanzas" in pedido:
    print("### Lo que va bien\n- Vas bien.\n\n### Ojo con\n- El delivery.\n\n### Para esta semana\n- Cocina 3 noches.")
else:
    print("listo")
