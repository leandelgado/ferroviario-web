"""
Unit tests for motor.ood — out-of-domain detection.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.ood import es_probable_ood, construir_sugerencias


def _make_intent(
    es_dominio=True,
    metrica="pax_pagos",
    filtros_linea=None,
    confianza=0.9,
):
    intent = MagicMock()
    intent.es_dominio = es_dominio
    intent.metrica = metrica
    intent.filtros_linea = filtros_linea if filtros_linea is not None else ["Mitre"]
    intent.confianza = confianza
    return intent


class TestEsProbableOod(unittest.TestCase):

    def test_es_dominio_false_es_ood(self):
        """intent.es_dominio=False → es_probable_ood returns True."""
        intent = _make_intent(es_dominio=False)
        self.assertTrue(es_probable_ood(intent))

    def test_baja_confianza_sin_metrica_sin_linea_es_ood(self):
        """Empty metrica, empty filtros_linea, confianza < 0.3 → True."""
        intent = _make_intent(
            es_dominio=True,
            metrica="",
            filtros_linea=[],
            confianza=0.1,
        )
        self.assertTrue(es_probable_ood(intent))

    def test_alta_confianza_no_es_ood(self):
        """es_dominio=True, valid metrica, confianza=0.9 → False."""
        intent = _make_intent(
            es_dominio=True,
            metrica="pax_pagos",
            filtros_linea=["Mitre"],
            confianza=0.9,
        )
        self.assertFalse(es_probable_ood(intent))

    def test_baja_confianza_con_metrica_no_es_ood(self):
        """Low confidence but with a metric specified → not OOD (heuristic requires all conditions)."""
        intent = _make_intent(
            es_dominio=True,
            metrica="pax_pagos",
            filtros_linea=[],
            confianza=0.1,
        )
        # metrica is not empty so the heuristic should NOT trigger
        self.assertFalse(es_probable_ood(intent))

    def test_baja_confianza_con_linea_no_es_ood(self):
        """Low confidence but with line filter → not OOD."""
        intent = _make_intent(
            es_dominio=True,
            metrica="",
            filtros_linea=["Mitre"],
            confianza=0.1,
        )
        self.assertFalse(es_probable_ood(intent))

    def test_confianza_exactamente_0_3_no_es_ood(self):
        """confianza=0.3 is NOT below 0.3 → condition requires < 0.3."""
        intent = _make_intent(
            es_dominio=True,
            metrica="",
            filtros_linea=[],
            confianza=0.3,
        )
        # 0.3 is not < 0.3, so it should NOT be OOD by that rule
        self.assertFalse(es_probable_ood(intent))


class TestConstruirSugerencias(unittest.TestCase):

    def test_sugerencias_son_3(self):
        sugerencias = construir_sugerencias()
        self.assertEqual(len(sugerencias), 3)

    def test_sugerencias_son_strings(self):
        sugerencias = construir_sugerencias()
        for s in sugerencias:
            self.assertIsInstance(s, str)
            self.assertGreater(len(s), 0)


class TestOodNoTocaAlmacen(unittest.TestCase):

    def test_no_toca_almacen_cuando_ood(self):
        """es_probable_ood should NOT call Almacen.obtener."""
        intent = _make_intent(es_dominio=False)
        with patch("motor.almacen.Almacen.obtener") as mock_obtener:
            result = es_probable_ood(intent)
            self.assertTrue(result)
            mock_obtener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
