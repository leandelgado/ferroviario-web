"""Public API for the railway conversational agent motor (query engine)."""

from motor.orquestador import responder
from motor.respuesta import Respuesta, Dato, Comparacion, TipoRespuesta, Metadata
from motor.almacen import Almacen as _Almacen


def cobertura_tabla(tabla: str) -> tuple[str, str]:
    """Return (desde, hasta) coverage strings for a given table."""
    return _Almacen.cobertura(tabla)


__all__ = ["responder", "Respuesta", "Dato", "Comparacion", "TipoRespuesta", "Metadata", "cobertura_tabla"]
