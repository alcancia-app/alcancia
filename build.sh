#!/bin/bash
# Compila Alcancía y la instala en ~/Applications/Alcancia.app (para desarrollo en este Mac).
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH
RAIZ="$(cd "$(dirname "$0")" && pwd)"
# Cerrar la app en medio de una importación la cortaría.
if pgrep -f "bin/importar.py guardar" >/dev/null && [ "${FORZAR:-0}" != "1" ]; then
  echo "✗ Alcancía está importando una cartola. Espera a que termine (o usa FORZAR=1)." >&2; exit 3
fi
bash "$RAIZ/herramientas/empaquetar.sh"
APP="$HOME/Applications/Alcancia.app"
mkdir -p "$HOME/Applications"
osascript -e 'tell application id "app.alcancia.mac" to quit' 2>/dev/null || true
sleep 1
rm -rf "$APP"
ditto "$RAIZ/dist/Alcancia.app" "$APP"
# La app sabe que viene de este checkout: se actualiza con git pull (Ajustes → Buscar actualizaciones).
mkdir -p "$HOME/Alcancia/.alcancia" && echo "$RAIZ" > "$HOME/Alcancia/.alcancia/desarrollo"
echo "Instalada en $APP ($(du -sh "$APP" | cut -f1))"
