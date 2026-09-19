# Architecture

How a PDF becomes a page that reads itself out loud. Read this before changing
any of the detection heuristics; the README section *Things I learned along the
way* explains **why** each one is shaped the way it is.

## The two halves

The project splits cleanly in two, and they only meet through a file on disk:

**Build time** (`book.py`, `fontmap.py`, `template.py`) turns a PDF into
`books/<name>/index.html` plus a folder of figure PNGs. Runs once per book.

**Read time** (`server.py`, plus the JavaScript inside `template.py`) serves
that HTML and synthesizes speech on demand. The PDF is no longer needed.

That boundary is deliberate: a processed book is self-contained and can be
copied to another machine on its own.

## The data that flows through

Two dictionary shapes carry everything.

A **line** starts as whatever `pdfplumber.extract_text_lines()` returns — at
least `text`, `chars`, `x0`, `x1`, `top`, `bottom` — and picks up flags as it
goes down the pipeline:

| key | added by | meaning |
|---|---|---|
| `note` | `read_document`, `clean` | the line is a margin note, not body text |
| `code` | `clean` | the line is code (mostly monospaced characters) |
| `heading` | `clean` | the line is a heading (font differs from the body's) |

A **block** is the output unit, one per paragraph, heading, code listing or
figure:

```python
{"kind": "paragraph" | "heading" | "code" | "image",
 "text": "...",      # or the image path, when kind == "image"
 "top":  123.4,      # for ordering
 "x0":   82.0,       # which column it came from
 "page": 26}         # printed page number, from pdfplumber
```

Every block except `image` becomes one speakable element in the HTML.

## Build time, stage by stage

`generate_html(path, out, start)` drives the whole thing.

### 1. `read_document(path, start)` — one page at a time, columns already split

A generator yielding `(page, lines)`. Two decisions are made **over the whole
document** before any page is touched, because neither can be read off a single
page:

- `running_header(pages)` — the running header, found by collecting the first
  line of every page and keeping it only if it repeats on at least 40 % of them.
  `without_digits()` masks digit runs first so `page 9` and `page 10` count as the
  same header.
- `is_two_column(pages)` — whether this is a two-column paper, sampled over the
  first few pages with `twin_columns()`.

Then, per page, the header is cropped and the page is split into columns
**before** the lines are extracted. This ordering is the whole point:
`extract_text_lines()` merges a margin note and the body line beside it into one
line, and no amount of post-processing can separate them again.

Which split depends on the document:

- **Two-column paper** → `column_stretches()` cuts the page into stretches,
  each with its own channel (or none, for a full-width title). Within a
  stretch, the left column is read *entirely* before the right one; sorting both
  by height would interleave them line by line.
- **Anything else** → `margin_note_gap()` looks for one narrow empty band
  separating a slim margin-note column from the body. The two detectors are
  deliberate opposites: a note is a thin column beside the body, whereas a
  paper's two columns are both body, split half and half.

Both work by projecting words onto the x axis and finding the widest band no
word crosses (`mark_occupied()` and `channel()` are the shared primitives).

### 2. `figure_boxes(page)` and `grow_boxes()` — find the diagrams

Diagrams are usually vector strokes, not embedded images, so `page.images`
never sees them. Curves, rects, lines and images above the header rule get
grouped into boxes, then `grow_boxes()` grows each box to swallow the labels
around it, which sit in a different font from the body and would otherwise be
sliced in half by the crop.

### 3. `clean(lines, boxes)` — lines become blocks

The core of the project, in order:

1. **Decode** every line through `decode()` from `fontmap.py` (see below).
2. **`reattach_quotes()`** puts floating quote characters back into the line
   below them. Quotes are drawn higher than the rest of the line, so
   `extract_text_lines()` hands them back separately; dropping them used to
   strip the strings out of every code example. `merge_line()` reinserts them,
   by column (`by_columns()`) when the line is monospaced, by horizontal
   position (`by_position()`) when it is prose.
3. **Drop lines inside a figure box** (`inside_figure()`) — they are already in the PNG.
4. **Classify code** with `mono_fonts()`, which identifies monospaced fonts by
   measuring character *width*, never by font name. A line is code if more than
   90 % of its characters use one of those fonts.
5. **Find the body margin** with `body_margin()`: the most frequent `x0`, not
   the minimum. Measured over prose only, since on an all-code page the
   dominant `x0` is a block's indentation.
6. **Rebuild code lines** with `by_columns()`, using the width and left edge
   of the whole code block, because indentation is relative to the block.
   `extract_text_lines()` starts each line at its first character, so the
   indentation is otherwise lost — and in Python indentation is syntax.
7. **Split body from notes**, dropping footer page numbers.
8. **Mark headings** per group, by comparing each line's dominant font against
   its group's.
9. **`merge_lines()`** merges lines into blocks, once per column. Called with
   `headings_apart=True` for the body, where a heading gets a block of its
   own, and without it for the notes column, where the heading is the term
   being defined and must stay with its definition.

### 4. Back in `generate_html()` — figures, page numbers, language

Each figure box is rasterized (`rasterize()`) into `figures/pNNN_I.png` and its
block is slotted into place by `place()`, which looks for the next block in
the same column rather than re-sorting the page. Every block is stamped with
`page.page_number` — pdfplumber's number, because `read_document` skips pages
with no text and counting yields would drift.

Finally `detect_language()` guesses the language by counting stop words
(`STOP_WORDS`), and `reading_document()` drops the body, the title and the
language into `TEMPLATE`.

### `fontmap.py` — the broken font

Some PDFs carry a Type 3 monospaced font with no standard encoding, and every
extractor falls back to the ZapfDingbats glyph list, so `>>> print` arrives as
`❃❃❃ ♣r✐♥t`. It is a consistent monoalphabetic substitution, so `TABLE` maps it back
character by character. The pairs were derived from known text: Python's
keywords, the interpreter's error messages, a line of ASCII punctuation.

Running `python fontmap.py` against a PDF reports which non-ASCII characters are
still unmapped — that is how the table was built and how it gets extended.

## Read time

`server.py` starts an `HTTPServer` on port 8765 with `Reader`, a
`SimpleHTTPRequestHandler` that also answers `POST /tts`.

The voice is chosen from `<html lang>` in the book's own HTML (`language_of()`),
not from the PDF: when a book is opened off the shelf, the PDF may be long gone.
A missing model prints the `curl` that fetches it and falls back to English.

The JavaScript in `template.py` holds the reading state:

- Only the current `<section class="page">` is displayed; the whole book at
  once is thousands of blocks.
- Everything with a `data-i` attribute is speakable, in reading order. Figures
  have no `data-i`, so they are skipped automatically.
- To read a block, the browser POSTs its `textContent` to `/tts` and plays the
  WAV that comes back. **The server knows nothing about the book** — it receives
  text and returns audio.
- The next block is fetched while the current one plays, or the gap between
  paragraphs is audible. `synthesize()` also caches by text, so stepping back
  does not re-synthesize.
- The position is kept in `localStorage`, keyed by path, along with the font
  size and column width.

One wrinkle worth knowing: a paragraph with nothing pronounceable in it (`• ...`)
makes Piper return no audio at all, and `wave` then raises on close. So
`synthesize()` sets the WAV format by hand and writes a short silence, because a
zero-length WAV never fires `ended` and the reader would stall.

## The terminal reader

`book.main()` is the original version: it reads straight to the terminal,
`draw()` redrawing the text with the current paragraph highlighted and
`speak()` shelling out to `aplay`. It only works where `aplay` exists (Linux)
and is kept because it is the shortest path to check extraction without a
browser.
