"""
Vocabulary loader module for the railway conversational agent.

Loads and exposes a structured vocabulary (Vocabulario) built from the
processed parquet files in data/processed/. The vocabulary is built once
and cached as a module-level singleton.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from semantica.normalizacion import normalizar


_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent / "data" / "processed"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Vocabulario:
    """Structured vocabulary extracted from the railway dimension tables."""

    # synonym → row dict for every metric
    metricas_por_sinonimo: dict[str, dict] = field(default_factory=dict)

    # Canonical line names as stored in dim_lineas.parquet
    lineas_canonicas: list[str] = field(default_factory=list)

    # normalized_alias → canonical_linea_name
    aliases_linea: dict[str, str] = field(default_factory=dict)

    # Unique service names from servicio_mensual.parquet
    servicios: set[str] = field(default_factory=set)

    # Unique traction types from servicio_mensual.parquet
    tracciones: set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------

_vocabulario: Optional[Vocabulario] = None


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------

def _build_metricas(df: pd.DataFrame) -> dict[str, dict]:
    """
    Build the metricas_por_sinonimo mapping from dim_indicadores.

    For every row, the following are used as synonym keys:
      - Each entry in the ``sinonimos`` JSON array
      - The ``campo`` value itself
      - The ``etiqueta_humana`` value

    All keys are normalized before being stored.
    """
    output_fields = [
        "campo",
        "etiqueta_humana",
        "descripcion_breve",
        "unidad",
        "agregable",
        "direccion_mejor",
        "granularidad_minima",
    ]

    result: dict[str, dict] = {}

    for _, row in df.iterrows():
        row_dict = {col: row[col] for col in output_fields}

        # Collect all synonyms for this row
        raw_synonyms: list[str] = []

        # 1. JSON array from the sinonimos column
        sinonimos_raw = row.get("sinonimos", "[]")
        if isinstance(sinonimos_raw, str) and sinonimos_raw.strip():
            try:
                parsed = json.loads(sinonimos_raw)
                if isinstance(parsed, list):
                    raw_synonyms.extend(
                        str(s).replace("_", " ").replace("-", " ") for s in parsed
                    )
            except json.JSONDecodeError:
                pass

        # 2. campo itself as an implicit synonym
        if row.get("campo"):
            raw_synonyms.append(str(row["campo"]).replace("_", " "))

        # 3. etiqueta_humana as an implicit synonym
        if row.get("etiqueta_humana"):
            raw_synonyms.append(str(row["etiqueta_humana"]))

        # Normalize and store (last writer wins for duplicates)
        for syn in raw_synonyms:
            normalized_key = normalizar(syn)
            if normalized_key:
                result[normalized_key] = row_dict.copy()

    return result


def _build_aliases_linea(lineas_canonicas: list[str]) -> dict[str, str]:
    """
    Build the aliases_linea mapping.

    Starts with every canonical name (normalized → canonical) and then
    adds hardcoded aliases for common alternative spellings.
    """
    aliases: dict[str, str] = {}

    # Canonical names as their own aliases
    for linea in lineas_canonicas:
        aliases[normalizar(linea)] = linea

    # Hardcoded aliases
    hardcoded: dict[str, str] = {
        # Mitre
        "mitre": "Mitre",
        "fc mitre": "Mitre",
        "linea mitre": "Mitre",
        "ferrocarril mitre": "Mitre",
        # Sarmiento
        "sarmiento": "Sarmiento",
        "fc sarmiento": "Sarmiento",
        "linea sarmiento": "Sarmiento",
        # San Martín
        "san martin": "San Martín",
        "fc san martin": "San Martín",
        "linea san martin": "San Martín",
        # Roca
        "roca": "Roca",
        "fc roca": "Roca",
        "linea roca": "Roca",
        "ferrocarril roca": "Roca",
        # Belgrano Norte
        "belgrano norte": "Belgrano Norte",
        "bn": "Belgrano Norte",
        # Belgrano Sur
        "belgrano sur": "Belgrano Sur",
        "bs": "Belgrano Sur",
        # Urquiza
        "urquiza": "Urquiza",
        "fc urquiza": "Urquiza",
        "linea urquiza": "Urquiza",
        # Tren de la Costa
        "tren de la costa": "Tren de la Costa",
        "costa": "Tren de la Costa",
        "tdc": "Tren de la Costa",
    }

    for alias, canonical in hardcoded.items():
        aliases[normalizar(alias)] = canonical

    return aliases


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cargar_vocabulario() -> Vocabulario:
    """
    Return the singleton Vocabulario, building it on the first call.

    Reads:
      - data/processed/dim_indicadores.parquet  → metricas_por_sinonimo
      - data/processed/dim_lineas.parquet       → lineas_canonicas, aliases_linea
      - data/processed/servicio_mensual.parquet → servicios, tracciones
    """
    global _vocabulario

    if _vocabulario is not None:
        return _vocabulario

    try:
        # --- dim_indicadores ---
        df_indicadores = pd.read_parquet(_DATA_DIR / "dim_indicadores.parquet")
        metricas_por_sinonimo = _build_metricas(df_indicadores)

        # --- dim_lineas ---
        df_lineas = pd.read_parquet(_DATA_DIR / "dim_lineas.parquet")
        lineas_canonicas: list[str] = df_lineas["linea"].tolist()
        aliases_linea = _build_aliases_linea(lineas_canonicas)

        # --- servicio_mensual ---
        df_servicio = pd.read_parquet(_DATA_DIR / "servicio_mensual.parquet")
        servicios: set[str] = set(df_servicio["servicio"].dropna().unique().tolist())
        tracciones: set[str] = set(df_servicio["tipo_traccion"].dropna().unique().tolist())

        _vocabulario = Vocabulario(
            metricas_por_sinonimo=metricas_por_sinonimo,
            lineas_canonicas=lineas_canonicas,
            aliases_linea=aliases_linea,
            servicios=servicios,
            tracciones=tracciones,
        )

        _logger.info(
            "Vocabulario cargado: %d sinónimos, %d líneas",
            len(_vocabulario.metricas_por_sinonimo),
            len(_vocabulario.lineas_canonicas),
        )

        return _vocabulario
    except Exception as e:
        raise RuntimeError(
            f"No se pudo cargar el vocabulario desde {_DATA_DIR}. "
            f"Verificar que los parquets de data/processed/ estén presentes. "
            f"Error original: {e}"
        ) from e


def resetear_vocabulario() -> None:
    """Clear the singleton so it is rebuilt on the next call to cargar_vocabulario()."""
    global _vocabulario
    _vocabulario = None
