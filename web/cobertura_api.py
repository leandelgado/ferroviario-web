def obtener_cobertura() -> dict:
    from motor.almacen import Almacen
    desde, hasta = Almacen.cobertura("linea_mensual")
    return {
        "tabla_default": "linea_mensual",
        "rango_general": {"desde": desde, "hasta": hasta},
        "casos_especiales": [
            {
                "linea": "Tren de la Costa",
                "desde": "2015-05",
                "nota": "Datos de regularidad desde mayo 2015"
            }
        ]
    }
