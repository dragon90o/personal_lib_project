"""lector de libros"""

import wave
import subprocess
import shutil
import textwrap
import pdfplumber
from piper import PiperVoice
from tabla import traducir, ta

RUTA_DE_DOCUMENTO = "/home/dravvt/Documentos/ThinkPython.pdf"
PAGINA_INICIAL = 25


def read_document(ruta, inicio=0):
    """coje el texto del libro y lo imprime"""
    with pdfplumber.open(ruta) as r:
        for page in r.pages[inicio:]:
            palabras = page.extract_words()
            if not palabras:
                continue
            recorte_pagina = page.crop(
                (0, palabras[0]["bottom"] + 2, page.width, page.height)
            )

            texto_del_libro = recorte_pagina.extract_text_lines(x_tolerance=1.5)

            yield texto_del_libro


def limpiar(texto):
    """limpia el texto de ascii"""
    buenas = []
    for linea in texto:
        traducido = traducir(linea["text"], ta)
        # las esquinas del marco que LaTeX dibuja alrededor de los bloques de
        # codigo salen como comillas sueltas: 435 lineas en el libro, ninguna
        # con contenido
        if all(c in "' " for c in traducido.strip()):
            continue
        linea["text"] = traducido
        buenas.append(linea)
    if not buenas:
        return []
    margen = min(l["x0"] for l in buenas)
    resultado = []
    anterior_codigo = False
    for l in buenas:
        # mirar solo el primer caracter falla con las frases que empiezan
        # por una palabra en fuente de codigo ("76trombones is illegal...")
        raros = sum(1 for c in l["chars"] if c["fontname"] == "unknown")
        # una linea de codigo de verdad es 100% fuente rota; la prosa con
        # nombres de variable dentro no pasa del 70%
        es_codigo = raros > len(l["chars"]) * 0.9
        continua = resultado and not resultado[-1]["texto"].endswith(
            (".", "?", "!", ":")
        )
        if (
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
                {"tipo": "codigo" if es_codigo else "parrafo", "texto": l["text"]}
            )
        anterior_codigo = es_codigo

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


def main():
    """lee el libro en voz alta resaltando el parrafo actual"""
    voz = cargar_voz()
    for lineas in read_document(RUTA_DE_DOCUMENTO, PAGINA_INICIAL):
        texto = limpiar(lineas)
        parrafos = texto.splitlines()
        for i, p in enumerate(parrafos):
            pintar(parrafos, i)
            hablar(voz, p)


if __name__ == "__main__":
    main()
