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

# Short Spanish month names to numbers (used for patterns like "ene-23", "ene-2023")
MESES_CORTOS = {
    "ene": "01", "feb": "02", "mar": "03", "abr": "04",
    "may": "05", "jun": "06", "jul": "07", "ago": "08",
    "sep": "09", "oct": "10", "nov": "11", "dic": "12"
}

# Build explicit pattern for valid month names to avoid typo fallthrough
_MESES_PATTERN = '|'.join(MESES.keys())
_MESES_CORTOS_PATTERN = '|'.join(MESES_CORTOS.keys())

# Earliest year in the railway dataset (used as open-start boundary)
_ANO_INICIO_DATOS = 1993


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
    7. Relative: "hace N anos" / "hace N meses"
    8. Relative: "en lo que va del ano" (year to date)
    9. "en los primeros N meses de YYYY" / "primeros N meses de YYYY"
    10. Open-end: "desde YYYY" (no upper bound specified)
    11. Open-start: "hasta YYYY" / "antes de YYYY"
    12. Open-start: "despues de YYYY" / "a partir de YYYY"
    13. Short date formats: "MM/YYYY" (normalized: "MMYYYY"), "mes-YY/YYYY" (normalized: "mesYY/YYYY")

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
    # Note: normalizer strips hyphens, so "2018-2020" → "20182020" is handled by pattern 2b.
    range_patterns = [
        r'entre\s+(\d{4})\s+y\s+(\d{4})',
        r'de\s+(\d{4})\s+a\s+(\d{4})',
        r'del\s+(\d{4})\s+al\s+(\d{4})',   # "del 2020 al 2022"
        r'(\d{4})\s+al\s+(\d{4})',          # "2020 al 2022"
        r'desde\s+(\d{4})\s+hasta\s+(\d{4})',
        r'(\d{4})\s*-\s*(\d{4})',           # Hyphen (raw text, pre-norm)
        r'(\d{4})\s+a\s+(\d{4})',           # "2015 a 2025" without leading "de"
    ]
    for pattern in range_patterns:
        match = re.search(pattern, texto)
        if match:
            ano_inicio, ano_fin = match.groups()
            now = datetime.now()
            if int(ano_fin) >= now.year:
                hasta_mes = f"{now.month:02d}"
                hasta_ano = str(now.year)
            else:
                hasta_mes = "12"
                hasta_ano = ano_fin
            return RangoTemporal(
                desde=f"{ano_inicio}-01",
                hasta=f"{hasta_ano}-{hasta_mes}"
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
            now = datetime.now()
            if int(ano) >= now.year:
                hasta = f"{ano}-{now.month:02d}"
            else:
                hasta = f"{ano}-12"
            return RangoTemporal(
                desde=f"{ano}-01",
                hasta=hasta
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
    ultimos_anos_match = re.search(r'ultimos\s+(\d+)\s+anos?(?:\s|$)', texto)
    if ultimos_anos_match:
        n_anos = int(ultimos_anos_match.group(1))
        now = datetime.now()
        # Start from N years ago at the current month
        ano_inicio = now.year - n_anos
        desde = f"{ano_inicio}-{now.month:02d}"
        hasta = f"{now.year}-{now.month:02d}"
        return RangoTemporal(desde=desde, hasta=hasta)

    ultimos_meses_match = re.search(r'ultimos\s+(\d+)\s+mes(?:es)?(?:\s|$)', texto)
    if ultimos_meses_match:
        n_meses = int(ultimos_meses_match.group(1))
        now = datetime.now()
        # Calculate the start date by subtracting n_meses
        start_date = now - timedelta(days=30 * n_meses)  # Approximate
        desde = f"{start_date.year}-{start_date.month:02d}"
        hasta = f"{now.year}-{now.month:02d}"
        return RangoTemporal(desde=desde, hasta=hasta)

    # Pattern 7: Relative "hace N anos" / "hace N meses"
    # "hace 2 anos" → desde=(now.year-2)-(now.month), hasta=now.year-now.month
    # "hace 3 meses" → desde=(now - 3*30days), hasta=now
    hace_anos_match = re.search(r'hace\s+(\d+)\s+anos?(?:\s|$)', texto)
    if hace_anos_match:
        n_anos = int(hace_anos_match.group(1))
        now = datetime.now()
        ano_inicio = now.year - n_anos
        desde = f"{ano_inicio}-{now.month:02d}"
        hasta = f"{now.year}-{now.month:02d}"
        return RangoTemporal(desde=desde, hasta=hasta)

    hace_meses_match = re.search(r'hace\s+(\d+)\s+mes(?:es)?(?:\s|$)', texto)
    if hace_meses_match:
        n_meses = int(hace_meses_match.group(1))
        now = datetime.now()
        start_date = now - timedelta(days=30 * n_meses)  # Approximate
        desde = f"{start_date.year}-{start_date.month:02d}"
        hasta = f"{now.year}-{now.month:02d}"
        return RangoTemporal(desde=desde, hasta=hasta)

    # Pattern 8: "en lo que va del ano" (year to date — same as "este ano")
    if re.search(r'en\s+lo\s+que\s+va\s+del\s+ano(?:\s|$)', texto):
        now = datetime.now()
        desde = f"{now.year}-01"
        hasta = f"{now.year}-{now.month:02d}"
        return RangoTemporal(desde=desde, hasta=hasta)

    # Pattern 9: "en los primeros N meses de YYYY" / "primeros N meses de YYYY"
    primeros_match = re.search(
        r'(?:en\s+los\s+)?primeros\s+(\d+)\s+meses\s+de\s+(\d{4})',
        texto
    )
    if primeros_match:
        n_meses, ano = primeros_match.groups()
        desde = f"{ano}-01"
        hasta = f"{ano}-{int(n_meses):02d}"
        return RangoTemporal(desde=desde, hasta=hasta)

    # Pattern 10: "desde YYYY" open-end (only when NOT followed by "hasta")
    # Must not conflict with Pattern 2 ("desde YYYY hasta YYYY")
    desde_match = re.search(r'desde\s+(\d{4})(?!\s+hasta)(?:\s|$)', texto)
    if desde_match:
        ano = desde_match.group(1)
        now = datetime.now()
        hasta = f"{now.year}-{now.month:02d}"
        return RangoTemporal(desde=f"{ano}-01", hasta=hasta)

    # Pattern 11: "hasta YYYY" / "antes de YYYY" open-start
    # "hasta 2022"   → desde=1993-01, hasta=2022-12
    # "antes de 2021" → desde=1993-01, hasta=2020-12 (year before stated)
    antes_match = re.search(r'antes\s+de\s+(\d{4})(?:\s|$)', texto)
    if antes_match:
        ano = int(antes_match.group(1))
        return RangoTemporal(
            desde=f"{_ANO_INICIO_DATOS}-01",
            hasta=f"{ano - 1}-12"
        )

    hasta_match = re.search(r'hasta\s+(\d{4})(?:\s|$)', texto)
    if hasta_match:
        ano = hasta_match.group(1)
        return RangoTemporal(
            desde=f"{_ANO_INICIO_DATOS}-01",
            hasta=f"{ano}-12"
        )

    # Pattern 12: "despues de YYYY" / "a partir de YYYY" open-end
    despues_match = re.search(r'(?:despues\s+de|a\s+partir\s+de)\s+(\d{4})(?:\s|$)', texto)
    if despues_match:
        ano = despues_match.group(1)
        now = datetime.now()
        hasta = f"{now.year}-{now.month:02d}"
        return RangoTemporal(desde=f"{ano}-01", hasta=hasta)

    # Pattern 2b: Fused year range (normalizer strips hyphens: "2018-2020" → "20182020")
    # Only matches when two valid railway-era years appear consecutively.
    fused_match = re.search(r'(?<!\d)((?:19|20)\d{2})((?:19|20)\d{2})(?!\d)', texto)
    if fused_match:
        ano_inicio, ano_fin = fused_match.groups()
        if ano_inicio < ano_fin:  # sanity check: first must precede second
            now = datetime.now()
            if int(ano_fin) >= now.year:
                hasta_mes = f"{now.month:02d}"
                hasta_ano = str(now.year)
            else:
                hasta_mes = "12"
                hasta_ano = ano_fin
            return RangoTemporal(
                desde=f"{ano_inicio}-01",
                hasta=f"{hasta_ano}-{hasta_mes}"
            )

    # Pattern 13: Short date formats (input is already normalized — punctuation stripped)
    # "01/2023" normalizes to "012023" → month=01, year=2023
    # "ene-23"  normalizes to "ene23"  → month=01, year=2023
    # "ene-2023" normalizes to "ene2023" → month=01, year=2023

    # 13a: Numeric MM/YYYY normalized to MMYYYY (e.g., "012023", "122023")
    num_date_match = re.search(r'(?<!\d)(0[1-9]|1[0-2])(\d{4})(?!\d)', texto)
    if num_date_match:
        mes, ano = num_date_match.groups()
        period = f"{ano}-{mes}"
        return RangoTemporal(desde=period, hasta=period)

    # 13b: Short month name + 4-digit year (e.g., "ene2023")
    short_4_match = re.search(
        rf'({_MESES_CORTOS_PATTERN})(\d{{4}})(?!\d)',
        texto
    )
    if short_4_match:
        mes_texto, ano = short_4_match.groups()
        mes = MESES_CORTOS[mes_texto]
        period = f"{ano}-{mes}"
        return RangoTemporal(desde=period, hasta=period)

    # 13c: Short month name + 2-digit year (e.g., "ene23")
    short_2_match = re.search(
        rf'({_MESES_CORTOS_PATTERN})(\d{{2}})(?!\d)',
        texto
    )
    if short_2_match:
        mes_texto, yy = short_2_match.groups()
        mes = MESES_CORTOS[mes_texto]
        yy_int = int(yy)
        ano = 2000 + yy_int if yy_int <= 50 else 1900 + yy_int
        period = f"{ano}-{mes}"
        return RangoTemporal(desde=period, hasta=period)

    # Fallback: standalone 4-digit year anywhere in text (handles "pasajeros Mitre 2023")
    # Runs last so it doesn't override more specific patterns above.
    year_any = re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)', texto)
    if year_any:
        ano = year_any.group(1)
        now = datetime.now()
        if int(ano) >= now.year:
            hasta = f"{ano}-{now.month:02d}"
        else:
            hasta = f"{ano}-12"
        return RangoTemporal(desde=f"{ano}-01", hasta=hasta)

    # No temporal expression found
    return None
