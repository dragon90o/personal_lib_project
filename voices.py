"""The voices the reader can read with, and how each one turns text into sound.

Two engines:

- Piper: small and fast, one ~60 MB model per voice. The first voice of each
  language below is Piper's, the one ReadAloud has always read with: it is
  downloaded by itself the first time a book in that language needs it.
- Kokoro: more natural, and bigger. Downloaded only when someone picks one of
  its voices in the library (Voices), after listening to the samples.
  English and Spanish share one model with all their voices inside (353 MB in
  total); each German voice is a model of its own (325 MB), because Kokoro has
  no German and these are separate German fine-tunes.

The samples heard in the library are bundled with the program
(assets/voices/<id>.mp3, ~70 KB each), so listening downloads nothing.

The choice is kept per language in voices.json, next to the books. A book
always asks for its language (/tts?lang=de), never for a voice, so the books
prepared before this existed read with the chosen voice too.
"""

import io
import json
import os
import re
import wave

from book import VOICES as PIPER_MODELS

# where each Kokoro file is fetched from. English and Spanish come from the
# kokoro-onnx releases; Martin from its own repository (Apache 2.0).
KOKORO_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
MARTIN_REPO = "https://huggingface.co/huggingFresse/Kokoro-82M-ONNX-German-Martin/resolve/main"
# Victoria is the full (not int8) export of kikiri-tts/kikiri-german-victoria,
# made by us: the int8 one on the web had a whistle. Published nowhere else, so
# it is kept in our own DigitalOcean Space (with its CDN). Without an address
# the voice is not offered.
# VICTORIA_URL = None
VICTORIA_URL = "https://lightup-videos.fra1.cdn.digitaloceanspaces.com/readaloud/voices"

# the folder the Kokoro files go in, next to the Piper models and the books
KOKORO_DIR = "kokoro"
# the chosen voice of each language: {"de": "victoria", ...}
CHOICES_FILE = "voices.json"

# shared by every English and Spanish Kokoro voice
KOKORO_MULTI = (
    ("kokoro-v1.0.onnx", KOKORO_RELEASE + "/kokoro-v1.0.onnx"),
    ("voices-v1.0.bin", KOKORO_RELEASE + "/voices-v1.0.bin"),
)


def piper(language, voice_id, name, gender):
    return {"id": voice_id, "name": name, "gender": gender, "engine": "piper",
            "language": language, "model": PIPER_MODELS[language], "mb": 60}


def kokoro_multi(language, speaker, name, gender):
    # the British voices (b...) are phonemized as British English
    code = {"en": "en-gb" if speaker.startswith("b") else "en-us", "es": "es"}[language]
    return {"id": speaker, "name": name, "gender": gender, "engine": "kokoro",
            "language": language, "files": KOKORO_MULTI, "speaker": speaker,
            "code": code, "mb": 353}


def kokoro_german(voice_id, name, gender, model_url, voices_url):
    files = ()
    if model_url and voices_url:
        files = (("de_DE-%s-kokoro.onnx" % voice_id, model_url),
                 ("%s_voices.npz" % voice_id, voices_url))
    return {"id": voice_id, "name": name, "gender": gender, "engine": "kokoro",
            "language": "de", "files": files, "speaker": voice_id, "code": "de",
            "mb": 325}


# the voices of each language, in the order the library shows them. The first
# one is the default: Piper, what was read with before anything was chosen.
# Picked by ear on 10-11-2026 from longer lists (see the git history).
CATALOG = {
    "de": [
        piper("de", "thorsten", "Thorsten", "m"),
        kokoro_german("victoria", "Victoria", "f",
                      VICTORIA_URL and VICTORIA_URL + "/de_DE-victoria-kokoro.onnx",
                      VICTORIA_URL and VICTORIA_URL + "/victoria_voices.npz"),
        kokoro_german("martin", "Martin", "m",
                      MARTIN_REPO + "/kokoro-martin.onnx",
                      MARTIN_REPO + "/voices-martin.npz"),
    ],
    "en": [
        piper("en", "lessac", "Lessac", "f"),
        kokoro_multi("en", "af_heart", "Heart", "f"),
        kokoro_multi("en", "af_bella", "Bella", "f"),
        kokoro_multi("en", "am_michael", "Michael", "m"),
        kokoro_multi("en", "am_fenrir", "Fenrir", "m"),
        kokoro_multi("en", "am_puck", "Puck", "m"),
        kokoro_multi("en", "bf_emma", "Emma", "f"),
        kokoro_multi("en", "bm_george", "George", "m"),
    ],
    "es": [
        piper("es", "davefx", "Dave", "m"),
        kokoro_multi("es", "ef_dora", "Dora", "f"),
        kokoro_multi("es", "em_alex", "Alex", "m"),
        kokoro_multi("es", "em_santa", "Santa", "m"),
    ],
}


def find(voice_id):
    for voices in CATALOG.values():
        for v in voices:
            if v["id"] == voice_id:
                return v
    return None


def offered(v):
    """Whether a voice can be picked: Kokoro needs somewhere to fetch it from."""
    return v["engine"] == "piper" or bool(v["files"])


def kokoro_path(name):
    return os.path.join(KOKORO_DIR, name)


def installed(v):
    """Whether everything the voice needs is on disk (Piper: model and .json)."""
    if v["engine"] == "piper":
        return os.path.isfile(v["model"]) and os.path.isfile(v["model"] + ".json")
    return bool(v["files"]) and all(os.path.isfile(kokoro_path(f)) for f, _ in v["files"])


def choices():
    try:
        with open(CHOICES_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        return saved if isinstance(saved, dict) else {}
    except (OSError, ValueError):
        return {}


def choose(language, voice_id):
    saved = choices()
    saved[language] = voice_id
    with open(CHOICES_FILE, "w", encoding="utf-8") as f:
        json.dump(saved, f)


def default(language):
    return CATALOG.get(language, CATALOG["en"])[0]


def current(language):
    """The voice to read this language with right now: the chosen one once it
    is fully downloaded, the default (Piper) until then."""
    v = find(choices().get(language, ""))
    if v and v["language"] == language and offered(v) and installed(v):
        return v
    return default(language)


# --- Kokoro ---------------------------------------------------------------

# one Kokoro per model file: the English and Spanish voices share one
KOKORO_MODELS = {}
KOKORO_RATE = 24000
# the gap left between the sentences of a paragraph
KOKORO_GAP_MS = 150
# Kokoro takes at most 510 phonemes at once and cuts the rest off; a sentence
# longer than this many characters is split again at its commas
KOKORO_CHUNK = 220


def kokoro_threads():
    """How many cores Kokoro works with. All of them is slower: on processors
    with fast and slow cores (an Intel Core Ultra, 20 of them) the fast ones
    wait for the slow ones. Measured on that one (10-11-2026): all 20 and
    spinning 2.3x real time, 12 without spinning 3.3x, 4 2.7x."""
    return max(2, min(12, (os.cpu_count() or 4) * 3 // 5))


def kokoro_model(v):
    import onnxruntime
    from kokoro_onnx import Kokoro

    model, pack = (kokoro_path(f) for f, _ in v["files"])
    if model not in KOKORO_MODELS:
        print("loading %s ..." % model)
        # KOKORO_MODELS[model] = Kokoro(model, pack)
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = kokoro_threads()
        # no busy-waiting between pieces: it kept every core at 100 % for nothing
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        session = onnxruntime.InferenceSession(model, sess_options=options,
                                               providers=["CPUExecutionProvider"])
        KOKORO_MODELS[model] = Kokoro.from_session(session, pack)
    return KOKORO_MODELS[model]


def sentences(text):
    """The pieces Kokoro reads one at a time. Whole paragraphs at once made the
    German voices buzz; their author reads sentence by sentence too. Line
    breaks and typographic quotes upset kokoro-onnx, so they go first."""
    text = re.sub("[«»‹›“”„\"]", ",", text.replace("\n", " "))
    pieces = []
    for s in re.split(r"(?<=[.!?:;])\s+(?=\S)", text):
        s = s.strip(" ,")
        while len(s) > KOKORO_CHUNK:
            cut = max(s.rfind(", ", 0, KOKORO_CHUNK), s.rfind(" ", 0, KOKORO_CHUNK))
            if cut <= 0:
                cut = KOKORO_CHUNK
            pieces.append(s[:cut].strip(" ,"))
            s = s[cut:].strip(" ,")
        if s:
            pieces.append(s)
    return pieces


def kokoro_pcm(v, text):
    import numpy as np

    k = kokoro_model(v)
    gap = np.zeros(KOKORO_RATE * KOKORO_GAP_MS // 1000, np.float32)
    parts = []
    for s in sentences(text):
        try:
            audio, _ = k.create(s, voice=v["speaker"], speed=1.0, lang=v["code"])
        except Exception as e:
            # a piece with nothing speakable in it ("•", "—"): skip it rather
            # than lose the whole paragraph
            print("  kokoro skipped %r: %s" % (s[:40], e))
            continue
        parts += [audio, gap]
    if not parts:
        return b""
    audio = np.clip(np.concatenate(parts), -1, 1)
    return (audio * 32767).astype(np.int16).tobytes()


# --- how fast each engine goes on this computer ----------------------------

# characters read per second of work. The start is what an Intel Core Ultra 7
# laptop did (10-11-2026: Piper 320, about 20x real time; Kokoro 50, about
# 3x), corrected with every paragraph actually read, so the time the MP3 says
# it will take is this computer's. Kept in voices.json too
SPEED_DEFAULT = {"piper": 320.0, "kokoro": 50.0}


def speed(engine):
    saved = choices().get("_speed", {})
    try:
        return float(saved.get(engine)) or SPEED_DEFAULT[engine]
    except (TypeError, ValueError):
        return SPEED_DEFAULT[engine]


def learn(engine, chars, seconds):
    """Fold one measured piece into the speed of an engine. Short pieces say
    little (loading, the gap), so only those of some length count."""
    if chars < 150 or seconds <= 0:
        return
    now = speed(engine) * 0.8 + (chars / seconds) * 0.2
    saved = choices()
    saved.setdefault("_speed", {})[engine] = round(now, 1)
    try:
        with open(CHOICES_FILE, "w", encoding="utf-8") as f:
            json.dump(saved, f)
    except OSError:
        pass


def seconds_for(engine, chars):
    return chars / speed(engine)


# --- both -----------------------------------------------------------------

def pcm(v, text, piper_voice):
    """Raw 16-bit mono samples for this text, and their sample rate.

    piper_voice is the loaded PiperVoice for a Piper voice (server.py loads and
    downloads those, as before), None for Kokoro."""
    if v["engine"] == "kokoro":
        return kokoro_pcm(v, text), KOKORO_RATE
    memory = io.BytesIO()
    with wave.open(memory, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(piper_voice.config.sample_rate)
        piper_voice.synthesize_wav(text, w, set_wav_format=False)
    memory.seek(0)
    with wave.open(memory, "rb") as r:
        return r.readframes(r.getnframes()), piper_voice.config.sample_rate


def public(language):
    """The voices of a language as the library page lists them."""
    chosen = choices().get(language)
    return [
        {"id": v["id"], "name": v["name"], "gender": v["gender"], "mb": v["mb"],
         "installed": installed(v), "chosen": v["id"] == chosen,
         "default": v is default(language)}
        for v in CATALOG.get(language, []) if offered(v)
    ]
