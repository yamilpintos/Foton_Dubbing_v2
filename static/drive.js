/* ══════════════════════════════════════════════════════════════════════════════
   Buscador sobre Google Drive.

   POR QUÉ ESTE PERMISO Y NO EL COMPLETO
   Se pide `drive.file`, que es el permiso ACOTADO: la app sólo ve los archivos que
   vos elegís a mano. Aun así podés buscar en TODO tu Drive, porque quien muestra y
   busca es el Picker de Google —corre dentro de tu sesión, no de esta página— y
   recién cuando elegís algo nos pasa ese archivo.

   La diferencia importa: el permiso completo (`drive.readonly`) es "restringido"
   para Google y exige verificar la app —semanas de trámite, y hasta entonces sólo
   entran las cuentas cargadas como usuarios de prueba—. Con `drive.file` no hace
   falta nada de eso y entra cualquiera, con la misma capacidad de búsqueda.

   Nada del video se descarga: se leen nombre, tamaño, duración, resolución y la
   miniatura. Alcanza de sobra para alimentar la demo.
   ══════════════════════════════════════════════════════════════════════════════ */
(() => {
"use strict";

const CFG   = window.DUBAI_CONFIG || {};
const SCOPE = "https://www.googleapis.com/auth/drive.file";

const btn    = document.getElementById("drive-btn");
const label  = document.getElementById("drive-label");
const status = document.getElementById("drive-status");
if (!btn) return;

let token = null;          // token de acceso, sólo en memoria: no se guarda en ningún lado
let tokenClient = null;
let pickerLoaded = false;

const configured = () => Boolean(CFG.GOOGLE_CLIENT_ID && CFG.GOOGLE_API_KEY);

function say(msg, kind){
  status.textContent = msg || "";
  status.className = "drive-status" + (kind ? ` is-${kind}` : "");
}
function busy(on, msg){
  btn.disabled = on;
  btn.classList.toggle("loading", on);
  if (msg) label.textContent = msg;
  if (!on) label.textContent = "Elegir desde mi Google Drive";
}

/* ── sin credenciales cargadas, el botón explica qué falta ── */
if (!configured()){
  btn.classList.add("off");
  say("Falta cargar las credenciales de Google en static/config.js — mirá el README.");
}

/* ── carga de las librerías de Google, a demanda ── */
function loadPicker(){
  return new Promise((ok, fail) => {
    if (pickerLoaded) return ok();
    if (!window.gapi) return fail(new Error("No cargó la librería de Google."));
    gapi.load("picker", {
      callback: () => { pickerLoaded = true; ok(); },
      onerror:  () => fail(new Error("No se pudo cargar el buscador de Drive.")),
    });
  });
}

function getToken(){
  return new Promise((ok, fail) => {
    if (token) return ok(token);
    if (!window.google?.accounts?.oauth2)
      return fail(new Error("No cargó la librería de Google. ¿Hay bloqueador de scripts?"));

    if (!tokenClient){
      tokenClient = google.accounts.oauth2.initTokenClient({
        client_id: CFG.GOOGLE_CLIENT_ID,
        scope: SCOPE,
        callback: (res) => {
          if (res.error) return fail(new Error(describe(res.error)));
          token = res.access_token;
          ok(token);
        },
        error_callback: (err) => fail(new Error(describe(err?.type || "popup_closed"))),
      });
    }
    tokenClient.callback = (res) => {
      if (res.error) return fail(new Error(describe(res.error)));
      token = res.access_token;
      ok(token);
    };
    tokenClient.requestAccessToken({prompt: token ? "" : "consent"});
  });
}

function describe(code){
  switch (code){
    case "popup_closed":
    case "popup_closed_by_user":  return "Cerraste la ventana de Google antes de dar el permiso.";
    case "popup_failed_to_open":  return "El navegador bloqueó la ventana de Google. Permití las ventanas emergentes.";
    case "access_denied":         return "Google no dio el permiso.";
    case "idpiframe_initialization_failed":
                                  return "Google no acepta este dominio. Agregalo como origen autorizado.";
    default:                      return `Google respondió: ${code}`;
  }
}

/* ── el buscador ── */
function openPicker(){
  const view = new google.picker.DocsView(google.picker.ViewId.DOCS_VIDEOS)
    .setIncludeFolders(true)
    .setSelectFolderEnabled(false);

  const all = new google.picker.DocsView()
    .setIncludeFolders(true)
    .setSelectFolderEnabled(false);

  const b = new google.picker.PickerBuilder()
    .setTitle("Elegí la película")
    .setOAuthToken(token)
    .setDeveloperKey(CFG.GOOGLE_API_KEY)
    .addView(view)                                  // videos, que es lo que se busca
    .addView(all)                                   // por si el archivo no figura como video
    .enableFeature(google.picker.Feature.SUPPORT_DRIVES)   // unidades compartidas
    .setCallback(onPick);

  if (CFG.GOOGLE_PROJECT_NUMBER) b.setAppId(CFG.GOOGLE_PROJECT_NUMBER);
  b.build().setVisible(true);
}

function onPick(data){
  const A = google.picker.Action, D = google.picker.Document;
  if (data[google.picker.Response.ACTION] === A.CANCEL){ say(""); busy(false); return; }
  if (data[google.picker.Response.ACTION] !== A.PICKED) return;

  const doc = data[google.picker.Response.DOCUMENTS][0];
  if (!doc) return;
  busy(true, "Leyendo el archivo…");
  say("");
  detail(doc[D.ID], doc[D.NAME]).then(start).catch(err => {
    busy(false);
    say(err.message, "err");
  });
}

/* metadatos del archivo elegido — nunca el video en sí */
async function detail(id, fallbackName){
  const fields = "id,name,size,mimeType,videoMediaMetadata,thumbnailLink";
  const url = `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(id)}`
            + `?fields=${encodeURIComponent(fields)}&supportsAllDrives=true`;

  const r = await fetch(url, {headers:{Authorization:`Bearer ${token}`}});
  if (!r.ok){
    if (r.status === 401 || r.status === 403){
      token = null;                       // vencido o revocado: que lo vuelva a pedir
      throw new Error("Google no dejó leer el archivo. Probá conectarte de nuevo.");
    }
    throw new Error(`No se pudo leer el archivo (${r.status}).`);
  }
  const f = await r.json();
  const v = f.videoMediaMetadata || {};

  return {
    name:  f.name || fallbackName || "pelicula.mp4",
    size:  Number(f.size) || 0,
    dur:   v.durationMillis ? Number(v.durationMillis) / 1000 : 0,
    w:     Number(v.width)  || 0,
    h:     Number(v.height) || 0,
    thumb: f.thumbnailLink || "",
    from:  "drive",
  };
}

function start(src){
  busy(false);
  say(`“${src.name}” tomada de tu Drive`, "ok");
  window.DubAIDemo.begin(src);
}

/* ── el botón ── */
btn.addEventListener("click", async () => {
  if (!configured()){
    say("Falta cargar las credenciales de Google en static/config.js — mirá el README.", "err");
    return;
  }
  if (window.DubAIDemo?.isRunning()) return;
  busy(true, "Conectando con Google…");
  say("");
  try{
    await getToken();
    busy(true, "Abriendo tu Drive…");
    await loadPicker();
    busy(false);
    openPicker();
  }catch(err){
    busy(false);
    say(err.message, "err");
  }
});

})();
