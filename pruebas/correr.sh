#!/bin/bash
# Todas las pruebas (las mismas que corre GitHub en cada cambio).
# Uso: bash pruebas/correr.sh   (la interfaz necesita Playwright: PLAYWRIGHT=/ruta/a/playwright si no está en node_modules)
set -e
cd "$(dirname "$0")/.."
echo "Sintaxis"; node --check ui/app.js; node --check ui/i18n.js; node --check ui/copia.js; node --check ui/cifrado.js; for f in movil/host/*.js movil/*.mjs pruebas/*.mjs pruebas/capacitor_falso.js; do node --check "$f"; done
python3 -m py_compile bin/*.py bin/conectores/*.py pruebas/*.py ejemplos/*.py herramientas/*.py; for f in build.sh herramientas/*.sh; do bash -n "$f"; done
python3 -c "import json, glob; [json.load(open(f, encoding='utf-8')) for f in glob.glob('ui/idiomas/*.json') + glob.glob('recetas/*.json') + ['ui/demo.json', 'pruebas/casos.json', 'movil/package.json', 'movil/capacitor.config.json']]"
echo "Privacidad"; bash herramientas/revisar_privacidad.sh --generico
echo "Contrato (Mac, celular, plugins nativos y vista previa)"; python3 pruebas/contrato.py
echo "Página de conexiones"; python3 herramientas/generar_conectar.py --revisar
echo "Python"; python3 pruebas/test_python.py 2>&1 | tail -3
echo "Copia para el celular (cifrado)"; node pruebas/copia.mjs
echo "Interfaz"; node pruebas/interfaz.mjs
echo "App del celular de punta a punta (anfitrión del teléfono y Capacitor falso)"; node pruebas/movil.mjs
