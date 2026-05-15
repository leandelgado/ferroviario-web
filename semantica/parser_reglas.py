"""
Rule-based deterministic intent parser for the railway conversational agent.

Applies a step-by-step pipeline to extract a structured Intent from a
Spanish natural-language question, using vocabulary matching (exact + fuzzy)
and a set of deterministic heuristics.
"""

from __future__ import annotations

import logging
import re
from typing import Literal, NamedTuple

from rapidfuzz import fuzz, process as fz_process

from semantica.fechas import extraer_fecha
from semantica.intent import Intent, RangoTemporal
from semantica.normalizacion import normalizar
from semantica.vocabulario import Vocabulario, cargar_vocabulario

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level compiled patterns and constants
# ---------------------------------------------------------------------------

_COMPARACION_KEYWORDS = (
    " vs ", "versus", "comparar", "frente a", " contra ", "diferencia entre"
)

_FERROVIARIO_KEYWORDS = re.compile(
    r'\b(tren(?:es)?|ferro|ffcc|lineas?|estacion(?:es)?|pasajeros?'
    r'|regularidad|puntualidad|amba|cnrt|servicios?|ferrocarril)\b'
)

_ANIO_RE = re.compile(r'\b(?:19|20)\d{2}\b')

# Frases (ya normalizadas — sin tildes) que indican agrupar por año.
_GRUPO_ANIO_KEYWORDS = (
    "por ano",
    "por anio",
    "por cada ano",
    "por cada anio",
    "cada ano",
    "cada anio",
    "anual",
    "anualmente",
    "ano a ano",
    "anio a anio",
    "ano por ano",
    "ano tras ano",
)

# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------

_voc: Vocabulario | None = None


def _get_voc() -> Vocabulario:
    global _voc
    if _voc is None:
        _voc = cargar_vocabulario()
    return _voc


# ---------------------------------------------------------------------------
# Public return type
# ---------------------------------------------------------------------------

class ParseResult(NamedTuple):
    intent: Intent
    requiere_llm: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def _all_ngrams(tokens: list[str]) -> list[str]:
    result: list[str] = []
    for n in range(1, 5):
        result.extend(_ngrams(tokens, n))
    return result


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------

def _extract_metrica(tokens: list[str], voc: Vocabulario) -> tuple[str | None, float]:
    """Return (campo_or_None, confianza)."""
    ngrams = _all_ngrams(tokens)
    sinonimos = voc.metricas_por_sinonimo

    # Exact match first (longest match wins — iterate all, prefer longer ngrams)
    best_exact: str | None = None
    best_exact_len = 0
    for ng in ngrams:
        if ng in sinonimos and len(ng) >= best_exact_len:
            best_exact = ng
            best_exact_len = len(ng)

    if best_exact is not None:
        return sinonimos[best_exact]["campo"], 1.0

    # Fuzzy match — use fuzz.ratio to avoid partial-string false positives
    # fuzz.ratio instead of WRatio: WRatio activates partial-ratio on short n-grams,
    # inflating scores for unrelated short tokens (e.g. "la" matches "tren de la costa" at 90%).
    all_keys = list(sinonimos.keys())
    best_score = 0.0
    best_campo: str | None = None
    for ng in ngrams:
        result = fz_process.extractOne(
            ng, all_keys, scorer=fuzz.ratio, score_cutoff=85
        )
        if result is not None:
            matched_key, score, _ = result
            if score > best_score:
                best_score = score
                best_campo = sinonimos[matched_key]["campo"]

    if best_campo is not None:
        return best_campo, best_score / 100.0

    return None, 0.0


def _extract_lineas(texto_norm: str, voc: Vocabulario) -> tuple[list[str], float]:
    """Return (list_of_canonical_names, confianza)."""
    aliases = voc.aliases_linea
    found: dict[str, str] = {}  # canonical → method ("exact"/"fuzzy")

    # Exact match: check if any alias key appears as a substring in the text
    for alias_norm, canonical in aliases.items():
        if alias_norm in texto_norm:
            found[canonical] = "exact"

    # Fuzzy match over the full alias dictionary using each word window
    # We try the whole normalized text tokens as candidate phrases
    tokens = texto_norm.split()
    alias_keys = list(aliases.keys())

    all_text_ngrams = _all_ngrams(tokens)
    for ng in all_text_ngrams:
        # fuzz.ratio instead of WRatio: WRatio activates partial-ratio on short n-grams,
        # inflating scores for unrelated short tokens (e.g. "la" matches "tren de la costa" at 90%).
        result = fz_process.extractOne(
            ng, alias_keys, scorer=fuzz.ratio, score_cutoff=88
        )
        if result is not None:
            matched_key, _score, _ = result
            canonical = aliases[matched_key]
            if canonical not in found:
                found[canonical] = "fuzzy"

    # Preserve insertion order from the original text order
    # Re-order by first appearance in text
    lineas_ordered: list[str] = []
    seen: set[str] = set()

    # Walk aliases in order of their position in texto_norm
    # Collect (position, canonical) pairs for exact matches
    positions: list[tuple[int, str]] = []
    for alias_norm, canonical in aliases.items():
        if canonical in found:
            pos = texto_norm.find(alias_norm)
            if pos >= 0:
                positions.append((pos, canonical))

    # Sort by position, deduplicate preserving order
    positions.sort(key=lambda x: x[0])
    for _, canonical in positions:
        if canonical not in seen:
            lineas_ordered.append(canonical)
            seen.add(canonical)

    # Add any fuzzy-only results not yet included
    for canonical, method in found.items():
        if canonical not in seen:
            lineas_ordered.append(canonical)
            seen.add(canonical)

    # Confidence: 1.0 if all exact, lower if any fuzzy
    if not lineas_ordered:
        confianza = 1.0  # no lines expected / none found
    elif all(found.get(c, "exact") == "exact" for c in lineas_ordered):
        confianza = 1.0
    else:
        confianza = 0.88  # fuzzy match confidence floor

    return lineas_ordered, confianza


def _extract_servicios(texto_norm: str, voc: Vocabulario) -> list[str]:
    """Return list of matched servicio values."""
    found: list[str] = []
    texto_lower = texto_norm.lower()
    for servicio in voc.servicios:
        if normalizar(servicio) in texto_lower:
            found.append(servicio)
    return found


def _extract_traccion(texto_norm: str, voc: Vocabulario) -> list[str]:
    """Return list of matched tracción canonical values."""
    result = []
    for traccion in voc.tracciones:
        traccion_norm = normalizar(traccion)
        if traccion_norm in texto_norm:
            result.append(traccion)
    return result


def _infer_agregacion(
    texto_norm: str, metrica: str | None, voc: Vocabulario
) -> tuple[Literal["sum", "mean", "max", "min", "none"], list[str]]:
    """Return (agregacion_literal, advertencias)."""
    advertencias: list[str] = []

    # Explicit keyword overrides
    if any(kw in texto_norm for kw in ("cuanto", "cuantos", "cuanta", "cuantas", "total", "suma")):
        return "sum", advertencias
    if any(kw in texto_norm for kw in ("promedio", "media")):
        return "mean", advertencias
    if any(kw in texto_norm for kw in ("maximo", "mayor", "pico", "mejor")):
        return "max", advertencias
    if any(kw in texto_norm for kw in ("minimo", "menor", "peor")):
        return "min", advertencias

    # Default based on metric agregability
    if metrica is None:
        return "sum", advertencias

    # Look up agregable flag
    # Find any synonym row for this campo
    row: dict | None = None
    for syn_row in voc.metricas_por_sinonimo.values():
        if syn_row["campo"] == metrica:
            row = syn_row
            break

    if row is None:
        return "sum", advertencias

    if row.get("agregable", True):
        return "sum", advertencias
    else:
        advertencias.append("métrica no agregable, usando mean")
        return "mean", advertencias


def _detectar_grupo_por(texto_norm: str) -> Literal["año"] | None:
    """Detect temporal grouping keywords. Returns "año" or None.

    Operates on text already passed through normalizar() — accents stripped,
    so we match the unaccented forms ("ano", "anio", "anual").
    """
    for kw in _GRUPO_ANIO_KEYWORDS:
        if kw in texto_norm:
            return "año"
    return None


def _detectar_tipo(
    texto_norm: str,
    lineas: list[str],
    rango_temporal: object,
) -> Literal["simple", "comparacion_lineas", "comparacion_periodos"]:
    """Detect the query type based on comparison keywords and detected entities.

    Args:
        texto_norm: Normalised text.
        lineas: List of canonical line names detected.
        rango_temporal: The rango_temporal result from extraer_fecha (used only
                        for presence check; year detection uses regex directly).

    Returns:
        "simple", "comparacion_lineas", or "comparacion_periodos".
    """
    es_comparacion = any(kw in texto_norm for kw in _COMPARACION_KEYWORDS)

    if not es_comparacion:
        return "simple"

    # Multiple lines detected → comparacion_lineas
    if len(lineas) >= 2:
        return "comparacion_lineas"

    # Multiple distinct years detected → comparacion_periodos
    anios = _ANIO_RE.findall(texto_norm)
    if len(set(anios)) >= 2:
        return "comparacion_periodos"

    # Comparison detected but axis unclear → default to comparacion_lineas
    return "comparacion_lineas"


def _es_dominio(texto_norm: str, metrica: str | None, lineas: list[str]) -> bool:
    """Conservative out-of-domain detection.

    Returns False ONLY when ALL of the following are true:
    - No metric found
    - No lines/services/traction detected
    - None of the ferroviario keywords appear in the text

    When in doubt, returns True (conservative).

    Args:
        texto_norm: Normalised text.
        metrica: Detected metric (None if not found).
        lineas: List of detected line names.

    Returns:
        True if the query is in-domain, False if clearly out-of-domain.
    """
    if metrica:
        return True
    if lineas:
        return True

    if _FERROVIARIO_KEYWORDS.search(texto_norm):
        return True

    return False


def _infer_tabla_y_granularidad(
    filtros_linea: list[str],
    filtros_servicio: list[str],
    filtros_traccion: list[str],
) -> tuple[Literal["red", "linea", "servicio"], Literal["red_mensual", "linea_mensual", "servicio_mensual"]]:
    """Return (granularidad, tabla)."""
    if filtros_servicio or filtros_traccion:
        return "servicio", "servicio_mensual"
    if filtros_linea:
        return "linea", "linea_mensual"
    return "red", "red_mensual"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(pregunta: str) -> ParseResult:
    """
    Apply a deterministic rule-based pipeline to extract an Intent from a
    Spanish railway question.

    Args:
        pregunta: Raw Spanish question (may contain accents, punctuation, etc.)

    Returns:
        ParseResult(intent, requiere_llm)
    """
    voc = _get_voc()

    # Step 1: Normalize
    texto_norm = normalizar(pregunta)
    tokens = texto_norm.split()

    # Step 2: Extract metric
    metrica, confianza_metrica = _extract_metrica(tokens, voc)

    # Step 3: Extract lines
    filtros_linea, confianza_lineas_raw = _extract_lineas(texto_norm, voc)

    # Step 4: Extract servicios / tracción
    filtros_servicio = _extract_servicios(texto_norm, voc)
    filtros_traccion = _extract_traccion(texto_norm, voc)

    # Step 5: Extract dates
    rango_temporal = extraer_fecha(texto_norm)

    # Step 6: Infer aggregation
    agregacion, advertencias = _infer_agregacion(texto_norm, metrica, voc)

    # Step 7: Determine granularity and table
    granularidad, tabla = _infer_tabla_y_granularidad(
        filtros_linea, filtros_servicio, filtros_traccion
    )

    # Step 8: Compute global confidence and requiere_llm
    # If granularidad is "red", no line was expected, so line confidence = 1.0
    confianza_lineas = 1.0 if granularidad == "red" else confianza_lineas_raw

    confianza_global = confianza_metrica * 0.6 + confianza_lineas * 0.4

    requiere_llm = confianza_global < 0.7 or metrica is None

    # Step 9: Detect query type (comparacion_lineas / comparacion_periodos / simple)
    tipo = _detectar_tipo(texto_norm, filtros_linea, rango_temporal)

    # Step 9b: Detect temporal grouping (Etapa 5)
    grupo_por = _detectar_grupo_por(texto_norm)
    if grupo_por == "año" and rango_temporal is None:
        advertencias.append(
            "Se solicitó agrupar por año pero no se detectó un rango temporal; "
            "se usará toda la cobertura disponible."
        )

    # Step 10: Conservative out-of-domain detection
    es_dominio = _es_dominio(texto_norm, metrica, filtros_linea)
    if not es_dominio:
        requiere_llm = True  # LLM gets final say on OOD queries

    intent = Intent(
        metrica=metrica if metrica is not None else "",
        agregacion=agregacion,
        filtros_linea=filtros_linea,
        filtros_servicio=filtros_servicio,
        filtros_traccion=filtros_traccion,
        rango_temporal=rango_temporal,
        granularidad=granularidad,
        tabla=tabla,
        confianza=round(confianza_global, 4),
        origen="reglas",
        advertencias=advertencias,
        es_dominio=es_dominio,
        tipo=tipo,
        grupo_por=grupo_por,
    )

    return ParseResult(intent=intent, requiere_llm=requiere_llm)


# ---------------------------------------------------------------------------
# Inline test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    preguntas = [
        "¿Cuántos pasajeros transportó la línea Mitre en 2023?",
        "Regularidad promedio del Sarmiento en los últimos 3 años",
        "Qué tan puntual fue la red en marzo 2024",
        "Cancelaciones en Belgrano Norte y Urquiza entre 2018 y 2020",
    ]

    for i, pregunta in enumerate(preguntas, 1):
        print(f"\n{'='*70}")
        print(f"Q{i}: {pregunta}")
        print("=" * 70)
        result = parse(pregunta)
        intent = result.intent
        print(f"  metrica          : {intent.metrica!r}")
        print(f"  filtros_linea    : {intent.filtros_linea}")
        rango = intent.rango_temporal
        if rango:
            print(f"  rango_temporal   : desde={rango.desde}  hasta={rango.hasta}")
        else:
            print(f"  rango_temporal   : None")
        print(f"  agregacion       : {intent.agregacion!r}")
        print(f"  granularidad     : {intent.granularidad!r}")
        print(f"  tabla            : {intent.tabla!r}")
        print(f"  confianza        : {intent.confianza}")
        print(f"  advertencias     : {intent.advertencias}")
        print(f"  requiere_llm     : {result.requiere_llm}")
