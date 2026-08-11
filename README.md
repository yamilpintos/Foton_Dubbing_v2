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
3. **Build Command:** `sh ./build.sh` · **Publish Directory:** `.`
4. **Environment:** cargá las tres variables de Google (ver más abajo). Sin ellas el
   sitio se publica igual, pero el botón de Drive queda apagado.

El `render.yaml` ya deja eso configurado si preferís usarlo como *Blueprint*
(**New → Blueprint**). Incluye caché largo para `media/`, que es lo pesado.

El plan gratuito de sitios estáticos alcanza de sobra: son ~60 MB y no hay servidor.

---

## Conectar tu Google Drive

El botón **"Elegir desde mi Google Drive"** abre el buscador de Google sobre **todo** tu
Drive —incluidas las unidades compartidas— y trae el archivo que elijas. No descarga el
video: lee nombre, tamaño, duración, resolución y la miniatura, que es todo lo que la
demo necesita.

Hasta que cargues las credenciales, el botón se muestra apagado y lo dice. Arrastrar un
archivo desde tu disco funciona igual, sin configurar nada.

### El permiso que pide, y por qué es el acotado

Pide `drive.file`, no el acceso completo. La app **sólo ve los archivos que elegís a
mano**; el resto de tu Drive le queda invisible. Podés igual buscar en todo el Drive
porque quien busca es el Picker de Google, que corre dentro de tu sesión y no de esta
página.

Eso no es una limitación, es lo que hace que esto sea usable: el permiso completo
(`drive.readonly`) está clasificado como **restringido** por Google y obliga a verificar
la app —trámite de semanas, y mientras tanto sólo entran las cuentas cargadas a mano como
usuarios de prueba—. Es exactamente el muro contra el que choca `dubai_web`, que sí
necesita el Drive entero porque tiene que *escribir* el resultado. Acá no hace falta.

### Puesta a punto (una vez)

1. [Google Cloud Console](https://console.cloud.google.com/) → elegí un proyecto (podés
   reusar el de `dubai_web`) o creá uno.
2. **APIs y servicios → Biblioteca** → habilitá **Google Drive API** y **Google Picker API**.
3. **Credenciales → Crear credenciales → ID de cliente de OAuth 2.0 → Aplicación web.**
   En *Orígenes de JavaScript autorizados* agregá —sin barra final:
   - `http://localhost:8080`
   - `https://TU-SITIO.onrender.com`

   > Van en **orígenes**, no en *URIs de redireccionamiento*: este flujo devuelve el
   > permiso a la misma página, no a una URL de vuelta. Dejar el campo de redirección
   > vacío está bien.
4. **Credenciales → Crear credenciales → Clave de API.** Editala y en *Restricciones de
   la aplicación* elegí **Referentes HTTP**, con los mismos dos dominios. En
   *Restricciones de API*, limitala a **Google Picker API**.
5. **Pantalla de consentimiento de OAuth:** tipo *Externo*. Con `drive.file` no hace falta
   verificación, pero mientras la app esté en modo **Prueba** sólo entran las cuentas que
   cargues como usuarios de prueba. Para abrirla a cualquiera, publicala.
6. Cargá las credenciales en Render: panel → **dubai-demo → Environment**, con estos
   nombres exactos:

   | variable | de dónde sale |
   |---|---|
   | `GOOGLE_CLIENT_ID` | el ID de cliente del paso 3 |
   | `GOOGLE_API_KEY` | la clave del paso 4 |
   | `GOOGLE_PROJECT_NUMBER` | el prefijo numérico del ID de cliente |

   No van al repositorio. [`build.sh`](build.sh) las lee durante el build y genera
   `static/config.js`; el log del deploy dice cuáles llegaron y cuáles no, sin imprimir
   sus valores.

   > **Para probar en tu máquina** completá [`static/config.js`](static/config.js) a mano
   > y no lo commitees. Para volver atrás: `git checkout static/config.js`.

### Que estén en "environment" no las vuelve secretas

El navegador necesita esos dos valores para hablar con Google, así que terminan a la
vista de cualquiera que mire el código de la página. En un sitio sin backend no hay forma
de evitarlo, y no hace falta: **ninguna de las dos es un secreto**. Lo que se gana con las
variables de entorno es que dejan de vivir en un repositorio público y que cambiarlas no
exige un commit.

Lo que de verdad las protege es el paso 4: la restricción por origen y por referente. Sin
eso, cualquiera puede gastar tu cuota desde otro dominio. El ID de cliente no sirve fuera
de los orígenes que autorizaste.

El que **sí** es un secreto es el `GOOGLE_CLIENT_SECRET` de `dubai_web`, y por eso no
aparece en ningún lado de este proyecto: este flujo corre entero en el navegador y no lo
usa.

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
| `static/drive.js` | el permiso de Google y el buscador sobre tu Drive |
| `static/config.js` | las dos credenciales de Google, y nada más |

Las perillas que vas a querer mover, todas en `static/app.js`:

- **`TOTAL_MS`** (arriba de todo) — cuánto dura la recreación. Por defecto 26 s.
  Para una demo en vivo frente a alguien, 15-18 s se banca mejor.
- **`buildStages()`** — las 14 etapas, su nombre, su peso en el tiempo total y las
  líneas que escupen en la consola.
- **`makeCtx()`** — de dónde salen los números plausibles (tomas, hablantes, palabras).
  Se derivan de la duración real del archivo que soltaste, así que si soltás una
  película de 90 minutos los números crecen solos.

Queda un solo aviso de que el resultado es una muestra: el
`<span class="tag-sample">` del panel final, junto al epígrafe que dice de qué película
es. Es una línea de `index.html` si lo querés sacar.
