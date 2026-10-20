"""The reading page: layout, controls and bookmark.

Deliberately not an f-string. The CSS and the JavaScript are full of braces and
every one of them would have to be doubled, which is exactly the kind of detail
that slips through unnoticed. The placeholders are @TITLE@, @LANG@ and
<!--BODY-->, and reading_document() substitutes them.

@LANG@ is not decoration: the server reads it back out of this html to know
which Piper voice to read the book with, because when a book is opened off the
shelf the PDF need not still be there.

The page holds all of the reading state -- which paragraph is current, which
page is shown, what has already been synthesized. The server only turns text
into audio; see server.py.
"""

from icons import with_icons

# The words of the interface in English, German and Spanish. The language is
# the browser's (navigator.languages), falling back to English; it has nothing
# to do with the language of the book, which is <html lang> and picks the
# voice. Both pages carry this script (@I18N@) before their own:
#   tr("key", {name: ...})  a string, with {name} filled in
#   data-t="key"            on an element: its text
#   data-t-title="key"      its tooltip;  data-t-placeholder="key" likewise
# A key missing in one language falls back to the English text.
I18N = """
var UI_TEXT = {
  en: {
    toggle: "show or hide the books", library: "Library",
    lead: "Click a book to open it. It picks up where you left off.",
    addBook: "Add a book", startAt: "Start at page",
    startHint: "to skip the cover and the table of contents",
    fromFolder: "From a folder", choosePdf: "Choose a PDF…",
    dragHint: "or drag the PDF onto this box", fromPath: "From its path", add: "Add",
    deleteBook: "delete this book",
    confirmDelete: "Delete “{name}”? It is removed from this computer.",
    paragraph: "paragraph {n}", notStarted: "not started",
    preparing: "preparing… this takes a few minutes",
    empty: "No books yet. Add your first one below.",
    downloadingVoice: "Downloading the {language} voice… {p} % (only the first time)",
    serverAnswered: "the server answered {status}",
    beingPrepared: "“{name}” is being prepared. It will show up above when it is ready.",
    notPdf: "That is not a PDF.", uploading: "Uploading {name}…",
    pastePath: "Paste the path to the PDF first.",
    err_no_name: "that file has no usable name",
    err_exists: "“{name}” is already in the library",
    err_preparing: "“{name}” is already being prepared",
    err_no_book: "there is no such book to delete",
    err_not_found: "cannot find {name}", err_not_pdf: "that is not a pdf",
    lang_en: "English", lang_de: "German", lang_es: "Spanish",
    backLibrary: "back to the library", prevPage: "previous page", nextPage: "next page",
    colors: "colors", smaller: "smaller text", bigger: "bigger text",
    narrower: "narrower column", wider: "wider column",
    background: "Background", text: "Text", highlight: "Highlight", reset: "Reset",
    themeDefault: "Default",
    prevParagraph: "previous paragraph", nextParagraph: "next paragraph",
    stop: "stop and release the audio", slower: "slower", faster: "faster",
    read: "Read", pause: "Pause", bookmark: "paragraph {n} of {total}",
    downloadingVoiceShort: "downloading the voice… {p} % (only the first time)",
    noAudio: "no audio: start server.py ({message})",
    search: "search the book (Ctrl+F)", searchPlaceholder: "Search the book…",
    noMatches: "nothing found", matches: "{n} of {total}", pageShort: "p. {n}",
    prevMatch: "previous match (Shift+Enter)", nextMatch: "next match (Enter)",
    exportMp3: "Make MP3", exportMp3Title: "read the whole book into one MP3 file",
    exporting: "MP3 {p} %", downloadMp3: "Download MP3",
    mp3Failed: "Could not make the MP3", mp3Interrupted: "The MP3 was interrupted",
    retry: "Retry", err_exporting: "“{name}” is already being exported",
    audios: "Audios", saveMp3: "Save", deleteMp3: "delete the MP3",
    confirmDeleteMp3: "Delete the MP3 of “{name}”? You can make it again.",
    coffee: "Like ReadAloud? Buy me a coffee ☕", coffeeShort: "Buy me a coffee",
    coffeeAsk: "Did listening to your PDF help?",
    coffeeText: "ReadAloud is free. If it helped you, buy me a coffee.",
    tabBooks: "Books", tabHelp: "Help", filterBooks: "Search a book…",
    rateText: "Is ReadAloud helpful?", rateLink: "Rate it in the Microsoft Store",
    noAudios: "No MP3 yet. Use “Make MP3” on a book.",
    feedbackTitle: "Errors or suggestions",
    feedbackPlaceholder: "What went wrong, or what would you change?",
    feedbackEmail: "Your email, only if you want an answer",
    feedbackSend: "Send", feedbackSending: "Sending…",
    feedbackThanks: "Thanks! I read every message.",
    feedbackShort: "Write a little more first.",
    err_feedback_invalid: "Check the email address.",
    err_feedback_rate_limited: "Too many messages in a short time. Try again in an hour.",
    err_feedback_send_failed: "It could not be sent. Try again later.",
    err_feedback_offline: "No internet connection: it could not be sent."
  },
  de: {
    toggle: "Bücher ein- oder ausblenden", library: "Bibliothek",
    lead: "Klicke auf ein Buch, um es zu öffnen. Es geht dort weiter, wo du aufgehört hast.",
    addBook: "Buch hinzufügen", startAt: "Ab Seite",
    startHint: "um Titelseite und Inhaltsverzeichnis zu überspringen",
    fromFolder: "Aus einem Ordner", choosePdf: "PDF auswählen …",
    dragHint: "oder zieh die PDF-Datei in dieses Feld", fromPath: "Über den Pfad", add: "Hinzufügen",
    deleteBook: "dieses Buch löschen",
    confirmDelete: "„{name}“ löschen? Es wird von diesem Computer entfernt.",
    paragraph: "Absatz {n}", notStarted: "noch nicht begonnen",
    preparing: "wird vorbereitet … das dauert ein paar Minuten",
    empty: "Noch keine Bücher. Füge unten dein erstes hinzu.",
    downloadingVoice: "Die Stimme für {language} wird heruntergeladen … {p} % (nur beim ersten Mal)",
    serverAnswered: "der Server antwortete {status}",
    beingPrepared: "„{name}“ wird vorbereitet. Es erscheint oben, sobald es fertig ist.",
    notPdf: "Das ist keine PDF-Datei.", uploading: "{name} wird hochgeladen …",
    pastePath: "Füge zuerst den Pfad zur PDF-Datei ein.",
    err_no_name: "diese Datei hat keinen verwendbaren Namen",
    err_exists: "„{name}“ ist schon in der Bibliothek",
    err_preparing: "„{name}“ wird schon vorbereitet",
    err_no_book: "dieses Buch gibt es nicht",
    err_not_found: "{name} wurde nicht gefunden", err_not_pdf: "das ist keine PDF-Datei",
    lang_en: "Englisch", lang_de: "Deutsch", lang_es: "Spanisch",
    backLibrary: "zurück zur Bibliothek", prevPage: "vorherige Seite", nextPage: "nächste Seite",
    colors: "Farben", smaller: "kleinere Schrift", bigger: "größere Schrift",
    narrower: "schmalere Spalte", wider: "breitere Spalte",
    background: "Hintergrund", text: "Text", highlight: "Markierung", reset: "Zurücksetzen",
    themeDefault: "Standard",
    prevParagraph: "vorheriger Absatz", nextParagraph: "nächster Absatz",
    stop: "anhalten und Audio freigeben", slower: "langsamer", faster: "schneller",
    read: "Vorlesen", pause: "Pause", bookmark: "Absatz {n} von {total}",
    downloadingVoiceShort: "Stimme wird heruntergeladen … {p} % (nur beim ersten Mal)",
    noAudio: "kein Ton: starte server.py ({message})",
    search: "im Buch suchen (Strg+F)", searchPlaceholder: "Im Buch suchen …",
    noMatches: "nichts gefunden", matches: "{n} von {total}", pageShort: "S. {n}",
    prevMatch: "vorheriger Treffer (Umschalt+Enter)", nextMatch: "nächster Treffer (Enter)",
    exportMp3: "MP3 erstellen", exportMp3Title: "das ganze Buch in eine MP3-Datei vorlesen",
    exporting: "MP3 {p} %", downloadMp3: "MP3 herunterladen",
    mp3Failed: "Das MP3 konnte nicht erstellt werden", mp3Interrupted: "Das MP3 wurde unterbrochen",
    retry: "Erneut versuchen", err_exporting: "„{name}“ wird schon exportiert",
    audios: "Audios", saveMp3: "Speichern", deleteMp3: "das MP3 löschen",
    confirmDeleteMp3: "Das MP3 von „{name}“ löschen? Du kannst es wieder erstellen.",
    coffee: "Gefällt dir ReadAloud? Lad mich auf einen Kaffee ein ☕", coffeeShort: "Lad mich auf einen Kaffee ein",
    coffeeAsk: "Hat es dir geholfen, dein PDF zu hören?",
    coffeeText: "ReadAloud ist kostenlos. Wenn es dir geholfen hat, lad mich auf einen Kaffee ein.",
    tabBooks: "Bücher", tabHelp: "Hilfe", filterBooks: "Buch suchen …",
    rateText: "Ist ReadAloud hilfreich?", rateLink: "Im Microsoft Store bewerten",
    noAudios: "Noch kein MP3. Nutze „MP3 erstellen“ bei einem Buch.",
    feedbackTitle: "Fehler oder Vorschläge",
    feedbackPlaceholder: "Was ist schiefgelaufen oder was würdest du ändern?",
    feedbackEmail: "Deine E-Mail, nur wenn du eine Antwort willst",
    feedbackSend: "Senden", feedbackSending: "Wird gesendet …",
    feedbackThanks: "Danke! Ich lese jede Nachricht.",
    feedbackShort: "Schreib zuerst etwas mehr.",
    err_feedback_invalid: "Prüfe die E-Mail-Adresse.",
    err_feedback_rate_limited: "Zu viele Nachrichten in kurzer Zeit. Versuch es in einer Stunde wieder.",
    err_feedback_send_failed: "Konnte nicht gesendet werden. Versuch es später noch einmal.",
    err_feedback_offline: "Keine Internetverbindung: konnte nicht gesendet werden."
  },
  es: {
    toggle: "mostrar u ocultar los libros", library: "Biblioteca",
    lead: "Haz clic en un libro para abrirlo. Sigue donde lo dejaste.",
    addBook: "Añadir un libro", startAt: "Empezar en la página",
    startHint: "para saltarte la portada y el índice",
    fromFolder: "Desde una carpeta", choosePdf: "Elegir un PDF…",
    dragHint: "o arrastra el PDF a este recuadro", fromPath: "Desde su ruta", add: "Añadir",
    deleteBook: "borrar este libro",
    confirmDelete: "¿Borrar «{name}»? Se elimina de este ordenador.",
    paragraph: "párrafo {n}", notStarted: "sin empezar",
    preparing: "preparando… tarda unos minutos",
    empty: "Aún no hay libros. Añade el primero abajo.",
    downloadingVoice: "Descargando la voz en {language}… {p} % (solo la primera vez)",
    serverAnswered: "el servidor respondió {status}",
    beingPrepared: "«{name}» se está preparando. Aparecerá arriba cuando esté listo.",
    notPdf: "Eso no es un PDF.", uploading: "Subiendo {name}…",
    pastePath: "Primero pega la ruta del PDF.",
    err_no_name: "ese archivo no tiene un nombre válido",
    err_exists: "«{name}» ya está en la biblioteca",
    err_preparing: "«{name}» ya se está preparando",
    err_no_book: "ese libro no existe",
    err_not_found: "no se encuentra {name}", err_not_pdf: "eso no es un PDF",
    lang_en: "inglés", lang_de: "alemán", lang_es: "español",
    backLibrary: "volver a la biblioteca", prevPage: "página anterior", nextPage: "página siguiente",
    colors: "colores", smaller: "letra más pequeña", bigger: "letra más grande",
    narrower: "columna más estrecha", wider: "columna más ancha",
    background: "Fondo", text: "Texto", highlight: "Resaltado", reset: "Restablecer",
    themeDefault: "Predeterminado",
    prevParagraph: "párrafo anterior", nextParagraph: "párrafo siguiente",
    stop: "detener y liberar el audio", slower: "más lento", faster: "más rápido",
    read: "Leer", pause: "Pausa", bookmark: "párrafo {n} de {total}",
    downloadingVoiceShort: "descargando la voz… {p} % (solo la primera vez)",
    noAudio: "sin audio: inicia server.py ({message})",
    search: "buscar en el libro (Ctrl+F)", searchPlaceholder: "Buscar en el libro…",
    noMatches: "no se encontró nada", matches: "{n} de {total}", pageShort: "p. {n}",
    prevMatch: "resultado anterior (Mayús+Enter)", nextMatch: "resultado siguiente (Enter)",
    exportMp3: "Crear MP3", exportMp3Title: "leer el libro entero en un archivo MP3",
    exporting: "MP3 {p} %", downloadMp3: "Descargar MP3",
    mp3Failed: "No se pudo crear el MP3", mp3Interrupted: "El MP3 se interrumpió",
    retry: "Reintentar", err_exporting: "“{name}” ya se está exportando",
    audios: "Audios", saveMp3: "Guardar", deleteMp3: "borrar el MP3",
    confirmDeleteMp3: "¿Borrar el MP3 de “{name}”? Puedes crearlo otra vez.",
    coffee: "¿Te sirve ReadAloud? Invítame un café ☕", coffeeShort: "Invítame un café",
    coffeeAsk: "¿Te sirvió escuchar tu PDF?",
    coffeeText: "ReadAloud es gratis. Si te ayudó, invítame un café.",
    tabBooks: "Libros", tabHelp: "Ayuda", filterBooks: "Buscar un libro…",
    rateText: "¿Te sirve ReadAloud?", rateLink: "Valóralo en Microsoft Store",
    noAudios: "Todavía no hay MP3. Usa «Crear MP3» en un libro.",
    feedbackTitle: "Errores o sugerencias",
    feedbackPlaceholder: "¿Qué falló o qué cambiarías?",
    feedbackEmail: "Tu email, solo si quieres respuesta",
    feedbackSend: "Enviar", feedbackSending: "Enviando…",
    feedbackThanks: "¡Gracias! Leo todos los mensajes.",
    feedbackShort: "Escribe un poco más primero.",
    err_feedback_invalid: "Revisa el email.",
    err_feedback_rate_limited: "Demasiados mensajes seguidos. Inténtalo dentro de una hora.",
    err_feedback_send_failed: "No se pudo enviar. Inténtalo más tarde.",
    err_feedback_offline: "Sin conexión a internet: no se pudo enviar."
  }
};
// Which language: the one chosen in the library (EN · DE · ES, kept in
// localStorage, which the book pages share), else the language of Windows
// (the server writes it into the library page), else the browser's. Brave or
// Chrome often list English first even on a Spanish Windows, so the browser
// alone is not a good guess for a desktop program.
var UI_LANG = (function () {
  var chosen = null, current = null;
  try {
    chosen = localStorage.getItem("ui:lang");          // picked with EN · DE · ES
    current = localStorage.getItem("ui:lang:current"); // what the library used last
  } catch (e) {}
  var wanted = [chosen, typeof SYSTEM_LANG === "string" ? SYSTEM_LANG : null, current]
    .concat(navigator.languages || [navigator.language || "en"]);
  for (var i = 0; i < wanted.length; i++) {
    var code = String(wanted[i] || "").slice(0, 2).toLowerCase();
    if (UI_TEXT[code]) return code;
  }
  return "en";
})();
// the book pages cannot ask the server for the Windows language (they are
// plain files), so the library leaves its decision here for them. chosen:
// picked by hand, which then wins over Windows from now on
function rememberLang(code, chosen) {
  try {
    localStorage.setItem("ui:lang:current", code);
    if (chosen) localStorage.setItem("ui:lang", code);
  } catch (e) {}
}
function tr(key, vars) {
  var s = UI_TEXT[UI_LANG][key];
  if (s === undefined) s = UI_TEXT.en[key];
  if (s === undefined) return key;
  return s.replace(/\\{(\\w+)\\}/g, function (m, k) {
    return vars && vars[k] !== undefined ? vars[k] : m;
  });
}
// an error from the server: its code, translated, or its English message
function trError(body, status) {
  if (body && body.code) return tr("err_" + body.code, { name: body.name || "" });
  return (body && body.error) || tr("serverAnswered", { status: status });
}
(function () {
  function each(attr, fn) {
    Array.prototype.forEach.call(document.querySelectorAll("[" + attr + "]"), function (el) {
      fn(el, tr(el.getAttribute(attr)));
    });
  }
  each("data-t", function (el, s) { el.textContent = s; });
  each("data-t-title", function (el, s) { el.title = s; });
  each("data-t-placeholder", function (el, s) { el.placeholder = s; });
})();
"""


def with_i18n(page):
    """Put the interface translations where the page has @I18N@."""
    return page.replace("@I18N@", I18N)


TEMPLATE = """<!DOCTYPE html>
<html lang="@LANG@">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- ?v=4: the browser keeps favicons in a cache of their own that neither
     Ctrl+F5 nor clearing the cache empties; a new address makes it fetch the
     current icon. Bump it whenever assets/readaloud.png changes. -->
<link rel="icon" type="image/png" href="/favicon.ico?v=4">
<title>@TITLE@</title>
<style>
:root {
  --bg: #14161a;
  --ink: #d8d4cc;
  --muted: #7d8590;
  --mark: #2b3a2f;
  --heading: #e8e4dc;
  --border: #262a31;
  --text-size: 18px;
  --width: 70ch;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Georgia, "Times New Roman", serif;
  font-size: var(--text-size);
  line-height: 1.6;
}
main {
  max-width: var(--width);
  margin: 0 auto;
  padding: 5rem 1.2rem 8rem;
}

/* only the current page is displayed: the whole book at once is some 4000
   blocks, which no browser lays out pleasantly */
.page { display: none; }
.page.active { display: block; }

p { margin: 0 0 1.2em; }
h3 {
  /* the section headings of the book. they carry data-i just like the
     paragraphs, so they are read out loud and can be bookmarked too */
  font-family: system-ui, sans-serif;
  font-size: 1.05em;
  font-weight: 600;
  color: var(--heading);
  margin: 2.2em 0 .8em;
}
.page > h3:first-child { margin-top: 0; }
pre {
  /* code is monospaced and never re-wrapped: the indentation is syntax, so it
     scrolls sideways rather than being reflowed */
  background: #0e1013;
  color: #cfe3d0;
  border-left: 3px solid #3c4a3f;
  padding: .7em 1em;
  margin: 0 0 1.2em;
  overflow-x: auto;
  font-family: "Cascadia Mono", Consolas, monospace;
  font-size: .9em;
  line-height: 1.45;
}
img {
  /* figures are black strokes on white: left exactly as they are so as not to
     misrepresent the original, but centered and kept inside the column. hence
     the white backdrop, which also keeps them legible on the dark page */
  display: block;
  max-width: 100%;
  margin: 1.6em auto;
  background: #fff;
  border-radius: 4px;
  padding: .5em;
}

/* the paragraph being spoken right now */
p[data-i], pre[data-i] {
  cursor: pointer;
  border-radius: 3px;
  transition: background .15s;
}
.reading {
  background: var(--mark);
  box-shadow: 0 0 0 .45em var(--mark);
}
.loading { opacity: .55; }

.bar {
  position: fixed;
  left: 0;
  right: 0;
  background: #10121580;
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: .6rem;
  padding: .55rem .9rem;
  font-family: system-ui, sans-serif;
  font-size: 14px;
  color: var(--muted);
}
.bar.top { top: 0; }
.bar.bottom {
  bottom: 0;
  top: auto;
  border-bottom: 0;
  border-top: 1px solid var(--border);
  justify-content: center;
}
button {
  background: #1b1f26;
  color: var(--ink);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .4rem .7rem;
  font: inherit;
  cursor: pointer;
}
button:hover { background: #232833; }
button:disabled { opacity: .4; cursor: default; }
.home {
  display: inline-flex;
  align-items: center;
  color: var(--ink);
  text-decoration: none;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .4rem .7rem;
  background: #1b1f26;
}
.home .icon { width: 1.1em; height: 1.1em; }
.home:hover { background: #232833; }
#play { min-width: 4.2rem; font-weight: 600; }
#speed { min-width: 3em; text-align: center; font-variant-numeric: tabular-nums; }
.spacer { flex: 1; }
#notice { color: #d98b8b; }
#notice.info { color: #8fbf8f; }
#colors .icon { width: 1.1em; height: 1.1em; vertical-align: -.2em; }

/* the colors panel, opened from the palette button */
.panel {
  position: fixed;
  top: 3.4rem;
  right: .9rem;
  width: 17rem;
  display: grid;
  gap: .7rem;
  padding: .9rem;
  background: #1b1f26;
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 10px 30px #0008;
  font-family: system-ui, sans-serif;
  font-size: 14px;
  color: #d8d4cc;
}
.panel[hidden] { display: none; }
.panel .themes { display: grid; grid-template-columns: 1fr 1fr; gap: .4rem; }
.panel .theme { display: flex; align-items: center; gap: .45rem; text-align: left; }
.swatch {
  display: inline-block;
  width: 1.1em;
  height: 1.1em;
  border-radius: 50%;
  border: 2px solid;
  flex: none;
}
.panel label { display: flex; align-items: center; justify-content: space-between; }
.panel input[type=color] {
  width: 2.6rem;
  height: 1.8rem;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: none;
  cursor: pointer;
}

/* the search panel. the browser's own Ctrl+F only sees the page on screen,
   since the others are display: none, so the book is searched here instead */
#search .icon { width: 1.1em; height: 1.1em; vertical-align: -.2em; }
.panel.find { width: 24rem; max-height: 70vh; grid-template-rows: auto auto 1fr; }
.find .row { display: flex; gap: .4rem; align-items: center; }
.find input[type=search] {
  flex: 1;
  min-width: 0;
  background: #0e1013;
  color: inherit;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .4rem .6rem;
  font: inherit;
}
.find .count { color: #7d8590; font-variant-numeric: tabular-nums; }
.find ol { list-style: none; margin: 0; padding: 0; overflow-y: auto; }
.find li {
  padding: .35rem .5rem;
  border-radius: 6px;
  cursor: pointer;
  line-height: 1.4;
}
.find li:hover, .find li.on { background: #232833; }
.find li .where { color: #7d8590; margin-right: .4em; }
.find li b { color: #f0d67a; font-weight: 600; }
/* the match inside the book, drawn without touching the text: the paragraph's
   textContent is what gets read out loud */
::highlight(match) { background: #f0d67a; color: #14161a; }
</style>
</head>
<body>

<div class="bar top">
  <a class="home" href="/" title="back to the library" data-t-title="backLibrary">@ICON:library-big@</a>
  <button id="prev" title="previous page" data-t-title="prevPage">&lsaquo;</button>
  <span id="page-number">1 / 1</span>
  <button id="next" title="next page" data-t-title="nextPage">&rsaquo;</button>
  <span class="spacer"></span>
  <span id="notice"></span>
  <button id="search" title="search the book (Ctrl+F)" data-t-title="search">@ICON:search@</button>
  <button id="colors" title="colors" data-t-title="colors">@ICON:palette@</button>
  <button id="smaller" title="smaller text" data-t-title="smaller">A-</button>
  <button id="bigger" title="bigger text" data-t-title="bigger">A+</button>
  <button id="narrower" title="narrower column" data-t-title="narrower">&#8677;&#8676;</button>
  <button id="wider" title="wider column" data-t-title="wider">&#8676;&#8677;</button>
</div>

<div class="panel" id="panel" hidden>
  <div class="themes" id="themes"></div>
  <label><span data-t="background">Background</span> <input type="color" id="c-bg"></label>
  <label><span data-t="text">Text</span> <input type="color" id="c-ink"></label>
  <label><span data-t="highlight">Highlight</span> <input type="color" id="c-mark"></label>
  <button id="c-reset" data-t="reset">Reset</button>
</div>

<div class="panel find" id="find" hidden>
  <div class="row">
    <input type="search" id="query" placeholder="Search the book…" data-t-placeholder="searchPlaceholder" autocomplete="off">
    <button id="match-prev" title="previous match (Shift+Enter)" data-t-title="prevMatch">&uarr;</button>
    <button id="match-next" title="next match (Enter)" data-t-title="nextMatch">&darr;</button>
  </div>
  <span class="count" id="match-count"></span>
  <ol id="results"></ol>
</div>

<main><!--BODY--></main>

<div class="bar bottom">
  <button id="back" title="previous paragraph" data-t-title="prevParagraph">&#9198;</button>
  <button id="play" data-t="read">Read</button>
  <button id="forward" title="next paragraph" data-t-title="nextParagraph">&#9197;</button>
  <button id="stop" title="stop and release the audio" data-t-title="stop">&#9209;</button>
  <button id="slower" title="slower" data-t-title="slower">&minus;</button>
  <span id="speed">1.0&times;</span>
  <button id="faster" title="faster" data-t-title="faster">+</button>
  <span id="bookmark"></span>
</div>

<!-- the interface in the browser's language (I18N in template.py) -->
<script>@I18N@</script>
<script>
"use strict";

// every block that can be read out loud, in reading order. figures carry no
// data-i, so they are skipped without having to be filtered out.
var blocks = Array.prototype.slice.call(document.querySelectorAll("[data-i]"));
var pages = Array.prototype.slice.call(document.querySelectorAll(".page"));
var key = "reader:" + location.pathname;

var current = 0;
var page = 0;
var playing = false;
var audio = new Audio();
var nextWav = null;   // the block after this one, already synthesized
var loaded = -1;      // which block the loaded audio belongs to

function save() {
  localStorage.setItem(key, String(current));
}

function remember() {
  var n = parseInt(localStorage.getItem(key), 10);
  return isNaN(n) ? 0 : Math.min(n, blocks.length - 1);
}

// turning the page by hand takes the reading point with it: if you are looking
// at page 5 and press play, it has to start on page 5 and not wherever the
// bookmark was left
function showPage(n, byHand) {
  if (n < 0 || n >= pages.length) return;
  pages.forEach(function (p, i) { p.classList.toggle("active", i === n); });
  page = n;
  // the number shown is the page number from the pdf, not the index of the
  // section: pages with no text never produce a section, so counting sections
  // would show a number that is not in the book
  document.getElementById("page-number").textContent =
    pages[n].getAttribute("data-page") + " / " +
    pages[pages.length - 1].getAttribute("data-page");
  document.getElementById("prev").disabled = n === 0;
  document.getElementById("next").disabled = n === pages.length - 1;
  if (byHand) {
    var first = pages[n].querySelector("[data-i]");
    if (first) {
      current = blocks.indexOf(first);
      drawBookmark();
      highlight();
      save();
    }
  }
}

function pageOf(block) {
  return pages.indexOf(block.closest(".page"));
}

function highlight() {
  blocks.forEach(function (b) { b.classList.remove("reading"); });
  if (blocks[current]) blocks[current].classList.add("reading");
}

function drawBookmark() {
  document.getElementById("bookmark").textContent =
    tr("bookmark", { n: current + 1, total: blocks.length });
}

function goTo(i, scroll) {
  var b = blocks[i];
  if (!b) return;
  current = i;
  var p = pageOf(b);
  if (p !== page) showPage(p);
  highlight();
  if (scroll) b.scrollIntoView({ block: "center", behavior: "smooth" });
  drawBookmark();
  save();
}

// piper synthesizes on demand: the browser asks for the wav of a block and the
// server returns it. the next one is fetched while this one plays, or the
// silence between paragraphs is audible.
function fetchWav(i) {
  if (i < 0 || i >= blocks.length) return Promise.resolve(null);
  // the server knows nothing about the book: it gets text and returns a wav.
  // the language goes along because one server now reads books in several
  var url = "/tts?lang=" + encodeURIComponent(document.documentElement.lang);
  return fetch(url, { method: "POST", body: blocks[i].textContent })
    .then(function (r) {
      if (!r.ok) throw new Error(tr("serverAnswered", { status: r.status }));
      return r.blob();
    })
    .then(function (b) { return URL.createObjectURL(b); });
}

function preload(i) {
  if (nextWav && nextWav.i === i) return;
  if (nextWav) URL.revokeObjectURL(nextWav.url);
  nextWav = null;
  fetchWav(i).then(function (url) {
    if (url) nextWav = { i: i, url: url };
  }).catch(function () {});
}

// while a paragraph is being waited for, the voice may still be downloading
// (the first time a language is read): show how far along it is, or the
// reader just looks stuck. Asks the server once a second until it arrives
var watching = null;
function watchDownload(on) {
  var notice = document.getElementById("notice");
  if (!on) {
    clearInterval(watching);
    watching = null;
    if (notice.classList.contains("info")) { notice.textContent = ""; notice.classList.remove("info"); }
    return;
  }
  if (watching) return;
  watching = setInterval(function () {
    fetch("/library").then(function (r) { return r.json(); }).then(function (d) {
      if (!watching || !d.download || !d.download.language) return;
      notice.classList.add("info");
      notice.textContent = tr("downloadingVoiceShort", { p: d.download.percent || 0 });
    }).catch(function () {});
  }, 1000);
}

function playBlock(i) {
  if (i < 0 || i >= blocks.length) { stop(); return; }
  current = i;
  goTo(i, true);
  var ready;
  if (nextWav && nextWav.i === i) {
    ready = Promise.resolve(nextWav.url);
    nextWav = null;
  } else {
    blocks[i].classList.add("loading");
    watchDownload(true);
    ready = fetchWav(i);
  }
  ready.then(function (url) {
    watchDownload(false);
    blocks[i].classList.remove("loading");
    if (!playing) return;
    audio.src = url;
    // a new src resets playbackRate to the default in some browsers, so it is
    // set again on every paragraph
    audio.playbackRate = speed;
    loaded = i;
    audio.play();
    preload(i + 1);
  }).catch(function (e) {
    watchDownload(false);
    blocks[i].classList.remove("loading");
    playing = false;
    drawPlay();
    document.getElementById("notice").textContent =
      tr("noAudio", { message: e.message });
  });
}

audio.addEventListener("ended", function () {
  if (playing) playBlock(current + 1);
});

function drawPlay() {
  document.getElementById("play").textContent = playing ? tr("pause") : tr("read");
}

function play() {
  if (nextWav && nextWav.i !== current) {
    URL.revokeObjectURL(nextWav.url);
    nextWav = null;
  }
  if (playing) {
    playing = false;
    audio.pause();
  } else {
    playing = true;
    // only resume if the paused audio belongs to the paragraph we are on; if
    // you have moved elsewhere the new one has to be synthesized
    if (loaded === current && audio.currentTime > 0 && !audio.ended) audio.play();
    else playBlock(current);
  }
  drawPlay();
}

function stop() {
  playing = false;
  audio.pause();
  audio.currentTime = 0;
  drawPlay();
}

function step(n) {
  audio.pause();
  var i = Math.max(0, Math.min(blocks.length - 1, current + n));
  if (playing) playBlock(i);
  else { current = i; goTo(i, true); }
}

document.getElementById("play").onclick = play;
document.getElementById("stop").onclick = stop;
document.getElementById("back").onclick = function () { step(-1); };
document.getElementById("forward").onclick = function () { step(1); };
document.getElementById("prev").onclick = function () { showPage(page - 1, true); };
document.getElementById("next").onclick = function () { showPage(page + 1, true); };

// clicking a paragraph starts reading right there
blocks.forEach(function (b) {
  b.onclick = function () {
    // not data-i: that counts the figures too, and this array does not
    current = blocks.indexOf(b);
    if (playing) playBlock(current);
    else goTo(current, false);
  };
});

function adjust(prop, step, minimum, maximum, unit) {
  var root = document.documentElement;
  var v = parseFloat(getComputedStyle(root).getPropertyValue(prop));
  v = Math.max(minimum, Math.min(maximum, v + step));
  root.style.setProperty(prop, v + unit);
  localStorage.setItem(key + prop, v + unit);
}
document.getElementById("bigger").onclick = function () { adjust("--text-size", 1, 12, 32, "px"); };
document.getElementById("smaller").onclick = function () { adjust("--text-size", -1, 12, 32, "px"); };
document.getElementById("wider").onclick = function () { adjust("--width", 5, 40, 120, "ch"); };
document.getElementById("narrower").onclick = function () { adjust("--width", -5, 40, 120, "ch"); };

// the speed is changed in the browser, not in piper: the same wav is just
// played faster, so the cache stays valid and nothing is re-synthesized.
// browsers keep the pitch by default, so the voice does not turn into a chipmunk
var speed = 1;
function setSpeed(v) {
  speed = Math.round(Math.max(0.5, Math.min(2.5, v)) * 10) / 10;
  audio.defaultPlaybackRate = speed;
  audio.playbackRate = speed;
  document.getElementById("speed").textContent = speed.toFixed(1) + "\\u00d7";
  localStorage.setItem("reader:speed", String(speed));
}
document.getElementById("slower").onclick = function () { setSpeed(speed - 0.1); };
document.getElementById("faster").onclick = function () { setSpeed(speed + 0.1); };
// kept for every book rather than per book: it is a property of the listener
setSpeed(parseFloat(localStorage.getItem("reader:speed")) || 1);

// colors, like a colorscheme in an editor: a few ready-made themes, and the
// three colors that matter can each be picked by hand. kept for every book
var THEMES = {
  "Default":     { bg: "#14161a", ink: "#d8d4cc", mark: "#2b3a2f" },
  "Gruvbox":     { bg: "#282828", ink: "#ebdbb2", mark: "#504945" },
  "Tokyo Night": { bg: "#1a1b26", ink: "#c0caf5", mark: "#33467c" },
  "Catppuccin":  { bg: "#1e1e2e", ink: "#cdd6f4", mark: "#45475a" },
  "Nord":        { bg: "#2e3440", ink: "#d8dee9", mark: "#434c5e" },
  "Dracula":     { bg: "#282a36", ink: "#f8f8f2", mark: "#44475a" }
};
var colors = THEMES.Default;

function setColors(c) {
  colors = { bg: c.bg, ink: c.ink, mark: c.mark };
  var root = document.documentElement.style;
  root.setProperty("--bg", colors.bg);
  root.setProperty("--ink", colors.ink);
  // the headings follow the text, or they stay light on a light background.
  // with the default text they keep their own, slightly brighter color
  if (colors.ink === THEMES.Default.ink) root.removeProperty("--heading");
  else root.setProperty("--heading", colors.ink);
  root.setProperty("--mark", colors.mark);
  document.getElementById("c-bg").value = colors.bg;
  document.getElementById("c-ink").value = colors.ink;
  document.getElementById("c-mark").value = colors.mark;
  try { localStorage.setItem("reader:colors", JSON.stringify(colors)); } catch (e) {}
}

Object.keys(THEMES).forEach(function (name) {
  var t = THEMES[name];
  var b = document.createElement("button");
  b.className = "theme";
  var s = document.createElement("span");
  s.className = "swatch";
  s.style.background = t.bg;
  s.style.borderColor = t.mark;
  b.appendChild(s);
  // "Default" is a word; the others are the names of well-known color schemes
  b.appendChild(document.createTextNode(name === "Default" ? tr("themeDefault") : name));
  b.onclick = function () { setColors(t); };
  document.getElementById("themes").appendChild(b);
});
["bg", "ink", "mark"].forEach(function (k) {
  document.getElementById("c-" + k).addEventListener("input", function () {
    var c = { bg: colors.bg, ink: colors.ink, mark: colors.mark };
    c[k] = this.value;
    setColors(c);
  });
});
document.getElementById("c-reset").onclick = function () { setColors(THEMES.Default); };

var panel = document.getElementById("panel");
document.getElementById("colors").onclick = function (e) {
  e.stopPropagation();
  panel.hidden = !panel.hidden;
};
// a click anywhere else closes it, but not a click inside it
panel.addEventListener("click", function (e) { e.stopPropagation(); });
document.addEventListener("click", function () { panel.hidden = true; });

try {
  var savedColors = JSON.parse(localStorage.getItem("reader:colors"));
  if (savedColors && savedColors.bg) colors = savedColors;
} catch (e) {}
setColors(colors);

["--text-size", "--width"].forEach(function (prop) {
  var v = localStorage.getItem(key + prop);
  if (v) document.documentElement.style.setProperty(prop, v);
});

// searching the whole book. Ctrl+F in the browser only finds what is on the
// page being shown, so it is taken over here. Case and accents are ignored:
// "qualitat" finds "Qualität", which matters when typing German on a Spanish
// keyboard. fold() keeps, for every folded character, where it came from, so
// the match can be marked in the original text.
var find = document.getElementById("find");
var query = document.getElementById("query");
var matches = [];   // {b: index into blocks, start, end} in the block's text
var shown = -1;     // which of them is on screen

function fold(s) {
  var text = "", from = [];
  for (var k = 0; k < s.length; k++) {
    var f = s[k].normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLowerCase();
    for (var j = 0; j < f.length; j++) { text += f[j]; from.push(k); }
  }
  from.push(s.length);
  return { text: text, from: from };
}

// folded once, the first time something is searched, not on every key
var folded = null;
function search(q) {
  var needle = fold(q.trim()).text;
  matches = [];
  if (needle.length >= 2) {
    if (!folded) folded = blocks.map(function (b) { return fold(b.textContent); });
    folded.forEach(function (f, b) {
      var at = f.text.indexOf(needle);
      while (at !== -1) {
        matches.push({ b: b, start: f.from[at], end: f.from[at + needle.length] });
        at = f.text.indexOf(needle, at + needle.length);
      }
    });
  }
  // the first match from where you are reading on, not from the cover
  shown = -1;
  for (var m = 0; m < matches.length; m++) {
    if (matches[m].b >= current) { shown = m; break; }
  }
  if (shown === -1 && matches.length) shown = 0;
  drawResults(needle.length >= 2);
  if (shown !== -1) showMatch(shown, false);
  else markMatch(null);
}

// a list of every match: the page, and the words around it
var LISTED = 300;
function drawResults(searched) {
  var list = document.getElementById("results");
  list.textContent = "";
  matches.slice(0, LISTED).forEach(function (m, n) {
    var text = blocks[m.b].textContent;
    var li = document.createElement("li");
    var where = document.createElement("span");
    where.className = "where";
    where.textContent = tr("pageShort", { n: blocks[m.b].closest(".page").getAttribute("data-page") });
    li.appendChild(where);
    var a = Math.max(0, m.start - 40), z = Math.min(text.length, m.end + 60);
    li.appendChild(document.createTextNode((a > 0 ? "…" : "") + text.slice(a, m.start)));
    var hit = document.createElement("b");
    hit.textContent = text.slice(m.start, m.end);
    li.appendChild(hit);
    li.appendChild(document.createTextNode(text.slice(m.end, z) + (z < text.length ? "…" : "")));
    li.onclick = function () { showMatch(n, true); };
    list.appendChild(li);
  });
  drawCount(searched);
}

function drawCount(searched) {
  document.getElementById("match-count").textContent = !searched ? "" :
    matches.length ? tr("matches", { n: shown + 1, total: matches.length }) : tr("noMatches");
}

// the match is drawn with the CSS Custom Highlight API, which leaves the DOM
// alone; a browser without it still jumps to the right paragraph
function markMatch(m) {
  if (!window.CSS || !CSS.highlights) return;
  CSS.highlights.delete("match");
  if (!m) return;
  var walker = document.createTreeWalker(blocks[m.b], NodeFilter.SHOW_TEXT);
  var range = document.createRange(), seen = 0, node, started = false;
  while ((node = walker.nextNode())) {
    var len = node.nodeValue.length;
    if (!started && m.start <= seen + len) { range.setStart(node, m.start - seen); started = true; }
    if (started && m.end <= seen + len) { range.setEnd(node, m.end - seen); break; }
    seen += len;
  }
  if (started) CSS.highlights.set("match", new Highlight(range));
}

// going through the matches only looks, so typing a search does not lose the
// bookmark; clicking one in the list moves the reading point there, just like
// clicking the paragraph itself
function showMatch(n, fromList) {
  if (!matches.length) return;
  shown = (n + matches.length) % matches.length;
  var m = matches[shown];
  if (fromList && playing) playBlock(m.b);
  else if (fromList) goTo(m.b, true);
  else {
    var p = pageOf(blocks[m.b]);
    if (p !== page) showPage(p);
    blocks[m.b].scrollIntoView({ block: "center", behavior: "smooth" });
  }
  markMatch(m);
  var items = document.getElementById("results").children;
  Array.prototype.forEach.call(items, function (li, i) { li.classList.toggle("on", i === shown); });
  if (items[shown] && !fromList) items[shown].scrollIntoView({ block: "nearest" });
  drawCount(true);
}

function openFind() {
  panel.hidden = true;
  find.hidden = false;
  query.focus();
  query.select();
}
function closeFind() {
  find.hidden = true;
  markMatch(null);
  query.blur();
}

// searched on a pause in typing, not on every key
var typing = null;
query.addEventListener("input", function () {
  clearTimeout(typing);
  typing = setTimeout(function () { typing = null; search(query.value); }, 150);
});
query.addEventListener("keydown", function (e) {
  if (e.key === "Enter") {
    e.preventDefault();
    // Enter before the pause: search now rather than step past the first match
    if (typing !== null) { clearTimeout(typing); typing = null; search(query.value); }
    else showMatch(shown + (e.shiftKey ? -1 : 1), false);
  } else if (e.key === "Escape") closeFind();
});
document.getElementById("match-prev").onclick = function () { showMatch(shown - 1, false); };
document.getElementById("match-next").onclick = function () { showMatch(shown + 1, false); };
document.getElementById("search").onclick = function (e) {
  e.stopPropagation();
  if (find.hidden) openFind(); else closeFind();
};
find.addEventListener("click", function (e) { e.stopPropagation(); });
// the colors button closes it, as a click anywhere else closes the colors
document.getElementById("colors").addEventListener("click", function () { find.hidden = true; });

document.addEventListener("keydown", function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
    e.preventDefault();
    openFind();
    return;
  }
  // typing in the search box is not a command for the reader
  if (e.target.tagName === "INPUT") return;
  if (e.key === "Escape" && !find.hidden) closeFind();
  else if (e.key === " ") { e.preventDefault(); play(); }
  else if (e.key === "ArrowRight") step(1);
  else if (e.key === "ArrowLeft") step(-1);
  else if (e.key === "PageDown") showPage(page + 1, true);
  else if (e.key === "PageUp") showPage(page - 1, true);
  else if (e.key === "+" || e.key === "=") setSpeed(speed + 0.1);
  else if (e.key === "-") setSpeed(speed - 0.1);
});

showPage(0);
current = remember();
goTo(current, true);
</script>
</body>
</html>
"""


# The library: one folder per book, and a way in for new ones. The list of
# books is fetched from GET /library rather than written in, so the same page
# can keep refreshing itself while a new book is being prepared. The only
# placeholders are the @ICON:name@ ones, filled in by with_icons() below.
SHELF = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<!-- ?v=4: see the note in TEMPLATE above -->
<link rel="icon" type="image/png" href="/favicon.ico?v=4">
<title>Library</title>
<style>
:root {
  --bg: #14161a;
  --ink: #d8d4cc;
  --muted: #7d8590;
  --border: #262a31;
  --card: #1b1f26;
  --card-hover: #232833;
  /* the green of dravvt (the brand, as on dravvt.com in dark mode) instead of
     the old folder yellow and soft green */
  /* --folder: #c9a55a; */
  /* --accent: #8fbf8f; */
  --folder: #00ff00;
  --accent: #00ff00;
  --error: #d98b8b;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: system-ui, sans-serif;
  font-size: 15px;
}
main { max-width: 1000px; margin: 0 auto; padding: 2.5rem 1rem 4rem; }
h1 {
  display: flex;
  align-items: center;
  gap: .5rem;
  font-size: 1.5rem;
  font-weight: 600;
  margin: 0 0 .3rem;
}
h1 .icon { width: 1.2em; height: 1.2em; color: var(--folder); }
/* the title folds the shelf away, so the whole page fits on one screen
h1 { cursor: pointer; user-select: none; } */
/* the tabs: Books, Audios, Help */
.tabs { display: flex; gap: .2rem; margin: 1.2rem 0 1.5rem; border-bottom: 1px solid var(--border); }
.tabs button {
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  margin-bottom: -1px;
  padding: .6rem .9rem;
  color: var(--muted);
}
.tabs button:hover { background: none; color: var(--ink); }
.tabs button.on { color: var(--accent); border-bottom-color: var(--accent); }
.tabs .n { font-size: .8em; }
.tabs { flex-wrap: wrap; align-items: center; }
/* the coffee, at the right of the tabs; on a narrow window it drops below */
.coffee-btn {
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  margin-left: auto;
  padding: .35rem .8rem;
  border: 1px solid var(--accent);
  border-radius: 999px;
  color: var(--accent);
  font-size: .85rem;
  text-decoration: none;
  white-space: nowrap;
}
.coffee-btn:hover { background: #00ff0014; }
.coffee-btn .icon, .coffee-box .icon { width: 16px; height: 16px; flex: none; }
.tabs .coffee-btn { margin-bottom: .4rem; }
/* the rating line in Help, under the form */
.rate-line { display: flex; align-items: center; gap: .4rem; margin: 0; color: var(--muted); font-size: .9rem; }
.rate-line .icon { width: 16px; height: 16px; color: #f0d67a; }
.rate-line a { color: var(--accent); text-decoration: none; }
.rate-line a:hover { text-decoration: underline; }
/* under the audios: the question, a line, and the same button */
.coffee-box {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .9rem;
  margin-top: 1rem;
  padding: .9rem 1rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
}
.coffee-box > .icon { width: 24px; height: 24px; color: var(--accent); }
.coffee-box .words { flex: 1; min-width: 14rem; display: grid; gap: .15rem; }
.coffee-box .words span { color: var(--muted); font-size: .9rem; }
/* the search and "+ Add a book", above the shelf */
.tools { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; margin: 0 0 1.2rem; }
.tools input[type=search] {
  flex: 1;
  min-width: 14rem;
  background: var(--bg);
  color: var(--ink);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .45rem .6rem;
  font: inherit;
}
#add { margin-bottom: 1.2rem; }
/* hidden wins over the display of .book (flex) or .add (grid), which would
   otherwise keep the filtered cards and the closed box on screen */
[hidden] { display: none !important; }
#message:empty { display: none; }
#message { margin: 0 0 1rem; }
h1 .chevron { display: flex; transition: transform .2s; }
h1 .chevron .icon { color: var(--muted); }
h1.open .chevron { transform: rotate(90deg); }
#count { color: var(--muted); font-weight: 400; font-size: .8em; }
/* folded, only the first row shows, however many books fit in it */
.shelf.folded {
  grid-template-rows: auto;
  grid-auto-rows: 0;
  row-gap: 0;
  overflow: hidden;
  /* room for the lift on hover, which the overflow would otherwise clip */
  padding-top: 3px;
  margin-top: -3px;
}
.lead { color: var(--muted); margin: 0 0 2rem; }
h2 { font-size: 1rem; font-weight: 600; margin: 2.5rem 0 1rem; color: var(--muted); }

.shelf {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 1rem;
}
.book {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: .5rem;
  padding: 1.1rem .8rem 1rem;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--ink);
  text-decoration: none;
  text-align: center;
  transition: background .15s, transform .15s;
  position: relative;
}
/* delete: only shows on the card under the mouse, so the shelf stays quiet */
.book .del {
  position: absolute;
  top: .35rem;
  right: .35rem;
  display: flex;
  padding: .3rem;
  border: 0;
  background: transparent;
  color: var(--muted);
  opacity: 0;
  transition: opacity .15s, color .15s;
}
.book:hover .del, .book .del:focus { opacity: 1; }
.book .del:hover { color: var(--error); background: #d98b8b1a; }
.book .del .icon { width: 16px; height: 16px; fill: none; stroke-width: 2; color: inherit; }
.book.failed .del { opacity: 1; }
#download {
  display: none;
  margin: 0 0 1.5rem;
  padding: .6rem .9rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--card);
  color: var(--accent);
  font-size: .9rem;
}
#download.on { display: block; }
a.book:hover { background: var(--card-hover); transform: translateY(-2px); }
.book .icon {
  width: 56px;
  height: 56px;
  color: var(--folder);
  /* fill: #c9a55a33; */
  /* the inside of the folder: the same green, faint */
  fill: #00ff001a;
  stroke-width: 1.5;
}
.book.busy .icon { color: var(--muted); fill: none; animation: pulse 1.4s ease-in-out infinite; }
.book.failed .icon { color: var(--error); fill: #d98b8b22; }
@keyframes pulse { 50% { opacity: .35; } }
.name {
  font-size: .92rem;
  line-height: 1.3;
  /* the long paper titles are cut at three lines, the full name is in the tooltip */
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}
.meta { font-size: .78rem; color: var(--muted); }
.lang {
  font-size: .7rem;
  font-weight: 600;
  letter-spacing: .05em;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: .05rem .35rem;
  margin-right: .3rem;
}
.failed .meta { color: var(--error); }
.empty { color: var(--muted); }
/* the MP3 of the whole book, under the name: a button to make it, its
   progress, the button to download it, or, in red, why it did not work */
.book .mp3 {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: .3rem;
  font-size: .78rem;
}
.book .mp3 button {
  display: flex;
  align-items: center;
  gap: .3rem;
  padding: .2rem .55rem;
  font-size: .78rem;
}
.book .mp3 .icon { width: 14px; height: 14px; fill: none; stroke-width: 2; color: inherit; }
.book .mp3 .progress { color: var(--accent); font-variant-numeric: tabular-nums; }
.book .mp3.bad { color: var(--error); }
.book .mp3 .detail { color: var(--muted); font-size: .7rem; word-break: break-word; }
/* the MP3s, one row each: the name, then the player, Save and delete */
.audios {
  list-style: none;
  margin: 0;
  padding: 0;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
}
.audios li { display: grid; gap: .5rem; padding: .8rem 1rem; }
.audios li + li { border-top: 1px solid var(--border); }
.audios .title { display: flex; align-items: center; gap: .3rem; font-size: .92rem; }
.audios .controls { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; }
/* .audios audio { flex: 1; min-width: 16rem; height: 36px; } */
/* the player drawn by the page (playerControls): the browser's is white */
.audios audio { display: none; }
.audios .player { flex: 1; min-width: 16rem; display: flex; align-items: center; gap: .6rem; }
.audios .play { width: 2.6rem; justify-content: center; }
.audios .speed { min-width: 3.8rem; justify-content: center; font-variant-numeric: tabular-nums; }
.audios .time { color: var(--muted); font-size: .8rem; font-variant-numeric: tabular-nums; }
.audios input[type=range] {
  flex: 1;
  min-width: 6rem;
  height: 6px;
  margin: 0;
  -webkit-appearance: none;
  appearance: none;
  border-radius: 3px;
  background: linear-gradient(to right, var(--accent) var(--p, 0%), var(--border) var(--p, 0%));
  cursor: pointer;
}
.audios input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border: 0;
  border-radius: 50%;
  background: var(--accent);
}
.audios input[type=range]::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border: 0;
  border-radius: 50%;
  background: var(--accent);
}
.audios button { display: flex; align-items: center; gap: .3rem; }
.audios .icon { width: 16px; height: 16px; fill: none; stroke-width: 2; color: inherit; }
.audios .del-mp3 { padding: .45rem; color: var(--muted); }
.audios .del-mp3:hover { color: var(--error); }
/* errors or suggestions, at the bottom, in a box like "Add a book" */
.feedback {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.2rem;
  display: grid;
  gap: .8rem;
  /* room for the signature fixed in the corner */
  margin-bottom: 3rem;
}
.feedback textarea {
  background: var(--bg);
  color: var(--ink);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .5rem .6rem;
  font: inherit;
  resize: vertical;
}
.feedback input[type=email] {
  flex: 1;
  min-width: 14rem;
  background: var(--bg);
  color: var(--ink);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .45rem .6rem;
  font: inherit;
}
.feedback .trap { position: absolute; left: -9999px; width: 1px; height: 1px; }
#fb-status { min-height: 1.2em; font-size: .9rem; }
#fb-status.bad { color: var(--error); }
#fb-status.good { color: var(--accent); }
.coffee-line { margin: .8rem 0 0; font-size: .9rem; }
.coffee-line a { color: var(--accent); text-decoration: none; }
.coffee-line a:hover { text-decoration: underline; }

.add {
  background: var(--card);
  border: 1px dashed #3a414c;
  border-radius: 10px;
  padding: 1.2rem;
  display: grid;
  gap: 1.1rem;
}
/* .add.dragging { border-color: var(--accent); background: #1c2620; } */
.add.dragging { border-color: var(--accent); background: #00ff000d; }
.option { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; }
.option b { min-width: 11rem; font-weight: 600; }
input[type=text], input[type=number] {
  background: var(--bg);
  color: var(--ink);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .45rem .6rem;
  font: inherit;
}
input[type=text] { flex: 1; min-width: 14rem; }
input[type=number] { width: 5rem; }
input[type=file] { display: none; }
button {
  background: #232833;
  color: var(--ink);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: .45rem .8rem;
  font: inherit;
  cursor: pointer;
}
button:hover { background: #2b3140; }
.hint { color: var(--muted); font-size: .85rem; }
#message { min-height: 1.2em; font-size: .9rem; }
#message.bad { color: var(--error); }
#message.good { color: var(--accent); }
/* 〰 dravvt · year, small, bottom right */
footer.brand {
  position: fixed;
  right: 1.25rem;
  bottom: .75rem;
  display: flex;
  align-items: center;
  gap: .4rem;
  font-size: .78rem;
  color: var(--muted);
}
footer.brand a { display: flex; align-items: center; gap: .4rem; color: inherit; text-decoration: none; }
footer.brand a:hover { color: var(--ink); }
footer.brand svg { width: 20px; height: 15px; }
footer.brand path { fill: none; stroke: var(--folder); stroke-width: 8; stroke-linecap: round; }
/* EN · DE · ES, top right: the chosen one lit */
.languages { float: right; display: flex; gap: .25rem; }
.languages button { padding: .2rem .5rem; font-size: .8rem; color: var(--muted); }
.languages button.on { color: var(--accent); border-color: var(--accent); }
</style>
</head>
<body>
<main>
  <div id="languages" class="languages"></div>
  <!-- <h1 id="toggle" title="show or hide the books" data-t-title="toggle"><span class="chevron">@ICON:chevron-right@</span>@ICON:library-big@ <span data-t="library">Library</span> <span id="count"></span></h1> -->
  <!-- the title no longer folds the shelf: with many books, the tabs and the
       search below are what keep the page short -->
  <h1>@ICON:library-big@ <span data-t="library">Library</span></h1>

  <!-- one page, three tabs: switching only hides the others, so an audio
       keeps playing while you look at the books -->
  <nav class="tabs" role="tablist">
    <button role="tab" data-tab="books"><span data-t="tabBooks">Books</span> <span class="n" id="count"></span></button>
    <button role="tab" data-tab="audios"><span data-t="audios">Audios</span> <span class="n" id="audio-count"></span></button>
    <button role="tab" data-tab="help" data-t="tabHelp">Help</button>
    <!-- not a tab: always in sight, and quiet (an outline, no fill) -->
    <a class="coffee-btn" href="@COFFEE@" target="_blank" rel="noopener">@ICON:coffee@ <span data-t="coffeeShort">Buy me a coffee</span></a>
  </nav>


  <!-- above the tabs' content: what the page says shows whatever tab is open -->
  <div id="download"></div>
  <div id="message"></div>

  <section class="tab" id="tab-books">
  <p class="lead" data-t="lead">Click a book to open it. It picks up where you left off.</p>
  <div class="tools">
    <input type="search" id="filter" placeholder="Search a book…" data-t-placeholder="filterBooks" autocomplete="off">
    <button id="add-toggle">+ <span data-t="addBook">Add a book</span></button>
  </div>

  <!-- <h2 data-t="addBook">Add a book</h2> -->
  <!-- opened with "+ Add a book", or by itself when the library is empty or a
       PDF is dragged over the page -->
  <div class="add" id="add" hidden>
    <div class="option">
      <b data-t="startAt">Start at page</b>
      <input type="number" id="start" value="1" min="1">
      <span class="hint" data-t="startHint">to skip the cover and the table of contents</span>
    </div>
    <div class="option">
      <b data-t="fromFolder">From a folder</b>
      <button id="browse" data-t="choosePdf">Choose a PDF&hellip;</button>
      <input type="file" id="file" accept=".pdf,application/pdf">
      <span class="hint" data-t="dragHint">or drag the PDF onto this box</span>
    </div>
    <div class="option">
      <b data-t="fromPath">From its path</b>
      <input type="text" id="path" placeholder="C:\\Users\\...\\book.pdf">
      <button id="add-path" data-t="add">Add</button>
    </div>
    <!-- <div id="message"></div>: moved above the tabs -->
  </div>

  <div class="shelf" id="shelf"></div>
  <p class="empty" id="no-match" hidden data-t="noMatches">nothing found</p>
  </section>

  <!-- the books that have their MP3, to listen to here or save -->
  <section class="tab" id="tab-audios" hidden>
    <p class="empty" id="no-audios" data-t="noAudios">No MP3 yet. Use “Make MP3” on a book.</p>
    <ul class="audios" id="audio-list"></ul>
    <!-- right after someone got something out of the program -->
    <!-- <p class="coffee-line"><a href="@COFFEE@" target="_blank" rel="noopener" data-t="coffee">Like ReadAloud? Buy me a coffee ☕</a></p> -->
    <!-- the moment people are glad their PDF became audio; only with audios -->
    <div class="coffee-box" id="coffee-box" hidden>
      @ICON:coffee@
      <div class="words">
        <b data-t="coffeeAsk">Did listening to your PDF help?</b>
        <span data-t="coffeeText">ReadAloud is free. If it helped you, buy me a coffee.</span>
      </div>
      <a class="coffee-btn" href="@COFFEE@" target="_blank" rel="noopener">@ICON:coffee@ <span data-t="coffeeShort">Buy me a coffee</span></a>
    </div>
  </section>

  <section class="tab" id="tab-help" hidden>
  <!-- errors and suggestions: server.py passes them to dravvt.com, which mails
       them. The email is optional, only to be able to answer -->
  <h2 data-t="feedbackTitle">Errors or suggestions</h2>
  <form class="feedback" id="feedback">
    <textarea id="fb-message" rows="4" maxlength="5000" placeholder="What went wrong, or what would you change?" data-t-placeholder="feedbackPlaceholder"></textarea>
    <div class="option">
      <input type="email" id="fb-email" maxlength="200" placeholder="Your email, only if you want an answer" data-t-placeholder="feedbackEmail">
      <!-- the trap for bots, as in the site's contact form: people never see it -->
      <input type="text" id="fb-website" class="trap" tabindex="-1" autocomplete="off" aria-hidden="true">
      <button type="submit" id="fb-send" data-t="feedbackSend">Send</button>
    </div>
    <div id="fb-status"></div>
  </form>
  <!-- a quiet line, no banner: whoever comes to Help can also leave a rating -->
  <p class="rate-line" id="rate-line" hidden>@ICON:star@ <span data-t="rateText">Is ReadAloud helpful?</span> <a href="@STORE_REVIEW@" data-t="rateLink">Rate it in the Microsoft Store</a></p>
  <!-- <p class="coffee-line"><a href="@COFFEE@" ...>Like ReadAloud? Buy me a coffee ☕</a></p>
       too many coffees: here people come to complain or suggest. It stays in the menu -->
  </section>
</main>

<!-- signature, the same as the footer of dravvt.com: the green wave, the
     name and the year, small in the bottom corner -->
<footer class="brand">
  <!-- to the projects on dravvt.com, where ReadAloud is, in the language of
       the interface (set below; English until then) -->
  <a id="brand-link" href="https://dravvt.com/projects" target="_blank" rel="noopener">
    <svg viewBox="0 0 40 30" aria-hidden="true"><path d="M 4 15 Q 12 4 20 15 Q 28 26 36 15"></path></svg>
    <span>dravvt</span>
  </a>
  <span>·</span>
  <span id="year"></span>
</footer>

<!-- the folder icon, copied into each card -->
<template id="folder">@ICON:folder@</template>
<template id="trash">@ICON:trash-2@</template>
<template id="download-icon">@ICON:download@</template>

<!-- the interface in the chosen or the Windows language (I18N at the top of
     this file). @SYSLANG@ is filled in by the server on every request -->
<script>var SYSTEM_LANG = "@SYSLANG@";</script>
<script>@I18N@</script>
<script>
"use strict";
// the page itself is in the language of its interface
document.documentElement.lang = UI_LANG;
// the book pages follow whatever the library settled on
rememberLang(UI_LANG);
// the year of the signature at the bottom, never out of date
document.getElementById("year").textContent = new Date().getFullYear();
// dravvt.com/projects is the English one; Spanish and German carry their prefix
document.getElementById("brand-link").href =
  "https://dravvt.com" + (UI_LANG === "en" ? "" : "/" + UI_LANG) + "/projects";

// EN · DE · ES in the corner: another language for the whole interface
(function () {
  var box = document.getElementById("languages");
  ["en", "de", "es"].forEach(function (code) {
    var b = document.createElement("button");
    b.textContent = code.toUpperCase();
    b.className = code === UI_LANG ? "on" : "";
    b.onclick = function () { rememberLang(code, true); location.reload(); };
    box.appendChild(b);
  });
})();

var FOLDER = document.getElementById("folder").innerHTML;
var TRASH = document.getElementById("trash").innerHTML;
var DOWNLOAD_ICON = document.getElementById("download-icon").innerHTML;
// var LANGUAGES = { en: "English", de: "German" };
// the name of a book's language, in the language of the interface
function languageName(code) { return tr("lang_" + code) === "lang_" + code ? code : tr("lang_" + code); }
var polling = null;

// the folder name is the file name, underscores and all
function pretty(name) {
  return name.replace(/_/g, " ");
}

// the reader keeps its bookmark in localStorage under its own path, and this
// page is on the same origin, so it can read it back
function bookmark(url) {
  try {
    var n = parseInt(localStorage.getItem("reader:" + url), 10);
    return isNaN(n) ? null : n + 1;
  } catch (e) {
    return null;
  }
}

function card(tag, name, cls, meta, lang) {
  var el = document.createElement(tag);
  el.className = "book" + (cls ? " " + cls : "");
  el.title = pretty(name);
  el.innerHTML = FOLDER;
  var n = document.createElement("div");
  n.className = "name";
  n.textContent = pretty(name);
  var m = document.createElement("div");
  m.className = "meta";
  if (lang) {
    var l = document.createElement("span");
    l.className = "lang";
    l.textContent = lang.toUpperCase();
    m.appendChild(l);
  }
  m.appendChild(document.createTextNode(meta));
  el.appendChild(n);
  el.appendChild(m);
  // a book still being prepared cannot be deleted halfway
  if (cls !== "busy") {
    var del = document.createElement("button");
    del.className = "del";
    del.title = tr("deleteBook");
    del.innerHTML = TRASH;
    // the href is read at click time: it is set on the card after this
    del.onclick = function (e) { remove(name, e, el.getAttribute("href")); };
    el.appendChild(del);
  }
  return el;
}

// deletes it for good: the server removes the book's folder, pdf included.
// The card is a link, so the click must not also open the book
function remove(name, e, url) {
  e.preventDefault();
  e.stopPropagation();
  if (!confirm(tr("confirmDelete", { name: pretty(name) }))) return;
  fetch("/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name })
  })
    .then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok) throw new Error(trError(body, r.status));
        // and the bookmark goes with it
        if (url) { try { localStorage.removeItem("reader:" + url); } catch (err) {} }
        refresh();
      });
    })
    .catch(function (err) { say(err.message, "bad"); });
}

// a small button inside a card. The card is a link, so the click must not
// also open the book
function cardButton(label, icon, onclick) {
  var b = document.createElement("button");
  b.innerHTML = icon || "";
  b.appendChild(document.createTextNode(label));
  b.onclick = function (e) {
    e.preventDefault();
    e.stopPropagation();
    onclick();
  };
  return b;
}

// the MP3 row of a book's card. status is what /library says in "exports":
// {done, total} while it is being made, "failed: ..." or "interrupted"; with
// nothing there, the book either has its mp3 or not
function mp3Row(b, status) {
  var row = document.createElement("div");
  row.className = "mp3";
  var start = function () { exportMp3(b.name); };
  if (status && typeof status === "object") {
    var p = status.total ? Math.floor(100 * status.done / status.total) : 0;
    var s = document.createElement("span");
    s.className = "progress";
    s.textContent = tr("exporting", { p: p });
    row.appendChild(s);
  } else if (status) {
    // a failure stays on the card until it is retried: nobody should be left
    // waiting for an mp3 that is not coming
    row.className += " bad";
    var interrupted = status === "interrupted";
    var t = document.createElement("span");
    t.textContent = tr(interrupted ? "mp3Interrupted" : "mp3Failed");
    row.appendChild(t);
    if (!interrupted) {
      // the reason as the server gave it, for whoever writes asking about it
      var d = document.createElement("span");
      d.className = "detail";
      d.textContent = status.replace(/^failed: /, "");
      row.appendChild(d);
    }
    row.appendChild(cardButton(tr("retry"), "", start));
  // } else if (b.mp3) {
  //   row.appendChild(cardButton(tr("downloadMp3"), DOWNLOAD_ICON, function () { ... }));
  // a book that has its mp3 shows nothing here: the mp3 is in Audios, below
  // the shelf (two things on one card was confusing)
  } else if (b.mp3) {
    return null;
  } else {
    var make = cardButton(tr("exportMp3"), DOWNLOAD_ICON, start);
    make.title = tr("exportMp3Title");
    row.appendChild(make);
  }
  return row;
}

function mp3Url(b) { return b.url.replace(/index\\.html$/, "audio.mp3"); }

// the Audios section. The shelf is redrawn every 2 s while something is being
// made, which would restart a player halfway through, so the list is only
// rebuilt when the set of mp3s changes
var audiosShown = null;
function drawAudios(books) {
  var key = books.map(function (b) { return b.name; }).join("\\n");
  if (key === audiosShown) return;
  audiosShown = key;
  // document.getElementById("audios").hidden = !books.length;
  // the tab is always there; empty, it says how to make one
  document.getElementById("no-audios").hidden = !!books.length;
  document.getElementById("audio-list").hidden = !books.length;
  document.getElementById("coffee-box").hidden = !books.length;
  syncCoffee();
  document.getElementById("audio-count").textContent = books.length ? "(" + books.length + ")" : "";
  var list = document.getElementById("audio-list");
  list.textContent = "";
  books.forEach(function (b) {
    var li = document.createElement("li");
    var title = document.createElement("div");
    title.className = "title";
    var l = document.createElement("span");
    l.className = "lang";
    l.textContent = (b.lang || "").toUpperCase();
    title.appendChild(l);
    title.appendChild(document.createTextNode(pretty(b.name)));
    li.appendChild(title);

    var controls = document.createElement("div");
    controls.className = "controls";
    // var player = document.createElement("audio");
    // player.controls = true;
    // player.preload = "none";
    // the browser's own player is white and barely takes colours, so it is
    // hidden and drawn here, like the rest of the page. Only the length is
    // read beforehand (a few bytes, now that the server sends pieces)
    var player = document.createElement("audio");
    player.preload = "metadata";
    player.src = mp3Url(b);
    controls.appendChild(player);
    controls.appendChild(playerControls(player));

    // saved under the book's name, not audio.mp3
    var save = document.createElement("button");
    save.innerHTML = DOWNLOAD_ICON;
    save.appendChild(document.createTextNode(tr("saveMp3")));
    save.onclick = function () {
      var a = document.createElement("a");
      a.href = mp3Url(b);
      a.download = pretty(b.name) + ".mp3";
      document.body.appendChild(a);
      a.click();
      a.remove();
    };
    controls.appendChild(save);

    var del = document.createElement("button");
    del.className = "del-mp3";
    del.title = tr("deleteMp3");
    del.innerHTML = TRASH;
    del.onclick = function () {
      if (!confirm(tr("confirmDeleteMp3", { name: pretty(b.name) }))) return;
      // let go of the file first: Windows will not delete it while it is
      // still being sent to the player
      player.pause();
      player.removeAttribute("src");
      player.load();
      deleteMp3(b.name);
    };
    controls.appendChild(del);
    li.appendChild(controls);
    list.appendChild(li);
  });
}

// 3:13, or 1:02:05 for the long books
function clock(s) {
  if (!isFinite(s)) return "0:00";
  s = Math.floor(s);
  var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return (h ? h + ":" + (m < 10 ? "0" : "") + m : m) + ":" + (x < 10 ? "0" : "") + x;
}

var SPEEDS = [1, 1.25, 1.5, 2];

// play/pause, the time, the green bar, the length and the speed of one mp3
function playerControls(player) {
  var box = document.createElement("div");
  box.className = "player";
  var play = document.createElement("button");
  play.className = "play";
  play.textContent = "\\u25B6";
  var now = document.createElement("span");
  now.className = "time";
  now.textContent = "0:00";
  // 0 to 1000 rather than seconds: the length is not known until it loads
  var bar = document.createElement("input");
  bar.type = "range";
  bar.min = 0;
  bar.max = 1000;
  bar.value = 0;
  var total = document.createElement("span");
  total.className = "time";
  total.textContent = "0:00";
  var speed = document.createElement("button");
  speed.className = "speed";
  speed.textContent = "1.0\\u00D7";
  [play, now, bar, total, speed].forEach(function (el) { box.appendChild(el); });

  // the bar is green up to where it is, through --p in the css
  var dragging = false;
  function paint() {
    var d = player.duration;
    if (!dragging) bar.value = d ? Math.round(1000 * player.currentTime / d) : 0;
    bar.style.setProperty("--p", bar.value / 10 + "%");
    if (!dragging) now.textContent = clock(player.currentTime);
    total.textContent = clock(d);
  }
  player.addEventListener("timeupdate", paint);
  player.addEventListener("loadedmetadata", paint);
  player.addEventListener("durationchange", paint);
  player.addEventListener("play", function () {
    play.textContent = "\\u275A\\u275A";
    // one at a time: starting this one pauses whichever was playing
    Array.prototype.forEach.call(document.querySelectorAll(".audios audio"), function (a) {
      if (a !== player) a.pause();
    });
  });
  player.addEventListener("pause", function () { play.textContent = "\\u25B6"; });
  player.addEventListener("ended", function () { play.textContent = "\\u25B6"; });

  play.onclick = function () {
    if (player.paused) player.play(); else player.pause();
  };
  // while dragging only the bar and the time move; the jump is on release
  bar.oninput = function () {
    dragging = true;
    bar.style.setProperty("--p", bar.value / 10 + "%");
    if (player.duration) now.textContent = clock(bar.value / 1000 * player.duration);
  };
  bar.onchange = function () {
    dragging = false;
    if (player.duration) player.currentTime = bar.value / 1000 * player.duration;
    paint();
  };
  speed.onclick = function () {
    var next = SPEEDS[(SPEEDS.indexOf(player.playbackRate) + 1) % SPEEDS.length];
    player.playbackRate = next;
    speed.textContent = (next % 1 ? next : next.toFixed(1)) + "\\u00D7";
  };
  return box;
}

function deleteMp3(name) {
  fetch("/delete-mp3", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name })
  })
    .then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok) throw new Error(trError(body, r.status));
        refresh();
      });
    })
    .catch(function (err) { say(err.message, "bad"); });
}


// errors or suggestions: the server passes them on to dravvt.com
document.getElementById("feedback").onsubmit = function (e) {
  e.preventDefault();
  var message = document.getElementById("fb-message");
  var send = document.getElementById("fb-send");
  var status = document.getElementById("fb-status");
  var show = function (text, kind) { status.textContent = text; status.className = kind || ""; };
  if (message.value.trim().length < 5) { show(tr("feedbackShort"), "bad"); return; }
  send.disabled = true;
  show(tr("feedbackSending"));
  fetch("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: message.value,
      email: document.getElementById("fb-email").value,
      website: document.getElementById("fb-website").value,
      lang: UI_LANG
    })
  })
    .then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok) throw new Error(trError(body, r.status));
        show(tr("feedbackThanks"), "good");
        message.value = "";
      });
    })
    .catch(function (err) { show(err.message, "bad"); })
    .then(function () { send.disabled = false; });
};

function exportMp3(name) {
  fetch("/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name })
  })
    .then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok) throw new Error(trError(body, r.status));
        refresh();
      });
    })
    .catch(function (err) { say(err.message, "bad"); });
}

// function fold(open) {
//   document.getElementById("shelf").classList.toggle("folded", !open);
//   document.getElementById("toggle").classList.toggle("open", open);
//   try { localStorage.setItem("library:open", open ? "1" : ""); } catch (e) {}
// }
// document.getElementById("toggle").onclick = ...; fold(!!localStorage.getItem("library:open"));
// the shelf no longer folds: the tabs and the search took its place

// Books · Audios · Help. The last one open is remembered
var TABS = ["books", "audios", "help"];
function showTab(name) {
  TABS.forEach(function (t) {
    document.getElementById("tab-" + t).hidden = t !== name;
    var b = document.querySelector('.tabs [data-tab="' + t + '"]');
    b.classList.toggle("on", t === name);
    b.setAttribute("aria-selected", t === name ? "true" : "false");
  });
  try { localStorage.setItem("library:tab", name); } catch (e) {}
  syncCoffee();
}

// one coffee at a time: on Audios, when its box is there, the menu's button
// steps aside (the box says more: it speaks of the PDF they just heard)
function syncCoffee() {
  var onAudios = !document.getElementById("tab-audios").hidden;
  var box = !document.getElementById("coffee-box").hidden;
  document.querySelector(".tabs .coffee-btn").hidden = onAudios && box;
}
Array.prototype.forEach.call(document.querySelectorAll(".tabs [data-tab]"), function (b) {
  b.onclick = function () { showTab(b.getAttribute("data-tab")); };
});
(function () {
  var saved = null;
  try { saved = localStorage.getItem("library:tab"); } catch (e) {}
  showTab(TABS.indexOf(saved) >= 0 ? saved : "books");
})();

// "+ Add a book" opens and closes the box
var addBox = document.getElementById("add");
document.getElementById("add-toggle").onclick = function () { addBox.hidden = !addBox.hidden; };

// the search: by name, ignoring case and accents, as you type
function plain(s) {
  return s.normalize("NFD").replace(/[\\u0300-\\u036f]/g, "").toLowerCase();
}
function applyFilter() {
  var q = plain(document.getElementById("filter").value.trim());
  var cards = document.querySelectorAll("#shelf .book");
  var shown = 0;
  Array.prototype.forEach.call(cards, function (el) {
    el.hidden = !!q && plain(el.title).indexOf(q) === -1;
    if (!el.hidden) shown++;
  });
  document.getElementById("no-match").hidden = !(q && cards.length && !shown);
}
document.getElementById("filter").addEventListener("input", applyFilter);

function draw(data) {
  var shelf = document.getElementById("shelf");
  shelf.innerHTML = "";
  document.getElementById("count").textContent = "(" + data.books.length + ")";
  var exports = data.exports || {};
  data.books.forEach(function (b) {
    var mark = bookmark(b.url);
    var el = card("a", b.name, "", mark ? tr("paragraph", { n: mark }) : tr("notStarted"), b.lang);
    el.href = b.url;
    var row = mp3Row(b, exports[b.name]);
    if (row) el.appendChild(row);
    shelf.appendChild(el);
  });
  drawAudios(data.books.filter(function (b) { return b.mp3 && !exports[b.name]; }));
  Object.keys(data.jobs).forEach(function (name) {
    var status = data.jobs[name];
    var failed = status !== "building";
    shelf.appendChild(card("div", name, failed ? "failed" : "busy",
                           failed ? status : tr("preparing")));
  });
  if (!shelf.children.length) {
    var p = document.createElement("p");
    p.className = "empty";
    p.textContent = tr("empty");
    shelf.appendChild(p);
    // nothing on the shelf yet: the way to add one is already open
    addBox.hidden = false;
  }
  // the shelf was just drawn again, the search still applies
  applyFilter();
  // "Rate it in the Microsoft Store", in Help: only where there is a Store,
  // the packaged Windows program
  document.getElementById("rate-line").hidden = !data.store;
  // without a console, this is the only place a voice download shows up
  var d = document.getElementById("download");
  var downloading = data.download && data.download.language;
  d.classList.toggle("on", !!downloading);
  if (downloading) {
    d.textContent = tr("downloadingVoice", {
      language: languageName(data.download.language), p: data.download.percent || 0
    });
  }
  // keep asking only while something is being prepared or downloaded
  // var busy = downloading || Object.keys(data.jobs).some(function (k) { return data.jobs[k] === "building"; });
  // or an mp3 is being made, for its progress
  var busy = downloading || Object.keys(data.jobs).some(function (k) { return data.jobs[k] === "building"; })
    || Object.keys(exports).some(function (k) { return typeof exports[k] === "object"; });
  if (busy && !polling) polling = setInterval(refresh, 2000);
  if (!busy && polling) { clearInterval(polling); polling = null; }
}

function refresh() {
  fetch("/library").then(function (r) { return r.json(); }).then(draw);
}

function say(text, kind) {
  var m = document.getElementById("message");
  m.textContent = text;
  m.className = kind || "";
}

function answered(r) {
  return r.json().then(function (body) {
    if (!r.ok) throw new Error(trError(body, r.status));
    say(tr("beingPrepared", { name: pretty(body.name) }), "good");
    // the new book should be seen arriving, so a folded shelf opens
    // fold(true);
    // ...and with tabs, on the books, with no search hiding it
    showTab("books");
    document.getElementById("filter").value = "";
    refresh();
  });
}

function startPage() {
  return Math.max(1, parseInt(document.getElementById("start").value, 10) || 1);
}

function upload(file) {
  if (!file) return;
  if (!/\\.pdf$/i.test(file.name)) { say(tr("notPdf"), "bad"); return; }
  say(tr("uploading", { name: file.name }));
  var url = "/upload?name=" + encodeURIComponent(file.name) + "&start=" + startPage();
  fetch(url, { method: "POST", body: file })
    .then(answered)
    .catch(function (e) { say(e.message, "bad"); });
}

document.getElementById("browse").onclick = function () {
  document.getElementById("file").click();
};
document.getElementById("file").onchange = function () {
  upload(this.files[0]);
  this.value = "";
};

function addPath() {
  var path = document.getElementById("path").value.trim();
  if (!path) { say(tr("pastePath"), "bad"); return; }
  fetch("/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: path, start: startPage() })
  })
    .then(function (r) {
      return answered(r).then(function () { document.getElementById("path").value = ""; });
    })
    .catch(function (e) { say(e.message, "bad"); });
}
document.getElementById("add-path").onclick = addPath;
document.getElementById("path").addEventListener("keydown", function (e) {
  if (e.key === "Enter") addPath();
});

// dropping a PDF on the box works like choosing it
var box = document.getElementById("add");
["dragenter", "dragover"].forEach(function (ev) {
  box.addEventListener(ev, function (e) { e.preventDefault(); box.classList.add("dragging"); });
});
["dragleave", "drop"].forEach(function (ev) {
  box.addEventListener(ev, function () { box.classList.remove("dragging"); });
});
box.addEventListener("drop", function (e) {
  e.preventDefault();
  upload(e.dataTransfer.files[0]);
});
// the box may be closed or on another tab: a file dragged over the page opens
// it, so there is somewhere to drop it
document.addEventListener("dragenter", function (e) {
  if (e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types, "Files") !== -1) {
    showTab("books");
    box.hidden = false;
  }
});

refresh();
</script>
</body>
</html>
"""

TEMPLATE = with_i18n(with_icons(TEMPLATE))
# SHELF = with_i18n(with_icons(SHELF))
# the "buy me a coffee" link: a Stripe Payment Link where the person picks the
# amount. Only the public link is here, no key: the program is downloaded by
# anyone, and the payment happens entirely on Stripe's page
COFFEE_URL = "https://buy.stripe.com/eVqfZhbkV2tp3J9a3f2B200"
# SHELF = with_i18n(with_icons(SHELF)).replace("@COFFEE@", COFFEE_URL)
# the app in the Microsoft Store (Partner Center, Product Identity). The
# ms-windows-store: link opens the Store app straight on its review page
STORE_ID = "9N1ZZ5R1X29M"
SHELF = (with_i18n(with_icons(SHELF))
         .replace("@COFFEE@", COFFEE_URL)
         .replace("@STORE_REVIEW@", "ms-windows-store://review/?ProductId=" + STORE_ID))
