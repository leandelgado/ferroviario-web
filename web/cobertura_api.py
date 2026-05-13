def obtener_cobertura() -> dict:
    from motor import cobertura_tabla
    desde, hasta = cobertura_tabla("linea_mensual")
    return {
        "tabla_default": "linea_mensual",
        "rango_general": {"desde": desde, "hasta": hasta},
        "casos_especiales": [
            # Tren de la Costa data starts from 2015-05 — not in the general parquet range
            {
                "linea": "Tren de la Costa",
                "desde": "2015-05",
                "nota": "Datos de regularidad desde mayo 2015"
            }
        ]
    }
