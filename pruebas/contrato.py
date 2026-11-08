#!/usr/bin/env python3
"""Contrato entre la interfaz (ui/app.js) y las apps, para que ninguna se quede atrás. Solo biblioteca estándar.

1. Escritorio (pieza «host-tauri»): cada host.enviar("x") de la interfaz lo atiende la app (registrar), el host (listo, config,
   abrirEnlace, actualizaciones) o una acción declarada de acciones.json; cada window.Alcancia.x que llaman la app, el host y lo
   declarado (responde, progreso) existe en la interfaz; los scripts de bin/ que se corren existen y acciones.json va dentro de
   la app. La misma app es la de Windows y Linux.
2. Celular (movil/host/host.js): cada acción de la interfaz está en ACCIONES o en SOLO_MAC (responde «Esto se hace en tu Mac»);
   cada window.Alcancia.x que llama existe; cada método nativo que llama (llamar("Plugin", "metodo")) existe en el plugin de iOS
   (Swift) y de Android (Kotlin o Java) y en el Capacitor falso de las pruebas (pruebas/capacitor_falso.js).
3. Vista previa: cada acción está simulada en simular() (ui/app.js).
4. Seguridad de la app del celular: Capacitor sin servidor remoto, http en claro ni navegación a otros sitios; Android sin respaldo
   ni traspaso, sin tráfico en claro, sin INTERNET, sin componentes exportados de más y solo los permisos de los avisos; iOS sin
   excepciones de ATS; la página con su CSP; dependencias con versión exacta y sin scripts de instalación.
"""
import glob
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def leer(r):
    ruta = os.path.join(RAIZ, r)
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return f.read()


def juntar(patron):
    return "\n".join(open(f, encoding="utf-8", errors="ignore").read() for f in sorted(glob.glob(os.path.join(RAIZ, patron), recursive=True)))


ui = leer("ui/app.js")
# Lo que manda la interfaz: app.js y las piezas de interfaz (componentes: probarIA, buscarActualizacion, actualizar, abrirEnlace).
piezas_ui = "\n".join(filter(None, (leer(f"ui/{f}") for f in ("componentes.js", "tema.js"))))
acciones = set(re.findall(r'host\.enviar\("(\w+)"', ui)) | set(re.findall(r'(?<![\w.])enviar\("(\w+)"', piezas_ui))
# Lo que la app puede llamar: las funciones de host.responder({...}) (pieza «host-ui»), como método o como propiedad.
cuerpo = ui.split("host.responder({", 1)[1].split("\n  });", 1)[0]
funciones_ui = set(re.findall(r"^\s{4}(?:async\s+)?(\w+)(?:\(|: )", cuerpo, re.M))
problemas = []

# Acciones que solo existen en una plataforma (con el motivo). El resto tiene que estar en todas.
SOLO_MOVIL = {"traer": "traer la copia cifrada desde la nube (solo el celular)"}
SOLO_ESCRITORIO = {"celular": "armar la copia para el celular (solo el computador)"}

# 1) Escritorio (pieza «host-tauri», Rust): cada acción la atiende alguno de los tres lados del puente, en este orden: lo que
#    registra la app (`registrar("x")` en escritorio/src, fuera de pieza/), lo que trae el host (sus internas en
#    escritorio/src/pieza/host.rs: listo, config, abrirEnlace, copiar y, con `actualizaciones`, buscarActualizacion y actualizar) y
#    lo declarado en acciones.json (lo arma pieza.py con las piezas y app.json → «acciones»).
def sin_comentarios(t):
    return re.sub(r"^\s*(//|///|//!).*$", "", t, flags=re.M)


def bloque(texto, inicio):
    i = texto.find(inicio)
    if i < 0:
        return ""
    j, n = texto.index("{", i), 0
    for k in range(j, len(texto)):
        n += {"{": 1, "}": -1}.get(texto[k], 0)
        if n == 0:
            return texto[j:k + 1]
    return ""


rust = sin_comentarios(juntar("escritorio/src/*.rs"))
host_rs = sin_comentarios(leer("escritorio/src/pieza/host.rs") or "")
declaradas = (json.loads(leer("acciones.json") or "{}").get("acciones") or {})
if not rust or not host_rs:
    problemas.append("Falta la app de escritorio (escritorio/src) o la pieza host-tauri (escritorio/src/pieza)")
else:
    registradas = set(re.findall(r'\.registrar\("(\w+)"', rust))
    del_host = set(re.findall(r'^\s*"(\w+)"(?:\s*\|\s*"\w+")*(?:\s+if\s[^=]*)?\s*=>', bloque(host_rs, "fn interna("), re.M))
    del_host |= {x for linea in re.findall(r'^\s*("\w+"(?:\s*\|\s*"\w+")+)', bloque(host_rs, "fn interna("), re.M) for x in re.findall(r'"(\w+)"', linea)}
    if not re.search(r"^\s*actualizaciones:\s", rust, re.M):
        del_host -= {"buscarActualizacion", "actualizar"}
    mac = registradas | del_host | set(declaradas)
    problemas += [f'El escritorio no atiende la acción "{a}" (ni registrada, ni del host, ni en acciones.json)' for a in sorted(acciones - mac - set(SOLO_MOVIL))]
    problemas += [f'El escritorio atiende «{a}», que la interfaz no manda' for a in sorted((registradas | set(declaradas)) - acciones)]
    # Lo que la app y el host llaman en window.Alcancia: responder/llamar("x") en Rust, «responde» y «progreso» de lo declarado, y lo
    # que el host manda siempre (estado, menu) o con las actualizaciones.
    llama = set(re.findall(r'(?:llamar|responder)\((?:h2?, |&h2?, )?"(\w+)"', rust)) | {"estado", "menu"} | {"actualizacionRevisada", "actualizacionProgreso"}
    llama |= {a[k] for a in declaradas.values() for k in ("responde", "progreso") if a.get(k)}
    problemas += [f"El escritorio llama window.Alcancia.{f} y la interfaz no la tiene" for f in sorted(llama - funciones_ui)]
    # probarIA lleva {ia} y responde iaProbada {ia, …} (forma común de la familia, pieza «ia»).
    p_ia = declaradas.get("probarIA") or {}
    if p_ia.get("responde") != "iaProbada" or "ia" not in (p_ia.get("datos") or {}):
        problemas.append("acciones.json: probarIA tiene que recibir {ia} y responder iaProbada (pieza «ia»)")
    scripts = set(re.findall(r'(?:correr_json|con_entrada|correr)\("(\w+\.py)"', rust)) | {a["script"] for a in declaradas.values()}
    problemas += [f"La app llama bin/{s} y no existe" for s in sorted(scripts) if not os.path.exists(os.path.join(RAIZ, "bin", s))]
    # La app lleva acciones.json junto a app.json (sin él, el host no carga nada declarado).
    recursos = ((json.loads(leer("escritorio/tauri.conf.json") or "{}").get("bundle") or {}).get("resources") or {})
    if recursos.get("../acciones.json") != "recursos/acciones.json":
        problemas.append("escritorio/tauri.conf.json no lleva acciones.json dentro de la app")
    # Las llaves de los conectores y la del celular: solo por el llavero y por la entrada estándar, nunca en un argumento.
    conexiones = leer("escritorio/src/conexiones.rs") or ""
    for texto in ('secreto: Some(', 'h.secretos(Some("conexiones"))'):
        if texto not in conexiones:
            problemas.append(f"escritorio/src/conexiones.rs: falta «{texto}» (la llave por la entrada estándar y en el llavero de siempre)")
    if 'h.secretos(Some("celular"))' not in (leer("escritorio/src/celular.rs") or ""):
        problemas.append("escritorio/src/celular.rs: la llave del celular va en el llavero de siempre («Alcancía · celular»)")
    if re.search(r'"--disallowedTools"|"--strict-mcp-config"|"--skip-git-repo-check"', rust):
        problemas.append("escritorio/src: arma el comando de una IA; eso lo hace solo bin/ia.py (pieza «ia»)")
# 2) Celular
host = leer("movil/host/host.js")
llamadas = set()
if host is None:
    problemas.append("Falta movil/host/host.js")
else:
    bloque = host[host.index("const ACCIONES = {"):host.index("\n  };", host.index("const ACCIONES = {"))]
    en_host = set(re.findall(r"^    (?:async )?(\w+)(?:\(|: )", bloque, re.M))
    solo_mac = set(re.findall(r'"(\w+)"', host[host.index("const SOLO_MAC = ["):host.index("];", host.index("const SOLO_MAC = ["))]))
    problemas += [f"La acción «{a}» no está en movil/host/host.js (ACCIONES ni SOLO_MAC)." for a in sorted(acciones - en_host - solo_mac)]
    problemas += [f"movil/host/host.js atiende «{a}», que la interfaz no manda." for a in sorted((en_host | solo_mac) - acciones)]
    problemas += [f"movil/host/host.js llama window.Alcancia.{f}, que no existe en ui/app.js." for f in sorted(set(re.findall(r"A\(\)\.(\w+)", host)) - funciones_ui)]
    PLUGINS = {
        "Carpeta": ("movil/plugins/carpeta/ios/**/*.swift", "movil/plugins/carpeta/android/**/*.kt"),
        "LocalNotifications": ("movil/node_modules/@capacitor/local-notifications/ios/**/*.swift", "movil/node_modules/@capacitor/local-notifications/android/**/*.java"),
    }
    falso = leer("pruebas/capacitor_falso.js") or ""
    falso = falso[falso.index("const P = {"):] if "const P = {" in falso else ""
    llamadas = set(re.findall(r'llamar\("(\w+)", "(\w+)"', host))
    for plugin, metodo in sorted(llamadas):
        if plugin not in PLUGINS:
            problemas.append(f"movil/host/host.js usa el plugin «{plugin}», que el contrato no conoce.")
            continue
        for plataforma, patron in zip(("iOS", "Android"), PLUGINS[plugin]):
            codigo = juntar(patron)
            if not codigo:
                if "node_modules" not in patron:  # los oficiales se revisan solo si están instalados (npm ci en movil/)
                    problemas.append(f"No encuentro el plugin {plugin} de {plataforma} ({patron}).")
                continue
            if plataforma == "iOS":
                ok = re.search(rf'CAPPluginMethod\(name: "{metodo}"', codigo) and re.search(rf"func {metodo}\(_ call: CAPPluginCall\)", codigo)
            else:
                ok = re.search(rf"@PluginMethod[^\n]*\n\s*(?:public )?(?:fun|void) {metodo}\(", codigo)
            if not ok:
                problemas.append(f"{plugin}.{metodo} no existe en el plugin de {plataforma}.")
        if plugin + ": {" not in falso or not re.search(rf"\b{metodo}\(", falso[falso.index(plugin + ": {"):]):
            problemas.append(f"{plugin}.{metodo} no está en pruebas/capacitor_falso.js.")

# 3) Vista previa
simular = ui[ui.index("function simular("):]
simular = simular[:simular.index("\n  }\n")]
problemas += [f"La acción «{a}» no está simulada en simular() (ui/app.js)." for a in sorted(acciones - set(re.findall(r'case "(\w+)"', simular)))]

# 4) Seguridad de la app del celular
cap = json.loads(leer("movil/capacitor.config.json") or "{}")
servidor = cap.get("server") or {}
for clave in ("url", "cleartext", "allowNavigation", "hostname"):
    if clave in servidor:
        problemas.append(f"movil/capacitor.config.json: server.{clave} no va (la app sirve sus archivos desde el teléfono, sin red).")
if servidor.get("androidScheme", "https") != "https" or servidor.get("iosScheme", "capacitor") not in ("capacitor", "ionic"):
    problemas.append("movil/capacitor.config.json: el esquema de la app cambió (eso además borra lo que guardó el WebView).")
if (cap.get("android") or {}).get("allowMixedContent") or (cap.get("android") or {}).get("webContentsDebuggingEnabled"):
    problemas.append("movil/capacitor.config.json: android.allowMixedContent y webContentsDebuggingEnabled no van.")
manifiesto = leer("movil/android/app/src/main/AndroidManifest.xml") or ""
for atributo in ('android:allowBackup="false"', 'android:fullBackupContent="false"', 'android:usesCleartextTraffic="false"', 'android:dataExtractionRules="@xml/data_extraction_rules"'):
    if atributo not in manifiesto:
        problemas.append(f"AndroidManifest.xml: falta {atributo} (finanzas: sin respaldo ni traspaso sin cifrar, ni http).")
reglas = leer("movil/android/app/src/main/res/xml/data_extraction_rules.xml") or ""
if reglas.count('<exclude domain="sharedpref" path="." />') < 2 or "<device-transfer>" not in reglas:
    problemas.append("data_extraction_rules.xml: tiene que dejar fuera todo, en el respaldo y en el traspaso a otro teléfono.")
if not re.search(r'<uses-permission android:name="android.permission.INTERNET" tools:node="remove" />', manifiesto):
    problemas.append("AndroidManifest.xml: INTERNET tiene que quitarse (tools:node=\"remove\"): la app del celular no usa la red.")
exportados = re.findall(r'<(activity|service|receiver|provider)\b[^>]*android:name="([^"]+)"[^>]*android:exported="true"', manifiesto, re.S)
if [n for _, n in exportados if n != ".MainActivity"]:
    problemas.append(f"AndroidManifest.xml: componentes exportados de más: {exportados}.")
permisos = set()
for f in glob.glob(os.path.join(RAIZ, "movil", "plugins", "*", "android", "src", "main", "AndroidManifest.xml")) + \
        glob.glob(os.path.join(RAIZ, "movil", "node_modules", "@capacitor", "local-notifications", "android", "src", "main", "AndroidManifest.xml")):
    texto = open(f, encoding="utf-8").read()
    permisos |= set(re.findall(r'<uses-permission android:name="([^"]+)"', texto))
    if re.search(r'android:exported="true"', texto):
        problemas.append(f"{os.path.relpath(f, RAIZ)}: un plugin exporta componentes.")
permisos |= {p for p in re.findall(r'<uses-permission android:name="([^"]+)"(?! tools:node="remove")', manifiesto)}
PERMITIDOS = {"android.permission.POST_NOTIFICATIONS", "android.permission.RECEIVE_BOOT_COMPLETED", "android.permission.WAKE_LOCK"}
if permisos - PERMITIDOS:
    problemas.append(f"Permisos de Android nuevos (revisar con cuidado antes de agregarlos): {sorted(permisos - PERMITIDOS)}.")
if "NSAppTransportSecurity" in (leer("movil/ios/App/App/Info.plist") or "NSAppTransportSecurity"):
    problemas.append("Info.plist: sin excepciones de App Transport Security (NSAppTransportSecurity).")
indice = leer("ui/index.html")
if "script-src 'self'" not in indice or "connect-src 'self'" not in indice or "unsafe-eval" in indice:
    problemas.append("ui/index.html: la Content-Security-Policy tiene que seguir con script-src 'self' y connect-src 'self'.")
paquete = json.loads(leer("movil/package.json") or "{}")
for seccion in ("dependencies", "devDependencies"):
    for nombre, version in (paquete.get(seccion) or {}).items():
        if not (re.fullmatch(r"\d+\.\d+\.\d+", version) or version.startswith("file:plugins/")):
            problemas.append(f"movil/package.json: {nombre} con versión «{version}» (va exacta, sin ^ ni ~).")
if "ignore-scripts=true" not in (leer("movil/.npmrc") or ""):
    problemas.append("movil/.npmrc: falta ignore-scripts=true (ningún paquete corre scripts al instalarse).")
if not os.path.exists(os.path.join(RAIZ, "movil", "package-lock.json")):
    problemas.append("Falta movil/package-lock.json (npm ci instala exactamente eso).")

if problemas:
    print("✗ Contrato roto:\n  - " + "\n  - ".join(problemas))
    sys.exit(1)
print(f"✓ Contrato: {len(acciones)} acciones, {len(funciones_ui)} funciones y {len(llamadas)} métodos nativos en orden (Mac, celular y vista previa)")
