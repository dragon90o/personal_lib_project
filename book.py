"""Turn a PDF into a local web page that can read itself out loud.

The pipeline is read_document() -> clean() -> to_html(), and generate_html()
drives it. The rule behind every decision here is that no content may be lost:
not a formula, a diagram, a code block or the indentation inside it. See
ARCHITECTURE.md for the stage-by-stage walkthrough and the README for why each
heuristic is shaped the way it is.

Two dictionary shapes carry everything. A *line* is whatever
pdfplumber.extract_text_lines() returns, plus the flags "note", "code" and
"heading" added as it goes down the pipeline. A *block* is the output unit:

    {"kind": "paragraph" | "heading" | "code" | "image",
     "text": "...",     # or the image path, when kind == "image"
     "top": 123.4,      # for ordering
     "x0": 82.0,        # which column it came from
     "page": 26}        # printed page number, from pdfplumber

Running this module reads a book straight to the terminal; server.py is the
browser version and the one actually used.
"""

import os
import wave
import subprocess
import shutil
import textwrap
import html
import pdfplumber
from piper import PiperVoice
from template import TEMPLATE
from fontmap import decode, TABLE

DOCUMENT_PATH = "ThinkPython.pdf"
FIRST_PAGE = 25

# one voice per language: German read with the English voice comes out
# half-spoken, because piper pronounces with the phonetics of the model and not
# of the text
VOICES = {
    "en": "en_US-lessac-medium.onnx",
    "de": "de_DE-thorsten-medium.onnx",
}
DEFAULT_LANGUAGE = "en"

# stop words used to guess the language. deliberately written without accents
# or umlauts: not every pdf extracts them correctly, and these words have to
# keep counting even when the rest of the text arrives dirty.
STOP_WORDS = {
    "de": set("""der die das und ist nicht auch werden eine sich dem den des
             ein einer im zu auf als wird kann bei nach oder aber diese
             durch sind wie man bereits jedoch sowie zum zur""".split()),
    "en": set("""the and of to is not are that with this for from have has
             was were will can be an it on at by as their which such
             about into these than""".split()),
}


def margin_note_gap(words, width, minimum=8, enough=40, spare=0.3):
    """The empty vertical band separating the body from the margin notes.

    The IU course notes carry the keywords in a column of their own beside the
    body text. extract_text_lines() does not see it as a column: it merges the
    note and the body line into a single line, which is where "auf Sympathien
    Logik Der Begriff bezeichnet fuer einzelne Politiker:innen zurueck" came
    from. Discarding the line afterwards is not enough: each column has to be
    cropped separately BEFORE the lines are extracted.

    Every word is projected onto the x axis and the widest band no word crosses
    is taken. Inside a paragraph there is no such band: with thirty lines
    stacked up, any x in the text block is covered by some word. Measured on
    this book, single-column pages give 0 or 3 pt and pages with a margin note
    give 11 or 12; the channel before the footer page number gives 54.

    Two safeguards keep a page from being split when it should not be: with
    little text a chance gap is easy to find, and a real note column only holds
    a handful of words. If there is plenty of text on both sides it is not a
    margin note but the whole page, and it is left alone.
    """
    if len(words) < enough:
        return None
    occupied = [False] * (int(width) + 2)
    for w in words:
        for x in range(int(w["x0"]), min(int(w["x1"]) + 1, len(occupied))):
            occupied[x] = True
    if True not in occupied:
        return None
    # the page margins are empty too, and they separate nothing
    first = occupied.index(True)
    last = len(occupied) - 1 - occupied[::-1].index(True)
    best, x = None, first
    while x <= last:
        if occupied[x]:
            x += 1
            continue
        end = x
        while end <= last and not occupied[end]:
            end += 1
        if best is None or end - x > best[1] - best[0]:
            best = (x, end)
        x = end
    if best is None or best[1] - best[0] < minimum:
        return None
    cut = (best[0] + best[1]) / 2
    smaller = min(
        sum(1 for w in words if w["x1"] <= cut),
        sum(1 for w in words if w["x0"] >= cut),
    )
    return None if smaller > len(words) * spare else cut


def rows(words, tolerance=3):
    """The words grouped into rows by their height.

    The page has to be examined row by row rather than word by word: a heading
    that spans both columns is only recognizable as one when the whole row is
    in view.
    """
    rs = []
    for w in sorted(words, key=lambda w: w["top"]):
        if rs and w["top"] - rs[-1][0]["top"] <= tolerance:
            rs[-1].append(w)
        else:
            rs.append([w])
    return rs


def mark_occupied(occupied, row):
    """Mark in `occupied` every x this row passes through."""
    for w in row:
        for x in range(int(w["x0"]), min(int(w["x1"]) + 1, len(occupied))):
            occupied[x] = True


def channel(occupied, minimum, start, stop):
    """The center of the widest empty band between start and stop, or None.

    Text is required on both sides: otherwise what has been found is the page
    margin, which is empty too and separates nothing.
    """
    best, x = None, start
    while x <= stop:
        if occupied[x]:
            x += 1
            continue
        end = x
        while end <= stop and not occupied[end]:
            end += 1
        if best is None or end - x > best[1] - best[0]:
            best = (x, end)
        x = end
    if best is None or best[1] - best[0] < minimum:
        return None
    if True not in occupied[:best[0]] or True not in occupied[best[1]:]:
        return None
    return (best[0] + best[1]) / 2


def twin_columns(words, width, band=0.2, minimum=8, split=0.3,
                 crossing=0.4, enough=10):
    """Whether the page carries the central channel of a two-column paper.

    margin_note_gap() is built for the margin note and deliberately rejects a
    half-and-half split (spare=0.3), which is exactly the shape of a paper.
    They are opposite cases: a note is a thin column accompanying the body,
    whereas here both columns are body.

    Only the central band is examined, which is where a paper's channel falls,
    counting for each x how many rows step on it. Some genuinely cross it -- a
    running header, a wide table -- which is why the minimum is not required to
    be zero. This does not decide how the page is read, only whether the
    document is one of the two-column kind.
    """
    rs = rows(words)
    if len(rs) < enough:
        return None
    start, stop = int(width * (0.5 - band)), int(width * (0.5 + band))
    if stop <= start:
        return None
    covering = [sum(1 for row in rs
                    if any(w["x0"] <= x <= w["x1"] for w in row))
                for x in range(start, stop + 1)]
    fewest = min(covering)
    if fewest > len(rs) * crossing:
        return None
    occupied = [c != fewest for c in covering]
    cut = channel(occupied, minimum, 0, len(occupied) - 1)
    if cut is None:
        return None
    cut += start
    left = sum(1 for w in words if w["x1"] <= cut)
    right = sum(1 for w in words if w["x0"] >= cut)
    if min(left, right) < len(words) * split:
        return None
    return cut


def is_two_column(pages, sample=6, minimum=0.5):
    """Whether the whole document is a paper laid out in two columns.

    Decided over the document and not page by page, because the first page of a
    paper has no two-column shape: half of it is title, authors and abstract
    running full width. If the rest of the article has two columns, that first
    page has to be read by columns too.
    """
    seen = []
    for page in pages[:sample]:
        words = page.extract_words()
        if words:
            seen.append(twin_columns(words, page.width) is not None)
    return bool(seen) and sum(seen) >= len(seen) * minimum


def column_stretches(words, width, minimum=8, consecutive=4, edge=0.15,
                     jump=24):
    """Split the page into stretches, each with its own column cut or None.

    A paper page does not have a single layout. The first one carries the title
    and the authors side to side, below that Keywords and Abstract in two
    columns with the channel far to the left, and at the end the body in two
    centered columns. One cut for the whole page will not do.

    Rows are accumulated for as long as the same empty channel fits all of
    them: as soon as one steps on it -- a heading, a wide table, or the body,
    whose channel sits at a different x than the abstract's -- the stretch is
    closed and another begins. Rows too few to form a stretch are read side to
    side, as they were.

    A stretch is also cut when one of the two columns goes blank for a good
    while: the "1. Introduction" sitting below the keywords respects the
    abstract's channel, but it is not the same layout, and slipped into that
    column it used to be read before the whole abstract.
    """
    rs = rows(words)
    start, stop = int(width * edge), int(width * (1 - edge))
    stretches, i = [], 0
    while i < len(rs):
        occupied = [False] * (int(width) + 2)
        j, cut, last_bottom = i, None, {}
        while j < len(rs):
            row = rs[j]
            sides = {}
            if cut is not None:
                sides["left"] = [w for w in row if w["x1"] <= cut]
                sides["right"] = [w for w in row if w["x0"] >= cut]
            # the gap is measured per column and not per whole row: the
            # "1. Introduction" shares a row with the abstract's last
            # "2025).", so as a row it shows no jump at all
            breaks = any(ws and side in last_bottom
                         and min(w["top"] for w in ws) - last_bottom[side] > jump
                         for side, ws in sides.items())
            if breaks:
                break
            mark_occupied(occupied, row)
            seen = channel(occupied, minimum, start, stop)
            if seen is None:
                break
            for side, ws in sides.items():
                if ws:
                    last_bottom[side] = max(w["bottom"] for w in ws)
            cut, j = seen, j + 1
        if cut is not None and j - i >= consecutive:
            stretches.append([rs[i:j], cut])
            i = j
        elif stretches and stretches[-1][1] is None:
            stretches[-1][0].append(rs[i])
            i += 1
        else:
            stretches.append([[rs[i]], None])
            i += 1
    out = []
    for group, cut in stretches:
        top = min(w["top"] for row in group for w in row)
        bottom = max(w["bottom"] for row in group for w in row)
        out.append((top, bottom, cut))
    return out


def without_digits(text):
    """The text with its numbers masked out.

    A running header like "Chapter 3, page 41" changes on every page and is
    still the same header. Each run of digits is masked with a single mark:
    otherwise "page 9" and "page 10" come out different and the header splits
    into two halves, neither of which reaches the threshold to be recognized.
    """
    out = []
    for c in text:
        if not c.isdigit():
            out.append(c)
        elif not out or out[-1] != "#":
            out.append("#")
    return "".join(out)


def first_line(page, band=0.25):
    """The topmost line of the page, if there is one."""
    top = page.crop((0, 0, page.width, page.height * band))
    lines = top.extract_text_lines(x_tolerance=1.5)
    return lines[0] if lines else None


def running_header(pages, minimum=0.4):
    """The line that repeats at the top of nearly every page.

    ThinkPython carries a running header across all 240 pages and it has to go.
    These course notes carry none, and cropping the first line blindly ate
    every section heading ("1.2 Was ist wahr?"), the "LEKTION 2" that opens
    each chapter, and the headings of the margin notes. Shape cannot tell them
    apart: a section heading is also a short line set off from the body. The
    one thing only a header does is repeat.
    """
    count = {}
    for page in pages:
        line = first_line(page)
        if line:
            key = without_digits(line["text"])
            count[key] = count.get(key, 0) + 1
    if not count:
        return None
    text = max(count, key=count.get)
    return text if count[text] >= len(pages) * minimum else None


def read_document(path, start=0):
    """Yield (page, lines) for each page of the book.

    Every line comes marked with whether it belongs to the body or to a margin
    note, which is something only known here: further down there is no trace
    left of which column it was in.
    """
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[start:]
        header = running_header(pages)
        two_column = is_two_column(pages)
        for page in pages:
            words = page.extract_words()
            if not words:
                continue
            # crop only if there really is a running header up there; if not,
            # that line is the section heading
            ceiling = 0
            if header:
                line = first_line(page)
                if line and without_digits(line["text"]) == header:
                    ceiling = line["bottom"] + 2
            body = [w for w in words if w["bottom"] > ceiling]
            if not body:
                continue

            def lines_in(x0, x1, note, y0=None, y1=None):
                up = ceiling if y0 is None else max(ceiling, y0)
                down = page.height if y1 is None else min(page.height, y1)
                if down - up < 1 or x1 - x0 < 1:
                    return []
                crop = page.crop((x0, up, x1, down))
                lines = crop.extract_text_lines(x_tolerance=1.5)
                for l in lines:
                    l["note"] = note
                return lines

            def by_height(lines):
                # reading order is top to bottom and, at equal height, left to
                # right
                lines.sort(key=lambda l: (round(l["top"]), l["x0"]))
                return lines

            if two_column:
                # in a paper the left column is read ENTIRELY and then the
                # right one. sorting both together by height interleaves them
                # row by row, which is where "RAG combines the power of LLMs
                # ... Language Models (LLMs), has enabled the understanding"
                # came from
                book_text = []
                for y0, y1, cut in column_stretches(body, page.width):
                    if cut is None:
                        book_text += by_height(
                            lines_in(0, page.width, False, y0 - 1, y1 + 1))
                    else:
                        book_text += by_height(
                            lines_in(0, cut, False, y0 - 1, y1 + 1))
                        book_text += by_height(
                            lines_in(cut, page.width, False, y0 - 1, y1 + 1))
                yield page, book_text
                continue

            cut = margin_note_gap(body, page.width)
            if cut is None:
                book_text = lines_in(0, page.width, False)
            else:
                # of the two columns, the body is the one carrying the text;
                # the margin note fits in four loose lines
                on_the_left = sum(1 for w in body if w["x1"] <= cut)
                body_on_left = on_the_left * 2 >= len(body)
                book_text = lines_in(0, cut, not body_on_left)
                book_text += lines_in(cut, page.width, body_on_left)
            by_height(book_text)

            yield page, book_text


def mono_fonts(lines, minimum=20, tolerance=0.02, dominance=0.8):
    """The monospaced fonts, which is where the code is.

    The name cannot be trusted: in ThinkPython.pdf the code font is an unnamed
    Type 3 that pdfminer calls "unknown", whereas in a healthy pdf it would be
    Courier or anything else. What is constant is the WIDTH: in a monospaced
    font every character measures the same, in prose they do not. Normalized by
    font size so a footer set in a smaller body does not throw it off.
    """
    widths = {}
    for l in lines:
        for c in l["chars"]:
            # the space carries its own kerning and dirties the measurement
            if c["text"] == " " or not c["size"]:
                continue
            widths.setdefault(c["fontname"], []).append(
                round((c["x1"] - c["x0"]) / c["size"] / tolerance)
            )
    mono = set()
    for font, measures in widths.items():
        # with four loose characters any font looks constant
        if len(measures) < minimum:
            continue
        # requiring that ALL of them measure the same does not work: several
        # different Type 3 fonts fall under "unknown", and eight loose symbols
        # among 297 characters used to bring down whole pages of code (67, 199,
        # 200, 208). It is enough for the dominant width to take the vast
        # majority.
        common = max(measures.count(m) for m in set(measures))
        if common >= len(measures) * dominance:
            mono.add(font)
    return mono


def figure_boxes(page, join=20, minimum=10, header=75):
    """Group the vector strokes of the page into boxes.

    The diagrams in the book are NOT images: across 240 pages there is a single
    embedded image (p. 205) and, against that, 253 curves and 217 rects.
    page.images does not see them, so the region has to be located here and
    rasterized afterwards.
    """
    objects = [
        o
        for o in page.curves + page.rects + page.lines + page.images
        # the horizontal rule of the header shows up on all 240 pages
        if o["top"] > header
    ]
    if not objects:
        return []
    boxes = []
    for o in sorted(objects, key=lambda o: o["top"]):
        if boxes and o["top"] <= boxes[-1][3] + join:
            b = boxes[-1]
            boxes[-1] = [
                min(b[0], o["x0"]),
                b[1],
                max(b[2], o["x1"]),
                max(b[3], o["bottom"]),
            ]
        else:
            boxes.append([o["x0"], o["top"], o["x1"], o["bottom"]])
    # a single loose stroke is not a figure
    return [b for b in boxes
            if b[2] - b[0] >= minimum and b[3] - b[1] >= minimum]


def dominant_font(chars):
    """The font most of these characters are written in."""
    count = {}
    for c in chars:
        count[c["fontname"]] = count.get(c["fontname"], 0) + 1
    return max(count, key=count.get) if count else None


def grow_boxes(boxes, lines, mono, margin=15):
    """Pull the labels around a figure inside it.

    The bounding box of the strokes does not include the text: "Point" or "box"
    were left outside and came out sliced in half in the png. The labels are
    set in a different font from the body of the book, and that is what
    distinguishes them from the paragraph just above or from the figure
    caption.
    """
    body = dominant_font([c for l in lines for c in l["chars"]])
    labels = []
    for l in lines:
        font = dominant_font(l["chars"])
        if font != body:
            labels.append((l, font in mono))
    for b in boxes:
        growing = True
        while growing:
            growing = False
            for l, is_code in labels:
                # at the same height as the strokes: part of the drawing
                overlapping = l["top"] < b[3] and l["bottom"] > b[1]
                # just above or below, but within the width of the box: a
                # caption like "Point". code is left alone, since it overflows
                # the figure and would be swallowed whole
                above = (
                    not is_code
                    and l["top"] < b[3] + margin
                    and l["bottom"] > b[1] - margin
                    and l["x0"] > b[0] - margin
                    and l["x1"] < b[2] + margin
                )
                if not (overlapping or above):
                    continue
                grown = [
                    min(b[0], l["x0"]),
                    min(b[1], l["top"]),
                    max(b[2], l["x1"]),
                    max(b[3], l["bottom"]),
                ]
                if grown != b:
                    b[:] = grown
                    growing = True
    return boxes


def rasterize(page, box, dest, resolution=200, margin=8):
    """Save the slice of page the figure occupies as a png."""
    x0, top, x1, bottom = box
    crop = (
        max(0, x0 - margin),
        max(0, top - margin),
        min(page.width, x1 + margin),
        min(page.height, bottom + margin),
    )
    page.crop(crop).to_image(resolution=resolution).save(dest)


def inside_figure(line, boxes):
    """The line falls inside a figure, so it is already rasterized."""
    middle = (line["top"] + line["bottom"]) / 2
    return any(
        b[1] <= middle <= b[3]
        and line["x0"] >= b[0] - 2
        and line["x1"] <= b[2] + 2
        for b in boxes
    )


def only_quotes(line):
    """The line is nothing but loose quote characters."""
    t = line["text"].strip()
    return bool(t) and all(c in "'\" " for c in t)


def char_width(chars):
    """The most repeated width and how dominant it is, which in mono is all."""
    widths = {}
    for c in chars:
        w = round(c["x1"] - c["x0"], 1)
        widths[w] = widths.get(w, 0) + 1
    width = max(widths, key=widths.get)
    return width, widths[width] / len(chars)


def by_columns(chars, width=None, left=None):
    """Rebuild the text placing every character in its column.

    Only works in a monospaced font: there the column comes from dividing by
    the width of one character. The width and the margin are passed in from
    outside when a whole block is rebuilt, because the indentation of a line is
    relative to the block and not to itself.
    """
    if width is None:
        width, _ = char_width(chars)
    if left is None:
        left = chars[0]["x0"]
    text = []
    for c in chars:
        column = int(round((c["x0"] - left) / width))
        if column > len(text):
            text.extend(" " * (column - len(text)))
        text.append(decode(c["text"], TABLE))
    return "".join(text)


def by_position(dest, loose):
    """Slip the loose characters into the text already assembled.

    In prose the line cannot be rebuilt by columns: the font has variable width
    and the words come out glued together ("operatoralsoworks"). So the text is
    kept as it is and room is made only for the quote, by working out which two
    characters it falls between from its position.
    """
    text = dest["text"]
    spots = []
    j = 0
    for pos, letter in enumerate(text):
        if j >= len(dest["chars"]):
            break
        c = dest["chars"][j]
        if letter == decode(c["text"], TABLE)[:1]:
            spots.append((c["x0"], pos))
            j += 1
    # right to left, or the spots behind each insertion would shift
    for c in sorted(loose["chars"], key=lambda c: -c["x0"]):
        pos = len(text)
        for x0, p in spots:
            if x0 > c["x0"]:
                pos = p
                break
        text = text[:pos] + decode(c["text"], TABLE) + text[pos:]
    return text


def merge_line(loose, dest):
    """Put the characters of a loose line into the one below it."""
    chars = sorted(dest["chars"] + loose["chars"], key=lambda c: c["x0"])
    _, dominance = char_width(chars)
    if dominance >= 0.8:
        dest["text"] = by_columns(chars)
    else:
        dest["text"] = by_position(dest, loose)
    dest["chars"] = chars


def reattach_quotes(lines, gap=10):
    """The lines with the loose quote characters put back in place.

    The quotes of a string are drawn higher than the rest of the line and
    extract_text_lines returns them as a line of their own: 435 lines in this
    book, 1339 quotes. Throwing them away wiped out the strings in EVERY code
    example ("print 'Hello, World!'" became "print Hello, World!").
    """
    loose, rest = [], []
    for l in lines:
        (loose if only_quotes(l) else rest).append(l)
    for s in loose:
        below = [l for l in rest if 0 < l["top"] - s["top"] < gap]
        # exactly one across the 240 pages has no line below it (p. 94)
        if below:
            merge_line(s, min(below, key=lambda l: l["top"]))
    return rest


def line_spacing(lines):
    """The distance from one line to the next within a single block.

    It is the shortest separation seen between two consecutive lines: if a pair
    is further apart than that, there is a blank line in between.
    """
    steps = [
        b["top"] - a["top"]
        for a, b in zip(lines, lines[1:])
        if b["top"] > a["top"]
    ]
    return min(steps) if steps else 0


def body_margin(lines, tolerance=2):
    """The left margin of the body text, not counting the notes.

    The minimum will not do. The IU course notes carry a column of margin notes
    to the left of the body, and a single note was enough to make EVERY line on
    the page look indented and get glued to the previous paragraph: the 142
    pages of the German book came out as 489 paragraphs, with paragraphs of
    3,383 characters. The real margin is the most repeated x0, which is where
    the body begins.
    """
    groups = {}
    for l in lines:
        groups.setdefault(round(l["x0"] / tolerance), []).append(l["x0"])
    if not groups:
        return 0
    # on a tie the leftmost wins, since that is the margin and not an indent
    return min(max(groups.values(), key=lambda g: (len(g), -min(g))))


def detect_language(blocks, default=DEFAULT_LANGUAGE):
    """Guess the language of the book by counting stop words.

    The title is no use (this book is called "Einfuehrung..." but could just as
    well be called "IU DLBWIRITT01") and the pdf carries no reliable metadata,
    so the text is what gets examined: stop words are the most repeated ones
    and they do not overlap between languages.
    """
    words = []
    for b in blocks:
        if b["kind"] == "paragraph":
            words.extend(b["text"].lower().split())
    if not words:
        return default
    cleaned = [w.strip(".,;:()[]“”\"'!?") for w in words]
    count = {
        language: sum(1 for w in cleaned if w in stop)
        for language, stop in STOP_WORDS.items()
    }
    winner = max(count, key=count.get)
    # with four loose words there is nothing to decide
    return winner if count[winner] > len(cleaned) * 0.02 else default


def clean(lines, boxes=()):
    """Decode the text and merge it into blocks of prose and code."""
    for line in lines:
        line["text"] = decode(line["text"], TABLE)
    # the labels of the diagrams already come inside the figure png
    kept = [l for l in reattach_quotes(lines) if not inside_figure(l, boxes)]
    if not kept:
        return []
    mono = mono_fonts(kept)
    for l in kept:
        # looking only at the first character fails on sentences starting with
        # a word in the code font ("76trombones is illegal...")
        odd = sum(1 for c in l["chars"] if c["fontname"] in mono)
        # a real line of code is 100% monospaced; prose with variable names in
        # it does not go beyond 70%
        l["code"] = odd > len(l["chars"]) * 0.9

    # the margin is taken from the prose: on a page of pure code the dominant
    # x0 is the indentation of the block, not the margin of the page
    prose = [l for l in kept if not l["code"]]
    margin = body_margin(prose or kept)

    # the course notes carry keywords in a column of their own to the left of
    # the body. they have to be read, since they are part of the book, but they
    # are not the sentence beside them: glued to the body it came out as
    # "Monografie Hier wird also nur ein Thema beleuchtet."
    for l in kept:
        l["note"] = l.get("note", not l["code"] and l["x1"] < margin)

    code = [l for l in kept if l["code"]]
    if code:
        # extract_text_lines starts each line at its first character, so the
        # indentation was lost and the body of a def ended up flush with the
        # margin. the line is rebuilt by columns counting from the margin of
        # the block, because in python indentation is syntax.
        left = min(l["x0"] for l in code)
        width, _ = char_width([c for l in code for c in l["chars"]])
        for l in code:
            l["text"] = by_columns(l["chars"], width, left)
    step = line_spacing(code)

    # the footer page number is not content, and alone in its own block piper
    # would sing it out on all 138 pages. in a book it falls in the same column
    # as the notes; in a paper it is centered and arrives as body
    body = [l for l in kept
            if not l["note"] and not l["text"].strip().isdigit()]
    notes = [l for l in kept
             if l["note"] and not l["text"].strip().isdigit()]
    # the heading of each note is in a different font from its text (bold), and
    # when two notes run together with no gap it is the only thing separating
    # them
    for group in (body, notes):
        # the body is all in the same font and the headings in another (bold).
        # code is left out of the count, since it has a font of its own and
        # would carry the majority on a page of pure example
        group_prose = [l for l in group if not l["code"]]
        normal = dominant_font(
            [c for l in group_prose for c in l["chars"]]
        )
        for l in group:
            l["heading"] = (
                not l["code"] and dominant_font(l["chars"]) != normal
            )
    blocks = merge_lines(body, margin, step, headings_apart=True)
    # the notes are merged separately and broken on the vertical gap, which,
    # with all of them in the same column, is the only thing separating them
    blocks += merge_lines(notes, margin, step, line_spacing(notes) * 1.8)
    # each note stays at the height of the paragraph it annotates. with no
    # notes there is nothing to reposition, and sorting by height would destroy
    # the reading order: in a paper the right column starts at the very top, so
    # its first paragraph slipped ahead of the last one on the left and
    # "2. Background" ended up behind section 3
    if not notes:
        return blocks
    return sorted(blocks, key=lambda b: b["top"])


def new_block(kind, line):
    # x0 is kept to know which column the block was in: that is what place()
    # needs in order to slot a figure into position
    return {"kind": kind, "text": line["text"], "top": line["top"],
            "x0": line["x0"]}


def place(page, block, near=80):
    """Slot the block into position without reordering the rest of the page.

    Sorting the whole page by height works in a single-column book, but in a
    paper the right column starts again at the very top: sorting made its first
    paragraph slip ahead of the last one on the left, and section 3 was read
    before section 2.

    The figure finds its own place, ahead of the first block in its own column
    that lies below it. If there is none, it was at the foot of the page and
    stays at the end.
    """
    for i, b in enumerate(page):
        if (abs(b.get("x0", block["x0"]) - block["x0"]) <= near
                and b["top"] > block["top"]):
            page.insert(i, block)
            return
    page.append(block)


def merge_lines(lines, margin, step, gap=0, headings_apart=False):
    """Glue the loose lines into blocks of prose and of code.

    Works on a single column: either the body or the margin notes, never the
    two mixed. Handed them mixed, every body line has a note behind it and
    nothing merges with anything.

    headings_apart says what to do with the lines in a different font. In the
    body they are section headings and go in a block of their own, since
    otherwise it came out as "Alltagswissen und Wissenschaft Das Alltagswissen
    beruht auf Erfahrungen...". In the notes column, by contrast, the heading is
    the term being defined and has to stay with its definition.
    """
    result = []
    previous = None
    for l in lines:
        is_code = l["code"]
        previous_code = previous is not None and previous["code"]
        # how many lines there are from the previous one to this: one is the
        # line right below, two means the example has a blank line in between
        steps = (
            int(round((l["top"] - previous["top"]) / step))
            if previous is not None and step
            else 0
        )
        continues = result and not result[-1]["text"].endswith(
            (".", "?", "!", ":")
        )
        # two things break a block even when the indentation says it carries
        # on: a large vertical gap, and a heading. both are needed, because a
        # page can hold three margin notes, all in the same column, and some of
        # them run together with no gap in between.
        is_heading = l.get("heading", False)
        separate = (
            is_heading
            or (headings_apart and previous is not None
                and previous.get("heading"))
            or (
                bool(gap)
                and previous is not None
                and l["top"] - previous["top"] > gap
            )
        )
        if result and is_code and previous_code and 1 <= steps <= 2:
            # the blank lines inside an example are preserved
            result[-1]["text"] += "\n" * steps + l["text"]
        elif (
            result
            and not separate
            and (l["x0"] > margin + 5 or continues)
            and not previous_code
            and not is_code
        ):
            if result[-1]["text"].endswith("-"):
                result[-1]["text"] = result[-1]["text"][:-1] + l["text"]
            else:
                result[-1]["text"] += " " + l["text"]
        elif is_code:
            result.append(new_block("code", l))
        elif headings_apart and is_heading:
            result.append(new_block("heading", l))
        else:
            result.append(new_block("paragraph", l))
        previous = l

    return result


def load_voice(language=DEFAULT_LANGUAGE):
    """Load the Piper model for this language, falling back to the default."""
    return PiperVoice.load(VOICES.get(language, VOICES[DEFAULT_LANGUAGE]))


def speak(voice, text):
    """Synthesize the text and play it. Needs aplay, so Linux only."""
    with wave.open("output.wav", "wb") as f:
        voice.synthesize_wav(text, f)
    subprocess.run(["aplay", "output.wav"])


def draw(paragraphs, current):
    """Redraw the text leaving the current paragraph at the very bottom."""
    width, height = shutil.get_terminal_size()
    blocks = []
    used = 0
    for i in range(current, -1, -1):
        lines = textwrap.wrap(paragraphs[i], width) or [""]
        if used + len(lines) > height - 1 and blocks:
            break
        if i == current:
            lines = [f"\033[93m{l}\033[0m" for l in lines]
        blocks.insert(0, "\n".join(lines))
        used += len(lines)
    print("\033[3J\033[2J\033[H", end="", flush=True)
    print("\n" * (height - 1 - used), end="")
    print("\n".join(blocks), flush=True)


def to_html(blocks):
    """Assemble the body of the html, one section per page of the pdf.

    It used to be split every 40 blocks, and then the page number in the reader
    had nothing to do with the one in the book: the 142 pages of the German
    book came out as 16 and it looked like half the book was missing. Now each
    section is the page it was.

    Every block that can be read out loud carries its number: it is the one the
    browser asks the server for so piper can synthesize it, and the one stored
    as the bookmark.
    """
    pages = []
    for i, block in enumerate(blocks):
        # books prepared before this have no page: they all fall on the first
        # one and the html still opens
        n = block.get("page", 1)
        if not pages or pages[-1][0] != n:
            pages.append((n, []))
        kind = block["kind"]
        txt = html.escape(block["text"])
        slot = pages[-1][1]
        if kind == "image":
            slot.append(f'<img src="{txt}" alt="figure">')
        elif kind == "paragraph":
            slot.append(f'<p id="b{i}" data-i="{i}">{txt}</p>')
        elif kind == "heading":
            slot.append(f'<h3 id="b{i}" data-i="{i}">{txt}</h3>')
        else:
            slot.append(f'<pre id="b{i}" data-i="{i}">{txt}</pre>')
    return "\n".join(
        '<section class="page" data-page="%d">\n%s\n</section>'
        % (n, "\n".join(p))
        for n, p in pages
    )


def reading_document(body, title="Reader", language=DEFAULT_LANGUAGE):
    """Wrap the blocks in the reading page.

    The template is not an f-string because the css and the javascript are full
    of braces and every one of them would have to be doubled.
    """
    return (
        TEMPLATE.replace("@TITLE@", html.escape(title))
        .replace("@LANG@", html.escape(language))
        .replace("<!--BODY-->", body)
    )


def generate_html(path, out, start=0, folder="figures", title=None):
    """Dump the whole book to a local html with its figures.

    The figures are saved in a folder beside the html, so that the src of each
    image is a short relative path and the whole book can be moved in one
    piece.
    """
    dest = os.path.join(os.path.dirname(out) or ".", folder)
    os.makedirs(dest, exist_ok=True)
    blocks = []
    for page, lines in read_document(path, start):
        # the number comes from pdfplumber and counts from 1, like the printed
        # book. enumerating what comes out does not work: read_document skips
        # pages with no text, and from the first blank page on every later page
        # was off by one.
        n = page.page_number
        boxes = grow_boxes(figure_boxes(page), lines, mono_fonts(lines))
        page_blocks = clean(lines, boxes)
        for i, box in enumerate(boxes):
            name = "p%03d_%d.png" % (n, i)
            rasterize(page, box, os.path.join(dest, name))
            # the figure has to stay where it was, not at the end of the page,
            # and without dragging the reading order along with it
            place(page_blocks, {"kind": "image", "top": box[1], "x0": box[0],
                                "text": folder + "/" + name})
        for b in page_blocks:
            b["page"] = n
        blocks.extend(page_blocks)
    if title is None:
        title = os.path.splitext(os.path.basename(path))[0]
    language = detect_language(blocks)
    with open(out, "w", encoding="utf-8") as f:
        f.write(reading_document(to_html(blocks), title, language))
    return blocks, language


def main():
    """Read the book out loud in the terminal, highlighting the paragraph."""
    voice = None
    for page, lines in read_document(DOCUMENT_PATH, FIRST_PAGE):
        blocks = clean(
            lines,
            grow_boxes(figure_boxes(page), lines, mono_fonts(lines)),
        )
        if voice is None:
            # here it goes page by page, so the language is decided from the
            # first one, which already carries hundreds of words.
            # generate_html() looks at the whole book, which is where getting
            # it right matters.
            voice = load_voice(detect_language(blocks))
        paragraphs = [b["text"] for b in blocks]
        for i, p in enumerate(paragraphs):
            draw(paragraphs, i)
            speak(voice, p)


if __name__ == "__main__":
    main()
