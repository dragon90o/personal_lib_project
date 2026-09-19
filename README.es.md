*[Read in English](README.md)*

# Lector de libros

Mi lector personal para estudiar: coge un PDF, lo limpia y lo convierte en una
página web local que se lee sola en voz alta con [Piper](https://github.com/rhasspy/piper),
resaltando el párrafo que suena en cada momento.

La regla del proyecto es **no perder contenido**. Si se come una fórmula, un
diagrama o un bloque de código, pierdo información de estudio. Fidelidad por
encima de elegancia.

## Qué hace

- Extrae el texto del PDF y separa la prosa del código, sin mezclarlos.
- Conserva la sangría del código, que en Python es sintaxis.
- Rasteriza los diagramas, que en muchos libros no son imágenes sino trazos
  vectoriales que `page.images` ni siquiera ve.
- Entiende libros a una columna, libros con notas al margen y papers a dos.
- Lee en voz alta con Piper, párrafo a párrafo, resaltando el actual.
- Controles de audio, tamaño de letra y ancho de columna.
- Guarda por dónde ibas en cada libro.

## Requisitos

- Python 3.9 o posterior
- [pdfplumber](https://github.com/jsvine/pdfplumber) para leer el PDF
- [piper-tts](https://github.com/rhasspy/piper) para la síntesis de voz
- Un modelo de voz de Piper por idioma (61 MB cada uno, no van en el repo)

## Instalación

Hace falta Python 3 y un entorno virtual:

```
python -m venv venv
venv/Scripts/activate        # en Linux: source venv/bin/activate
pip install -r requirements.txt
```

Y un modelo de voz por idioma:

```
V=https://huggingface.co/rhasspy/piper-voices/resolve/main
curl -LO $V/en/en_US/lessac/medium/en_US-lessac-medium.onnx
curl -LO $V/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
curl -LO $V/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx
curl -LO $V/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json
```

El idioma de cada libro se detecta solo al prepararlo y se guarda en el
`<html lang>` de su `index.html`, así que al abrirlo desde la estantería el
servidor ya sabe con qué voz leerlo. Si falta el modelo, te dice el `curl` que
lo baja y mientras tanto lee con el inglés.

## Uso

```
python server.py
```

Enseña los libros que ya tienes preparados y te deja elegir, o le das la ruta de
un PDF nuevo y lo procesa. También directo:

```
python server.py libro.pdf 26     # empezando en la pagina 26, saltando el indice
python server.py libro.pdf 26 -r  # rehaciendo el html
```

El servidor imprime una dirección `http://localhost:8765/...` para abrir en el
navegador. Barra espaciadora para leer y pausar, flechas para moverse de
párrafo, PageUp/PageDown para cambiar de página, y clic en cualquier párrafo
para empezar a leer justo ahí.

Cada libro queda en `books/<nombre>/` con su `index.html` y sus figuras al lado,
así que se puede copiar a otro ordenador de una pieza. Una vez procesado, el PDF
ya no hace falta para leer (solo para volver a generarlo).

## Cómo funciona

```
PDF ──> read_document() ──> clean() ──> to_html() ──> books/<nombre>/index.html
        parte las columnas, bloques de  una sección             │
        quita la cabecera   prosa y     por página del PDF      │
                            código,                              v
                            figuras            server.py ──> Piper ──> wav
```

`server.py` sirve esa página y sintetiza bajo demanda: el navegador manda por
POST el texto de un párrafo a `/tts` y el servidor devuelve el WAV. El recorrido
etapa por etapa está en [ARCHITECTURE.md](ARCHITECTURE.md) (en inglés).

## Ficheros

| | |
|---|---|
| `book.py` | extracción, limpieza y montaje del HTML |
| `fontmap.py` | descifrado de la fuente rota (ver abajo) |
| `template.py` | la página de lectura: maquetación, controles y marcador |
| `server.py` | sirve la página, elige la voz y sintetiza con Piper |
| `tests.py` | comprobaciones del margen, la paginación y el idioma |
| `books/` | una carpeta por libro procesado (no va en el repo) |

Todo está en inglés: los nombres, los ficheros, los comentarios, la
documentación y la interfaz del lector, para que cualquiera pueda colaborar.
Antes de mandar un pull request, mira [CONTRIBUTING.md](CONTRIBUTING.md).

## Tests

```
python tests.py
```

Va imprimiendo cada comprobación y para en el primer `assert` que falle. La 5
necesita un libro ya procesado en `books/`, y si no lo hay avisa y sigue; las
demás se construyen sus propias páginas y corren en cualquier sitio.

## Cosas que aprendí por el camino

Casi todo el trabajo está en lo que el PDF **no** te da bien:

**La fuente del código puede estar rota.** ThinkPython.pdf lo generó LaTeX +
Ghostscript 9.25, y su fuente monoespaciada es un Type3 sin nombre, o sea sin
encoding estándar. pdfminer, poppler y mupdf caen todos al glyph-list de
ZapfDingbats, así que `>>> print` se extrae como `❃❃❃ ♣r✐♥t`. No es culpa de
pdfplumber: `pdftotext` y `mutool` fallan igual. Es una sustitución
monoalfabética consistente, y la tabla se dedujo con texto conocido (las 31
palabras clave de Python, los mensajes de error). No depende del libro: es
siempre el mismo fallback de pdfminer.

**Clasificar por el nombre de la fuente no vale.** Se mira la anchura: en
monoespaciada todos los caracteres miden igual, en prosa no. Así funciona tanto
con el PDF roto como con uno sano. Y no basta con mirar el primer carácter de la
línea, porque hay prosa que empieza con una palabra en fuente de código; se usa
el porcentaje, con umbral del 0.9.

**Las comillas se dibujan más altas que el resto del renglón** y
`extract_text_lines` las devuelve en una línea aparte: 435 líneas y 1339
comillas en este libro. Descartarlas se llevaba por delante las cadenas de todos
los ejemplos (`print 'Hello, World!'` quedaba en `print Hello, World!`). Hay que
volver a meterlas en su sitio por su posición horizontal.

**Los diagramas son vectoriales.** En las 240 páginas hay una sola imagen
embebida y en cambio 253 curvas y 217 rects. Se localiza la región y se
rasteriza con `page.crop(bbox).to_image()`. Y el bbox de los trazos no incluye
las etiquetas de texto, así que hay que estirarlo o salen cortadas por la mitad.

**Las columnas hay que separarlas antes de sacar las líneas.** Los apuntes de la
IU llevan las palabras clave en una columna propia al lado del cuerpo.
`extract_text_lines` no la ve como columna: junta la nota y el renglón del cuerpo
en una sola línea, y salía `auf Sympathien Logik Der Begriff bezeichnet für
einzelne Politiker:innen zurück`. Descartar la línea después no sirve, porque la
nota y el cuerpo van dentro del mismo objeto.

La columna se encuentra proyectando las palabras sobre el eje x y buscando la
franja más ancha por la que no pasa ninguna. Dentro de un párrafo no hay hueco
que valga: con treinta renglones encima, cualquier `x` de la mancha la tapa
alguna palabra. Medido en este libro, las páginas de una sola columna dan 0 o
3 pt, las que llevan nota al margen dan 11 o 12, y el canal del número de página
del pie da 54. Con dos precauciones: con poca palabra en la página no se parte
nada, y si a los dos lados hay texto de sobra tampoco, porque entonces no es una
nota sino la página entera.

Después, cada columna se junta por su lado. Mezcladas no se junta ninguna: cada
renglón del cuerpo lleva una nota detrás y ninguno llega a tocar al siguiente.
Y dentro de la columna de notas, dos notas seguidas se separan por el hueco
vertical o, si van pegadas, por el título en negrita.

**Un paper a dos columnas es el caso opuesto.** Ahí las dos columnas son
cuerpo, repartidas mitad y mitad, que es justo la forma que el detector de notas
al margen descarta a propósito. Se decide sobre el documento entero y no página
a página, porque la primera de un paper no tiene forma de dos columnas: media
página es título, autores y abstract a lo ancho. Y un solo corte por página
tampoco basta, porque una misma página puede llevar el título de lado a lado,
debajo el abstract a dos columnas con el canal muy a la izquierda, y al final el
cuerpo a dos columnas centradas. La página se parte en tramos, cada uno con su
canal.

**El margen izquierdo tampoco es el mínimo.** Se calculaba con `min(x0)`, así
que una línea suelta más a la izquierda hacía que *todas* las demás pareciesen
sangradas y se pegasen al párrafo anterior. El margen de verdad es la `x0` que
más se repite.

**No todos los libros tienen título corrido.** El recorte de la cabecera era
`words[0]["bottom"] + 2`: fuera el primer renglón de cada página, sin
preguntar. En ThinkPython acierta, porque ahí hay un título corrido en las 240
páginas. Estos apuntes no llevan ninguno, así que se comía el título de cada
sección (`1.2 Was ist wahr?`), el `LEKTION 2` que abre cada capítulo y los
títulos de las notas al margen. Por la forma no se distinguen: un título de
sección también es un renglón corto y separado del cuerpo. Lo que solo hace la
cabecera es **repetirse**, así que se mira el primer renglón de todas las
páginas y solo se recorta si es el mismo en al menos el 40 %. Las cifras se
tapan antes de comparar, y cada tirada con una sola marca: si no, `página 9` y
`página 10` salen distintas y la cabecera se parte en dos mitades, ninguna de
las cuales llega al mínimo.

**Los títulos van en otra fuente.** Un subtítulo en negrita se pegaba al párrafo
de debajo (`Alltagswissen und Wissenschaft Das Alltagswissen beruht auf
Erfahrungen...`). Se detectan comparando la fuente dominante del renglón con la
del cuerpo, y salen en su propio bloque, como `<h3>`. En la columna de notas la
regla se invierte: ahí el título es el término que se define y tiene que
quedarse pegado a su definición.

**El número de página lo pone pdfplumber.** Enumerando lo que va saliendo no
vale: `read_document` se salta las páginas sin texto, y a partir de la primera
en blanco todas las demás quedaban corridas un número.

**Una sección por página del PDF.** El HTML se repartía de 40 en 40 bloques, así
que el número de página del lector no tenía nada que ver con el del libro: un
libro de 142 páginas se abría en 16 y parecía que faltaba contenido. Ahora cada
sección es la página que era y `data-page` lleva el número impreso.

## Limitaciones

- Solo hay voz de inglés y de alemán; para otro idioma hay que añadirlo a
  `VOICES` en `book.py` y bajar el modelo.
- Un libro escrito en dos idiomas se lee entero con la voz del que más pese.
- Los pies de figura quedan dentro del PNG y no se leen en voz alta.
- Probado a fondo con apenas un puñado de documentos.

## Contribuir

Los issues y los pull requests son bienvenidos.
[CONTRIBUTING.md](CONTRIBUTING.md) explica cómo montar el proyecto, qué
convenciones sigue el código y qué tipo de cambio es más útil. Si tienes un PDF
que este lector destroza, eso es un buen issue: cuenta qué salió y qué debería
haber salido.

## Licencia

[MIT](LICENSE) © dragon90o
