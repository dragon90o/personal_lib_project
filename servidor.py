"""servidor local del lector

al arrancar ensena la biblioteca para que elijas, o le pasas un pdf
nuevo y lo prepara. mientras esta en marcha va sintetizando con piper el
parrafo que el navegador le pide: el mismo camino que hacia hablar() en
la terminal (generar el wav, sonar, tirarlo), solo que ahora el wav no
toca el disco, va y viene en memoria.

    python servidor.py                    -> ensena la biblioteca
    python servidor.py libro.pdf          -> ese, desde la primera pagina
    python servidor.py libro.pdf 26       -> saltandose el indice
    python servidor.py libro.pdf 26 -r    -> rehaciendo el html
"""

import io
import os
import sys
import wave
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler

from piper import PiperVoice

from lib_pro import generar_html

PUERTO = 8765
MODELO = "en_US-lessac-medium.onnx"
BIBLIOTECA = "libros"
# volver atras un parrafo no deberia costar otra sintesis
CACHE = {}
LIMITE = 400


def biblioteca():
    """los libros ya preparados, por orden alfabetico"""
    if not os.path.isdir(BIBLIOTECA):
        return []
    return sorted(
        nombre
        for nombre in os.listdir(BIBLIOTECA)
        if os.path.isfile(os.path.join(BIBLIOTECA, nombre, "index.html"))
    )


def limpiar_ruta(texto):
    """al arrastrar el fichero a la terminal vienen comillas pegadas"""
    return texto.strip().strip('"').strip("'")


def pedir_pdf(pdf):
    """insiste hasta que la ruta sea un fichero de verdad"""
    while not os.path.isfile(pdf):
        if pdf:
            print("no encuentro %r" % pdf)
        pdf = limpiar_ruta(input("ruta del pdf: "))
        if not pdf:
            sys.exit("sin libro no hay nada que leer")
    return pdf


def pedir_pagina():
    pagina = input("empezar en la pagina [1]: ").strip()
    return max(0, int(pagina) - 1) if pagina else 0


def preguntar_libro(argumentos):
    """devuelve (pdf, nombre, inicio, rehacer)

    con pdf a None es un libro que ya esta preparado y solo hay que
    abrirlo; con nombre a None es un pdf nuevo que hay que procesar.
    """
    rehacer = "-r" in argumentos
    argumentos = [a for a in argumentos if a != "-r"]
    if argumentos:
        pdf = pedir_pdf(argumentos[0])
        inicio = max(0, int(argumentos[1]) - 1) if len(argumentos) > 1 else 0
        return pdf, None, inicio, rehacer

    estanteria = biblioteca()
    if estanteria:
        print("en la biblioteca:")
        for i, nombre in enumerate(estanteria, 1):
            print("  %d) %s" % (i, nombre))
        respuesta = limpiar_ruta(input("numero, o ruta de un pdf nuevo: "))
        if respuesta.isdigit() and 1 <= int(respuesta) <= len(estanteria):
            return None, estanteria[int(respuesta) - 1], 0, rehacer
        pdf = pedir_pdf(respuesta)
    else:
        pdf = pedir_pdf("")
    return pdf, None, pedir_pagina(), rehacer


def preparar(pdf, nombre, inicio, rehacer):
    """deja el libro listo en libros/<nombre>/ y devuelve su url"""
    if nombre is None:
        nombre = os.path.splitext(os.path.basename(pdf))[0]
    carpeta = os.path.join(BIBLIOTECA, nombre)
    salida = os.path.join(carpeta, "index.html")
    if pdf is None:
        # elegido de la estanteria: ya esta hecho, solo hay que abrirlo
        if rehacer:
            print("para rehacer %s hace falta el pdf" % nombre)
    elif rehacer or not os.path.isfile(salida):
        os.makedirs(carpeta, exist_ok=True)
        print("preparando %s ..." % nombre)
        bloques = generar_html(pdf, salida, inicio, titulo=nombre)
        print("  %d bloques" % len(bloques))
    else:
        print("%s ya estaba preparado (-r para rehacerlo)" % nombre)
    return "http://localhost:%d/%s/%s/index.html" % (PUERTO, BIBLIOTECA, nombre)


def sintetizar(voz, texto):
    """devuelve el wav del texto, ya listo para mandar al navegador"""
    if texto in CACHE:
        return CACHE[texto]
    memoria = io.BytesIO()
    with wave.open(memoria, "wb") as w:
        voz.synthesize_wav(texto, w)
    datos = memoria.getvalue()
    if len(CACHE) > LIMITE:
        CACHE.clear()
    CACHE[texto] = datos
    return datos


class Lector(SimpleHTTPRequestHandler):
    voz = None

    def do_POST(self):
        if self.path.split("?")[0] != "/tts":
            self.send_error(404)
            return
        largo = int(self.headers.get("Content-Length", 0))
        texto = self.rfile.read(largo).decode("utf-8").strip()
        if not texto:
            self.send_error(400, "sin texto")
            return
        try:
            datos = sintetizar(self.voz, texto)
        except Exception as e:  # que el navegador vea el motivo
            self.send_error(500, str(e))
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def log_message(self, *args):
        pass


def main():
    pdf, nombre, inicio, rehacer = preguntar_libro(sys.argv[1:])
    url = preparar(pdf, nombre, inicio, rehacer)
    print("cargando %s ..." % MODELO)
    Lector.voz = PiperVoice.load(MODELO)
    print("lector en %s   (ctrl-c para parar)" % url)
    webbrowser.open(url)
    servidor = HTTPServer(("127.0.0.1", PUERTO), Lector)
    try:
        servidor.serve_forever()
    finally:
        # sin esto el puerto se queda cogido y el siguiente arranque falla
        servidor.server_close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # ctrl-c es la forma normal de cerrar esto, no un error que
        # merezca vomitar el traceback entero por pantalla
        print("\nhasta luego")
        sys.exit(0)
