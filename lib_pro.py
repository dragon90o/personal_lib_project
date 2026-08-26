"""lector de libros"""

import os
import wave
import subprocess
import shutil
import textwrap
import html 
import pdfplumber
from piper import PiperVoice
from plantilla import PLANTILLA
from tabla import traducir, ta

RUTA_DE_DOCUMENTO = "ThinkPython.pdf"
PAGINA_INICIAL = 25


def read_document(ruta, inicio=0):
    """va soltando (pagina, lineas) de cada pagina del libro"""
    with pdfplumber.open(ruta) as r:
        for page in r.pages[inicio:]:
            palabras = page.extract_words()
            if not palabras:
                continue
            recorte_pagina = page.crop(
                (0, palabras[0]["bottom"] + 2, page.width, page.height)
            )

            texto_del_libro = recorte_pagina.extract_text_lines(x_tolerance=1.5)

            yield page, texto_del_libro


def fuentes_mono(lineas, minimo=20, tolerancia=0.02, dominio=0.8):
    """devuelve las fuentes monoespaciadas, que es donde va el codigo

    no se puede mirar el nombre: en ThinkPython.pdf la fuente del codigo es
    un Type3 sin nombre y pdfminer la llama "unknown", pero en un pdf sano
    seria Courier o cualquier otra. lo que si es constante es la ANCHURA:
    en monoespaciada todos los caracteres miden igual, en prosa no.
    se normaliza por el tamano de letra para que no despiste un pie de
    pagina en cuerpo menor.
    """
    anchos = {}
    for l in lineas:
        for c in l["chars"]:
            # el espacio lleva kerning propio y ensucia la medida
            if c["text"] == " " or not c["size"]:
                continue
            anchos.setdefault(c["fontname"], []).append(
                round((c["x1"] - c["x0"]) / c["size"] / tolerancia)
            )
    mono = set()
    for fuente, medidas in anchos.items():
        # con cuatro caracteres sueltos cualquier fuente parece constante
        if len(medidas) < minimo:
            continue
        # no vale exigir que TODOS midan igual: bajo "unknown" caen varias
        # fuentes Type3 distintas, y ocho simbolos sueltos entre 297
        # caracteres tumbaban paginas enteras de codigo (67, 199, 200, 208).
        # basta con que la anchura dominante se lleve la gran mayoria.
        comun = max(medidas.count(m) for m in set(medidas))
        if comun >= len(medidas) * dominio:
            mono.add(fuente)
    return mono


def cajas_de_figuras(page, junta=20, minimo=10, cabecera=75):
    """agrupa los trazos vectoriales de la pagina en cajas

    los diagramas del libro NO son imagenes: en las 240 paginas hay una
    sola imagen embebida (pag. 205) y en cambio 253 curvas y 217 rects.
    page.images no los ve, asi que hay que localizar la region y
    rasterizarla despues.
    """
    objetos = [
        o
        for o in page.curves + page.rects + page.lines + page.images
        # la regla horizontal de la cabecera sale en las 240 paginas
        if o["top"] > cabecera
    ]
    if not objetos:
        return []
    cajas = []
    for o in sorted(objetos, key=lambda o: o["top"]):
        if cajas and o["top"] <= cajas[-1][3] + junta:
            c = cajas[-1]
            cajas[-1] = [
                min(c[0], o["x0"]),
                c[1],
                max(c[2], o["x1"]),
                max(c[3], o["bottom"]),
            ]
        else:
            cajas.append([o["x0"], o["top"], o["x1"], o["bottom"]])
    # un trazo suelto no es una figura
    return [c for c in cajas if c[2] - c[0] >= minimo and c[3] - c[1] >= minimo]


def fuente_principal(chars):
    """la fuente con la que esta escrita la mayoria de estos caracteres"""
    cuenta = {}
    for c in chars:
        cuenta[c["fontname"]] = cuenta.get(c["fontname"], 0) + 1
    return max(cuenta, key=cuenta.get) if cuenta else None


def estirar_cajas(cajas, lineas, mono, margen=15):
    """mete dentro de la figura las etiquetas que la rodean

    el bbox de los trazos no incluye el texto: "Point" o "box" se quedaban
    fuera y salian cortados por la mitad en el png. las etiquetas van en
    otra fuente que el cuerpo del libro, y por ahi se distinguen del
    parrafo que va justo encima o del pie de figura.
    """
    cuerpo = fuente_principal([c for l in lineas for c in l["chars"]])
    etiquetas = []
    for l in lineas:
        fuente = fuente_principal(l["chars"])
        if fuente != cuerpo:
            etiquetas.append((l, fuente in mono))
    for c in cajas:
        creciendo = True
        while creciendo:
            creciendo = False
            for l, es_codigo in etiquetas:
                # a la misma altura que los trazos: es parte del dibujo
                pegada = l["top"] < c[3] and l["bottom"] > c[1]
                # justo encima o debajo, pero metida en el ancho de la caja:
                # un titulo como "Point". el codigo no se toca, que desborda
                # la figura y se lo tragaria entero
                encima = (
                    not es_codigo
                    and l["top"] < c[3] + margen
                    and l["bottom"] > c[1] - margen
                    and l["x0"] > c[0] - margen
                    and l["x1"] < c[2] + margen
                )
                if not (pegada or encima):
                    continue
                crecida = [
                    min(c[0], l["x0"]),
                    min(c[1], l["top"]),
                    max(c[2], l["x1"]),
                    max(c[3], l["bottom"]),
                ]
                if crecida != c:
                    c[:] = crecida
                    creciendo = True
    return cajas


def rasterizar(page, caja, destino, resolucion=200, margen=8):
    """guarda en png el trozo de pagina que ocupa la figura"""
    x0, top, x1, bottom = caja
    recorte = (
        max(0, x0 - margen),
        max(0, top - margen),
        min(page.width, x1 + margen),
        min(page.height, bottom + margen),
    )
    page.crop(recorte).to_image(resolution=resolucion).save(destino)


def dentro(linea, cajas):
    """la linea cae dentro de una figura, o sea que ya esta rasterizada"""
    medio = (linea["top"] + linea["bottom"]) / 2
    return any(
        c[1] <= medio <= c[3] and linea["x0"] >= c[0] - 2 and linea["x1"] <= c[2] + 2
        for c in cajas
    )


def solo_comillas(linea):
    """la linea no es mas que comillas sueltas"""
    t = linea["text"].strip()
    return bool(t) and all(c in "'\" " for c in t)


def ancho_char(chars):
    """anchura mas repetida y cuanto manda, que en monoespaciada es todo"""
    anchos = {}
    for c in chars:
        a = round(c["x1"] - c["x0"], 1)
        anchos[a] = anchos.get(a, 0) + 1
    ancho = max(anchos, key=anchos.get)
    return ancho, anchos[ancho] / len(chars)


def por_columnas(chars, ancho=None, izquierda=None):
    """rehace el texto colocando cada caracter en su columna

    solo sirve en monoespaciada: ahi la columna sale de dividir por la
    anchura de un caracter. la anchura y el margen se pasan desde fuera
    cuando se rehace un bloque entero, porque la sangria de una linea es
    relativa al bloque y no a si misma.
    """
    if ancho is None:
        ancho, _ = ancho_char(chars)
    if izquierda is None:
        izquierda = chars[0]["x0"]
    texto = []
    for c in chars:
        columna = int(round((c["x0"] - izquierda) / ancho))
        if columna > len(texto):
            texto.extend(" " * (columna - len(texto)))
        texto.append(traducir(c["text"], ta))
    return "".join(texto)


def por_posicion(destino, suelta):
    """cuela los caracteres sueltos dentro del texto ya montado

    en prosa no se puede rehacer la linea por columnas: la fuente es de
    anchura variable y salen las palabras pegadas ("operatoralsoworks").
    asi que se respeta el texto tal cual y solo se abre hueco para la
    comilla, buscando entre que dos caracteres cae por su posicion.
    """
    texto = destino["text"]
    sitios = []
    j = 0
    for pos, letra in enumerate(texto):
        if j >= len(destino["chars"]):
            break
        c = destino["chars"][j]
        if letra == traducir(c["text"], ta)[:1]:
            sitios.append((c["x0"], pos))
            j += 1
    # de derecha a izquierda, que si no se desplazan los sitios de detras
    for c in sorted(suelta["chars"], key=lambda c: -c["x0"]):
        pos = len(texto)
        for x0, p in sitios:
            if x0 > c["x0"]:
                pos = p
                break
        texto = texto[:pos] + traducir(c["text"], ta) + texto[pos:]
    return texto


def fusionar(suelta, destino):
    """mete los caracteres de una linea suelta en la de debajo"""
    chars = sorted(destino["chars"] + suelta["chars"], key=lambda c: c["x0"])
    _, manda = ancho_char(chars)
    if manda >= 0.8:
        destino["text"] = por_columnas(chars)
    else:
        destino["text"] = por_posicion(destino, suelta)
    destino["chars"] = chars


def pegar_comillas(lineas, hueco=10):
    """devuelve las lineas con las comillas sueltas puestas en su sitio

    las comillas de las cadenas se dibujan mas altas que el resto del
    renglon y extract_text_lines las saca en una linea propia: 435 lineas
    en el libro, 1339 comillas. tirarlas se llevaba por delante las
    cadenas de TODOS los ejemplos de codigo ("print 'Hello, World!'"
    quedaba en "print Hello, World!").
    """
    sueltas, resto = [], []
    for l in lineas:
        (sueltas if solo_comillas(l) else resto).append(l)
    for s in sueltas:
        debajo = [l for l in resto if 0 < l["top"] - s["top"] < hueco]
        # una sola en las 240 paginas se queda sin renglon debajo (pag. 94)
        if debajo:
            fusionar(s, min(debajo, key=lambda l: l["top"]))
    return resto


def interlineado(lineas):
    """distancia de un renglon al siguiente dentro de un mismo bloque

    es la separacion mas corta que se ve entre dos renglones seguidos: si
    una pareja esta mas separada que eso, en medio hay una linea en blanco.
    """
    saltos = [
        b["top"] - a["top"]
        for a, b in zip(lineas, lineas[1:])
        if b["top"] > a["top"]
    ]
    return min(saltos) if saltos else 0


def limpiar(texto, cajas=()):
    """limpia el texto de ascii y lo junta en bloques de prosa y codigo"""
    for linea in texto:
        linea["text"] = traducir(linea["text"], ta)
    # las etiquetas de los diagramas ya salen dentro del png de la figura
    buenas = [l for l in pegar_comillas(texto) if not dentro(l, cajas)]
    if not buenas:
        return []
    margen = min(l["x0"] for l in buenas)
    mono = fuentes_mono(buenas)
    for l in buenas:
        # mirar solo el primer caracter falla con las frases que empiezan
        # por una palabra en fuente de codigo ("76trombones is illegal...")
        raros = sum(1 for c in l["chars"] if c["fontname"] in mono)
        # una linea de codigo de verdad es 100% monoespaciada; la prosa con
        # nombres de variable dentro no pasa del 70%
        l["codigo"] = raros > len(l["chars"]) * 0.9

    codigo = [l for l in buenas if l["codigo"]]
    if codigo:
        # extract_text_lines empieza cada linea en su primer caracter, asi
        # que la sangria se perdia y el cuerpo de un def acababa pegado al
        # margen. se rehace el renglon por columnas contando desde el
        # margen del bloque, que en python la sangria es sintaxis.
        izquierda = min(l["x0"] for l in codigo)
        ancho, _ = ancho_char([c for l in codigo for c in l["chars"]])
        for l in codigo:
            l["text"] = por_columnas(l["chars"], ancho, izquierda)
    paso = interlineado(codigo)

    resultado = []
    anterior = None
    for l in buenas:
        es_codigo = l["codigo"]
        anterior_codigo = anterior is not None and anterior["codigo"]
        # cuantos renglones hay del anterior a este: uno es la linea de
        # debajo, dos es que el ejemplo lleva una linea en blanco en medio
        saltos = (
            int(round((l["top"] - anterior["top"]) / paso))
            if anterior is not None and paso
            else 0
        )
        continua = resultado and not resultado[-1]["texto"].endswith(
            (".", "?", "!", ":")
        )
        if resultado and es_codigo and anterior_codigo and 1 <= saltos <= 2:
            # las lineas en blanco de dentro de un ejemplo se conservan
            resultado[-1]["texto"] += "\n" * saltos + l["text"]
        elif (
            resultado
            and (l["x0"] > margen + 5 or continua)
            and not anterior_codigo
            and not es_codigo
        ):
            if resultado[-1]["texto"].endswith("-"):
                resultado[-1]["texto"] = resultado[-1]["texto"][:-1] + l["text"]
            else:
                resultado[-1]["texto"] += " " + l["text"]
        else:
            resultado.append(
                {
                    "tipo": "codigo" if es_codigo else "parrafo",
                    "texto": l["text"],
                    "top": l["top"],
                }
            )
        anterior = l

    return resultado


def cargar_voz():

    return PiperVoice.load("en_US-lessac-medium.onnx")


def hablar(voz, textolimpio):
    """habla piper"""
    with wave.open("salida.wav", "wb") as r:
        voz.synthesize_wav(textolimpio, r)
    subprocess.run(["aplay", "salida.wav"])


def pintar(parrafos, actual):
    """redibuja el texto dejando el parrafo actual abajo del todo"""
    ancho, alto = shutil.get_terminal_size()
    bloques = []
    usado = 0
    for i in range(actual, -1, -1):
        lineas = textwrap.wrap(parrafos[i], ancho) or [""]
        if usado + len(lineas) > alto - 1 and bloques:
            break
        if i == actual:
            lineas = [f"\033[93m{l}\033[0m" for l in lineas]
        bloques.insert(0, "\n".join(lineas))
        usado += len(lineas)
    print("\033[3J\033[2J\033[H", end="", flush=True)
    print("\n" * (alto - 1 - usado), end="")
    print("\n".join(bloques), flush=True)

def a_html(bloques, por_pagina=40):
    """monta el cuerpo del html, repartido en paginas

    cada bloque que se puede leer en voz alta lleva su numero: es el que
    el navegador le pide al servidor para que piper lo sintetice, y el
    que se guarda como marcador.
    """
    paginas = []
    for i, bloque in enumerate(bloques):
        if i % por_pagina == 0:
            paginas.append([])
        tipo = bloque["tipo"]
        txt = html.escape(bloque["texto"])
        if tipo == "imagen":
            paginas[-1].append(f'<img src="{txt}" alt="figura">')
        elif tipo == "parrafo":
            paginas[-1].append(f'<p id="b{i}" data-i="{i}">{txt}</p>')
        else:
            paginas[-1].append(f'<pre id="b{i}" data-i="{i}">{txt}</pre>')
    return "\n".join(
        '<section class="pagina" data-pagina="%d">\n%s\n</section>'
        % (n, "\n".join(p))
        for n, p in enumerate(paginas)
    )


def documento_lectura(cuerpo, titulo="Lector"):
    """envuelve los bloques en la pagina de lectura

    la plantilla no es una f-string porque el css y el javascript van
    llenos de llaves y habria que doblarlas todas.
    """
    return PLANTILLA.replace("@TITULO@", html.escape(titulo)).replace(
        "<!--CUERPO-->", cuerpo
    )


def generar_html(ruta, salida, inicio=0, carpeta="figuras", titulo=None):
    """vuelca el libro entero a un html local con sus figuras

    las figuras se guardan en una carpeta al lado del html, para que el
    src de cada imagen sea una ruta corta y el libro entero se pueda
    mover de sitio de una pieza.
    """
    destino = os.path.join(os.path.dirname(salida) or ".", carpeta)
    os.makedirs(destino, exist_ok=True)
    bloques = []
    for n, (page, lineas) in enumerate(read_document(ruta, inicio), inicio):
        cajas = estirar_cajas(cajas_de_figuras(page), lineas, fuentes_mono(lineas))
        pagina = limpiar(lineas, cajas)
        for i, caja in enumerate(cajas):
            nombre = "p%03d_%d.png" % (n, i)
            rasterizar(page, caja, os.path.join(destino, nombre))
            pagina.append(
                {"tipo": "imagen", "texto": carpeta + "/" + nombre, "top": caja[1]}
            )
        # la figura tiene que quedar donde estaba, no al final de la pagina
        pagina.sort(key=lambda b: b["top"])
        bloques.extend(pagina)
    if titulo is None:
        titulo = os.path.splitext(os.path.basename(ruta))[0]
    with open(salida, "w", encoding="utf-8") as f:
        f.write(documento_lectura(a_html(bloques), titulo))
    return bloques


def main():
    """lee el libro en voz alta resaltando el parrafo actual"""
    voz = cargar_voz()
    for page, lineas in read_document(RUTA_DE_DOCUMENTO, PAGINA_INICIAL):
        bloques = limpiar(
            lineas,
            estirar_cajas(cajas_de_figuras(page), lineas, fuentes_mono(lineas)),
        )
        parrafos = [b["texto"] for b in bloques]
        for i, p in enumerate(parrafos):
            pintar(parrafos, i)
            hablar(voz, p)


if __name__ == "__main__":
    main()
