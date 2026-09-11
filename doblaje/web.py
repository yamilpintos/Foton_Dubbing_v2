# -*- coding: utf-8 -*-
"""
Doblaje web: conectás tu Google Drive, elegís videos, motor, idioma y fuerza de clonado,
ves el costo contra el saldo real, y cada video se dobla, se verifica y se sube a una
carpeta `doblaje/` al lado del original.

Sola:              python -m doblaje.web        →  http://localhost:8790
Dentro del portal: el portal hace  app.mount("/doblaje", doblaje.web.app)

Cumple el contrato de docs/AGREGAR_HERRAMIENTA.md: expone `app`, URLs relativas, calcula
su URL absoluta del request, corre sola.

★ GUARDAS DE GASTO (cada una independiente):
  1. la estimación está a la vista antes de confirmar, contra el saldo real de la cuenta
  2. no arranca si el saldo no alcanza para lo que se pidió
  3. no manda dos veces el mismo video mientras uno está en curso
  4. tope de trabajos a la vez (ElevenLabs admite 3 por cuenta) y por día
  5. un video de más de MAX_MIN_VIDEO no entra
  6. cancelar corta ANTES de crear el proyecto; después ya está cobrado, y lo dice
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import sys
import threading
import time
import traceback
import uuid
from datetime import date, datetime
from pathlib import Path
from queue import Queue

for _s in (sys.stdout, sys.stderr):          # consola cp1252 de Windows
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests

from . import config as C
from . import drive, media, verificar
from .dubbing import Cuenta, DubbingError, estimar_creditos

AQUI = Path(__file__).resolve().parent
ESTATICO = AQUI / "static"
PUERTO = int(os.getenv("DOBLAJE_PUERTO", os.getenv("PORT", "8790")))
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()          # un espacio pegado en el panel = invalid_client
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
SCOPES = ["https://www.googleapis.com/auth/drive",
          "https://www.googleapis.com/auth/userinfo.email", "openid"]
if not os.getenv("RENDER"):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
TRABAJOS_JSON = C.TRABAJO / "trabajos.json"

app = FastAPI(title="Doblaje")


# ---------------------------------------------------------------- cuentas
def _cuentas() -> list[dict]:
    return [dict(id=et, etiqueta=et) for var, et in C.CUENTAS if os.getenv(var)]


def _cuenta(nombre: str | None) -> Cuenta:
    for var, et in C.CUENTAS:
        if (nombre or C.CUENTAS[0][1]) == et:
            return Cuenta(os.getenv(var, ""), et)
    raise HTTPException(400, f"cuenta desconocida: {nombre}")


# ---------------------------------------------------------------- sesiones (en memoria)
_sesiones: dict[str, dict] = {}
COOKIE = "db_sesion"


def _mi_url(req: Request) -> str:
    forzada = os.getenv("DOBLAJE_URL")
    return forzada.rstrip("/") if forzada else str(req.base_url).rstrip("/") + req.scope.get("root_path", "")


def _sesion(req: Request) -> dict:
    tok = req.cookies.get(COOKIE)
    if not tok or tok not in _sesiones or "creds" not in _sesiones[tok]:
        raise HTTPException(401, "no conectado")
    return _sesiones[tok]


def _creds_a_dict(c: Credentials) -> dict:
    return dict(token=c.token, refresh_token=c.refresh_token, token_uri=c.token_uri,
                client_id=c.client_id, client_secret=c.client_secret, scopes=list(c.scopes or []))


def _creds(s: dict, forzar_refresh: bool = False) -> Credentials:
    c = Credentials(**s["creds"])
    if (c.expired or forzar_refresh) and c.refresh_token:
        c.refresh(google.auth.transport.requests.Request())
        s["creds"] = _creds_a_dict(c)
    return c


def _drive(s: dict):
    return drive.cliente(_creds(s))


def _flow(req: Request, state=None) -> Flow:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(500, "faltan GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET en .env")
    cb = _mi_url(req) + "/auth/callback"
    cfg = {"web": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                   "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                   "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": [cb]}}
    f = Flow.from_client_config(cfg, scopes=SCOPES, state=state)
    f.redirect_uri = cb
    return f


# ---------------------------------------------------------------- rutas básicas
@app.get("/")
def index():
    return FileResponse(str(ESTATICO / "index.html"))


@app.get("/api/config")
def api_config(req: Request):
    return dict(google_configurado=bool(CLIENT_ID and CLIENT_SECRET), callback=_mi_url(req) + "/auth/callback",
                motores=C.MOTORES, idiomas_destino=C.IDIOMAS_DESTINO, idiomas_origen=C.IDIOMAS_ORIGEN,
                clonacion_default=C.CLONACION_DEFAULT, cr_por_min=C.CR_POR_MIN, umbral=C.UMBRAL,
                cuentas=_cuentas(), verificacion=verificar.disponible(), ffmpeg=media.ffmpeg_disponible(),
                nivel=dict(activo=C.NIVELAR, modo=C.MODO_NIVEL, separador=media.separador_disponible()),
                limites=dict(simultaneos=C.SIMULTANEOS, max_por_dia=C.MAX_POR_DIA, max_min_video=C.MAX_MIN_VIDEO))


def _pagina_error(req: Request, titulo: str, detalle: str, pistas: list[str], status: int = 500):
    """Una página legible en vez del 'Internal Server Error' pelado: qué falló y qué revisar."""
    from html import escape
    raiz = req.scope.get("root_path", "") or ""
    items = "".join(f"<li>{escape(p)}</li>" for p in pistas)
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Doblaje · error al conectar</title>
<style>body{{font-family:system-ui,sans-serif;background:#F3F4F6;color:#151A21;margin:0}}main{{max-width:680px;margin:48px auto;padding:0 24px}}
.box{{background:#fff;border:1px solid #E2E6EB;border-radius:12px;padding:22px}}h1{{font-size:1.25rem;margin:0 0 10px}}
pre{{background:#F9E3E1;color:#B3261E;padding:12px;border-radius:8px;white-space:pre-wrap;word-break:break-word;font-size:.85rem}}
li{{margin:6px 0;color:#4A5563}}a{{color:#2F6FED;font-weight:600}}</style></head><body><main><div class="box">
<h1>{escape(titulo)}</h1><pre>{escape(detalle)}</pre><p>Qué revisar:</p><ul>{items}</ul>
<p><a href="{raiz}/">← Volver e intentar de nuevo</a></p></div></main></body></html>"""
    return HTMLResponse(html, status_code=status)


PISTAS_GOOGLE = [
    "GOOGLE_CLIENT_SECRET en el servidor: tiene que ser el secreto del MISMO cliente que GOOGLE_CLIENT_ID, sin espacios ni saltos de línea pegados.",
    "En Google Cloud → Credenciales → ese cliente OAuth (tipo 'Aplicación web') → 'URI de redireccionamiento autorizados' tiene que estar EXACTAMENTE la URL de callback que muestra api/config.",
    "Pantalla de consentimiento en modo 'prueba': tu mail tiene que figurar como usuario de prueba, si no Google bloquea el ingreso.",
    "Si volviste a esta página después de mucho tiempo o abriste el login en dos pestañas, la sesión venció: volvé y conectá de nuevo.",
]


@app.get("/auth/login")
def login(req: Request):
    try:
        f = _flow(req)
        url, state = f.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    except HTTPException:
        raise
    except Exception as e:
        print("[auth/login] " + traceback.format_exc(), flush=True)
        return _pagina_error(req, "No pude armar el pedido de conexión a Google", f"{type(e).__name__}: {e}", PISTAS_GOOGLE)
    tok = secrets.token_urlsafe(24)
    # ★ PKCE: google-auth-oauthlib ≥ 1.1 genera un code_verifier al armar el login y Google exige
    #   el MISMO al canjear el código. El callback crea otro Flow, así que hay que guardarlo acá.
    _sesiones[tok] = dict(state=state, code_verifier=getattr(f, "code_verifier", None))
    r = RedirectResponse(url)
    r.set_cookie(COOKIE, tok, httponly=True, samesite="lax", secure=bool(os.getenv("RENDER")))
    return r


@app.get("/auth/callback")
def callback(req: Request):
    raiz = req.scope.get("root_path", "") or "/"
    destino = raiz if raiz.endswith("/") else raiz + "/"
    s = _sesiones.get(req.cookies.get(COOKIE) or "")
    if not s:
        return RedirectResponse(destino)
    # Google vuelve con ?error=... cuando el usuario cancela o la cuenta no está permitida
    err = req.query_params.get("error")
    if err:
        return _pagina_error(req, "Google no autorizó la conexión", f"Google devolvió: {err}", PISTAS_GOOGLE, status=400)
    try:
        f = _flow(req, state=s.get("state"))
        if s.get("code_verifier"):
            f.code_verifier = s["code_verifier"]          # sin esto: "(invalid_grant) Missing code verifier"
        url = str(req.url)
        f.fetch_token(authorization_response=url.replace("http://", "https://", 1) if os.getenv("RENDER") else url)
    except HTTPException:
        raise
    except Exception as e:
        # ★ acá es donde antes moría en silencio con un 500: Google rechazó el intercambio del código
        print("[auth/callback] " + traceback.format_exc(), flush=True)
        return _pagina_error(req, "Google rechazó el intercambio del código", f"{type(e).__name__}: {e}", PISTAS_GOOGLE)
    s["creds"] = _creds_a_dict(f.credentials)
    try:
        info = build("oauth2", "v2", credentials=f.credentials, cache_discovery=False).userinfo().get().execute()
        s["email"], s["nombre"] = info.get("email", ""), info.get("name", "")
    except Exception:
        s["email"] = s["nombre"] = ""
    return RedirectResponse(destino)


@app.post("/auth/logout")
def logout(req: Request):
    _sesiones.pop(req.cookies.get(COOKIE) or "", None)
    r = JSONResponse(dict(ok=True))
    r.delete_cookie(COOKIE)
    return r


@app.get("/api/me")
def me(req: Request):
    s = _sesiones.get(req.cookies.get(COOKIE) or "")
    if not s or "creds" not in s:
        return dict(conectado=False)
    return dict(conectado=True, email=s.get("email", ""), nombre=s.get("nombre", ""))


def _error_drive(e: Exception) -> HTTPException:
    """Los errores de la API de Google, en cristiano y con qué hacer. Sin esto la página
    muestra 'No se pudo leer la carpeta:' y nada más."""
    from googleapiclient.errors import HttpError
    if isinstance(e, HttpError):
        try:
            err = json.loads(e.content.decode("utf-8", "replace")).get("error", {})
            msg = err.get("message", "") if isinstance(err, dict) else str(err)
            razones = [x.get("reason", "") for x in (err.get("errors", []) if isinstance(err, dict) else [])]
        except Exception:
            msg, razones = str(e), []
        st = getattr(getattr(e, "resp", None), "status", 0)
        if st == 403 and ("accessNotConfigured" in razones or "has not been used" in msg or "is disabled" in msg):
            return HTTPException(503, "La API de Google Drive no está habilitada en tu proyecto de Google Cloud. "
                                      "Habilitala en https://console.cloud.google.com/apis/library/drive.googleapis.com "
                                      "(con el mismo proyecto del cliente OAuth) y volvé a intentar en un minuto.")
        if st in (401, 403) and "insufficient" in msg.lower():
            return HTTPException(403, "Google no dio permiso sobre Drive. Desconectá (✕ arriba a la derecha) y volvé a "
                                      "conectar aceptando el acceso a Drive en la pantalla de Google.")
        if st == 401:
            return HTTPException(401, "no conectado")
        return HTTPException(502, f"Google Drive respondió {st}: {msg or e}")
    return HTTPException(500, f"{type(e).__name__}: {e}")


@app.get("/api/carpeta")
def carpeta(req: Request, id: str = "root"):
    s = _sesion(req)
    try:
        return drive.listar(_drive(s), id)
    except HTTPException:
        raise
    except Exception as e:
        print("[api/carpeta] " + traceback.format_exc(), flush=True)
        raise _error_drive(e)


@app.get("/api/buscar")
def buscar(req: Request, q: str = ""):
    """Carpetas y videos por nombre en todo el Drive, para no bajar nivel por nivel."""
    s = _sesion(req)
    q = q.strip()
    if len(q) < 2:
        raise HTTPException(400, "escribí al menos dos letras")
    try:
        return drive.buscar(_drive(s), q)
    except HTTPException:
        raise
    except Exception as e:
        print("[api/buscar] " + traceback.format_exc(), flush=True)
        raise _error_drive(e)


@app.get("/api/saldo")
def saldo(req: Request, cuenta: str | None = None):
    _sesion(req)
    c = _cuenta(cuenta)
    try:
        s = c.saldo()
    except DubbingError as e:
        return dict(ok=False, cuenta=c.etiqueta, error=str(e))
    ren = s.get("renueva_unix")
    return dict(ok=True, cuenta=c.etiqueta,
                renueva=datetime.fromtimestamp(ren).strftime("%d/%m %H:%M") if ren else None, **s)


@app.post("/api/estimar")
async def estimar(req: Request):
    """★ guarda 1: el número a la vista, contra el saldo real, antes de confirmar."""
    s = _sesion(req)
    body = await req.json()
    ids = list(dict.fromkeys(body.get("videos", [])))
    videos, total = [], 0.0
    try:
        d = _drive(s)
        for vid in ids:
            f = drive.meta(d, vid)
            dur = int((f.get("videoMediaMetadata") or {}).get("durationMillis", 0) or 0) / 1000
            videos.append(dict(id=vid, nombre=f["name"], duracion_s=dur, creditos=estimar_creditos(dur),
                               demasiado_largo=dur > C.MAX_MIN_VIDEO * 60, sin_duracion=dur == 0))
            total += dur
    except HTTPException:
        raise
    except Exception as e:
        print("[api/estimar] " + traceback.format_exc(), flush=True)
        raise _error_drive(e)
    creditos = estimar_creditos(total)
    out = dict(videos=videos, total_s=total, creditos=creditos, cr_por_min=C.CR_POR_MIN)
    try:
        sal = _cuenta(body.get("cuenta")).saldo()
        out.update(saldo=sal["libres"], plan=sal.get("plan"), alcanza=sal["libres"] >= creditos)
    except DubbingError as e:
        out.update(saldo=None, alcanza=None, error_saldo=str(e))
    return out


# ---------------------------------------------------------------- trabajos
_cola: Queue = Queue()
_trabajos: dict[str, dict] = {}
_lock = threading.Lock()
ACTIVOS = ("en cola", "procesando")
ETAPAS = dict(bajando="bajando de Drive", comprimiendo="comprimiendo para subir", subiendo="subiendo a ElevenLabs",
              transcribiendo="transcribiendo", doblando="traduciendo y doblando", audio="bajando el audio doblado",
              separando="separando voz y fondo para nivelar por pistas",
              montando="pegando el audio al video", verificando="verificando que no quede el original",
              drive="subiendo a Drive", fin="terminado")


def _guardar():
    C.TRABAJO.mkdir(parents=True, exist_ok=True)
    with _lock:
        TRABAJOS_JSON.write_text(json.dumps(list(_trabajos.values()), indent=1, ensure_ascii=False),
                                 encoding="utf-8")


def _activos() -> list[dict]:
    return [t for t in _trabajos.values() if t["estado"] in ACTIVOS]


def _de_hoy() -> int:
    hoy = date.today().isoformat()
    return sum(1 for t in _trabajos.values() if t["creado"].startswith(hoy))


def _log_en(t: dict):
    def _l(msg: str):
        t["log"].append(str(msg))
        if len(t["log"]) > 400:
            del t["log"][:100]
        print(f"[{t['nombre']}] {msg}", flush=True)
    return _l


@app.post("/api/doblar")
async def doblar(req: Request):
    s = _sesion(req)
    body = await req.json()
    ids = list(dict.fromkeys(body.get("videos", [])))
    if not ids:
        raise HTTPException(400, "no elegiste ningún video")
    motor = next((m for m in C.MOTORES if m["id"] == body.get("motor")), None)
    if not motor:
        raise HTTPException(400, "motor desconocido")
    if not motor["disponible"]:
        raise HTTPException(400, f"{motor['nombre']}: {motor['detalle']}")
    destino = body.get("idioma_destino")
    if destino not in {c for c, _ in C.IDIOMAS_DESTINO}:
        raise HTTPException(400, "idioma de destino desconocido")
    origen = body.get("idioma_origen") or "auto"
    try:
        clonacion = int(body.get("clonacion", C.CLONACION_DEFAULT))
    except (TypeError, ValueError):
        raise HTTPException(400, "la fuerza de clonado tiene que ser un entero de 0 a 10")
    if not 0 <= clonacion <= 10:
        raise HTTPException(400, "la fuerza de clonado va de 0 a 10")
    keyterms = [k.strip() for k in str(body.get("keyterms", "")).replace(";", ",").split(",") if k.strip()][:50]
    cuenta = _cuenta(body.get("cuenta"))
    # destino: una carpeta elegida en Drive, o (por defecto) `doblaje/` al lado de cada original
    destino_carpeta = (str(body.get("destino_carpeta") or "")).strip() or None
    destino_nombre = None

    # ---- guardas 3 y 4 ----
    en_curso = {t["video_id"] for t in _activos()}
    if any(v in en_curso for v in ids):
        raise HTTPException(409, "alguno de esos videos ya está en curso; esperá a que termine")
    if len(_activos()) + len(ids) > C.SIMULTANEOS * 6:
        raise HTTPException(429, f"demasiados trabajos encolados ({len(_activos())}); esperá a que bajen")
    if _de_hoy() + len(ids) > C.MAX_POR_DIA:
        raise HTTPException(429, f"tope de {C.MAX_POR_DIA} trabajos por día (van {_de_hoy()}). "
                                 f"Es una guarda de gasto; se sube con DOBLAJE_MAX_POR_DIA.")

    # ---- guardas 2 y 5: metadatos, largo y saldo ----
    metas, total = [], 0.0
    try:
        d = _drive(s)
        if destino_carpeta:
            m = drive.meta(d, destino_carpeta)
            if m.get("mimeType") != drive.CARPETA:
                raise HTTPException(400, "el destino elegido no es una carpeta de Drive")
            destino_nombre = m.get("name", "")
        for vid in ids:
            f = drive.meta(d, vid)
            dur = int((f.get("videoMediaMetadata") or {}).get("durationMillis", 0) or 0) / 1000
            if dur > C.MAX_MIN_VIDEO * 60:
                raise HTTPException(400, f"{f['name']} dura {dur/60:.0f} min; el máximo de ElevenLabs es {C.MAX_MIN_VIDEO}")
            metas.append((f, dur))
            total += dur
    except HTTPException:
        raise
    except Exception as e:
        print("[api/doblar] " + traceback.format_exc(), flush=True)
        raise _error_drive(e)
    try:
        libres = cuenta.saldo()["libres"]
    except DubbingError as e:
        raise HTTPException(502, f"no pude leer el saldo de ElevenLabs: {e}")
    necesita = estimar_creditos(total)
    if libres < necesita:
        raise HTTPException(402, f"el saldo no alcanza: hay {libres:,} créditos y esto necesita ~{necesita:,}")

    nuevos = []
    for f, dur in metas:
        t = dict(id=uuid.uuid4().hex[:10], video_id=f["id"], nombre=f["name"],
                 padre=(f.get("parents") or ["root"])[0], tamano=int(f.get("size", 0) or 0), duracion_s=dur,
                 motor=motor["id"], origen=origen, destino=destino, clonacion=clonacion, cuenta=cuenta.etiqueta,
                 keyterms=keyterms, estimado=estimar_creditos(dur),
                 destino_carpeta=destino_carpeta, destino_nombre=destino_nombre,
                 estado="en cola", etapa="", progreso=0.0, log=[], creado=time.strftime("%Y-%m-%d %H:%M:%S"),
                 usuario=s.get("email", ""), carpeta_salida_id=None, salidas=[], informe=None, error=None)
        _trabajos[t["id"]] = t
        _cola.put((t["id"], dict(s)))
        nuevos.append(t["id"])
    _guardar()
    return dict(trabajos=nuevos, creditos_estimados=necesita)


@app.get("/api/trabajos")
def trabajos(req: Request):
    s = _sesiones.get(req.cookies.get(COOKIE) or "") or {}
    mail = s.get("email")
    lista = [dict(t, log=t["log"][-4:]) for t in _trabajos.values() if not mail or t.get("usuario") == mail]
    return dict(trabajos=sorted(lista, key=lambda t: t["creado"], reverse=True))


@app.post("/api/trabajos/{tid}/cancelar")
def cancelar(req: Request, tid: str):
    _sesion(req)
    t = _trabajos.get(tid)
    if not t:
        raise HTTPException(404, "no existe")
    if t["estado"] not in ACTIVOS:
        return dict(ok=True, estado=t["estado"])
    t["cancelar"] = True
    if t["estado"] == "en cola":
        t["estado"], t["etapa"] = "cancelado", "cancelado antes de empezar"
    _guardar()
    return dict(ok=True, estado=t["estado"])


# ---------------------------------------------------------------- el trabajo en sí
def _procesar(t: dict, s: dict):
    log = _log_en(t)
    cancelado = lambda: bool(t.get("cancelar"))
    wdir = C.TRABAJO / "web" / t["id"]
    wdir.mkdir(parents=True, exist_ok=True)

    def etapa(k, f):
        t["etapa"], t["progreso"] = ETAPAS[k], f
    try:
        t["estado"] = "procesando"
        cuenta = _cuenta(t["cuenta"])
        d = _drive(s)

        etapa("bajando", 0.0)
        local = wdir / t["nombre"]
        log(f"bajando {t['nombre']} ({t['tamano']/1e6:.0f} MB)")
        drive.bajar(d, t["video_id"], local, lambda f: t.__setitem__("progreso", 0.15 * f))
        if cancelado():
            raise DubbingError("cancelado")
        dur = media.duracion_s(local) or t["duracion_s"]
        t["duracion_s"] = dur
        if dur > C.MAX_MIN_VIDEO * 60:
            raise DubbingError(f"dura {dur/60:.0f} min; el máximo es {C.MAX_MIN_VIDEO}")

        a_subir = local
        if local.stat().st_size > C.MAX_SUBIDA_MB * 1e6:
            etapa("comprimiendo", 0.15)
            a_subir = media.comprimir_para_subir(local, wdir / "liviano.mp4")
            log(f"comprimido para subir: {local.stat().st_size/1e6:.0f} MB → "
                f"{a_subir.stat().st_size/1e6:.0f} MB (mismo cobro)")
        if cancelado():
            raise DubbingError("cancelado")

        saldo_antes = cuenta.saldo()["libres"]
        etapa("subiendo", 0.25)
        log(f"subiendo a ElevenLabs · destino {t['destino']} · clonación {t['clonacion']} · cuenta {cuenta.etiqueta}")
        pid = cuenta.crear_proyecto(a_subir, t["origen"], f"doblaje :: {t['nombre']}", t["keyterms"])
        t.setdefault("informe", {})
        t["informe"] = t["informe"] or {}
        t["informe"]["project_id"] = pid
        log(f"proyecto {pid} · desde acá el cobro ya no se puede cancelar")
        etapa("transcribiendo", 0.35)
        p = cuenta.esperar_proyecto(pid)                      # sin cancelación: ya está cobrado
        if p.get("status") == "failed":
            raise DubbingError(f"ElevenLabs falló al preparar el proyecto: {p.get('error')}")
        etapa("doblando", 0.45)
        lid = cuenta.crear_idioma(pid, t["destino"], t["clonacion"])
        t["informe"]["language_id"] = lid
        L = cuenta.esperar_idioma(pid, lid)
        if L.get("status") == "failed":
            raise DubbingError(f"ElevenLabs falló al doblar: {L.get('error')}")
        url = (L.get("outputs") or {}).get("lossless_audio")
        if not url:
            raise DubbingError("ElevenLabs no devolvió el audio")

        etapa("audio", 0.75)
        wav_crudo = cuenta.bajar_audio(url, wdir / "doblado_crudo.wav")
        segs = cuenta.transcripto(pid)
        # ★ nivel. v2 entrega la voz +2…+10 dB sobre la original, el fondo casi intacto y picos > 0 dBFS.
        #   modo "pistas" (aprobado de oído 11-sep): se separan original y doblado, la voz doblada se lleva al
        #   nivel de la voz original (por segmento) y se mezcla con el FONDO ORIGINAL sin tocar → voz y fondo
        #   a ±0,1 dB. Necesita separador (lento en CPU). Sin separador, modo "mezcla": se iguala la sonoridad
        #   de la mezcla entera → la voz queda bien pero el fondo baja ~4 dB, y el informe lo muestra.
        nivel = None
        wav = wav_crudo
        usar_pistas = C.NIVELAR and C.MODO_NIVEL in ("pistas", "auto") and media.separador_disponible()
        if usar_pistas:
            etapa("separando", 0.76)
            log("separando voz y fondo del original y del doblado (2 pasadas, lento en CPU)")
            so = media.separar(media.extraer_audio(local, wdir / "orig_44k.wav"), wdir / "sep_orig", log)
            sd = media.separar(media.extraer_audio(wav_crudo, wdir / "dub_44k.wav"), wdir / "sep_dub", log) if so else None
            if so and sd:
                off = verificar.nivel_voz(so[0], sd[0], segs)
                gain_voz = -(off or 0.0)
                media.mezclar_pistas(sd[0], so[1], gain_voz, wdir / "doblado.wav")
                wav = wdir / "doblado.wav"
                e_o, e_n = media.sonoridad(local), media.sonoridad(wav)
                nivel = dict(modo="pistas", gain_db=round(gain_voz, 1), I_original=e_o.get("I"), I_antes=media.sonoridad(wav_crudo).get("I"),
                             I_despues=e_n.get("I"), tp_antes=None, tp_despues=e_n.get("TP"))
                log(f"pistas: voz doblada {off:+.1f} dB respecto de la voz original → corregida {gain_voz:+.1f} dB; fondo = el original")
            else:
                log("no pude separar: caigo al modo mezcla")
                usar_pistas = False
        if C.NIVELAR and not usar_pistas:
            nivel = media.igualar_sonoridad(local, wav_crudo, wdir / "doblado.wav")
            if nivel:
                nivel["modo"] = "mezcla"
                wav = wdir / "doblado.wav"
                log(f"nivel igualado al original: {nivel['gain_db']:+.1f} dB (de {nivel['I_antes']:.1f} a {nivel['I_despues']:.1f} LUFS, "
                    f"pico {nivel['tp_antes']:+.1f} → {nivel['tp_despues']:+.1f} dBFS)")
            else:
                log("no pude medir la sonoridad: queda sin nivelar")
        etapa("montando", 0.80)
        sufijo = t["destino"].replace("-", "")
        salida = wdir / f"{Path(t['nombre']).stem}_{sufijo}.mp4"
        media.pegar_audio(local, wav, salida)

        etapa("verificando", 0.85)
        ver = verificar.castellano_restante(local, wav, segs)
        if nivel is not None:
            nivel["voz_vs_original_antes_db"] = verificar.nivel_voz(local, wav_crudo, segs)
            nivel["voz_vs_original_db"] = verificar.nivel_voz(local, wav, segs)
            nivel["fondo_vs_original_db"] = verificar.nivel_fondo(local, wav, segs)
            if nivel["voz_vs_original_db"] is not None:
                log(f"voz respecto de la original: {nivel['voz_vs_original_antes_db']:+.1f} dB antes → {nivel['voz_vs_original_db']:+.1f} dB después")
            if nivel["fondo_vs_original_db"] is not None:
                log(f"fondo respecto del original: {nivel['fondo_vs_original_db']:+.1f} dB" +
                    ("  (v2 sube la voz y deja el fondo: al igualar la mezcla, el fondo baja; la corrección por pistas lo evita)"
                     if nivel["fondo_vs_original_db"] < -2 else ""))
        try:
            saldo_despues = cuenta.saldo()["libres"]
        except DubbingError:
            saldo_despues = None
        inf = dict(project_id=pid, language_id=lid, destino=t["destino"], clonacion=t["clonacion"],
                   duracion_s=round(dur, 1), segmentos=len(segs),
                   cobro=(saldo_antes - saldo_despues) if saldo_despues is not None else None,
                   saldo_antes=saldo_antes, saldo_despues=saldo_despues,
                   verificacion=ver, nivel=nivel, comprimido=a_subir is not local,
                   traduccion=[dict(inicio=x.get("start_s"), fin=x.get("end_s"), texto=x.get("source_text"),
                                    traduccion=x.get("translation")) for x in cuenta.traduccion(pid, lid)])
        t["informe"] = inf
        if ver is None:
            log("sin numpy: no se verificó")
        elif ver["restantes"]:
            log(f"quedan {len(ver['restantes'])} segmentos con el original: " +
                ", ".join(f"{r['inicio']}s" for r in ver["restantes"]))
        else:
            log("verificado: ningún segmento con el original")
        informe_json = wdir / f"{Path(t['nombre']).stem}_{sufijo}_informe.json"
        informe_json.write_text(json.dumps(inf, indent=1, ensure_ascii=False), encoding="utf-8")

        etapa("drive", 0.90)
        d = _drive(s)
        # a la carpeta que eligió el usuario, o a `doblaje/` dentro de la carpeta del original
        cid = t.get("destino_carpeta") or drive.carpeta_salida(d, t["padre"], C.PREFIJO)
        t["carpeta_salida_id"] = cid
        log("subiendo a " + (f"«{t['destino_nombre']}»" if t.get("destino_carpeta") else f"{C.PREFIJO}/ junto al original"))
        for k, p in enumerate((salida, informe_json)):
            log(f"subiendo {p.name}")
            t["salidas"].append(dict(nombre=p.name, id=drive.subir(d, p, cid)))
            t["progreso"] = 0.90 + 0.10 * (k + 1) / 2
        t["estado"] = "listo" if (ver is None or not ver["restantes"]) else "revisar"
        etapa("fin", 1.0)
    except Exception as e:
        if isinstance(e, DubbingError) and str(e) == "cancelado":
            t["estado"], t["etapa"] = "cancelado", "cancelado antes de subir a ElevenLabs"
        else:
            t["estado"], t["error"] = "error", f"{type(e).__name__}: {e}"
            log("ERROR " + traceback.format_exc()[-1200:])
    finally:
        _guardar()
        shutil.rmtree(wdir, ignore_errors=True)


def _worker():
    while True:
        tid, s = _cola.get()
        t = _trabajos.get(tid)
        if t and t["estado"] == "en cola" and not t.get("cancelar"):
            _procesar(t, s)
        _cola.task_done()


def _cargar_trabajos():
    if not TRABAJOS_JSON.exists():
        return
    for t in json.loads(TRABAJOS_JSON.read_text(encoding="utf-8")):
        if t["estado"] in ACTIVOS:
            t["estado"], t["etapa"] = "interrumpido", "la web se reinició"
        _trabajos[t["id"]] = t


_cargar_trabajos()
for _i in range(max(1, min(C.SIMULTANEOS, C.CONCURRENCIA_ELEVEN))):
    threading.Thread(target=_worker, daemon=True, name=f"doblaje-worker-{_i}").start()


def main():
    import uvicorn
    print(f"Doblaje -> http://localhost:{PUERTO}")
    if not (CLIENT_ID and CLIENT_SECRET):
        print("  AVISO: faltan GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET; la página explica cómo crearlos")
    if not _cuentas():
        print("  AVISO: falta ELEVENLABS_API_KEY")
    print(f"  ffmpeg: {C.FFMPEG} · verificación acústica: {'sí' if verificar.disponible() else 'NO (sin numpy)'}")
    uvicorn.run(app, host="0.0.0.0", port=PUERTO, log_level="warning", proxy_headers=True,
                forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
