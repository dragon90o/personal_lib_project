"""Put sideways figures upright.

Books turn a figure 90 degrees when it is wider than the page: a landscape
diagram set along the length of a portrait page, to be read by turning the book.
In the reader that came out lying on its side (p. 25, 48 and 124 of the
Softwaretechnik course book).

Two cases, told apart by whether the figure carries real text:

- Drawn in the PDF (vector) with its labels as text: every character comes
  with its own matrix, so the page itself says which way the words run. Free
  and exact.
- A picture (JPEG, PNG) with the words baked into the pixels: the PDF places it
  upright and nothing in it says the content is turned. Here the figure has to
  be looked at: an OCR pass (RapidOCR) finds the lines of text, and if nearly
  all of them stand vertical the figure is lying on its side.

The OCR reads a turned line just as well either way round, so it cannot tell
which way to turn it back. The convention of printed books is used instead:
the top of the figure goes to the left edge of the page (it is read by turning
the book clockwise), so it is turned back clockwise. All three sideways figures
of the course book follow it.

Without RapidOCR installed only the vector case is handled; pictures are left
as they are, never broken.
"""
import math
import re

from PIL import Image

# a line of text counts as vertical, or horizontal, when one side is this much
# longer than the other
ELONGATED = 1.5
# sideways only when the vertical lines win by far: an upright table with
# numbers written vertically in its cells (p. 112: 13 vertical, 7 horizontal)
# must not be turned. The real ones had 20 to 31 against 1 or 2.
DOMINANCE = 4
# and several of those vertical lines have to be actual words, not "056"
MIN_WORDS = 3
# the OCR does not need the full 200 dpi raster, and it is several times faster
OCR_SIDE = 1000

_ocr = None


# cores the OCR may use. onnxruntime takes all of them by default, and while a
# book was being prepared the whole computer stuttered (mouse, browser). With
# two, a picture takes a couple of seconds longer and nothing else notices.
OCR_THREADS = 2


def _limit_threads():
    """Make RapidOCR's onnxruntime sessions use OCR_THREADS cores.

    RapidOCR has no setting for it: it builds a SessionOptions() of its own for
    each model, so that class is swapped for one that comes pre-limited.
    """
    import rapidocr_onnxruntime.utils as rapid

    original = rapid.SessionOptions

    def limited():
        options = original()
        options.intra_op_num_threads = OCR_THREADS
        options.inter_op_num_threads = 1
        return options

    rapid.SessionOptions = limited


def _engine():
    """RapidOCR, loaded the first time a picture needs it. None if missing."""
    global _ocr
    if _ocr is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _limit_threads()
            _ocr = RapidOCR()
        except Exception as e:  # not installed, or its models failed to load
            print("orientation: OCR unavailable (%s), pictures stay as they are" % e)
            _ocr = False
    return _ocr or None


def inside(obj, box):
    """The middle of a pdfplumber object falls inside the box."""
    x = (obj["x0"] + obj["x1"]) / 2
    y = (obj["top"] + obj["bottom"]) / 2
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def text_turn(page, box, minimum=8):
    """Degrees to turn the png so the figure's own PDF text reads upright.

    0 when its text already runs left to right, None when there is too little
    text inside to say (a picture, or labels drawn as curves).
    """
    angles = []
    for c in page.chars:
        if not c["text"].strip() or not inside(c, box):
            continue
        # the matrix runs in PDF space (y upwards): (a, b) is the direction
        # the text is written in, snapped to a quarter turn
        a, b = c["matrix"][0], c["matrix"][1]
        angles.append(round(math.degrees(math.atan2(b, a)) / 90) * 90 % 360)
    if len(angles) < minimum:
        return None
    common = max(set(angles), key=angles.count)
    # the figure's labels, not the odd rotated character, have to agree
    if angles.count(common) < len(angles) * 0.6:
        return 0
    # text written upwards (90) is fixed by turning the picture clockwise
    return -common % 360


def has_picture(page, box):
    """The figure is mostly an embedded image rather than vector strokes."""
    area = (box[2] - box[0]) * (box[3] - box[1])
    for im in page.images:
        w = min(box[2], im["x1"]) - max(box[0], im["x0"])
        h = min(box[3], im["bottom"]) - max(box[1], im["top"])
        if w > 0 and h > 0 and w * h > area * 0.5:
            return True
    return False


def picture_sideways(png):
    """The picture's lines of text stand vertical: it lies on its side."""
    engine = _engine()
    if engine is None:
        return False
    import numpy as np

    img = Image.open(png).convert("RGB")
    img.thumbnail((OCR_SIDE, OCR_SIDE))
    found, _ = engine(np.array(img))
    wide = tall = words = 0
    for points, text, _score in found or []:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if w > ELONGATED * h:
            wide += 1
        elif h > ELONGATED * w:
            tall += 1
            words += len(re.findall(r"[^\W\d_]{3,}", text))
    return tall >= DOMINANCE * max(wide, 1) and words >= MIN_WORDS


def straighten(page, box, png):
    """Turn the saved png upright if the figure lies sideways in the book."""
    # A picture is judged by its pixels: the PDF text around it (the caption,
    # "Quelle: …") is always upright and says nothing about the picture.
    # turn = text_turn(page, box)
    # if turn is None and has_picture(page, box) and picture_sideways(png):
    #     turn = 270
    if has_picture(page, box):
        # clockwise, the convention of printed books (see above)
        turn = 270 if picture_sideways(png) else 0
    else:
        turn = text_turn(page, box)
    if turn:
        img = Image.open(png)
        # PIL turns counterclockwise; expand keeps the whole figure
        img.rotate(turn, expand=True).save(png)
    return turn or 0
