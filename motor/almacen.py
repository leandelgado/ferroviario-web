"""
Singleton lazy-loader of DataFrames from the parquet data warehouse.

All access to the processed parquet tables should go through `Almacen`
so that files are read at most once per process.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Known tables
# ---------------------------------------------------------------------------

_TABLAS: dict[str, str] = {
    "linea_mensual": "linea_mensual.parquet",
    "red_mensual": "red_mensual.parquet",
    "servicio_mensual": "servicio_mensual.parquet",
    "dim_lineas": "dim_lineas.parquet",
    "dim_indicadores": "dim_indicadores.parquet",
}

# Dimension tables have no temporal coverage
_DIM_TABLAS = {"dim_lineas", "dim_indicadores"}

# Resolve the data directory relative to this file's location
DATA_DIR: Path = Path(__file__).parent.parent / "data" / "processed"


class Almacen:
    """Singleton cache for parquet DataFrames."""

    _cache: dict[str, pd.DataFrame] = {}
    _cobertura: dict[str, tuple[str, str]] = {}

    # ------------------------------------------------------------------
    # Public class methods
    # ------------------------------------------------------------------

    @classmethod
    def obtener(cls, tabla: str) -> pd.DataFrame:
        """Return the DataFrame for *tabla*, loading it on first call.

        Raises
        ------
        ValueError
            If *tabla* is not one of the recognised table names.
        """
        if tabla not in _TABLAS:
            raise ValueError(
                f"Tabla desconocida: {tabla!r}. "
                f"Tablas disponibles: {list(_TABLAS)}"
            )

        if tabla not in cls._cache:
            cls._cache[tabla] = cls._cargar(tabla)

        return cls._cache[tabla]

    @classmethod
    def cobertura(cls, tabla: str) -> tuple[str, str]:
        """Return (desde, hasta) as 'YYYY-MM' strings for *tabla*.

        Dimension tables (dim_lineas, dim_indicadores) return ("", "").
        """
        if tabla not in cls._cobertura:
            # Trigger load so cobertura gets populated
            cls.obtener(tabla)

        return cls._cobertura[tabla]

    @classmethod
    def reset(cls) -> None:
        """Clear the in-memory cache (useful for isolated tests)."""
        cls._cache.clear()
        cls._cobertura.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @classmethod
    def _cargar(cls, tabla: str) -> pd.DataFrame:
        """Load a parquet file, convert periodo column, and record cobertura."""
        ruta = DATA_DIR / _TABLAS[tabla]
        df = pd.read_parquet(ruta)

        if tabla in _DIM_TABLAS:
            cls._cobertura[tabla] = ("", "")
        else:
            # Convert periodo to "YYYY-MM" strings if it's datetime
            if "periodo" in df.columns:
                df["periodo"] = pd.to_datetime(df["periodo"]).dt.strftime("%Y-%m")
                desde = df["periodo"].min()
                hasta = df["periodo"].max()
            else:
                desde = ""
                hasta = ""
            cls._cobertura[tabla] = (desde, hasta)

        return df
