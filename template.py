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

TEMPLATE = """<!DOCTYPE html>
<html lang="@LANG@">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
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
</style>
</head>
<body>

<div class="bar top">
  <a class="home" href="/" title="back to the library">@ICON:library-big@</a>
  <button id="prev" title="previous page">&lsaquo;</button>
  <span id="page-number">1 / 1</span>
  <button id="next" title="next page">&rsaquo;</button>
  <span class="spacer"></span>
  <span id="notice"></span>
  <button id="colors" title="colors">@ICON:palette@</button>
  <button id="smaller" title="smaller text">A-</button>
  <button id="bigger" title="bigger text">A+</button>
  <button id="narrower" title="narrower column">&#8677;&#8676;</button>
  <button id="wider" title="wider column">&#8676;&#8677;</button>
</div>

<div class="panel" id="panel" hidden>
  <div class="themes" id="themes"></div>
  <label>Background <input type="color" id="c-bg"></label>
  <label>Text <input type="color" id="c-ink"></label>
  <label>Highlight <input type="color" id="c-mark"></label>
  <button id="c-reset">Reset</button>
</div>

<main><!--BODY--></main>

<div class="bar bottom">
  <button id="back" title="previous paragraph">&#9198;</button>
  <button id="play">Read</button>
  <button id="forward" title="next paragraph">&#9197;</button>
  <button id="stop" title="stop and release the audio">&#9209;</button>
  <button id="slower" title="slower">&minus;</button>
  <span id="speed">1.0&times;</span>
  <button id="faster" title="faster">+</button>
  <span id="bookmark"></span>
</div>

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
    "paragraph " + (current + 1) + " of " + blocks.length;
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
      if (!r.ok) throw new Error("the server answered " + r.status);
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
    ready = fetchWav(i);
  }
  ready.then(function (url) {
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
    blocks[i].classList.remove("loading");
    playing = false;
    drawPlay();
    document.getElementById("notice").textContent =
      "no audio: start server.py (" + e.message + ")";
  });
}

audio.addEventListener("ended", function () {
  if (playing) playBlock(current + 1);
});

function drawPlay() {
  document.getElementById("play").textContent = playing ? "Pause" : "Read";
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
  b.appendChild(document.createTextNode(name));
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

document.addEventListener("keydown", function (e) {
  if (e.key === " ") { e.preventDefault(); play(); }
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
<title>Library</title>
<style>
:root {
  --bg: #14161a;
  --ink: #d8d4cc;
  --muted: #7d8590;
  --border: #262a31;
  --card: #1b1f26;
  --card-hover: #232833;
  --folder: #c9a55a;
  --accent: #8fbf8f;
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
/* the title folds the shelf away, so the whole page fits on one screen */
h1 { cursor: pointer; user-select: none; }
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
}
a.book:hover { background: var(--card-hover); transform: translateY(-2px); }
.book .icon {
  width: 56px;
  height: 56px;
  color: var(--folder);
  fill: #c9a55a33;
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

.add {
  background: var(--card);
  border: 1px dashed #3a414c;
  border-radius: 10px;
  padding: 1.2rem;
  display: grid;
  gap: 1.1rem;
}
.add.dragging { border-color: var(--accent); background: #1c2620; }
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
</style>
</head>
<body>
<main>
  <h1 id="toggle" title="show or hide the books"><span class="chevron">@ICON:chevron-right@</span>@ICON:library-big@ Library <span id="count"></span></h1>
  <p class="lead">Click a book to open it. It picks up where you left off.</p>

  <div class="shelf" id="shelf"></div>

  <h2>Add a book</h2>
  <div class="add" id="add">
    <div class="option">
      <b>Start at page</b>
      <input type="number" id="start" value="1" min="1">
      <span class="hint">to skip the cover and the table of contents</span>
    </div>
    <div class="option">
      <b>From a folder</b>
      <button id="browse">Choose a PDF&hellip;</button>
      <input type="file" id="file" accept=".pdf,application/pdf">
      <span class="hint">or drag the PDF onto this box</span>
    </div>
    <div class="option">
      <b>From its path</b>
      <input type="text" id="path" placeholder="C:\\Users\\...\\book.pdf">
      <button id="add-path">Add</button>
    </div>
    <div id="message"></div>
  </div>
</main>

<!-- the folder icon, copied into each card -->
<template id="folder">@ICON:folder@</template>

<script>
"use strict";

var FOLDER = document.getElementById("folder").innerHTML;
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
  return el;
}

function fold(open) {
  document.getElementById("shelf").classList.toggle("folded", !open);
  document.getElementById("toggle").classList.toggle("open", open);
  try { localStorage.setItem("library:open", open ? "1" : ""); } catch (e) {}
}
document.getElementById("toggle").onclick = function () {
  fold(document.getElementById("shelf").classList.contains("folded"));
};
try { fold(!!localStorage.getItem("library:open")); } catch (e) { fold(false); }

function draw(data) {
  var shelf = document.getElementById("shelf");
  shelf.innerHTML = "";
  document.getElementById("count").textContent = "(" + data.books.length + ")";
  data.books.forEach(function (b) {
    var mark = bookmark(b.url);
    var el = card("a", b.name, "", mark ? "paragraph " + mark : "not started", b.lang);
    el.href = b.url;
    shelf.appendChild(el);
  });
  Object.keys(data.jobs).forEach(function (name) {
    var status = data.jobs[name];
    var failed = status !== "building";
    shelf.appendChild(card("div", name, failed ? "failed" : "busy",
                           failed ? status : "preparing\\u2026 this takes a few minutes"));
  });
  if (!shelf.children.length) {
    var p = document.createElement("p");
    p.className = "empty";
    p.textContent = "No books yet. Add your first one below.";
    shelf.appendChild(p);
  }
  // keep asking only while something is being prepared
  var busy = Object.keys(data.jobs).some(function (k) { return data.jobs[k] === "building"; });
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
    if (!r.ok) throw new Error(body.error || "the server answered " + r.status);
    say("\\u201c" + pretty(body.name) + "\\u201d is being prepared. It will show up above when it is ready.", "good");
    // the new book should be seen arriving, so a folded shelf opens
    fold(true);
    refresh();
  });
}

function startPage() {
  return Math.max(1, parseInt(document.getElementById("start").value, 10) || 1);
}

function upload(file) {
  if (!file) return;
  if (!/\\.pdf$/i.test(file.name)) { say("That is not a PDF.", "bad"); return; }
  say("Uploading " + file.name + "\\u2026");
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
  if (!path) { say("Paste the path to the PDF first.", "bad"); return; }
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

refresh();
</script>
</body>
</html>
"""

TEMPLATE = with_icons(TEMPLATE)
SHELF = with_icons(SHELF)
