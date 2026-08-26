*[Leer en español](README.md)*

# Book reader

My personal reader for studying: it takes a PDF, cleans it up and turns it into
a local web page that reads itself out loud with [Piper](https://github.com/rhasspy/piper),
highlighting the paragraph currently being spoken.

The rule of this project is **don't lose content**. If it swallows a formula, a
diagram or a code block, I lose study material. Fidelity over elegance.

## What it does

- Extracts the text from the PDF and keeps prose and code apart, without mixing them.
- Preserves code indentation, which in Python is syntax.
- Rasterizes diagrams, which in many books aren't images at all but vector
  strokes that `page.images` doesn't even see.
- Reads out loud with Piper, paragraph by paragraph, highlighting the current one.
- Audio controls, font size and column width.
- Remembers where you left off in each book.

## Install

You need Python 3 and a virtual environment:

```
python -m venv venv
venv/Scripts/activate        # on Linux: source venv/bin/activate
pip install pdfplumber piper-tts
```

And the voice model (61 MB, not in the repo):

```
B=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium
curl -O $B/en_US-lessac-medium.onnx
curl -O $B/en_US-lessac-medium.onnx.json
```

## Usage

```
python servidor.py
```

It lists the books you already have prepared and lets you pick one, or you give
it the path to a new PDF and it processes it. Also directly:

```
python servidor.py book.pdf 26     # starting at page 26, skipping the index
python servidor.py book.pdf 26 -r  # rebuilding the html
```

The browser opens on its own. Spacebar to read and pause, arrow keys to move
between paragraphs, PageUp/PageDown to change page, and click any paragraph to
start reading right there.

Each book ends up in `libros/<name>/` with its `index.html` and figures next to
it, so you can copy it to another machine in one piece. Once processed, the PDF
is no longer needed for reading (only to regenerate it).

## Files

| | |
|---|---|
| `lib_pro.py` | extraction, cleanup and HTML assembly |
| `tabla.py` | decoding of the broken font (see below) |
| `plantilla.py` | the reading page: layout, controls and bookmark |
| `servidor.py` | serves the page and synthesizes with Piper on demand |

## Things I learned along the way

Almost all the work is in what the PDF **doesn't** hand you cleanly:

**The code font can be broken.** ThinkPython.pdf was produced by LaTeX +
Ghostscript 9.25, and its monospaced font is an unnamed Type3, meaning no
standard encoding. pdfminer, poppler and mupdf all fall back to the ZapfDingbats
glyph list, so `>>> print` comes out as `❃❃❃ ♣r✐♥t`. It isn't pdfplumber's fault:
`pdftotext` and `mutool` fail the same way. It's a consistent monoalphabetic
substitution, and the table was worked out from known text (Python's 31
keywords, the error messages). It doesn't depend on the book: it's always the
same pdfminer fallback.

**Classifying by font name doesn't work.** Look at the width instead: in a
monospaced font every character measures the same, in prose they don't. That
works both with the broken PDF and with a healthy one. And looking at the first
character of the line isn't enough either, because some prose starts with a word
in the code font; a percentage is used, with a 0.9 threshold.

**Quotes are drawn higher than the rest of the line** and `extract_text_lines`
returns them as a separate line: 435 lines and 1339 quotes in this book.
Discarding them wiped out the strings in every code example (`print 'Hello,
World!'` became `print Hello, World!`). They have to be put back in place by
their horizontal position.

**Diagrams are vector art.** Across 240 pages there's a single embedded image,
against 253 curves and 217 rects. You locate the region and rasterize it with
`page.crop(bbox).to_image()`. And the bounding box of the strokes doesn't
include the text labels, so it has to be stretched or they come out cut in half.

## Limitations

- The voice model is English, so it reads books in English.
- Figure captions end up inside the PNG and aren't read out loud.
- Only thoroughly tested with one book.
