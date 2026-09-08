# -*- coding: utf-8 -*-
"""Lo poco de ffmpeg que hace falta: medir, comprimir para subir, y pegar el audio nuevo."""
from __future__ import annotations

import re
import subprocess
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
