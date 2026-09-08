# -*- coding: utf-8 -*-
"""
ElevenLabs Dubbing v2 por HTTP directo (API de proyectos).

Por qué no la SDK: `cloning_strength` va dentro de `voice_settings` al crear el idioma y la
SDK de Python (2.65) no lo expone en su tipo `VoiceSettings`, así que lo tira. Y es la
perilla que decide si el doblaje sale limpio o con el original adentro (ver README).

Flujo:  crear_proyecto → esperar_proyecto → crear_idioma(cloning_strength) → esperar_idioma
        → bajar_audio(outputs.lossless_audio)   (+ transcripto / traduccion para verificar)
El cobro es UNA vez, por segundo de fuente, cuando el idioma termina. La URL del audio
firmada vence a la hora: bajar enseguida.
"""
from __future__ import annotations

import time
from pathlib import Path

import requests

from . import config as C


class DubbingError(RuntimeError):
    pass


class Cuenta:
    def __init__(self, api_key: str, etiqueta: str = ""):
        if not api_key:
            raise DubbingError("falta la clave de ElevenLabs")
        self.key = api_key
        self.etiqueta = etiqueta
        self.h = {"xi-api-key": api_key}

    # ------------------------------------------------------------ http
    def _req(self, metodo: str, ruta: str, reintentos: int = 6, **kw) -> dict:
        """El endpoint de saldo tira 429 si se lo consulta seguido: se reintenta con espera creciente."""
        ultimo = None
        for i in range(reintentos):
            try:
                r = requests.request(metodo, C.API + ruta, headers=self.h, timeout=kw.pop("timeout", 120), **kw)
            except requests.RequestException as e:
                ultimo = e
                time.sleep(8 * (i + 1))
                continue
            if r.status_code == 429:
                ultimo = DubbingError("429 rate limit")
                time.sleep(12 * (i + 1))
                continue
            if r.status_code >= 400:
                try:
                    det = r.json().get("detail")
                except Exception:
                    det = r.text[:300]
                raise DubbingError(f"HTTP {r.status_code}: {det}")
            return r.json() if r.content else {}
        raise DubbingError(f"sin respuesta tras {reintentos} intentos: {ultimo}")

    # ------------------------------------------------------------ cuenta
    def saldo(self) -> dict:
        s = self._req("GET", "/v1/user/subscription")
        return dict(libres=s["character_limit"] - s["character_count"], limite=s["character_limit"],
                    usados=s["character_count"], plan=s.get("tier"),
                    renueva_unix=s.get("next_character_count_reset_unix"))

    # ------------------------------------------------------------ proyecto
    def crear_proyecto(self, archivo: Path, origen: str | None, referencia: str, keyterms: list[str]) -> str:
        datos = [("model_id", C.MODELO), ("reference", referencia[:500])]
        if origen and origen != "auto":
            datos.append(("source_language", origen))
        datos += [("keyterms", k) for k in keyterms if k.strip()]        # campo repetido, como pide la API
        mime = "video/mp4" if archivo.suffix.lower() in (".mp4", ".m4v", ".mov") else "application/octet-stream"
        with open(archivo, "rb") as fh:
            r = self._req("POST", "/v1/dubbing/project", reintentos=2, timeout=3600,
                          files=[("file", (archivo.name, fh, mime))], data=datos)
        return r["project_id"]

    def proyecto(self, pid: str) -> dict:
        return self._req("GET", f"/v1/dubbing/project/{pid}")

    def esperar_proyecto(self, pid: str, cancelado=lambda: False, paso: float = 5.0) -> dict:
        while True:
            p = self.proyecto(pid)
            if p.get("status") in ("ready", "failed"):
                return p
            if cancelado():
                raise DubbingError("cancelado")
            time.sleep(paso)

    # ------------------------------------------------------------ idioma
    def crear_idioma(self, pid: str, destino: str, clonacion: int) -> str:
        cuerpo = {"target_language": destino, "voice_settings": {"cloning_strength": int(clonacion)}}
        r = self._req("POST", f"/v1/dubbing/project/{pid}/language", json=cuerpo)
        return r["language_id"]

    def idioma(self, pid: str, lid: str) -> dict:
        return self._req("GET", f"/v1/dubbing/project/{pid}/language/{lid}")

    def esperar_idioma(self, pid: str, lid: str, cancelado=lambda: False, paso: float = 8.0) -> dict:
        while True:
            L = self.idioma(pid, lid)
            if L.get("status") in ("completed", "failed"):
                return L
            if cancelado():
                raise DubbingError("cancelado")
            time.sleep(paso)

    # ------------------------------------------------------------ resultados
    def transcripto(self, pid: str) -> list[dict]:
        return self._req("GET", f"/v1/dubbing/project/{pid}/transcript").get("segments", [])

    def traduccion(self, pid: str, lid: str) -> list[dict]:
        return self._req("GET", f"/v1/dubbing/project/{pid}/language/{lid}/transcript").get("segments", [])

    @staticmethod
    def bajar_audio(url: str, dst: Path) -> Path:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=3600) as r:
            r.raise_for_status()
            with open(dst, "wb") as f:
                for trozo in r.iter_content(1 << 20):
                    f.write(trozo)
        return dst


def estimar_creditos(segundos: float) -> int:
    return int(round(segundos / 60.0 * C.CR_POR_MIN))
