# DubAI — maqueta de demostración

Página de una sola pantalla para **mostrar** cómo se siente usar DubAI: soltás una
película, se ve el motor trabajando etapa por etapa, y al final aparece el resultado.

> **Esto es una maqueta, no el producto.** El video que soltás no se sube a ningún lado
> ni se procesa: se lee en el navegador para sacarle duración, resolución y un cuadro de
> muestra. Las etapas que corren en pantalla son una recreación cronometrada del proceso
> real —los nombres técnicos son los del motor de producción— y el video final es una
> muestra ya renderizada que viaja con la página.
>
> La app de verdad está en [`../dubai_web`](../dubai_web).

---

## Verla en tu máquina

No hay build ni dependencias. Con cualquier servidor estático alcanza:

```bash
python -m http.server 8080
# http://localhost:8080
```

> Abrir `index.html` con doble clic (`file://`) también funciona, pero algunos navegadores
> se ponen quisquillosos con el video local. Con el servidor va siempre.

## Subirla a Render

1. Subí esta carpeta a un repositorio de GitHub.
2. En Render: **New → Static Site**, elegí el repo.
3. **Build Command:** vacío · **Publish Directory:** `.`

El `render.yaml` ya deja eso configurado si preferís usarlo como *Blueprint*
(**New → Blueprint**). Incluye caché largo para `media/`, que es lo pesado.

El plan gratuito de sitios estáticos alcanza de sobra: son ~60 MB y no hay servidor.

---

## El video de muestra

`media/resultado.mp4` es la ventana **1:26 → 6:26 de Goazen S3E7**, doblada del euskera al
español con el motor de producción (la versión `5_TRADUCCION_AJUSTADA` del 11-ago).

El original mide 252 MB a 1080p. Acá va recomprimido a **720p, 60 MB**, porque GitHub
rechaza archivos de más de 100 MB. El audio se dejó alto a propósito (**AAC 160 kb/s**):
en una demo de doblaje, el audio *es* el producto.

Para regenerarlo desde otro render:

```bash
ffmpeg -i ENTRADA.mp4 -vf scale=-2:720 -c:v libx264 -preset slow -crf 26 \
       -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 160k -ar 48000 \
       media/resultado.mp4

ffmpeg -ss 00:00:42 -i media/resultado.mp4 -frames:v 1 -vf scale=1280:-2 -q:v 4 \
       media/poster.jpg
```

Si cambiás el video, actualizá también el epígrafe del panel de resultado en
`index.html` (la línea que dice de qué película es) y las cifras fijas de `.stats`.

---

## Tocar la demo

Todo vive en tres archivos, sin frameworks:

| archivo | qué tiene |
|---|---|
| `index.html` | la estructura y los textos |
| `static/style.css` | el diseño entero |
| `static/app.js` | la lectura del archivo y la recreación por etapas |

Las perillas que vas a querer mover, todas en `static/app.js`:

- **`TOTAL_MS`** (arriba de todo) — cuánto dura la recreación. Por defecto 26 s.
  Para una demo en vivo frente a alguien, 15-18 s se banca mejor.
- **`buildStages()`** — las 14 etapas, su nombre, su peso en el tiempo total y las
  líneas que escupen en la consola.
- **`makeCtx()`** — de dónde salen los números plausibles (tomas, hablantes, palabras).
  Se derivan de la duración real del archivo que soltaste, así que si soltás una
  película de 90 minutos los números crecen solos.

Los avisos de que es una maqueta están en dos lugares y son una línea cada uno:
el bloque `.note` de `index.html` y el `<span class="tag-sample">` del resultado.
Si la vas a mostrar como concepto de producto, dejalos.
