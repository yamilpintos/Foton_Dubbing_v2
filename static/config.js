/* ══════════════════════════════════════════════════════════════════════════════
   Credenciales de Google para el buscador de Drive.

   EN RENDER ESTE ARCHIVO SE PISA. Lo genera `build.sh` durante el build, con las
   variables de entorno del servicio (panel -> dubai-demo -> Environment). Por eso
   acá va vacío: las credenciales no viven en el repositorio.

   PARA PROBAR EN TU MÁQUINA podés completarlo a mano — pero no lo commitees así.
   Para volver atrás:  git checkout static/config.js

   QUE ESTÉN EN "ENVIRONMENT" NO LAS VUELVE SECRETAS. El navegador necesita estos
   valores para hablar con Google, así que terminan a la vista de cualquiera que
   mire el código de la página; en un sitio sin backend no hay forma de evitarlo.
   Lo que de verdad las protege es restringirlas en la consola de Google:

     · el ID de cliente sólo funciona desde los orígenes que autorices
     · la clave de API hay que limitarla por "referente HTTP" a tu dominio

   El paso a paso está en el README.

   Mientras estén vacías, el botón de Drive se muestra apagado y explica qué falta.
   Arrastrar un archivo desde tu disco funciona igual, sin configurar nada.
   ══════════════════════════════════════════════════════════════════════════════ */
window.DUBAI_CONFIG = {
  GOOGLE_CLIENT_ID: "",
  GOOGLE_API_KEY: "",
  GOOGLE_PROJECT_NUMBER: "",
};

/* OJO: el GOOGLE_CLIENT_SECRET que está en dubai_web/.env NO va acá y NO debe
   subirse nunca a este repo, que es público. Ese secreto es para el flujo de
   servidor de dubai_web. Este flujo corre entero en el navegador y no lo usa:
   si un secreto viaja al navegador, deja de ser secreto. */
