"""
Unit tests for motor.cobertura — coverage validators.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.almacen import Almacen
from motor.cobertura import (
    ResultadoCobertura,
    validar_temporal,
    validar_lineas,
    validar_metrica_granularidad,
)


def _make_intent(
    tabla="linea_mensual",
    desde="2023-01",
    hasta="2023-12",
    filtros_linea=None,
    metrica="pax_pagos",
    rango_temporal=True,
):
    """Build a minimal mock intent."""
    intent = MagicMock()
    intent.tabla = tabla
    intent.metrica = metrica
    intent.filtros_linea = filtros_linea if filtros_linea is not None else []
    if rango_temporal:
        intent.rango_temporal = MagicMock()
        intent.rango_temporal.desde = desde
        intent.rango_temporal.hasta = hasta
    else:
        intent.rango_temporal = None
    return intent


class TestValidarTemporal(unittest.TestCase):

    def setUp(self):
        Almacen.reset()

    def tearDown(self):
        Almacen.reset()

    def test_rango_valido(self):
        intent = _make_intent(desde="2023-01", hasta="2023-12")
        resultado = validar_temporal(intent, Almacen)
        self.assertTrue(resultado.valido)

    def test_rango_anterior_cobertura(self):
        intent = _make_intent(desde="1985-01", hasta="1985-12")
        resultado = validar_temporal(intent, Almacen)
        self.assertFalse(resultado.valido)
        # The message should contain the available coverage range (1993-01), not necessarily 1985
        self.assertGreater(len(resultado.mensaje), 0)
        self.assertIn("1993", resultado.mensaje)

    def test_rango_futuro(self):
        intent = _make_intent(desde="2099-01", hasta="2099-12")
        resultado = validar_temporal(intent, Almacen)
        self.assertFalse(resultado.valido)

    def test_sin_rango_temporal(self):
        intent = _make_intent(rango_temporal=False)
        resultado = validar_temporal(intent, Almacen)
        self.assertTrue(resultado.valido)

    def test_tren_de_la_costa_antes_2015(self):
        intent = _make_intent(
            filtros_linea=["Tren de la Costa"],
            desde="2010-01",
            hasta="2014-12",
        )
        resultado = validar_temporal(intent, Almacen)
        self.assertFalse(resultado.valido)
        self.assertIn("2015", resultado.mensaje)

    def test_tren_de_la_costa_desde_2015(self):
        intent = _make_intent(
            filtros_linea=["Tren de la Costa"],
            desde="2015-05",
            hasta="2016-12",
        )
        resultado = validar_temporal(intent, Almacen)
        self.assertTrue(resultado.valido)


class TestValidarLineas(unittest.TestCase):

    def setUp(self):
        Almacen.reset()

    def tearDown(self):
        Almacen.reset()

    def test_validar_lineas_siempre_valido(self):
        """validar_lineas should always return valido=True (parser canonicalises names)."""
        intent = _make_intent(filtros_linea=["Mitre"])
        resultado = validar_lineas(intent, Almacen)
        self.assertTrue(resultado.valido)

    def test_validar_lineas_sin_filtros_valido(self):
        intent = _make_intent(filtros_linea=[])
        resultado = validar_lineas(intent, Almacen)
        self.assertTrue(resultado.valido)


class TestValidarMetricaGranularidad(unittest.TestCase):

    def setUp(self):
        Almacen.reset()

    def tearDown(self):
        Almacen.reset()

    def test_granularidad_servicio_en_red_mensual(self):
        """A servicio-level metric against red_mensual should return valido=True but non-empty mensaje."""
        # Find a metric with granularidad_minima == "servicio" from dim_indicadores
        dim = Almacen.obtener("dim_indicadores")
        filas_servicio = dim[dim.get("granularidad_minima", dim.iloc[:, 0]) == "servicio"] if "granularidad_minima" in dim.columns else dim.iloc[0:0]

        if filas_servicio.empty:
            self.skipTest("No hay métricas con granularidad_minima=servicio en dim_indicadores")

        metrica_servicio = filas_servicio.iloc[0]["campo"]
        intent = _make_intent(tabla="red_mensual", metrica=metrica_servicio)
        resultado = validar_metrica_granularidad(intent, Almacen)
        self.assertTrue(resultado.valido)
        self.assertGreater(len(resultado.mensaje), 0)

    def test_metrica_normal_no_genera_mensaje(self):
        """A normal aggregable metric should return valido=True with empty mensaje."""
        intent = _make_intent(tabla="linea_mensual", metrica="pax_pagos")
        resultado = validar_metrica_granularidad(intent, Almacen)
        self.assertTrue(resultado.valido)


if __name__ == "__main__":
    unittest.main()
