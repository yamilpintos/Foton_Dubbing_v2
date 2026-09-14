# -*- coding: utf-8 -*-
"""
Verificación ACÚSTICA del doblaje: ¿quedó la voz original en algún segmento?

Por qué acústica y no por texto: entre castellano y portugués, "Ayuda, Sara, por favor"
y "Me ajuda, Sara, por favor" son casi la misma cadena, así que comparar transcripciones
no distingue nada (y dio por buenos seis segmentos que estaban en castellano). Lo que sí
funciona es comparar el AUDIO doblado contra el AUDIO original, por segmento declarado:
pasa-banda de voz (300-3400 Hz) y correlación normalizada buscando desfasaje de ±50 ms.
  · parecido > UMBRAL  →  quedó la voz original
  · parecido < UMBRAL  →  voz nueva
Calibrado el 7-sep-2026 contra el oído del usuario: 4 de 4. Los limpios dan 0,03-0,26;
los que quedaron en el original, 0,29-0,52.

Sin numpy no falla: devuelve `None` y la web avisa que no verificó.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import config as C

try:
    import numpy as np
except Exception:          # pragma: no cover
    np = None


def disponible() -> bool:
    return np is not None


def _cargar(path: Path):
    """Audio mono a SR_VERIF, leído por un pipe de ffmpeg (sin archivos temporales)."""
    cmd = [C.FFMPEG, "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(C.SR_VERIF), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0


def _banda(x):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / C.SR_VERIF)
    X[(f < 300) | (f > 3400)] = 0
    return np.fft.irfft(X, n)


def _parecido(a, b, maxlag: int = 800) -> float:
    a = _banda(a - a.mean())
    b = _banda(b - b.mean())
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    c = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    c = np.concatenate([c[-maxlag:], c[:maxlag + 1]]) / (na * nb)
    return float(np.max(np.abs(c)))


def castellano_restante(original: Path, doblado: Path, segmentos: list[dict],
                        umbral: float = C.UMBRAL) -> dict | None:
    """Por cada segmento declarado por ElevenLabs, cuánto se parece el doblado al original.
    Devuelve dict(segmentos=N, medidos=M, restantes=[{inicio, fin, parecido, texto}]) o None sin numpy."""
    if np is None:
        return None
    ao, ad = _cargar(original), _cargar(doblado)
    n = min(len(ao), len(ad))
    sr = C.SR_VERIF
    restantes, medidos = [], 0
    for s in segmentos:
        i, j = int(float(s["start_s"]) * sr), int(min(float(s["end_s"]) * sr, n))
        if j - i < sr // 3:                       # menos de 0,33 s no se puede medir
            continue
        medidos += 1
        p = _parecido(ao[i:j], ad[i:j])
        if p > umbral:
            restantes.append(dict(inicio=round(float(s["start_s"]), 1), fin=round(float(s["end_s"]), 1),
                                  parecido=round(p, 3), texto=(s.get("text") or "")[:80]))
    return dict(segmentos=len(segmentos), medidos=medidos, umbral=umbral, restantes=restantes)


def nivel_voz(original: Path, doblado: Path, segmentos: list[dict]) -> float | None:
    """Cuántos dB está la VOZ doblada por encima (+) o por debajo (-) de la voz original: RMS en la
    banda de voz (300-3400 Hz) sobre cada segmento declarado, mediana. Es el número que responde
    "¿se nota diferencia de nivel?": hasta ±2 dB no se oye, más de 3 dB sí. None sin numpy."""
    if np is None:
        return None
    ao, ad = _cargar(original), _cargar(doblado)
    n = min(len(ao), len(ad)); sr = C.SR_VERIF
    def db(x): return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
    v = []
    for s in segmentos:
        i, j = int(float(s["start_s"]) * sr), int(min(float(s["end_s"]) * sr, n))
        if j - i >= sr // 3:
            v.append(db(_banda(ad[i:j])) - db(_banda(ao[i:j])))
    return round(float(np.median(v)), 1) if v else None


def nivel_fondo(original: Path, doblado: Path, segmentos: list[dict]) -> float | None:
    """Cuántos dB está el FONDO (música y ambiente) del doblado respecto del original, medido en huecos
    sin habla de 0,25 s con 150 ms de margen alrededor de cada segmento. v2 conserva el fondo (≈ −0,5 dB)
    pero sube la voz; al igualar la sonoridad de la mezcla entera el fondo cae ~4 dB: este número lo delata.
    None sin numpy o sin huecos."""
    if np is None:
        return None
    ao, ad = _cargar(original), _cargar(doblado)
    n = min(len(ao), len(ad)); sr = C.SR_VERIF; m = int(0.15 * sr); w = int(0.25 * sr)
    ocupado = np.zeros(n, dtype=bool)
    for s in segmentos:
        i, j = int(float(s["start_s"]) * sr) - m, int(min(float(s["end_s"]) * sr, n)) + m
        ocupado[max(0, i):min(n, j)] = True
    def db(x): return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
    f = [db(ad[i:i + w]) - db(ao[i:i + w]) for i in range(0, n - w, w)
         if not ocupado[i:i + w].any() and db(ao[i:i + w]) > -55]
    return round(float(np.median(f)), 1) if len(f) >= 4 else None


def filtracion_voz(voz_original: Path, doblado: Path, segmentos: list[dict], umbral_db: float = -14.0) -> dict | None:
    """Cuánto de la voz ORIGINAL se oye POR DEBAJO de la voz doblada, por segmento (el segundo modo de
    fallo de v2: "se escucha el inglés detrás"). El detector de parecido no lo ve porque la voz nueva,
    más fuerte, domina. Acá se estima la ganancia del original dentro del doblado por mínimos cuadrados
    con búsqueda de desfasaje (±25 ms), en banda de voz. Referencia ideal: la pista de voz original
    separada; con la mezcla original también sirve, algo sesgado por el fondo común.
    Escala medida 13-sep: > −14 dB se oye claramente detrás · −14…−20 se intuye · < −20 limpio.
    Devuelve dict(mediana, p90, filtradas=[{inicio, fin, db, texto}]) o None sin numpy."""
    if np is None:
        return None
    o, d = _cargar(voz_original), _cargar(doblado)
    n = min(len(o), len(d)); sr = C.SR_VERIF; maxlag = int(0.025 * sr)
    valores, filtradas = [], []
    for s in segmentos:
        i, j = int(float(s["start_s"]) * sr), int(min(float(s["end_s"]) * sr, n))
        if j - i < sr // 3:
            continue
        ob = _banda(o[i:j] - o[i:j].mean()); db_ = _banda(d[i:j] - d[i:j].mean())
        if np.dot(ob, ob) < 1e-9:
            continue
        mejor = 0.0
        for lag in range(-maxlag, maxlag + 1, 4):
            oo, dd = (ob[:len(ob) - lag], db_[lag:]) if lag >= 0 else (ob[-lag:], db_[:len(db_) + lag])
            g = float(np.dot(dd, oo) / np.dot(oo, oo))
            if abs(g) > abs(mejor):
                mejor = g
        v = 20 * np.log10(abs(mejor) + 1e-9); valores.append(v)
        if v > umbral_db:
            filtradas.append(dict(inicio=round(float(s["start_s"]), 1), fin=round(float(s["end_s"]), 1),
                                  db=round(float(v), 1), texto=(s.get("text") or "")[:80]))
    if not valores:
        return None
    return dict(mediana=round(float(np.median(valores)), 1), p90=round(float(np.percentile(valores, 90)), 1),
                umbral_db=umbral_db, filtradas=filtradas)
