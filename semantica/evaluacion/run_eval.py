#!/usr/bin/env python3
"""
Evaluation runner for the semantic layer parser.

Usage:
    python semantica/evaluacion/run_eval.py [--solo-reglas]

Options:
    --solo-reglas   Only run the rule-based parser (no LLM fallback).
"""
import sys
import json
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Gold set path
# ---------------------------------------------------------------------------

_GOLD_PATH = Path(__file__).parent / "gold_set.json"

# ---------------------------------------------------------------------------
# Components evaluated (order defines table row order)
# ---------------------------------------------------------------------------

COMPONENTS = [
    "metrica",
    "agregacion",
    "filtros_linea",
    "filtros_servicio",
    "filtros_traccion",
    "rango_temporal",
    "granularidad",
    "tabla",
]


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _compare_rango(expected_rt, actual_rt) -> bool:
    """Compare rango_temporal: both None, or matching desde+hasta."""
    if expected_rt is None and actual_rt is None:
        return True
    if expected_rt is None or actual_rt is None:
        return False
    return (
        expected_rt.get("desde") == actual_rt.get("desde")
        and expected_rt.get("hasta") == actual_rt.get("hasta")
    )


def _compare_component(component: str, expected, actual) -> bool:
    """Return True if expected == actual for the given component.

    Both expected and actual are already normalized Python values
    (dicts, lists, strings, or None) as returned by _expected_value
    and _actual_value respectively.
    """
    if component in ("filtros_linea", "filtros_servicio", "filtros_traccion"):
        return set(expected) == set(actual)
    elif component == "rango_temporal":
        # Both are already dicts or None at this point
        return _compare_rango(expected, actual)
    else:
        return expected == actual


def _actual_value(component: str, intent) -> object:
    """Extract component value from an Intent object."""
    if component == "rango_temporal":
        rt = intent.rango_temporal
        if rt is None:
            return None
        return {"desde": rt.desde, "hasta": rt.hasta}
    return getattr(intent, component)


def _expected_value(component: str, esperado: dict) -> object:
    """Extract component value from the gold set dict."""
    return esperado.get(component)


# ---------------------------------------------------------------------------
# Main evaluation logic
# ---------------------------------------------------------------------------

def run_evaluation(gold: list[dict], parse_fn) -> dict:
    """
    Run evaluation against the gold set using parse_fn.

    Args:
        gold: List of gold set items (id, pregunta, esperado).
        parse_fn: Callable that takes a question string and returns an Intent.

    Returns:
        Dict with keys:
          - "per_component": {component: {"correct": int, "total": int}}
          - "global_correct": int
          - "total": int
          - "failures": list of failure dicts
    """
    n = len(gold)
    per_component = {c: {"correct": 0, "total": n} for c in COMPONENTS}
    global_correct = 0
    failures = []

    for item in gold:
        qid = item["id"]
        pregunta = item["pregunta"]
        esperado = item["esperado"]

        try:
            intent = parse_fn(pregunta)
        except Exception as exc:
            # Count all components as wrong and record failure
            failure = {
                "id": qid,
                "pregunta": pregunta,
                "error": str(exc),
                "mismatches": {},
            }
            for c in COMPONENTS:
                failure["mismatches"][c] = {
                    "esperado": _expected_value(c, esperado),
                    "obtenido": f"ERROR: {exc}",
                }
            failures.append(failure)
            continue

        # Evaluate each component
        mismatches = {}
        all_correct = True

        for component in COMPONENTS:
            exp = _expected_value(component, esperado)
            act = _actual_value(component, intent)
            if _compare_component(component, exp, act):
                per_component[component]["correct"] += 1
            else:
                all_correct = False
                mismatches[component] = {
                    "esperado": exp,
                    "obtenido": act,
                }

        if all_correct:
            global_correct += 1
        else:
            failures.append({
                "id": qid,
                "pregunta": pregunta,
                "mismatches": mismatches,
            })

    return {
        "per_component": per_component,
        "global_correct": global_correct,
        "total": n,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _pct(correct: int, total: int) -> str:
    if total == 0:
        return " 0.0%"
    return f"{100.0 * correct / total:5.1f}%"


def print_markdown_table(results: dict) -> None:
    """Print a markdown table of per-component and global accuracy."""
    per_component = results["per_component"]
    global_correct = results["global_correct"]
    total = results["total"]

    header = f"| {'Componente':<16} | {'Correcto':>8} | {'Total':>5} | {'Accuracy':>8} |"
    separator = f"|{'-'*18}|{'-'*10}|{'-'*7}|{'-'*10}|"

    print()
    print(header)
    print(separator)

    for component in COMPONENTS:
        c = per_component[component]["correct"]
        t = per_component[component]["total"]
        pct = _pct(c, t)
        print(f"| {component:<16} | {c:>8} | {t:>5} | {pct:>8} |")

    # Global row
    pct_global = _pct(global_correct, total)
    print(f"| {'**GLOBAL**':<16} | **{global_correct:>6}** | {total:>5} | **{pct_global:>6}** |")
    print()


def print_failures(results: dict) -> None:
    """Print details of each failed question."""
    failures = results["failures"]
    if not failures:
        print("Todas las preguntas correctas.")
        return

    print(f"## Fallos ({len(failures)} de {results['total']})\n")

    for f in failures:
        print(f"### [{f['id']}] {f['pregunta']}")

        if "error" in f:
            print(f"  ERROR: {f['error']}")
        else:
            for component, vals in f["mismatches"].items():
                print(f"  {component}:")
                print(f"    esperado : {vals['esperado']}")
                print(f"    obtenido : {vals['obtenido']}")
        print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluation runner for the semantic layer parser."
    )
    parser.add_argument(
        "--solo-reglas",
        action="store_true",
        help="Only run the rule-based parser (no LLM fallback).",
    )
    args = parser.parse_args()

    # Load gold set
    if not _GOLD_PATH.exists():
        print(f"ERROR: gold_set.json not found at {_GOLD_PATH}", file=sys.stderr)
        return 1

    with open(_GOLD_PATH, encoding="utf-8") as f:
        gold = json.load(f)

    print(f"Loaded {len(gold)} gold questions from {_GOLD_PATH}")

    # Select parser
    if args.solo_reglas:
        print("Mode: --solo-reglas (rule-based parser only)\n")
        from semantica.parser_reglas import parse as _parse_reglas

        def parse_fn(pregunta: str):
            return _parse_reglas(pregunta).intent

    else:
        print("Mode: full pipeline (rules + LLM fallback)\n")
        from semantica import parse as _parse_full

        def parse_fn(pregunta: str):
            return _parse_full(pregunta).intent

    # Run evaluation
    results = run_evaluation(gold, parse_fn)

    # Print results
    print("## Resultados por componente\n")
    print_markdown_table(results)
    print_failures(results)

    global_acc = 100.0 * results["global_correct"] / results["total"] if results["total"] else 0.0
    print(f"Accuracy global: {results['global_correct']}/{results['total']} ({global_acc:.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
