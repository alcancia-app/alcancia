"""Tu IA aprende a leer una cartola que Alcancía aún no conoce. Solo biblioteca estándar.

  receta_ia.py <archivo> <pais> <salida.json>

Le muestra a la IA las primeras filas (en tu computador, con tu cuenta), le pide una receta, la valida y la prueba con el
mismo archivo. No guarda nada: la app la guarda cuando la persona confirma que los movimientos se ven bien.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datos  # noqa: E402
import ia  # noqa: E402
import pdf  # noqa: E402
import recetas  # noqa: E402

EJEMPLO = {
    "formato": 1, "id": "cl-banco-ejemplo", "nombre": "Banco Ejemplo — cuenta corriente", "institucion": "Banco Ejemplo",
    "pais": "CL", "moneda": "CLP", "tipo": "cartola", "archivo": {"extension": ["csv"], "separador": ";"},
    "reconocer": {"encabezados": ["Fecha", "Descripción", "Cargos", "Abonos"]},
    "columnas": {"fecha": "Fecha", "descripcion": "Descripción", "cargo": "Cargos", "abono": "Abonos"},
    "fecha": "%d/%m/%Y", "numeros": {"decimal": ",", "miles": "."}, "signo": "normal", "ignorar_si_contiene": ["SALDO"],
}


def prompt(nombre_archivo, muestra, pais):
    es_pdf = nombre_archivo.lower().endswith(".pdf")
    nota_pdf = ("\nEl archivo es un PDF: Alcancía ya sacó su texto y lo armó como tabla (cada fila es una línea de la página y las "
                "celdas van por columna). Usa archivo.extension [\"pdf\"] y no pongas separador.\n") if es_pdf else ""
    return f"""Eres parte de una app de finanzas personales de código abierto. Necesito una «receta»: un JSON que explica cómo
leer este archivo de movimientos bancarios. El archivo se llama «{nombre_archivo}» y la persona vive en el país {pais}.

Primeras filas del archivo (celdas separadas por « | »):
{muestra}
{nota_pdf}
Reglas de la receta:
- Solo estos campos: formato (siempre 1), id («pais-institucion-producto», minúsculas y guiones), nombre, institucion, pais
  (2 letras), moneda (3 letras), tipo (siempre «cartola»), archivo (extension: lista; separador si es csv), reconocer.encabezados
  (los nombres EXACTOS de las columnas de la fila de encabezados que identifican el archivo), columnas (une fecha, descripcion y
  monto — o cargo y abono si vienen separados — con el nombre exacto de su columna; opcional detalle y moneda), fecha (formato de
  Python strptime, o lista), numeros (decimal y miles), signo («normal» si los gastos vienen negativos o en columna de cargos;
  «invertido» si los gastos vienen positivos en una sola columna de monto), ignorar_si_contiene (filas de saldo o totales).
- Nunca pongas datos de las filas (montos, nombres, comercios) dentro de la receta: solo nombres de columnas y formatos.

Ejemplo de una receta válida (de un banco ficticio):
{json.dumps(EJEMPLO, ensure_ascii=False, indent=2)}

Responde SOLO con el JSON de la receta, sin explicaciones."""


def main(archivo, pais, salida):
    try:
        muestra = recetas.muestra(archivo)
    except pdf.PdfError as e:
        return {"ok": False, "error": str(e)}
    except (OSError, ValueError) as e:
        return {"ok": False, "error": f"No pude leer el archivo: {e}"}
    texto, error = ia.preguntar(prompt(os.path.basename(archivo), muestra, pais))
    if error:
        return {"ok": False, "error": error}
    receta = recetas.leer_receta_texto(texto)
    problemas = recetas.validar(receta) if receta is not None else [f"{ia.nombre()} no devolvió una receta."]
    if problemas:
        return {"ok": False, "error": f"La receta que propuso {ia.nombre()} no sirve: " + " ".join(problemas[:3])}
    receta["autor"] = "ia"
    # La receta tiene que reconocer el archivo con que se probó (si la IA puso otra extensión, se agrega la de este archivo).
    ext = os.path.splitext(archivo)[1].lower().lstrip(".")
    a = receta.setdefault("archivo", {})
    if ext and isinstance(a.get("extension"), list) and ext not in a["extension"]:
        a["extension"].append(ext)
    if ext == "pdf":
        a.pop("separador", None)
    movs, avisos = recetas.aplicar(archivo, receta, "vista")
    if not movs:
        return {"ok": False, "error": f"Con la receta de {ia.nombre()} no salió ningún movimiento. " + " ".join(avisos[:1])}
    return {"ok": True, "receta": receta, "total": len(movs), "avisos": avisos,
            "muestra": sorted(movs, key=lambda m: m["fecha"], reverse=True)[:6]}


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    r = main(sys.argv[1], sys.argv[2], sys.argv[3])
    datos.escribir_json(sys.argv[3], r)
    print(json.dumps(r, ensure_ascii=False)[:400])
