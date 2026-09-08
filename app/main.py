# -*- coding: utf-8 -*-
"""
Render, cuando el servicio se crea a mano, arranca con `uvicorn app.main:app`. Este módulo
expone la misma app de doblaje bajo ese nombre, así el repo arranca con el comando por
defecto y también con el de render.yaml (`uvicorn doblaje.web:app`). No hay lógica acá.
"""
from doblaje.web import app  # noqa: F401
