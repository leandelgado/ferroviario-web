"""
Unit tests for motor.ejecutor_comparacion.ejecutar_comparacion.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.almacen import Almacen
from motor.ejecutor_comparacion import ejecutar_comparacion
from semantica.intent import RangoTemporal


def _make_comparacion_lineas_intent(
    metrica="pax_pagos",
    filtros_linea=None,
    desde="2023-01",
    hasta="2023-12",
    tabla="linea_mensual",
):
    intent = MagicMock()
    intent.tipo = "comparacion_lineas"
    intent.tabla = tabla
    intent.metrica = metrica
    intent.filtros_linea = filtros_linea if filtros_linea is not None else []
    intent.rango_temporal = MagicMock()
    intent.rango_temporal.desde = desde
    intent.rango_temporal.hasta = hasta
    intent.rangos_temporales = []
    return intent


def _make_comparacion_periodos_intent(
    metrica="pax_pagos",
    filtros_linea=None,
    tabla="linea_mensual",
    rangos_temporales=None,
):
    intent = MagicMock()
    intent.tipo = "comparacion_periodos"
    intent.tabla = tabla
    intent.metrica = metrica
    intent.filtros_linea = filtros_linea if filtros_linea is not None else []
    intent.rango_temporal = None
    intent.rangos_temporales = rangos_temporales or []
    return intent


class TestEjecutarComparacionLineas(unittest.TestCase):

    def setUp(self):
        Almacen.reset()

    def tearDown(self):
        Almacen.reset()

    def test_comparacion_lineas_mitre_sarmiento(self):
        """pax_pagos 2023 Mitre vs Sarmiento: returns Comparacion with eje='linea', 2 items."""
        intent = _make_comparacion_lineas_intent(
            metrica="pax_pagos",
            filtros_linea=["Mitre", "Sarmiento"],
            desde="2023-01",
            hasta="2023-12",
        )
        comparacion, _ = ejecutar_comparacion(intent, Almacen)
        self.assertEqual(comparacion.eje, "linea")
        self.assertEqual(len(comparacion.items), 2)
        etiquetas = {i.etiqueta for i in comparacion.items}
        self.assertIn("Mitre", etiquetas)
        self.assertIn("Sarmiento", etiquetas)
        # C(2,2)=1 diferencia pair
        self.assertEqual(len(comparacion.diferencias), 1)
        # Ranking should have 2 entries
        self.assertEqual(len(comparacion.ranking), 2)

    def test_ranking_direccion_menor_tasa_cancelacion(self):
        """tasa_cancelacion (direccion_mejor='menor'): line with LOWEST rate should be first in ranking."""
        intent = _make_comparacion_lineas_intent(
            metrica="tasa_cancelacion",
            filtros_linea=["Mitre", "Sarmiento"],
            desde="2023-01",
            hasta="2023-12",
        )
        comparacion, _ = ejecutar_comparacion(intent, Almacen)
        self.assertEqual(len(comparacion.items), 2)
        # With direccion_mejor='menor', items are sorted ascending (lowest first)
        valores = [i.valor for i in comparacion.items]
        self.assertEqual(valores, sorted(valores))
        # ranking[0] should be the line with the lowest cancellation rate
        item_menor = min(comparacion.items, key=lambda x: x.valor)
        self.assertEqual(comparacion.ranking[0], item_menor.etiqueta)

    def test_n_lineas_en_un_periodo_3_items(self):
        """3 lines in 2023: 3 items, C(3,2)=3 diferencias."""
        intent = _make_comparacion_lineas_intent(
            metrica="pax_pagos",
            filtros_linea=["Mitre", "Sarmiento", "Roca"],
            desde="2023-01",
            hasta="2023-12",
        )
        comparacion, _ = ejecutar_comparacion(intent, Almacen)
        self.assertEqual(len(comparacion.items), 3)
        self.assertEqual(len(comparacion.diferencias), 3)  # C(3,2) = 3

    def test_tabla_sin_columna_linea_raises(self):
        """comparacion_lineas on red_mensual (no 'linea' column) should raise ValueError."""
        intent = MagicMock()
        intent.tipo = "comparacion_lineas"
        intent.tabla = "red_mensual"
        intent.metrica = "pax_pagos"
        intent.filtros_linea = []
        intent.rango_temporal = MagicMock()
        intent.rango_temporal.desde = "2023-01"
        intent.rango_temporal.hasta = "2023-12"
        intent.rangos_temporales = []

        with self.assertRaises(ValueError):
            ejecutar_comparacion(intent, Almacen)


class TestEjecutarComparacionPeriodos(unittest.TestCase):

    def setUp(self):
        Almacen.reset()

    def tearDown(self):
        Almacen.reset()

    def test_comparacion_periodos_dos_anios(self):
        """comparacion_periodos 2022 vs 2023: 2 items in Comparacion, eje='periodo'."""
        rango1 = RangoTemporal(desde="2022-01", hasta="2022-12", etiqueta="2022")
        rango2 = RangoTemporal(desde="2023-01", hasta="2023-12", etiqueta="2023")
        intent = _make_comparacion_periodos_intent(
            metrica="pax_pagos",
            filtros_linea=["Mitre"],
            rangos_temporales=[rango1, rango2],
        )
        comparacion, _ = ejecutar_comparacion(intent, Almacen)
        self.assertEqual(comparacion.eje, "periodo")
        self.assertEqual(len(comparacion.items), 2)
        etiquetas = {i.etiqueta for i in comparacion.items}
        self.assertIn("2022", etiquetas)
        self.assertIn("2023", etiquetas)


if __name__ == "__main__":
    unittest.main()
