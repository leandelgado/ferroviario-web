"""
Pydantic v2 models for the motor (query engine) response layer.

These models represent the structured output of the query engine after
executing an Intent against the parquet data warehouse.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

TipoRespuesta = Literal["dato", "comparacion", "ood", "sin_datos", "error"]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

class Metadata(BaseModel):
    """Provenance and coverage information for a query result."""

    tabla: str = ""
    cobertura_desde: str = ""  # "YYYY-MM"
    cobertura_hasta: str = ""  # "YYYY-MM"
    fuente_nl: Literal["groq", "plantilla", "ninguna"] = "ninguna"
    tiempo_ms: float = 0.0
    intent_fallback: bool = False


# ---------------------------------------------------------------------------
# Single-value result
# ---------------------------------------------------------------------------

class Dato(BaseModel):
    """A single aggregated metric value."""

    metrica: str
    etiqueta_humana: str
    unidad: str
    valor: float
    agregacion: str
    filas_detalle: list[dict] = Field(default_factory=list)
    etiqueta_destacada: str = ""  # entity (line) that holds the max/min value


# ---------------------------------------------------------------------------
# Comparison result
# ---------------------------------------------------------------------------

class ItemComparacion(BaseModel):
    """One element in a comparative breakdown."""

    etiqueta: str  # e.g. "Mitre", "2022"
    valor: float
    unidad: str


class Comparacion(BaseModel):
    """A set of values compared across lines or time periods."""

    eje: Literal["linea", "periodo"]
    items: list[ItemComparacion]
    diferencias: list[dict] = Field(default_factory=list)
    # Pairwise diffs: [{"entre": ["A", "B"], "delta": 5.2}]
    ranking: list[str] = Field(default_factory=list)
    # Labels ordered best→worst according to direccion_mejor


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

class Respuesta(BaseModel):
    """Complete response object returned by the query engine."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tipo: TipoRespuesta
    texto_nl: str = ""  # ALWAYS present; empty string is acceptable
    intent: Any  # semantica.Intent at runtime; Any for serialization flexibility
    dato: Dato | None = None
    comparacion: Comparacion | None = None
    sugerencias: list[str] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
    metadata: Metadata = Field(default_factory=Metadata)

    @field_serializer('intent')
    def serialize_intent(self, intent: Any) -> dict | None:
        if intent is None:
            return None
        if hasattr(intent, 'model_dump'):
            return intent.model_dump()
        return str(intent)
