"""Local server for the reader.

On startup it serves the library: a page in the browser with one folder per
book, where new PDFs can also be added, either chosen from a folder or by
pasting their path. While it runs it synthesizes with Piper whichever paragraph
the browser asks for: the same path speak() takes in the terminal (build the
WAV, play it, throw it away), except the WAV never touches the disk now and
goes back and forth in memory.

    python server.py                    -> the library, in the browser
    python server.py book.pdf           -> that one, from the first page
    python server.py book.pdf 26        -> skipping the table of contents
    python server.py book.pdf 26 -r     -> rebuilding the html

The server knows nothing about the book itself: it receives the text of a
paragraph over POST /tts and hands back audio. Everything about which paragraph
comes next lives in the JavaScript of template.py.
"""

import io
import json
import os
import re
import shutil
import sys
import threading
import urllib.request
import wave
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, quote, urlsplit

from piper import PiperVoice

# import translate
# The translation add-on (translate.py) is personal: it stays on this computer,
# out of git and out of the published program. Without it the reader works the
# same, with no translate button and no /translate routes.
try:
    import translate
except ImportError:
    class translate:  # noqa: N801 -- stands in for the missing module
        ENABLED = False

        @staticmethod
        def warm_up(_ensure_voice):
            pass
from book import VOICES, DEFAULT_LANGUAGE, generate_html
from template import SHELF

PORT = 8765
LIBRARY = "books"
# where the voice models come from; they weigh 61 MB and are not in the repo
VOICES_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
# one download of a given voice at a time; see ensure_voice()
DOWNLOAD_LOCK = threading.Lock()
# the voice being downloaded right now, for the pages to show: without a
# console there is no other way to see why the first paragraph is slow.
# {"language": ..., "percent": ...} while it lasts, empty otherwise
DOWNLOAD = {}
# where the packaged program (ReadAloud.exe) keeps the books and the voices: the
# user's own data folder, since the program's folder may be read-only and is
# replaced on every update. Run from source, everything stays in the project.
APP_NAME = "ReadAloud"


class UserError(ValueError):
    """A problem the library page shows to the person, in their language.

    The message stays in English (the log, and the fallback); the code and the
    book name go to the page, which has the translations (I18N in template.py,
    keys err_<code>).
    """

    def __init__(self, code, message, name=""):
        super().__init__(message)
        self.code = code
        self.name = name


# The tray menu, in the language of Windows. The pages pick theirs from the
# browser (I18N in template.py); the tray has no browser to ask.
TRAY_TEXT = {
    "en": {"open": "Open library", "quit": "Quit"},
    "de": {"open": "Bibliothek öffnen", "quit": "Beenden"},
    "es": {"open": "Abrir biblioteca", "quit": "Salir"},
}


def system_language():
    """Two-letter code of the Windows display language ("es"), "en" if unknown."""
    try:
        if sys.platform == "win32":
            import ctypes
            import locale

            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return (locale.windows_locale.get(lcid) or "en")[:2]
        import locale

        return (locale.getlocale()[0] or "en")[:2].lower()
    except Exception:
        return "en"


def error_body(e):
    """The JSON for a refused request: the English message and, if it has one,
    the code the page translates."""
    return {"error": str(e), "code": getattr(e, "code", None), "name": getattr(e, "name", "")}


# stepping back a paragraph should not cost another synthesis. keyed by the
# language and the text, so it survives moving between pages and books
CACHE = {}
CACHE_LIMIT = 400
# milliseconds of silence for paragraphs with nothing to read out loud
SILENCE_MS = 300
# one voice per language, loaded the first time a book in it is read: the
# library holds books in several languages and a model takes seconds to load
LOADED = {}
# the server answers requests on several threads (so the library page keeps
# refreshing while a book is prepared), but one voice synthesizes one text at a
# time
VOICE_LOCK = threading.Lock()
# books being prepared from the library page: name -> "building" or the error
# that stopped it. a finished book leaves this and shows up in library()
JOBS = {}


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


def book_url(name):
    """The address a book is read at, percent-encoded like location.pathname.

    It has to match exactly: the reader keys its bookmark by its own path, and
    the library reads that bookmark back with this url.
    """
    return "/%s/%s/index.html" % (LIBRARY, quote(name))


def clean_path(text):
    """Clean up a path that was typed into the terminal or dragged onto it.

    Dragging a file in brings the quotes along with it. And ~ is expanded by
    the shell, but whatever is typed at an input() arrives raw, so expanduser
    has to translate it to the home directory (on Windows, %USERPROFILE%).
    """
    return os.path.expanduser(text.strip().strip('"').strip("'"))


def book_name(filename):
    """The folder a PDF is prepared into: its file name, without the .pdf.

    basename() also drops any directory a browser might send along with the
    name, so an upload can never write outside books/.
    """
    name = os.path.splitext(os.path.basename(filename.replace("\\", "/")))[0]
    name = name.strip()
    if name in ("", ".", ".."):
        raise UserError("no_name", "that file has no usable name")
    return name


def choose_book(arguments):
    """Read the book to open from the arguments.

    Returns (pdf, start, rebuild), with pdf None when there are no arguments:
    then the library is opened in the browser instead.
    """
    rebuild = "-r" in arguments
    arguments = [a for a in arguments if a != "-r"]
    if not arguments:
        return None, 0, rebuild
    pdf = clean_path(arguments[0])
    if not os.path.isfile(pdf):
        sys.exit("cannot find %r" % pdf)
    start = max(0, int(arguments[1]) - 1) if len(arguments) > 1 else 0
    return pdf, start, rebuild


def prepare(pdf, start, rebuild):
    """Leave the book ready under books/<name>/ and return its url.

    Processing is skipped when the page is already there, unless -r was given:
    a book takes minutes to build and is rebuilt only when asked.
    """
    name = book_name(pdf)
    folder = os.path.join(LIBRARY, name)
    out = os.path.join(folder, "index.html")
    if rebuild or not os.path.isfile(out):
        os.makedirs(folder, exist_ok=True)
        print("preparing %s ..." % name)
        blocks, language = generate_html(pdf, out, start, title=name)
        print("  %d blocks, in %s" % (len(blocks), language))
    else:
        print("%s was already prepared (-r to rebuild it)" % name)
    return book_url(name)


def build(pdf, name, start):
    """Prepare a book in the background, for the library page.

    It takes minutes, so it runs on its own thread and reports through JOBS,
    which the page polls. The book appears on the shelf by itself once its
    index.html is written.
    """
    try:
        folder = os.path.join(LIBRARY, name)
        os.makedirs(folder, exist_ok=True)
        print("preparing %s ..." % name)
        blocks, language = generate_html(
            pdf, os.path.join(folder, "index.html"), start, title=name
        )
        print("  %d blocks, in %s" % (len(blocks), language))
        # the voice is fetched now, while the page still says "preparing",
        # rather than on the first paragraph, where the wait has no explanation
        ensure_voice(language)
        JOBS.pop(name, None)
    except Exception as e:
        print("  %s failed: %s" % (name, e))
        JOBS[name] = "failed: %s" % e


def check_new(name):
    """Refuse a book the library already has, or is already preparing."""
    if name in library():
        raise UserError("exists", "“%s” is already in the library" % name, name)
    if JOBS.get(name) == "building":
        raise UserError("preparing", "“%s” is already being prepared" % name, name)


def start_build(pdf, name, start):
    """Queue a book from the library page."""
    check_new(name)
    JOBS[name] = "building"
    threading.Thread(target=build, args=(pdf, name, start), daemon=True).start()


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


def download(url, path):
    """Fetch url into path, printing the progress as it goes.

    It goes to a .part file that is renamed only once complete, so a download
    cut halfway never leaves behind a model that looks fine and fails to load.
    """
    part = path + ".part"
    with urllib.request.urlopen(url, timeout=60) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, shown = 0, -1
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                DOWNLOAD["percent"] = done * 100 // total
            if total and done * 10 // total != shown:
                shown = done * 10 // total
                print("  %3d %%  (%d of %d MB)" % (shown * 10, done >> 20, total >> 20))
    os.replace(part, path)


def ensure_voice(language):
    """Make sure the model for a language is on disk, downloading it if not.

    Returns the model's file name, or None when it is missing and could not be
    fetched (no internet, say). The small .json goes second, and a model counts
    as present only when both are there. The lock stops two books in the same
    language from fetching the same 61 MB at once.
    """
    model = VOICES.get(language, VOICES[DEFAULT_LANGUAGE])
    with DOWNLOAD_LOCK:
        if os.path.isfile(model) and os.path.isfile(model + ".json"):
            return model
        print("downloading the %s voice (%s, about 60 MB, only once) ..." % (language, model))
        DOWNLOAD.update(language=language, percent=0)
        try:
            for name in (model, model + ".json"):
                if not os.path.isfile(name):
                    download(voice_url(model).replace(model, name), name)
        except OSError as e:
            print("  could not download it: %s" % e)
            print("  it can also be fetched by hand:")
            for name in (model, model + ".json"):
                print("    curl -LO %s" % voice_url(model).replace(model, name))
            return None
        finally:
            DOWNLOAD.clear()
        print("  done")
        return model


def load_voice(language):
    """Load the voice for the language of the book, downloading it if needed.

    If it cannot be had, reading carries on with the default voice: German
    read with an English accent is ugly, but it beats having no reader at all.
    main() has already made sure the default is on disk, so there is always
    something to fall back to.
    """
    model = ensure_voice(language)
    if model is None:
        model = VOICES[DEFAULT_LANGUAGE]
        print("reading with %s in the meantime" % model)
    print("loading %s ..." % model)
    return PiperVoice.load(model)


def voice_for(language):
    """The voice for a language, loaded the first time it is asked for."""
    if language not in VOICES:
        language = DEFAULT_LANGUAGE
    if language not in LOADED:
        LOADED[language] = load_voice(language)
    return LOADED[language]


def synthesize(language, text):
    """Return the WAV for this text, ready to send to the browser."""
    key = (language, text)
    if key in CACHE:
        return CACHE[key]
    with VOICE_LOCK:
        voice = voice_for(language)
        memory = io.BytesIO()
        with wave.open(memory, "wb") as w:
            # the format is set by hand because a paragraph with no actual
            # words in it ("• ...") makes piper emit no audio at all; nothing
            # then sets the format and wave raises "# channels not specified"
            # on close
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(voice.config.sample_rate)
            voice.synthesize_wav(text, w, set_wav_format=False)
            if w.getnframes() == 0:
                # an empty wav never plays, so the browser would never fire
                # "ended" and the reader would stall here: a short breath of
                # silence keeps it moving
                w.writeframes(
                    bytes(2 * voice.config.sample_rate * SILENCE_MS // 1000)
                )
    data = memory.getvalue()
    if len(CACHE) > CACHE_LIMIT:
        CACHE.clear()
    CACHE[key] = data
    return data


class Reader(SimpleHTTPRequestHandler):
    """Serves the library and the book folders, and answers the POSTs.

    The books themselves are plain static files: the html, the figures and the
    javascript are all inherited from SimpleHTTPRequestHandler. On top of that:

        GET  /          the library page
        GET  /library   the books and the ones being prepared, as json
        POST /tts       text in, wav out
        POST /upload    a pdf chosen in the browser, as the raw request body
        POST /add       {"path": ..., "start": ...} for a pdf already on disk
    """

    def end_headers(self):
        # A rebuilt book keeps its file names (figures/p048_0.png), so without
        # this the browser kept showing the old figure, sideways, until Ctrl+F5.
        # no-cache = ask every time; the files carry Last-Modified, so an
        # unchanged one costs a 304 and nothing is sent again.
        if self.command == "GET":
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            # self.reply(200, SHELF.encode("utf-8"), "text/html; charset=utf-8")
            # the page starts in the language of Windows (the browser often
            # says English first); only [a-z] reaches the page
            lang = re.sub(r"[^a-z]", "", system_language())[:2] or "en"
            page = SHELF.replace("@SYSLANG@", lang)
            self.reply(200, page.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/library":
            # newest first: the folded shelf shows only its first row, and
            # that row should be what was added last
            names = sorted(
                library(),
                key=lambda n: os.path.getctime(os.path.join(LIBRARY, n)),
                reverse=True,
            )
            books = [
                {
                    "name": name,
                    "url": book_url(name),
                    "lang": language_of(
                        os.path.join(LIBRARY, name, "index.html")
                    ),
                }
                for name in names
            ]
            self.json(200, {"books": books, "jobs": JOBS, "download": DOWNLOAD})
        elif path == "/favicon.ico":
            # the browser asks for it by itself; the png is what it gets
            try:
                with open(resource("assets", "readaloud.png"), "rb") as f:
                    self.reply(200, f.read(), "image/png")
            except OSError:
                self.send_error(404)
        # the optional translation add-on, see translate.py
        elif translate.ENABLED and path == "/translate.js":
            translate.serve_script(self)
        elif translate.ENABLED and translate.serve_book(self, path):
            pass
        else:
            super().do_GET()

    def do_POST(self):
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        if parts.path == "/tts":
            self.tts(query.get("lang", [DEFAULT_LANGUAGE])[0])
        elif parts.path == "/upload":
            self.upload(query)
        elif parts.path == "/add":
            self.add()
        elif parts.path == "/delete":
            self.delete()
        elif translate.ENABLED and parts.path == "/translate":
            translate.handle_post(self, query)
        else:
            self.send_error(404)

    def delete(self):
        """Remove a book for good: its folder, with the page, the figures and
        the uploaded pdf. A book that failed to prepare can be removed the same
        way, which also clears it off the shelf."""
        length = int(self.headers.get("Content-Length", 0))
        try:
            name = str(json.loads(self.rfile.read(length) or b"{}").get("name", ""))
            # only names that are actually on the shelf, never a path: this
            # deletes folders, so nothing from the request gets near rmtree
            known = set(library()) | set(JOBS)
            if name not in known or JOBS.get(name) == "building":
                raise UserError("no_book", "there is no such book to delete")
            shutil.rmtree(os.path.join(LIBRARY, name), ignore_errors=True)
            JOBS.pop(name, None)
            print("deleted %s" % name)
        except ValueError as e:
            self.json(400, error_body(e))
            return
        self.json(200, {"name": name})

    def tts(self, language):
        length = int(self.headers.get("Content-Length", 0))
        # "replace" rather than raising: the browser always sends utf-8, but if
        # a stray byte does arrive it is better to read the paragraph with one
        # odd symbol in it than to drop the connection without a word
        text = self.rfile.read(length).decode("utf-8", "replace").strip()
        if not text:
            self.send_error(400, "no text")
            return
        try:
            data = synthesize(language, text)
        except Exception as e:  # let the browser display the reason
            self.send_error(500, str(e))
            return
        self.reply(200, data, "audio/wav")

    def upload(self, query):
        """A pdf picked in the browser. It is kept inside the book's folder,
        which is also what makes a later rebuild possible."""
        length = int(self.headers.get("Content-Length", 0))
        try:
            name = book_name(query.get("name", [""])[0])
            start = max(0, int(query.get("start", ["1"])[0]) - 1)
            # checked before reading the body, so a duplicate is refused
            # without writing anything over the book that is there
            check_new(name)
            folder = os.path.join(LIBRARY, name)
            os.makedirs(folder, exist_ok=True)
            pdf = os.path.join(folder, name + ".pdf")
            with open(pdf, "wb") as f:
                left = length
                while left > 0:
                    chunk = self.rfile.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    f.write(chunk)
                    left -= len(chunk)
            start_build(pdf, name, start)
        except ValueError as e:
            self.json(400, error_body(e))
            return
        self.json(200, {"name": name})

    def add(self):
        """A pdf already somewhere on this machine, by its path."""
        length = int(self.headers.get("Content-Length", 0))
        try:
            request = json.loads(self.rfile.read(length) or b"{}")
            pdf = clean_path(str(request.get("path", "")))
            if not os.path.isfile(pdf):
                raise UserError("not_found", "cannot find %s" % pdf, pdf)
            if not pdf.lower().endswith(".pdf"):
                raise UserError("not_pdf", "that is not a pdf")
            name = book_name(pdf)
            start_build(pdf, name, max(0, int(request.get("start", 1)) - 1))
        except ValueError as e:
            self.json(400, error_body(e))
            return
        self.json(200, {"name": name})

    def reply(self, code, data, kind):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def json(self, code, value):
        self.reply(code, json.dumps(value).encode("utf-8"), "application/json")

    def log_message(self, *args):
        pass


class Server(ThreadingHTTPServer):
    """The HTTP server, refusing a port that is already taken.

    HTTPServer sets SO_REUSEADDR, which on Linux only lets a restart reuse the
    port straight away, but on Windows lets a second program bind a port that
    is already being listened on. A second double click on ReadAloud.exe then
    started a second server instead of noticing the first one. On Windows the
    option is off, so the bind fails and main() just opens the library.
    """

    allow_reuse_address = sys.platform != "win32"


def frozen():
    """Whether this is the packaged ReadAloud.exe rather than python server.py."""
    return getattr(sys, "frozen", False)


def resource(*parts):
    """A file shipped with the program (the icon): inside the bundle when
    packaged, next to this script when run from source."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def fail(message):
    """Stop with a message. The packaged program has no console to print it
    in, so there it goes in an ordinary Windows message box."""
    print(message)
    if frozen() and sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
    sys.exit(1)


def tray(server, url):
    """The icon next to the clock, the only visible part of the packaged
    program: it has no window, and this is how it is reopened and closed.

    It runs on the main thread and blocks until Quit; the server runs on its
    own thread meanwhile. Without pystray (from source, say) it just serves.
    """
    try:
        import pystray
        from PIL import Image
    except ImportError:
        server.serve_forever()
        return

    def quit_(icon, _item):
        icon.stop()
        server.shutdown()

    threading.Thread(target=server.serve_forever, daemon=True).start()
    words = TRAY_TEXT.get(system_language(), TRAY_TEXT["en"])
    menu = pystray.Menu(
        # default=True: a plain click on the icon opens the library too
        # pystray.MenuItem("Open library", lambda *_: webbrowser.open(url), default=True),
        # pystray.MenuItem("Quit", quit_),
        pystray.MenuItem(words["open"], lambda *_: webbrowser.open(url), default=True),
        pystray.MenuItem(words["quit"], quit_),
    )
    # pystray.Icon(APP_NAME, Image.open(resource("assets", "readaloud.png")), APP_NAME, menu).run()
    try:
        pystray.Icon(APP_NAME, Image.open(resource("assets", "readaloud.png")), APP_NAME, menu).run()
    except Exception as e:
        # some Linux desktops (GNOME without the AppIndicator extension, a
        # Wayland session with no X) have nowhere to put the icon. The reader
        # works the same without it: keep serving until the process is ended
        print("no tray icon here (%s); the library stays at %s" % (e, url))
        threading.Event().wait()


def data_home():
    """Where each system keeps the data of a user's programs.

    Windows %LOCALAPPDATA%, macOS ~/Library/Application Support, Linux
    $XDG_DATA_HOME or ~/.local/share. Before the Linux build it fell back to
    the home folder itself, which left a ReadAloud folder lying in ~.
    """
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return os.environ["LOCALAPPDATA"]
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    return os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")


def main():
    """Prepare a book or open the library, and serve until stopped."""
    if frozen():
        # everything below (books/, the voices, the static files the server
        # hands out) is relative, so moving into the data folder is enough
        # data = os.path.join(
        #     os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME
        # )
        data = os.path.join(data_home(), APP_NAME)
        os.makedirs(data, exist_ok=True)
        os.chdir(data)
        # no console: what would have been printed goes to a log in the same
        # folder, which is where to look when something goes wrong
        log = open(os.path.join(data, "readaloud.log"), "w", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
        print("%s - books and voices are kept in %s" % (APP_NAME, data))
    pdf, start, rebuild = choose_book(sys.argv[1:])
    path = prepare(pdf, start, rebuild) if pdf else "/"
    url = "http://localhost:%d%s" % (PORT, path)
    try:
        server = Server(("127.0.0.1", PORT), Reader)
    except OSError:
        # the usual cause is the reader already running: a second double
        # click then just opens the library, which is what it was for
        webbrowser.open(url)
        if frozen():
            sys.exit(0)
        fail("port %d is already in use: the reader is probably already open" % PORT)
    print()
    print("   %s" % url)
    print()
    print("(ctrl-c to stop)")
    # on Linux opening the browser is not reliable: xdg-open depends on the
    # .desktop entry of the default browser, and some of them (Mullvad, for
    # one) wrap their Exec in a sh -c that breaks when it is re-split. There
    # the printed URL has to do; on Windows and macOS it simply opens.
    # if sys.platform in ("win32", "darwin"):
    #     webbrowser.open(url)
    # The packaged Linux program (AppImage) has no terminal to print to, so
    # there it tries anyway: if the browser does not come up, the URL is in
    # readaloud.log and the tray's "Open library" tries again.
    if sys.platform in ("win32", "darwin") or frozen():
        try:
            webbrowser.open(url)
        except Exception as e:
            print("could not open the browser (%s): open %s by hand" % (e, url))
    # the default voice is fetched after the library is already open, not
    # before: the first time that is a 60 MB download, and it looked as if the
    # program had not started. The library does not need a voice; the first
    # paragraph read waits for it, since load_voice() goes through the same
    # lock, and the pages show the progress (DOWNLOAD).
    threading.Thread(target=ensure_voice, args=(DEFAULT_LANGUAGE,), daemon=True).start()
    translate.warm_up(ensure_voice)
    try:
        if frozen():
            tray(server, url)
        else:
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
