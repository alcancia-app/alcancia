"""Conectores: traen los movimientos directo desde la API oficial de un banco, billetera o servicio. Solo biblioteca estándar.

A diferencia de las recetas (solo datos), un conector es código que habla por internet, así que **solo existen los que vienen en la
app**, revisados por quien mantiene el proyecto. Reglas para todos (ver CONTRIBUTING.md, "Agregar un conector"):
  - Solo APIs oficiales y una llave que la persona crea ella misma en el servicio. Nunca usuario y clave del banco.
  - Solo lectura. Solo los dominios de INFO["hosts"].
  - La credencial llega a sincronizar.py por la entrada estándar (la app la guarda en el Llavero) y nunca se escribe en disco.
  - Nunca se siguen redirecciones (bin/red.py) y la IA que categoriza no hereda nada de Alcancía (bin/ia.py).

Cada módulo define:
  INFO = {"id", "nombre", "paises": ["CL", …] o ["*"], "hosts": [...], "campos": [{"id", "etiqueta", "secreto"}],
          "enlace": página donde se crea la llave, "pasos": [textos], "dias_inicio": cuántos días traer la primera vez,
          "estado": "beta" (probado con un servidor de prueba) | "probado" (alguien lo usó con su cuenta real)}
  probar(cred, red) -> (cred_nueva | None, [{"id", "nombre", "moneda"}])                      revisa la llave y lista las cuentas
  movimientos(cred, desde, hasta, memoria, red) -> (movs, memoria_nueva, cred_nueva | None)
      movs = [{"cuenta", "id_externo", "fecha": "AAAA-MM-DD", "descripcion", "monto" (negativo = gasto), "moneda"}]
      `memoria` es un dict sin secretos que el conector guarda entre una vez y otra (p. ej. un reporte pedido y aún no listo).
      Opcionales en cada movimiento: "medio" (saldo | debito | credito | otro), "cuotas" (2 a 72) y "cuota" (monto de cada una).
Opcionales:
  saldo(cred, red) -> [{"cuenta", "monto", "moneda", "fecha"?}]   el saldo de cada cuenta que informa el servicio (se guarda en
      cuentas.json con origen «conector»); si falla, no pasa nada: Alcancía sigue con el saldo que anotó la persona
  reparar(lista) -> n             arregla lo guardado por una versión anterior (corre una vez por cada REPARACIONES nueva)
  RELEER_DIAS = n                 con una reparación pendiente, se vuelven a pedir n días para completar lo guardado (por id)
"""
import importlib
import pkgutil


class Error(Exception):
    """Un problema que la persona puede entender y arreglar (llave mala, falta un paso en el servicio…)."""


class Esperar(Exception):
    """El servicio está preparando los datos: se vuelve a intentar en la próxima sincronización."""


def todos():
    r = {}
    for m in pkgutil.iter_modules(__path__):
        if m.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{m.name}")
        if hasattr(mod, "INFO"):
            r[mod.INFO["id"]] = mod
    return r


def info_publica():
    """Lo que la interfaz necesita para mostrar cada conector (sin nada secreto)."""
    claves = ("id", "nombre", "paises", "campos", "enlace", "pasos", "estado", "nota")
    return sorted(({k: m.INFO[k] for k in claves if k in m.INFO} for m in todos().values()), key=lambda x: x["nombre"].lower())
