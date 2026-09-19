"""Checks on the margin, the pagination, the columns and the language.

A plain script rather than pytest: it prints what it is checking and stops at
the first failed assertion, so the output doubles as a description of the
invariants.

Most checks build their pages out of synthetic extract_text_lines()-shaped
dictionaries and run anywhere. Check 5 needs a processed book under books/ and
says so and moves on when there is none.
"""
import os
import re
import html as H
import book
from book import (
    body_margin, clean, to_html, detect_language, margin_note_gap,
    running_header, twin_columns, column_stretches,
)

FONT = "ABCDEF+Palatino"


def line(text, x0, top, font=FONT):
    """One line, shaped like the ones extract_text_lines returns.

    The widths are deliberately varied: in prose every character measures
    something different, and that is exactly how mono_fonts() tells prose from
    code. With all of them equal the text would pass for monospaced.
    """
    chars, x = [], x0
    for c in text:
        width = 4.0 + (ord(c) % 5)
        chars.append({"text": c, "fontname": font, "size": 10.0,
                      "x0": x, "x1": x + width})
        x += width
    return {"text": text, "chars": chars, "x0": x0,
            "x1": x, "top": top, "bottom": top + 11}


# a page of IU course notes: a margin note to the left of the body
BODY, NOTE, STEP = 120.0, 50.0, 14.0
notes_page = [
    line("Monografie", NOTE, 100.0),
    line("Hier wird also nur ein Thema beleuchtet.", BODY, 100.0),
    line("Monografien liefern Beitraege zum Diskurs.", BODY, 100.0 + STEP),
    line("Dissertationen sind klassische Monografien.", BODY, 100.0 + 2 * STEP),
]

print("1) body_margin")
print("   the minimum (what it used to be):",
      min(l["x0"] for l in notes_page))
print("   the body margin                 :", body_margin(notes_page))
assert body_margin(notes_page) == BODY

print("2) clean: one paragraph per sentence")
blocks = clean([dict(l, chars=list(l["chars"])) for l in notes_page])
for b in blocks:
    print("   [%s] %s" % (b["kind"], b["text"][:60]))
assert len(blocks) == 4, "glued back together: %d blocks" % len(blocks)

print("3) real continuations still get glued")
split_sentence = [
    line("Ein Satz, der auf der naechsten Zeile", BODY, 100.0),
    line("weitergeht und erst hier endet.", BODY + 12, 100.0 + STEP),
]
joined = clean(split_sentence)
print("   ->", joined[0]["text"])
assert len(joined) == 1, "a sentence was broken into %d" % len(joined)

print("4) to_html: one section per page of the pdf")
fakes = [
    {"kind": "paragraph", "text": "one", "top": 1, "page": 1},
    {"kind": "paragraph", "text": "two", "top": 2, "page": 1},
    {"kind": "paragraph", "text": "three", "top": 1, "page": 8},
    {"kind": "image", "text": "figures/x.png", "top": 2, "page": 8},
]
body = to_html(fakes)
numbers = re.findall(r'data-page="(\d+)"', body)
print("   sections:", numbers)
assert numbers == ["1", "8"], numbers
assert body.count("<section") == 2

print("5) detect_language on real text")
for title, expected in [
    ("Einführung_in_das_wissenschaftliche_arbeit_von_IT_und_Tech", "de"),
    ("ThinkPython", "en"),
]:
    path = "books/%s/index.html" % title
    if not os.path.isfile(path):
        print("   %-32s -> skipped, not on disk" % title[:32])
        continue
    with open(path, encoding="utf-8") as f:
        page_html = f.read()
    paragraphs = [{"kind": "paragraph", "text": H.unescape(t)}
                  for t in re.findall(r'<p id="b\d+"[^>]*>(.*?)</p>',
                                      page_html, re.S)]
    seen = detect_language(paragraphs)
    print("   %-32s -> %s" % (title[:32], seen))
    assert seen == expected, (title, seen)


print("6) margin_note_gap separates the note from the body")


def word(x0, x1, top):
    return {"x0": x0, "x1": x1, "top": top, "bottom": top + 11}


# 40 rows of body from x=82 to x=438 and a note to the right, from 470 to 545:
# the cut has to fall in the channel between them
with_note = [word(82 + 30 * i, 108 + 30 * i, 100.0 + 10 * r)
             for r in range(40) for i in range(12)]
with_note += [word(470, 545, 100.0 + 10 * r) for r in range(8)]
cut = margin_note_gap(with_note, 595.0)
print("   with a margin note :", cut)
assert cut is not None and 438 < cut < 470, cut

no_note = [word(82 + 30 * i, 108 + 30 * i, 100.0 + 10 * r)
           for r in range(40) for i in range(12)]
print("   a single column    :", margin_note_gap(no_note, 595.0))
assert margin_note_gap(no_note, 595.0) is None

# two halves of text are not body and note: that is the whole page
halves = [word(82 + 30 * i, 108 + 30 * i, 100.0 + 10 * r)
          for r in range(40) for i in range(6)]
halves += [word(320 + 30 * i, 346 + 30 * i, 100.0 + 10 * r)
           for r in range(40) for i in range(6)]
print("   two equal columns  :", margin_note_gap(halves, 595.0))
assert margin_note_gap(halves, 595.0) is None

print("7) running_header only crops what repeats")


class FakeBand:
    def __init__(self, lines):
        self.lines = lines

    def extract_text_lines(self, **_):
        return self.lines


class PageWithHeader:
    """A page of which only its first line matters."""

    width, height = 595.0, 842.0

    def __init__(self, first):
        self.first = first

    def crop(self, _box):
        return FakeBand([{"text": self.first, "bottom": 60.0}])


with_header = [PageWithHeader("Einfuehrung, Seite %d" % n)
               for n in range(1, 21)]
print("   a running header   :", repr(running_header(with_header)))
assert running_header(with_header) == "Einfuehrung, Seite #"

# a book with no header: every page starts with its own section heading, and
# every heading says something different. if they all said the same but for the
# number it would be a running header to all intents, and cropping it is right
HEADINGS = """wahr Logik Zweifel Quellen Methoden Empirie Theorie Modell
              Daten Analyse Ethik Zitat Plagiat Aufbau Stil Recherche
              Hypothese Statistik Umfrage Bericht""".split()
no_header = [PageWithHeader("%d.%d Was ist %s?" % (n, n, t))
             for n, t in enumerate(HEADINGS, 1)]
print("   no header          :", running_header(no_header))
assert running_header(no_header) is None

print("8) headings in the body get a block of their own")
BOLD = "ABCDEF+PalatinoBold"
with_heading = [
    line("Erster Absatz endet hier.", BODY, 100.0),
    line("Alltagswissen und Wissenschaft", BODY, 100.0 + STEP, BOLD),
    line("Das Alltagswissen beruht auf Erfahrungen.", BODY, 100.0 + 2 * STEP),
]
heading_blocks = clean(with_heading)
for b in heading_blocks:
    print("   [%-9s] %s" % (b["kind"], b["text"][:55]))
assert [b["kind"] for b in heading_blocks] == [
    "paragraph", "heading", "paragraph"], heading_blocks

print("9) the whole book, end to end")


class FakePage:
    """The little of a pdfplumber page that generate_html() looks at."""

    width, height = 595.0, 842.0
    curves = rects = lines = images = []

    def __init__(self, number):
        self.page_number = number


def fake_read(path, start=0):
    for number in (26, 27):
        yield (
            FakePage(number),
            [dict(l, chars=list(l["chars"]), note=False) for l in notes_page],
        )


book.read_document = fake_read
blocks, language = book.generate_html("fake.pdf", "test_output.html", start=25)
with open("test_output.html", encoding="utf-8") as f:
    doc = f.read()
print("   blocks: %d, language: %s" % (len(blocks), language))
print("   pages:", re.findall(r'data-page="(\d+)"', doc))
assert '<html lang="de">' in doc, "the language never reached the html"
# the number is the one pdfplumber gives, not the order things came out in
assert re.findall(r'data-page="(\d+)"', doc) == ["26", "27"]
assert "@LANG@" not in doc and "@TITLE@" not in doc, "placeholder left unfilled"
assert 'getAttribute("data-page")' in doc, "the js does not show the real page"

print("10) the two columns of a paper")

# the same page of halves that margin_note_gap rejects on purpose: for
# twin_columns it is exactly what it is looking for
halves = [word(82 + 30 * i, 108 + 30 * i, 100.0 + 10 * r)
          for r in range(40) for i in range(6)]
halves += [word(320 + 30 * i, 346 + 30 * i, 100.0 + 10 * r)
           for r in range(40) for i in range(6)]
cut = twin_columns(halves, 595.0)
print("   two equal columns  :", cut)
assert cut is not None and 262 < cut < 320, cut

# a margin note is not two columns of body
print("   with a margin note :", twin_columns(with_note, 595.0))
assert twin_columns(with_note, 595.0) is None
print("   a single column    :", twin_columns(no_note, 595.0))
assert twin_columns(no_note, 595.0) is None

# a full-width title on top and the body in two columns below: two stretches,
# the upper one with no cut because it is read side to side
wide_title = [word(82, 500, 40.0), word(82, 500, 55.0)]
wide_title += halves
stretches = column_stretches(wide_title, 595.0)
print("   stretches:", [(round(a), round(b), c) for a, b, c in stretches])
assert len(stretches) == 2, stretches
assert stretches[0][2] is None, "the title does not go by columns"
assert stretches[1][2] is not None, "the body does"

# the left column goes blank halfway down: what is below it is already another
# layout and must not slip ahead of the right column
short_column = [word(82 + 30 * i, 108 + 30 * i, 100.0 + 10 * r)
                for r in range(10) for i in range(6)]
short_column += [word(320 + 30 * i, 346 + 30 * i, 100.0 + 10 * r)
                 for r in range(40) for i in range(6)]
short_column += [word(82, 150, 560.0)]
stretches = column_stretches(short_column, 595.0)
print("   with a short column:",
      [(round(a), round(b), c) for a, b, c in stretches])
assert len(stretches) >= 2 and stretches[0][1] < 560, stretches

print("\nALL OK")
