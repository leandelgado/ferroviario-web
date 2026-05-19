"""
Date expression parser for the railway conversational agent.

Extracts temporal expressions from normalized Spanish text and returns
a RangoTemporal object representing the start and end of the period.
"""

import re
from datetime import datetime, timedelta
from typing import Optional

from semantica.intent import RangoTemporal


# Spanish month names to numbers
MESES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
}

# Build explicit pattern for valid month names to avoid typo fallthrough
_MESES_PATTERN = '|'.join(MESES.keys())


def extraer_fecha(texto: str) -> Optional[RangoTemporal]:
    """
    Parse Spanish temporal expressions from normalized text.

    Applies patterns in order of specificity:
    1. Month + year explicit (e.g., "marzo 2024", "en enero de 2023")
    2. Range of years (e.g., "entre 2010 y 2020", "2015-2020")
    3. Single year (e.g., "en 2023", "durante 2023", "2023")
    4. Relative: "este ano" (this year)
    5. Relative: "ano pasado" (last year)
    6. Relative: "ultimos N anos" / "ultimos N meses" (last N years/months)

    Args:
        texto: Normalized text (lowercase, unidecode applied, no accents)

    Returns:
        RangoTemporal with desde and hasta in "YYYY-MM" format, or None
        if no temporal expression is found.

    Note:
        Input should already be normalized (lowercase, unidecode applied).
        Patterns use normalized forms (e.g., "ultimos" not "últimos",
        "ano" not "año").
    """

    # Pattern 1: Month + year explicit
    # Matches: "marzo 2024", "en marzo de 2024", "en marzo del 2024", "marzo de 2024"
    match = re.search(
        rf'(?:en\s+)?({_MESES_PATTERN})\s+(?:de\s+|del\s+)?(\d{{4}})',
        texto
    )
    if match:
        mes_texto, ano = match.groups()
        mes = MESES[mes_texto]
        period = f"{ano}-{mes}"
        return RangoTemporal(desde=period, hasta=period)

    # Pattern 2: Range of years
    # Matches: "entre 2010 y 2020", "de 2015 a 2020", "2015-2020", "desde 2015 hasta 2020"
    # Check for "entre X y Y" or "de X a Y" or "desde X hasta Y"
    range_patterns = [
        r'entre\s+(\d{4})\s+y\s+(\d{4})',
        r'de\s+(\d{4})\s+a\s+(\d{4})',
        r'desde\s+(\d{4})\s+hasta\s+(\d{4})',
        r'(\d{4})\s*-\s*(\d{4})',  # Hyphen with optional spaces
        r'(\d{4})\s+a\s+(\d{4})',  # "2015 a 2025" without leading "de"
    ]
    for pattern in range_patterns:
        match = re.search(pattern, texto)
        if match:
            ano_inicio, ano_fin = match.groups()
            return RangoTemporal(
                desde=f"{ano_inicio}-01",
                hasta=f"{ano_fin}-12"
            )

    # Pattern 3: Single year
    # Matches: "en 2023", "durante 2023", "el ano 2023", "ano 2023", or standalone "2023"
    # Note: Avoids matching years that follow unrecognized words (e.g., "jumlio 2024")
    single_year_patterns = [
        r'(?:en|durante|el\s+ano|ano)\s+(\d{4})',
        r'^(\d{4})$',  # Standalone 4-digit year (entire string is just the year)
    ]
    for pattern in single_year_patterns:
        match = re.search(pattern, texto)
        if match:
            ano = match.group(1)
            return RangoTemporal(
                desde=f"{ano}-01",
                hasta=f"{ano}-12"
            )

    # Pattern 4: Relative "este ano" (this year)
    if re.search(r'este\s+ano(?:\s|$)', texto):
        now = datetime.now()
        desde = f"{now.year}-01"
        hasta = f"{now.year}-{now.month:02d}"
        return RangoTemporal(desde=desde, hasta=hasta)

    # Pattern 5: Relative "ano pasado" (last year)
    if re.search(r'ano\s+pasado(?:\s|$)', texto):
        now = datetime.now()
        ano_pasado = now.year - 1
        return RangoTemporal(
            desde=f"{ano_pasado}-01",
            hasta=f"{ano_pasado}-12"
        )

    # Pattern 6: Relative "ultimos N anos" / "ultimos N meses"
    # Matches: "ultimos 3 anos", "ultimos 6 meses", etc.
    ultimos_anos_match = re.search(r'ultimos\s+(\d+)\s+anos(?:\s|$)', texto)
    if ultimos_anos_match:
        n_anos = int(ultimos_anos_match.group(1))
        now = datetime.now()
        # Start from N years ago at the current month
        ano_inicio = now.year - n_anos
        desde = f"{ano_inicio}-{now.month:02d}"
        hasta = f"{now.year}-{now.month:02d}"
        return RangoTemporal(desde=desde, hasta=hasta)

    ultimos_meses_match = re.search(r'ultimos\s+(\d+)\s+meses(?:\s|$)', texto)
    if ultimos_meses_match:
        n_meses = int(ultimos_meses_match.group(1))
        now = datetime.now()
        # Calculate the start date by subtracting n_meses
        start_date = now - timedelta(days=30 * n_meses)  # Approximate
        desde = f"{start_date.year}-{start_date.month:02d}"
        hasta = f"{now.year}-{now.month:02d}"
        return RangoTemporal(desde=desde, hasta=hasta)

    # No temporal expression found
    return None
