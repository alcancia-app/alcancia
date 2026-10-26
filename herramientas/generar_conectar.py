"""Genera docs/conectar.html (guía de conexiones automáticas y del MCP) a partir de bin/conectores y ui/idiomas/en.json.
Así la página y la app muestran siempre los mismos pasos. Reusa el estilo de docs/ia.html.

Uso: python3 herramientas/generar_conectar.py    (las pruebas revisan que esté al día)
"""
import html
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "bin"))
import conectores  # noqa: E402

EN = json.load(open(os.path.join(RAIZ, "ui", "idiomas", "en.json"), encoding="utf-8"))["textos"]
PAISES = {"AR": ("Argentina", "Argentina"), "BR": ("Brasil", "Brazil"), "CL": ("Chile", "Chile"), "CO": ("Colombia", "Colombia"),
          "MX": ("México", "Mexico"), "PE": ("Perú", "Peru"), "UY": ("Uruguay", "Uruguay"), "US": ("Estados Unidos", "United States"),
          "CA": ("Canadá", "Canada"), "AU": ("Australia", "Australia"), "NZ": ("Nueva Zelanda", "New Zealand"), "*": ("Todo el mundo", "Worldwide")}


def md(t):
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)


def dos(es, en=None):
    en = EN.get(es, es) if en is None else en
    return f'<span data-es>{md(es)}</span><span data-en>{md(en)}</span>'


def seccion_conector(m):
    i = m.INFO
    paises = " · ".join(f'<span data-es>{PAISES.get(p, (p, p))[0]}</span><span data-en>{PAISES.get(p, (p, p))[1]}</span>' for p in i["paises"])
    beta = '<span class="beta">beta</span>' if i.get("estado") == "beta" else ""
    pasos = "\n".join(f"    <li><p>{dos(p)}</p></li>" for p in i["pasos"])
    nota = f'\n  <p class="nota">{dos(i["nota"])}</p>' if i.get("nota") else ""
    enlace = f'\n  <p><a href="{html.escape(i["enlace"])}" rel="noopener">{dos("Abrir la página de {s}").replace("{s}", html.escape(i["nombre"].split(" (")[0]))} ↗</a></p>' if i.get("enlace") else ""
    letra = html.escape(i["nombre"][0])
    return f'''<section id="{i["id"]}" class="ia"><div class="ancho">
  <div class="ia-cab"><span class="logo" style="background:#2a2420;color:#f2b632">{letra}</span><div><h2>{dos(i["nombre"])} {beta}</h2><small>{paises}</small></div></div>
  <ol class="pasos">
{pasos}
    <li><p>{dos("En Alcancía, abre **Conexiones**, toca **Conectar** en {s} y pega lo que copiaste. Listo: tus movimientos llegan solos al abrir la app y cada 6 horas.", "In Alcancía, open **Connections**, click **Connect** on {s} and paste what you copied. Done: your transactions arrive on their own when the app opens and every 6 hours.").replace("{s}", html.escape(i["nombre"].split(" (")[0]))}</p></li>
  </ol>{nota}{enlace}
</div></section>'''


def main():
    ia = open(os.path.join(RAIZ, "docs", "ia.html"), encoding="utf-8").read()
    estilo = ia[ia.index("<style>"):ia.index("</style>")] + """  .lista { padding-left: 20px; line-height: 1.7; } .lista li { margin-bottom: 8px; }
  .enlaces { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
</style>"""
    todos = sorted(conectores.todos().values(), key=lambda m: (m.INFO["paises"] != ["*"] and "CL" not in m.INFO["paises"], m.INFO["nombre"].lower()))
    secciones = "\n\n".join(seccion_conector(m) for m in todos)
    nav = "".join(f'<a href="#{m.INFO["id"]}">{html.escape(m.INFO["nombre"].split(" (")[0])}</a>' for m in todos)
    pagina = f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conectar tus cuentas a Alcancía: Mercado Pago, PayPal, Stripe, Buda y más — sin la clave del banco</title>
<meta name="description" content="Cómo hacer que tus movimientos lleguen solos a Alcancía con conexiones oficiales (Mercado Pago, PayPal, Stripe, Buda.com, SimpleFIN, Up, Akahu), la carpeta de descargas y cómo conectar tu propia IA por MCP. Nunca con la clave de tu banco.">
<link rel="canonical" href="https://alcancia-app.github.io/alcancia/conectar.html">
<meta name="theme-color" content="#15100c">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Alcancía">
<meta property="og:url" content="https://alcancia-app.github.io/alcancia/conectar.html">
<meta property="og:title" content="Que tus movimientos lleguen solos a Alcancía">
<meta property="og:description" content="Conexiones oficiales con una llave que creas tú, la carpeta de descargas y tu propia IA por MCP.">
<meta property="og:image" content="https://alcancia-app.github.io/alcancia/img/compartir.png">
<meta name="twitter:card" content="summary_large_image">
{estilo}
</head>
<body>
<header class="barra"><div class="ancho">
  <a class="marca" href="./"><img src="favicon.svg" alt="">Alcancía</a>
  <nav><a href="#como">{dos("Cómo funciona", "How it works")}</a><a href="#descargas">{dos("Descargas", "Downloads")}</a>{nav}<a href="#mcp">{dos("Tu IA", "Your AI")}</a></nav>
  <button class="idioma" id="idioma" aria-label="Cambiar idioma / Change language">EN</button>
</div></header>

<main>
<div class="ancho cab">
  <h1>{dos("Que tus movimientos lleguen solos", "Let your transactions arrive on their own")}</h1>
  <p>{dos("Alcancía junta todas las conexiones **oficiales** que existen para que una persona traiga sus propios movimientos, siempre con una llave que creas tú en cada servicio. **Nunca te pedimos la clave de tu banco** ni entramos a su sitio haciéndonos pasar por ti.", "Alcancía brings together every **official** connection that lets a person fetch their own transactions, always with a key you create in each service. **We never ask for your bank password** or log into its website pretending to be you.")}</p>
</div>

<section id="como" class="ia"><div class="ancho">
  <h2>{dos("Cómo funciona", "How it works")}</h2>
  <ul class="lista">
    <li>{dos("La llave se guarda **cifrada en el Llavero** de tu computador (nunca en un archivo) y solo se usa para leer.", "The key is stored **encrypted in your computer's Keychain** (never in a file) and is only used to read.")}</li>
    <li>{dos("Alcancía revisa sola al abrirse y cada 6 horas, trae lo nuevo, **no duplica nada** y le pone categoría igual que a una cartola.", "Alcancía checks on its own when it opens and every 6 hours, fetches what's new, **never duplicates anything** and categorizes it like a statement.")}</li>
    <li>{dos("Habla **solo** con el servicio que conectaste. No hay servidores de Alcancía en el medio.", "It talks **only** to the service you connected. There are no Alcancía servers in between.")}</li>
    <li>{dos("**Beta** = funciona con la API oficial y pasa nuestras pruebas, pero falta que alguien lo use con su cuenta real. Si lo pruebas, [cuéntanos](https://github.com/alcancia-app/alcancia/discussions).".replace("[cuéntanos](https://github.com/alcancia-app/alcancia/discussions)", "cuéntanos en la comunidad"), "**Beta** = works with the official API and passes our tests, but nobody has used it with a real account yet. If you try it, tell us in the community.")}</li>
  </ul>
</div></section>

<section id="descargas" class="ia"><div class="ancho">
  <div class="ia-cab"><span class="logo" style="background:#20302a;color:#7fe0b4">⬇</span><div><h2>{dos("Cartolas que descargues", "Statements you download")}</h2><small>{dos("Cualquier banco del mundo", "Any bank in the world")}</small></div></div>
  <p>{dos("Para los bancos sin API (casi todos): en **Conexiones**, activa **Cartolas que descargues**. Desde ese momento, cada cartola que descargues a tu carpeta de **Descargas** se agrega sola si Alcancía sabe leerla: CSV o Excel con su receta, **OFX/QFX**, **QIF** o **CAMT.053**. Si no la sabe leer, te avisa para que tu IA aprenda. Nunca borra ni mueve tus archivos.", "For banks without an API (almost all of them): in **Connections**, turn on **Statements you download**. From then on, every statement you download to your **Downloads** folder is added automatically if Alcancía can read it: CSV or Excel with its recipe, **OFX/QFX**, **QIF** or **CAMT.053**. If it can't, it lets you know so your AI can learn it. It never deletes or moves your files.")}</p>
</div></section>

{secciones}

<section id="mcp" class="ia"><div class="ancho">
  <div class="ia-cab"><span class="logo" style="background:#222b40;color:#f2b632">✦</span><div><h2>{dos("Tu IA, fuera de Alcancía (MCP)", "Your AI, outside Alcancía (MCP)")}</h2><small>Claude · ChatGPT · Gemini</small></div></div>
  <p>{dos("Alcancía trae un pequeño servidor **MCP** (el estándar con que las IA se conectan a herramientas). Corre en tu computador, solo puede **leer** y no abre nada a internet. Con él, la IA que ya usas puede responder preguntas como «¿cuánto gasté en delivery este mes?» o «¿en qué se me va la plata?».", "Alcancía ships a small **MCP** server (the standard AIs use to connect to tools). It runs on your computer, can only **read** and opens nothing to the internet. With it, the AI you already use can answer questions like “how much did I spend on delivery this month?” or “where is my money going?”.")}</p>
  <ol class="pasos">
    <li><p>{dos("En Alcancía, abre **Conexiones → Tu IA, fuera de Alcancía**. Aparecen las IA que tienes instaladas: Claude (app de escritorio), Claude Code, ChatGPT (app de escritorio y Codex), Gemini CLI o Antigravity.", "In Alcancía, open **Connections → Your AI, outside Alcancía**. The AIs installed on your computer show up: Claude (desktop app), Claude Code, ChatGPT (desktop app and Codex), Gemini CLI or Antigravity.")}</p></li>
    <li><p>{dos("Toca **Conectar**. Alcancía agrega la conexión con el comando oficial de cada IA o editando con cuidado su configuración (guarda una copia la primera vez).", "Click **Connect**. Alcancía adds the connection with each AI's official command or by carefully editing its settings (it keeps a backup the first time).")}</p></li>
    <li><p>{dos("Abre tu IA (la app de Claude hay que cerrarla y abrirla de nuevo) y pregúntale: «Según Alcancía, ¿cómo voy este mes?».", "Open your AI (quit and reopen the Claude app) and ask: “According to Alcancía, how am I doing this month?”.")}</p></li>
  </ol>
  <details class="otras"><summary>{dos("Conectarlo a mano", "Connect it manually")}</summary>
    <div class="comando"><code id="m1">claude mcp add --scope user alcancia -- python3 ~/Developer/alcancia/bin/mcp_servidor.py</code><button data-copiar="m1">{dos("Copiar", "Copy")}</button></div>
    <div class="comando"><code id="m2">codex mcp add alcancia -- python3 ~/Developer/alcancia/bin/mcp_servidor.py</code><button data-copiar="m2">{dos("Copiar", "Copy")}</button></div>
    <div class="comando"><code id="m3">gemini mcp add -s user alcancia python3 ~/Developer/alcancia/bin/mcp_servidor.py</code><button data-copiar="m3">{dos("Copiar", "Copy")}</button></div>
    <p>{dos("Usa la ruta donde tengas Alcancía. Con la app de Mac instalada, el botón Conectar pone la ruta correcta por ti.", "Use the path where you have Alcancía. With the Mac app installed, the Connect button sets the right path for you.")}</p>
  </details>
  <p class="nota">{dos("Cuando le preguntes, tu IA puede leer tus movimientos (fecha, descripción, monto y categoría), y lo que consulta viaja a tu proveedor de IA con tu cuenta, igual que si se lo escribieras. Alcancía no tiene servidores: todo corre en tu computador.")}</p>
</div></section>

<section id="otros" class="ia"><div class="ancho">
  <h2>{dos("¿Y mi banco?", "What about my bank?")}</h2>
  <p>{dos("Casi ningún banco deja que una persona use su propia API todavía: las que existen son para empresas con convenio. Las **finanzas abiertas** oficiales lo van a cambiar (en Chile, la CMF parte en julio de 2027) y Alcancía las va a sumar cuando no exijan un servidor nuestro. ¿Conoces una API oficial que una persona pueda usar con su propia cuenta? Cuéntanos en la comunidad o agrégala tú: está explicado en «Agregar un conector» de la guía para aportar.", "Almost no bank lets individuals use their own API yet: the ones that exist are for companies under contract. Official **open finance** will change that (in Chile, the CMF starts in July 2027) and Alcancía will add it when it doesn't require a server of ours. Know an official API that a person can use with their own account? Tell us in the community or add it yourself: it's explained under “Add a connector” in the contributing guide.")}</p>
  <div class="enlaces"><a href="https://github.com/alcancia-app/alcancia/discussions">{dos("Comunidad", "Community")}</a> · <a href="https://github.com/alcancia-app/alcancia/blob/main/CONTRIBUTING.md#agregar-un-conector-conexión-automática">{dos("Agregar un conector", "Add a connector")}</a></div>
</div></section>
</main>

<footer><div class="ancho">
  <span><a href="./">Alcancía</a> · {dos("Licencia AGPL-3.0", "AGPL-3.0 License")}</span>
  <span>{dos("Las marcas mencionadas son de sus dueños. Alcancía es un proyecto independiente, sin relación con esos servicios.", "The brands mentioned belong to their owners. Alcancía is an independent project, not affiliated with those services.")}</span>
</div></footer>

<script>
  const html = document.documentElement, boton = document.getElementById("idioma");
  const TITULOS = {{ es: document.title, en: "Connect your accounts to Alcancía: Mercado Pago, PayPal, Stripe, Buda and more — no bank password" }};
  let guardado = null; try {{ guardado = localStorage.getItem("alcancia-idioma"); }} catch (e) {{}}
  const poner = (l) => {{ html.lang = l; boton.textContent = l === "es" ? "EN" : "ES"; document.title = TITULOS[l]; }};
  poner(guardado || ((navigator.language || "es").toLowerCase().startsWith("es") ? "es" : "en"));
  boton.onclick = () => {{ const l = html.lang === "es" ? "en" : "es"; poner(l); try {{ localStorage.setItem("alcancia-idioma", l); }} catch (e) {{}} }};
  document.querySelectorAll("[data-copiar]").forEach((b) => b.onclick = async () => {{
    try {{ await navigator.clipboard.writeText(document.getElementById(b.dataset.copiar).textContent); }} catch (e) {{}}
    const antes = b.innerHTML; b.textContent = html.lang === "es" ? "¡Copiado!" : "Copied!"; setTimeout(() => (b.innerHTML = antes), 1600);
  }});
</script>
</body>
</html>
'''
    destino = os.path.join(RAIZ, "docs", "conectar.html")
    if "--revisar" in sys.argv:
        actual = open(destino, encoding="utf-8").read() if os.path.exists(destino) else ""
        if actual != pagina:
            print("✗ docs/conectar.html no está al día: corre python3 herramientas/generar_conectar.py")
            sys.exit(1)
        print("✓ docs/conectar.html al día")
        return
    with open(destino, "w", encoding="utf-8") as f:
        f.write(pagina)
    print("✓ docs/conectar.html")


if __name__ == "__main__":
    main()
