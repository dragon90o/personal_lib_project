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
  color: #e8e4dc;
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
#play { min-width: 4.2rem; font-weight: 600; }
.spacer { flex: 1; }
#notice { color: #d98b8b; }
</style>
</head>
<body>

<div class="bar top">
  <button id="prev" title="previous page">&lsaquo;</button>
  <span id="page-number">1 / 1</span>
  <button id="next" title="next page">&rsaquo;</button>
  <span class="spacer"></span>
  <span id="notice"></span>
  <button id="smaller" title="smaller text">A-</button>
  <button id="bigger" title="bigger text">A+</button>
  <button id="narrower" title="narrower column">&#8677;&#8676;</button>
  <button id="wider" title="wider column">&#8676;&#8677;</button>
</div>

<main><!--BODY--></main>

<div class="bar bottom">
  <button id="back" title="previous paragraph">&#9198;</button>
  <button id="play">Read</button>
  <button id="forward" title="next paragraph">&#9197;</button>
  <button id="stop" title="stop and release the audio">&#9209;</button>
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
  // the server knows nothing about the book: it gets text and returns a wav
  return fetch("/tts", { method: "POST", body: blocks[i].textContent })
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
});

showPage(0);
current = remember();
goTo(current, true);
</script>
</body>
</html>
"""
