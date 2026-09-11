# -*- coding: utf-8 -*-
"""Lo poco de ffmpeg que hace falta: medir, comprimir para subir, y pegar el audio nuevo."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from . import config as C


def duracion_s(path: Path) -> float:
    """Con ffprobe si hay; si no (Render con imageio-ffmpeg), `ffmpeg -i` imprime
    `Duration: HH:MM:SS.xx` en stderr y de ahí se saca."""
    if C.FFPROBE:
        r = subprocess.run([C.FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                            str(path)], capture_output=True, text=True, errors="replace")
        try:
            return float(r.stdout.strip())
        except ValueError:
            pass
    r = subprocess.run([C.FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def comprimir_para_subir(src: Path, dst: Path) -> Path:
    """720p CRF 26: 1,8 GB → 84 MB medido, misma duración. El cobro es por minuto de fuente,
    así que comprimir no cambia el precio; sólo la subida. El audio se mantiene entero."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([C.FFMPEG, "-y", "-v", "error", "-i", str(src), "-vf", "scale=-2:720", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "26", "-c:a", "aac", "-b:a", "192k", str(dst)], check=True)
    return dst


def pegar_audio(video_original: Path, audio: Path, dst: Path) -> Path:
    """El video ORIGINAL (calidad plena, copiado sin recodificar) con el audio doblado encima."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([C.FFMPEG, "-y", "-v", "error", "-i", str(video_original), "-i", str(audio),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", str(dst)], check=True)
    return dst


def ffmpeg_disponible() -> bool:
    try:
        subprocess.run([C.FFMPEG, "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def sonoridad(path: Path) -> dict:
    """Sonoridad integrada (EBU R128) y pico verdadero, con ffmpeg. {I: LUFS, TP: dBFS}; None si no pudo."""
    r = subprocess.run([C.FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true:framelog=quiet",
                        "-f", "null", "-"], capture_output=True, text=True, errors="replace")
    def ultimo(pat):
        m = re.findall(pat, r.stderr)
        return float(m[-1]) if m else None
    return dict(I=ultimo(r"I:\s*(-?[\d.]+) LUFS"), TP=ultimo(r"Peak:\s*(-?[\d.]+) dBFS"))


def igualar_sonoridad(original: Path, audio: Path, dst: Path, tp_max_db: float = C.TP_MAX_DB) -> dict | None:
    """Deja `dst` con el audio doblado a la MISMA sonoridad integrada que el original y los picos
    verdaderos por debajo de `tp_max_db`. Medido 11-sep sobre 4 videos: Dubbing v2 entrega ~-7,5 LUFS
    sea cual sea el original, con la voz +2…+10 dB y picos > 0 dBFS; con esto la voz queda a ±0,5 dB
    de la original. Devuelve la medición (o None si ffmpeg no pudo medir)."""
    eo, ed = sonoridad(original), sonoridad(audio)
    if eo.get("I") is None or ed.get("I") is None:
        return None
    gain = eo["I"] - ed["I"]
    lim = 10 ** (tp_max_db / 20)
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([C.FFMPEG, "-y", "-v", "error", "-i", str(audio),
                    "-af", f"volume={gain:.2f}dB,alimiter=limit={lim:.4f}:attack=5:release=50:level=false",
                    "-ar", "48000", "-c:a", "pcm_s16le", str(dst)], check=True)
    en = sonoridad(dst)
    return dict(gain_db=round(gain, 1), I_original=eo["I"], I_antes=ed["I"], I_despues=en.get("I"),
                tp_antes=ed.get("TP"), tp_despues=en.get("TP"))


# ---------------------------------------------------------------- pistas
def separador_disponible() -> bool:
    return Path(C.SEPARADOR).exists()


def extraer_audio(src: Path, dst: Path, sr: int = 44100) -> Path:
    """wav estéreo a `sr` (el separador espera 44,1 kHz)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([C.FFMPEG, "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "2", "-ar", str(sr),
                    "-c:a", "pcm_s16le", str(dst)], check=True)
    return dst


def separar(audio: Path, out_dir: Path, log=None) -> tuple[Path, Path] | None:
    """Voz y fondo con el separador sellado (BS-RoFormer, backend local). Devuelve
    (vocals_clean.wav, music_effects.wav) o None si no hay separador o falló. Lento en CPU:
    ~7 min por minuto de audio en la PC; en GPU, segundos."""
    if not separador_disponible():
        return None
    py = C.PY_SEP or sys.executable
    sep = Path(C.SEPARADOR)
    cwd = sep.parents[2] if len(sep.parents) > 2 else sep.parent      # .../dubai_v2, como se corre a mano
    out_dir.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([py, "-u", str(sep), str(audio), str(out_dir), "--backend", "local"],
                       capture_output=True, text=True, errors="replace", cwd=str(cwd))
    v, f = out_dir / "vocals_clean.wav", out_dir / "music_effects.wav"
    if r.returncode != 0 or not (v.exists() and f.exists()):
        if log:
            log("separador falló: " + (r.stdout + r.stderr)[-300:].strip())
        return None
    return v, f


def mezclar_pistas(voz: Path, fondo: Path, gain_voz_db: float, dst: Path, tp_max_db: float = C.TP_MAX_DB) -> Path:
    """voz doblada (con su corrección) + fondo original a unidad, limitador de picos, 48 kHz."""
    lim = 10 ** (tp_max_db / 20)
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([C.FFMPEG, "-y", "-v", "error", "-i", str(voz), "-i", str(fondo), "-filter_complex",
                    f"[0:a]aresample=48000,volume={gain_voz_db:.2f}dB[v];[1:a]aresample=48000[f];"
                    f"[v][f]amix=inputs=2:duration=first:normalize=0,alimiter=limit={lim:.4f}:attack=5:release=50:level=false[a]",
                    "-map", "[a]", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(dst)], check=True)
    return dst
