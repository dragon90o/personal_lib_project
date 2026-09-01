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
import re
import sys
import wave
from http.server import HTTPServer, SimpleHTTPRequestHandler

from piper import PiperVoice

from lib_pro import VOCES, VOZ_POR_DEFECTO, generar_html

PUERTO = 8765
BIBLIOTECA = "libros"
# de aqui salen los modelos de voz, que pesan 61 MB y no van en el repo
VOCES_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
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
    """al arrastrar el fichero a la terminal vienen comillas pegadas

    el ~ lo expande la shell, pero lo que se teclea en un input() llega
    crudo: expanduser lo traduce al home (en windows, a %USERPROFILE%).
    """
    return os.path.expanduser(texto.strip().strip('"').strip("'"))


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
    """deja el libro listo en libros/<nombre>/ y devuelve (url, idioma)"""
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
        bloques, idioma = generar_html(pdf, salida, inicio, titulo=nombre)
        print("  %d bloques, en %s" % (len(bloques), idioma))
    else:
        print("%s ya estaba preparado (-r para rehacerlo)" % nombre)
    url = "http://localhost:%d/%s/%s/index.html" % (PUERTO, BIBLIOTECA, nombre)
    # se relee del html en vez de arrastrar la variable: asi da igual si
    # el libro se acaba de preparar o si ya estaba en la estanteria
    return url, idioma_de(salida)


def idioma_de(salida):
    """el idioma que se le detecto al libro cuando se preparo

    lo lleva puesto el propio html en <html lang>: al abrir un libro de
    la estanteria el pdf ya no tiene por que seguir en el disco, asi que
    no se puede volver a mirar el texto.
    """
    try:
        with open(salida, encoding="utf-8") as f:
            cabecera = f.read(500)
    except OSError:
        return VOZ_POR_DEFECTO
    encontrado = re.search(r'<html lang="([a-z]{2})"', cabecera)
    return encontrado.group(1) if encontrado else VOZ_POR_DEFECTO


def url_voz(modelo):
    """la direccion de la que se baja un modelo de piper

    el nombre del fichero ya lleva la ruta dentro: de_DE-thorsten-medium
    esta colgado de de/de_DE/thorsten/medium.
    """
    locale, nombre, calidad = modelo[: -len(".onnx")].split("-")
    return "%s/%s/%s/%s/%s/%s" % (
        VOCES_URL, locale.split("_")[0], locale, nombre, calidad, modelo
    )


def cargar_voz(idioma):
    """carga la voz del idioma del libro

    si falta el modelo se avisa con el comando para bajarlo y se sigue
    con la voz de por defecto: leer aleman con acento ingles es feo,
    pero es mejor que quedarse sin lector.
    """
    modelo = VOCES.get(idioma, VOCES[VOZ_POR_DEFECTO])
    if not os.path.isfile(modelo):
        print("falta la voz de %s (%s). para tenerla:" % (idioma, modelo))
        for fichero in (modelo, modelo + ".json"):
            print("  curl -LO %s" % url_voz(modelo).replace(modelo, fichero))
        modelo = VOCES[VOZ_POR_DEFECTO]
        print("mientras tanto leo con %s" % modelo)
    if not os.path.isfile(modelo):
        sys.exit("sin ninguna voz no hay nada que leer: baja %s" % modelo)
    print("cargando %s ..." % modelo)
    return PiperVoice.load(modelo)


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
        # "replace" y no reventar: el navegador manda utf-8 siempre, pero
        # si llega un byte suelto mas vale leer el parrafo con un simbolo
        # raro que cortarle la conexion al lector sin decir nada
        texto = self.rfile.read(largo).decode("utf-8", "replace").strip()
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
    url, idioma = preparar(pdf, nombre, inicio, rehacer)
    Lector.voz = cargar_voz(idioma)
    # abrir el navegador solo no es fiable: xdg-open depende del .desktop del
    # navegador por defecto, y hay entradas (Mullvad, por ejemplo) cuyo Exec
    # viene envuelto en un sh -c que se rompe al re-trocearlo.  Imprimir la
    # URL funciona en cualquier maquina.
    print()
    print("   %s" % url)
    print()
    print("(pega esa direccion en el navegador; ctrl-c para parar)")
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
