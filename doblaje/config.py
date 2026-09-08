# -*- coding: utf-8 -*-
"""Configuración única de Doblaje. Todo lo que es una ruta, una clave o un umbral vive acá."""
from __future__ import annotations

import glob
import os
import shutil
from pathlib import Path

PAQUETE = Path(__file__).resolve().parent              # .../doblaje/doblaje
RAIZ = PAQUETE.parent                                  # la carpeta de la app (o del repo)
FOTON = Path(os.getenv("FOTON", str(RAIZ.parent.parent.parent if RAIZ.parent.name == "apps" else RAIZ.parent)))


def cargar_env() -> None:
    """`.env` de la app primero; lo que falte, de `dubai_v2/.env` (las claves ya viven ahí)."""
    for p in (RAIZ / ".env", FOTON / "dubai_v2" / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


cargar_env()


def _ffmpeg() -> str:
    """FFMPEG del entorno; si no, el de dubai_v2; si no, ~/ffmpeg/*/bin; si no, el del PATH;
    si no, el binario que trae el paquete `imageio-ffmpeg` (Render y otros Linux sin ffmpeg)."""
    if os.getenv("FFMPEG"):
        return os.environ["FFMPEG"]
    local = FOTON / "dubai_v2" / "_bin" / "ffmpeg.exe"
    if local.exists():
        return str(local)
    casa = sorted(glob.glob(str(Path.home() / "ffmpeg" / "*" / "bin" / "ffmpeg.exe")))
    if casa:
        return casa[-1]
    en_path = shutil.which("ffmpeg")
    if en_path:
        return en_path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _ffprobe() -> str | None:
    """El ffprobe que acompaña a ese ffmpeg, o el del PATH. `None` si no hay: media.py
    saca la duración con `ffmpeg -i` (imageio-ffmpeg trae ffmpeg pero no ffprobe)."""
    if os.getenv("FFPROBE"):
        return os.environ["FFPROBE"]
    p = Path(FFMPEG)
    if p.parent != Path("") and "ffmpeg" in p.name:
        cand = p.with_name(p.name.replace("ffmpeg", "ffprobe"))
        if cand.exists():
            return str(cand)
    return shutil.which("ffprobe")


FFMPEG = _ffmpeg()
FFPROBE = _ffprobe()

TRABAJO = Path(os.getenv("DOBLAJE_TRABAJO", str(RAIZ / "_trabajo")))
PREFIJO = "doblaje"                                    # la carpeta de salida en Drive

# ---- ElevenLabs ----
API = "https://api.elevenlabs.io"
MODELO = "dubbing_v2"
CR_POR_MIN = float(os.getenv("DOBLAJE_CR_POR_MIN", "13245"))      # medido 7-sep-2026, cuenta paga
CLONACION_DEFAULT = int(os.getenv("DOBLAJE_CLONACION", "1"))     # 7 = default de ElevenLabs = copia el original
MAX_MIN_VIDEO = 180                                              # límite de ElevenLabs por archivo
CONCURRENCIA_ELEVEN = 3                                          # trabajos de dubbing a la vez por cuenta

# ---- verificación ----
UMBRAL = float(os.getenv("DOBLAJE_UMBRAL", "0.28"))              # validado 4/4 contra el oído (7-sep-2026)
SR_VERIF = 16000

# ---- subida ----
MAX_SUBIDA_MB = float(os.getenv("DOBLAJE_MAX_SUBIDA_MB", "200"))

# ---- topes de la web ----
SIMULTANEOS = int(os.getenv("DOBLAJE_SIMULTANEOS", "2"))
MAX_POR_DIA = int(os.getenv("DOBLAJE_MAX_POR_DIA", "30"))

# ---- cuentas: (clave de entorno, etiqueta) ----
CUENTAS = [("ELEVENLABS_API_KEY", "principal"), ("ELEVENLABS_API_KEY_ALT", "alternativa")]

# ---- motores ----
MOTORES = [
    dict(id="eleven_v2", nombre="ElevenLabs Dubbing v2", disponible=True,
         detalle="Transcribe, traduce y sintetiza con la voz clonada del actor. Se cobra por segundo de fuente."),
    dict(id="propio", nombre="Motor propio", disponible=False,
         detalle="La cadena propia (ASR → traducción → clones con casting). Todavía no está subido."),
]

# ---- idiomas (BCP-47; los dialectos son los que Dubbing v2 acepta como destino) ----
IDIOMAS_DESTINO = [
    ("pt-BR", "Portugués (Brasil)"), ("pt-PT", "Portugués (Portugal)"),
    ("en-US", "Inglés (EE. UU.)"), ("en-GB", "Inglés (Reino Unido)"),
    ("es-MX", "Español (México)"), ("es-ES", "Español (España)"), ("es", "Español (neutro)"),
    ("fr", "Francés"), ("it", "Italiano"), ("de", "Alemán"), ("ja", "Japonés"), ("ko", "Coreano"),
    ("zh", "Chino"), ("hi", "Hindi"), ("ar", "Árabe"), ("tr", "Turco"), ("ru", "Ruso"),
    ("pl", "Polaco"), ("nl", "Neerlandés"), ("id", "Indonesio"), ("tl", "Filipino"),
]
IDIOMAS_ORIGEN = [("auto", "Detectar solo"), ("es", "Español"), ("en", "Inglés"), ("pt", "Portugués"),
                  ("fr", "Francés"), ("it", "Italiano"), ("de", "Alemán")]
