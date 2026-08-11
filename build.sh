#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# Genera static/config.js a partir de las variables de entorno de Render.
#
# POR QUÉ EXISTE ESTE PASO
# La página es estática: no hay servidor que lea variables de entorno cuando
# alguien la visita. Así que se leen UNA vez, durante el build, y se hornean en
# un archivo que el navegador después descarga.
#
# QUÉ NO HACE ESTO
# No las vuelve secretas. El navegador necesita esos valores para hablar con
# Google, así que quedan a la vista de cualquiera que mire el código de la
# página — no hay forma de evitarlo en un sitio sin backend. Lo que se gana es
# que dejan de vivir en un repositorio público. Lo que de verdad las protege es
# restringirlas por origen y por referente en la consola de Google.
# ══════════════════════════════════════════════════════════════════════════════
set -e

OUT="static/config.js"

# Sólo se dejan pasar los caracteres que estas credenciales realmente usan.
# Sin esto, una comilla pegada de más en el panel de Render rompería el archivo
# entero y la página quedaría muda, sin explicar por qué.
limpiar() {
  printf '%s' "$1" | tr -cd 'A-Za-z0-9._~:@/-'
}

CLIENT_ID=$(limpiar "${GOOGLE_CLIENT_ID:-}")
API_KEY=$(limpiar "${GOOGLE_API_KEY:-}")
PROJECT_NUMBER=$(limpiar "${GOOGLE_PROJECT_NUMBER:-}")

cat > "$OUT" <<EOF
/* GENERADO EN EL BUILD por build.sh — no editar a mano.
   Los valores salen de las variables de entorno del servicio en Render.
   Para tocarlos: panel de Render -> dubai-demo -> Environment. */
window.DUBAI_CONFIG = {
  GOOGLE_CLIENT_ID: "$CLIENT_ID",
  GOOGLE_API_KEY: "$API_KEY",
  GOOGLE_PROJECT_NUMBER: "$PROJECT_NUMBER",
};
EOF

# Se informa si cada variable llegó o no, nunca su valor: los logs de build
# quedan guardados y son legibles para cualquiera con acceso al panel.
estado() {
  if [ -n "$2" ]; then printf '  %-22s cargada (%s caracteres)\n' "$1" "${#2}"
  else                 printf '  %-22s VACIA\n' "$1"; fi
}

echo "config.js generado:"
estado GOOGLE_CLIENT_ID      "$CLIENT_ID"
estado GOOGLE_API_KEY        "$API_KEY"
estado GOOGLE_PROJECT_NUMBER "$PROJECT_NUMBER"

if [ -z "$CLIENT_ID" ] || [ -z "$API_KEY" ]; then
  echo ""
  echo "AVISO: faltan credenciales. El sitio se publica igual y funciona, pero el"
  echo "boton de Drive va a aparecer apagado. Cargalas en Environment y redeploy."
fi
