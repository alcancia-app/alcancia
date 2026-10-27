# Seguridad de Alcancía

Alcancía guarda tus finanzas en tu computador, así que un error de seguridad puede importar mucho. Si encontraste uno, gracias por
avisarnos en privado. *(English below.)*

## Cómo avisar (en privado)
1. Entra a **[Reportar una vulnerabilidad](https://github.com/alcancia-app/alcancia/security/advisories/new)** (pestaña *Security* del
   repo → *Report a vulnerability*). Solo lo ve quien mantiene el proyecto.
2. Cuenta qué pasa, cómo repetirlo y qué podría hacer alguien con eso. Si necesitas un archivo de ejemplo, **arma uno ficticio**:
   nunca mandes una cartola real, llaves de un servicio ni datos tuyos.
3. **No abras un issue público** ni lo cuentes en Discussions hasta que esté arreglado.

## Qué puedes esperar
- Te respondemos en **5 días hábiles** como máximo (es un proyecto chico, mantenido por personas).
- En **30 días** te contamos qué vamos a hacer y, si se puede, ya está arreglado. Lo grave va primero.
- Publicamos el aviso de seguridad cuando haya versión arreglada, con tu nombre si quieres. Si después de **90 días** no hay arreglo,
  conversamos cómo hacerlo público.
- Si investigas de buena fe, sin tocar datos de otras personas ni dañar nada, no vamos a tomar ninguna acción en tu contra.

## Qué cubre
Todo lo de este repo y lo que sale de él: la app de Mac (y las de Windows y Linux cuando existan), los scripts de `bin/`, la
interfaz de `ui/`, los conectores, el servidor MCP, las actualizaciones, la página publicada y los workflows de GitHub. También el
[catálogo de recetas](https://github.com/alcancia-app/alcancia-catalogo).

Nos interesa especialmente:
- Que una cartola, una receta, una traducción, la descripción de un movimiento o la respuesta de una IA logre **ejecutar código**,
  leer archivos o usar el puente con la app.
- Que una **llave de un conector** salga del Llavero hacia otro lugar que no sea el dominio oficial del servicio.
- Que alguien pueda hacer llegar una **actualización falsa** de Alcancía.
- Que la IA de la persona vea más de lo que dice el [README](README.md) (nunca números de cuenta, RUT ni claves).
- Que un pull request pueda robar secretos o permisos de los workflows.

No cubre: lo que exige tener ya el control de tu computador o de tu cuenta de usuario, problemas de la IA que tú elegiste (Claude,
ChatGPT/Codex o Gemini) o de los servicios con los que conectas, ni ataques de ingeniería social.

## Cómo nos cuidamos (resumen)
- Sin servidores propios ni telemetría; tus datos viven en `~/Alcancia`, solo para tu usuario.
- Nunca pedimos la clave del banco. Las llaves de los conectores van al Llavero, viajan por la entrada estándar y solo a los dominios
  declarados de cada servicio, sin seguir redirecciones.
- Recetas = solo datos, validadas. Todo lo que viene de afuera se escapa antes de mostrarse y la interfaz tiene una política de
  contenido (CSP) que no deja correr código que no venga con la app.
- La IA corre en una carpeta temporal, sin herramientas ni conexiones extra, y lo que propone se valida y la persona lo confirma.
- Todo cambio entra por pull request revisado. Las actions de GitHub están fijadas por SHA, con permisos mínimos y sin
  `pull_request_target`.
- Actualizaciones: hoy se verifica la huella SHA-256 publicada junto al Release. La **firma** de las actualizaciones (para que ni
  siquiera alguien con acceso a la cuenta de GitHub pueda publicar una versión falsa) está diseñada y pendiente: ver abajo.

## Firma de las actualizaciones (diseño, pendiente)
**Estado hoy:** todavía no hay Releases publicados. Cuando los haya, la app baja `Alcancia-macOS.zip` y su `.sha256` del mismo
Release: eso detecta una descarga rota, pero **no** una versión falsa subida por alguien que tome la cuenta de GitHub (subiría las dos
cosas). La app va firmada ad hoc y el actualizador le quita la cuarentena, así que macOS tampoco la revisa.

**Lo que se propone, antes del primer Release:**
1. Una llave **Ed25519** que se crea una sola vez en el Mac de quien mantiene el proyecto (CryptoKit `Curve25519.Signing`), con la
   privada en el Llavero (no sincronizada, ojalá con confirmación) y un respaldo fuera de línea. **Nunca** en GitHub ni en un secreto
   de Actions: si la cuenta cae, la llave no cae con ella.
2. La pública se escribe en la app (`Actualizaciones.swift`, constante en base64). Se puede tener una segunda pública de reserva para
   poder rotar si la primera se pierde.
3. Al publicar, `herramientas/empaquetar.sh` (en el Mac) firma el SHA-256 del zip junto con la versión
   (`alcancia-actualizacion|<versión>|<sha256>`) y deja `Alcancia-macOS.zip.sig` (base64) para subir al Release.
4. La app baja zip, `.sha256` y `.sig` **con URLSession**, calcula el SHA-256, verifica la firma con
   `Curve25519.Signing.PublicKey.isValidSignature` y revisa que la versión firmada sea la del Release y mayor que la instalada (así no
   se puede volver a una versión vieja con fallas). Solo si todo calza escribe el guion que reemplaza la app. Sin `.sig` válido: no
   actualiza y lo dice.
5. Alternativa (o complemento) con costo: firmar con **Developer ID** de Apple y notarizar; el guion verificaría con
   `codesign --verify --deep --strict -R '=anchor apple generic and certificate leaf[subject.OU] = "<TEAMID>"'` y ya no haría falta
   quitar la cuarentena a ciegas.

Por qué no está implementado todavía: cambia el camino de instalación de la app, que no se puede compilar ni probar fuera de un Mac,
y un actualizador roto no se puede arreglar con otra actualización. Se hace junto con el primer Release, probándolo en el Mac.

---

## Security policy (English)
**Report privately** through [Report a vulnerability](https://github.com/alcancia-app/alcancia/security/advisories/new) (GitHub's
private vulnerability reporting). Don't open a public issue. Never send real bank statements, API keys or personal data: build a
fictitious sample instead.

We reply within **5 business days**, share a plan within **30 days**, and publish an advisory once a fix ships (crediting you if you
wish); after **90 days** without a fix we'll agree on disclosure with you. Good-faith research that doesn't touch other people's data
is welcome and won't be pursued.

**In scope:** the Mac app (and future Windows/Linux apps), `bin/` scripts, the `ui/` interface, connectors, the MCP server, updates,
the published site, GitHub workflows, and the recipe catalog. We especially care about code execution from statements, recipes,
translations, transaction descriptions or AI replies; connector keys leaving the Keychain for anything but the service's official
domain; forged updates; the AI seeing more than documented; and pull requests stealing workflow secrets or permissions.
**Out of scope:** attacks that already require control of your computer or user account, issues in the AI tool or connected service
themselves, and social engineering.
