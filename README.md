# Doblaje

Doblás videos de tu Google Drive a otro idioma. Conectás Drive, navegás carpeta por
carpeta, elegís uno o varios videos, el motor, el idioma y la fuerza de clonado, ves el
costo en créditos ANTES de confirmar, y el resultado se sube a una carpeta `doblaje/`
dentro de la carpeta donde estaba cada video.

Dos motores:

| Motor | Estado | Qué hace |
|---|---|---|
| **ElevenLabs Dubbing v2** | anda | Transcribe, traduce y sintetiza con la voz clonada del actor. Salida: sólo audio; esta app lo pega sobre el video original. |
| **Motor propio** | todavía no está subido | La cadena propia (ASR → traducción → clones con casting). Aparece en la web, deshabilitado, hasta que se suba. |

## Lo que aprendimos a los golpes (y esta app ya trae puesto)

- **`cloning_strength` es la perilla que importa.** Va de 0 a 10; el valor por defecto de
  ElevenLabs es 7 y con ése el modelo **copia el audio original** en los segmentos
  difíciles (susurros, rezos, gritos): quedan en el idioma de origen. Con 1, once videos
  salieron limpios. La SDK de Python **no expone** el parámetro; acá se manda por HTTP.
- **Regenerar es gratis pero acá no hace falta**: el cobro es una sola vez, por segundo de
  fuente, al crear el idioma. Medido: 13.245 créditos/min en la cuenta paga.
- **Cada video se verifica solo**, comparando el audio doblado contra el original,
  segmento por segmento (pasa-banda de voz + correlación con desfasaje). Si queda algo en
  el idioma de origen, el trabajo termina en **REVISAR** con los timecodes.
- **Los archivos grandes se comprimen antes de subir** (1,8 GB → 84 MB, mismo cobro), y el
  audio final se pega sobre el original en calidad plena.

## Correr sola

```
pip install -r requirements.txt
cp .env.example .env        # completar GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / ELEVENLABS_API_KEY
python -m doblaje.web       # → http://localhost:8790
```

Este repo es la app sola. Dentro de la plataforma de herramientas vive en `apps/doblaje/` y el portal la monta en `/doblaje/`.

## Qué necesita

- **Google OAuth** (una vez): Google Cloud → habilitar Drive API → pantalla de
  consentimiento (externo, tu mail como usuario de prueba) → ID de cliente OAuth,
  aplicación web, URI de redirección `http://localhost:8790/auth/callback`.
- **`ELEVENLABS_API_KEY`**. Si no está en `.env`, se toma de `dubai_v2/.env`. Una segunda
  cuenta opcional en `ELEVENLABS_API_KEY_ALT` (aparece un selector).
- **ffmpeg** (`FFMPEG` en `.env`, o `dubai_v2/_bin/ffmpeg.exe`, o `~/ffmpeg/*/bin`, o el PATH, o el que instala `imageio-ffmpeg`).
- **numpy**, sólo para la verificación acústica; sin numpy la app dobla igual y avisa
  que no verificó.

El procesamiento corre en la máquina que sirve la web (baja de Drive, sube a ElevenLabs,
pega el audio, verifica, sube a Drive). No hay GPU de por medio: el trabajo pesado lo
hace ElevenLabs.

## Desplegar en Render

`render.yaml` define un **servicio web Python** llamado `doblaje`. El servicio anterior de este
repo (`dubai-demo`) era un sitio estático y no puede correr esto: hay que borrarlo desde el
panel y dejar que el Blueprint cree el nuevo.

1. Render → New → Blueprint → este repo (o, si el Blueprint ya está conectado, sincronizar).
2. En el servicio `doblaje` → Environment: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `ELEVENLABS_API_KEY` (y `ELEVENLABS_API_KEY_ALT` si hay segunda cuenta).
3. En Google Cloud, agregar la URI de redirección `https://<nombre>.onrender.com/auth/callback`.

ffmpeg no viene en Render: `imageio-ffmpeg` (en `requirements.txt`) instala el binario por pip y
la app lo encuentra sola. Ojo con la memoria del plan Starter (512 MB): la verificación acústica
carga el audio entero; con videos de más de ~15 min conviene subir de plan o desactivar numpy.

## Guardas de gasto

- Estimación a la vista antes de confirmar, contra el saldo real de la cuenta.
- No arranca si el saldo no alcanza para lo que se pidió.
- Tope de trabajos simultáneos (ElevenLabs admite 3 por cuenta) y por día.
- No manda dos veces el mismo video mientras uno está en curso.
- Un video de más de 180 min no entra (límite de ElevenLabs).
