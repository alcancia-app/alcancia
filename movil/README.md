# Alcancía en el celular (iPhone y Android) — fase 1

La misma interfaz de `ui/` dentro de una app de [Capacitor](https://capacitorjs.com) 7, **para mirar**. Los datos llegan desde el
Mac en la [copia para el celular](../README.md#copia-celular): un archivo cifrado (`Alcancia-celular.alcancia`) que el Mac deja en
una carpeta de la nube de la persona y que el teléfono abre con su frase. La app del celular no usa internet: no hay servidores,
cuentas, llaves de conectores, IA ni telemetría.

| Ruta | Qué es |
|---|---|
| `armar.mjs` | Arma `www/` (no se versiona): copia `ui/` (sin `demo.json`) y `host/`, y carga el anfitrión en `index.html` (la CSP no cambia). |
| `host/arranque.js`, `host/host.js` | El anfitrión del teléfono: atiende `host.enviar(...)` de la interfaz (como `Ventana.swift` en el Mac). Lee y abre la copia (`ui/copia.js`), guarda los ajustes del teléfono y programa los avisos. Lo que cambia datos (`SOLO_MAC`) responde «Esto se hace en tu Mac por ahora». |
| `plugins/carpeta/` | Plugin propio (Swift y Kotlin): elegir el archivo con el selector del sistema **con permiso para volver a leerlo** (marcador en iOS; permiso persistente de Storage Access Framework en Android), la última copia que se abrió bien, la llave recordada (Llavero de iOS / Android Keystore) y los ajustes. |
| `ios/`, `android/` | Proyectos nativos (Xcode con Swift Package Manager; Gradle). Se versionan; `www/` y `node_modules/` no. |
| `iconos.mjs` | Íconos, pantallas de carga y el ícono chico de los avisos de Android desde `ui/favicon.svg` (solo si cambia el logo). |

Versiones fijas (sin `^`): `@capacitor/core`, `cli`, `ios` y `android` 7.6.9 y `@capacitor/local-notifications` 7.0.7 (la única
dependencia además de Capacitor: los avisos de pagos). Kotlin 2.2.20, Android 8.0 (API 26) o más nuevo, iOS 14 o más nuevo.
`.npmrc` no deja correr scripts de instalación (`ignore-scripts=true`).

## Compilar en el Mac

Necesitas Node 22, Xcode 26 y Android Studio (con el Android SDK 35 y su JDK 21). En la carpeta del repo:

```bash
cd movil
npm ci                       # instala exactamente lo de package-lock.json (incluye el plugin propio, por ruta), sin scripts de instalación (.npmrc)
npx cap telemetry off        # la herramienta de Capacitor no manda estadísticas de uso (una vez por computador)
npm run sync                 # = node armar.mjs && npx cap sync   (repetir cada vez que cambie ui/ u host/)
```

### iPhone: simulador
```bash
npx cap open ios             # abre ios/App/App.xcodeproj en Xcode
```
En Xcode: arriba elige el esquema **App** y un simulador (por ejemplo «iPhone 17», iOS 26) → ▶︎ (⌘R). La primera vez Xcode baja los
paquetes de Swift (Capacitor y el plugin de avisos, desde GitHub). Para probar «Traer tus datos» en el simulador: en el Mac,
Ajustes → «Alcancía en tu celular» con una carpeta de iCloud Drive, e inicia sesión con tu Apple ID en el simulador (Ajustes →
iCloud Drive); o arrastra `Alcancia-celular.alcancia` a la ventana del simulador y guárdalo en «En mi iPhone».

### iPhone: en tu teléfono, sin cuenta pagada
1. Xcode → Settings → Accounts → **+** → tu Apple ID (queda un «Personal Team»).
2. En el proyecto: target **App** → Signing & Capabilities → Team: *tu nombre (Personal Team)*. Si dice que el identificador
   `app.alcancia.movil` no está disponible, cámbialo por uno tuyo (por ejemplo `app.alcancia.movil.casa`).
3. Conecta el iPhone por cable, desbloquéalo y acepta «Confiar en este computador». En el iPhone: Ajustes → Privacidad y
   seguridad → **Modo de desarrollador** → activar (se reinicia).
4. En Xcode elige tu iPhone arriba y ▶︎. La primera vez, en el iPhone: Ajustes → General → VPN y gestión de dispositivos → tu
   Apple ID → **Confiar**.
5. Con una cuenta gratis la app dura **7 días** instalada: para renovarla, conecta el iPhone y vuelve a ▶︎ (los datos se mantienen).

### Android: emulador
```bash
npx cap open android         # abre android/ en Android Studio (espera a que termine «Gradle sync»)
```
En Android Studio: Device Manager → crea o elige un emulador (API 35) → ▶︎ Run 'app'. Para la copia: inicia sesión en Google Drive
en el emulador, o súbela con `adb push Alcancia-celular.alcancia /sdcard/Download/` y elígela desde «Descargas».

### Android: APK para tu teléfono
```bash
cd android
./gradlew assembleDebug      # → app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/debug/app-debug.apk    # con «Depuración por USB» activada en el teléfono
```
Es una versión de prueba firmada con la llave de depuración de tu computador; para las tiendas se firma aparte (más adelante).

### Mirar la interfaz por dentro
- iOS (versión de prueba): Safari del Mac → Desarrollo → *simulador o iPhone* → Alcancía.
- Android (versión de prueba): Chrome → `chrome://inspect`.
- Sin compilar nada: `node pruebas/movil.mjs` la prueba en un navegador con un Capacitor falso.

## Cómo funciona
- **Primer uso:** el idioma, un saludo y «Trae tus datos»: elegir el archivo (iCloud Drive, Google Drive, OneDrive, Dropbox o lo
  que muestre el selector del sistema) y escribir la frase. «Recordarla en este teléfono» guarda la **llave derivada** (nunca la
  frase) en el Llavero de iOS (`WhenUnlockedThisDeviceOnly`) o cifrada con una llave del Android Keystore; si no, se pide al abrir.
- **Al abrir y al volver a primer plano** (como mucho una vez por minuto) se relee el archivo: si el Mac lo actualizó, se ve lo
  nuevo. Si no se puede (sin conexión, a medio subir, de una versión más nueva), queda la última copia que se abrió bien (guardada
  todavía cifrada, fuera de los respaldos) y se dice.
- **Solo para mirar:** la interfaz corre con `LECTURA` (`ui/app.js`): sin «+», sin chat, sin categorizar ni «Ya lo pagué»; lo que
  igual llegue a pedirse responde «Esto se hace en tu Mac por ahora».
- **Avisos de pagos:** al activarlos se pide el permiso y se programan avisos locales para los próximos 35 días (`avisosPagos` en
  `ui/app.js`): 3 días antes y el día que vence, a las 9:00, solo de los gastos que pagas tú y que todavía no tienen pago, sin montos
  y con título genérico (con la pantalla bloqueada iOS muestra solo «Tienes un pago por vencer»). Se vuelven a programar cada vez
  que llega una copia; tocar uno abre Pagos.
- **Seguridad:** sin `server.url` ni navegación a otros sitios; Android sin respaldo ni traspaso (`allowBackup=false`,
  `dataExtractionRules`), sin tráfico en claro, **sin el permiso INTERNET** y sin componentes exportados de más; iOS sin
  excepciones de ATS. `pruebas/contrato.py` lo revisa en cada cambio.

## Qué falta (fase 2)
- **Cambiar cosas desde el celular** (categorizar, «Ya lo pagué», anotar un compromiso): el teléfono dejaría un pedido cifrado en
  la misma carpeta y el Mac lo aplicaría al abrir la copia (el Mac sigue siendo la fuente).
- **La IA del propio teléfono** para conversar con Alcancía (como Repasa: Apple Foundation Models / Gemini Nano), con el mismo
  contexto calculado por código que `bin/chat.py`.
- Windows y Linux escribiendo la copia (hoy solo el Mac), Mercado Pago u otros conectores sin el Mac, tiendas y firma.
