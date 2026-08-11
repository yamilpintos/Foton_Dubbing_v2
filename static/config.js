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
  // Consola de Google → Credenciales → ID de cliente de OAuth 2.0 → Aplicación web
  GOOGLE_CLIENT_ID: "",

  // Consola de Google → Credenciales → Clave de API (restringila por referente)
  GOOGLE_API_KEY: "",

  // Opcional: el NÚMERO del proyecto (no el ID). Ayuda al Picker con unidades
  // compartidas. Consola de Google → Configuración del proyecto → Número de proyecto.
  GOOGLE_PROJECT_NUMBER: "",
};
