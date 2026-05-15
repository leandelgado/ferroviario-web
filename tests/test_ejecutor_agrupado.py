"""
Unit tests for motor.ejecutor_agrupado.ejecutar_agrupado.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.almacen import Almacen
from motor.ejecutor import ejecutar_simple
from motor.ejecutor_agrupado import ejecutar_agrupado


def _intent(
    *,
    tabla="linea_mensual",
    metrica="pax_pagos",
    filtros_linea=None,
    desde="2018-01",
    hasta="2020-12",
    agregacion="sum",
    es_dominio=True,
    confianza=0.9,
):
    i = MagicMock()
    i.tabla = tabla
    i.metrica = metrica
    i.filtros_linea = filtros_linea if filtros_linea is not None else []
    i.agregacion = agregacion
    i.confianza = confianza
    i.es_dominio = es_dominio
    i.tipo = "simple"
    i.grupo_por = "año"
    i.rango_temporal = MagicMock(desde=desde, hasta=hasta)
    return i


def test_monoline_returns_one_item_per_year():
    intent = _intent(filtros_linea=["Urquiza"], desde="2018-01", hasta="2020-12")
    comp, _adv = ejecutar_agrupado(intent, Almacen)

    assert comp.eje == "periodo"
    etiquetas = [it.etiqueta for it in comp.items]
    assert etiquetas == ["2018", "2019", "2020"]
    for it in comp.items:
        assert it.valor > 0
        assert it.unidad == "pasajeros"


def test_monoline_sum_matches_simple_executor():
    """Suma de los items por año ≈ resultado del mismo rango sin agrupar."""
    intent_g = _intent(filtros_linea=["Urquiza"], desde="2018-01", hasta="2020-12")
    intent_s = _intent(filtros_linea=["Urquiza"], desde="2018-01", hasta="2020-12")
    intent_s.grupo_por = None

    comp, _ = ejecutar_agrupado(intent_g, Almacen)
    dato, _ = ejecutar_simple(intent_s, Almacen)

    total_agrupado = sum(it.valor for it in comp.items)
    assert total_agrupado == pytest.approx(dato.valor, rel=1e-6)


def test_multilinea_returns_cartesian_year_x_line():
    intent = _intent(
        metrica="trenes_cancelados",
        filtros_linea=["Mitre", "Sarmiento"],
        desde="2018-01",
        hasta="2020-12",
    )
    comp, _ = ejecutar_agrupado(intent, Almacen)
    etiquetas = [it.etiqueta for it in comp.items]
    assert etiquetas == [
        "Mitre 2018", "Mitre 2019", "Mitre 2020",
        "Sarmiento 2018", "Sarmiento 2019", "Sarmiento 2020",
    ]
    assert len(comp.items) == 6


def test_ratio_metric_uses_components_not_mean():
    """Para regularidad_relativa, cada año debe recalcularse a partir de los
    componentes (puntuales/corridos), no como media de los ratios mensuales."""
    intent = _intent(
        metrica="regularidad_relativa",
        filtros_linea=["Mitre"],
        desde="2018-01",
        hasta="2018-12",
    )
    comp, _ = ejecutar_agrupado(intent, Almacen)
    assert len(comp.items) == 1
    valor = comp.items[0].valor
    assert 0 <= valor <= 1

    # Sanity: debe coincidir con la suma de puntuales / suma de corridos del año
    df = Almacen.obtener("linea_mensual")
    df = df[
        (df["linea"] == "Mitre")
        & (df["periodo"] >= "2018-01")
        & (df["periodo"] <= "2018-12")
    ]
    esperado = df["trenes_puntuales"].sum() / df["trenes_corridos"].sum()
    assert valor == pytest.approx(esperado, rel=1e-6)


def test_sin_datos_raises():
    """Rango fuera de la cobertura → ValueError."""
    intent = _intent(filtros_linea=["Urquiza"], desde="1985-01", hasta="1985-12")
    with pytest.raises(ValueError, match="Sin datos"):
        ejecutar_agrupado(intent, Almacen)
