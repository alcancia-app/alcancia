"""Genera las cartolas PDF FICTICIAS de las pruebas (pruebas/datos/), sin librerías.

  python3 herramientas/generar_pdf_prueba.py

- cartola_ejemplo.pdf: Banco Ejemplo, sin compresión, Helvetica con WinAnsi (la «ó» de «Descripción» es un byte), con Tm, Td,
  T*, ', TJ con espacios por ajuste, xref correcta. Mismos movimientos que cartola_ejemplo.csv.
- cartola_ejemplo_comprimida.pdf: Billetera Ejemplo, 2 páginas, flujos con FlateDecode, una fuente Type0/Identity-H con
  ToUnicode (bfchar y bfrange), fuentes dentro de un flujo de objetos (/ObjStm) con xref en flujo, el título en un
  formulario (Do), la página 2 escalada con cm y una descripción que sigue en una segunda línea.
Todos los datos son inventados (Ana Pérez, Matías Soto, Banco Ejemplo).
"""
import os
import sys
import zlib

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "bin"))
from pdf import ancho_helvetica  # noqa: E402

DESTINO = os.path.join(RAIZ, "pruebas", "datos")


def cadena(texto, codificacion="cp1252"):
    b = texto.encode(codificacion)
    return b"(" + b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def armar(objetos, raiz, xref_en_flujo=None):
    """objetos: {num: bytes del objeto (sin «n 0 obj»)}. Devuelve el PDF con su xref (tabla clásica o en flujo)."""
    salida = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    posiciones = {}
    for num in sorted(objetos):
        posiciones[num] = len(salida)
        salida += f"{num} 0 obj\n".encode() + objetos[num] + b"\nendobj\n"
    total = max(objetos) + 1
    if xref_en_flujo is None:
        inicio = len(salida)
        salida += f"xref\n0 {total}\n0000000000 65535 f \n".encode()
        for n in range(1, total):
            salida += f"{posiciones.get(n, 0):010d} {'00000 n' if n in posiciones else '65535 f'} \n".encode()
        salida += f"trailer\n<< /Size {total} /Root {raiz} 0 R >>\nstartxref\n{inicio}\n%%EOF\n".encode()
        return bytes(salida)
    comprimidos, num_xref = xref_en_flujo  # {num: (objstm, índice)}
    total = max(total, num_xref + 1)
    filas = bytearray(b"\x00\x00\x00\x00\x00\xff\xff")
    inicio = len(salida)
    for n in range(1, total):
        if n in comprimidos:
            filas += bytes([2]) + comprimidos[n][0].to_bytes(4, "big") + comprimidos[n][1].to_bytes(2, "big")
        elif n == num_xref:
            filas += bytes([1]) + inicio.to_bytes(4, "big") + b"\x00\x00"
        else:
            filas += bytes([1]) + posiciones.get(n, 0).to_bytes(4, "big") + b"\x00\x00"
    datos = zlib.compress(bytes(filas), 9)
    salida += (f"{num_xref} 0 obj\n<< /Type /XRef /Size {total} /W [1 4 2] /Root {raiz} 0 R /Filter /FlateDecode "
               f"/Length {len(datos)} >>\nstream\n").encode() + datos + b"\nendstream\nendobj\n"
    salida += f"startxref\n{inicio}\n%%EOF\n".encode()
    return bytes(salida)


def flujo(datos, comprimir=False, extra=b""):
    if comprimir:
        datos = zlib.compress(datos, 9)
        extra += b" /Filter /FlateDecode"
    return b"<< /Length " + str(len(datos)).encode() + extra + b" >>\nstream\n" + datos + b"\nendstream"


# ───────────── 1) Banco Ejemplo, sin compresión ─────────────
MOVIMIENTOS = [
    ("01/10/2026", "SALDO INICIAL", "", "", "850.000"),
    ("02/10/2026", "COMPRA LIDER EXPRESS 2231", "23.450", "", "826.550"),
    ("03/10/2026", "UBER EATS *PEDIDO 8F2K", "12.990", "", "813.560"),
    ("03/10/2026", "CAFE LA ESQUINA", "3.200", "", "810.360"),
    ("03/10/2026", "CAFE LA ESQUINA", "3.200", "", "807.160"),
    ("05/10/2026", "REMUNERACION EMPRESA FICTICIA SPA", "", "1.250.000", "2.057.160"),
    ("06/10/2026", "NETFLIX.COM", "9.990", "", "2.047.170"),
    ("08/10/2026", "COPEC AV SIEMPREVIVA", "35.000", "", "2.012.170"),
    ("09/10/2026", "TRANSFERENCIA A MATIAS SOTO", "50.000", "", "1.962.170"),
    ("10/10/2026", "FARMACIA CRUZ VERDE", "8.750,50", "", "1.953.419,50"),
]


def banco_ejemplo():
    tam = 9
    c = bytearray()
    # Títulos con Td, T* y ' (comillas simples: «baja una línea y escribe»).
    c += b"BT /F2 14 Tf 16 TL 50 790 Td " + cadena("Banco Ejemplo") + b" Tj /F1 10 Tf T* " + cadena("Cartola de cuenta corriente") \
        + b" Tj " + cadena("Titular: Ana Pérez") + b" ' ET\n"
    # Columnas: fecha y descripción a la izquierda; montos alineados a la derecha.
    izq = {0: 50, 1: 115}
    der = {2: 400, 3: 480, 4: 560}
    y = 720
    c += b"BT /F2 9 Tf\n"
    for i, h in enumerate(["Fecha", "Descripción", "Cargos", "Abonos", "Saldo"]):
        x = izq[i] if i in izq else der[i] - ancho_helvetica(h) * tam / 1000
        c += f"1 0 0 1 {x:.2f} {y} Tm ".encode() + cadena(h) + b" Tj\n"
    c += b"ET\n"
    for fila in MOVIMIENTOS:
        y -= 14
        c += b"BT /F1 9 Tf\n"
        for i, v in enumerate(fila):
            if not v:
                continue
            if i == 1 and " " in v:  # la descripción con TJ: el espacio entre palabras es un ajuste, no un carácter
                partes = v.split(" ")
                arreglo = b" -278 ".join(cadena(p) for p in partes)
                c += f"1 0 0 1 {izq[1]} {y} Tm ".encode() + b"[" + arreglo + b"] TJ\n"
                continue
            x = izq[i] if i in izq else der[i] - ancho_helvetica(v) * tam / 1000
            c += f"1 0 0 1 {x:.2f} {y} Tm ".encode() + cadena(v) + b" Tj\n"
        c += b"ET\n"
    y -= 28
    c += f"BT /F2 9 Tf 1 0 0 1 50 {y} Tm ".encode() + cadena("Total cargos") + b" Tj "
    c += f"1 0 0 1 {der[2] - ancho_helvetica('146.580,50') * tam / 1000:.2f} {y} Tm ".encode() + cadena("146.580,50") + b" Tj ET\n"
    c += b"0.8 g 50 60 510 0.5 re f\n"  # una línea (dibujo, no texto)
    objetos = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
        4: flujo(bytes(c)),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        6: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        7: b"<< /Producer (Alcancia - generar_pdf_prueba.py) /Title (Cartola ficticia) >>",
    }
    return armar(objetos, 1)


# ───────────── 2) Billetera Ejemplo, comprimida, Type0 con ToUnicode ─────────────
PAGINA1 = [
    ("2026-10-01", "SALDO ANTERIOR", "", "120.000"),
    ("2026-10-02", "CAFÉ LA ESQUINA", "-3.400", "116.600"),
    ("2026-10-04", "DELIVERY RAPIDITO *PEDIDO", "-14.990", "101.610"),
    ("2026-10-06", ("PAGO SUSCRIPCIÓN", "MÚSICA PREMIUM"), "-5.490", "96.120"),
    ("2026-10-09", "CARGA DESDE BANCO EJEMPLO", "50.000", "146.120"),
]
PAGINA2 = [
    ("2026-10-12", "VIAJES APP *TRIP", "-6.200", "139.920"),
    ("2026-10-15", "DEVOLUCIÓN TIENDA ONLINE", "9.990", "149.910"),
    ("2026-10-18", "TRANSFERENCIA DE MATÍAS SOTO", "20.000", "169.910"),
]
ENCABEZADOS2 = ["Fecha", "Detalle", "Monto", "Saldo"]


def billetera_ejemplo():
    textos = ["Billetera Ejemplo", "Movimientos de tu cuenta", "Ana Pérez", "Página 1 de 2", "Página 2 de 2", "Total del período"]
    textos += ENCABEZADOS2 + [x for f in PAGINA1 + PAGINA2 for v in f for x in (v if isinstance(v, tuple) else (v,))]
    letras = sorted({ch for t in textos for ch in t})
    cid = {ch: i + 1 for i, ch in enumerate(letras)}  # CID 1, 2, 3… en orden de código: los seguidos van en bfrange
    hexa = lambda t: b"<" + "".join(f"{cid[ch]:04X}" for ch in t).encode() + b">"
    tam = 9

    def ancho(t):
        return ancho_helvetica(t) * tam / 1000

    def fila(y, valores, f="/F1"):
        izq, der = {0: 50, 1: 130}, {2: 430, 3: 540}
        b = bytearray(b"BT " + f.encode() + f" {tam} Tf\n".encode())
        for i, v in enumerate(valores):
            if v:
                x = izq[i] if i in izq else der[i] - ancho(v)
                b += f"1 0 0 1 {x:.2f} {y} Tm ".encode() + hexa(v) + b" Tj\n"
        return b + b"ET\n"

    def pagina(movs, y0, numero):
        c = bytearray(fila(y0, ENCABEZADOS2))
        y = y0
        for f, d, m, s in movs:
            y -= 14
            if isinstance(d, tuple):
                c += fila(y, [f, d[0], m, s])
                y -= 11
                c += fila(y, ["", d[1], "", ""])  # la descripción sigue abajo, sin fecha
            else:
                c += fila(y, [f, d, m, s])
        c += f"BT /F1 8 Tf 1 0 0 1 270 40 Tm ".encode() + hexa(numero) + b" Tj ET\n"
        return c

    p1 = bytearray(b"q 1 0 0 1 50 770 cm /Titulo Do Q\n") + pagina(PAGINA1, 700, "Página 1 de 2")
    # Página 2 escalada a la mitad con cm: las coordenadas van al doble y el resultado es el mismo.
    c2 = pagina(PAGINA2, 700, "Página 2 de 2") + fila(600, ["", "Total del período", "", "169.910"])
    p2 = bytearray(b"q 0.5 0 0 0.5 0 0 cm\n")
    for linea in bytes(c2).split(b"\n"):
        partes = linea.split(b" ")
        if b"Tm" in partes:
            k = partes.index(b"Tm")
            partes[k - 2] = f"{float(partes[k - 2]) * 2:.2f}".encode()
            partes[k - 1] = f"{float(partes[k - 1]) * 2:.2f}".encode()
        if b"Tf" in partes:
            k = partes.index(b"Tf")
            partes[k - 1] = str(int(partes[k - 1]) * 2).encode()
        p2 += b" ".join(partes) + b"\n"
    p2 += b"Q\n"
    titulo = b"BT /F1 14 Tf 0 0 Td " + hexa("Billetera Ejemplo") + b" Tj 0 -16 Td /F1 10 Tf " + hexa("Movimientos de tu cuenta") \
        + b" Tj 0 -13 Td " + hexa("Ana Pérez") + b" Tj ET"

    # ToUnicode: tramos seguidos en bfrange y el resto en bfchar.
    tramos, actual = [], [letras[0]]
    for ch in letras[1:]:
        if ord(ch) == ord(actual[-1]) + 1:
            actual.append(ch)
        else:
            tramos.append(actual)
            actual = [ch]
    tramos.append(actual)
    rangos = [t for t in tramos if len(t) > 1]
    sueltos = [t[0] for t in tramos if len(t) == 1]
    cmap = ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CMapName /Alcancia-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n")
    cmap += f"{len(sueltos)} beginbfchar\n" + "".join(f"<{cid[ch]:04X}> <{ord(ch):04X}>\n" for ch in sueltos) + "endbfchar\n"
    cmap += f"{len(rangos)} beginbfrange\n" + "".join(f"<{cid[t[0]]:04X}> <{cid[t[-1]]:04X}> <{ord(t[0]):04X}>\n" for t in rangos)
    cmap += "endbfrange\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
    anchos = " ".join(f"{cid[ch]} [{ancho_helvetica(ch) if ord(ch) < 127 else 556}]" for ch in letras)

    # Fuentes dentro de un flujo de objetos (10 y 11): así son muchos PDFs modernos.
    fuente = b"<< /Type /Font /Subtype /Type0 /BaseFont /EjemploSans /Encoding /Identity-H /DescendantFonts [11 0 R] /ToUnicode 12 0 R >>"
    cidfont = (b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /EjemploSans /CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) "
               b"/Supplement 0 >> /DW 556 /W [" + anchos.encode() + b"] >>")
    cabecera = f"10 0 11 {len(fuente) + 1} ".encode()
    objstm = cabecera + fuente + b" " + cidfont
    objetos = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 /Resources << /Font << /F1 10 0 R >> /XObject << /Titulo 7 0 R >> >> >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents 5 0 R >>",
        4: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents [6 0 R] >>",
        5: flujo(bytes(p1), True),
        6: flujo(bytes(p2), True),
        7: flujo(titulo, True, b" /Type /XObject /Subtype /Form /BBox [0 -40 300 20] /Resources << /Font << /F1 10 0 R >> >>"),
        8: flujo(objstm, True, f" /Type /ObjStm /N 2 /First {len(cabecera)}".encode()),
        12: flujo(cmap.encode(), True),
    }
    return armar(objetos, 1, ({10: (8, 0), 11: (8, 1)}, 13))


ARCHIVOS = {"cartola_ejemplo.pdf": banco_ejemplo, "cartola_ejemplo_comprimida.pdf": billetera_ejemplo}

if __name__ == "__main__":
    for nombre, f in ARCHIVOS.items():
        datos, ruta = f(), os.path.join(DESTINO, nombre)
        with open(ruta, "wb") as a:
            a.write(datos)
        print(f"{ruta} ({len(datos)} bytes)")
