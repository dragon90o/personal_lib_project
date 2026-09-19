*[Leer en español](README.es.md)*

# Book reader

A personal reader for studying: it takes a PDF, cleans it up and turns it into a
local web page that reads itself out loud with
[Piper](https://github.com/rhasspy/piper), highlighting the paragraph currently
being spoken.

The rule of this project is **don't lose content**. If it swallows a formula, a
diagram or a code block, study material is lost. Fidelity over elegance.

## What it does

- Extracts the text from the PDF and keeps prose and code apart, without mixing them.
- Preserves code indentation, which in Python is syntax.
- Rasterizes diagrams, which in many books aren't images at all but vector
  strokes that `page.images` doesn't even see.
- Handles single-column books, books with margin notes, and two-column papers.
- Reads out loud with Piper, paragraph by paragraph, highlighting the current one.
- Audio controls, font size and column width.
- Remembers where you left off in each book.

## Requirements

- Python 3.9 or newer
- [pdfplumber](https://github.com/jsvine/pdfplumber) for reading the PDF
- [piper-tts](https://github.com/rhasspy/piper) for the speech synthesis
- One Piper voice model per language (61 MB each, not in the repo)

## Install

```
python -m venv venv
venv/Scripts/activate        # on Linux: source venv/bin/activate
pip install -r requirements.txt
```

And one voice model per language:

```
V=https://huggingface.co/rhasspy/piper-voices/resolve/main
curl -LO $V/en/en_US/lessac/medium/en_US-lessac-medium.onnx
curl -LO $V/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
curl -LO $V/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx
curl -LO $V/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json
```

Each book's language is detected when it is processed and stored in the
`<html lang>` of its `index.html`, so opening it from the shelf is enough for
the server to know which voice to read it with. If the model is missing it
prints the `curl` that fetches it and falls back to English meanwhile.

## Usage

```
python server.py
```

It lists the books you already have prepared and lets you pick one, or you give
it the path to a new PDF and it processes it. Also directly:

```
python server.py book.pdf 26     # starting at page 26, skipping the index
python server.py book.pdf 26 -r  # rebuilding the html
```

The server prints a `http://localhost:8765/...` URL to open in the browser.
Spacebar to read and pause, arrow keys to move between paragraphs,
PageUp/PageDown to change page, and click any paragraph to start reading right
there.

Each book ends up in `books/<name>/` with its `index.html` and figures next to
it, so you can copy it to another machine in one piece. Once processed, the PDF
is no longer needed for reading (only to regenerate it).

## How it works

```
PDF ──> read_document() ──> clean() ──> to_html() ──> books/<name>/index.html
        split the columns,  blocks of   one section              │
        drop the header     prose and   per PDF page             │
                            code,                                v
                            figures            server.py ──> Piper ──> wav
```

`server.py` serves that page and synthesizes on demand: the browser POSTs the
text of a paragraph to `/tts` and the server hands back a WAV. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the stage-by-stage walkthrough.

## Project layout

| | |
|---|---|
| `book.py` | extraction, cleanup and HTML assembly |
| `fontmap.py` | decoding of the broken font (see below) |
| `template.py` | the reading page: layout, controls and bookmark |
| `server.py` | serves the page, picks the voice and synthesizes with Piper |
| `tests.py` | checks on the margin, the pagination and the language |
| `books/` | one folder per processed book (not in the repo) |

Everything -- identifiers, file names, comments, documentation and the reader
interface -- is in English. See [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request.

## Tests

```
python tests.py
```

It prints each check and stops at the first failed assertion. Check 5 needs a
processed book under `books/`, and reports that it was skipped when there is
none; every other check builds its own pages and runs anywhere.

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

**Columns have to be split before the lines are extracted.** The IU course notes
carry the keywords in a column of their own beside the body text.
`extract_text_lines` doesn't see it as a column: it merges the note and the body
line into a single line, and out came `auf Sympathien Logik Der Begriff
bezeichnet für einzelne Politiker:innen zurück`. Discarding the line afterwards
doesn't help, because note and body live inside the same object.

The column is found by projecting every word onto the x axis and looking for the
widest band no word crosses. Inside a paragraph there is no such band: with
thirty lines stacked up, any `x` in the text block is covered by some word.
Measured on this book, single-column pages give 0 or 3 pt, pages with a margin
note give 11 or 12, and the channel before the footer page number gives 54. With
two safeguards: a page with few words is never split, and neither is one with
plenty of text on both sides, because that is not a note but the whole page.

Then each column is merged on its own. Interleaved, nothing merges at all: every
body line has a note line behind it and never reaches the next one. And within
the note column, two consecutive notes are separated by the vertical gap or, when
they sit flush, by the bold heading.

**A two-column paper is the opposite case.** There both columns are body, split
half and half, which is exactly the shape the margin-note detector throws away
on purpose. It is decided over the whole document and not page by page, because
the first page of a paper has no two-column shape at all: half of it is title,
authors and abstract running full width. And a single cut per page is not enough
either, since one page can carry a full-width title, then an abstract in two
columns with the channel far to the left, then the body in two centered columns.
The page is split into stretches, each with its own channel.

**The left margin is not the minimum either.** It was computed as `min(x0)`, so a
single line further left made *every* other line look indented and get glued to
the previous paragraph. The real margin is the most frequent `x0`.

**Not every book has a running header.** The header crop was
`words[0]["bottom"] + 2`: drop the first line of every page, no questions
asked. It is right for ThinkPython, which does carry a running title across all
240 pages. These course notes carry none, so it ate every section heading
(`1.2 Was ist wahr?`), the `LEKTION 2` that opens each chapter, and the headings
of the margin notes. Shape cannot tell them apart: a section heading is also a
short line set off from the body. The one thing only a header does is **repeat**,
so the first line of every page is collected and the crop happens only if it is
the same on at least 40 % of them. Digits are masked before comparing, each run
by a single mark: otherwise `page 9` and `page 10` differ and the header splits
into two halves, neither reaching the threshold.

**Headings are in a different font.** A bold subheading was getting glued to the
paragraph below it (`Alltagswissen und Wissenschaft Das Alltagswissen beruht auf
Erfahrungen...`). They are found by comparing the line's dominant font against
the body's, and go in a block of their own, as an `<h3>`. In the note column the
rule is inverted: there the heading is the term being defined and has to stay
with its definition.

**The page number comes from pdfplumber.** Enumerating what comes out doesn't
work: `read_document` skips pages with no text, and from the first blank page on
every later page was off by one.

**One section per PDF page.** The HTML used to be split every 40 blocks, so the
reader's page number had nothing to do with the book's: a 142-page book opened
as 16 and looked like half of it was missing. Now each section is the page it
came from and `data-page` carries the printed number.

## Limitations

- Only English and German voices; for another language add it to `VOICES` in
  `book.py` and download the model.
- A book written in two languages is read entirely with the voice of whichever
  weighs more.
- Figure captions end up inside the PNG and aren't read out loud.
- Thoroughly tested with only a handful of documents.

## Contributing

Issues and pull requests are welcome. [CONTRIBUTING.md](CONTRIBUTING.md) covers
how to set the project up, what the code conventions are and what kind of change
is most useful. If you have a PDF this reader mangles, that makes a good issue:
say what came out and what should have.

## License

[MIT](LICENSE) © dragon90o
