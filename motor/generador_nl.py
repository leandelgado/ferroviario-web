"""
Natural language response generator for the railway conversational agent.

Generates plain-text NL responses using Gemini (google-genai SDK) with
automatic fallback to deterministic templates (motor.plantillas) when:
  - sin_llm=True is passed explicitly
  - No API key is configured
  - Gemini call fails for any reason

Public API
----------
generar_nl(pregunta, intent, dato_o_comp, tipo, advertencias, sugerencias,
           almacen, *, sin_llm=False) -> tuple[str, str]
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import TYPE_CHECKING, Any

from motor import plantillas

if TYPE_CHECKING:
    from motor.respuesta import Comparacion, Dato, TipoRespuesta
    from motor.almacen import Almacen as AlmacenType
    from semantica.intent import Intent

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt (Spanish rioplatense, exact specification)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
Sos un asistente experto en datos del sistema ferroviario metropolitano de
Buenos Aires (CNRT AMBA). Respondé en español rioplatense neutral, profesional
y conciso, usando EXCLUSIVAMENTE los datos numéricos del bloque DATOS.

Reglas estrictas:
1. NUNCA inventes números. Si un valor no está en DATOS, no lo menciones.
2. Citá la unidad y el período cubierto cuando corresponda.
3. Si hay advertencias en el contexto, mencionalas brevemente.
4. Para comparaciones, indicá quién tuvo mejor desempeño según direccion_mejor.
5. Largo objetivo: 2-4 oraciones. Bullets solo si son 3+ items.
6. No expliques cómo obtuviste el dato.
7. Si la pregunta es ambigua, respondé con los datos y sugerí cómo precisarla.
8. No uses emojis ni markdown decorativo."""


# ---------------------------------------------------------------------------
# Mock backend for testing (at module level so tests can import it easily)
# ---------------------------------------------------------------------------

class MockGeminiNLBackend:
    """Used in tests to verify prompt structure without calling the real API."""

    def __init__(self) -> None:
        self.last_system_prompt: str = ""
        self.last_user_message: str = ""
        self.response_text: str = "Respuesta de prueba."
        self.should_raise: bool = False

    def generate(self, system_prompt: str, user_message: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_message = user_message
        if self.should_raise:
            raise RuntimeError("Mock error")
        return self.response_text


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_datos_dict(
    dato_o_comp: "Dato | Comparacion | None",
    tipo: str,
    sugerencias: list[str],
) -> dict:
    """Build the DATOS payload for the Gemini user message."""
    if tipo == "dato" and dato_o_comp is not None:
        dato = dato_o_comp  # type: ignore[assignment]
        return {
            "valor": dato.valor,
            "unidad": dato.unidad,
            "metrica": dato.metrica,
            "etiqueta_humana": dato.etiqueta_humana,
            "agregacion": dato.agregacion,
        }
    if tipo == "comparacion" and dato_o_comp is not None:
        comp = dato_o_comp  # type: ignore[assignment]
        return {
            "eje": comp.eje,
            "items": [
                {"etiqueta": i.etiqueta, "valor": i.valor, "unidad": i.unidad}
                for i in comp.items
            ],
            "ranking": comp.ranking,
        }
    if tipo in ("ood", "sin_datos"):
        return {"sugerencias": sugerencias}
    # error or unknown
    return {}


def _build_dim_dict(intent: "Intent", almacen: Any) -> dict:
    """Load dim_indicadores and extract the relevant row for intent.metrica."""
    metrica = getattr(intent, "metrica", "") or ""
    if not metrica:
        return {}
    try:
        df = almacen.obtener("dim_indicadores")
        row = df[df["campo"] == metrica]
        if row.empty:
            return {}
        r = row.iloc[0]
        result: dict = {}
        for col in ("etiqueta_humana", "descripcion_breve", "direccion_mejor"):
            if col in r.index:
                val = r[col]
                # Convert pandas NA / NaN to None for clean JSON serialization
                try:
                    if isinstance(val, float) and math.isnan(val):
                        result[col] = None
                        continue
                except (TypeError, ValueError):
                    pass
                result[col] = val if val is not None else None
        return result
    except Exception as exc:  # noqa: BLE001
        _logger.debug("No se pudo cargar dim_indicadores: %s", exc)
        return {}


def _build_intent_dict(intent: "Intent") -> dict:
    """Serialize a trimmed version of the intent to avoid huge payloads."""
    fields = ("tabla", "metrica", "filtros_linea", "rango_temporal", "tipo", "es_dominio")
    if hasattr(intent, "model_dump"):
        full = intent.model_dump()
        return {k: full[k] for k in fields if k in full}
    # Fallback for non-Pydantic objects
    result = {}
    for k in fields:
        if hasattr(intent, k):
            result[k] = getattr(intent, k)
    return result


def _build_user_message(
    pregunta: str,
    intent: "Intent",
    dato_o_comp: "Dato | Comparacion | None",
    tipo: str,
    advertencias: list[str],
    sugerencias: list[str],
    almacen: Any,
) -> str:
    """Build the full user message string for Gemini."""
    intent_dict = _build_intent_dict(intent)
    datos_dict = _build_datos_dict(dato_o_comp, tipo, sugerencias)
    dim_dict = _build_dim_dict(intent, almacen)

    advertencias_str = "; ".join(advertencias) if advertencias else "Ninguna"

    return (
        f"PREGUNTA: {pregunta}\n\n"
        f"INTENT: {json.dumps(intent_dict, ensure_ascii=False)}\n\n"
        f"DATOS: {json.dumps(datos_dict, ensure_ascii=False, indent=2)}\n\n"
        f"DIM_INDICADOR: {json.dumps(dim_dict, ensure_ascii=False)}\n\n"
        f"ADVERTENCIAS: {advertencias_str}"
    )


def _llamar_gemini(
    pregunta: str,
    intent: "Intent",
    dato_o_comp: "Dato | Comparacion | None",
    tipo: str,
    advertencias: list[str],
    sugerencias: list[str],
    almacen: Any,
    api_key: str,
    *,
    _backend: MockGeminiNLBackend | None = None,
) -> str:
    """Call Gemini and return the generated text. May raise."""
    user_message = _build_user_message(
        pregunta, intent, dato_o_comp, tipo, advertencias, sugerencias, almacen
    )

    if _backend is not None:
        return _backend.generate(_SYSTEM_PROMPT, user_message)

    from google import genai  # local import — keeps module importable without SDK
    from google.genai import types

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=10_000),  # 10 seconds in ms
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.1,
            max_output_tokens=1024,
            response_mime_type="text/plain",
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    texto = (response.text or "").strip()
    if not texto:
        try:
            finish_reason = response.candidates[0].finish_reason
        except (IndexError, AttributeError):
            finish_reason = "unknown"
        raise ValueError(f"Gemini no devolvió texto (finish_reason={finish_reason!r})")
    return texto


def _extraer_periodo(intent: "Intent") -> tuple[str, str]:
    """Extract periodo_desde / periodo_hasta from intent.rango_temporal."""
    rango = getattr(intent, "rango_temporal", None)
    if rango is None:
        return "", ""
    desde = getattr(rango, "desde", "") or ""
    hasta = getattr(rango, "hasta", "") or ""
    return desde, hasta


def _extraer_filtros(intent: "Intent") -> str:
    """Extract a human-readable filtros string from intent.filtros_linea."""
    lineas = getattr(intent, "filtros_linea", []) or []
    if not lineas:
        return "red"
    return "/".join(lineas)


def _fallback_plantillas(
    tipo: "TipoRespuesta",
    dato_o_comp: "Dato | Comparacion | None",
    advertencias: list[str],
    sugerencias: list[str],
    intent: "Intent",
) -> str:
    """Delegate to motor.plantillas.render with appropriate kwargs."""
    periodo_desde, periodo_hasta = _extraer_periodo(intent)
    filtros = _extraer_filtros(intent)

    if tipo == "dato" and dato_o_comp is not None:
        dato = dato_o_comp  # type: ignore[assignment]
        return plantillas.render(
            "dato",
            metrica=dato.metrica,
            etiqueta_humana=dato.etiqueta_humana,
            valor=dato.valor,
            unidad=dato.unidad,
            agregacion=dato.agregacion,
            periodo_desde=periodo_desde,
            periodo_hasta=periodo_hasta,
            filtros=filtros,
        )
    if tipo == "comparacion" and dato_o_comp is not None:
        comp = dato_o_comp  # type: ignore[assignment]
        # ItemComparacion objects → dicts for plantillas._render_comparacion
        items_dicts = [
            {"etiqueta": i.etiqueta, "valor": i.valor, "unidad": i.unidad}
            for i in comp.items
        ]
        return plantillas.render(
            "comparacion",
            eje=comp.eje,
            items=items_dicts,
            diferencias=comp.diferencias,
            ranking=comp.ranking,
        )
    if tipo == "ood":
        return plantillas.render("ood", sugerencias=sugerencias)
    if tipo == "sin_datos":
        return plantillas.render(
            "sin_datos",
            mensaje="Sin datos para el período solicitado.",
            sugerencias=sugerencias,
        )
    # "error" or fallthrough
    return plantillas.render("error")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generar_nl(
    pregunta: str,
    intent: "Intent",
    dato_o_comp: "Dato | Comparacion | None",
    tipo: "TipoRespuesta",
    advertencias: list[str],
    sugerencias: list[str],
    almacen: Any,
    *,
    sin_llm: bool = False,
) -> tuple[str, str]:
    """Generate a plain-text NL response for the given query result.

    Parameters
    ----------
    pregunta:
        Original user question in Spanish.
    intent:
        Parsed intent (semantica.Intent or compatible object).
    dato_o_comp:
        A Dato, Comparacion, or None depending on *tipo*.
    tipo:
        One of "dato", "comparacion", "ood", "sin_datos", "error".
    advertencias:
        List of warning strings to include in the response.
    sugerencias:
        List of suggestion strings (used for ood/sin_datos).
    almacen:
        Almacen class (or compatible) for loading dim_indicadores.
    sin_llm:
        If True, skip Gemini entirely and use plantillas directly.

    Returns
    -------
    tuple[str, str]
        (texto_nl, fuente_nl) where fuente_nl is one of
        "gemini", "plantilla", or "ninguna".
    """
    # 1. Explicit bypass
    if sin_llm:
        texto = _fallback_plantillas(tipo, dato_o_comp, advertencias, sugerencias, intent)
        return texto, "plantilla"

    # 2. Check API key availability
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        _logger.debug(
            "GEMINI_API_KEY no configurada — usando plantillas para generación NL."
        )
        texto = _fallback_plantillas(tipo, dato_o_comp, advertencias, sugerencias, intent)
        return texto, "plantilla"

    # 3. Try Gemini
    try:
        texto = _llamar_gemini(
            pregunta, intent, dato_o_comp, tipo, advertencias, sugerencias, almacen, api_key
        )
        if not texto:
            _logger.debug("Gemini devolvió texto vacío — usando plantillas.")
            texto = _fallback_plantillas(tipo, dato_o_comp, advertencias, sugerencias, intent)
            return texto, "plantilla"
        return texto, "gemini"
    except Exception as exc:  # noqa: BLE001
        _logger.warning("Error llamando a Gemini para NL: %s — usando plantillas.", exc)
        texto = _fallback_plantillas(tipo, dato_o_comp, advertencias, sugerencias, intent)
        return texto, "plantilla"
