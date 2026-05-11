"""
Text normalization module for the railway conversational agent.

Provides functions to clean and normalize Spanish Argentine railway queries
for consistent semantic analysis and tokenization.
"""

import re
import string
from typing import List

from unidecode import unidecode


def normalizar(texto: str) -> str:
    """
    Normalize text for semantic processing.

    Process steps (in order):
    1. Convert to lowercase
    2. Apply unidecode to remove/replace accented characters (ñ→n, á→a, etc.)
    3. Remove punctuation (keep alphanumeric and spaces only)
    4. Collapse multiple consecutive whitespaces into single spaces
    5. Strip leading/trailing whitespace

    Args:
        texto: The text to normalize (raw user input)

    Returns:
        Normalized, clean, tokenizable text

    Examples:
        >>> normalizar("¿Cuántos pasajeros transportó la línea Mitre en 2023?")
        'cuantos pasajeros transporto la linea mitre en 2023'

        >>> normalizar("  REGULARIDAD   promedio   DEL   Sarmiento  ")
        'regularidad promedio del sarmiento'
    """
    if not isinstance(texto, str):
        raise TypeError(f"Expected str, got {type(texto).__name__}")

    # Step 1: Convert to lowercase
    texto = texto.lower()

    # Step 2: Apply unidecode (removes accents: á→a, ñ→n, etc.)
    texto = unidecode(texto)

    # Step 3: Remove punctuation (keep alphanumeric and spaces only)
    # Build a translation table that removes all punctuation
    texto = texto.translate(
        str.maketrans('', '', string.punctuation)
    )

    # Step 4: Collapse multiple whitespaces into single spaces
    texto = re.sub(r'\s+', ' ', texto)

    # Step 5: Strip leading/trailing whitespace
    texto = texto.strip()

    return texto


def tokenizar(texto: str) -> List[str]:
    """
    Tokenize normalized text into a list of words.

    Process:
    1. Call normalizar() to clean the text
    2. Split on whitespace
    3. Filter out empty strings

    Args:
        texto: The text to tokenize (raw user input)

    Returns:
        List of normalized tokens (words)

    Examples:
        >>> tokenizar("¿Cuántos pasajeros transportó?")
        ['cuantos', 'pasajeros', 'transporto']

        >>> tokenizar("qué tan puntual fue la red en marzo 2024")
        ['que', 'tan', 'puntual', 'fue', 'la', 'red', 'en', 'marzo', '2024']
    """
    normalized = normalizar(texto)
    tokens = normalized.split()
    return [token for token in tokens if token]
