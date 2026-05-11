"""
Test script for the date expression parser.
"""

from datetime import datetime
from semantica.fechas import extraer_fecha


def test_fechas():
    """Run all test cases and print results."""

    tests = [
        ("marzo 2024", ("2024-03", "2024-03")),
        ("en enero de 2023", ("2023-01", "2023-01")),
        ("entre 2010 y 2020", ("2010-01", "2020-12")),
        ("de 2015 a 2020", ("2015-01", "2020-12")),
        ("2015-2020", ("2015-01", "2020-12")),
        ("en 2023", ("2023-01", "2023-12")),
        ("durante 2023", ("2023-01", "2023-12")),
        ("este ano", None),  # relative — just verify it returns non-None with desde/hasta
        ("ano pasado", None),  # relative — just verify non-None
        ("ultimos 3 anos", None),  # relative — just verify non-None
        ("ultimos 6 meses", None),  # relative — just verify non-None
        ("cuantos pasajeros en la linea mitre", None),  # no date → None
    ]

    passed = 0
    failed = 0

    print("=" * 70)
    print("DATE EXPRESSION PARSER TEST RESULTS")
    print("=" * 70)

    for texto, expected in tests:
        result = extraer_fecha(texto)

        # Determine if test passed
        if expected is None:
            # Test cases that expect None should match exactly or be relative dates that return non-None
            # For relative dates ("este ano", "ano pasado", "ultimos N..."), we accept non-None results
            # For non-temporal queries, we expect None
            if "ano" in texto or "este" in texto or "ultimos" in texto:
                # Relative date patterns — accepting non-None
                if result is not None:
                    status = "PASS"
                    passed += 1
                else:
                    status = "FAIL"
                    failed += 1
            else:
                # Non-temporal query — expecting None
                if result is None:
                    status = "PASS"
                    passed += 1
                else:
                    status = "FAIL"
                    failed += 1
        else:
            # For absolute dates, we check exact match
            if result is not None and result.desde == expected[0] and result.hasta == expected[1]:
                status = "PASS"
                passed += 1
            else:
                status = "FAIL"
                failed += 1

        # Format result string for output
        result_str = f"RangoTemporal(desde={result.desde!r}, hasta={result.hasta!r})" if result else "None"

        print(f"{status:6} | '{texto}'")
        print(f"       Expected: {expected}")
        print(f"       Got:      {result_str}")
        print()

    print("=" * 70)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 70)

    return passed, failed


if __name__ == "__main__":
    test_fechas()
