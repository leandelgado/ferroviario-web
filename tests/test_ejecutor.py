"""
Unit tests for motor.ejecutor.ejecutar_simple.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.almacen import Almacen
from motor.ejecutor import ejecutar_simple


def _make_intent(
    tabla="linea_mensual",
    metrica="pax_pagos",
    filtros_linea=None,
    desde="2023-01",
    hasta="2023-12",
    agregacion="sum",
    tipo="simple",
    confianza=0.9,
    es_dominio=True,
):
    intent = MagicMock()
    intent.tabla = tabla
    intent.metrica = metrica
    intent.filtros_linea = filtros_linea if filtros_linea is not None else []
    intent.agregacion = agregacion
    intent.tipo = tipo
    intent.confianza = confianza
    intent.es_dominio = es_dominio
    intent.rango_temporal = MagicMock()
    intent.rango_temporal.desde = desde
    intent.rango_temporal.hasta = hasta
    return intent


class TestEjecutarSimple(unittest.TestCase):

    def setUp(self):
        Almacen.reset()

    def tearDown(self):
        Almacen.reset()

    def test_happy_path_mitre_2023(self):
        """pax_pagos Mitre 2023 should be approximately 39,515,170 (±5%)."""
        intent = _make_intent(
            tabla="linea_mensual",
            metrica="pax_pagos",
            filtros_linea=["Mitre"],
            desde="2023-01",
            hasta="2023-12",
        )
        dato, advertencias = ejecutar_simple(intent, Almacen)
        expected = 39_515_170
        tolerance = 0.05
        self.assertAlmostEqual(
            dato.valor,
            expected,
            delta=expected * tolerance,
            msg=f"Valor {dato.valor} fuera del ±5% de {expected}",
        )
        self.assertEqual(dato.metrica, "pax_pagos")

    def test_ratio_recalculado_regularidad_absoluta(self):
        """regularidad_absoluta should be recalculated from components, result between 0 and 1."""
        intent = _make_intent(
            tabla="linea_mensual",
            metrica="regularidad_absoluta",
            filtros_linea=["Mitre"],
            desde="2023-01",
            hasta="2023-12",
        )
        dato, _ = ejecutar_simple(intent, Almacen)
        self.assertGreaterEqual(dato.valor, 0.0)
        self.assertLessEqual(dato.valor, 1.0)
        self.assertEqual(dato.agregacion, "ratio_recalculado")

    def test_non_aggregable_sum_forces_mean(self):
        """A non-aggregable metric with agregacion='sum' should trigger a warning and use mean."""
        # Find a non-aggregable, non-ratio metric from dim_indicadores
        dim = Almacen.obtener("dim_indicadores")
        from motor.ejecutor import _FORMULAS_RATIOS

        non_agg = dim[(dim["agregable"] == False) & (~dim["campo"].isin(_FORMULAS_RATIOS))]  # noqa: E712
        if non_agg.empty:
            self.skipTest("No hay métricas no-agregables no-ratio en dim_indicadores")

        metrica = non_agg.iloc[0]["campo"]
        intent = _make_intent(
            tabla="linea_mensual",
            metrica=metrica,
            filtros_linea=["Mitre"],
            desde="2023-01",
            hasta="2023-12",
            agregacion="sum",
        )
        dato, advertencias = ejecutar_simple(intent, Almacen)
        adv_text = " ".join(advertencias).lower()
        self.assertTrue(
            "mean" in adv_text or "promedio" in adv_text,
            f"Se esperaba advertencia sobre promedio, got: {advertencias}",
        )

    def test_filtros_vacios_devuelve_red(self):
        """No line filters with red_mensual should return a valid Dato."""
        intent = _make_intent(
            tabla="red_mensual",
            metrica="pax_pagos",
            filtros_linea=[],
            desde="2023-01",
            hasta="2023-12",
        )
        dato, _ = ejecutar_simple(intent, Almacen)
        self.assertIsNotNone(dato)
        self.assertGreater(dato.valor, 0)

    def test_filtros_linea_en_tabla_sin_columna_linea(self):
        """Applying line filters to red_mensual (no 'linea' column) should warn."""
        # Use a MagicMock that bypasses Pydantic validation for this test
        intent = MagicMock()
        intent.tabla = "red_mensual"
        intent.metrica = "pax_pagos"
        intent.filtros_linea = ["Mitre"]
        intent.agregacion = "sum"
        intent.rango_temporal = MagicMock()
        intent.rango_temporal.desde = "2023-01"
        intent.rango_temporal.hasta = "2023-12"

        dato, advertencias = ejecutar_simple(intent, Almacen)
        adv_text = " ".join(advertencias).lower()
        self.assertIn("linea", adv_text)

    def test_sin_datos_raises_value_error(self):
        """Non-existent line in filter should raise ValueError."""
        intent = _make_intent(
            tabla="linea_mensual",
            metrica="pax_pagos",
            filtros_linea=["LineaQueNoExisteJamas"],
            desde="2023-01",
            hasta="2023-12",
        )
        with self.assertRaises(ValueError) as ctx:
            ejecutar_simple(intent, Almacen)
        self.assertIn("Sin datos", str(ctx.exception))

    def test_metrica_invalida_raises_value_error(self):
        """Non-existent metric column should raise ValueError."""
        intent = _make_intent(
            tabla="linea_mensual",
            metrica="campo_inexistente_xyz",
            filtros_linea=["Mitre"],
            desde="2023-01",
            hasta="2023-12",
        )
        with self.assertRaises(ValueError):
            ejecutar_simple(intent, Almacen)


if __name__ == "__main__":
    unittest.main()
