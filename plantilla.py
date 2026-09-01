"""la pagina de lectura: maquetacion, controles y marcador

no es una f-string a proposito. el css y el javascript van llenos de
llaves y en una f-string habria que doblarlas todas, que es justo la
clase de detalle que se cuela sin avisar. aqui los huecos son @TITULO@,
@IDIOMA@ y <!--CUERPO-->, y documento_lectura() los sustituye.

@IDIOMA@ no es decoracion: el servidor lo lee de vuelta de este html
para saber con que voz de piper tiene que leer el libro, porque cuando
se abre un libro de la estanteria el pdf ya no tiene por que estar.
"""

PLANTILLA = """<!DOCTYPE html>
<html lang="@IDIOMA@">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@TITULO@</title>
<style>
:root {
  --fondo: #14161a;
  --tinta: #d8d4cc;
  --apagado: #7d8590;
  --marca: #2b3a2f;
  --borde: #262a31;
  --cuerpo: 18px;
  --ancho: 70ch;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--fondo);
  color: var(--tinta);
  font-family: Georgia, "Times New Roman", serif;
  font-size: var(--cuerpo);
  line-height: 1.6;
}
main {
  max-width: var(--ancho);
  margin: 0 auto;
  padding: 5rem 1.2rem 8rem;
}

/* solo se ve la pagina actual: el libro entero de golpe son 4000 bloques */
.pagina { display: none; }
.pagina.activa { display: block; }

p { margin: 0 0 1.2em; }
h3 {
  /* los titulos de seccion del libro. llevan data-i como los parrafos,
     asi que tambien se leen en voz alta y se pueden marcar */
  font-family: system-ui, sans-serif;
  font-size: 1.05em;
  font-weight: 600;
  color: #e8e4dc;
  margin: 2.2em 0 .8em;
}
.pagina > h3:first-child { margin-top: 0; }
pre {
  /* el codigo va monoespaciado y sin ajustar: la sangria es sintaxis */
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
  /* las figuras son trazo negro sobre blanco: se dejan tal cual para no
     falsear el original, pero centradas y sin desbordar la columna */
  display: block;
  max-width: 100%;
  margin: 1.6em auto;
  background: #fff;
  border-radius: 4px;
  padding: .5em;
}

/* el parrafo que suena ahora mismo */
p[data-i], pre[data-i] {
  cursor: pointer;
  border-radius: 3px;
  transition: background .15s;
}
.leyendo {
  background: var(--marca);
  box-shadow: 0 0 0 .45em var(--marca);
}
.cargando { opacity: .55; }

.barra {
  position: fixed;
  left: 0;
  right: 0;
  background: #10121580;
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--borde);
  display: flex;
  align-items: center;
  gap: .6rem;
  padding: .55rem .9rem;
  font-family: system-ui, sans-serif;
  font-size: 14px;
  color: var(--apagado);
}
.barra.arriba { top: 0; }
.barra.abajo {
  bottom: 0;
  top: auto;
  border-bottom: 0;
  border-top: 1px solid var(--borde);
  justify-content: center;
}
button {
  background: #1b1f26;
  color: var(--tinta);
  border: 1px solid var(--borde);
  border-radius: 6px;
  padding: .4rem .7rem;
  font: inherit;
  cursor: pointer;
}
button:hover { background: #232833; }
button:disabled { opacity: .4; cursor: default; }
#play { min-width: 4.2rem; font-weight: 600; }
.hueco { flex: 1; }
#aviso { color: #d98b8b; }
</style>
</head>
<body>

<div class="barra arriba">
  <button id="anterior" title="pagina anterior">&lsaquo;</button>
  <span id="pagina">1 / 1</span>
  <button id="siguiente" title="pagina siguiente">&rsaquo;</button>
  <span class="hueco"></span>
  <span id="aviso"></span>
  <button id="menos" title="letra mas pequena">A-</button>
  <button id="mas" title="letra mas grande">A+</button>
  <button id="estrecho" title="columna mas estrecha">&#8677;&#8676;</button>
  <button id="ancho" title="columna mas ancha">&#8676;&#8677;</button>
</div>

<main><!--CUERPO--></main>

<div class="barra abajo">
  <button id="atras" title="parrafo anterior">&#9198;</button>
  <button id="play">Leer</button>
  <button id="adelante" title="parrafo siguiente">&#9197;</button>
  <button id="parar" title="parar y soltar el audio">&#9209;</button>
  <span id="marcador"></span>
</div>

<script>
"use strict";

// todos los bloques que se pueden leer en voz alta, en orden de lectura.
// las figuras no llevan data-i, asi que se saltan solas.
var bloques = Array.prototype.slice.call(document.querySelectorAll("[data-i]"));
var paginas = Array.prototype.slice.call(document.querySelectorAll(".pagina"));
var clave = "lector:" + location.pathname;

var actual = 0;
var pagina = 0;
var sonando = false;
var audio = new Audio();
var siguienteWav = null;   // el bloque de despues, ya sintetizado
var cargado = -1;          // que bloque es el que tiene el audio ahora

function guardar() {
  localStorage.setItem(clave, String(actual));
}

function recordar() {
  var n = parseInt(localStorage.getItem(clave), 10);
  return isNaN(n) ? 0 : Math.min(n, bloques.length - 1);
}

// al pasar de pagina a mano, el punto de lectura se va con ella: si estas
// mirando la pagina 5 y le das a leer, tiene que empezar por la 5 y no por
// donde se quedo el marcador
function verPagina(n, aMano) {
  if (n < 0 || n >= paginas.length) return;
  paginas.forEach(function (p, i) { p.classList.toggle("activa", i === n); });
  pagina = n;
  // el numero que se ensena es el de la pagina del pdf, no el indice de
  // la seccion: las paginas en blanco no llegan a generar seccion, asi
  // que contar secciones daria un numero que no esta en el libro
  document.getElementById("pagina").textContent =
    paginas[n].getAttribute("data-pagina") + " / " +
    paginas[paginas.length - 1].getAttribute("data-pagina");
  document.getElementById("anterior").disabled = n === 0;
  document.getElementById("siguiente").disabled = n === paginas.length - 1;
  if (aMano) {
    var primero = paginas[n].querySelector("[data-i]");
    if (primero) {
      actual = bloques.indexOf(primero);
      pintarMarcador();
      resaltar();
      guardar();
    }
  }
}

function paginaDe(bloque) {
  return paginas.indexOf(bloque.closest(".pagina"));
}

function resaltar() {
  bloques.forEach(function (b) { b.classList.remove("leyendo"); });
  if (bloques[actual]) bloques[actual].classList.add("leyendo");
}

function pintarMarcador() {
  document.getElementById("marcador").textContent =
    "parrafo " + (actual + 1) + " de " + bloques.length;
}

function marcar(i, desplazar) {
  var b = bloques[i];
  if (!b) return;
  actual = i;
  var p = paginaDe(b);
  if (p !== pagina) verPagina(p);
  resaltar();
  if (desplazar) b.scrollIntoView({ block: "center", behavior: "smooth" });
  pintarMarcador();
  guardar();
}

// piper sintetiza bajo demanda: el navegador pide el wav de un bloque y el
// servidor lo devuelve. se pide tambien el siguiente mientras suena este,
// que si no se nota el silencio entre parrafo y parrafo.
function pedirWav(i) {
  if (i < 0 || i >= bloques.length) return Promise.resolve(null);
  // el servidor no sabe nada del libro: le llega el texto y devuelve el wav
  return fetch("/tts", { method: "POST", body: bloques[i].textContent })
    .then(function (r) {
      if (!r.ok) throw new Error("el servidor respondio " + r.status);
      return r.blob();
    })
    .then(function (b) { return URL.createObjectURL(b); });
}

function precargar(i) {
  if (siguienteWav && siguienteWav.i === i) return;
  if (siguienteWav) URL.revokeObjectURL(siguienteWav.url);
  siguienteWav = null;
  pedirWav(i).then(function (url) {
    if (url) siguienteWav = { i: i, url: url };
  }).catch(function () {});
}

function reproducir(i) {
  if (i < 0 || i >= bloques.length) { parar(); return; }
  actual = i;
  marcar(i, true);
  var listo;
  if (siguienteWav && siguienteWav.i === i) {
    listo = Promise.resolve(siguienteWav.url);
    siguienteWav = null;
  } else {
    bloques[i].classList.add("cargando");
    listo = pedirWav(i);
  }
  listo.then(function (url) {
    bloques[i].classList.remove("cargando");
    if (!sonando) return;
    audio.src = url;
    cargado = i;
    audio.play();
    precargar(i + 1);
  }).catch(function (e) {
    bloques[i].classList.remove("cargando");
    sonando = false;
    pintarPlay();
    document.getElementById("aviso").textContent =
      "sin audio: arranca servidor.py (" + e.message + ")";
  });
}

audio.addEventListener("ended", function () {
  if (sonando) reproducir(actual + 1);
});

function pintarPlay() {
  document.getElementById("play").textContent = sonando ? "Pausa" : "Leer";
}

function play() {
  if (siguienteWav && siguienteWav.i !== actual) {
    URL.revokeObjectURL(siguienteWav.url);
    siguienteWav = null;
  }
  if (sonando) {
    sonando = false;
    audio.pause();
  } else {
    sonando = true;
    // solo se reanuda si el audio parado es el del parrafo en el que
    // estamos; si te has movido de sitio hay que sintetizar el nuevo
    if (cargado === actual && audio.currentTime > 0 && !audio.ended) audio.play();
    else reproducir(actual);
  }
  pintarPlay();
}

function parar() {
  sonando = false;
  audio.pause();
  audio.currentTime = 0;
  pintarPlay();
}

function saltar(n) {
  audio.pause();
  var i = Math.max(0, Math.min(bloques.length - 1, actual + n));
  if (sonando) reproducir(i);
  else { actual = i; marcar(i, true); }
}

document.getElementById("play").onclick = play;
document.getElementById("parar").onclick = parar;
document.getElementById("atras").onclick = function () { saltar(-1); };
document.getElementById("adelante").onclick = function () { saltar(1); };
document.getElementById("anterior").onclick = function () { verPagina(pagina - 1, true); };
document.getElementById("siguiente").onclick = function () { verPagina(pagina + 1, true); };

// pinchar un parrafo empieza a leer justo ahi
bloques.forEach(function (b) {
  b.onclick = function () {
    actual = parseInt(b.getAttribute("data-i"), 10);
    actual = bloques.indexOf(b);
    if (sonando) reproducir(actual);
    else marcar(actual, false);
  };
});

function ajustar(prop, paso, minimo, maximo, unidad) {
  var raiz = document.documentElement;
  var v = parseFloat(getComputedStyle(raiz).getPropertyValue(prop));
  v = Math.max(minimo, Math.min(maximo, v + paso));
  raiz.style.setProperty(prop, v + unidad);
  localStorage.setItem(clave + prop, v + unidad);
}
document.getElementById("mas").onclick = function () { ajustar("--cuerpo", 1, 12, 32, "px"); };
document.getElementById("menos").onclick = function () { ajustar("--cuerpo", -1, 12, 32, "px"); };
document.getElementById("ancho").onclick = function () { ajustar("--ancho", 5, 40, 120, "ch"); };
document.getElementById("estrecho").onclick = function () { ajustar("--ancho", -5, 40, 120, "ch"); };

["--cuerpo", "--ancho"].forEach(function (prop) {
  var v = localStorage.getItem(clave + prop);
  if (v) document.documentElement.style.setProperty(prop, v);
});

document.addEventListener("keydown", function (e) {
  if (e.key === " ") { e.preventDefault(); play(); }
  else if (e.key === "ArrowRight") saltar(1);
  else if (e.key === "ArrowLeft") saltar(-1);
  else if (e.key === "PageDown") verPagina(pagina + 1, true);
  else if (e.key === "PageUp") verPagina(pagina - 1, true);
});

verPagina(0);
actual = recordar();
marcar(actual, true);
</script>
</body>
</html>
"""
