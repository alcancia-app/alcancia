# Cambios · Changelog

Lo que cambia para quien usa Alcancía, en palabras simples. Las versiones anteriores a este archivo están en
[Releases](https://github.com/alcancia-app/alcancia/releases).
*What changes for people using Alcancía, in plain words. Earlier versions are listed in Releases.*

## Sin publicar · Unreleased

- Si tu IA está desactualizada, el aviso ahora te dice dónde elegir otra (Ajustes → Tu IA). Al escribir en un campo mientras
  Alcancía se pone al día, el cursor queda donde estaba.
  *If your AI is out of date, the notice now tells you where to pick another one (Settings → Your AI). When you type in a field
  while Alcancía refreshes, the cursor stays where it was.*
- Los errores de las conexiones (por ejemplo «Mercado Pago no aceptó la llave») ahora salen en tu idioma, y una respuesta enorme o
  que tarda demasiado se corta en vez de dejar la revisión colgada. Tu copia para el celular y tu frase siguen sirviendo igual.
  *Connection errors (for example «Mercado Pago didn't accept the key») now show in your language, and a huge or very slow answer
  is cut off instead of leaving the check hanging. Your phone copy and your passphrase keep working the same.*
- Antes de borrar un pago que se repite (o de desconectar el celular), Alcancía te pregunta, con «Cancelar» ya elegido: un Enter
  apurado no borra nada. Lo mismo al borrar la conversación con Alcancía.
  *Before deleting a recurring payment (or disconnecting your phone), Alcancía asks you, with «Cancel» already selected: a hurried
  Enter deletes nothing. The same when you delete your conversation with Alcancía.*
- **Apariencia:** en Ajustes eliges si Alcancía se ve clara, oscura o como el sistema (también en el celular).
  *Appearance: in Settings you choose whether Alcancía looks light, dark or matches your system (on your phone too).*
- Los diálogos se manejan mejor con el teclado: el foco queda adentro, Esc o tocar fuera los cierra y vuelves a donde estabas.
  Los avisos ya no se pisan: salen uno después del otro. Al actualizar ves el paso y una barra de avance, y en Ajustes puedes
  enviarnos un comentario o una idea (se abre GitHub con tu mensaje listo; nada tuyo se incluye).
  *Dialogs work better with the keyboard: focus stays inside, Esc or tapping outside closes them and you're back where you were.
  Notices no longer overwrite each other: they show one after another. While updating you see the step and a progress bar, and in
  Settings you can send us feedback or an idea (GitHub opens with your message ready; nothing of yours is included).*
- **Por dentro, piezas de Pieza:** tu IA, los ajustes y los idiomas ahora usan las piezas compartidas de la familia (`nucleo`, `ia`,
  `i18n`). Probar tu IA en Ajustes usa las mismas protecciones que todo lo demás (sin herramientas, sin tu memoria) y, si tu IA es
  muy antigua para correr con ellas, Alcancía te pide actualizarla en vez de usarla sin protección. Tus datos siguen en `~/Alcancia`.
  *Under the hood, Pieza pieces: your AI, settings and languages now use the family's shared pieces (`nucleo`, `ia`, `i18n`).
  Testing your AI in Settings uses the same protections as everything else (no tools, no memory) and, if your AI is too old to run
  with them, Alcancía asks you to update it instead of using it unprotected. Your data stays in `~/Alcancia`.*
- Tu IA ya no usa tu memoria de Claude ni tus extensiones al ayudarte con tus finanzas: solo ve lo que Alcancía le muestra.
  *Your AI no longer uses your Claude memory or extensions when helping with your finances: it only sees what Alcancía shows it.*
- Los nombres de pagos, cuentas y movimientos se muestran siempre como texto, nunca como parte de la página.
  *Payment, account and transaction names are always shown as plain text, never as part of the page.*
