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
elif "Eres Alcancía, la alcancía" in pedido:  # la conversación con Alcancía (bin/chat.py)
    ultimo = pedido.split("Último mensaje de la persona: «", 1)[-1].split("»\n", 1)[0]
    lineas = re.findall(r"^(C\d+) · (.*)$", pedido, re.M)
    ref = lambda *p: next((r for r, l in lineas if any(x in l.upper() for x in p)), "C99")
    responder = lambda texto, acciones: print("```json\n" + json.dumps({"respuesta": texto, "acciones": acciones}, ensure_ascii=False) + "\n```")
    if "INVALIDA" in ultimo:
        print("Claro, te ayudo con eso.")  # sin JSON: no sirve
    elif "RARA" in ultimo:  # una acción que no existe, otra con un campo de más y una buena: solo pasa la buena
        responder("Te dejo lo que entendí.", [{"tipo": "borrar_todo"}, {"tipo": "marcar_pagado", "compromiso": "C1", "comando": "rm"},
                                               {"tipo": "crear_compromiso", "compromiso": {"nombre": "Gimnasio", "tipo": "suscripcion", "monto": 25000,
                                                                                          "frecuencia": "mensual", "dia": 3}}])
    elif "busc" in ultimo.lower().replace("ú", "u") or "cuánto me cobra" in ultimo.lower():  # la IA no ve los movimientos: pide que el código busque
        que = next((p for p in ("Netflix", "Gimnasio", "Colegio", "Dividendo") if p.lower() in ultimo.lower()), "algo")
        responder("Déjame buscarlo en tus movimientos.", [{"tipo": "buscar_pago", "texto": que}])
    elif "netflix" in ultimo.lower() or "colegio" in ultimo.lower():  # sin monto ni día: la app lo busca y lo completa (o no)
        nombre = "Netflix" if "netflix" in ultimo.lower() else "Colegio"
        responder("Lo anoto, pero me falta el monto.", [{"tipo": "crear_compromiso", "compromiso": {
            "nombre": nombre, "tipo": "suscripcion" if nombre == "Netflix" else "cuenta", "frecuencia": "mensual", "buscar": [nombre.upper()],
            **({"pago": "automatico"} if nombre == "Netflix" else {})}}])
    elif "OTRACUOTA" in ultimo:  # un préstamo suelto que ya podría estar anotado: la app pregunta si es el mismo
        responder("Lo anoto. Ojo: ya tienes un préstamo con tu mamá; dime si es el mismo.", [{"tipo": "crear_compromiso", "compromiso": {
            "tipo": "prestamo", "con": "Mamá", "signo": "gasto", "prestamo": {"total": 1500000}, "cuotas_total": 12}}])
    elif "prest" in ultimo.lower():
        responder("Veamos cuánto te cabe al mes sin salirte de tus gastos.", [{"tipo": "plan_prestamos", "deudas": [
            {"con": "Mamá", "total": 1500000}, {"con": "Tío Matías", "total": 4000000, "interes": 0}]}])
    elif "aún no" in ultimo.lower() or "aun no" in ultimo.lower():
        responder("Entonces ese pago era del mes pasado. ¿Lo corrijo?", [{"tipo": "reasignar_pago", "compromiso": ref("DIVIDENDO", "HIPOTEC")}])
    elif "ya pagué" in ultimo.lower():
        responder("¡Bien! Lo marco como pagado.", [{"tipo": "marcar_pagado", "compromiso": ref("ARRIENDO")}])
    elif "subió" in ultimo.lower():
        responder("Anotado el monto nuevo.", [{"tipo": "editar_compromiso", "compromiso": ref("ARRIENDO"), "cambios": {"monto": 470000}}])
    elif "SINMONTO" in ultimo:
        responder("Casi: me falta el monto.", [{"tipo": "crear_compromiso", "compromiso": {"nombre": "Clases de yoga", "tipo": "suscripcion",
                                                                                           "frecuencia": "mensual", "dia": 3}}])
    else:
        responder("Lo anoto para recordártelo.", [{"tipo": "crear_compromiso", "compromiso": {
            "nombre": "Arriendo bodega", "tipo": "cuenta", "monto": 85000, "frecuencia": "mensual", "dia": 5, "pago": "manual"}}])
elif "Conviértelo en UN objeto JSON" in pedido:
    texto = pedido.split("Texto de la persona: «", 1)[-1].split("»", 1)[0]
    if "ROMPER" in texto:
        print('{"nombre": "Algo", "monto": 1000, "dia": 5, "comando": "rm -rf"}')
    elif "NADA" in texto:
        print("No entendí.")
    elif "me prestó" in texto or "me presto" in texto:  # un préstamo de una persona (montos dichos como sea: la IA los entiende)
        print(json.dumps({"tipo": "prestamo", "con": "Tía", "signo": "gasto", "prestamo": {"total": 1800000}, "cuotas_total": 12,
                          "frecuencia": "mensual", "categoria": "otros"}))
    elif "le presté" in texto:
        print(json.dumps({"tipo": "prestamo", "con": "Matías", "signo": "ingreso", "prestamo": {"total": 850000}, "cuotas_total": 5}))
    elif "se cobra solo" in texto:  # una suscripción que se paga sola
        print(json.dumps({"nombre": "Streaming Ejemplo", "tipo": "suscripcion", "monto": 7990, "frecuencia": "mensual", "dia": 12,
                          "categoria": "suscripciones", "buscar": ["STREAMING EJEMPLO"], "pago": "automatico"}))
    elif "PAGORARO" in texto:  # una forma de pago que no existe: no pasa la validación
        print(json.dumps({"nombre": "Plan funerario", "tipo": "suscripcion", "monto": 25000, "dia": 5, "pago": "a veces"}))
    elif "SINMONTO" in texto:  # la IA entendió casi todo, pero no el monto: igual se abre la tarjeta con lo demás
        print(json.dumps({"nombre": "Gimnasio", "tipo": "suscripcion", "monto": 0, "frecuencia": "mensual", "dia": 3, "buscar": ["GIMNASIO"]}))
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
