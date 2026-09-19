"""Decoding table for a PDF whose code font has no usable encoding.

Some PDFs carry a Type 3 monospaced font with no standard encoding --
ThinkPython.pdf, produced by LaTeX + Ghostscript 9.25, is the one this was
written for. pdfminer, poppler and mupdf all fall back to the ZapfDingbats
glyph list for it, so ">>> print" is extracted as "❃❃❃ ♣r✐♥t". It is not
pdfplumber's fault: pdftotext and mutool fail the same way, which also means
the mapping is always this same fallback and not a property of the book.

The substitution is monoalphabetic and consistent, so it can simply be
reversed. The pairs below were derived from text whose plaintext is known in
advance: Python's 31 keywords, the interpreter's error messages, and a line of
ASCII punctuation the book happens to print in full.

Importing this module gives you TABLE and decode(), which is what book.py uses.
Running it as a script instead reports which characters are still unmapped in a
document -- that is how the table was built, and how it gets extended for a new
broken PDF.
"""

import pdfplumber

# only used when running this module as a script, to hunt for the characters
# still missing from the table
DOCUMENT_PATH = "ThinkPython.pdf"
# skip the front matter, which is set in the normal text font and would say
# nothing about the broken one
FIRST_PAGE = 20


def build_table(pairs):
    """Build the character map out of (ciphered, plain) string pairs.

    The pairs are written out as whole phrases rather than character by
    character because that is how they were read off the page, and a phrase can
    be checked against the PDF by eye. Both halves therefore have to be the
    same length, and a mismatch is a typo in the table: it would silently shift
    every character after it onto the wrong key, so it raises instead.
    """
    table = {}
    for cipher, plain in pairs:
        if len(cipher) != len(plain):
            raise ValueError(
                "length mismatch:\n  %s (%d)\n  %s (%d)"
                % (cipher, len(cipher), plain, len(plain))
            )
        table.update(dict(zip(cipher, plain)))

    return table


def decode(text, table):
    """Decode a string, leaving anything not in the table untouched.

    Called on every line of every document, including the healthy ones, where
    no character is in the table and the text comes back unchanged.
    """
    out = []
    for c in text:
        out.append(table.get(c, c))

    return "".join(out)


TABLE = build_table(
    [
        ("❛♥❞ ❞❡❧ ❢r♦♠ ♥♦t ✇❤✐❧❡", "and del from not while"),
        ("❛s ❡❧✐❢ ❣❧♦❜❛❧ ♦r ✇✐t❤", "as elif global or with"),
        ("❛ss❡rt ❡❧s❡ ✐❢ ♣❛ss ②✐❡❧❞", "assert else if pass yield"),
        ("❜r❡❛❦ ❡①❝❡♣t ✐♠♣♦rt ♣r✐♥t", "break except import print"),
        ("❝❧❛ss ❡①❡❝ ✐♥ r❛✐s❡", "class exec in raise"),
        ("❝♦♥t✐♥✉❡ ❢✐♥❛❧❧② ✐s r❡t✉r♥", "continue finally is return"),
        ("❞❡❢ ❢♦r ❧❛♠❜❞❛ tr②", "def for lambda try"),
        ("❃❃❃ ✶✱✵✵✵✱✵✵✵", ">>> 1,000,000"),
        ("❃❃❃ ✼✻tr♦♠❜♦♥❡s ❂ ❜✐❣ ♣❛r❛❞❡", ">>> 76trombones = big parade"),
        ("❙②♥t❛①❊rr♦r✿ ✐♥✈❛❧✐❞ s②♥t❛①", "SyntaxError: invalid syntax"),
        ("❃❃❃ ♠♦r❡❅ ❂ ✶✵✵✵✵✵✵", ">>> more@ = 1000000"),
        (
            "❃❃❃ ❝❧❛ss ❂ ❆❞✈❛♥❝❡❞ ❚❤❡♦r❡t✐❝❛❧ ❩②♠✉r❣②",
            ">>> class = Advanced Theoretical Zymurgy",
        ),
        (
            "✷✵✰✸✷ ❤♦✉r✲✶ ❤♦✉r✯✻✵✰♠✐♥✉t❡ ♠✐♥✉t❡✴✻✵ ✺✯✯✷ ✭✺✰✾✮✯✭✶✺✲✼✮",
            "20+32 hour-1 hour*60+minute minute/60 5**2 (5+9)*(15-7)",
        ),
        (
            "❤tt♣✿✴✴✇✐❦✐✳♣②t❤♦♥✳♦r❣✴♠♦✐♥✴❇✐t✇✐s❡❖♣❡r❛t♦rs✳",
            "http://wiki.python.org/moin/BitwiseOperators.",
        ),
        ("✬❫❴", "'^_"),
        # the book prints one line with the whole of ASCII punctuation in a
        # row, which is where these came from:
        #   !"#$%& ()*+,-./:;<=>?@[\]^_ `{|}~
        ("✦✧★✩✪✫❀❁❄❬❭❪❵④⑤⑥⑦", '!"#$%&;<?[\\]`{|}~'),
        # capitals, taken from the error messages and from the JKLMNOPQ
        # prefix list in the chapter on strings
        ("❋■◆❈▲❉❲❘❍▼●❏❑◗❱❨❯❳③❥✹✽", "FINCLDWRHMGJKQVYUXzj48"),
    ]
)

def main():
    """Report the characters this document still has no mapping for.

    Decode the whole book and collect whatever comes out non-ASCII: those are
    the glyphs the table is still missing. The way to close the gap is to find
    a line containing them whose plaintext you can work out, and add the pair
    to the table above. An empty report means the document decodes completely.
    """
    missing = set()

    with pdfplumber.open(DOCUMENT_PATH) as pdf:
        for page in pdf.pages[FIRST_PAGE:]:
            lines = page.extract_text_lines(x_tolerance=1.5)
            for line in lines:
                for c in decode(line["text"], TABLE):
                    if not c.isascii():
                        missing.add(c)

    print("missing", len(missing), ":", "".join(sorted(missing)))


if __name__ == "__main__":
    main()
