"""Local server for the reader.

On startup it shows the library so you can pick a book, or you hand it a new
PDF and it prepares one. While it runs it synthesizes with Piper whichever
paragraph the browser asks for: the same path speak() takes in the terminal
(build the WAV, play it, throw it away), except the WAV never touches the disk
now and goes back and forth in memory.

    python server.py                    -> show the library
    python server.py book.pdf           -> that one, from the first page
    python server.py book.pdf 26        -> skipping the table of contents
    python server.py book.pdf 26 -r     -> rebuilding the html

The server knows nothing about the book itself: it receives the text of a
paragraph over POST /tts and hands back audio. Everything about which paragraph
comes next lives in the JavaScript of template.py.
"""

import io
import os
import re
import sys
import wave
from http.server import HTTPServer, SimpleHTTPRequestHandler

from piper import PiperVoice

from book import VOICES, DEFAULT_LANGUAGE, generate_html

PORT = 8765
LIBRARY = "books"
# where the voice models come from; they weigh 61 MB and are not in the repo
VOICES_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
# stepping back a paragraph should not cost another synthesis. keyed by the text
# itself, so it survives moving between pages and books
CACHE = {}
CACHE_LIMIT = 400
# milliseconds of silence for paragraphs with nothing to read out loud
SILENCE_MS = 300


def library():
    """The books already prepared, in alphabetical order.

    A folder counts as a book once it has an index.html, which is the last
    thing generate_html() writes: a run interrupted halfway leaves figures
    behind but no page, and is correctly not offered.
    """
    if not os.path.isdir(LIBRARY):
        return []
    return sorted(
        name
        for name in os.listdir(LIBRARY)
        if os.path.isfile(os.path.join(LIBRARY, name, "index.html"))
    )


def clean_path(text):
    """Clean up a path that was typed into the terminal or dragged onto it.

    Dragging a file in brings the quotes along with it. And ~ is expanded by
    the shell, but whatever is typed at an input() arrives raw, so expanduser
    has to translate it to the home directory (on Windows, %USERPROFILE%).
    """
    return os.path.expanduser(text.strip().strip('"').strip("'"))


def ask_pdf(pdf):
    """Keep asking until the path is a real file.

    An empty answer is taken as giving up, since there is nothing to read
    without a book.
    """
    while not os.path.isfile(pdf):
        if pdf:
            print("cannot find %r" % pdf)
        pdf = clean_path(input("path to the pdf: "))
        if not pdf:
            sys.exit("no book, nothing to read")
    return pdf


def ask_page():
    """Ask which page to start from, counting from 1 like the printed book.

    Used to skip the front matter and the table of contents, whose layout has
    nothing to do with the body and only confuses the column detection.
    """
    page = input("start at page [1]: ").strip()
    return max(0, int(page) - 1) if page else 0


def choose_book(arguments):
    """Work out which book to open, from the arguments or by asking.

    Returns (pdf, name, start, rebuild). Exactly one of the first two is None:
    pdf is None for a book already on the shelf, which only has to be opened,
    and name is None for a new PDF, which has to be processed.
    """
    rebuild = "-r" in arguments
    arguments = [a for a in arguments if a != "-r"]
    if arguments:
        pdf = ask_pdf(arguments[0])
        start = max(0, int(arguments[1]) - 1) if len(arguments) > 1 else 0
        return pdf, None, start, rebuild

    shelf = library()
    if shelf:
        print("in the library:")
        for i, name in enumerate(shelf, 1):
            print("  %d) %s" % (i, name))
        answer = clean_path(input("a number, or the path to a new pdf: "))
        if answer.isdigit() and 1 <= int(answer) <= len(shelf):
            return None, shelf[int(answer) - 1], 0, rebuild
        pdf = ask_pdf(answer)
    else:
        pdf = ask_pdf("")
    return pdf, None, ask_page(), rebuild


def prepare(pdf, name, start, rebuild):
    """Leave the book ready under books/<name>/ and return (url, language).

    Processing is skipped when the page is already there, unless -r was given:
    a book takes minutes to build and is rebuilt only when asked.
    """
    if name is None:
        name = os.path.splitext(os.path.basename(pdf))[0]
    folder = os.path.join(LIBRARY, name)
    out = os.path.join(folder, "index.html")
    if pdf is None:
        # picked off the shelf: already built, it only has to be opened
        if rebuild:
            print("rebuilding %s needs the pdf" % name)
    elif rebuild or not os.path.isfile(out):
        os.makedirs(folder, exist_ok=True)
        print("preparing %s ..." % name)
        blocks, language = generate_html(pdf, out, start, title=name)
        print("  %d blocks, in %s" % (len(blocks), language))
    else:
        print("%s was already prepared (-r to rebuild it)" % name)
    url = "http://localhost:%d/%s/%s/index.html" % (PORT, LIBRARY, name)
    # the language is read back out of the html instead of being carried in a
    # variable, so it makes no difference whether the book was just built or
    # was already on the shelf
    return url, language_of(out)


def language_of(out):
    """The language detected for the book when it was prepared.

    The html carries it in <html lang>. It has to be stored there because when
    a book is opened off the shelf the PDF need not still be on disk, so the
    text cannot be examined again.

    Falls back to the default voice if the file or the attribute is missing,
    which is what happens with books built before this was stored.
    """
    try:
        with open(out, encoding="utf-8") as f:
            header = f.read(500)
    except OSError:
        return DEFAULT_LANGUAGE
    found = re.search(r'<html lang="([a-z]{2})"', header)
    return found.group(1) if found else DEFAULT_LANGUAGE


def voice_url(model):
    """The URL a Piper model is downloaded from.

    The file name already contains its own path: de_DE-thorsten-medium lives
    under de/de_DE/thorsten/medium, so the URL can be rebuilt from the name
    alone and no table of links has to be maintained.
    """
    locale, name, quality = model[: -len(".onnx")].split("-")
    return "%s/%s/%s/%s/%s/%s" % (
        VOICES_URL, locale.split("_")[0], locale, name, quality, model
    )


def load_voice(language):
    """Load the voice for the language of the book.

    A missing model is reported together with the command that fetches it, and
    reading carries on with the default voice: German read with an English
    accent is ugly, but it beats having no reader at all.

    With no model on disk at all there is nothing to fall back to, and that
    does stop the program.
    """
    model = VOICES.get(language, VOICES[DEFAULT_LANGUAGE])
    if not os.path.isfile(model):
        print("the %s voice is missing (%s). to get it:" % (language, model))
        for name in (model, model + ".json"):
            print("  curl -LO %s" % voice_url(model).replace(model, name))
        model = VOICES[DEFAULT_LANGUAGE]
        print("reading with %s in the meantime" % model)
    if not os.path.isfile(model):
        sys.exit("without any voice there is nothing to read: fetch %s" % model)
    print("loading %s ..." % model)
    return PiperVoice.load(model)


def synthesize(voice, text):
    """Return the WAV for this text, ready to send to the browser."""
    if text in CACHE:
        return CACHE[text]
    memory = io.BytesIO()
    with wave.open(memory, "wb") as w:
        # the format is set by hand because a paragraph with no actual words in
        # it ("• ...") makes piper emit no audio at all; nothing then sets the
        # format and wave raises "# channels not specified" on close
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(voice.config.sample_rate)
        voice.synthesize_wav(text, w, set_wav_format=False)
        if w.getnframes() == 0:
            # an empty wav never plays, so the browser would never fire "ended"
            # and the reader would stall here: a short breath of silence keeps
            # it moving
            w.writeframes(
                bytes(2 * voice.config.sample_rate * SILENCE_MS // 1000)
            )
    data = memory.getvalue()
    if len(CACHE) > CACHE_LIMIT:
        CACHE.clear()
    CACHE[text] = data
    return data


class Reader(SimpleHTTPRequestHandler):
    """Serves the book folder, and answers POST /tts with synthesized audio.

    Everything else is inherited: the html, the figures and the javascript are
    plain static files. The voice is a class attribute because
    SimpleHTTPRequestHandler is instantiated once per request and loading the
    model takes seconds.
    """

    voice = None

    def do_POST(self):
        if self.path.split("?")[0] != "/tts":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        # "replace" rather than raising: the browser always sends utf-8, but if
        # a stray byte does arrive it is better to read the paragraph with one
        # odd symbol in it than to drop the connection without a word
        text = self.rfile.read(length).decode("utf-8", "replace").strip()
        if not text:
            self.send_error(400, "no text")
            return
        try:
            data = synthesize(self.voice, text)
        except Exception as e:  # let the browser display the reason
            self.send_error(500, str(e))
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    """Prepare or pick a book, load its voice, and serve it until ctrl-c."""
    pdf, name, start, rebuild = choose_book(sys.argv[1:])
    url, language = prepare(pdf, name, start, rebuild)
    Reader.voice = load_voice(language)
    # opening the browser automatically is not reliable: xdg-open depends on
    # the .desktop entry of the default browser, and some of them (Mullvad, for
    # one) wrap their Exec in a sh -c that breaks when it is re-split. Printing
    # the URL works on any machine.
    print()
    print("   %s" % url)
    print()
    print("(paste that address in the browser; ctrl-c to stop)")
    server = HTTPServer(("127.0.0.1", PORT), Reader)
    try:
        server.serve_forever()
    finally:
        # without this the port stays taken and the next run fails to bind
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # ctrl-c is the normal way to close this, not an error worth dumping a
        # whole traceback on screen for
        print("\nsee you")
        sys.exit(0)
