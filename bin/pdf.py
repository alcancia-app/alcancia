"""Leer cartolas en PDF sin librerías (solo biblioteca estándar). Saca el texto con su posición y lo arma como una tabla.

Muchos bancos generan la cartola en PDF con texto (no imagen). Este módulo:
1. Recorre el archivo buscando sus objetos («n g obj … endobj»), sin confiar en la tabla xref (así lee también PDFs con la
   xref rota o con incrementos), y abre los flujos de objetos (/ObjStm) de los PDF modernos.
2. Descomprime los flujos: FlateDecode (zlib, con predictores PNG), ASCIIHex, ASCII85 o sin filtro.
3. Interpreta el contenido de cada página: q/Q/cm, BT/ET, Tf, Td, TD, Tm, T*, TL, Tc, Tw, Tz, Ts, Tj, TJ, ' y ", y los
   formularios (Do). Cada trozo de texto queda con su posición x/y y su ancho.
4. Decodifica el texto: fuentes simples con WinAnsi/MacRoman/Standard (+ /Differences) y, si la fuente trae /ToUnicode,
   su CMap (bfchar y bfrange), que es lo que usan las fuentes Type0/Identity-H.
5. Agrupa los trozos en filas (misma coordenada y) y en celdas (por la distancia en x). Si encuentra la fila de encabezados,
   alinea las celdas de las filas siguientes con sus columnas (así un abono no cae en la columna de cargos).

El resultado es una lista de filas de textos, igual que un CSV, para que la receta del banco funcione igual (recetas.leer_tabla).
No ejecuta nada del PDF (ni JavaScript ni formularios). Si el PDF está cifrado o es una imagen escaneada, lo dice con un error claro.
"""
import math
import os
import re
import unicodedata
import zlib

MAXIMO_ARCHIVO = 30 * 1024 * 1024
MAXIMO_FLUJO = 40 * 1024 * 1024   # descomprimido: protege contra «bombas» de compresión
MAXIMO_PAGINAS = 300


class PdfError(ValueError):
    """Error que se le puede mostrar tal cual a la persona."""


# ───────────── Objetos del PDF ─────────────
class Nombre(str):
    pass


class Op(str):
    pass


class Ref(tuple):
    @property
    def num(self):
        return self[0]


ESPACIOS = b"\x00\t\n\x0c\r "
DELIM = b"()<>[]{}/%"
_FIN_TOKEN = re.compile(rb"[\x00\t\n\x0c\r ()<>\[\]{}/%]")


class Lector:
    """Tokenizador de la sintaxis de PDF sobre bytes."""

    def __init__(self, datos, pos=0):
        self.d = datos
        self.p = pos

    def saltar(self):
        d, n = self.d, len(self.d)
        while self.p < n:
            c = d[self.p]
            if c in ESPACIOS:
                self.p += 1
            elif c == 0x25:  # % comentario
                fin = d.find(b"\n", self.p)
                fin2 = d.find(b"\r", self.p)
                fin = min(x for x in (fin, fin2, n) if x >= 0)
                self.p = fin
            else:
                break

    def palabra(self):
        m = _FIN_TOKEN.search(self.d, self.p)
        fin = m.start() if m else len(self.d)
        if fin == self.p:
            fin += 1
        t = self.d[self.p:fin]
        self.p = fin
        return t

    def cadena(self):
        d, p, n = self.d, self.p + 1, len(self.d)
        salida, nivel = bytearray(), 1
        while p < n:
            c = d[p]
            if c == 0x5C and p + 1 < n:  # \
                p += 1
                e = d[p]
                if e in b"nrtbf":
                    salida.append({0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}[e])
                elif e in b"01234567":
                    o = d[p:p + 3]
                    k = 1
                    while k < len(o) and o[k] in b"01234567":
                        k += 1
                    salida.append(int(o[:k], 8) & 0xFF)
                    p += k - 1
                elif e == 0x0D:
                    if p + 1 < n and d[p + 1] == 0x0A:
                        p += 1
                elif e == 0x0A:
                    pass
                else:
                    salida.append(e)
            elif c == 0x28:
                nivel += 1
                salida.append(c)
            elif c == 0x29:
                nivel -= 1
                if nivel == 0:
                    p += 1
                    break
                salida.append(c)
            else:
                salida.append(c)
            p += 1
        self.p = p
        return bytes(salida)

    def hexa(self):
        fin = self.d.find(b">", self.p)
        fin = len(self.d) if fin < 0 else fin
        t = re.sub(rb"[^0-9A-Fa-f]", b"", self.d[self.p + 1:fin])
        self.p = fin + 1
        if len(t) % 2:
            t += b"0"
        return bytes.fromhex(t.decode())

    def nombre(self):
        self.p += 1
        crudo = self.palabra() if self.p < len(self.d) and not _FIN_TOKEN.match(self.d, self.p) else b""
        crudo = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), crudo)
        return Nombre(crudo.decode("latin-1"))

    def token(self):
        """Un token: número, nombre, cadena, hexa, '[', ']', '<<', '>>', palabra clave (Op). None al final."""
        self.saltar()
        if self.p >= len(self.d):
            return None
        c = self.d[self.p]
        if c == 0x28:
            return self.cadena()
        if c == 0x3C:
            if self.d[self.p + 1:self.p + 2] == b"<":
                self.p += 2
                return "<<"
            return self.hexa()
        if c == 0x3E:
            if self.d[self.p + 1:self.p + 2] == b">":
                self.p += 2
                return ">>"
            self.p += 1
            return Op(">")
        if c in b"[]{}":
            self.p += 1
            return chr(c)
        if c == 0x2F:
            return self.nombre()
        t = self.palabra()
        if re.fullmatch(rb"[+-]?\d+", t):
            return int(t)
        if re.fullmatch(rb"[+-]?(\d+\.\d*|\.\d+|\d+\.)", t):
            return float(t)
        return Op(t.decode("latin-1"))

    def objeto(self, tok=None, profundidad=0):
        """Un objeto completo (arreglos y diccionarios anidados, referencias «n g R»)."""
        if tok is None:
            tok = self.token()
        if profundidad > 60:
            raise PdfError("El PDF tiene una estructura que no sé leer.")
        if tok == "[":
            lista = []
            while True:
                t = self.token()
                if t is None or t == "]":
                    return lista
                lista.append(self.objeto(t, profundidad + 1))
        if tok == "<<":
            dic = {}
            while True:
                t = self.token()
                if t is None or t == ">>":
                    return dic
                if isinstance(t, Nombre):
                    dic[t] = self.objeto(None, profundidad + 1)
        if isinstance(tok, int) and not isinstance(tok, bool):
            guardado = self.p
            t2 = self.token()
            if isinstance(t2, int):
                t3 = self.token()
                if t3 == "R":
                    return Ref((tok, t2))
            self.p = guardado
            return tok
        if tok == "true":
            return True
        if tok == "false":
            return False
        if tok == "null":
            return None
        return tok


# ───────────── Flujos ─────────────
def _inflar(datos):
    d = zlib.decompressobj()
    try:
        salida = d.decompress(datos, MAXIMO_FLUJO)
    except zlib.error:
        # Algunos PDFs traen el flujo sin la cabecera zlib (deflate «crudo») o cortado al final.
        try:
            d = zlib.decompressobj(-15)
            salida = d.decompress(datos[2:], MAXIMO_FLUJO)
        except zlib.error:
            return b""
    if d.unconsumed_tail:
        raise PdfError("El PDF trae una parte demasiado grande para ser una cartola.")
    return salida


def _predictor(datos, parametros):
    pred = parametros.get("Predictor", 1) if isinstance(parametros, dict) else 1
    if pred < 10:
        return datos
    columnas = parametros.get("Columns", 1) * parametros.get("Colors", 1) * parametros.get("BitsPerComponent", 8) // 8
    bpp = max(1, parametros.get("Colors", 1) * parametros.get("BitsPerComponent", 8) // 8)
    salida, anterior = bytearray(), bytearray(columnas)
    for i in range(0, len(datos), columnas + 1):
        tipo, fila = datos[i], bytearray(datos[i + 1:i + 1 + columnas])
        for j in range(len(fila)):
            izq = fila[j - bpp] if j >= bpp else 0
            arriba = anterior[j] if j < len(anterior) else 0
            diag = anterior[j - bpp] if j >= bpp and j - bpp < len(anterior) else 0
            if tipo == 1:
                fila[j] = (fila[j] + izq) & 0xFF
            elif tipo == 2:
                fila[j] = (fila[j] + arriba) & 0xFF
            elif tipo == 3:
                fila[j] = (fila[j] + (izq + arriba) // 2) & 0xFF
            elif tipo == 4:
                p = izq + arriba - diag
                pa, pb, pc = abs(p - izq), abs(p - arriba), abs(p - diag)
                fila[j] = (fila[j] + (izq if pa <= pb and pa <= pc else arriba if pb <= pc else diag)) & 0xFF
        salida += fila
        anterior = fila
    return bytes(salida)


def _a85(datos):
    datos = re.sub(rb"\s", b"", datos)
    if datos.startswith(b"<~"):
        datos = datos[2:]
    fin = datos.find(b"~>")
    datos = datos[:fin] if fin >= 0 else datos
    salida, grupo = bytearray(), []
    for c in datos:
        if c == 0x7A and not grupo:
            salida += b"\0\0\0\0"
            continue
        grupo.append(c - 33)
        if len(grupo) == 5:
            v = 0
            for x in grupo:
                v = v * 85 + x
            salida += (v & 0xFFFFFFFF).to_bytes(4, "big")
            grupo = []
    if grupo:
        n = len(grupo)
        grupo += [84] * (5 - n)
        v = 0
        for x in grupo:
            v = v * 85 + x
        salida += (v & 0xFFFFFFFF).to_bytes(4, "big")[:n - 1]
    return bytes(salida)


# ───────────── Documento ─────────────
class Documento:
    def __init__(self, datos):
        if not datos.lstrip()[:5].startswith(b"%PDF"):
            raise PdfError("Este archivo no parece un PDF.")
        self.d = datos
        self.objetos = {}     # num → (inicio, fin del diccionario, inicio y fin del flujo o None)
        self.cache = {}
        self.trailers = []
        self._escanear()
        if any("Encrypt" in t for t in self.trailers):
            raise PdfError("Este PDF está protegido con clave. Ábrelo, guárdalo sin clave (Imprimir → Guardar como PDF) y vuelve a "
                           "agregarlo, o descarga la cartola en CSV o Excel.")

    def _escanear(self):
        d = self.d
        patron = re.compile(rb"(?<![0-9])(\d{1,10})\s+(\d{1,5})\s+obj\b")
        pos = 0
        while True:
            m = patron.search(d, pos)
            if not m:
                break
            num = int(m.group(1))
            lector = Lector(d, m.end())
            try:
                valor = lector.objeto()
            except (PdfError, IndexError, ValueError):
                pos = m.end()
                continue
            flujo = None
            guardado = lector.p
            if isinstance(valor, dict) and lector.token() == "stream":
                inicio = lector.p
                if d[inicio:inicio + 2] == b"\r\n":
                    inicio += 2
                elif d[inicio:inicio + 1] in (b"\n", b"\r"):
                    inicio += 1
                largo = valor.get("Length")
                fin = None
                if isinstance(largo, int) and 0 <= largo and d[inicio + largo:inicio + largo + 30].lstrip().startswith(b"endstream"):
                    fin = inicio + largo
                if fin is None:  # Length indirecto o mentiroso: se busca «endstream»
                    k = d.find(b"endstream", inicio)
                    fin = len(d) if k < 0 else k
                    while fin > inicio and d[fin - 1] in b"\r\n":
                        fin -= 1
                flujo = (inicio, fin)
                pos = fin
            else:
                lector.p = guardado
                pos = lector.p
            self.objetos[num] = (valor, flujo)  # el último gana: así funcionan las actualizaciones incrementales
            self.cache.pop(num, None)
            if isinstance(valor, dict) and valor.get("Type") == "XRef":
                self.trailers.append(valor)
        for m in re.finditer(rb"trailer\s*<<", d):
            try:
                t = Lector(d, m.end() - 2).objeto()
            except (PdfError, IndexError, ValueError):
                continue
            if isinstance(t, dict):
                self.trailers.append(t)
        self._flujos_de_objetos()

    def _flujos_de_objetos(self):
        """PDF 1.5+: muchos objetos (fuentes, páginas) vienen comprimidos dentro de un /ObjStm."""
        for num, (valor, flujo) in list(self.objetos.items()):
            if not (isinstance(valor, dict) and valor.get("Type") == "ObjStm" and flujo):
                continue
            try:
                datos = self.flujo(valor, flujo)
                n, primero = int(self.res(valor.get("N", 0))), int(self.res(valor.get("First", 0)))
                lector = Lector(datos)
                pares = [(lector.token(), lector.token()) for _ in range(n)]
                for onum, desp in pares:
                    if isinstance(onum, int) and isinstance(desp, int) and onum not in self.objetos:
                        self.objetos[onum] = (Lector(datos, primero + desp).objeto(), None)
            except (PdfError, IndexError, ValueError, TypeError):
                continue

    def res(self, v, profundidad=0):
        """Resuelve referencias «n g R»."""
        while isinstance(v, Ref) and profundidad < 30:
            v = self.objetos.get(v.num, (None, None))[0]
            profundidad += 1
        return v

    def flujo_de(self, ref):
        """Los bytes (ya decodificados) del flujo al que apunta `ref`."""
        if isinstance(ref, Ref):
            if ref.num in self.cache:
                return self.cache[ref.num]
            valor, flujo = self.objetos.get(ref.num, (None, None))
            datos = self.flujo(valor, flujo) if isinstance(valor, dict) and flujo else b""
            self.cache[ref.num] = datos
            return datos
        return b""

    def flujo(self, dic, flujo):
        datos = self.d[flujo[0]:flujo[1]]
        filtros = self.res(dic.get("Filter"))
        filtros = filtros if isinstance(filtros, list) else [filtros] if filtros else []
        parametros = self.res(dic.get("DecodeParms"))
        parametros = parametros if isinstance(parametros, list) else [parametros] * len(filtros)
        for i, f in enumerate(filtros):
            f = self.res(f)
            par = self.res(parametros[i]) if i < len(parametros) else None
            if f in ("FlateDecode", "Fl"):
                datos = _predictor(_inflar(datos), par or {})
            elif f in ("ASCIIHexDecode", "AHx"):
                datos = Lector(b"<" + datos.split(b">")[0] + b">").hexa()
            elif f in ("ASCII85Decode", "A85"):
                datos = _a85(datos)
            else:
                return b""  # imágenes (DCT, JBIG2…) u otros filtros: no traen texto
        return datos

    def raiz(self):
        for t in reversed(self.trailers):
            r = self.res(t.get("Root"))
            if isinstance(r, dict):
                return r
        for valor, _ in self.objetos.values():
            if isinstance(valor, dict) and valor.get("Type") == "Catalog":
                return valor
        return {}

    def paginas(self):
        """Las páginas en orden, con sus recursos heredados."""
        salida, vistos = [], set()

        def recorrer(nodo, heredado, profundidad):
            if profundidad > 40 or len(salida) >= MAXIMO_PAGINAS:
                return
            dic = self.res(nodo)
            if not isinstance(dic, dict) or id(dic) in vistos:
                return
            vistos.add(id(dic))
            h = dict(heredado)
            for k in ("Resources", "Rotate", "MediaBox"):
                if k in dic:
                    h[k] = self.res(dic[k])
            if dic.get("Type") == "Pages" or "Kids" in dic:
                for hijo in self.res(dic.get("Kids")) or []:
                    recorrer(hijo, h, profundidad + 1)
            else:
                salida.append((dic, h))

        recorrer(self.raiz().get("Pages"), {}, 0)
        if not salida:  # sin árbol de páginas legible: toda /Type /Page que exista
            salida = [(v, {"Resources": self.res(v.get("Resources")), "Rotate": self.res(v.get("Rotate", 0))})
                      for v, _ in self.objetos.values() if isinstance(v, dict) and v.get("Type") == "Page"][:MAXIMO_PAGINAS]
        return salida


# ───────────── Fuentes y texto ─────────────
#: Anchos de Helvetica (cada 1000 del cuerpo) para los caracteres 32–126. Las fuentes estándar no traen /Widths.
_HELVETICA = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556,
              556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833,
              722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556,
              556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334,
              260, 334, 584]


def ancho_helvetica(texto):
    """Ancho aproximado de un texto en Helvetica, en milésimas del cuerpo (también lo usa el generador de PDFs de prueba)."""
    return sum(_HELVETICA[ord(c) - 32] if 32 <= ord(c) <= 126 else 556 for c in texto)


_ACENTOS = {"ACUTE": "acute", "GRAVE": "grave", "CIRCUMFLEX": "circumflex", "TILDE": "tilde", "DIAERESIS": "dieresis",
            "CEDILLA": "cedilla", "RING ABOVE": "ring"}
_GLIFOS = {"space": " ", "exclam": "!", "quotedbl": '"', "numbersign": "#", "dollar": "$", "percent": "%", "ampersand": "&",
           "quotesingle": "'", "quoteright": "’", "quoteleft": "‘", "parenleft": "(", "parenright": ")", "asterisk": "*", "plus": "+",
           "comma": ",", "hyphen": "-", "minus": "-", "period": ".", "slash": "/", "colon": ":", "semicolon": ";", "less": "<",
           "equal": "=", "greater": ">", "question": "?", "at": "@", "bracketleft": "[", "backslash": "\\", "bracketright": "]",
           "underscore": "_", "braceleft": "{", "bar": "|", "braceright": "}", "degree": "°", "ordfeminine": "ª",
           "ordmasculine": "º", "exclamdown": "¡", "questiondown": "¿", "euro": "€", "endash": "–", "emdash": "—",
           "quotedblleft": "“", "quotedblright": "”", "guillemotleft": "«", "guillemotright": "»", "bullet": "•", "nbspace": " ",
           "germandbls": "ß", "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
           "seven": "7", "eight": "8", "nine": "9"}


def glifo(nombre):
    """Nombre de glifo (de /Differences) → carácter: «aacute» → «á», «uni00F1» → «ñ»."""
    if nombre in _GLIFOS:
        return _GLIFOS[nombre]
    if len(nombre) == 1:
        return nombre
    m = re.fullmatch(r"uni([0-9A-Fa-f]{4})+|u([0-9A-Fa-f]{4,6})", nombre)
    if m:
        h = nombre[3:] if nombre.startswith("uni") else nombre[1:]
        paso = 4 if nombre.startswith("uni") else len(h)
        try:
            return "".join(chr(int(h[i:i + paso], 16)) for i in range(0, len(h), paso))
        except ValueError:
            return ""
    for marca, sufijo in _ACENTOS.items():
        if nombre.endswith(sufijo) and len(nombre) == len(sufijo) + 1:
            letra = nombre[0]
            caso = "SMALL" if letra.islower() else "CAPITAL"
            try:
                return unicodedata.lookup(f"LATIN {caso} LETTER {letra.upper()} WITH {marca}")
            except KeyError:
                return ""
    if nombre in ("ntilde", "Ntilde"):
        return "ñ" if nombre[0] == "n" else "Ñ"
    return ""


def leer_cmap(datos):
    """CMap /ToUnicode: códigos (bytes) → texto. Entiende codespacerange, bfchar y bfrange (con destino o con lista)."""
    mapa, largos = {}, set()
    texto = datos.decode("latin-1")
    hexa = lambda h: bytes.fromhex(re.sub(r"\s", "", h) + ("0" if len(re.sub(r"\s", "", h)) % 2 else ""))
    utf16 = lambda b: b.decode("utf-16-be", "ignore") if len(b) % 2 == 0 else b.decode("latin-1")
    for bloque in re.findall(r"begincodespacerange(.*?)endcodespacerange", texto, re.S):
        for lo in re.findall(r"<([0-9A-Fa-f\s]+)>\s*<[0-9A-Fa-f\s]+>", bloque):
            largos.add(len(hexa(lo)))
    for bloque in re.findall(r"beginbfchar(.*?)endbfchar", texto, re.S):
        for origen, destino in re.findall(r"<([0-9A-Fa-f\s]+)>\s*<([0-9A-Fa-f\s]*)>", bloque):
            mapa[hexa(origen)] = utf16(hexa(destino))
    for bloque in re.findall(r"beginbfrange(.*?)endbfrange", texto, re.S):
        for lo, hi, destino in re.findall(r"<([0-9A-Fa-f\s]+)>\s*<([0-9A-Fa-f\s]+)>\s*(<[0-9A-Fa-f\s]*>|\[[^\]]*\])", bloque):
            blo, bhi = hexa(lo), hexa(hi)
            a, b = int.from_bytes(blo, "big"), int.from_bytes(bhi, "big")
            if b < a or b - a > 65535:
                continue
            if destino.startswith("["):
                lista = [utf16(hexa(x)) for x in re.findall(r"<([0-9A-Fa-f\s]*)>", destino)]
                for i, t in enumerate(lista[:b - a + 1]):
                    mapa[(a + i).to_bytes(len(blo), "big")] = t
            else:
                base = hexa(destino[1:-1])
                for i in range(b - a + 1):
                    v = (int.from_bytes(base, "big") + i).to_bytes(max(2, len(base)), "big")
                    mapa[(a + i).to_bytes(len(blo), "big")] = utf16(v)
    if not largos:
        largos = {len(k) for k in mapa} or {1}
    return mapa, sorted(largos)


class Fuente:
    def __init__(self, doc, dic):
        dic = doc.res(dic) if dic is not None else {}
        dic = dic if isinstance(dic, dict) else {}
        self.compuesta = dic.get("Subtype") == "Type0"
        self.base = str(doc.res(dic.get("BaseFont")) or "")
        self.anchos, self.ancho_defecto = {}, None
        self.cmap, self.largos = {}, [2] if self.compuesta else [1]
        tu = dic.get("ToUnicode")
        if isinstance(tu, Ref):
            try:
                self.cmap, self.largos = leer_cmap(doc.flujo_de(tu))
            except (ValueError, PdfError):
                self.cmap = {}
        if self.compuesta:
            self.largos = [2] if not self.cmap else self.largos
            desc = doc.res(dic.get("DescendantFonts"))
            desc = doc.res(desc[0]) if isinstance(desc, list) and desc else {}
            desc = desc if isinstance(desc, dict) else {}
            self.ancho_defecto = doc.res(desc.get("DW", 1000))
            w = doc.res(desc.get("W")) or []
            i = 0
            while i < len(w):
                a = doc.res(w[i])
                b = doc.res(w[i + 1]) if i + 1 < len(w) else None
                if isinstance(b, list):
                    for k, x in enumerate(b):
                        self.anchos[a + k] = doc.res(x)
                    i += 2
                elif i + 2 < len(w):
                    for k in range(a, min(doc.res(w[i + 1]), a + 65535) + 1):
                        self.anchos[k] = doc.res(w[i + 2])
                    i += 3
                else:
                    break
            self.tabla = None
        else:
            primero = doc.res(dic.get("FirstChar", 0)) or 0
            for k, x in enumerate(doc.res(dic.get("Widths")) or []):
                self.anchos[primero + k] = doc.res(x)
            fd = doc.res(dic.get("FontDescriptor"))
            if isinstance(fd, dict) and isinstance(doc.res(fd.get("MissingWidth")), (int, float)):
                self.ancho_defecto = doc.res(fd["MissingWidth"])
            enc = doc.res(dic.get("Encoding"))
            base, dif = "WinAnsiEncoding", []
            if isinstance(enc, str):
                base = enc
            elif isinstance(enc, dict):
                base = doc.res(enc.get("BaseEncoding")) or "WinAnsiEncoding"
                dif = doc.res(enc.get("Differences")) or []
            codec = "mac_roman" if base == "MacRomanEncoding" else "cp1252"
            self.tabla = {}
            for c in range(256):
                try:
                    self.tabla[c] = bytes([c]).decode(codec)
                except UnicodeDecodeError:
                    self.tabla[c] = bytes([c]).decode("latin-1")
            codigo = 0
            for x in dif:
                x = doc.res(x)
                if isinstance(x, int):
                    codigo = x
                elif isinstance(x, str):
                    t = glifo(str(x))
                    if t and 0 <= codigo < 256:
                        self.tabla[codigo] = t
                    codigo += 1
        self.monoespaciada = "Courier" in self.base

    def codigos(self, b):
        """Parte los bytes de una cadena en códigos (1 byte en fuentes simples; 2 o lo que diga el CMap en las compuestas)."""
        if not self.compuesta and self.largos == [1]:
            return [b[i:i + 1] for i in range(len(b))]
        salida, i = [], 0
        while i < len(b):
            for n in self.largos:
                if b[i:i + n] in self.cmap or n == self.largos[-1]:
                    salida.append(b[i:i + n])
                    i += n
                    break
        return salida

    def texto(self, codigo):
        if codigo in self.cmap:
            return self.cmap[codigo]
        if self.compuesta:
            # Sin /ToUnicode no hay forma segura de saber el carácter: algunos generadores usan el propio código Unicode.
            v = int.from_bytes(codigo, "big")
            return chr(v) if 32 <= v < 0xD800 else ""
        return self.tabla.get(codigo[0], "")

    def ancho(self, codigo):
        """Ancho del glifo en milésimas del cuerpo."""
        c = int.from_bytes(codigo, "big")
        if c in self.anchos:
            return self.anchos[c] or 0
        if self.ancho_defecto is not None:
            return self.ancho_defecto
        if self.monoespaciada:
            return 600
        t = self.texto(codigo)
        return ancho_helvetica(t) if t else 556


def _mult(a, b):
    """Producto de matrices de PDF [a b c d e f] (a × b)."""
    return (a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5])


IDENTIDAD = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _rotar(x, y, rot):
    rot %= 360
    return (y, -x) if rot == 90 else (-x, -y) if rot == 180 else (-y, x) if rot == 270 else (x, y)


def trozos_de_pagina(doc, pagina, heredado):
    """Los trozos de texto de una página: (x, y, x_fin, tamaño, texto)."""
    salida = []
    rot = heredado.get("Rotate", 0) if isinstance(heredado.get("Rotate", 0), int) else 0
    fuentes_cache = {}

    def fuentes_de(recursos):
        recursos = doc.res(recursos) if recursos is not None else {}
        f = doc.res(recursos.get("Font")) if isinstance(recursos, dict) else None
        return f if isinstance(f, dict) else {}

    def fuente(dic_fuentes, nombre):
        ref = dic_fuentes.get(nombre)
        clave = ref if isinstance(ref, Ref) else (id(dic_fuentes), nombre)
        if clave not in fuentes_cache:
            fuentes_cache[clave] = Fuente(doc, ref)
        return fuentes_cache[clave]

    def ejecutar(contenido, recursos, ctm, profundidad):
        if profundidad > 6:
            return
        dic_fuentes = fuentes_de(recursos)
        xobjetos = doc.res(recursos.get("XObject")) if isinstance(recursos, dict) else None
        xobjetos = xobjetos if isinstance(xobjetos, dict) else {}
        pila = []
        g = {"ctm": ctm}
        t = {"tc": 0.0, "tw": 0.0, "th": 1.0, "tl": 0.0, "ts": 0.0, "tf": None, "fs": 0.0}
        tm = tlm = IDENTIDAD
        lector = Lector(contenido)
        operandos = []

        def mostrar(cadena):
            nonlocal tm
            f = t["tf"] or Fuente(doc, None)
            trm = _mult((t["fs"] * t["th"], 0, 0, t["fs"], 0, t["ts"]), _mult(tm, g["ctm"]))
            x0, y0 = trm[4], trm[5]
            texto, avance = [], 0.0
            for cod in f.codigos(cadena):
                ch = f.texto(cod)
                w = f.ancho(cod) / 1000.0
                tx = (w * t["fs"] + t["tc"] + (t["tw"] if cod == b" " else 0.0)) * t["th"]
                avance += tx
                texto.append(ch)
            tm = _mult((1, 0, 0, 1, avance, 0), tm)
            fin = _mult((1, 0, 0, 1, 0, t["ts"]), _mult(tm, g["ctm"]))
            tam = abs(t["fs"]) * math.hypot(_mult(tm, g["ctm"])[2], _mult(tm, g["ctm"])[3])
            s = "".join(texto)
            if s.strip():
                xa, ya = _rotar(x0, y0, rot)
                xb, yb = _rotar(fin[4], fin[5], rot)
                salida.append((min(xa, xb), ya, max(xa, xb), tam or 1.0, s))

        while True:
            tok = lector.token()
            if tok is None:
                break
            if not isinstance(tok, Op):
                if tok == "[" or tok == "<<":
                    operandos.append(lector.objeto(tok))
                else:
                    operandos.append(tok)
                continue
            op, a = str(tok), operandos
            operandos = []
            try:
                if op == "BI":  # imagen en línea: se salta hasta «EI»
                    k = re.compile(rb"\sEI(?=[\s]|$)").search(lector.d, lector.d.find(b"ID", lector.p) + 2)
                    lector.p = k.end() if k else len(lector.d)
                elif op == "q":
                    pila.append(dict(g))
                elif op == "Q":
                    if pila:
                        g = pila.pop()
                elif op == "cm" and len(a) >= 6:
                    g["ctm"] = _mult(tuple(float(x) for x in a[-6:]), g["ctm"])
                elif op == "BT":
                    tm = tlm = IDENTIDAD
                elif op == "Tf" and len(a) >= 2:
                    t["tf"], t["fs"] = fuente(dic_fuentes, a[-2]), float(a[-1])
                elif op == "Tc" and a:
                    t["tc"] = float(a[-1])
                elif op == "Tw" and a:
                    t["tw"] = float(a[-1])
                elif op == "Tz" and a:
                    t["th"] = float(a[-1]) / 100.0
                elif op == "TL" and a:
                    t["tl"] = float(a[-1])
                elif op == "Ts" and a:
                    t["ts"] = float(a[-1])
                elif op in ("Td", "TD") and len(a) >= 2:
                    if op == "TD":
                        t["tl"] = -float(a[-1])
                    tlm = _mult((1, 0, 0, 1, float(a[-2]), float(a[-1])), tlm)
                    tm = tlm
                elif op == "Tm" and len(a) >= 6:
                    tlm = tm = tuple(float(x) for x in a[-6:])
                elif op == "T*":
                    tlm = _mult((1, 0, 0, 1, 0, -t["tl"]), tlm)
                    tm = tlm
                elif op == "Tj" and a and isinstance(a[-1], bytes):
                    mostrar(a[-1])
                elif op == "'" and a and isinstance(a[-1], bytes):
                    tlm = _mult((1, 0, 0, 1, 0, -t["tl"]), tlm)
                    tm = tlm
                    mostrar(a[-1])
                elif op == '"' and len(a) >= 3 and isinstance(a[-1], bytes):
                    t["tw"], t["tc"] = float(a[-3]), float(a[-2])
                    tlm = _mult((1, 0, 0, 1, 0, -t["tl"]), tlm)
                    tm = tlm
                    mostrar(a[-1])
                elif op == "TJ" and a and isinstance(a[-1], list):
                    for x in a[-1]:
                        if isinstance(x, bytes):
                            mostrar(x)
                        elif isinstance(x, (int, float)):
                            tm = _mult((1, 0, 0, 1, -float(x) / 1000.0 * t["fs"] * t["th"], 0), tm)
                elif op == "Do" and a:
                    ref = xobjetos.get(a[-1])
                    x = doc.res(ref)
                    if isinstance(x, dict) and x.get("Subtype") == "Form" and isinstance(ref, Ref):
                        matriz = doc.res(x.get("Matrix")) or list(IDENTIDAD)
                        sub = doc.res(x.get("Resources")) or recursos
                        ejecutar(doc.flujo_de(ref), sub, _mult(tuple(float(v) for v in matriz), g["ctm"]), profundidad + 1)
            except (TypeError, ValueError, IndexError):
                continue  # un operador mal formado no echa a perder el resto de la página

    contenidos = doc.res(pagina.get("Contents"))
    refs = contenidos if isinstance(contenidos, list) else [pagina.get("Contents")]
    datos = b"\n".join(doc.flujo_de(r) for r in refs if isinstance(r, Ref))
    ejecutar(datos, heredado.get("Resources") or {}, IDENTIDAD, 0)
    return salida


# ───────────── De trozos a tabla ─────────────
def _clave(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", t.lower())


def lineas(trozos):
    """Agrupa trozos en filas (de arriba hacia abajo) y, dentro de cada fila, en celdas [x0, x1, texto]."""
    filas = []
    for x0, y, x1, tam, s in sorted(trozos, key=lambda z: (-z[1], z[0])):
        if filas and abs(filas[-1]["y"] - y) <= max(1.5, 0.35 * min(tam, filas[-1]["tam"])):
            filas[-1]["trozos"].append((x0, x1, tam, s))
        else:
            filas.append({"y": y, "tam": tam, "trozos": [(x0, x1, tam, s)]})
    salida = []
    for f in filas:
        celdas = []
        for x0, x1, tam, s in sorted(f["trozos"]):
            if celdas:
                hueco = x0 - celdas[-1][1]
                if hueco < 0.15 * tam:
                    celdas[-1][1], celdas[-1][2] = max(x1, celdas[-1][1]), celdas[-1][2] + s
                    continue
                if hueco < 0.9 * tam:  # un espacio entre palabras
                    celdas[-1][1], celdas[-1][2] = max(x1, celdas[-1][1]), celdas[-1][2].rstrip() + " " + s.lstrip()
                    continue
            celdas.append([x0, x1, s])
        celdas = [[a, b, " ".join(s.split())] for a, b, s in celdas if s.strip()]
        if celdas:
            salida.append({"y": f["y"], "tam": f["tam"], "celdas": celdas})
    return salida


def _es_encabezado(fila, encabezados):
    if encabezados:
        buscados = {_clave(e) for e in encabezados}
        return buscados <= {_clave(c[2]) for c in fila["celdas"]}
    textos = [c[2] for c in fila["celdas"]]
    return len(textos) >= 3 and all(re.search(r"[^\W\d_]", t) and not re.search(r"\d", t) for t in textos)


def _alinear(fila, columnas):
    """Pone cada celda en la columna del encabezado que le queda más cerca (por su centro, entre los puntos medios)."""
    salida = [""] * len(columnas)
    limites = [(columnas[i][1] + columnas[i + 1][0]) / 2 for i in range(len(columnas) - 1)]
    for x0, x1, s in fila["celdas"]:
        centro = (x0 + x1) / 2
        i = sum(1 for lim in limites if centro > lim)
        # Si la celda está entera dentro de la columna de un encabezado, esa gana (descripciones largas que cruzan el punto medio).
        for k, (a, b, _) in enumerate(columnas):
            if x0 >= a - 2 and x1 <= b + 2:
                i = k
                break
        salida[i] = (salida[i] + " " + s).strip()
    return salida


def tabla_de_paginas(paginas, encabezados=None):
    """Lista de filas (como un CSV). Antes de la fila de encabezados, las celdas van en orden; después, alineadas a sus columnas.
    Una línea que solo continúa el texto de la fila anterior (sin fecha, justo debajo) se junta con ella."""
    filas, columnas, previa = [], None, None
    for pag in paginas:
        for f in lineas(pag):
            if _es_encabezado(f, encabezados) and (encabezados or columnas is None):
                columnas = [list(c) for c in f["celdas"]]
                filas.append([c[2] for c in f["celdas"]])
                previa = None
                continue
            if columnas is None:
                filas.append([c[2] for c in f["celdas"]])
                continue
            celdas = _alinear(f, columnas)
            llenas = [i for i, c in enumerate(celdas) if c]
            if previa and len(llenas) == 1 and llenas[0] > 0 and not celdas[0] and previa["fila"][0] and previa["fila"][llenas[0]] \
                    and not re.search(r"\d[\d.,]*$", celdas[llenas[0]]) and previa["y"] - f["y"] <= 1.6 * f["tam"]:
                previa["fila"][llenas[0]] += " " + celdas[llenas[0]]
                previa["y"] = f["y"]
                continue
            filas.append(celdas)
            previa = {"fila": celdas, "y": f["y"]}
        previa = None
    return filas


_CACHE = {}


def trozos(ruta):
    """Todos los trozos de texto del PDF, página por página. Con error claro si está cifrado, roto o sin texto."""
    try:
        st = os.stat(ruta)
    except OSError as e:
        raise PdfError(f"No pude abrir el PDF: {e.strerror or e}.") from e
    clave = (os.path.abspath(ruta), st.st_mtime_ns, st.st_size)
    if clave in _CACHE:
        return _CACHE[clave]
    if st.st_size > MAXIMO_ARCHIVO:
        raise PdfError("El PDF es demasiado grande para ser una cartola.")
    with open(ruta, "rb") as f:
        doc = Documento(f.read())
    paginas = [trozos_de_pagina(doc, p, h) for p, h in doc.paginas()]
    if not paginas:
        raise PdfError("No encontré páginas en este PDF. Puede estar dañado: descárgalo de nuevo desde tu banco.")
    if not any(paginas):
        raise PdfError("Este PDF no tiene texto: parece una imagen escaneada. Descarga la cartola en CSV o Excel desde tu banco, "
                       "o una cartola en PDF «digital» (no escaneada).")
    _CACHE.clear()  # basta con recordar el último archivo
    _CACHE[clave] = paginas
    return paginas


def tabla(ruta, encabezados=None):
    return tabla_de_paginas(trozos(ruta), encabezados)
