"""Lo de Alcancía alrededor de la pieza «ia» (bin/ia.py, que no se edita aquí): los errores en palabras, diciendo dónde se elige
la IA en Alcancía. Solo biblioteca estándar."""
import ia

#: La pieza no sabe dónde se elige la IA en cada app: lo dice la app.
DONDE = {"no_instalada": "Revisa en Ajustes → Tu IA."}


def frase(error):
    """El error de ia.preguntar() en español, para la persona («» si no hay error)."""
    if not error:
        return ""
    return (ia.frase(error) + " " + DONDE.get(error.get("codigo"), "")).strip()


def respuesta(error, **extra):
    """La respuesta de un script cuando la IA falló: el texto para la persona y el código (la interfaz puede decidir por él)."""
    return {"ok": False, "error": frase(error), "codigo": error["codigo"], **extra}
