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
elif "Conviértelo en UN objeto JSON" in pedido:
    texto = pedido.split("Texto de la persona: «", 1)[-1].split("»", 1)[0]
    if "ROMPER" in texto:
        print('{"nombre": "Algo", "monto": 1000, "dia": 5, "comando": "rm -rf"}')
    elif "NADA" in texto:
        print("No entendí.")
    elif "MALAPROX" in texto:  # un rango al revés: no pasa la validación
        print(json.dumps({"nombre": "Luz", "tipo": "cuenta", "monto": 30000, "dia": 8, "aproximado": {"min": 40000, "max": 20000}}))
    elif " UF" in texto:
        print(json.dumps({"nombre": "Dividendo", "tipo": "deuda", "monto": 12.75, "moneda": "UF", "frecuencia": "mensual", "dia": 15,
                          "categoria": "casa", "buscar": ["DIVIDENDO"], "aproximado": {"variacion": 2}}))
    elif "entre" in texto:
        print(json.dumps({"nombre": "Gastos comunes", "tipo": "cuenta", "monto": 95000, "frecuencia": "mensual", "dia": 10,
                          "categoria": "casa", "aproximado": {"min": 80000, "max": 110000}}))
    elif "aprox" in texto:
        print(json.dumps({"nombre": "Luz", "tipo": "cuenta", "monto": 30000, "frecuencia": "mensual", "dia": 8, "categoria": "cuentas",
                          "buscar": ["LUZ"], "aproximado": {"variacion": 3}}))
    else:
        print("```json\n" + json.dumps({"nombre": "Crédito hipotecario 12345678", "tipo": "deuda", "monto": 500000, "moneda": "CLP",
                                        "frecuencia": "mensual", "dia": 15, "categoria": "casa", "buscar": ["DIVIDENDO"],
                                        "cuotas_restantes": 120}, ensure_ascii=False) + "\n```")
elif "coach de finanzas" in pedido:
    print("### Lo que va bien\n- Vas bien.\n\n### Ojo con\n- El delivery.\n\n### Para esta semana\n- Cocina 3 noches.")
else:
    print("listo")
