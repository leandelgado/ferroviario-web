"""
LLM-based fallback intent parser for the railway conversational agent.

Provides an abstract LLMBackend interface and two concrete implementations:
  - GeminiBackend: uses Google Gemini (google-genai SDK) with structured output
  - StubBackend: returns a hardcoded Intent for testing without an API key

Public API
----------
parse(pregunta, hint=None, *, backend=None) -> Intent
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

from semantica.intent import Intent, RangoTemporal

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class LLMBackend(ABC):
    """Abstract interface for LLM-based intent parsers."""

    @abstractmethod
    def parse(self, pregunta: str, hint: Optional[Intent] = None) -> Intent:
        """Parse a Spanish railway question into a structured Intent."""
        ...


# ---------------------------------------------------------------------------
# Stub backend (for testing without a real API key)
# ---------------------------------------------------------------------------

class StubBackend(LLMBackend):
    """Returns a hardcoded Intent with origen='llm' and confianza=0.5.

    Use this in unit tests to exercise parser_llm without hitting the
    Gemini API.
    """

    def parse(self, pregunta: str, hint: Optional[Intent] = None) -> Intent:  # noqa: ARG002
        return Intent(
            metrica="pax_pagos",
            agregacion="sum",
            filtros_linea=[],
            filtros_servicio=[],
            filtros_traccion=[],
            rango_temporal=None,
            granularidad="red",
            tabla="red_mensual",
            confianza=0.5,
            origen="llm",
            advertencias=["stub backend — no real API call was made"],
        )


# ---------------------------------------------------------------------------
# System prompt helpers
# ---------------------------------------------------------------------------

# 20 indicadores serialized as compact JSON (pre-computed constant).
_INDICADORES_JSON: str = json.dumps(
    [
        {"campo": "pax_pagos", "etiqueta_humana": "Pasajeros pagos",
         "descripcion_breve": "Pasajeros que abonaron boleto",
         "sinonimos": ["pasajeros", "demanda", "viajeros", "usuarios"],
         "agregable": True},
        {"campo": "pax_dia_habil", "etiqueta_humana": "Pasajeros por día hábil",
         "descripcion_breve": "Promedio estimado de pasajeros en día hábil",
         "sinonimos": ["pasajeros diarios", "afluencia diaria"],
         "agregable": False},
        {"campo": "pax_km", "etiqueta_humana": "Pasajeros kilómetro",
         "descripcion_breve": "Suma de distancias recorridas por cada pasajero",
         "sinonimos": ["pax-km", "pasajeros kilómetro"],
         "agregable": True},
        {"campo": "pax_variacion_yoy", "etiqueta_humana": "Variación interanual pasajeros",
         "descripcion_breve": "Cambio porcentual vs mismo mes del año anterior",
         "sinonimos": ["variación anual pasajeros", "crecimiento pasajeros"],
         "agregable": False},
        {"campo": "trenes_programados", "etiqueta_humana": "Trenes programados",
         "descripcion_breve": "Total de servicios planificados",
         "sinonimos": ["servicios programados", "oferta"],
         "agregable": True},
        {"campo": "trenes_cancelados", "etiqueta_humana": "Trenes cancelados",
         "descripcion_breve": "Servicios planificados que no se realizaron",
         "sinonimos": ["cancelaciones", "servicios cancelados"],
         "agregable": True},
        {"campo": "trenes_corridos", "etiqueta_humana": "Trenes corridos",
         "descripcion_breve": "Servicios efectivamente realizados",
         "sinonimos": ["servicios realizados", "trenes realizados"],
         "agregable": True},
        {"campo": "trenes_puntuales", "etiqueta_humana": "Trenes puntuales",
         "descripcion_breve": "Servicios realizados con demora <=5 min",
         "sinonimos": ["servicios puntuales", "puntualidad absoluta"],
         "agregable": True},
        {"campo": "trenes_atrasados", "etiqueta_humana": "Trenes atrasados",
         "descripcion_breve": "Servicios realizados con demora >5 min",
         "sinonimos": ["atrasos", "demoras"],
         "agregable": True},
        {"campo": "trenes_km", "etiqueta_humana": "Trenes kilómetro",
         "descripcion_breve": "Kilómetros totales recorridos por los trenes",
         "sinonimos": ["TK", "trenes-km"],
         "agregable": True},
        {"campo": "coches_km", "etiqueta_humana": "Coches kilómetro",
         "descripcion_breve": "Kilómetros totales recorridos por los coches",
         "sinonimos": ["CK", "coches-km"],
         "agregable": True},
        {"campo": "tasa_cancelacion", "etiqueta_humana": "Tasa de cancelación",
         "descripcion_breve": "Trenes cancelados / trenes programados",
         "sinonimos": ["cancelados %", "porcentaje cancelaciones"],
         "agregable": False},
        {"campo": "regularidad_absoluta", "etiqueta_humana": "Regularidad absoluta",
         "descripcion_breve": "Trenes puntuales / trenes programados. Meta >=0.95",
         "sinonimos": ["puntualidad", "regularidad"],
         "agregable": False},
        {"campo": "regularidad_relativa", "etiqueta_humana": "Regularidad relativa",
         "descripcion_breve": "Trenes puntuales / trenes corridos",
         "sinonimos": ["puntualidad relativa"],
         "agregable": False},
        {"campo": "cumplimiento_programa", "etiqueta_humana": "Cumplimiento de programa",
         "descripcion_breve": "Trenes corridos / trenes programados",
         "sinonimos": ["cumplimiento"],
         "agregable": False},
        {"campo": "recaudacion_pesos", "etiqueta_humana": "Recaudación (pesos)",
         "descripcion_breve": "Ingresos por venta de boletos en pesos corrientes",
         "sinonimos": ["recaudación", "ingresos boletos"],
         "agregable": True},
        {"campo": "tarifa_media_pesos", "etiqueta_humana": "Tarifa media (pesos)",
         "descripcion_breve": "Recaudación / pasajeros pagos en pesos corrientes",
         "sinonimos": ["precio promedio boleto", "tarifa"],
         "agregable": False},
        {"campo": "ocupacion_media", "etiqueta_humana": "Ocupación media",
         "descripcion_breve": "Pasajeros-km / coches-km. Pax promedio por coche",
         "sinonimos": ["ocupación", "carga media"],
         "agregable": False},
        {"campo": "km_linea", "etiqueta_humana": "Kilómetros de línea",
         "descripcion_breve": "Extensión de la línea entre cabeceras en servicio",
         "sinonimos": ["extensión", "longitud línea"],
         "agregable": False},
        {"campo": "estaciones", "etiqueta_humana": "Estaciones en servicio",
         "descripcion_breve": "Cantidad de estaciones activas",
         "sinonimos": ["paradas", "estaciones"],
         "agregable": False},
    ],
    ensure_ascii=False,
    separators=(",", ":"),
)

_LINEAS_CANONICAS: list[str] = [
    "Belgrano Norte",
    "Belgrano Sur",
    "Mitre",
    "Roca",
    "San Martín",
    "Sarmiento",
    "Tren de la Costa",
    "Urquiza",
]

_SYSTEM_PROMPT_TEMPLATE = """\
Eres un parser de intenciones para consultas sobre el sistema ferroviario metropolitano AMBA (Argentina). Tu tarea es extraer la intención estructurada de una pregunta en español.

## Indicadores disponibles (dim_indicadores)

Los 20 indicadores disponibles (campo, etiqueta_humana, descripcion_breve, sinonimos, agregable):
{indicadores_json}

## Líneas ferroviarias canónicas

Las 8 líneas del sistema son exactamente:
{lineas_json}

## Esquema de salida (Intent)

Devuelve un objeto JSON con estos campos:
- metrica (str): campo de dim_indicadores que mejor responde la consulta
- agregacion (str): una de "sum", "mean", "max", "min", "none"
  - "sum" para totales/conteos (pasajeros, trenes, etc.) cuando la métrica es agregable
  - "mean" para promedios, tasas, ratios y métricas no agregables
  - "max"/"min" para máximos/mínimos explícitos
- filtros_linea (list[str]): nombres canónicos de líneas mencionadas (lista vacía si no aplica)
- filtros_servicio (list[str]): nombres de servicios específicos (lista vacía si no aplica)
- filtros_traccion (list[str]): tipo de tracción como "Eléctrico" o "Diesel" (lista vacía si no aplica)
- rango_temporal (object | null): {{"desde": "YYYY-MM", "hasta": "YYYY-MM"}} o null si no se menciona fecha
- granularidad (str): "red" si es toda la red, "linea" si hay filtros de línea, "servicio" si hay filtros de servicio o tracción
- tabla (str): "red_mensual", "linea_mensual" o "servicio_mensual" (coherente con granularidad)
- confianza (float): entre 0.0 y 1.0, tu nivel de certeza sobre la interpretación
- origen (str): siempre "llm"
- advertencias (list[str]): lista de advertencias si hay ambigüedad (lista vacía si no hay)

## Reglas de coherencia

- Si filtros_servicio o filtros_traccion no están vacíos → tabla debe ser "servicio_mensual" y granularidad "servicio"
- Si filtros_linea no está vacío (y no hay filtros de servicio/tracción) → tabla "linea_mensual", granularidad "linea"
- Si todo está vacío → tabla "red_mensual", granularidad "red"
- La tabla "red_mensual" NO puede tener filtros de ninguna clase

## Ejemplos

Ejemplo 1:
Input: "¿Cuántos pasajeros tuvo la línea Mitre en 2023?"
Output: {{"metrica":"pax_pagos","agregacion":"sum","filtros_linea":["Mitre"],"filtros_servicio":[],"filtros_traccion":[],"rango_temporal":{{"desde":"2023-01","hasta":"2023-12"}},"granularidad":"linea","tabla":"linea_mensual","confianza":0.95,"origen":"llm","advertencias":[]}}

Ejemplo 2:
Input: "¿Qué tan puntual fue la red en marzo 2024?"
Output: {{"metrica":"regularidad_absoluta","agregacion":"mean","filtros_linea":[],"filtros_servicio":[],"filtros_traccion":[],"rango_temporal":{{"desde":"2024-03","hasta":"2024-03"}},"granularidad":"red","tabla":"red_mensual","confianza":0.9,"origen":"llm","advertencias":[]}}

Ejemplo 3:
Input: "Cancelaciones en Belgrano Norte y Urquiza entre 2018 y 2020"
Output: {{"metrica":"trenes_cancelados","agregacion":"sum","filtros_linea":["Belgrano Norte","Urquiza"],"filtros_servicio":[],"filtros_traccion":[],"rango_temporal":{{"desde":"2018-01","hasta":"2020-12"}},"granularidad":"linea","tabla":"linea_mensual","confianza":0.92,"origen":"llm","advertencias":[]}}

Ejemplo 4:
Input: "Ocupación media de trenes eléctricos del Roca en 2021"
Output: {{"metrica":"ocupacion_media","agregacion":"mean","filtros_linea":["Roca"],"filtros_servicio":[],"filtros_traccion":["Eléctrico"],"rango_temporal":{{"desde":"2021-01","hasta":"2021-12"}},"granularidad":"servicio","tabla":"servicio_mensual","confianza":0.93,"origen":"llm","advertencias":[]}}
"""


def _build_system_prompt() -> str:
    """Build the static system prompt with indicators and canonical lines."""
    return _SYSTEM_PROMPT_TEMPLATE.format(
        indicadores_json=_INDICADORES_JSON,
        lineas_json=json.dumps(_LINEAS_CANONICAS, ensure_ascii=False),
    )


def _build_user_message(pregunta: str, hint: Optional[Intent]) -> str:
    """Build the user message, optionally including the rule-based hint."""
    parts = [f'Input: "{pregunta}"']
    if hint is not None:
        parts.append(
            "El parser de reglas obtuvo la siguiente información parcial que "
            f"puedes usar como contexto: {hint.model_dump()}"
        )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------

class GeminiBackend(LLMBackend):
    """Calls Google Gemini with structured output to parse railway intents.

    Uses the new ``google-genai`` SDK (package name ``google-genai``, import
    path ``google.genai``).

    Primary model: ``gemini-2.5-flash``
    Fallback model: ``gemini-2.5-pro`` (can be used when primary is unavailable
    or for more nuanced queries).

    API key is read from the ``GEMINI_API_KEY`` env var, falling back to
    ``GOOGLE_API_KEY``. A ``RuntimeError`` is raised if neither is set.
    """

    PRIMARY_MODEL = "gemini-2.5-flash"
    FALLBACK_MODEL = "gemini-2.5-pro"

    def __init__(self, model: Optional[str] = None) -> None:
        """Initialise the Gemini client.

        Args:
            model: Override the model name. Defaults to PRIMARY_MODEL.

        Raises:
            RuntimeError: If neither GEMINI_API_KEY nor GOOGLE_API_KEY is set.
        """
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No se encontró la clave de API de Gemini. "
                "Configura la variable de entorno GEMINI_API_KEY (o GOOGLE_API_KEY)."
            )

        from google import genai  # local import to keep module importable without SDK

        self._client = genai.Client(api_key=api_key)
        self._model = model or self.PRIMARY_MODEL
        self._system_prompt = _build_system_prompt()

        _logger.debug("GeminiBackend inicializado con modelo=%s", self._model)

    def parse(self, pregunta: str, hint: Optional[Intent] = None) -> Intent:
        """Call the Gemini API and return a structured Intent.

        Args:
            pregunta: Raw Spanish question.
            hint: Optional partial Intent from the rule-based parser.

        Returns:
            Intent with origen="llm".
        """
        from google.genai import types  # local import

        user_message = _build_user_message(pregunta, hint)
        full_prompt = f"{self._system_prompt}\n\n{user_message}"

        _logger.debug("Llamando a Gemini model=%s", self._model)

        response = self._client.models.generate_content(
            model=self._model,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Intent,
            ),
        )

        raw_text: str = response.text
        _logger.debug("Respuesta Gemini (raw): %s", raw_text[:300])

        intent_dict = json.loads(raw_text)

        # Ensure origen is always "llm" regardless of what the model returned
        intent_dict["origen"] = "llm"

        intent = Intent(**intent_dict)
        return intent


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(
    pregunta: str,
    hint: Optional[Intent] = None,
    *,
    backend: Optional[LLMBackend] = None,
) -> Intent:
    """Parse a railway question using an LLM backend.

    Uses GeminiBackend by default if GEMINI_API_KEY (or GOOGLE_API_KEY) is
    set in the environment. Falls back gracefully to StubBackend if neither
    key is available and no explicit backend was provided.

    Args:
        pregunta: Raw Spanish question.
        hint: Optional partial Intent from the rule-based parser to provide
              context to the LLM.
        backend: Explicit LLMBackend to use. If None, GeminiBackend is
                 instantiated when an API key is available; StubBackend
                 otherwise.

    Returns:
        Intent with origen="llm".
    """
    if backend is None:
        has_key = bool(
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        )
        if has_key:
            backend = GeminiBackend()
        else:
            _logger.warning(
                "GEMINI_API_KEY no configurada — usando StubBackend. "
                "Configura GEMINI_API_KEY para habilitar el parser LLM real."
            )
            backend = StubBackend()

    intent = backend.parse(pregunta, hint)
    # Enforce origen="llm" at the public API level
    if intent.origen != "llm":
        intent = intent.model_copy(update={"origen": "llm"})
    return intent
