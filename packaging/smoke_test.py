"""Start the program just built and check that it works, before it is published.

Used by .github/workflows/release.yml on Windows and on Linux, the same way:

    python packaging/smoke_test.py dist/ReadAloud/ReadAloud.exe
    python packaging/smoke_test.py ReadAloud-1.2.0-x86_64.AppImage --appimage-extract-and-run

It starts the program as a user would, then checks two things:

1. the library answers at http://127.0.0.1:8765/ (the page with the
   interface translations, so it is the current one);
2. the voice works: /tts turns a sentence into a WAV. That needs no speakers,
   and it proves Piper and its voice model are packaged and load. The first
   time it downloads the English voice (about 60 MB).

If either fails it prints the program's own log and exits with an error, so
the workflow stops and nothing is published. Standard library only.
"""

import os
import signal
import subprocess
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8765"
LIBRARY_WAIT = 60   # seconds for the library to answer
VOICE_WAIT = 240    # the first sentence includes downloading the voice


def data_log():
    """Where the packaged program writes readaloud.log (see server.data_home)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", "")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "ReadAloud", "readaloud.log")


def wait_for(what, check, seconds):
    deadline = time.time() + seconds
    last = None
    while time.time() < deadline:
        try:
            if check():
                print("ok:", what)
                return True
        except Exception as e:  # not up yet, or still downloading
            last = e
        time.sleep(2)
    print("FAILED:", what, "(%s)" % last)
    return False


def library_answers():
    with urllib.request.urlopen(URL + "/", timeout=5) as r:
        return r.status == 200 and b"UI_TEXT" in r.read()


def voice_works():
    request = urllib.request.Request(
        URL + "/tts?lang=en", data=b"This is a test of the reading voice.", method="POST"
    )
    with urllib.request.urlopen(request, timeout=120) as r:
        wav = r.read()
    # a real WAV: RIFF header and more than a moment of sound
    return r.status == 200 and wav[:4] == b"RIFF" and len(wav) > 20000


def main():
    command = sys.argv[1:]
    # own process group on Linux: the AppImage starts the program as a child,
    # and stopping only the parent would leave it holding the port
    extra = {"start_new_session": True} if sys.platform != "win32" else {}
    program = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **extra)
    ok = False
    try:
        ok = wait_for("the library answers", library_answers, LIBRARY_WAIT) and wait_for(
            "the voice speaks", voice_works, VOICE_WAIT
        )
    finally:
        if sys.platform != "win32":
            try:
                os.killpg(program.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        else:
            program.kill()
        if not ok:
            try:
                out = program.communicate(timeout=10)[0]
                print("--- program output ---\n" + out.decode("utf-8", "replace"))
            except Exception:
                pass
            if os.path.isfile(data_log()):
                with open(data_log(), encoding="utf-8", errors="replace") as f:
                    print("--- readaloud.log ---\n" + f.read())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
