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
import pdf

FORMATO = 1
CLAVES = {"formato", "id", "nombre", "institucion", "pais", "moneda", "tipo", "archivo", "reconocer", "columnas", "fecha",
          "numeros", "signo", "ignorar_si_contiene", "autor", "notas"}
COLUMNAS = {"fecha", "descripcion", "monto", "cargo", "abono", "moneda", "detalle", "saldo"}

#: Límites para leer archivos que llegan de afuera (una cartola real pesa mucho menos): protegen contra archivos armados para
#: colgar la app o llenar la memoria, como un .xlsx que se descomprime a gigas («bomba zip») o un XML con entidades.
MAXIMO_ARCHIVO = 30 * 1024 * 1024
MAXIMO_XLSX_PARTE = 60 * 1024 * 1024   # cada XML de adentro, ya descomprimido
MAXIMO_XLSX_TOTAL = 200 * 1024 * 1024


class ArchivoNoValido(ValueError):
    """El archivo es demasiado grande o trae algo que una cartola nunca trae. El mensaje es para la persona."""


def _revisar_tamano(ruta):
    if os.path.getsize(ruta) > MAXIMO_ARCHIVO:
        raise ArchivoNoValido("El archivo es demasiado grande para ser una cartola (más de 30 MB).")


def _xml(texto):
    """XML de afuera, sin DTD ni entidades (las cartolas y los .xlsx nunca las traen): así no hay «billion laughs» ni XXE,
    aunque el lector de Python ya no resuelve entidades externas. En el texto de una celda, «<» siempre viene como «&lt;»."""
    if re.search(rb"<!(DOCTYPE|ENTITY)", texto, re.I):
        raise ArchivoNoValido("El archivo trae definiciones XML que una cartola no usa; no lo leo por seguridad.")
    return ElementTree.fromstring(texto)


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


# ───────────── Leer la tabla (CSV, Excel .xlsx o PDF con texto) ─────────────
def _celdas_xlsx(ruta, hoja=None):
    """Lee un .xlsx con zipfile + XML (sin librerías). Devuelve filas de textos; las fechas de Excel quedan como número."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    _revisar_tamano(ruta)
    with zipfile.ZipFile(ruta) as z:
        partes = z.infolist()
        if len(partes) > 5000 or sum(p.file_size for p in partes) > MAXIMO_XLSX_TOTAL \
                or any(p.file_size > MAXIMO_XLSX_PARTE for p in partes):
            raise ArchivoNoValido("El Excel es demasiado grande por dentro para ser una cartola; no lo leo por seguridad.")
        compartidos = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in _xml(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                compartidos.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        hojas = sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        elegida = f"xl/worksheets/sheet{hoja}.xml" if hoja else (hojas[0] if hojas else "")
        filas = []
        for fila in _xml(z.read(elegida)).iter(f"{{{ns['m']}}}row"):
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


def leer_tabla(ruta, archivo=None, encabezados=None):
    """Filas de textos. En un PDF, `encabezados` (los de la receta) ayuda a alinear las celdas con sus columnas."""
    archivo = archivo or {}
    if ruta.lower().endswith(".xlsx"):
        return _celdas_xlsx(ruta, archivo.get("hoja"))
    if ruta.lower().endswith(".pdf"):
        return pdf.tabla(ruta, encabezados)
    _revisar_tamano(ruta)
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
    estandar = receta_estandar(ruta)
    if estandar:
        return estandar
    recetas = disponibles() if recetas is None else recetas
    ext = ruta.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        pdf.trozos(ruta)  # si está cifrado o escaneado, el error claro sale aquí (y no un «no sé leerlo»)
    candidatas = []
    for r in recetas.values():
        exts = r.get("archivo", {}).get("extension")
        if exts and ext not in exts:
            continue
        try:
            filas = leer_tabla(ruta, r.get("archivo"), r["reconocer"]["encabezados"])
        except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError):
            continue
        if fila_encabezados(filas, r["reconocer"]["encabezados"]) >= 0:
            candidatas.append((len(r["reconocer"]["encabezados"]), r))
    return max(candidatas, key=lambda x: x[0])[1] if candidatas else None


# ───────────── OFX / QFX (formato estándar que exportan muchos bancos del mundo) ─────────────
#: Receta virtual: los archivos OFX traen todo lo necesario (fecha, monto con signo, id único), así que no necesitan receta propia.
RECETA_OFX = {"formato": 1, "id": "xx-ofx", "nombre": "Archivo OFX/QFX", "institucion": "Cuenta OFX", "pais": "XX", "moneda": "",
              "tipo": "cartola", "archivo": {"extension": ["ofx", "qfx"]}, "reconocer": {"encabezados": []}, "columnas": {}, "fecha": "%Y%m%d"}


def _ofx_texto(ruta):
    with open(ruta, "rb") as f:
        crudo = f.read(30_000_000)
    for cod in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return crudo.decode(cod)
        except UnicodeDecodeError:
            continue
    return ""


def _ofx_campo(bloque, nombre):
    """OFX 1 (SGML, sin etiquetas de cierre) y OFX 2 (XML): «<NAME>Café» o «<NAME>Café</NAME>»."""
    m = re.search(rf"<{nombre}>([^<\r\n]*)", bloque, re.I)
    return m.group(1).strip() if m else ""


def es_ofx(ruta):
    return ruta.lower().endswith((".ofx", ".qfx")) and "<STMTTRN>" in _ofx_texto(ruta).upper()


def receta_ofx(ruta):
    texto = _ofx_texto(ruta)
    org = _ofx_campo(texto, "ORG") or _ofx_campo(texto, "BANKID")
    r = dict(RECETA_OFX)
    if org and len(org) <= 60 and "<" not in org:
        r["institucion"] = org
        r["nombre"] = f"{org} (OFX)"
    r["moneda"] = (_ofx_campo(texto, "CURDEF") or "").upper()[:3]
    return r


def leer_ofx(ruta, cuenta):
    """Movimientos de un OFX: DTPOSTED (AAAAMMDD…), TRNAMT (negativo = gasto), FITID (id único del banco), NAME/MEMO."""
    texto = _ofx_texto(ruta)
    moneda = (_ofx_campo(texto, "CURDEF") or "").upper()[:3]
    movimientos, avisos = [], []
    for bloque in re.findall(r"<STMTTRN>(.*?)(?=</STMTTRN>|<STMTTRN>|</BANKTRANLIST>)", texto, re.S | re.I):
        f = _ofx_campo(bloque, "DTPOSTED")[:8]
        try:
            f = datetime.strptime(f, "%Y%m%d").date().isoformat()
        except ValueError:
            f = None
        monto = numero(_ofx_campo(bloque, "TRNAMT").replace(",", "."), ".", "")
        nombre, memo = _ofx_campo(bloque, "NAME"), _ofx_campo(bloque, "MEMO")
        desc = nombre if not memo or memo in nombre else f"{nombre} {memo}".strip()
        desc = desc or _ofx_campo(bloque, "TRNTYPE")
        fitid = _ofx_campo(bloque, "FITID")
        if not f or monto is None or not desc:
            if len(avisos) < 5:
                avisos.append("Movimiento OFX incompleto ignorado.")
            continue
        clave = fitid or f"{desc}|{monto}|{len(movimientos)}"
        movimientos.append({"id": datos.nuevo_id(cuenta, f, "OFX:" + clave, monto), "fecha": f, "descripcion": desc[:200], "monto": monto,
                            "moneda": (_ofx_campo(bloque, "CURRENCY") or moneda or "").upper()[:3], "categoria": "", "cuenta": cuenta,
                            "origen": "xx-ofx", "nota": ""})
    return movimientos, avisos


# ───────────── CAMT.053 (estándar ISO 20022 de Europa) y QIF (formato antiguo de Quicken) ─────────────
RECETA_CAMT = {**RECETA_OFX, "id": "xx-camt053", "nombre": "Cartola CAMT.053", "institucion": "Cuenta CAMT.053", "archivo": {"extension": ["xml"]}}
RECETA_QIF = {**RECETA_OFX, "id": "xx-qif", "nombre": "Archivo QIF", "institucion": "Cuenta QIF", "archivo": {"extension": ["qif"]}}


def _sin_ns(raiz):
    for e in raiz.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]
    return raiz


def es_camt(ruta):
    if not ruta.lower().endswith(".xml"):
        return False
    with open(ruta, "rb") as f:
        inicio = f.read(4000)
    return b"BkToCstmrStmt" in inicio or b"camt.053" in inicio


def leer_camt(ruta, cuenta):
    """Ntry: Amt (siempre positivo) + CdtDbtInd (CRDT/DBIT), BookgDt, Sts BOOK; texto en RmtInf/Ustrd o la contraparte."""
    _revisar_tamano(ruta)
    with open(ruta, "rb") as f:
        raiz = _sin_ns(_xml(f.read()))
    movimientos, avisos, vistos = [], [], {}
    for st in raiz.iter("Stmt"):
        moneda_cta = (st.findtext("Acct/Ccy") or "").upper()[:3]
        for n in st.iter("Ntry"):
            sts = (n.findtext("Sts/Cd") or n.findtext("Sts") or "BOOK").strip()
            if sts != "BOOK":
                continue
            amt = n.find("Amt")
            monto = numero(amt.text if amt is not None else "", ".", "")
            f = (n.findtext("BookgDt/Dt") or n.findtext("BookgDt/DtTm") or n.findtext("ValDt/Dt") or "")[:10]
            if monto is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", f):
                if len(avisos) < 5:
                    avisos.append("Movimiento CAMT incompleto ignorado.")
                continue
            if (n.findtext("CdtDbtInd") or "").strip() == "DBIT":
                monto = -abs(monto)
            credito = monto > 0
            contraparte = (n.findtext(".//RltdPties/Dbtr/Nm") or n.findtext(".//RltdPties/Dbtr/Pty/Nm")) if credito else \
                (n.findtext(".//RltdPties/Cdtr/Nm") or n.findtext(".//RltdPties/Cdtr/Pty/Nm"))
            texto = " ".join(x.text.strip() for x in n.iter("Ustrd") if x.text)
            desc = " ".join(x for x in (contraparte, texto) if x).strip() or (n.findtext("AddtlNtryInf") or "").strip() or "Movimiento"
            desc = re.sub(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b", "", desc).strip() or "Movimiento"  # sin IBAN de nadie
            ref = n.findtext("AcctSvcrRef") or n.findtext("NtryRef") or n.findtext(".//Refs/AcctSvcrRef") or ""
            llave = (f, desc, monto)
            vistos[llave] = vistos.get(llave, -1) + 1
            clave = f"CAMT:{ref}" if ref else f"{desc}#{vistos[llave]}"
            movimientos.append({"id": datos.nuevo_id(cuenta, f, clave, monto), "fecha": f, "descripcion": " ".join(desc.split())[:200],
                                "monto": monto, "moneda": ((amt.get("Ccy") if amt is not None else "") or moneda_cta).upper()[:3],
                                "categoria": "", "cuenta": cuenta, "origen": RECETA_CAMT["id"], "nota": ""})
    return movimientos, avisos


def es_qif(ruta):
    if not ruta.lower().endswith(".qif"):
        return False
    with open(ruta, "rb") as f:
        return f.read(200).lstrip().startswith(b"!")


def _fechas_qif(textos):
    """QIF no dice si la fecha es día/mes o mes/día: se mira si algún número pasa de 12; si no, se usa la costumbre del país."""
    partes = [re.split(r"[/\-.' ]+", t.strip()) for t in textos if t.strip()]
    if any(len(p) >= 2 and p[0].isdigit() and int(p[0]) > 12 for p in partes):
        orden = "dm"
    elif any(len(p) >= 2 and p[1].isdigit() and int(p[1]) > 12 for p in partes):
        orden = "md"
    else:
        orden = "md" if datos.config().get("pais") in ("US", "CA") else "dm"

    def una(t):
        p = [x for x in re.split(r"[/\-.' ]+", t.strip()) if x]
        if len(p) != 3 or not all(x.isdigit() for x in p):
            return None
        a, b, c = (int(x) for x in p)
        if a > 31:  # AAAA-MM-DD
            anio, mes, dia = a, b, c
        else:
            dia, mes = (a, b) if orden == "dm" else (b, a)
            anio = c + (2000 if c < 70 else 1900) if c < 100 else c
        try:
            return date(anio, mes, dia).isoformat()
        except ValueError:
            return None
    return una


def leer_qif(ruta, cuenta):
    texto = None
    with open(ruta, "rb") as f:
        crudo = f.read(30_000_000)
    for cod in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = crudo.decode(cod)
            break
        except UnicodeDecodeError:
            continue
    registros, actual = [], {}
    for linea in (texto or "").splitlines():
        if not linea or linea.startswith("!"):
            continue
        if linea.startswith("^"):
            if actual:
                registros.append(actual)
            actual = {}
            continue
        actual.setdefault(linea[0], linea[1:].strip())
    if actual:
        registros.append(actual)
    fecha_de = _fechas_qif([r.get("D", "") for r in registros])
    movimientos, avisos, vistos = [], [], {}
    for r in registros:
        f = fecha_de(r.get("D", ""))
        monto = numero((r.get("T") or r.get("U") or "").replace(",", ""), ".", "")
        desc = " ".join(x for x in (r.get("P"), r.get("M")) if x).strip()
        if not f or monto is None or not desc:
            if len(avisos) < 5:
                avisos.append("Movimiento QIF incompleto ignorado.")
            continue
        llave = (f, datos.normalizar(desc), monto)
        vistos[llave] = vistos.get(llave, -1) + 1
        movimientos.append({"id": datos.nuevo_id(cuenta, f, desc, monto, vistos[llave]), "fecha": f, "descripcion": desc[:200], "monto": monto,
                            "moneda": "", "categoria": "", "cuenta": cuenta, "origen": RECETA_QIF["id"], "nota": ""})
    return movimientos, avisos


VIRTUALES = {RECETA_OFX["id"]: (lambda r: receta_ofx(r), leer_ofx), RECETA_CAMT["id"]: (lambda r: dict(RECETA_CAMT), leer_camt),
             RECETA_QIF["id"]: (lambda r: dict(RECETA_QIF), leer_qif)}


def receta_estandar(ruta):
    """Archivos de formato estándar (OFX, CAMT.053, QIF): se leen sin receta."""
    try:
        if es_ofx(ruta):
            return receta_ofx(ruta)
        if es_camt(ruta):
            return dict(RECETA_CAMT)
        if es_qif(ruta):
            return dict(RECETA_QIF)
    except OSError:
        return None
    return None


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
def aplicar(ruta, receta, cuenta, info=None):
    """Lee la cartola con la receta. Devuelve (movimientos, avisos). Si la receta tiene la columna `saldo` y se pasa `info` (un
    dict), deja en info["saldo"] = {"monto", "fecha"} el saldo de la fila más reciente (la última de ese día en el orden del archivo:
    hacia abajo si la cartola va de lo antiguo a lo nuevo, hacia arriba si va al revés)."""
    if receta.get("id") in VIRTUALES:
        return VIRTUALES[receta["id"]][1](ruta, cuenta)
    filas = leer_tabla(ruta, receta.get("archivo"), receta["reconocer"]["encabezados"])
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
    movimientos, avisos, vistos, saldos = [], [], {}, []
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
        if "saldo" in col:
            s = numero(celda(fila, "saldo"), dec, mil)
            if s is not None:
                saldos.append((f, s))
    if info is not None and saldos:
        ascendente = saldos[0][0] <= saldos[-1][0]
        ultimo = max(f for f, _ in saldos)
        del_dia = [s for f, s in saldos if f == ultimo]
        info["saldo"] = {"monto": del_dia[-1] if ascendente else del_dia[0], "fecha": ultimo}
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
