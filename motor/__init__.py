"""Public API for the railway conversational agent motor (query engine)."""

from motor.orquestador import responder
from motor.respuesta import Respuesta, Dato, Comparacion, TipoRespuesta, Metadata

__all__ = ["responder", "Respuesta", "Dato", "Comparacion", "TipoRespuesta", "Metadata"]
