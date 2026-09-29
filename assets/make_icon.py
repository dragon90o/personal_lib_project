"""Draws the FIRST ReadAloud icon (the pale book on a dark green square).

NOT the current one. Since 29-09-2026 the icon is readaloud-1024.png: the
Microsoft Store icon (line-drawn book with sound waves) in dravvt green on plain
black, and readaloud.png / .ico are scaled down from it. This script is kept
only as the first version; running it would overwrite the current icon.

Original description:

Draws the ReadAloud icon: an open book with sound waves coming out of it.

Drawn in code rather than in an editor, so it can be tweaked by changing a
number and regenerated:

    python assets/make_icon.py

It writes readaloud.png (512 px, for the tray icon and the browser tab) and
readaloud.ico (every size Windows asks for, for the exe). Everything is drawn
at 1024 px and scaled down, which is what keeps the edges smooth.
"""

import os

from PIL import Image, ImageDraw

SIZE = 1024
HERE = os.path.dirname(os.path.abspath(__file__))

# the reader's own colors: its green highlight, darkened, and a pale ink
TOP = (52, 84, 64)
BOTTOM = (24, 38, 30)
PAGE = (241, 237, 228)
WAVE = (150, 222, 150)


def gradient(size, top, bottom):
    """A vertical gradient filling a square."""
    im = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(im)
    for y in range(size):
        t = y / (size - 1)
        d.line([(0, y), (size, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return im


def arc(d, center, radius, start, end, width, fill):
    """An arc with round ends: PIL draws them square, which looks harsh."""
    import math

    cx, cy = center
    box = [cx - radius, cy - radius, cx + radius, cy + radius]
    d.arc(box, start, end, fill=fill, width=width)
    # the round caps sit on the middle of the stroke
    mid = radius - width / 2
    for angle in (start, end):
        a = math.radians(angle)
        x, y = cx + mid * math.cos(a), cy + mid * math.sin(a)
        d.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=fill)


def draw():
    # rounded square, the shape Windows 11 icons tend to have
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=220, fill=255)
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(gradient(SIZE, TOP, BOTTOM), (0, 0), mask)

    d = ImageDraw.Draw(icon)
    # the open book: two pages leaning out from the spine, a little higher at
    # the outer edge, like a book lying open
    left = [(160, 560), (492, 626), (492, 870), (160, 804)]
    right = [(532, 626), (864, 560), (864, 804), (532, 870)]
    d.polygon(left, fill=PAGE)
    d.polygon(right, fill=PAGE)

    # sound waves rising from the spine
    center = (512, 610)
    for radius in (190, 300, 410):
        arc(d, center, radius, 235, 305, 46, WAVE)
    return icon


def main():
    icon = draw()
    icon.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, "readaloud.png"))
    icon.save(
        os.path.join(HERE, "readaloud.ico"),
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("wrote readaloud.png and readaloud.ico in", HERE)


if __name__ == "__main__":
    main()
