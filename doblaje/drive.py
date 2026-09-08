# -*- coding: utf-8 -*-
"""
Google Drive con las credenciales OAuth del usuario: navegar, bajar el video, crear
`doblaje/` al lado y subir el resultado. Mismo contrato que usa el resto de la
plataforma; escrito acá porque una app no importa de otra.
"""
from __future__ import annotations

from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials

CHUNK = 32 * 1024 * 1024
CARPETA = "application/vnd.google-apps.folder"


def cliente(creds: Credentials):
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def meta(d, file_id: str) -> dict:
    return d.files().get(fileId=file_id, fields="id,name,parents,size,mimeType,videoMediaMetadata(durationMillis)",
                         supportsAllDrives=True).execute()


def listar(d, carpeta_id: str = "root") -> dict:
    """Subcarpetas, videos y migas de una carpeta. `compartidos` = 'Compartido conmigo'."""
    campos = ("nextPageToken, files(id, name, mimeType, size, thumbnailLink, parents, "
              "videoMediaMetadata(durationMillis), modifiedTime)")
    q = ("sharedWithMe = true and trashed = false" if carpeta_id == "compartidos"
         else f"'{carpeta_id}' in parents and trashed = false")
    items, page = [], None
    while True:
        r = d.files().list(q=q, fields=campos, pageSize=200, pageToken=page, orderBy="folder,name",
                           supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        items += r.get("files", [])
        page = r.get("nextPageToken")
        if not page:
            break
    carpetas = [dict(id=f["id"], nombre=f["name"]) for f in items if f["mimeType"] == CARPETA]
    videos = []
    for f in items:
        if f["mimeType"].startswith("video/"):
            vm = f.get("videoMediaMetadata") or {}
            videos.append(dict(id=f["id"], nombre=f["name"], tamano=int(f.get("size", 0) or 0),
                               duracion_s=int(vm.get("durationMillis", 0) or 0) / 1000,
                               miniatura=f.get("thumbnailLink"), padre=(f.get("parents") or [None])[0]))
    migas = []
    if carpeta_id == "compartidos":
        migas = [dict(id="compartidos", nombre="Compartido conmigo")]
    else:
        cur = carpeta_id
        while cur and cur != "root" and len(migas) < 12:
            m = d.files().get(fileId=cur, fields="id,name,parents", supportsAllDrives=True).execute()
            migas.insert(0, dict(id=m["id"], nombre=m["name"]))
            cur = (m.get("parents") or [None])[0]
        migas.insert(0, dict(id="root", nombre="Mi unidad"))
    return dict(id=carpeta_id, migas=migas, carpetas=carpetas, videos=videos)


def bajar(d, file_id: str, dst: Path, progreso=None) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = d.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(dst, "wb") as f:
        dl = MediaIoBaseDownload(f, req, chunksize=CHUNK)
        done = False
        while not done:
            st, done = dl.next_chunk()
            if st and progreso:
                progreso(st.progress())
    return dst


def carpeta_salida(d, padre: str, nombre: str) -> str:
    """La carpeta `nombre/` dentro del padre; la crea si no está."""
    q = f"'{padre}' in parents and name = '{nombre}' and mimeType = '{CARPETA}' and trashed = false"
    r = d.files().list(q=q, fields="files(id)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    if r.get("files"):
        return r["files"][0]["id"]
    body = {"name": nombre, "mimeType": CARPETA, "parents": [padre]}
    return d.files().create(body=body, fields="id", supportsAllDrives=True).execute()["id"]


def subir(d, ruta: Path, carpeta_id: str) -> str:
    """Sube (o reemplaza si ya existe con ese nombre). Devuelve el id."""
    mime = {".mp4": "video/mp4", ".wav": "audio/wav", ".json": "application/json"}.get(
        ruta.suffix.lower(), "application/octet-stream")
    nombre_q = ruta.name.replace("\\", "\\\\").replace("'", "\'")
    q = f"'{carpeta_id}' in parents and name = '{nombre_q}' and trashed = false"
    r = d.files().list(q=q, fields="files(id)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    media = MediaFileUpload(str(ruta), mimetype=mime, resumable=True, chunksize=CHUNK)
    if r.get("files"):
        req = d.files().update(fileId=r["files"][0]["id"], media_body=media, supportsAllDrives=True, fields="id")
    else:
        req = d.files().create(body={"name": ruta.name, "parents": [carpeta_id]}, media_body=media,
                               supportsAllDrives=True, fields="id")
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


def buscar(d, texto: str, maximo: int = 40) -> dict:
    """Carpetas y videos cuyo nombre contiene `texto`, en TODO lo que el usuario ve
    (su unidad y lo compartido). Trae el nombre de la carpeta madre de cada resultado
    para distinguir homónimos; una llamada extra por carpeta madre distinta."""
    t = texto.replace("\\", "\\\\").replace("'", "\'")
    q = (f"name contains '{t}' and trashed = false and "
         f"(mimeType = '{CARPETA}' or mimeType contains 'video/')")
    campos = "files(id, name, mimeType, size, thumbnailLink, parents, videoMediaMetadata(durationMillis))"
    r = d.files().list(q=q, fields=campos, pageSize=maximo, orderBy="folder,name",
                       supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    items = r.get("files", [])
    nombres = {}
    for f in items:
        p = (f.get("parents") or [None])[0]
        if p and p not in nombres:
            try:
                nombres[p] = d.files().get(fileId=p, fields="name", supportsAllDrives=True).execute()["name"]
            except Exception:
                nombres[p] = ""

    def madre(f):
        p = (f.get("parents") or [None])[0]
        return dict(id=p, nombre=nombres.get(p, "")) if p else None

    carpetas = [dict(id=f["id"], nombre=f["name"], madre=madre(f)) for f in items if f["mimeType"] == CARPETA]
    videos = []
    for f in items:
        if f["mimeType"].startswith("video/"):
            vm = f.get("videoMediaMetadata") or {}
            videos.append(dict(id=f["id"], nombre=f["name"], tamano=int(f.get("size", 0) or 0),
                               duracion_s=int(vm.get("durationMillis", 0) or 0) / 1000,
                               miniatura=f.get("thumbnailLink"), padre=(f.get("parents") or [None])[0],
                               madre=madre(f)))
    return dict(texto=texto, carpetas=carpetas, videos=videos, truncado=len(items) >= maximo)
