"""CLI entry point for the motor package.

Usage:
    python -m motor "pregunta en lenguaje natural" [--json] [--debug]
                    [--sin-llm-nl] [--solo-reglas]
"""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Motor de consulta ferroviario CNRT AMBA",
        prog="python -m motor",
    )
    parser.add_argument("pregunta", help="Pregunta en lenguaje natural")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", help="Salida en JSON")
    output_group.add_argument("--debug", action="store_true",
                              help="Mostrar intent, datos y metadata")
    parser.add_argument(
        "--sin-llm-nl",
        action="store_true",
        dest="sin_llm_nl",
        help="Usar solo plantillas (sin Groq para NL)",
    )
    parser.add_argument(
        "--solo-reglas",
        action="store_true",
        dest="solo_reglas",
        help="Forzar parser de reglas (sin LLM para parsing)",
    )

    args = parser.parse_args()

    try:
        from motor import responder

        respuesta = responder(
            args.pregunta,
            sin_llm_nl=args.sin_llm_nl,
            forzar_reglas=args.solo_reglas,
        )

        if args.json:
            print(respuesta.model_dump_json(indent=2))
        elif args.debug:
            print(respuesta.texto_nl)
            print()
            print(f"[TIPO]: {respuesta.tipo}")
            print(
                f"[INTENT]: tabla={respuesta.intent.tabla} "
                f"metrica={respuesta.intent.metrica} "
                f"lineas={respuesta.intent.filtros_linea} "
                f"tipo={respuesta.intent.tipo}"
            )
            if respuesta.dato:
                print(
                    f"[DATO]: {respuesta.dato.valor} {respuesta.dato.unidad} "
                    f"({respuesta.dato.agregacion})"
                )
            if respuesta.comparacion:
                print(
                    f"[COMPARACION]: eje={respuesta.comparacion.eje} "
                    f"ranking={respuesta.comparacion.ranking}"
                )
            print(
                f"[METADATA]: fuente_nl={respuesta.metadata.fuente_nl} "
                f"tiempo_ms={respuesta.metadata.tiempo_ms:.0f}ms"
            )
            if respuesta.advertencias:
                print(f"[ADVERTENCIAS]: {'; '.join(respuesta.advertencias)}")
        else:
            print(respuesta.texto_nl)

        # Exit 1 only for hard errors
        sys.exit(0 if respuesta.tipo != "error" else 1)

    except Exception as e:
        print(f"Error fatal: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
