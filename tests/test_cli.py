"""
Unit tests for the motor CLI (python -m motor).
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

_WORKDIR = str(Path(__file__).parent.parent)


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "motor"] + list(args),
        capture_output=True,
        text=True,
        cwd=_WORKDIR,
    )


class TestCLI(unittest.TestCase):

    def test_cli_texto_simple(self):
        """Basic invocation with --sin-llm-nl should succeed and print text."""
        result = run_cli("pasajeros Mitre 2023", "--sin-llm-nl", "--solo-reglas")
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertGreater(len(result.stdout.strip()), 0)

    def test_cli_json_output(self):
        """--json flag should produce valid JSON with a 'tipo' key."""
        result = run_cli("pasajeros Mitre 2023", "--json", "--sin-llm-nl", "--solo-reglas")
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            self.fail(f"Output is not valid JSON: {e}\nOutput: {result.stdout}")
        self.assertIn("tipo", parsed)

    def test_cli_debug_output(self):
        """--debug flag should print [TIPO] and [METADATA] markers."""
        result = run_cli("pasajeros Mitre 2023", "--debug", "--sin-llm-nl", "--solo-reglas")
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertIn("[TIPO]", result.stdout)
        self.assertIn("[METADATA]", result.stdout)

    def test_cli_json_parseable_con_metadatos(self):
        """Parsed JSON should have nested metadata with fuente_nl."""
        result = run_cli("pasajeros Mitre 2023", "--json", "--sin-llm-nl", "--solo-reglas")
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        parsed = json.loads(result.stdout)
        self.assertIn("tipo", parsed)
        self.assertIn("metadata", parsed)
        self.assertIn("fuente_nl", parsed["metadata"])

    def test_cli_exit_code_0_dato(self):
        """A dato response should exit with code 0."""
        result = run_cli("pasajeros Mitre 2023", "--sin-llm-nl", "--solo-reglas")
        self.assertEqual(result.returncode, 0)

    def test_cli_sin_argumentos_falla(self):
        """Running without arguments should exit with non-zero code."""
        result = run_cli()
        self.assertNotEqual(result.returncode, 0)

    def test_cli_json_tipo_es_string_valido(self):
        """The 'tipo' field in JSON output must be one of the valid TipoRespuesta values."""
        result = run_cli("pasajeros Mitre 2023", "--json", "--sin-llm-nl", "--solo-reglas")
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        parsed = json.loads(result.stdout)
        valid_tipos = {"dato", "comparacion", "ood", "sin_datos", "error"}
        self.assertIn(parsed["tipo"], valid_tipos)


if __name__ == "__main__":
    unittest.main()
