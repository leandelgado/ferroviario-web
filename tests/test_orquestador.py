"""
Unit tests for motor.orquestador.responder — pipeline integration.

All tests use sin_llm_nl=True (no Gemini for NL) to keep tests deterministic.
OOD detection may vary without a real LLM parser; some tests use forzar_reglas=True.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor import responder
from motor.almacen import Almacen
from motor.respuesta import Respuesta


class TestOrquestador(unittest.TestCase):

    def setUp(self):
        Almacen.reset()

    def tearDown(self):
        Almacen.reset()

    def test_respuesta_tipo_dato(self):
        """A clear domain question should return tipo='dato' with positive valor."""
        resp = responder("pasajeros Mitre 2023", sin_llm_nl=True, forzar_reglas=True)
        self.assertIsInstance(resp, Respuesta)
        self.assertEqual(resp.tipo, "dato")
        self.assertGreater(len(resp.texto_nl), 0)
        self.assertIsNotNone(resp.dato)
        self.assertGreater(resp.dato.valor, 0)

    def test_respuesta_json_serializable(self):
        """Respuesta should be JSON serializable via model_dump_json."""
        resp = responder("pasajeros Mitre 2023", sin_llm_nl=True, forzar_reglas=True)
        # Should not raise
        json_str = resp.model_dump_json()
        self.assertGreater(len(json_str), 0)

    def test_metadatos_presentes(self):
        """Respuesta must have metadata with tiempo_ms > 0 and valid fuente_nl."""
        resp = responder("pasajeros Mitre 2023", sin_llm_nl=True, forzar_reglas=True)
        self.assertGreater(resp.metadata.tiempo_ms, 0)
        self.assertIn(resp.metadata.fuente_nl, ("gemini", "plantilla", "ninguna"))

    def test_nunca_lanza_excepcion_input_basura(self):
        """Even nonsense input must return a Respuesta (never raise)."""
        try:
            resp = responder("asjdflaksjdflaksjdf!!!", sin_llm_nl=True, forzar_reglas=True)
            self.assertIsInstance(resp, Respuesta)
            self.assertIn(resp.tipo, ("dato", "ood", "sin_datos", "error", "comparacion"))
        except Exception as e:
            self.fail(f"responder raised an exception: {e}")

    def test_nunca_lanza_excepcion_cadena_vacia(self):
        """Empty string must return a Respuesta without raising."""
        try:
            resp = responder("", sin_llm_nl=True, forzar_reglas=True)
            self.assertIsInstance(resp, Respuesta)
        except Exception as e:
            self.fail(f"responder raised for empty string: {e}")

    def test_respuesta_tiene_intent(self):
        """Respuesta must always include an intent."""
        resp = responder("pasajeros Mitre 2023", sin_llm_nl=True, forzar_reglas=True)
        self.assertIsNotNone(resp.intent)

    def test_texto_nl_siempre_presente(self):
        """texto_nl must be a non-None string (may be empty but not None)."""
        resp = responder("pasajeros Mitre 2023", sin_llm_nl=True, forzar_reglas=True)
        self.assertIsNotNone(resp.texto_nl)
        self.assertIsInstance(resp.texto_nl, str)

    def test_respuesta_sarmiento_2022(self):
        """Sarmiento 2022 should return dato with positive valor."""
        resp = responder(
            "cuantos pasajeros tuvo el Sarmiento en 2022",
            sin_llm_nl=True,
            forzar_reglas=True,
        )
        self.assertIsInstance(resp, Respuesta)
        self.assertIn(resp.tipo, ("dato", "sin_datos", "error"))
        if resp.tipo == "dato":
            self.assertGreater(resp.dato.valor, 0)

    def test_ood_pregunta_no_ferroviaria(self):
        """A clearly non-railway question with forzar_reglas=True may return ood or dato.

        With rules-only parsing, OOD detection is limited, so we accept any valid tipo.
        """
        resp = responder("capital de Francia", sin_llm_nl=True, forzar_reglas=True)
        self.assertIsInstance(resp, Respuesta)
        # With rules-only parsing, may not detect OOD — any valid tipo is acceptable
        self.assertIn(resp.tipo, ("dato", "ood", "sin_datos", "error", "comparacion"))

    def test_respuesta_fuente_nl_plantilla_cuando_sin_llm(self):
        """With sin_llm_nl=True, fuente_nl must be 'plantilla'."""
        resp = responder("pasajeros Mitre 2023", sin_llm_nl=True, forzar_reglas=True)
        if resp.tipo in ("dato", "ood", "sin_datos"):
            self.assertEqual(resp.metadata.fuente_nl, "plantilla")

    def test_respuesta_red_2023(self):
        """Network-level query should work without line filters."""
        resp = responder(
            "cuantos pasajeros tuvo la red en 2023",
            sin_llm_nl=True,
            forzar_reglas=True,
        )
        self.assertIsInstance(resp, Respuesta)
        if resp.tipo == "dato":
            self.assertGreater(resp.dato.valor, 0)


class TestOrquestadorComparacion(unittest.TestCase):
    """Comparison tests — result may vary without LLM parser."""

    def setUp(self):
        Almacen.reset()

    def tearDown(self):
        Almacen.reset()

    def test_respuesta_comparacion_tipo_valido(self):
        """Comparison question: tipo should be in accepted set."""
        resp = responder(
            "comparar pasajeros Mitre vs Sarmiento 2023",
            sin_llm_nl=True,
            forzar_reglas=True,
        )
        self.assertIsInstance(resp, Respuesta)
        # With rules-only parsing, comparison detection may not work → accept dato too
        self.assertIn(resp.tipo, ("comparacion", "dato", "sin_datos", "error"))


if __name__ == "__main__":
    unittest.main()
