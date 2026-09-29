"""NOT the current icon: a try from 29-09-2026 that was dropped the same day.

The current one is readaloud-1024.png (and the png/ico made from it): the
Microsoft Store icon itself, with its lines turned dravvt green and the
halftone dots removed, leaving plain black. Running this script without an
argument would overwrite it.

Original description:

Draws the current ReadAloud icon: an open book with the green wave of
dravvt above it, on black.

The book is the line-drawn open book of the reader (Lucide's book-open, the
same one used in the pages), the wave is the dravvt logo (the path of the
footer of dravvt.com, "M 4 15 Q 12 4 20 15 Q 28 26 36 15"), in the brand green.

    python assets/make_icon_v2.py            # writes readaloud.png and .ico
    python assets/make_icon_v2.py out.png    # only a preview, nothing replaced

Drawn at 4096 px and scaled down, which is what keeps the edges smooth. After
changing it, bump ?v= of the favicon in template.py so browsers fetch it again.
"""

import math
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
BIG = 4096            # drawing size
S = BIG / 1024        # everything below is written in a 1024 px icon

BACKGROUND = (10, 10, 10)
PAPER = (242, 242, 236)   # the off-white of the book lines
GREEN = (0, 255, 0)       # dravvt


def arc(cx, cy, r, start, end, steps=24):
    """Points of a circular arc, angles in degrees (y grows downwards)."""
    return [
        (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
        for a in (start + (end - start) * i / steps for i in range(steps + 1))
    ]


def book_outline():
    """Lucide book-open in its own 24-unit grid, as one closed line."""
    pts = [(3, 18)]
    pts += arc(3, 17, 1, 90, 180)[1:]      # bottom left corner
    pts += arc(3, 4, 1, 180, 270)          # top left corner
    pts += arc(8, 7, 4, 270, 360)          # left page into the spine
    pts += arc(16, 7, 4, 180, 270)[1:]     # spine out to the right page
    pts += arc(21, 4, 1, 270, 360)         # top right corner
    pts += arc(21, 17, 1, 0, 90)           # bottom right corner
    pts += arc(15, 21, 3, 270, 180, 16)    # into the tail of the spine
    pts += arc(9, 21, 3, 0, -90, 16)[1:]   # and out again
    pts.append((3, 18))
    return pts


def polyline(draw, pts, width, color):
    """A thick line with round joints and caps."""
    draw.line(pts, fill=color, width=int(width))
    r = width / 2
    for x, y in pts:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def quad(p0, p1, p2, steps=40):
    """Points of a quadratic Bezier curve."""
    return [
        (
            (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1],
        )
        for t in (i / steps for i in range(steps + 1))
    ]


def simple_book():
    """An open book reduced to what still reads at 16 px: two pages meeting
    at the spine, the tops dipping slightly towards it. 24-unit grid."""
    return [(2, 4), (12, 6), (22, 4), (22, 19), (12, 21), (2, 19), (2, 4)]


def draw_icon():
    img = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded square, like the Store icon
    d.rounded_rectangle((0, 0, BIG - 1, BIG - 1), radius=int(230 * S), fill=BACKGROUND)

    # First version, with Lucide's book-open: too much detail and too thin to
    # be seen small. Kept for reference:
    # unit = 28 * S
    # ox = BIG / 2 - 12 * unit
    # oy = 430 * S - 3 * unit
    # book = [(ox + x * unit, oy + y * unit) for x, y in book_outline()]
    # polyline(d, book, 1.9 * unit, PAPER)
    # polyline(d, [(ox + 12 * unit, oy + 7 * unit), (ox + 12 * unit, oy + 20.2 * unit)], 1.9 * unit, PAPER)

    # the book: big and with thick lines, filling the lower part
    unit = 31 * S
    ox = BIG / 2 - 12 * unit
    oy = 395 * S - 4 * unit
    at = lambda x, y: (ox + x * unit, oy + y * unit)
    polyline(d, [at(x, y) for x, y in simple_book()], 2.6 * unit, PAPER)
    polyline(d, [at(12, 6), at(12, 21)], 2.6 * unit, PAPER)  # the spine

    # the dravvt wave above it: 40x30 grid of the logo, 560 px wide
    w = 14 * S
    wx = BIG / 2 - 20 * w
    wy = 215 * S - 15 * w
    p = lambda x, y: (wx + x * w, wy + y * w)
    wave = quad(p(4, 15), p(12, 4), p(20, 15)) + quad(p(20, 15), p(28, 26), p(36, 15))[1:]
    polyline(d, wave, 7.5 * w, GREEN)
    return img


def main():
    icon = draw_icon()
    if len(sys.argv) > 1:
        icon.resize((1024, 1024), Image.LANCZOS).save(sys.argv[1])
        return
    icon.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, "readaloud.png"), optimize=True)
    icon.resize((1024, 1024), Image.LANCZOS).save(
        os.path.join(HERE, "readaloud.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
