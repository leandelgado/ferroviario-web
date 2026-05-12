"""
Pipeline orchestrator for the railway conversational agent.

The sole public function `responder` accepts a natural-language question,
parses it, validates coverage, executes the appropriate query, generates a
plain-text NL response, and returns a fully-populated `Respuesta` object.
It never raises — all exceptions are caught and converted to error responses.
"""

from __future__ import annotations

import time

from motor.respuesta import Respuesta, Metadata, TipoRespuesta
from motor.almacen import Almacen
from motor.cobertura import validar_temporal, validar_lineas, validar_metrica_granularidad
from motor.ejecutor import ejecutar_simple
from motor.ejecutor_comparacion import ejecutar_comparacion
from motor.generador_nl import generar_nl
from motor.ood import es_probable_ood, construir_sugerencias
import semantica


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def responder(
    pregunta: str,
    *,
    sin_llm_nl: bool = False,
    forzar_reglas: bool = False,
) -> Respuesta:
    """Parse the question and execute the full pipeline. Never raises.

    Parameters
    ----------
    pregunta:
        Natural language question in Spanish.
    sin_llm_nl:
        If True, skip Gemini for NL generation and use templates only.
    forzar_reglas:
        If True, skip the LLM parser and use only the rule-based parser for
        intent extraction.

    Returns
    -------
    Respuesta
        Always returns a Respuesta — tipo="error" when an unrecoverable
        exception occurs.
    """
    t0 = time.monotonic()

    # ------------------------------------------------------------------
    # Step 1: Parse intent
    # ------------------------------------------------------------------
    try:
        if forzar_reglas:
            # Bypass hybrid orchestrator; use rules-only parser directly
            from semantica.parser_reglas import parse as parse_reglas
            resultado_reglas = parse_reglas(pregunta)
            intent = resultado_reglas.intent
        else:
            intent = semantica.parse(pregunta)
    except Exception as e:
        return _error_respuesta(pregunta, str(e), t0)

    try:
        # ------------------------------------------------------------------
        # Step 2: OOD check
        # ------------------------------------------------------------------
        if es_probable_ood(intent):
            return _ood_respuesta(pregunta, intent, t0, sin_llm_nl)

        # ------------------------------------------------------------------
        # Step 3: Validate coverage
        # ------------------------------------------------------------------
        resultado = None
        for validar in [validar_temporal, validar_lineas, validar_metrica_granularidad]:
            resultado = validar(intent, Almacen)
            if not resultado.valido:
                return _sin_datos_respuesta(pregunta, intent, resultado.mensaje, t0, sin_llm_nl)

        # ------------------------------------------------------------------
        # Step 4: Execute query
        # ------------------------------------------------------------------
        advertencias: list[str] = []

        # The last validator (validar_metrica_granularidad) always returns
        # valido=True but may carry a warning in its mensaje.
        if resultado is not None and resultado.mensaje:
            advertencias.append(resultado.mensaje)

        if intent.tipo in ("comparacion_lineas", "comparacion_periodos"):
            dato_o_comp, adv = ejecutar_comparacion(intent, Almacen)
            tipo: TipoRespuesta = "comparacion"
        else:
            dato_o_comp, adv = ejecutar_simple(intent, Almacen)
            tipo = "dato"

        advertencias.extend(adv)

        # ------------------------------------------------------------------
        # Step 5: Generate NL response
        # ------------------------------------------------------------------
        sugerencias: list[str] = []
        texto_nl, fuente_nl = generar_nl(
            pregunta,
            intent,
            dato_o_comp,
            tipo,
            advertencias,
            sugerencias,
            Almacen,
            sin_llm=sin_llm_nl,
        )

        # ------------------------------------------------------------------
        # Step 6: Build and return Respuesta
        # ------------------------------------------------------------------
        elapsed_ms = (time.monotonic() - t0) * 1000
        cob_desde, cob_hasta = Almacen.cobertura(intent.tabla)
        metadata = Metadata(
            tabla=intent.tabla,
            cobertura_desde=cob_desde,
            cobertura_hasta=cob_hasta,
            fuente_nl=fuente_nl,
            tiempo_ms=elapsed_ms,
        )

        dato = dato_o_comp if tipo == "dato" else None
        comparacion = dato_o_comp if tipo == "comparacion" else None

        return Respuesta(
            tipo=tipo,
            texto_nl=texto_nl,
            intent=intent,
            dato=dato,
            comparacion=comparacion,
            advertencias=advertencias,
            metadata=metadata,
        )

    except Exception as e:
        return _error_respuesta(pregunta, str(e), t0, intent=intent)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _ood_respuesta(pregunta: str, intent, t0: float, sin_llm_nl: bool) -> Respuesta:
    """Build an OOD (out-of-domain) Respuesta."""
    sugerencias = construir_sugerencias()
    texto_nl, fuente_nl = generar_nl(
        pregunta, intent, None, "ood", [], sugerencias, Almacen, sin_llm=sin_llm_nl
    )
    elapsed = (time.monotonic() - t0) * 1000
    return Respuesta(
        tipo="ood",
        texto_nl=texto_nl,
        intent=intent,
        sugerencias=sugerencias,
        metadata=Metadata(tabla="", fuente_nl=fuente_nl, tiempo_ms=elapsed),
    )


def _sin_datos_respuesta(
    pregunta: str, intent, mensaje: str, t0: float, sin_llm_nl: bool
) -> Respuesta:
    """Build a sin_datos (no data available) Respuesta."""
    sugerencias = construir_sugerencias()
    texto_nl, fuente_nl = generar_nl(
        pregunta, intent, None, "sin_datos", [], sugerencias, Almacen, sin_llm=sin_llm_nl
    )
    elapsed = (time.monotonic() - t0) * 1000
    return Respuesta(
        tipo="sin_datos",
        texto_nl=texto_nl,
        intent=intent,
        sugerencias=sugerencias,
        advertencias=[mensaje] if mensaje else [],
        metadata=Metadata(
            tabla=getattr(intent, "tabla", ""),
            fuente_nl=fuente_nl,
            tiempo_ms=elapsed,
        ),
    )


def _error_respuesta(
    pregunta: str, mensaje: str, t0: float, intent=None
) -> Respuesta:
    """Build an error Respuesta from an unhandled exception."""
    elapsed = (time.monotonic() - t0) * 1000
    from semantica.intent import Intent as _Intent

    # Use the provided intent or construct a minimal stub
    stub = intent or _Intent(
        metrica="",
        tabla="red_mensual",
        granularidad="red",
        agregacion="sum",
        confianza=0.0,
        origen="reglas",
        es_dominio=False,
    )
    return Respuesta(
        tipo="error",
        texto_nl=f"Ocurrió un error al procesar tu consulta: {mensaje}",
        intent=stub,
        metadata=Metadata(tabla="", fuente_nl="ninguna", tiempo_ms=elapsed),
    )
