"""
Hybrid orchestrator for the railway conversational agent intent parser.

Combines rule-based and LLM-based intent parsing, falling back to LLM when
rule-based confidence is low or metric extraction fails.

Public API
----------
parse(pregunta, *, forzar_llm=False, llm_backend=None) -> Intent
"""

from __future__ import annotations

import logging
from typing import Optional

from semantica.intent import Intent
from semantica.parser_llm import LLMBackend, parse as parse_llm
from semantica.parser_reglas import parse as parse_reglas

_logger = logging.getLogger(__name__)


def _merge(intent_reglas: Intent, intent_llm: Intent) -> Intent:
    """Merge rule-based and LLM results, preferring LLM with fallback to rules.

    Strategy:
    1. Start with intent_llm as the base (LLM is more capable)
    2. For fields where rule-based parser had high confidence (> 0.7),
       either value works — LLM wins ties
    3. Set origen = "hibrido"
    4. Combine advertencias from both parsers
    5. Set confianza as the max of the two
    6. If rules-parser detected es_dominio=False, preserve it — only the rules
       parser performs OOD detection; the LLM (or StubBackend) always defaults
       to es_dominio=True, which would silently override a valid OOD signal.

    Args:
        intent_reglas: Intent from rule-based parser with origen="reglas"
        intent_llm: Intent from LLM parser with origen="llm"

    Returns:
        Merged Intent with origen="hibrido" and combined quality signals
    """
    combined_advertencias = list(
        dict.fromkeys(intent_reglas.advertencias + intent_llm.advertencias)
    )
    confianza = max(intent_reglas.confianza, intent_llm.confianza)

    # If the rules parser detected an out-of-domain query, preserve that signal.
    # The LLM defaults to es_dominio=True and would otherwise silently mask OOD.
    es_dominio = intent_llm.es_dominio and intent_reglas.es_dominio

    return intent_llm.model_copy(
        update={
            "origen": "hibrido",
            "advertencias": combined_advertencias,
            "confianza": confianza,
            "es_dominio": es_dominio,
        }
    )


def parse(
    pregunta: str,
    *,
    forzar_llm: bool = False,
    llm_backend: Optional[LLMBackend] = None,
) -> Intent:
    """Parse a Spanish question about the Argentine AMBA railway system.

    Uses a hybrid approach: applies the rule-based parser first, falling back
    to LLM if confidence is low or metric extraction fails.

    Hybrid logic:
    - If forzar_llm is True: skip rules, go directly to LLM
    - Otherwise: run rule-based parser
      - If confidence >= 0.7 and metric found: return rule-based result
      - Otherwise: call LLM and merge with rule-based result

    Args:
        pregunta: Natural language question in Spanish.
        forzar_llm: Skip rule-based parser and go directly to LLM. Useful
                    for testing LLM fallback path.
        llm_backend: Custom LLM backend instance. Defaults to GeminiBackend
                     if GEMINI_API_KEY is set, else StubBackend.

    Returns:
        Intent with metrica, filtros_linea, filtros_servicio, filtros_traccion,
        rango_temporal, agregacion, tabla, granularidad, confianza, origen,
        and advertencias.

        origen is one of:
        - "reglas" (rule-based only, high confidence)
        - "llm" (LLM fallback, forced via forzar_llm)
        - "hibrido" (both parsers used, merged)
    """
    if forzar_llm:
        _logger.debug("forzar_llm=True, saltando parser de reglas")
        intent = parse_llm(pregunta, backend=llm_backend)
        return intent

    # Run rule-based parser
    result_reglas = parse_reglas(pregunta)

    # If confidence is high and metric was found, return rule-based result
    if not result_reglas.requiere_llm:
        _logger.debug(
            "Parser de reglas: confianza=%.3f, metrica=%r → return reglas",
            result_reglas.intent.confianza,
            result_reglas.intent.metrica,
        )
        return result_reglas.intent

    # Confidence is low or metric missing → fall back to LLM and merge
    _logger.debug(
        "Parser de reglas: confianza=%.3f, metrica=%r → requiere_llm=True",
        result_reglas.intent.confianza,
        result_reglas.intent.metrica,
    )
    intent_llm = parse_llm(pregunta, hint=result_reglas.intent, backend=llm_backend)
    merged = _merge(result_reglas.intent, intent_llm)

    _logger.debug(
        "Merged: origen=hibrido, confianza=%.3f, metrica=%r",
        merged.confianza,
        merged.metrica,
    )
    return merged
