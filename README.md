*[Read in English](README.en.md)*

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
- Lee en voz alta con Piper, párrafo a párrafo, resaltando el actual.
- Controles de audio, tamaño de letra y ancho de columna.
- Guarda por dónde ibas en cada libro.

## Instalación

Hace falta Python 3 y un entorno virtual:

```
python -m venv venv
venv/Scripts/activate        # en Linux: source venv/bin/activate
pip install pdfplumber piper-tts
```

Y el modelo de voz (61 MB, no está en el repo):

```
B=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium
curl -O $B/en_US-lessac-medium.onnx
curl -O $B/en_US-lessac-medium.onnx.json
```

## Uso

```
python servidor.py
```

Enseña los libros que ya tienes preparados y te deja elegir, o le das la ruta de
un PDF nuevo y lo procesa. También directo:

```
python servidor.py libro.pdf 26     # empezando en la pagina 26, saltando el indice
python servidor.py libro.pdf 26 -r  # rehaciendo el html
```

Se abre el navegador solo. Barra espaciadora para leer y pausar, flechas para
moverse de párrafo, PageUp/PageDown para cambiar de página, y clic en cualquier
párrafo para empezar a leer justo ahí.

Cada libro queda en `libros/<nombre>/` con su `index.html` y sus figuras al lado,
así que se puede copiar a otro ordenador de una pieza. Una vez procesado, el PDF
ya no hace falta para leer (solo para volver a generarlo).

## Ficheros

| | |
|---|---|
| `lib_pro.py` | extracción, limpieza y montaje del HTML |
| `tabla.py` | descifrado de la fuente rota (ver abajo) |
| `plantilla.py` | la página de lectura: maquetación, controles y marcador |
| `servidor.py` | sirve la página y sintetiza con Piper bajo demanda |

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

## Limitaciones

- El modelo de voz es inglés, así que lee libros en inglés.
- Los pies de figura quedan dentro del PNG y no se leen en voz alta.
- Probado a fondo con un solo libro.
