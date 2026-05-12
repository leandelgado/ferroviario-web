"""
Unit tests for motor.plantillas.render.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.plantillas import render


class TestPlantillas(unittest.TestCase):

    def test_render_dato_simple(self):
        texto = render(
            "dato",
            metrica="pax_pagos",
            etiqueta_humana="Pasajeros con boleto",
            valor=39_515_170.0,
            unidad="pasajeros",
            agregacion="sum",
            periodo_desde="2023-01",
            periodo_hasta="2023-12",
            filtros="Mitre",
        )
        self.assertGreater(len(texto), 0)
        self.assertIsInstance(texto, str)

    def test_render_dato_con_periodo(self):
        texto = render(
            "dato",
            metrica="pax_pagos",
            etiqueta_humana="Pasajeros con boleto",
            valor=1_000_000.0,
            unidad="pasajeros",
            agregacion="sum",
            periodo_desde="2022-01",
            periodo_hasta="2022-12",
            filtros="red",
        )
        # Should include period information
        self.assertIn("2022", texto)

    def test_render_comparacion_lineas(self):
        items = [
            {"etiqueta": "Mitre", "valor": 39_515_170.0, "unidad": "pasajeros"},
            {"etiqueta": "Sarmiento", "valor": 71_549_514.0, "unidad": "pasajeros"},
        ]
        diferencias = [{"entre": ["Mitre", "Sarmiento"], "delta": 32_034_344.0}]
        ranking = ["Sarmiento", "Mitre"]
        texto = render(
            "comparacion",
            eje="linea",
            items=items,
            diferencias=diferencias,
            ranking=ranking,
        )
        self.assertGreater(len(texto), 0)
        # Should mention ranking
        self.assertIn("Sarmiento", texto)

    def test_render_ood(self):
        sugerencias = [
            "¿Cuántos pasajeros transportó el Mitre en 2023?",
            "¿Cuál fue la puntualidad de la red en 2022?",
            "¿Cómo varió la recaudación del Sarmiento?",
        ]
        texto = render("ood", sugerencias=sugerencias)
        self.assertGreater(len(texto), 0)
        # Should contain suggestions text
        self.assertIn("Mitre", texto)

    def test_render_sin_datos(self):
        texto = render(
            "sin_datos",
            mensaje="No hay datos para ese período.",
            sugerencias=["¿Cuántos pasajeros en 2023?"],
        )
        self.assertGreater(len(texto), 0)

    def test_render_error(self):
        texto = render("error")
        self.assertGreater(len(texto), 0)

    def test_render_error_con_mensaje(self):
        texto = render("error", mensaje="Error de conexión.")
        self.assertGreater(len(texto), 0)
        self.assertIn("Error de conexión", texto)

    def test_render_tipo_invalido_raises(self):
        with self.assertRaises((ValueError, KeyError)):
            render("tipo_no_existe")

    def test_render_comparacion_periodos(self):
        items = [
            {"etiqueta": "2022", "valor": 35_000_000.0, "unidad": "pasajeros"},
            {"etiqueta": "2023", "valor": 39_515_170.0, "unidad": "pasajeros"},
        ]
        diferencias = [{"entre": ["2022", "2023"], "delta": 4_515_170.0}]
        ranking = ["2023", "2022"]
        texto = render(
            "comparacion",
            eje="periodo",
            items=items,
            diferencias=diferencias,
            ranking=ranking,
        )
        self.assertGreater(len(texto), 0)


if __name__ == "__main__":
    unittest.main()
