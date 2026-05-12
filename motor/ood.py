"""
Out-of-domain detection and suggestion generation.

Provides a defensive heuristic check (`es_probable_ood`) that works in
addition to the semantic layer's es_dominio flag, and a canonical list of
example questions (`construir_sugerencias`) used for OOD and sin_datos
responses.
"""

from __future__ import annotations


def es_probable_ood(intent) -> bool:
    """Heuristic: True if intent looks OOD despite possibly passing the rules-based check.

    Parameters
    ----------
    intent:
        A ``semantica.Intent`` instance (typed as Any to avoid circular import).

    Returns
    -------
    bool
        ``True`` when the intent is considered out-of-domain:
        - ``intent.es_dominio`` is ``False``, OR
        - ``intent.metrica`` is empty AND ``intent.filtros_linea`` is empty
          AND ``intent.confianza`` is below 0.3 (very low confidence with no
          signal).
    """
    if not intent.es_dominio:
        return True

    if (
        intent.metrica == ""
        and intent.filtros_linea == []
        and intent.confianza < 0.3
    ):
        return True

    return False


def construir_sugerencias() -> list[str]:
    """Return 3 canonical example questions for OOD and sin_datos responses."""
    return [
        "¿Cuántos pasajeros transportó el Mitre en 2023?",
        "¿Cuál fue la puntualidad de la red ferroviaria en 2022?",
        "¿Cómo varió la recaudación del Sarmiento en el último año disponible?",
    ]
