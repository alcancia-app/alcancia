"""Recetas: cómo leer la cartola de cada banco o billetera, del mundo entero. Solo biblioteca estándar.

Una receta es un JSON de **solo datos** (nunca código) que dice qué columna es la fecha, cuál la descripción, cuál el monto y cómo
vienen escritos los números. Así cualquiera agrega su banco sin programar. Formato completo en recetas/README.md.

Se buscan en: ~/Alcancia/.alcancia/recetas/ (descargadas o creadas por la persona; ganan) y recetas/ del código (incluidas).
"""
import csv
import io
import json
import os
import re
import unicodedata
import zipfile
from datetime import date, datetime, timedelta
from xml.etree import ElementTree

import datos

FORMATO = 1
CLAVES = {"formato", "id", "nombre", "institucion", "pais", "moneda", "tipo", "archivo", "reconocer", "columnas", "fecha",
          "numeros", "signo", "ignorar_si_contiene", "autor", "notas"}
COLUMNAS = {"fecha", "descripcion", "monto", "cargo", "abono", "moneda", "detalle"}


# ───────────── Validar ─────────────
def validar(r):
    """Lista de problemas (vacía = receta válida). Todo lo que viene de afuera pasa por aquí antes de usarse."""
    if not isinstance(r, dict):
        return ["La receta no es un objeto JSON."]
    p = []
    if r.get("formato") != FORMATO:
        p.append(f"formato debe ser {FORMATO}.")
    if extra := set(r) - CLAVES:
        p.append("Campos desconocidos: " + ", ".join(sorted(extra)) + ".")
    if not re.fullmatch(r"[a-z]{2}-[a-z0-9-]{2,60}", str(r.get("id", ""))):
        p.append("id debe ser como «cl-mi-banco» (país + nombre, minúsculas y guiones).")
    for c in ("nombre", "institucion"):
        if not isinstance(r.get(c), str) or not r[c].strip() or len(r[c]) > 80 or "<" in r[c]:
            p.append(f"{c} debe ser un texto corto, sin HTML.")
    if not re.fullmatch(r"[A-Z]{2}", str(r.get("pais", ""))):
        p.append("pais debe ser un código de 2 letras (CL, AR, MX, ES…).")
    if not re.fullmatch(r"[A-Z]{3}", str(r.get("moneda", ""))):
        p.append("moneda debe ser un código de 3 letras (CLP, USD, EUR…).")
    if r.get("tipo") not in ("cartola",):
        p.append("tipo debe ser «cartola».")
    col = r.get("columnas")
    if not isinstance(col, dict) or not col or set(col) - COLUMNAS or not all(isinstance(v, str) and v for v in col.values()):
        p.append("columnas debe unir fecha, descripcion y monto (o cargo y abono) con el nombre de su columna.")
    else:
        if "fecha" not in col or "descripcion" not in col:
            p.append("columnas necesita fecha y descripcion.")
        if "monto" not in col and not ("cargo" in col or "abono" in col):
            p.append("columnas necesita monto, o cargo y/o abono.")
    rec = r.get("reconocer", {})
    if not isinstance(rec, dict) or not isinstance(rec.get("encabezados"), list) or not rec["encabezados"] \
            or not all(isinstance(x, str) for x in rec["encabezados"]):
        p.append("reconocer.encabezados debe ser una lista con los nombres de columna que identifican esta cartola.")
    f = r.get("fecha")
    if not (isinstance(f, str) or (isinstance(f, list) and f and all(isinstance(x, str) for x in f))):
        p.append("fecha debe ser un formato (p. ej. «%d/%m/%Y») o una lista de formatos.")
    num = r.get("numeros", {})
    if not isinstance(num, dict) or num.get("decimal", ",") not in (",", ".") or num.get("miles", ".") not in (",", ".", " ", "", "'"):
        p.append("numeros.decimal debe ser «,» o «.».")
    if r.get("signo", "normal") not in ("normal", "invertido"):
        p.append("signo debe ser «normal» o «invertido».")
    a = r.get("archivo", {})
    if not isinstance(a, dict) or not set(a) <= {"extension", "separador", "codificacion", "hoja"}:
        p.append("archivo solo acepta extension, separador, codificacion y hoja.")
    return p


def disponibles():
    """Todas las recetas válidas: las de la persona ganan sobre las incluidas con el mismo id."""
    todas = {}
    for carpeta in (os.path.join(datos.RECURSOS, "recetas"), os.path.join(datos.INTERNO, "recetas")):
        try:
            nombres = sorted(os.listdir(carpeta))
        except OSError:
            continue
        for n in nombres:
            if n.endswith(".json"):
                r = datos.leer_json(os.path.join(carpeta, n), None)
                if r is not None and not validar(r):
                    todas[r["id"]] = r
    return todas


# ───────────── Leer la tabla (CSV o Excel .xlsx) ─────────────
def _celdas_xlsx(ruta, hoja=None):
    """Lee un .xlsx con zipfile + XML (sin librerías). Devuelve filas de textos; las fechas de Excel quedan como número."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(ruta) as z:
        compartidos = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ElementTree.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                compartidos.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        hojas = sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        elegida = f"xl/worksheets/sheet{hoja}.xml" if hoja else (hojas[0] if hojas else "")
        filas = []
        for fila in ElementTree.fromstring(z.read(elegida)).iter(f"{{{ns['m']}}}row"):
            valores = {}
            for c in fila.findall("m:c", ns):
                ref = re.match(r"([A-Z]+)", c.get("r", "A"))
                col = 0
                for letra in ref.group(1):
                    col = col * 26 + ord(letra) - 64
                v = c.find("m:v", ns)
                t = c.get("t")
                if t == "s" and v is not None:
                    texto = compartidos[int(v.text)]
                elif t == "inlineStr":
                    texto = "".join(x.text or "" for x in c.iter(f"{{{ns['m']}}}t"))
                else:
                    texto = v.text if v is not None else ""
                valores[col - 1] = texto or ""
            if valores:
                filas.append([valores.get(i, "") for i in range(max(valores) + 1)])
        return filas


def leer_tabla(ruta, archivo=None):
    archivo = archivo or {}
    if ruta.lower().endswith(".xlsx"):
        return _celdas_xlsx(ruta, archivo.get("hoja"))
    with open(ruta, "rb") as f:
        crudo = f.read()
    for cod in [archivo.get("codificacion"), "utf-8-sig", "cp1252", "latin-1"]:
        if not cod:
            continue
        try:
            texto = crudo.decode(cod)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    sep = archivo.get("separador")
    if not sep:
        muestra = "\n".join(texto.splitlines()[:30])
        sep = max([";", ",", "\t", "|"], key=muestra.count)
    return [[c.strip() for c in fila] for fila in csv.reader(io.StringIO(texto), delimiter=sep)]


def _clave(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", t.lower())


def fila_encabezados(filas, encabezados):
    """Índice de la fila donde están todos los encabezados (las cartolas suelen traer títulos y saldos arriba)."""
    buscados = {_clave(e) for e in encabezados}
    for i, fila in enumerate(filas[:40]):
        if buscados <= {_clave(c) for c in fila}:
            return i
    return -1


def detectar(ruta, recetas=None):
    """La receta que calza con el archivo (la que reconoce más encabezados gana), o None."""
    recetas = disponibles() if recetas is None else recetas
    ext = ruta.lower().rsplit(".", 1)[-1]
    candidatas = []
    for r in recetas.values():
        exts = r.get("archivo", {}).get("extension")
        if exts and ext not in exts:
            continue
        try:
            filas = leer_tabla(ruta, r.get("archivo"))
        except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError):
            continue
        if fila_encabezados(filas, r["reconocer"]["encabezados"]) >= 0:
            candidatas.append((len(r["reconocer"]["encabezados"]), r))
    return max(candidatas, key=lambda x: x[0])[1] if candidatas else None


# ───────────── Números y fechas ─────────────
def numero(texto, decimal=",", miles="."):
    """«-$ 12.345,50» → -12345.5 · «(1,200.00)» → -1200.0 · «» → None."""
    t = str(texto or "").strip()
    if not t:
        return None
    negativo = t.startswith("-") or t.endswith("-") or (t.startswith("(") and t.endswith(")"))
    t = re.sub(r"[^\d,.' ]", "", t).strip()
    if miles:
        t = t.replace(miles, "")
    t = t.replace(" ", "").replace(decimal, ".")
    if not re.fullmatch(r"\d+(\.\d+)?", t):
        return None
    v = float(t)
    return -v if negativo else v


def fecha(texto, formatos):
    """Texto → «AAAA-MM-DD». Acepta varios formatos y el número de serie de Excel (días desde 1899-12-30)."""
    t = str(texto or "").strip()
    if re.fullmatch(r"\d{5}(\.\d+)?", t):
        return (date(1899, 12, 30) + timedelta(days=int(float(t)))).isoformat()
    for f in [formatos] if isinstance(formatos, str) else formatos:
        for candidato in (t, t[:len(datetime.now().strftime(f))]):
            try:
                return datetime.strptime(candidato, f).date().isoformat()
            except ValueError:
                pass
    return None


# ───────────── Aplicar ─────────────
def aplicar(ruta, receta, cuenta):
    """Lee la cartola con la receta. Devuelve (movimientos, avisos)."""
    filas = leer_tabla(ruta, receta.get("archivo"))
    i = fila_encabezados(filas, receta["reconocer"]["encabezados"])
    if i < 0:
        return [], ["Este archivo no tiene las columnas que espera la receta."]
    nombres = {_clave(c): n for n, c in enumerate(filas[i])}
    col = {k: nombres.get(_clave(v)) for k, v in receta["columnas"].items()}
    faltan = [receta["columnas"][k] for k, v in col.items() if v is None]
    if faltan:
        return [], ["Faltan columnas: " + ", ".join(faltan) + "."]
    num = receta.get("numeros", {})
    dec, mil = num.get("decimal", ","), num.get("miles", "." if num.get("decimal", ",") == "," else ",")
    signo = -1 if receta.get("signo") == "invertido" else 1
    ignorar = [datos.normalizar(x) for x in receta.get("ignorar_si_contiene", [])]
    movimientos, avisos, vistos = [], [], {}
    celda = lambda fila, k: fila[col[k]] if col.get(k) is not None and col[k] < len(fila) else ""
    for fila in filas[i + 1:]:
        if not any(c.strip() for c in fila):
            continue
        desc = " ".join(x for x in (celda(fila, "descripcion"), celda(fila, "detalle")) if x).strip()
        if any(x in datos.normalizar(desc) for x in ignorar):
            continue
        f = fecha(celda(fila, "fecha"), receta["fecha"])
        if "monto" in col:
            monto = numero(celda(fila, "monto"), dec, mil)
        else:
            cargo, abono = numero(celda(fila, "cargo"), dec, mil), numero(celda(fila, "abono"), dec, mil)
            monto = None if cargo is None and abono is None else (abono or 0) - abs(cargo or 0)
        if not f or monto is None or not desc:
            if any(c.strip() for c in fila[:3]) and len(avisos) < 5:
                avisos.append("Fila ignorada: " + " · ".join(c for c in fila if c)[:90])
            continue
        monto *= signo
        moneda = (celda(fila, "moneda") or receta["moneda"]).upper()[:3]
        llave = (f, datos.normalizar(desc), monto)
        vistos[llave] = vistos.get(llave, -1) + 1
        movimientos.append({"id": datos.nuevo_id(cuenta, f, desc, monto, vistos[llave]), "fecha": f, "descripcion": desc,
                            "monto": monto, "moneda": moneda, "categoria": "", "cuenta": cuenta, "origen": receta["id"], "nota": ""})
    return movimientos, avisos


def guardar(receta):
    """Guarda una receta nueva (creada con la IA o descargada) en la carpeta de la persona."""
    problemas = validar(receta)
    if problemas:
        raise ValueError(" ".join(problemas))
    datos.escribir_json(os.path.join(datos.INTERNO, "recetas", receta["id"] + ".json"), receta)


def muestra(ruta, filas=25):
    """Las primeras filas como texto, para que la IA proponga una receta."""
    return "\n".join(" | ".join(f) for f in leer_tabla(ruta)[:filas])


def leer_receta_texto(texto):
    """Saca el JSON de una respuesta de la IA (puede venir entre ``` o con texto alrededor)."""
    m = re.search(r"\{.*\}", texto or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None
