"""
Unit tests for motor.almacen.Almacen — singleton parquet cache.
"""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.almacen import Almacen


class TestAlmacen(unittest.TestCase):

    def setUp(self):
        Almacen.reset()

    def tearDown(self):
        Almacen.reset()

    # ------------------------------------------------------------------
    # Basic load tests
    # ------------------------------------------------------------------

    def test_obtener_linea_mensual(self):
        df = Almacen.obtener("linea_mensual")
        self.assertIsNotNone(df)
        self.assertGreater(len(df), 0)

    def test_linea_mensual_tiene_columnas_esperadas(self):
        df = Almacen.obtener("linea_mensual")
        for col in ("periodo", "linea", "pax_pagos"):
            self.assertIn(col, df.columns, f"Falta columna '{col}'")

    def test_periodo_es_string_yyyymm(self):
        df = Almacen.obtener("linea_mensual")
        muestra = df["periodo"].iloc[0]
        # Must be a string, not a datetime
        self.assertIsInstance(muestra, str, "periodo debe ser string")
        # Must match YYYY-MM format
        import re
        self.assertTrue(
            re.match(r"^\d{4}-\d{2}$", muestra),
            f"periodo no tiene formato YYYY-MM: {muestra!r}"
        )

    # ------------------------------------------------------------------
    # Cobertura tests
    # ------------------------------------------------------------------

    def test_cobertura_linea_mensual(self):
        desde, hasta = Almacen.cobertura("linea_mensual")
        self.assertIsInstance(desde, str)
        self.assertIsInstance(hasta, str)
        self.assertGreater(len(desde), 0)
        self.assertGreater(len(hasta), 0)
        # Approximate range check
        self.assertLessEqual(desde, "1993-12")
        self.assertGreaterEqual(hasta, "2025-01")

    def test_cobertura_dim_tables(self):
        desde_lineas, hasta_lineas = Almacen.cobertura("dim_lineas")
        self.assertEqual(desde_lineas, "")
        self.assertEqual(hasta_lineas, "")

        desde_ind, hasta_ind = Almacen.cobertura("dim_indicadores")
        self.assertEqual(desde_ind, "")
        self.assertEqual(hasta_ind, "")

    # ------------------------------------------------------------------
    # Singleton / cache tests
    # ------------------------------------------------------------------

    def test_singleton_cache(self):
        df1 = Almacen.obtener("linea_mensual")
        df2 = Almacen.obtener("linea_mensual")
        self.assertIs(df1, df2, "Debe retornar el mismo objeto (singleton)")

    def test_reset_clears_cache(self):
        Almacen.obtener("linea_mensual")
        self.assertIn("linea_mensual", Almacen._cache)
        Almacen.reset()
        self.assertEqual(len(Almacen._cache), 0)
        self.assertEqual(len(Almacen._cobertura), 0)

    # ------------------------------------------------------------------
    # Error cases
    # ------------------------------------------------------------------

    def test_tabla_desconocida_raises(self):
        with self.assertRaises(ValueError) as ctx:
            Almacen.obtener("no_existe")
        self.assertIn("no_existe", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
