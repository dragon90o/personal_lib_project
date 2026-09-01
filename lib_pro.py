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

# una voz por idioma: leer aleman con la voz inglesa sale a media lengua,
# que piper pronuncia con la fonetica del modelo, no con la del texto.
VOCES = {
    "en": "en_US-lessac-medium.onnx",
    "de": "de_DE-thorsten-medium.onnx",
}
VOZ_POR_DEFECTO = "en"

# palabras vacias con las que se adivina el idioma. van sin acentos ni
# umlauts a proposito: no todos los pdf los sacan bien, y estas palabras
# tienen que seguir contando aunque el resto del texto venga sucio.
PALABRAS = {
    "de": set("""der die das und ist nicht auch werden eine sich dem den des
             ein einer im zu auf als wird kann bei nach oder aber diese
             durch sind wie man bereits jedoch sowie zum zur""".split()),
    "en": set("""the and of to is not are that with this for from have has
             was were will can be an it on at by as their which such
             about into these than""".split()),
}


def hueco_de_columnas(palabras, ancho, minimo=8, bastantes=40, sobra=0.3):
    """la franja vertical vacia que separa el cuerpo de las notas

    los apuntes de la IU llevan las palabras clave en una columna propia
    al lado del cuerpo. extract_text_lines() no la ve como columna: junta
    la nota y el renglon del cuerpo en una sola linea, y de ahi salia
    "auf Sympathien Logik Der Begriff bezeichnet fuer einzelne
    Politiker:innen zurueck". no basta con descartar la linea despues:
    hay que recortar cada columna por separado ANTES de sacar las lineas.

    se proyectan todas las palabras sobre el eje x y se busca la franja
    mas ancha por la que no pasa ninguna. dentro de un parrafo no hay
    hueco que valga: con treinta renglones encima, cualquier x de la
    mancha la tapa alguna palabra. medido en este libro, las paginas de
    una sola columna dan 0 o 3 pt y las que llevan nota al margen dan 11
    o 12; el canal del numero de pagina del pie da 54.

    dos precauciones para no partir una pagina que no toca: con poco
    texto un hueco casual es facil, y una columna de verdad se lleva
    solo un puñado de palabras. si a los dos lados hay texto de sobra,
    no es una nota al margen sino la pagina entera y se deja como esta.
    """
    if len(palabras) < bastantes:
        return None
    ocupado = [False] * (int(ancho) + 2)
    for w in palabras:
        for x in range(int(w["x0"]), min(int(w["x1"]) + 1, len(ocupado))):
            ocupado[x] = True
    if True not in ocupado:
        return None
    # los margenes de la pagina tambien estan vacios y no separan nada
    primero = ocupado.index(True)
    ultimo = len(ocupado) - 1 - ocupado[::-1].index(True)
    mejor, x = None, primero
    while x <= ultimo:
        if ocupado[x]:
            x += 1
            continue
        fin = x
        while fin <= ultimo and not ocupado[fin]:
            fin += 1
        if mejor is None or fin - x > mejor[1] - mejor[0]:
            mejor = (x, fin)
        x = fin
    if mejor is None or mejor[1] - mejor[0] < minimo:
        return None
    corte = (mejor[0] + mejor[1]) / 2
    menor = min(
        sum(1 for w in palabras if w["x1"] <= corte),
        sum(1 for w in palabras if w["x0"] >= corte),
    )
    return None if menor > len(palabras) * sobra else corte


def sin_cifras(texto):
    """el texto con los numeros tapados

    una cabecera corrida del tipo "Capitulo 3, pagina 41" cambia en cada
    pagina y sigue siendo la misma cabecera. cada tirada de cifras se
    tapa con una sola marca: si no, "pagina 9" y "pagina 10" salen
    distintas y la cabecera se parte en dos mitades, ninguna de las
    cuales llega al minimo para que se la reconozca.
    """
    fuera = []
    for c in texto:
        if not c.isdigit():
            fuera.append(c)
        elif not fuera or fuera[-1] != "#":
            fuera.append("#")
    return "".join(fuera)


def primer_renglon(page, banda=0.25):
    """el renglon de mas arriba de la pagina, si hay alguno"""
    alto = page.crop((0, 0, page.width, page.height * banda))
    lineas = alto.extract_text_lines(x_tolerance=1.5)
    return lineas[0] if lineas else None


def titulo_corrido(paginas, minimo=0.4):
    """el renglon que se repite arriba de casi todas las paginas

    ThinkPython lleva un titulo corrido en las 240 paginas y hay que
    quitarlo. estos apuntes no llevan ninguno, y recortar el primer
    renglon a ciegas se comia el titulo de cada seccion ("1.2 Was ist
    wahr?"), el "LEKTION 2" que abre cada capitulo y los titulos de las
    notas al margen. por la forma no se distinguen: un titulo de seccion
    tambien es un renglon corto y separado del cuerpo. lo que solo hace
    la cabecera es repetirse.
    """
    cuenta = {}
    for page in paginas:
        renglon = primer_renglon(page)
        if renglon:
            clave = sin_cifras(renglon["text"])
            cuenta[clave] = cuenta.get(clave, 0) + 1
    if not cuenta:
        return None
    texto = max(cuenta, key=cuenta.get)
    return texto if cuenta[texto] >= len(paginas) * minimo else None


def read_document(ruta, inicio=0):
    """va soltando (pagina, lineas) de cada pagina del libro

    cada linea sale marcada con si es del cuerpo o de una nota al
    margen, que es algo que solo se sabe aqui: mas abajo ya no queda
    rastro de en que columna estaba.
    """
    with pdfplumber.open(ruta) as r:
        cabecera = titulo_corrido(r.pages[inicio:])
        for page in r.pages[inicio:]:
            palabras = page.extract_words()
            if not palabras:
                continue
            # solo se recorta si arriba hay de verdad una cabecera
            # corrida; si no, ese renglon es el titulo de la seccion
            arriba = 0
            if cabecera:
                renglon = primer_renglon(page)
                if renglon and sin_cifras(renglon["text"]) == cabecera:
                    arriba = renglon["bottom"] + 2
            cuerpo = [w for w in palabras if w["bottom"] > arriba]
            if not cuerpo:
                continue
            def renglones(x0, x1, nota):
                recorte = page.crop((x0, arriba, x1, page.height))
                lineas = recorte.extract_text_lines(x_tolerance=1.5)
                for l in lineas:
                    l["nota"] = nota
                return lineas

            corte = hueco_de_columnas(cuerpo, page.width)
            if corte is None:
                texto_del_libro = renglones(0, page.width, False)
            else:
                # de las dos columnas, el cuerpo es la que trae el texto;
                # la nota al margen cabe en cuatro renglones sueltos
                a_la_izquierda = sum(1 for w in cuerpo if w["x1"] <= corte)
                cuerpo_izquierda = a_la_izquierda * 2 >= len(cuerpo)
                texto_del_libro = renglones(0, corte, not cuerpo_izquierda)
                texto_del_libro += renglones(corte, page.width, cuerpo_izquierda)
            # el orden de lectura es de arriba abajo y, a igual altura,
            # de izquierda a derecha
            texto_del_libro.sort(key=lambda l: (round(l["top"]), l["x0"]))

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


def margen_cuerpo(lineas, tolerancia=2):
    """el margen izquierdo del cuerpo del texto, sin contar las notas

    no vale el minimo. los apuntes de la IU llevan una columna de notas
    al margen a la izquierda del cuerpo, y bastaba una nota suelta para
    que TODAS las lineas de la pagina parecieran sangradas y se pegaran
    al parrafo de antes: las 142 paginas del libro aleman salian en 489
    parrafos, con parrafos de 3.383 caracteres. el margen de verdad es
    la x0 que mas se repite, que es por donde empieza el cuerpo.
    """
    grupos = {}
    for l in lineas:
        grupos.setdefault(round(l["x0"] / tolerancia), []).append(l["x0"])
    if not grupos:
        return 0
    # en empate gana el mas a la izquierda, que es el margen y no una sangria
    return min(max(grupos.values(), key=lambda g: (len(g), -min(g))))


def detectar_idioma(bloques, por_defecto=VOZ_POR_DEFECTO):
    """adivina el idioma del libro contando palabras vacias

    el titulo no sirve (este libro se llama "Einfuehrung..." pero podria
    llamarse "IU DLBWIRITT01") y el pdf no trae metadato fiable, asi que
    se mira el texto: las palabras vacias son las que mas se repiten y no
    se solapan entre idiomas.
    """
    palabras = []
    for b in bloques:
        if b["tipo"] == "parrafo":
            palabras.extend(b["texto"].lower().split())
    if not palabras:
        return por_defecto
    limpio = [w.strip(".,;:()[]“”\"'!?") for w in palabras]
    cuenta = {
        idioma: sum(1 for w in limpio if w in vacias)
        for idioma, vacias in PALABRAS.items()
    }
    ganador = max(cuenta, key=cuenta.get)
    # con cuatro palabras sueltas no hay nada que decidir
    return ganador if cuenta[ganador] > len(limpio) * 0.02 else por_defecto


def limpiar(texto, cajas=()):
    """limpia el texto de ascii y lo junta en bloques de prosa y codigo"""
    for linea in texto:
        linea["text"] = traducir(linea["text"], ta)
    # las etiquetas de los diagramas ya salen dentro del png de la figura
    buenas = [l for l in pegar_comillas(texto) if not dentro(l, cajas)]
    if not buenas:
        return []
    mono = fuentes_mono(buenas)
    for l in buenas:
        # mirar solo el primer caracter falla con las frases que empiezan
        # por una palabra en fuente de codigo ("76trombones is illegal...")
        raros = sum(1 for c in l["chars"] if c["fontname"] in mono)
        # una linea de codigo de verdad es 100% monoespaciada; la prosa con
        # nombres de variable dentro no pasa del 70%
        l["codigo"] = raros > len(l["chars"]) * 0.9

    # el margen se saca de la prosa: en una pagina de puro codigo la x0
    # que mas manda es la sangria del bloque, no el margen de la pagina
    prosa = [l for l in buenas if not l["codigo"]]
    margen = margen_cuerpo(prosa or buenas)

    # los apuntes llevan palabras clave en una columna propia a la
    # izquierda del cuerpo. hay que leerlas, que son parte del libro,
    # pero no son la frase de al lado: pegadas al cuerpo salia
    # "Monografie Hier wird also nur ein Thema beleuchtet."
    for l in buenas:
        l["nota"] = l.get("nota", not l["codigo"] and l["x1"] < margen)

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

    cuerpo = [l for l in buenas if not l["nota"]]
    # el numero de pagina del pie cae en la misma columna que las notas.
    # es lo unico que se tira del libro entero: no es contenido, y suelto
    # en su bloque piper lo cantaria en las 138 paginas
    notas = [l for l in buenas if l["nota"] and not l["text"].strip().isdigit()]
    # el titulo de cada nota va en otra fuente que su texto (negrita), y
    # cuando dos notas van seguidas sin hueco es lo unico que las separa
    for grupo in (cuerpo, notas):
        # el cuerpo va todo en la misma fuente y los titulos en otra
        # (negrita). el codigo se deja fuera de la cuenta, que tiene
        # fuente propia y arrastraria la mayoria en una pagina de puro
        # ejemplo
        prosa_del_grupo = [l for l in grupo if not l["codigo"]]
        corriente = fuente_principal(
            [c for l in prosa_del_grupo for c in l["chars"]]
        )
        for l in grupo:
            l["titulo"] = (
                not l["codigo"] and fuente_principal(l["chars"]) != corriente
            )
    bloques = juntar(cuerpo, margen, paso, titulo_solo=True)
    # las notas se juntan por separado y se rompen por el hueco vertical,
    # que estando todas en la misma columna es lo unico que las separa
    bloques += juntar(notas, margen, paso, interlineado(notas) * 1.8)
    # cada nota se queda a la altura del parrafo que anota
    return sorted(bloques, key=lambda b: b["top"])


def nuevo_bloque(tipo, linea):
    return {"tipo": tipo, "texto": linea["text"], "top": linea["top"]}


def juntar(lineas, margen, paso, hueco=0, titulo_solo=False):
    """pega los renglones sueltos en bloques de prosa y de codigo

    va por una sola columna: el cuerpo o las notas al margen, nunca los
    dos mezclados. si se le pasan mezclados, cada renglon del cuerpo
    lleva una nota detras y no se junta con nada.

    titulo_solo dice que hacer con los renglones en otra fuente. en el
    cuerpo son titulos de seccion y van en su propio bloque, que si no
    salia "Alltagswissen und Wissenschaft Das Alltagswissen beruht auf
    Erfahrungen...". en la columna de notas, en cambio, el titulo es el
    termino que se define y tiene que quedarse con su definicion.
    """
    resultado = []
    anterior = None
    for l in lineas:
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
        # dos cosas cortan un bloque aunque la sangria diga que sigue:
        # un hueco vertical grande, y un titulo. hacen falta las dos
        # porque en una pagina puede haber tres notas al margen, todas
        # en la misma columna, y las hay pegadas sin hueco en medio.
        es_titulo = l.get("titulo", False)
        aparte = (
            es_titulo
            or (titulo_solo and anterior is not None and anterior.get("titulo"))
            or (
                bool(hueco)
                and anterior is not None
                and l["top"] - anterior["top"] > hueco
            )
        )
        if resultado and es_codigo and anterior_codigo and 1 <= saltos <= 2:
            # las lineas en blanco de dentro de un ejemplo se conservan
            resultado[-1]["texto"] += "\n" * saltos + l["text"]
        elif (
            resultado
            and not aparte
            and (l["x0"] > margen + 5 or continua)
            and not anterior_codigo
            and not es_codigo
        ):
            if resultado[-1]["texto"].endswith("-"):
                resultado[-1]["texto"] = resultado[-1]["texto"][:-1] + l["text"]
            else:
                resultado[-1]["texto"] += " " + l["text"]
        elif es_codigo:
            resultado.append(nuevo_bloque("codigo", l))
        elif titulo_solo and es_titulo:
            resultado.append(nuevo_bloque("titulo", l))
        else:
            resultado.append(nuevo_bloque("parrafo", l))
        anterior = l

    return resultado


def cargar_voz(idioma=VOZ_POR_DEFECTO):

    return PiperVoice.load(VOCES.get(idioma, VOCES[VOZ_POR_DEFECTO]))


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

def a_html(bloques):
    """monta el cuerpo del html, una seccion por pagina del pdf

    antes se repartia de 40 en 40 bloques, y entonces el numero de
    pagina del lector no tenia nada que ver con el del libro: las 142
    paginas del libro aleman salian en 16 y parecia que faltaba medio
    libro. ahora cada seccion es la pagina que era.

    cada bloque que se puede leer en voz alta lleva su numero: es el que
    el navegador le pide al servidor para que piper lo sintetice, y el
    que se guarda como marcador.
    """
    paginas = []
    for i, bloque in enumerate(bloques):
        # los libros preparados antes de esto no traen pagina: caen
        # todos en la primera y el html sigue abriendose
        n = bloque.get("pagina", 1)
        if not paginas or paginas[-1][0] != n:
            paginas.append((n, []))
        tipo = bloque["tipo"]
        txt = html.escape(bloque["texto"])
        hueco = paginas[-1][1]
        if tipo == "imagen":
            hueco.append(f'<img src="{txt}" alt="figura">')
        elif tipo == "parrafo":
            hueco.append(f'<p id="b{i}" data-i="{i}">{txt}</p>')
        elif tipo == "titulo":
            hueco.append(f'<h3 id="b{i}" data-i="{i}">{txt}</h3>')
        else:
            hueco.append(f'<pre id="b{i}" data-i="{i}">{txt}</pre>')
    return "\n".join(
        '<section class="pagina" data-pagina="%d">\n%s\n</section>'
        % (n, "\n".join(p))
        for n, p in paginas
    )


def documento_lectura(cuerpo, titulo="Lector", idioma=VOZ_POR_DEFECTO):
    """envuelve los bloques en la pagina de lectura

    la plantilla no es una f-string porque el css y el javascript van
    llenos de llaves y habria que doblarlas todas.
    """
    return (
        PLANTILLA.replace("@TITULO@", html.escape(titulo))
        .replace("@IDIOMA@", html.escape(idioma))
        .replace("<!--CUERPO-->", cuerpo)
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
    for page, lineas in read_document(ruta, inicio):
        # el numero lo pone pdfplumber y cuenta desde 1, como el libro
        # impreso. no vale enumerar lo que va saliendo: read_document se
        # salta las paginas sin texto y a partir de la primera en blanco
        # todas las demas quedaban corridas un numero.
        n = page.page_number
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
        for b in pagina:
            b["pagina"] = n
        bloques.extend(pagina)
    if titulo is None:
        titulo = os.path.splitext(os.path.basename(ruta))[0]
    idioma = detectar_idioma(bloques)
    with open(salida, "w", encoding="utf-8") as f:
        f.write(documento_lectura(a_html(bloques), titulo, idioma))
    return bloques, idioma


def main():
    """lee el libro en voz alta resaltando el parrafo actual"""
    voz = None
    for page, lineas in read_document(RUTA_DE_DOCUMENTO, PAGINA_INICIAL):
        bloques = limpiar(
            lineas,
            estirar_cajas(cajas_de_figuras(page), lineas, fuentes_mono(lineas)),
        )
        if voz is None:
            # aqui se va pagina a pagina, asi que el idioma se decide con
            # la primera, que ya trae cientos de palabras. generar_html()
            # lo mira con el libro entero, que es donde importa acertar.
            voz = cargar_voz(detectar_idioma(bloques))
        parrafos = [b["texto"] for b in bloques]
        for i, p in enumerate(parrafos):
            pintar(parrafos, i)
            hablar(voz, p)


if __name__ == "__main__":
    main()
