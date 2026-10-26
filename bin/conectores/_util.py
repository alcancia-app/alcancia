"""Ayudas compartidas por los conectores."""
from datetime import date, datetime, timezone


def fecha_local(texto):
    """«2026-10-03T12:10:44.000-04:00» → «2026-10-03» (la fecha tal como la ve la persona en su zona horaria)."""
    t = str(texto or "").strip()
    if not t:
        return None
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return date.fromisoformat(t[:10]).isoformat()
        except ValueError:
            return None


def fecha_unix(segundos):
    try:
        return datetime.fromtimestamp(int(segundos), tz=timezone.utc).astimezone().date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def unix(d, fin=False):
    """Fecha → segundos unix (inicio o fin del día, en la zona del computador)."""
    hora = datetime.max.time().replace(microsecond=0) if fin else datetime.min.time()
    return int(datetime.combine(d, hora).astimezone().timestamp())


def rfc3339(d, fin=False):
    hora = datetime.max.time().replace(microsecond=0) if fin else datetime.min.time()
    return datetime.combine(d, hora).astimezone().isoformat(timespec="seconds")


def numero(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
