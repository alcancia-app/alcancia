#!/bin/bash
# Todas las pruebas (las mismas que corre GitHub en cada cambio).
# Uso: bash pruebas/correr.sh   (la interfaz necesita Playwright: PLAYWRIGHT=/ruta/a/playwright si no está en node_modules)
#      La app de escritorio (Rust, pieza «host-tauri») se compila y prueba si hay cargo (SIN_RUST=1 la salta), y se abre si hay Xvfb.
set -e
cd "$(dirname "$0")/.."
echo "Sintaxis"; node --check ui/app.js; node --check ui/i18n.js; node --check ui/copia.js; node --check ui/cifrado.js; for f in movil/host/*.js movil/*.mjs pruebas/*.mjs pruebas/capacitor_falso.js; do node --check "$f"; done
python3 -m py_compile bin/*.py bin/conectores/*.py pruebas/*.py ejemplos/*.py herramientas/*.py; for f in build.sh herramientas/*.sh; do bash -n "$f"; done
python3 -c "import json, glob; [json.load(open(f, encoding='utf-8')) for f in glob.glob('ui/idiomas/*.json') + glob.glob('recetas/*.json') + ['ui/demo.json', 'pruebas/casos.json', 'movil/package.json', 'movil/capacitor.config.json']]"
echo "Privacidad"; bash herramientas/revisar_privacidad.sh --generico
echo "Contrato (escritorio, celular, plugins nativos y vista previa)"; python3 pruebas/contrato.py
echo "Página de conexiones"; python3 herramientas/generar_conectar.py --revisar
echo "Python"; python3 pruebas/test_python.py > /tmp/alcancia-python.txt 2>&1 || { cat /tmp/alcancia-python.txt; exit 1; }; tail -3 /tmp/alcancia-python.txt
echo "Copia para el celular (cifrado)"; node pruebas/copia.mjs
echo "Interfaz"; node pruebas/interfaz.mjs
echo "App del celular de punta a punta (anfitrión del teléfono y Capacitor falso)"; node pruebas/movil.mjs
if command -v cargo >/dev/null && [ "${SIN_RUST:-0}" != "1" ]; then
  echo "App de escritorio (Rust, pieza «host-tauri»)"; (cd escritorio && cargo test --quiet 2>&1 | grep -E "test result|error" | tail -3)
  if command -v xvfb-run >/dev/null && command -v dbus-run-session >/dev/null; then bash escritorio/pruebas/arranque.sh; fi
else
  echo "App de escritorio: sin cargo (o SIN_RUST=1), se prueba en GitHub (job «app»)"
fi
