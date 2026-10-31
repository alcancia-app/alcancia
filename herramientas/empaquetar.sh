#!/bin/bash
# Arma dist/Alcancia.app (autosuficiente) y dist/Alcancia-macOS.zip + .sha256, sin instalar nada.
# Lo usan build.sh (en tu Mac) y, cuando exista, la acción de GitHub que publica cada versión.
# Dentro van: la app, Python portátil y el código (bin/, ui/, recetas/) en Contents/Resources/alcancia.
# Los datos de la persona quedan en ~/Alcancia.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$PATH
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ/app"
swift build -c release 2>&1 | tee "${ALCANCIA_PROGRESO:-/dev/null}" | tail -20
REL=.build/release

# Python portátil (python-build-standalone): se descarga una vez y se verifica su huella. La persona no instala nada.
PY_URL="https://github.com/astral-sh/python-build-standalone/releases/download/20261003/cpython-3.13.16%2B20261003-aarch64-apple-darwin-install_only_stripped.tar.gz"
PY_SHA="9e01f63bbb08576cd9c8bc2d0564d098cb30c8453a0cd4bcf6aef458f6d2a147"
PY_TGZ=.build/python-3.13.16.tar.gz
if [ ! -f "$PY_TGZ" ] || [ "$(shasum -a 256 "$PY_TGZ" | cut -d' ' -f1)" != "$PY_SHA" ]; then
  curl -fsSL "$PY_URL" -o "$PY_TGZ.tmp"
  [ "$(shasum -a 256 "$PY_TGZ.tmp" | cut -d' ' -f1)" = "$PY_SHA" ] || { echo "✗ El Python descargado no coincide con su huella" >&2; exit 1; }
  mv "$PY_TGZ.tmp" "$PY_TGZ"
fi

DIST="$RAIZ/dist"; APP="$DIST/Alcancia.app"
rm -rf "$DIST"; mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/alcancia"
cp "$REL/Alcancia" "$APP/Contents/MacOS/"
cp Info.plist "$APP/Contents/Info.plist"
[ -f Alcancia.icns ] && cp Alcancia.icns "$APP/Contents/Resources/Alcancia.icns"
tar -xzf "$PY_TGZ" -C "$APP/Contents/Resources"   # → Resources/python/bin/python3
for d in bin ui recetas; do ditto "$RAIZ/$d" "$APP/Contents/Resources/alcancia/$d"; done
# app.json: la descripción de la app que leen las piezas (bin/nucleo.py la busca junto a bin/; sin ella ningún script arranca).
cp "$RAIZ/app.json" "$APP/Contents/Resources/alcancia/app.json"
rm -f "$APP/Contents/Resources/alcancia/ui/demo.json"   # la app usa tus datos, nunca la demo
find "$APP/Contents/Resources/alcancia" -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
chmod +x "$APP/Contents/Resources/alcancia/bin/"*.py

# Firma ad hoc, de adentro hacia afuera, con requisito por identificador (macOS reconoce la app entre versiones).
find "$APP/Contents/Resources/python" -type f \( -name "*.so" -o -name "*.dylib" -o -perm -u+x \) -exec codesign --force --sign - {} \; 2>/dev/null || true
codesign --force --sign - --requirements '=designated => identifier "app.alcancia.mac"' "$APP"

cd "$DIST"
ditto -c -k --keepParent Alcancia.app Alcancia-macOS.zip
shasum -a 256 Alcancia-macOS.zip > Alcancia-macOS.zip.sha256
echo "Listo: $DIST/Alcancia-macOS.zip ($(du -h Alcancia-macOS.zip | cut -f1))"
