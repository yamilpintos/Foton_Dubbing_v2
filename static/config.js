/* ══════════════════════════════════════════════════════════════════════════════
   Credenciales de Google para el buscador de Drive.

   Las dos son PÚBLICAS por diseño: viajan al navegador de cualquiera que abra la
   página, así que no son secretos y pueden vivir en un repo público. Lo que las
   protege NO es esconderlas, es restringirlas en la consola de Google:

     · el ID de cliente sólo funciona desde los orígenes que autorices
     · la clave de API hay que limitarla por "referente HTTP" a tu dominio

   Si dejás la clave de API sin restringir, cualquiera puede usar tu cuota.
   El paso a paso está en el README.

   Mientras estén vacías, el botón de Drive se muestra apagado y explica qué falta.
   Subir el archivo por arrastre sigue funcionando igual.
   ══════════════════════════════════════════════════════════════════════════════ */
window.DUBAI_CONFIG = {
  // Proyecto "DubAI" (composed-arbor-503012-j4) — el mismo cliente que usa dubai_web.
  // Para que sirva ACÁ hay que agregarle los "Orígenes de JavaScript autorizados"
  // (localhost:8080 y la URL de Render). Sin eso Google rechaza el permiso.
  GOOGLE_CLIENT_ID: "258756225705-1clagl9d3f1fd8b9t3kub7rclpgs9bou.apps.googleusercontent.com",

  // FALTA CREAR. Consola de Google → Credenciales → Crear credenciales → Clave de API.
  // Restringila por referente HTTP a tus dominios y limitala a Google Picker API.
  // Hasta que esté, el botón de Drive queda apagado.
  GOOGLE_API_KEY: "",

  // El número del proyecto. Es el prefijo del ID de cliente de arriba.
  GOOGLE_PROJECT_NUMBER: "258756225705",
};

/* OJO: el GOOGLE_CLIENT_SECRET que está en dubai_web/.env NO va acá y NO debe
   subirse nunca a este repo, que es público. Ese secreto es para el flujo de
   servidor de dubai_web. Este flujo corre entero en el navegador y no lo usa:
   si un secreto viaja al navegador, deja de ser secreto. */
