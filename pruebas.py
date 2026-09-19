"""comprueba el arreglo del margen, la paginacion y el idioma"""
import re, html as H
import lib_pro
from lib_pro import (
    margen_cuerpo, limpiar, a_html, detectar_idioma, hueco_de_columnas,
    titulo_corrido, columnas_gemelas, tramos_de_columnas,
)

FUENTE = "ABCDEF+Palatino"

def linea(texto, x0, top, fuente=FUENTE):
    """una linea como la que devuelve extract_text_lines

    los anchos van variados a proposito: en prosa cada caracter mide una
    cosa, y es justo por ahi por donde fuentes_mono() distingue la prosa
    del codigo. con todos iguales el texto pasaria por monoespaciado.
    """
    chars, x = [], x0
    for c in texto:
        ancho = 4.0 + (ord(c) % 5)
        chars.append({"text": c, "fontname": fuente, "size": 10.0,
                      "x0": x, "x1": x + ancho})
        x += ancho
    return {"text": texto, "chars": chars, "x0": x0,
            "x1": x, "top": top, "bottom": top + 11}

# una pagina de apuntes de la IU: nota al margen a la izquierda del cuerpo
CUERPO, NOTA, PASO = 120.0, 50.0, 14.0
pagina = [
    linea("Monografie", NOTA, 100.0),
    linea("Hier wird also nur ein Thema beleuchtet.", CUERPO, 100.0),
    linea("Monografien liefern Beitraege zum Diskurs.", CUERPO, 100.0 + PASO),
    linea("Dissertationen sind klassische Monografien.", CUERPO, 100.0 + 2 * PASO),
]

print("1) margen_cuerpo")
print("   minimo (lo de antes):", min(l["x0"] for l in pagina))
print("   margen del cuerpo   :", margen_cuerpo(pagina))
assert margen_cuerpo(pagina) == CUERPO

print("2) limpiar: cada frase su parrafo")
bloques = limpiar([dict(l, chars=list(l["chars"])) for l in pagina])
for b in bloques:
    print("   [%s] %s" % (b["tipo"], b["texto"][:60]))
assert len(bloques) == 4, "se han vuelto a pegar: %d bloques" % len(bloques)

print("3) las continuaciones de verdad se siguen pegando")
partido = [
    linea("Ein Satz, der auf der naechsten Zeile", CUERPO, 100.0),
    linea("weitergeht und erst hier endet.", CUERPO + 12, 100.0 + PASO),
]
b2 = limpiar(partido)
print("   ->", b2[0]["texto"])
assert len(b2) == 1, "se ha partido una frase en %d" % len(b2)

print("4) a_html pagina por pagina del pdf")
falsos = [
    {"tipo": "parrafo", "texto": "uno", "top": 1, "pagina": 1},
    {"tipo": "parrafo", "texto": "dos", "top": 2, "pagina": 1},
    {"tipo": "parrafo", "texto": "tres", "top": 1, "pagina": 8},
    {"tipo": "imagen", "texto": "figuras/x.png", "top": 2, "pagina": 8},
]
cuerpo = a_html(falsos)
nums = re.findall(r'data-pagina="(\d+)"', cuerpo)
print("   secciones:", nums)
assert nums == ["1", "8"], nums
assert cuerpo.count("<section") == 2

print("5) detectar_idioma con el texto de verdad")
for libro, esperado in [
    ("Einf\u00fchrung_in_das_wissenschaftliche_arbeit_von_IT_und_Tech", "de"),
    ("ThinkPython", "en"),
]:
    s = open("libros/%s/index.html" % libro, encoding="utf-8").read()
    ps = [{"tipo": "parrafo", "texto": H.unescape(t)}
          for t in re.findall(r'<p id="b\d+"[^>]*>(.*?)</p>', s, re.S)]
    visto = detectar_idioma(ps)
    print("   %-32s -> %s" % (libro[:32], visto))
    assert visto == esperado, (libro, visto)


print("6) hueco_de_columnas separa la nota del cuerpo")


def palabra(x0, x1, top):
    return {"x0": x0, "x1": x1, "top": top, "bottom": top + 11}


# 40 renglones de cuerpo de x=82 a x=438 y una nota a la derecha, de 470
# a 545: el corte tiene que caer en el canal de en medio
conNota = [palabra(82 + 30 * i, 108 + 30 * i, 100.0 + 10 * f)
           for f in range(40) for i in range(12)]
conNota += [palabra(470, 545, 100.0 + 10 * f) for f in range(8)]
corte = hueco_de_columnas(conNota, 595.0)
print("   con nota al margen:", corte)
assert corte is not None and 438 < corte < 470, corte

sinNota = [palabra(82 + 30 * i, 108 + 30 * i, 100.0 + 10 * f)
           for f in range(40) for i in range(12)]
print("   una sola columna  :", hueco_de_columnas(sinNota, 595.0))
assert hueco_de_columnas(sinNota, 595.0) is None

# dos mitades de texto no son cuerpo y nota: es la pagina entera
mitades = [palabra(82 + 30 * i, 108 + 30 * i, 100.0 + 10 * f)
           for f in range(40) for i in range(6)]
mitades += [palabra(320 + 30 * i, 346 + 30 * i, 100.0 + 10 * f)
            for f in range(40) for i in range(6)]
print("   dos columnas iguales:", hueco_de_columnas(mitades, 595.0))
assert hueco_de_columnas(mitades, 595.0) is None

print("7) titulo_corrido solo recorta lo que se repite")


class BandaFalsa:
    def __init__(self, lineas):
        self.lineas = lineas

    def extract_text_lines(self, **_):
        return self.lineas


class PaginaConCabecera:
    """una pagina de la que solo interesa su primer renglon"""

    width, height = 595.0, 842.0

    def __init__(self, primera):
        self.primera = primera

    def crop(self, _caja):
        return BandaFalsa([{"text": self.primera, "bottom": 60.0}])


conCabecera = [PaginaConCabecera("Einfuehrung, Seite %d" % n) for n in range(1, 21)]
print("   cabecera corrida  :", repr(titulo_corrido(conCabecera)))
assert titulo_corrido(conCabecera) == "Einfuehrung, Seite #"

# un libro sin cabecera: cada pagina empieza por su titulo de seccion, y
# cada titulo dice una cosa distinta. si dijeran todos lo mismo salvo el
# numero seria una cabecera corrida a todos los efectos, y esta bien que
# se recorte
TITULOS = """wahr Logik Zweifel Quellen Methoden Empirie Theorie Modell
             Daten Analyse Ethik Zitat Plagiat Aufbau Stil Recherche
             Hypothese Statistik Umfrage Bericht""".split()
sinCabecera = [PaginaConCabecera("%d.%d Was ist %s?" % (n, n, t))
               for n, t in enumerate(TITULOS, 1)]
print("   sin cabecera      :", titulo_corrido(sinCabecera))
assert titulo_corrido(sinCabecera) is None

print("8) los titulos del cuerpo van en su bloque")
NEGRITA = "ABCDEF+PalatinoBold"
conTitulo = [
    linea("Erster Absatz endet hier.", CUERPO, 100.0),
    linea("Alltagswissen und Wissenschaft", CUERPO, 100.0 + PASO, NEGRITA),
    linea("Das Alltagswissen beruht auf Erfahrungen.", CUERPO, 100.0 + 2 * PASO),
]
b3 = limpiar(conTitulo)
for b in b3:
    print("   [%-7s] %s" % (b["tipo"], b["texto"][:55]))
assert [b["tipo"] for b in b3] == ["parrafo", "titulo", "parrafo"], b3

print("9) el libro entero, de punta a punta")


class PaginaFalsa:
    """lo poco de una pagina de pdfplumber que mira generar_html()"""

    width, height = 595.0, 842.0
    curves = rects = lines = images = []

    def __init__(self, numero):
        self.page_number = numero


def leer_falso(ruta, inicio=0):
    for numero in (26, 27):
        yield (
            PaginaFalsa(numero),
            [dict(l, chars=list(l["chars"]), nota=False) for l in pagina],
        )


lib_pro.read_document = leer_falso
bloques, idioma = lib_pro.generar_html("falso.pdf", "prueba.html", inicio=25)
doc = open("prueba.html", encoding="utf-8").read()
print("   bloques: %d, idioma: %s" % (len(bloques), idioma))
print("   paginas:", re.findall(r'data-pagina="(\d+)"', doc))
assert '<html lang="de">' in doc, "el idioma no ha llegado al html"
# el numero es el que pone pdfplumber, no el orden en que van saliendo
assert re.findall(r'data-pagina="(\d+)"', doc) == ["26", "27"]
assert "@IDIOMA@" not in doc and "@TITULO@" not in doc, "hueco sin rellenar"
assert 'getAttribute("data-pagina")' in doc, "el js no ensena la pagina real"

print("10) las dos columnas de un paper")

# la misma pagina de mitades que hueco_de_columnas descarta a proposito:
# para columnas_gemelas es justo lo que busca
mitades = [palabra(82 + 30 * i, 108 + 30 * i, 100.0 + 10 * f)
           for f in range(40) for i in range(6)]
mitades += [palabra(320 + 30 * i, 346 + 30 * i, 100.0 + 10 * f)
            for f in range(40) for i in range(6)]
corte = columnas_gemelas(mitades, 595.0)
print("   dos columnas iguales:", corte)
assert corte is not None and 262 < corte < 320, corte

# una nota al margen no son dos columnas de cuerpo
print("   con nota al margen  :", columnas_gemelas(conNota, 595.0))
assert columnas_gemelas(conNota, 595.0) is None
print("   una sola columna    :", columnas_gemelas(sinNota, 595.0))
assert columnas_gemelas(sinNota, 595.0) is None

# titulo a lo ancho arriba y debajo el cuerpo a dos columnas: dos tramos,
# y el de arriba sin corte porque se lee de lado a lado
conTitulo = [palabra(82, 500, 40.0), palabra(82, 500, 55.0)]
conTitulo += mitades
tramos = tramos_de_columnas(conTitulo, 595.0)
print("   tramos:", [(round(a), round(b), c) for a, b, c in tramos])
assert len(tramos) == 2, tramos
assert tramos[0][2] is None, "el titulo no va por columnas"
assert tramos[1][2] is not None, "el cuerpo si"

# la columna izquierda se queda en blanco a media pagina: lo de debajo ya
# es otra maqueta y no puede colarse delante de la derecha
cortada = [palabra(82 + 30 * i, 108 + 30 * i, 100.0 + 10 * f)
           for f in range(10) for i in range(6)]
cortada += [palabra(320 + 30 * i, 346 + 30 * i, 100.0 + 10 * f)
            for f in range(40) for i in range(6)]
cortada += [palabra(82, 150, 560.0)]
tramos = tramos_de_columnas(cortada, 595.0)
print("   con columna corta:", [(round(a), round(b), c) for a, b, c in tramos])
assert len(tramos) >= 2 and tramos[0][1] < 560, tramos

print("\nTODO OK")
