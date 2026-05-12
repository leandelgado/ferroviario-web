"""
Unit tests for motor.generador_nl — NL response generator.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.almacen import Almacen
from motor.generador_nl import generar_nl, _llamar_gemini, MockGeminiNLBackend
from motor.respuesta import Dato


def _make_dato():
    return Dato(
        metrica="pax_pagos",
        etiqueta_humana="Pasajeros con boleto",
        unidad="pasajeros",
        valor=39_515_170.0,
        agregacion="sum",
        filas_detalle=[],
    )


def _make_intent(metrica="pax_pagos", filtros_linea=None, desde="2023-01", hasta="2023-12"):
    intent = MagicMock()
    intent.tabla = "linea_mensual"
    intent.metrica = metrica
    intent.filtros_linea = filtros_linea or ["Mitre"]
    intent.es_dominio = True
    intent.tipo = "simple"
    rango = MagicMock()
    rango.desde = desde
    rango.hasta = hasta
    intent.rango_temporal = rango
    if hasattr(intent, "model_dump"):
        intent.model_dump.return_value = {
            "tabla": "linea_mensual",
            "metrica": metrica,
            "filtros_linea": filtros_linea or ["Mitre"],
            "rango_temporal": {"desde": desde, "hasta": hasta},
            "tipo": "simple",
            "es_dominio": True,
        }
    return intent


class TestGeneradorNL(unittest.TestCase):

    def setUp(self):
        Almacen.reset()

    def tearDown(self):
        Almacen.reset()

    def test_sin_llm_usa_plantilla(self):
        """sin_llm=True should return fuente='plantilla' with non-empty text."""
        intent = _make_intent()
        dato = _make_dato()
        texto, fuente = generar_nl(
            "¿Cuántos pasajeros tuvo Mitre en 2023?",
            intent,
            dato,
            "dato",
            [],
            [],
            Almacen,
            sin_llm=True,
        )
        self.assertEqual(fuente, "plantilla")
        self.assertGreater(len(texto), 0)

    def test_sin_api_key_usa_plantilla(self):
        """No GEMINI_API_KEY → fuente='plantilla'."""
        original_gemini = os.environ.pop("GEMINI_API_KEY", None)
        original_google = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            intent = _make_intent()
            dato = _make_dato()
            texto, fuente = generar_nl(
                "¿Cuántos pasajeros tuvo Mitre en 2023?",
                intent,
                dato,
                "dato",
                [],
                [],
                Almacen,
                sin_llm=False,
            )
            self.assertEqual(fuente, "plantilla")
            self.assertGreater(len(texto), 0)
        finally:
            if original_gemini is not None:
                os.environ["GEMINI_API_KEY"] = original_gemini
            if original_google is not None:
                os.environ["GOOGLE_API_KEY"] = original_google

    def test_mock_backend_captura_prompt(self):
        """Mock backend captures user message containing PREGUNTA and DATOS."""
        mock = MockGeminiNLBackend()
        intent = _make_intent()
        dato = _make_dato()
        _llamar_gemini(
            "¿Cuántos pasajeros?",
            intent,
            dato,
            "dato",
            [],
            [],
            Almacen,
            "fake-key",
            _backend=mock,
        )
        self.assertIn("PREGUNTA", mock.last_user_message)
        self.assertIn("DATOS", mock.last_user_message)

    def test_mock_backend_devuelve_texto_mock(self):
        """Mock backend custom text should be returned with fuente='gemini'."""
        mock = MockGeminiNLBackend()
        mock.response_text = "Texto de prueba especial."
        intent = _make_intent()
        dato = _make_dato()

        # Inject mock via monkeypatching _llamar_gemini
        import motor.generador_nl as gnl
        original_llamar = gnl._llamar_gemini

        def mock_llamar(*args, **kwargs):
            kwargs["_backend"] = mock
            return original_llamar(*args, **kwargs)

        gnl._llamar_gemini = mock_llamar

        # Temporarily set a fake API key
        original_key = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = "fake-key-for-test"
        try:
            texto, fuente = generar_nl(
                "¿Cuántos pasajeros?",
                intent,
                dato,
                "dato",
                [],
                [],
                Almacen,
                sin_llm=False,
            )
            self.assertEqual(fuente, "gemini")
            self.assertEqual(texto, "Texto de prueba especial.")
        finally:
            gnl._llamar_gemini = original_llamar
            if original_key is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = original_key

    def test_mock_backend_error_usa_fallback(self):
        """Mock with should_raise=True should fall back to plantilla."""
        mock = MockGeminiNLBackend()
        mock.should_raise = True
        intent = _make_intent()
        dato = _make_dato()

        import motor.generador_nl as gnl
        original_llamar = gnl._llamar_gemini

        def mock_llamar_raise(*args, **kwargs):
            kwargs["_backend"] = mock
            return original_llamar(*args, **kwargs)

        gnl._llamar_gemini = mock_llamar_raise
        original_key = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = "fake-key-for-test"
        try:
            texto, fuente = generar_nl(
                "¿Cuántos pasajeros?",
                intent,
                dato,
                "dato",
                [],
                [],
                Almacen,
                sin_llm=False,
            )
            self.assertEqual(fuente, "plantilla")
            self.assertGreater(len(texto), 0)
        finally:
            gnl._llamar_gemini = original_llamar
            if original_key is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = original_key

    def test_prompt_contiene_intent(self):
        """User message must contain INTENT section."""
        mock = MockGeminiNLBackend()
        intent = _make_intent()
        dato = _make_dato()
        _llamar_gemini(
            "¿Cuántos pasajeros?",
            intent,
            dato,
            "dato",
            [],
            [],
            Almacen,
            "fake-key",
            _backend=mock,
        )
        self.assertIn("INTENT", mock.last_user_message)

    def test_prompt_contiene_dim_indicador(self):
        """User message must contain DIM_INDICADOR section."""
        mock = MockGeminiNLBackend()
        intent = _make_intent()
        dato = _make_dato()
        _llamar_gemini(
            "¿Cuántos pasajeros?",
            intent,
            dato,
            "dato",
            [],
            [],
            Almacen,
            "fake-key",
            _backend=mock,
        )
        self.assertIn("DIM_INDICADOR", mock.last_user_message)


if __name__ == "__main__":
    unittest.main()
