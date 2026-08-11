/* ══════════════════════════════════════════════════════════════════════════════
   DubAI — maqueta de demostración.

   QUÉ HACE DE VERDAD Y QUÉ NO:
   El archivo que soltás NO se sube a ningún lado. Se lee en el navegador para
   sacarle duración, resolución y un cuadro de muestra — nada sale de la máquina.
   Las etapas que se ven correr son una RECREACIÓN cronometrada del proceso real
   (los nombres técnicos de cada etapa son los del motor de producción), y el
   video final es una muestra ya renderizada que viaja con la página.

   Para ajustar el ritmo de la demo, tocá TOTAL_MS.
   ══════════════════════════════════════════════════════════════════════════════ */
(() => {
"use strict";

const TOTAL_MS = 26000;          // cuánto dura la "recreación" completa
const $  = (s) => document.querySelector(s);

const el = {
  drop:    $("#drop"),
  file:    $("#file"),
  lang:    $("#lang"),
  hint:    $("#lang-hint"),
  voices:  $("#voices"),
  pDrop:   $("#panel-drop"),
  pWork:   $("#panel-work"),
  pDone:   $("#panel-done"),
  thumb:   $("#thumb"),
  wName:   $("#w-name"),
  wSpecs:  $("#w-specs"),
  ring:    $("#ring"),
  pct:     $("#pct"),
  bars:    $("#bars"),
  steps:   $("#steps"),
  console: $("#console"),
  video:   $("#video"),
  doneLang:$("#done-lang"),
  again:   $("#again"),
  stage:   $("#stage"),
};

const LANGS = {
  es:{n:"español",  m:"eleven_v3"},
  en:{n:"inglés",   m:"eleven_multilingual_v2"},
  pt:{n:"portugués",m:"eleven_v3"},
  he:{n:"hebreo",   m:"eleven_v3"},
  fr:{n:"francés",  m:"eleven_v3"},
  de:{n:"alemán",   m:"eleven_v3"},
  it:{n:"italiano", m:"eleven_v3"},
  ja:{n:"japonés",  m:"eleven_v3"},
};

let voiceMode = "clon";
let running   = false;
let timers    = [];

/* ══════════════ utilidades ══════════════ */
const clamp = (v,a,b) => Math.min(b, Math.max(a, v));
const later = (fn, ms) => { const t = setTimeout(fn, ms); timers.push(t); return t; };
const clearTimers = () => { timers.forEach(clearTimeout); timers = []; };

function mmss(s){
  if (!isFinite(s) || s <= 0) return "—";
  const m = Math.floor(s/60), r = Math.round(s%60);
  return `${m}:${String(r).padStart(2,"0")}`;
}
const nfmt = (n) => n.toLocaleString("es-AR");

/* ══════════════ selector de idioma ══════════════ */
function paintHint(){
  const L = LANGS[el.lang.value] || LANGS.es;
  el.hint.innerHTML = `Modelo: <code>${L.m}</code>`;
}
el.lang.addEventListener("change", paintHint);
paintHint();

el.voices.addEventListener("click", (e) => {
  const b = e.target.closest(".seg");
  if (!b) return;
  el.voices.querySelectorAll(".seg").forEach(s => {
    const on = s === b;
    s.classList.toggle("on", on);
    s.setAttribute("aria-checked", String(on));
  });
  voiceMode = b.dataset.v;
});

/* ══════════════ entrada del archivo ══════════════ */
el.drop.addEventListener("click", () => el.file.click());
el.drop.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); el.file.click(); }
});
el.file.addEventListener("change", () => {
  if (el.file.files && el.file.files[0]) accept(el.file.files[0]);
});

["dragenter","dragover"].forEach(t =>
  el.drop.addEventListener(t, (e) => { e.preventDefault(); el.drop.classList.add("over"); }));
["dragleave","drop"].forEach(t =>
  el.drop.addEventListener(t, (e) => { e.preventDefault(); el.drop.classList.remove("over"); }));

el.drop.addEventListener("drop", (e) => {
  const f = e.dataTransfer?.files?.[0];
  if (f) accept(f);
});
// que soltar el archivo FUERA de la zona no navegue a él
window.addEventListener("dragover", e => e.preventDefault());
window.addEventListener("drop",     e => e.preventDefault());

function accept(file){
  if (running) return;
  const looksVideo = file.type.startsWith("video/") ||
                     /\.(mp4|mov|mkv|avi|webm|m4v|mxf|mpg|mpeg)$/i.test(file.name);
  if (!looksVideo){
    el.drop.animate(
      [{transform:"translateX(0)"},{transform:"translateX(-9px)"},
       {transform:"translateX(8px)"},{transform:"translateX(0)"}],
      {duration:320, easing:"ease-in-out"});
    return;
  }
  running = true;
  readMeta(file).then(meta => start({
    name: file.name, size: file.size,
    dur: meta.dur, w: meta.w, h: meta.h,
  }));
}

/* Puerta de entrada común. El archivo puede venir de tu disco (arrastrado) o de tu
   Drive (elegido en el buscador de Google, ver drive.js): de acá para abajo la demo
   no distingue, porque en los dos casos lo único que tiene son metadatos. */
window.DubAIDemo = {
  isRunning: () => running,
  begin(src){
    if (running) return;
    running = true;
    clearThumb();
    if (src.thumb) paintThumb(src.thumb);
    start(src);
  },
};

function clearThumb(){
  const c = el.thumb.getContext("2d");
  c.clearRect(0, 0, el.thumb.width, el.thumb.height);
}

/* la miniatura de Drive llega como URL; puede fallar por CORS y no es grave */
function paintThumb(url){
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.referrerPolicy = "no-referrer";
  img.onload = () => {
    const c = el.thumb.getContext("2d");
    const s = Math.max(el.thumb.width / img.width, el.thumb.height / img.height);
    const w = img.width * s, h = img.height * s;
    c.drawImage(img, (el.thumb.width - w)/2, (el.thumb.height - h)/2, w, h);
  };
  img.src = url;
}

/* lee duración y resolución, y roba un cuadro para la miniatura — todo local */
function readMeta(file){
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const v = document.createElement("video");
    v.preload = "metadata"; v.muted = true; v.playsInline = true; v.src = url;

    const done = (meta) => { resolve(meta); };
    const fallback = later(() => done({dur:0,w:0,h:0,url}), 4000);

    v.addEventListener("loadedmetadata", () => {
      const meta = {dur:v.duration, w:v.videoWidth, h:v.videoHeight, url, v};
      // buscar un cuadro con contenido (no el negro del arranque)
      const t = clamp(v.duration * 0.18, 0.4, 90);
      v.addEventListener("seeked", () => {
        try{
          const c = el.thumb.getContext("2d");
          c.drawImage(v, 0, 0, el.thumb.width, el.thumb.height);
        }catch(_){ /* si el códec no deja pintar, queda el fondo negro */ }
        clearTimeout(fallback);
        done(meta);
      }, {once:true});
      v.currentTime = t;
    }, {once:true});

    v.addEventListener("error", () => { clearTimeout(fallback); done({dur:0,w:0,h:0,url}); },
                       {once:true});
  });
}

/* ══════════════ las etapas (nombres reales del motor) ══════════════ */
function buildStages(ctx){
  const L = LANGS[el.lang.value] || LANGS.es;
  const clon = voiceMode === "clon";
  return [
  { tag:"extract", w:3, name:"Extrayendo el audio",
    logs:[ c => `pista de audio · ${c.w}×${c.h} · ${mmss(c.dur)}`,
           () => `wav 48 kHz estéreo + copia a 16 kHz para el análisis` ]},

  { tag:"separate", w:9, name:"Separando las voces de la música",
    logs:[ () => `BS-Roformer · separando diálogo / música / efectos`,
           c => `${c.win} ventana${c.win>1?"s":""} de 5 min en paralelo`,
           () => `M&E preservado aparte — la música original no se toca` ]},

  { tag:"p2window", w:8, name:"Identificando quién habla",
    logs:[ () => `pyannote Precision-2 sobre la película <b>completa</b>`,
           c => `${c.spk} hablantes distintos`,
           () => `huella ECAPA por hablante contra el ledger de casting` ]},

  { tag:"clone", w:10, name: clon ? "Clonando las voces del elenco"
                                  : "Eligiendo voces de catálogo",
    logs: clon
      ? [ c => `${c.spk} voces sin clon previo — clonando`,
          () => `muestras limpias tomadas del stem de diálogo`,
          c => `<em>${c.spk} clones listos</em> · se reusan en los próximos episodios` ]
      : [ () => `midiendo tono y registro de cada hablante`,
          c => `${c.spk} voces de catálogo asignadas por timbre medido` ]},

  { tag:"asr", w:7, name:"Transcribiendo el diálogo original",
    logs:[ () => `Scribe · transcripción con marcas de tiempo`,
           c => `${c.takes} intervenciones · ${nfmt(c.words)} palabras` ]},

  { tag:"mouth+asd", w:7, name:"Mirando la boca en pantalla",
    logs:[ () => `TalkNet-ASD · quién habla en cuadro y si la boca se ve`,
           c => `${c.visible} de ${c.takes} tomas con boca visible`,
           () => `esas pesan más el esfuerzo bilabial (P, B, M)` ]},

  { tag:"emotion", w:5, name:"Midiendo la actuación del actor",
    logs:[ () => `intensidad y registro por toma, del audio original`,
           () => `la vara no es "buen TTS": es el parecido con el actor` ]},

  { tag:"translate", w:13, name:`Adaptando el diálogo al ${L.n}`,
    logs:[ () => `adaptación, no traducción: se mide la duración hablada real`,
           c => `${c.takes} tomas · candidatas hasta que entra en la boca`,
           c => `<em>${c.fit} de ${c.takes}</em> entran sin recortar` ]},

  { tag:"labial", w:6, name:"Ajuste labial",
    logs:[ () => `reescritura para respetar las bilabiales visibles`,
           c => `${c.lab} líneas retocadas` ]},

  { tag:"nondialogue", w:5, name:"Rescatando lo no-verbal",
    logs:[ () => `risas, gritos, respiraciones y canto del original`,
           c => `${c.nv} eventos preservados` ]},

  { tag:"synth", w:14, name:"Sintetizando las tomas",
    logs:[ () => `${L.m} · una toma por pieza`,
           c => `${c.takes} tomas · caché por hash de contenido`,
           c => `<em>${c.takes} tomas sintetizadas</em>` ]},

  { tag:"postexact", w:6, name:"Colocando e isocronía",
    logs:[ () => `cada toma anclada al arranque real de la boca`,
           () => `el texto cede; el audio nunca se comprime` ]},

  { tag:"postmix+master", w:5, name:"Mezcla y máster",
    logs:[ () => `voz doblada contra el M&E original`,
           () => `máster estéreo · -16 LUFS · pico -1 dBTP` ]},

  { tag:"qa", w:2, name:"Control de calidad",
    logs:[ () => `cobertura de diálogo, sincronía y timbre por pieza`,
           () => `<em>sin piezas marcadas</em>` ]},
  ];
}

/* números plausibles derivados del archivo real que soltaste */
function makeCtx(meta){
  const dur   = meta.dur > 0 ? meta.dur : 300;
  const mins  = dur / 60;
  const takes = Math.max(6, Math.round(mins * 10.6));       // ~53 tomas en 5 min
  const spk   = clamp(Math.round(2 + mins * 0.6), 2, 12);
  return {
    dur, w: meta.w || 1920, h: meta.h || 1080,
    win: Math.max(1, Math.ceil(dur / 300)),
    takes, spk,
    words:   Math.round(takes * 8.4),
    visible: Math.round(takes * 0.62),
    fit:     Math.round(takes * 0.81),
    lab:     Math.round(takes * 0.17),
    nv:      Math.round(mins * 5.2),
  };
}

/* ══════════════ la corrida ══════════════ */
function start(src){
  const ctx    = makeCtx(src);
  const stages = buildStages(ctx);

  el.wName.textContent  = src.name;
  const size = src.size ? ` · ${(src.size/1e6).toFixed(0)} MB` : "";
  const orig = src.from === "drive" ? " · desde Drive" : "";
  el.wSpecs.textContent =
    `${mmss(ctx.dur)} · ${ctx.w}×${ctx.h}${size}`
    + ` · ${ctx.win} ventana${ctx.win>1?"s":""}${orig}`;

  el.pDrop.hidden = true;
  el.pWork.hidden = false;
  el.pWork.scrollIntoView({block:"center", behavior:"smooth"});

  // pintar la lista de etapas
  el.steps.innerHTML = "";
  stages.forEach((s,i) => {
    const li = document.createElement("li");
    li.className = "step"; li.id = `st${i}`;
    li.innerHTML =
      `<span class="step-dot"><svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg></span>`
      + `<span class="step-name"></span><span class="step-tag"></span>`;
    li.querySelector(".step-name").textContent = s.name;
    li.querySelector(".step-tag").textContent  = s.tag;
    el.steps.appendChild(li);
  });

  el.console.innerHTML = "";
  startBars();
  say(`<b>${src.name}</b> — ${mmss(ctx.dur)}`);
  say(`destino: ${(LANGS[el.lang.value]||LANGS.es).n} · voces: ${voiceMode}`);

  // repartir el tiempo total según el peso de cada etapa
  const totalW = stages.reduce((a,s) => a + s.w, 0);
  let acc = 0;
  const marks = stages.map(s => {
    const t0 = acc; acc += s.w / totalW * TOTAL_MS;
    return {t0, t1: acc};
  });

  stages.forEach((s,i) => {
    const {t0,t1} = marks[i];
    const dur = t1 - t0;
    later(() => {
      document.querySelectorAll(".step.now").forEach(n => {
        n.classList.remove("now"); n.classList.add("done");
      });
      const li = document.getElementById(`st${i}`);
      li.classList.add("now");
      // que la etapa activa quede a la vista en pantallas chicas
      li.scrollIntoView({block:"nearest"});
      s.logs.forEach((fn,k) =>
        later(() => say(fn(ctx)), dur * (0.18 + 0.62 * k / Math.max(1, s.logs.length))));
    }, t0);
  });

  // progreso continuo
  const t0 = performance.now();
  (function tick(){
    const p = clamp((performance.now() - t0) / TOTAL_MS, 0, 1);
    setRing(p);
    if (p < 1) requestAnimationFrame(tick);
  })();

  later(() => {
    document.querySelectorAll(".step.now").forEach(n => {
      n.classList.remove("now"); n.classList.add("done");
    });
    setRing(1);
    say(`<em>listo</em> — ${ctx.takes} tomas colocadas`);
    later(() => finish(ctx), 900);
  }, TOTAL_MS);
}

function setRing(p){
  const C = 2 * Math.PI * 52;
  el.ring.style.strokeDashoffset = String(C * (1 - p));
  el.pct.innerHTML = `${Math.round(p*100)}<i>%</i>`;
}

function say(html){
  const d = document.createElement("div");
  d.innerHTML = html;
  el.console.appendChild(d);
  while (el.console.children.length > 7) el.console.removeChild(el.console.firstChild);
}

/* barritas de espectro — decorativas, no analizan audio */
let barsRAF = null;
function startBars(){
  if (!el.bars.children.length){
    for (let i=0;i<64;i++) el.bars.appendChild(document.createElement("span"));
  }
  const kids = [...el.bars.children];
  const phase = kids.map((_,i) => i * 0.35);
  let t = 0;
  (function loop(){
    t += 0.09;
    kids.forEach((s,i) => {
      const v = (Math.sin(t + phase[i]) + Math.sin(t*0.63 + phase[i]*1.7)) / 2;
      const env = 0.45 + 0.55 * Math.sin(i / kids.length * Math.PI);
      s.style.height = `${clamp((0.5 + v*0.5) * env * 100, 6, 100)}%`;
    });
    barsRAF = requestAnimationFrame(loop);
  })();
}
function stopBars(){ if (barsRAF) cancelAnimationFrame(barsRAF); barsRAF = null; }

/* ══════════════ resultado ══════════════ */
function finish(ctx){
  stopBars();
  el.pWork.hidden = true;
  el.pDone.hidden = false;
  el.doneLang.textContent = (LANGS[el.lang.value] || LANGS.es).n;

  // las cifras de la tarjeta salen de lo que se acaba de "medir"
  const stats = el.pDone.querySelectorAll(".stat b");
  if (stats.length >= 4){
    stats[0].textContent = String(ctx.takes);
    stats[1].textContent = String(ctx.spk);
  }
  el.pDone.scrollIntoView({block:"center", behavior:"smooth"});
  running = false;
}

el.again.addEventListener("click", () => {
  clearTimers();
  el.video.pause();
  el.pDone.hidden = true;
  el.pWork.hidden = true;
  el.pDrop.hidden = false;
  el.file.value = "";
  const ds = document.getElementById("drive-status");
  if (ds){ ds.textContent = ""; ds.className = "drive-status"; }
  setRing(0);
  el.pDrop.scrollIntoView({block:"center", behavior:"smooth"});
});

})();
