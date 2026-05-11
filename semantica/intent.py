"""
Pydantic models for the semantic layer of the railway conversational agent.

RangoTemporal and Intent models define the structured representation of a
user's analytical intent after parsing their natural language query.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class RangoTemporal(BaseModel):
    """Periodo mensual de análisis, ambos extremos inclusivos."""

    desde: str  # formato "YYYY-MM"
    hasta: str  # formato "YYYY-MM"

    @field_validator('desde', 'hasta')
    @classmethod
    def validar_formato_periodo(cls, v: str) -> str:
        if not re.match(r'^\d{4}-\d{2}$', v):
            raise ValueError(f"Periodo debe ser YYYY-MM, recibido: {v!r}")
        return v

    @model_validator(mode='after')
    def validar_orden_cronologico(self) -> 'RangoTemporal':
        if self.desde > self.hasta:
            raise ValueError(
                f"'desde' debe ser anterior o igual a 'hasta', "
                f"pero se recibió desde={self.desde!r}, hasta={self.hasta!r}"
            )
        return self


class Intent(BaseModel):
    """Intención analítica estructurada extraída de la consulta del usuario."""

    # Métrica objetivo (campo de dim_indicadores)
    metrica: str

    # Tipo de agregación a aplicar
    agregacion: Literal["sum", "mean", "max", "min", "none"]

    # Filtros dimensionales
    filtros_linea: list[str] = Field(default_factory=list)
    filtros_servicio: list[str] = Field(default_factory=list)
    filtros_traccion: list[str] = Field(default_factory=list)

    # Dimensión temporal
    rango_temporal: RangoTemporal | None = None

    # Granularidad del análisis
    granularidad: Literal["red", "linea", "servicio"]

    # Tabla analítica a consultar.
    # Nota: granularidad y tabla son asignados de forma independiente por el
    # parser (provienen de pipelines de matching distintos) y no se validan
    # entre sí aquí.
    tabla: Literal["red_mensual", "linea_mensual", "servicio_mensual"]

    # Metadatos de calidad de la interpretación
    confianza: float = Field(ge=0.0, le=1.0)
    origen: Literal["reglas", "llm", "hibrido"]
    advertencias: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_coherencia_tabla_filtros(self) -> "Intent":
        """
        Valida que la tabla seleccionada sea coherente con los filtros activos.

        Reglas:
        - Si hay filtros de tracción o servicio → tabla debe ser "servicio_mensual"
        - Si tabla es "red_mensual" → no puede haber ningún filtro dimensional
        """
        tiene_filtros_servicio = bool(self.filtros_servicio)
        tiene_filtros_traccion = bool(self.filtros_traccion)

        if tiene_filtros_servicio or tiene_filtros_traccion:
            if self.tabla != "servicio_mensual":
                raise ValueError(
                    f"Cuando se usan filtros de tracción o servicio, "
                    f"la tabla debe ser 'servicio_mensual', pero se recibió '{self.tabla}'. "
                    f"filtros_servicio={self.filtros_servicio}, "
                    f"filtros_traccion={self.filtros_traccion}"
                )

        if self.tabla == "red_mensual":
            if self.filtros_linea:
                raise ValueError(
                    f"La tabla 'red_mensual' no admite filtros de línea, "
                    f"pero se recibió filtros_linea={self.filtros_linea}"
                )
            if self.filtros_servicio:
                raise ValueError(
                    f"La tabla 'red_mensual' no admite filtros de servicio, "
                    f"pero se recibió filtros_servicio={self.filtros_servicio}"
                )
            if self.filtros_traccion:
                raise ValueError(
                    f"La tabla 'red_mensual' no admite filtros de tracción, "
                    f"pero se recibió filtros_traccion={self.filtros_traccion}"
                )

        return self
