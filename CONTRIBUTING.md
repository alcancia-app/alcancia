# Cómo aportar a Alcancía

Alcancía es gratis y abierta, y la hacemos entre todos. Hay lugar para cualquiera, programes o no. *(English below.)*

## Sin programar
- **Agrega tu banco:** abre la app, agrega tu cartola y deja que tu IA aprenda a leerla. Al final te ofrece compartir **solo la receta**
  (nunca tus movimientos) en el [catálogo](https://github.com/alcancia-app/alcancia-catalogo). También puedes escribirla a mano:
  el formato está en [`recetas/README.md`](recetas/README.md).
- **Conversa:** dudas, ideas o cómo te ordenaste con Alcancía → [Discussions](https://github.com/alcancia-app/alcancia/discussions).
- **Cuéntanos qué falla o qué te gustaría** en [issues](https://github.com/alcancia-app/alcancia/issues/new/choose).
- **Pruébala en tu sistema:** los issues con la etiqueta [`probar`](https://github.com/alcancia-app/alcancia/labels/probar) piden justo eso.
- **Comercios de tu país:** `bin/categorizar.py` tiene una lista de comercios conocidos por categoría. Agregar los de tu país ayuda a todos.
- **Palabras que delatan un compromiso:** `bin/compromisos_conocidos.json` (solo datos) tiene las palabras con que las cartolas
  muestran un dividendo, un crédito, un PAC o un seguro. Suma las de tu país (en mayúsculas y sin tildes) bajo su código.
- **Traducciones:** revisa o mejora `ui/idiomas/en.json`, o propón otro idioma.

## Programando (con o sin IA)
1. Lee [`AGENTS.md`](AGENTS.md): cómo funciona, reglas y cómo se conectan las piezas. Sirve igual para personas y para tu IA
   (`CLAUDE.md` y `GEMINI.md` solo apuntan a ese archivo).
2. Haz un fork, una rama y tu cambio. La sección "Desarrollo" del [README](README.md#desarrollo) explica cómo correrla.
3. Corre `bash pruebas/correr.sh` (lo mismo que revisa GitHub en cada cambio).
4. Si tu cambio se nota (una función nueva, otra forma de hacer algo, otra pantalla), deja al día lo que lo cuenta: el
   README, la página (`docs/`), las capturas y [`CHANGELOG.md`](CHANGELOG.md). Si no sabes bien qué tocar, dilo en el pull
   request y lo completamos nosotros.
5. Abre un pull request contando qué cambia para quien usa Alcancía y cómo lo probaste.

Reglas que importan: código, comentarios y textos en español (todo texto nuevo de la interfaz con su traducción en `ui/idiomas/en.json`);
**nunca subas una cartola real ni datos personales** (usa datos ficticios); solo biblioteca estándar en Python; y no romper el
[formato de los datos](README.md#formato-de-los-datos), porque hay gente con scripts que dependen de él.

**Archivos de piezas:** `bin/nucleo.py`, `bin/ia.py` y `ui/i18n.js` vienen de [Pieza](https://github.com/pieza-app/pieza) (están en
`piezas.json`, con el aviso de la MPL-2.0). No los cambies aquí: propón el cambio en Pieza y llega a Alcancía con «Pieza al día».

Los aportes entran con la licencia del proyecto, [AGPL-3.0](LICENSE).

## Agregar un conector (conexión automática)
Un conector trae los movimientos solo, desde la **API oficial** de un banco, billetera o servicio, con una llave que la persona crea
en ese servicio. Como es código que habla por internet, lo revisamos con más cuidado que una receta. Requisitos:

1. **API oficial y documentada**, que una persona pueda usar con su propia cuenta. Nada de entrar al sitio del banco con usuario y
   clave, ni APIs "no oficiales". Si el servicio exige ser empresa o firmar convenio, no sirve (todavía).
2. **Solo lectura.** Si el servicio permite elegir permisos, pide solo los de leer movimientos.
3. Un archivo en `bin/conectores/<id>.py` con `INFO`, `probar()` y `movimientos()` (el contrato está al inicio de
   `bin/conectores/__init__.py`). Todos los pedidos van por `red` (el objeto que recibes), que solo deja hablar con `INFO["hosts"]`.
4. **Solo biblioteca estándar** de Python. Sin SDKs.
5. Una prueba en `pruebas/test_python.py` contra `pruebas/servidor_falso.py`, con respuestas copiadas de la documentación oficial
   (datos inventados). Que revise que la llave va en la cabecera correcta, la paginación y el signo de los montos.
6. Los pasos para crear la llave (`INFO["pasos"]`) con su traducción en `ui/idiomas/en.json`, y una sección en `docs/conectar.html`.
7. Entra como `"estado": "beta"`. Pasa a `"probado"` cuando alguien lo usa con su cuenta real y cuenta en el PR que los movimientos
   calzan con los de la app del servicio (sin pegar sus movimientos).

¿Quieres un conector pero no programas? Abre una idea en [Discussions](https://github.com/alcancia-app/alcancia/discussions) con el
enlace a la documentación de la API: así sabemos dónde hay conexiones oficiales.

## Cómo revisamos
Todo entra por pull request y lo junta alguien que mantiene el proyecto: nadie puede subir cambios directo. Revisamos:
- **Siempre:** que las pruebas de GitHub pasen, que no haya datos personales y que el cambio haga lo que dice. Si es tu primer
  aporte, GitHub espera a que aprobemos correr las pruebas (es normal).
- **Que la documentación diga la verdad:** si el cambio agrega, cambia o quita algo que se nota, revisamos que el
  README, la página, las guías y el `CHANGELOG.md` cuenten la app como queda. Lo que falte lo completamos antes de juntar.
- **Código:** que no cambie el formato de los datos, que los textos nuevos tengan su traducción y que no agregue dependencias,
  conexiones a internet nuevas ni nada que pida claves o datos bancarios.
- **Conectores:** API oficial, llave de la persona, solo lectura, solo los dominios declarados, sin dependencias, con prueba contra el
  servidor falso. Leemos cada línea que toca la red.
- **Recetas:** que sea válida (`recetas.validar`), que no traiga datos de la cartola (solo nombres de columnas y formatos) y, para
  incluirla en la app, que alguien la haya probado con una cartola real de ese banco.
- **Traducciones:** que una persona que hable el idioma revise el texto.
- **Workflows y herramientas:** cualquier cambio en `.github/`, `build.sh`, `herramientas/` o algo que descargue o instale lo revisa
  quien mantiene el proyecto línea por línea. Las actions van fijadas por SHA completo, con permisos mínimos y sin
  `pull_request_target`.

Si algo falta te lo pedimos con un comentario; casi nunca cerramos un aporte sin conversar.

¿Buscas por dónde empezar? Mira los issues con la etiqueta
[`good first issue`](https://github.com/alcancia-app/alcancia/labels/good%20first%20issue) (o [`sin programar`](https://github.com/alcancia-app/alcancia/labels/sin%20programar)) o pregunta en Discussions.

¿Encontraste un problema de seguridad? No abras un issue: avísanos en privado como dice [`SECURITY.md`](SECURITY.md).

Al participar aceptas el [código de conducta](CODE_OF_CONDUCT.md).

---

## Contributing (English)
- **Connectors (automatic sync):** a module in `bin/conectores/` using an official, documented API with a key the user creates;
  read-only, stdlib only, requests only to its declared hosts, tested against `pruebas/servidor_falso.py`. Ships as `beta` until someone
  confirms it with a real account. No scraping with bank usernames/passwords, ever.
- **No code needed:** add your bank (let your AI learn your statement and share just the *recipe*, never your transactions), chat in
  [Discussions](https://github.com/alcancia-app/alcancia/discussions), report bugs or ideas in
  [issues](https://github.com/alcancia-app/alcancia/issues/new/choose), test it on your system (label `probar`), add well-known
  merchants and the words statements use for loans, mortgages or insurance (`bin/compromisos_conocidos.json`) from your country, and help with translations.
- **Code (with or without AI):** read [`AGENTS.md`](AGENTS.md), fork, branch, run `bash pruebas/correr.sh` and open a pull request.
  Code and comments are in Spanish; UI text needs its English entry in `ui/idiomas/en.json`; never commit real statements or personal data.
  If your change is visible, also update the README, the page (`docs/`), screenshots and `CHANGELOG.md`, or say so in the
  pull request and we'll do it.
- **Piece files:** `bin/nucleo.py`, `bin/ia.py` and `ui/i18n.js` come from [Pieza](https://github.com/pieza-app/pieza) (listed in
  `piezas.json`, MPL-2.0 notice included). Don't change them here: propose the change in Pieza and it arrives through «Pieza al día».
- **Review:** everything goes through a pull request and a maintainer merges it. Contributions are licensed under AGPL-3.0.
  We also check that the README, the page and the docs still describe the app as it is.
- **Security issues:** never in a public issue; report privately as described in [`SECURITY.md`](SECURITY.md).

## Aportar con los flujos de Pieza

Esta app es parte de la familia de [Pieza](https://github.com/pieza-app/pieza). Instala sus flujos (crear, revisar aportes y las
reglas de seguridad) en tu IA:
- **Claude Code:** `/plugin marketplace add pieza-app/pieza` y `/plugin install pieza@pieza`.
- **Gemini CLI:** `gemini extensions install https://github.com/pieza-app/pieza` (comandos `/pieza:crear` y `/pieza:revisar`).
- **Codex:** clona Pieza y corre `python3 herramientas/pieza.py skills instalar codex` (quedan en `~/.agents/skills`).
- **Otra IA:** sigue `AGENTS.md` y la [tabla de equivalencias](https://github.com/pieza-app/pieza/blob/main/docs/otras-ias.md).

Si mejoras algo que sirve a todas las apps, propónlo en Pieza.
