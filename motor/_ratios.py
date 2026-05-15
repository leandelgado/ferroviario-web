"""
Ratio metrics shared across executors.

For these metrics, mean() is meaningless — they must be recalculated from
numerator and denominator columns. Centralised here so simple, comparison
and grouped executors stay in sync.
"""

from __future__ import annotations

FORMULAS_RATIOS: dict[str, tuple[str, str]] = {
    "regularidad_absoluta": ("trenes_puntuales", "trenes_programados"),
    "regularidad_relativa": ("trenes_puntuales", "trenes_corridos"),
    "cumplimiento_programa": ("trenes_corridos", "trenes_programados"),
    "tasa_cancelacion": ("trenes_cancelados", "trenes_programados"),
    "tarifa_media_pesos": ("recaudacion_pesos", "pax_pagos"),
}
