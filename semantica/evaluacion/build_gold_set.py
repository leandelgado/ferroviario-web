#!/usr/bin/env python3
"""
Build expanded gold_set.json from base set + new variants.

Usage:
    python semantica/evaluacion/build_gold_set.py

Validates each new entry's metrica slug against dim_indicadores.parquet
before writing the final JSON.
"""
import json
import sys
from pathlib import Path

import pandas as pd

_BASE = Path(__file__).parent
_DATA_DIR = _BASE.parent.parent / "data" / "processed"
_GOLD_OUT = _BASE / "gold_set.json"

# ---------------------------------------------------------------------------
# Load valid metric slugs for validation
# ---------------------------------------------------------------------------

def _load_campos() -> set[str]:
    df = pd.read_parquet(_DATA_DIR / "dim_indicadores.parquet")
    return set(df["campo"].tolist())


# ---------------------------------------------------------------------------
# Base 35 entries (kept exactly as-is)
# ---------------------------------------------------------------------------

BASE = json.loads((_BASE / "gold_set.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helper to build an entry
# ---------------------------------------------------------------------------

def e(
    id_: str,
    pregunta: str,
    categoria: str,
    metrica: str,
    agregacion: str,
    filtros_linea: list,
    rango_temporal,   # None | {"desde": "YYYY-MM", "hasta": "YYYY-MM"}
    granularidad: str,
    tabla: str,
    filtros_servicio: list = None,
    filtros_traccion: list = None,
    tipo_esperado: str = None,   # "ood" for out-of-domain entries
) -> dict:
    out = {"id": id_, "pregunta": pregunta, "categoria": categoria}
    if tipo_esperado == "ood":
        out["tipo_esperado"] = "ood"
        out["esperado"] = None
    else:
        out["esperado"] = {
            "metrica": metrica,
            "agregacion": agregacion,
            "filtros_linea": filtros_linea,
            "filtros_servicio": filtros_servicio or [],
            "filtros_traccion": filtros_traccion or [],
            "rango_temporal": rango_temporal,
            "granularidad": granularidad,
            "tabla": tabla,
        }
    return out


def yr(y: int):
    """Single full year range."""
    return {"desde": f"{y}-01", "hasta": f"{y}-12"}


def ym(y: int, m: int):
    """Single month."""
    return {"desde": f"{y}-{m:02d}", "hasta": f"{y}-{m:02d}"}


def rng(y1: int, y2: int):
    """Year range."""
    return {"desde": f"{y1}-01", "hasta": f"{y2}-12"}


# Date constants (machine date: 2026-05-20)
NOW_Y, NOW_M = 2026, 5
THIS_YEAR = {"desde": "2026-01", "hasta": "2026-05"}
LAST_YEAR = {"desde": "2025-01", "hasta": "2025-12"}
LAST_2Y   = {"desde": "2024-05", "hasta": "2026-05"}
LAST_3Y   = {"desde": "2023-05", "hasta": "2026-05"}
LAST_6M   = {"desde": "2025-11", "hasta": "2026-05"}
HACE_1Y   = {"desde": "2025-05", "hasta": "2026-05"}
HACE_2Y   = {"desde": "2024-05", "hasta": "2026-05"}
SINCE2020 = {"desde": "2020-01", "hasta": "2026-05"}
UPTO2022  = {"desde": "1993-01", "hasta": "2022-12"}
PRE2021   = {"desde": "1993-01", "hasta": "2020-12"}
POST2019  = {"desde": "2019-01", "hasta": "2026-05"}
FROM2020  = {"desde": "2020-01", "hasta": "2026-05"}
YTD       = THIS_YEAR


# ---------------------------------------------------------------------------
# New entries by category
# ---------------------------------------------------------------------------

NEW: list[dict] = []

# ── CATEGORY A: Variantes de formulación ──────────────────────────────────
# pax_pagos synonyms & verb variants
NEW += [
    e("q036","cuántos viajeros tuvo el Mitre en 2023","A","pax_pagos","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q037","demanda del Sarmiento en 2022","A","pax_pagos","sum",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q038","usuarios del Roca en 2024","A","pax_pagos","sum",["Roca"],yr(2024),"linea","linea_mensual"),
    e("q039","cuántos pax tuvo la red en 2020","A","pax_pagos","sum",[],yr(2020),"red","red_mensual"),
    e("q040","personas que viajaron en el Belgrano Norte en 2021","A","pax_pagos","sum",["Belgrano Norte"],yr(2021),"linea","linea_mensual"),
    e("q041","cantidad de pasajeros del San Martín en 2022","A","pax_pagos","sum",["San Martín"],yr(2022),"linea","linea_mensual"),
    e("q042","tráfico del Tren de la Costa en 2021","A","pax_pagos","sum",["Tren de la Costa"],yr(2021),"linea","linea_mensual"),
    e("q043","en 2023 cuántos pasajeros tuvo el Mitre","A","pax_pagos","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q044","gente que usó el Urquiza en 2023","A","pax_pagos","sum",["Urquiza"],yr(2023),"linea","linea_mensual"),
]
# trenes_cancelados synonyms
NEW += [
    e("q045","cuántos trenes anulados hubo en el Mitre en 2022","A","trenes_cancelados","sum",["Mitre"],yr(2022),"linea","linea_mensual"),
    e("q046","servicios cancelados del Roca en 2023","A","trenes_cancelados","sum",["Roca"],yr(2023),"linea","linea_mensual"),
    e("q047","trenes que no salieron del Urquiza en 2021","A","trenes_cancelados","sum",["Urquiza"],yr(2021),"linea","linea_mensual"),
    e("q048","trenes anulados del San Martín en 2023","A","trenes_cancelados","sum",["San Martín"],yr(2023),"linea","linea_mensual"),
]
# regularidad_absoluta synonyms
NEW += [
    e("q049","cómo anduvo la puntualidad del Mitre en 2024","A","regularidad_absoluta","mean",["Mitre"],yr(2024),"linea","linea_mensual"),
    e("q050","índice de puntualidad del Sarmiento en 2022","A","regularidad_absoluta","mean",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q051","performance del Roca en 2023","A","regularidad_absoluta","mean",["Roca"],yr(2023),"linea","linea_mensual"),
    e("q052","cumplimiento de horarios del Belgrano Norte en 2021","A","regularidad_absoluta","mean",["Belgrano Norte"],yr(2021),"linea","linea_mensual"),
    e("q053","regularidad absoluta del Urquiza en 2022","A","regularidad_absoluta","mean",["Urquiza"],yr(2022),"linea","linea_mensual"),
]
# regularidad_relativa
NEW += [
    e("q054","puntualidad relativa del Mitre en 2023","A","regularidad_relativa","mean",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q055","ratio de puntualidad del Sarmiento en 2024","A","regularidad_relativa","mean",["Sarmiento"],yr(2024),"linea","linea_mensual"),
    e("q056","índice de regularidad del Roca en 2022","A","regularidad_relativa","mean",["Roca"],yr(2022),"linea","linea_mensual"),
]
# tasa_cancelacion
NEW += [
    e("q057","tasa de cancelaciones del Mitre en 2022","A","tasa_cancelacion","mean",["Mitre"],yr(2022),"linea","linea_mensual"),
    e("q058","porcentaje de cancelados del Roca en 2023","A","tasa_cancelacion","mean",["Roca"],yr(2023),"linea","linea_mensual"),
    e("q059","tasa cancelados del Sarmiento en 2024","A","tasa_cancelacion","mean",["Sarmiento"],yr(2024),"linea","linea_mensual"),
    e("q060","ratio cancelación del Belgrano Sur en 2022","A","tasa_cancelacion","mean",["Belgrano Sur"],yr(2022),"linea","linea_mensual"),
]
# trenes_corridos synonyms
NEW += [
    e("q061","servicios realizados del Mitre en 2023","A","trenes_corridos","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q062","trenes que circularon en el Sarmiento en 2022","A","trenes_corridos","sum",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q063","trenes operados en el Roca en 2021","A","trenes_corridos","sum",["Roca"],yr(2021),"linea","linea_mensual"),
    e("q064","trenes efectivos del San Martín en 2024","A","trenes_corridos","sum",["San Martín"],yr(2024),"linea","linea_mensual"),
    e("q065","servicios prestados por el Belgrano Norte en 2023","A","trenes_corridos","sum",["Belgrano Norte"],yr(2023),"linea","linea_mensual"),
]
# trenes_programados
NEW += [
    e("q066","servicios programados del Mitre en 2023","A","trenes_programados","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q067","oferta del Sarmiento en 2022","A","trenes_programados","sum",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q068","planificación del Roca en 2023","A","trenes_programados","sum",["Roca"],yr(2023),"linea","linea_mensual"),
    e("q069","cronograma del San Martín en 2024","A","trenes_programados","sum",["San Martín"],yr(2024),"linea","linea_mensual"),
]
# trenes_atrasados
NEW += [
    e("q070","atrasos en el Mitre en 2022","A","trenes_atrasados","sum",["Mitre"],yr(2022),"linea","linea_mensual"),
    e("q071","demorados en el Sarmiento en 2023","A","trenes_atrasados","sum",["Sarmiento"],yr(2023),"linea","linea_mensual"),
    e("q072","retrasos del Belgrano Norte en 2021","A","trenes_atrasados","sum",["Belgrano Norte"],yr(2021),"linea","linea_mensual"),
    e("q073","trenes tarde del Roca en 2022","A","trenes_atrasados","sum",["Roca"],yr(2022),"linea","linea_mensual"),
]
# recaudacion_pesos
NEW += [
    e("q074","facturación del Mitre en 2023","A","recaudacion_pesos","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q075","ingresos del Sarmiento en 2022","A","recaudacion_pesos","sum",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q076","plata recaudada por el Roca en 2024","A","recaudacion_pesos","sum",["Roca"],yr(2024),"linea","linea_mensual"),
    e("q077","ventas del Belgrano Norte en 2022","A","recaudacion_pesos","sum",["Belgrano Norte"],yr(2022),"linea","linea_mensual"),
]
# tarifa_media_pesos
NEW += [
    e("q078","precio promedio del boleto del Mitre en 2023","A","tarifa_media_pesos","mean",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q079","boleto promedio del Sarmiento en 2022","A","tarifa_media_pesos","mean",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q080","valor del boleto del Roca en 2024","A","tarifa_media_pesos","mean",["Roca"],yr(2024),"linea","linea_mensual"),
    e("q081","cuánto sale el boleto del San Martín en 2023","A","tarifa_media_pesos","mean",["San Martín"],yr(2023),"linea","linea_mensual"),
]
# ocupacion_media
NEW += [
    e("q082","factor de ocupación del Mitre en 2023","A","ocupacion_media","mean",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q083","llenado del Sarmiento en 2022","A","ocupacion_media","mean",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q084","carga media del San Martín en 2024","A","ocupacion_media","mean",["San Martín"],yr(2024),"linea","linea_mensual"),
]
# km_linea & estaciones variants
NEW += [
    e("q085","longitud de la línea Mitre","A","km_linea","none",["Mitre"],None,"linea","linea_mensual"),
    e("q086","cuántos kilómetros tiene el Roca","A","km_linea","none",["Roca"],None,"linea","linea_mensual"),
    e("q087","largo de la línea Sarmiento","A","km_linea","none",["Sarmiento"],None,"linea","linea_mensual"),
    e("q088","cuántas paradas tiene el Mitre","A","estaciones","none",["Mitre"],None,"linea","linea_mensual"),
    e("q089","número de paradas del Sarmiento","A","estaciones","none",["Sarmiento"],None,"linea","linea_mensual"),
    e("q090","estaciones en servicio del Roca","A","estaciones","none",["Roca"],None,"linea","linea_mensual"),
]
# Line alias variants
NEW += [
    e("q091","pasajeros del FC Mitre en 2023","A","pax_pagos","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q092","regularidad de la línea BN en 2022","A","regularidad_absoluta","mean",["Belgrano Norte"],yr(2022),"linea","linea_mensual"),
    e("q093","cancelaciones del TDC en 2021","A","trenes_cancelados","sum",["Tren de la Costa"],yr(2021),"linea","linea_mensual"),
    e("q094","pasajeros del BS en 2023","A","pax_pagos","sum",["Belgrano Sur"],yr(2023),"linea","linea_mensual"),
    e("q095","puntualidad del FC Sarmiento en 2022","A","regularidad_absoluta","mean",["Sarmiento"],yr(2022),"linea","linea_mensual"),
]
# trenes_puntuales synonyms
NEW += [
    e("q096","trenes a horario del Mitre en 2023","A","trenes_puntuales","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q097","servicios puntuales del Sarmiento en 2022","A","trenes_puntuales","sum",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q098","trenes en horario del Belgrano Norte en 2022","A","trenes_puntuales","sum",["Belgrano Norte"],yr(2022),"linea","linea_mensual"),
]
# Multi-line queries
NEW += [
    e("q099","Mitre y Roca pasajeros en 2023","A","pax_pagos","sum",["Mitre","Roca"],yr(2023),"linea","linea_mensual"),
    e("q100","Sarmiento y San Martín regularidad en 2022","A","regularidad_absoluta","mean",["Sarmiento","San Martín"],yr(2022),"linea","linea_mensual"),
    e("q101","cancelaciones en Roca y Urquiza en 2023","A","trenes_cancelados","sum",["Roca","Urquiza"],yr(2023),"linea","linea_mensual"),
    e("q102","recaudación del Belgrano Norte y Belgrano Sur en 2023","A","recaudacion_pesos","sum",["Belgrano Norte","Belgrano Sur"],yr(2023),"linea","linea_mensual"),
    e("q103","trenes corridos en Mitre, Sarmiento y Roca en 2021","A","trenes_corridos","sum",["Mitre","Sarmiento","Roca"],yr(2021),"linea","linea_mensual"),
]
# trenes_km & coches_km
NEW += [
    e("q104","trenes km del Sarmiento en 2022","A","trenes_km","sum",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q105","coches km del Mitre en 2023","A","coches_km","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q106","kilometros de tren del Roca en 2021","A","trenes_km","sum",["Roca"],yr(2021),"linea","linea_mensual"),
]

# ── CATEGORY B: Errores tipográficos y acentuación ────────────────────────
NEW += [
    # No accents on line names (normalizer handles)
    e("q107","pasajeros del san martin en 2023","B","pax_pagos","sum",["San Martín"],yr(2023),"linea","linea_mensual"),
    e("q108","regularidad del belgrano norte en 2022","B","regularidad_absoluta","mean",["Belgrano Norte"],yr(2022),"linea","linea_mensual"),
    e("q109","extension de la linea mitre","B","km_linea","none",["Mitre"],None,"linea","linea_mensual"),
    e("q110","estaciones del roca","B","estaciones","none",["Roca"],None,"linea","linea_mensual"),
    e("q111","recaudacion del roca en 2023","B","recaudacion_pesos","sum",["Roca"],yr(2023),"linea","linea_mensual"),
    # Uppercase
    e("q112","CANCELACIONES DEL ROCA EN 2023","B","trenes_cancelados","sum",["Roca"],yr(2023),"linea","linea_mensual"),
    e("q113","PASAJEROS DEL MITRE EN 2022","B","pax_pagos","sum",["Mitre"],yr(2022),"linea","linea_mensual"),
    # Fuzzy line name typos
    e("q114","pasajeros del Sarmento en 2023","B","pax_pagos","sum",["Sarmiento"],yr(2023),"linea","linea_mensual"),
    e("q115","cancelaciones del Sarmineto en 2022","B","trenes_cancelados","sum",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q116","regularidad del Belrgano Norte en 2023","B","regularidad_absoluta","mean",["Belgrano Norte"],yr(2023),"linea","linea_mensual"),
    e("q117","pasajeros del Tren de la Cota en 2021","B","pax_pagos","sum",["Tren de la Costa"],yr(2021),"linea","linea_mensual"),
    # Abbreviation aliases
    e("q118","cancelaciones del FC roca en 2023","B","trenes_cancelados","sum",["Roca"],yr(2023),"linea","linea_mensual"),
    e("q119","pasajeros del fc sarmiento en 2022","B","pax_pagos","sum",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    e("q120","regularidad del linea roca en 2022","B","regularidad_absoluta","mean",["Roca"],yr(2022),"linea","linea_mensual"),
    # No accent on metric synonyms
    e("q121","puntualidad del Mitre en 2022","B","regularidad_absoluta","mean",["Mitre"],yr(2022),"linea","linea_mensual"),
    e("q122","cancelaciones del Roca en 2022","B","trenes_cancelados","sum",["Roca"],yr(2022),"linea","linea_mensual"),
    e("q123","regularidad del Sarmiento en 2023","B","regularidad_absoluta","mean",["Sarmiento"],yr(2023),"linea","linea_mensual"),
    # Capitalization mix
    e("q124","Pasajeros Del Mitre En 2023","B","pax_pagos","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q125","REGULARIDAD del sarmiento en 2022","B","regularidad_absoluta","mean",["Sarmiento"],yr(2022),"linea","linea_mensual"),
    # Typo in metric word
    e("q126","cancelasiones del Roca en 2022","B","trenes_cancelados","sum",["Roca"],yr(2022),"linea","linea_mensual"),
    e("q127","puntualiad del Mitre en 2023","B","regularidad_absoluta","mean",["Mitre"],yr(2023),"linea","linea_mensual"),
    # "el" prefix variants
    e("q128","pasajeros del el Mitre en 2023","B","pax_pagos","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q129","demoras en el roca en 2022","B","trenes_atrasados","sum",["Roca"],yr(2022),"linea","linea_mensual"),
]

# ── CATEGORY C: Ambigüedad temporal ───────────────────────────────────────
NEW += [
    # Relative year expressions
    e("q130","pasajeros del Mitre este año","C","pax_pagos","sum",["Mitre"],THIS_YEAR,"linea","linea_mensual"),
    e("q131","trenes cancelados del Sarmiento el año pasado","C","trenes_cancelados","sum",["Sarmiento"],LAST_YEAR,"linea","linea_mensual"),
    e("q132","puntualidad del Roca hace 2 años","C","regularidad_absoluta","mean",["Roca"],HACE_2Y,"linea","linea_mensual"),
    e("q133","pasajeros del Mitre en los últimos 3 años","C","pax_pagos","sum",["Mitre"],LAST_3Y,"linea","linea_mensual"),
    e("q134","cancelaciones del Sarmiento en los últimos 6 meses","C","trenes_cancelados","sum",["Sarmiento"],LAST_6M,"linea","linea_mensual"),
    e("q135","regularidad del San Martín hace 1 año","C","regularidad_absoluta","mean",["San Martín"],HACE_1Y,"linea","linea_mensual"),
    e("q136","pasajeros de la red en los últimos 2 años","C","pax_pagos","sum",[],LAST_2Y,"red","red_mensual"),
    e("q137","recaudación del Roca año pasado","C","recaudacion_pesos","sum",["Roca"],LAST_YEAR,"linea","linea_mensual"),
    e("q138","trenes corridos del Mitre este año","C","trenes_corridos","sum",["Mitre"],THIS_YEAR,"linea","linea_mensual"),
    # Year ranges
    e("q139","pasajeros del Mitre entre 2018 y 2020","C","pax_pagos","sum",["Mitre"],rng(2018,2020),"linea","linea_mensual"),
    e("q140","regularidad de la red de 2019 a 2021","C","regularidad_absoluta","mean",[],rng(2019,2021),"red","red_mensual"),
    e("q141","cancelaciones del Roca desde 2020 hasta 2022","C","trenes_cancelados","sum",["Roca"],rng(2020,2022),"linea","linea_mensual"),
    e("q142","pasajeros del Mitre del 2020 al 2022","C","pax_pagos","sum",["Mitre"],rng(2020,2022),"linea","linea_mensual"),
    e("q143","trenes corridos del Sarmiento de 2018 a 2022","C","trenes_corridos","sum",["Sarmiento"],rng(2018,2022),"linea","linea_mensual"),
    # Hyphen range (normalizer strips hyphen → fused years)
    e("q144","pasajeros del Mitre 2019-2021","C","pax_pagos","sum",["Mitre"],rng(2019,2021),"linea","linea_mensual"),
    e("q145","cancelaciones del Roca 2018-2020","C","trenes_cancelados","sum",["Roca"],rng(2018,2020),"linea","linea_mensual"),
    # Open bounds
    e("q146","pasajeros del Sarmiento desde 2020","C","pax_pagos","sum",["Sarmiento"],SINCE2020,"linea","linea_mensual"),
    e("q147","cancelaciones del Roca hasta 2022","C","trenes_cancelados","sum",["Roca"],UPTO2022,"linea","linea_mensual"),
    e("q148","puntualidad del Mitre antes de 2021","C","regularidad_absoluta","mean",["Mitre"],PRE2021,"linea","linea_mensual"),
    e("q149","pasajeros del San Martín después de 2019","C","pax_pagos","sum",["San Martín"],POST2019,"linea","linea_mensual"),
    e("q150","trenes corridos del Belgrano Norte a partir de 2020","C","trenes_corridos","sum",["Belgrano Norte"],FROM2020,"linea","linea_mensual"),
    # Month + year
    e("q151","pasajeros del Mitre en enero 2023","C","pax_pagos","sum",["Mitre"],ym(2023,1),"linea","linea_mensual"),
    e("q152","cancelaciones del Sarmiento en diciembre de 2022","C","trenes_cancelados","sum",["Sarmiento"],ym(2022,12),"linea","linea_mensual"),
    e("q153","regularidad del Roca en marzo de 2024","C","regularidad_absoluta","mean",["Roca"],ym(2024,3),"linea","linea_mensual"),
    e("q154","pasajeros del Mitre en junio 2021","C","pax_pagos","sum",["Mitre"],ym(2021,6),"linea","linea_mensual"),
    e("q155","trenes corridos del San Martín en agosto 2023","C","trenes_corridos","sum",["San Martín"],ym(2023,8),"linea","linea_mensual"),
    # YTD and primeros N meses
    e("q156","pasajeros del Mitre en lo que va del año","C","pax_pagos","sum",["Mitre"],YTD,"linea","linea_mensual"),
    e("q157","cancelaciones del Sarmiento en los primeros 6 meses de 2023","C","trenes_cancelados","sum",["Sarmiento"],{"desde":"2023-01","hasta":"2023-06"},"linea","linea_mensual"),
    e("q158","regularidad del Roca en los primeros 3 meses de 2024","C","regularidad_absoluta","mean",["Roca"],{"desde":"2024-01","hasta":"2024-03"},"linea","linea_mensual"),
    # Short date formats
    e("q159","pasajeros del Mitre en ene-23","C","pax_pagos","sum",["Mitre"],ym(2023,1),"linea","linea_mensual"),
    e("q160","cancelaciones del Sarmiento en dic-22","C","trenes_cancelados","sum",["Sarmiento"],ym(2022,12),"linea","linea_mensual"),
    e("q161","regularidad del Roca en mar-24","C","regularidad_absoluta","mean",["Roca"],ym(2024,3),"linea","linea_mensual"),
    # No date (null)
    e("q162","cuántos pasajeros tiene el Mitre","C","pax_pagos","sum",["Mitre"],None,"linea","linea_mensual"),
    e("q163","puntualidad del Sarmiento","C","regularidad_absoluta","mean",["Sarmiento"],None,"linea","linea_mensual"),
    e("q164","cancelaciones del Roca","C","trenes_cancelados","sum",["Roca"],None,"linea","linea_mensual"),
    e("q165","tarifa media del Belgrano Norte","C","tarifa_media_pesos","mean",["Belgrano Norte"],None,"linea","linea_mensual"),
    e("q166","ocupación del San Martín","C","ocupacion_media","mean",["San Martín"],None,"linea","linea_mensual"),
    # "hace N meses"
    e("q167","cancelaciones del Roca hace 3 meses","C","trenes_cancelados","sum",["Roca"],{"desde":"2026-02","hasta":"2026-05"},"linea","linea_mensual"),
    e("q168","pasajeros del Mitre hace 1 mes","C","pax_pagos","sum",["Mitre"],{"desde":"2026-04","hasta":"2026-05"},"linea","linea_mensual"),
    # "durante YYYY"
    e("q169","pasajeros del Sarmiento durante 2023","C","pax_pagos","sum",["Sarmiento"],yr(2023),"linea","linea_mensual"),
    e("q170","trenes corridos del Roca durante 2022","C","trenes_corridos","sum",["Roca"],yr(2022),"linea","linea_mensual"),
]

# ── CATEGORY D: Elipsis y preguntas telegráficas ──────────────────────────
NEW += [
    # Sin verbo, año presente como número suelto
    e("q171","pasajeros Mitre 2023","D","pax_pagos","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q172","cancelaciones Roca 2022","D","trenes_cancelados","sum",["Roca"],yr(2022),"linea","linea_mensual"),
    e("q173","regularidad Sarmiento 2023","D","regularidad_absoluta","mean",["Sarmiento"],yr(2023),"linea","linea_mensual"),
    e("q174","puntualidad Belgrano Norte 2021","D","regularidad_absoluta","mean",["Belgrano Norte"],yr(2021),"linea","linea_mensual"),
    # Sin fecha
    e("q175","puntualidad Sarmiento","D","regularidad_absoluta","mean",["Sarmiento"],None,"linea","linea_mensual"),
    e("q176","cancelaciones Roca","D","trenes_cancelados","sum",["Roca"],None,"linea","linea_mensual"),
    e("q177","trenes corridos Mitre 2024","D","trenes_corridos","sum",["Mitre"],yr(2024),"linea","linea_mensual"),
    e("q178","recaudación Sarmiento 2023","D","recaudacion_pesos","sum",["Sarmiento"],yr(2023),"linea","linea_mensual"),
    e("q179","ocupación San Martín 2022","D","ocupacion_media","mean",["San Martín"],yr(2022),"linea","linea_mensual"),
    e("q180","tarifa Mitre 2024","D","tarifa_media_pesos","mean",["Mitre"],yr(2024),"linea","linea_mensual"),
    # Solo línea + métrica (sin año)
    e("q181","trenes cancelados Urquiza","D","trenes_cancelados","sum",["Urquiza"],None,"linea","linea_mensual"),
    e("q182","estaciones San Martín","D","estaciones","none",["San Martín"],None,"linea","linea_mensual"),
    e("q183","extensión Belgrano Sur","D","km_linea","none",["Belgrano Sur"],None,"linea","linea_mensual"),
    # Con signo de pregunta sin verbo
    e("q184","Mitre 2023?","D","pax_pagos","sum",["Mitre"],yr(2023),"linea","linea_mensual"),
    e("q185","Sarmiento puntualidad?","D","regularidad_absoluta","mean",["Sarmiento"],None,"linea","linea_mensual"),
    # Variantes de orden telegráfico
    e("q186","2022 pasajeros Roca","D","pax_pagos","sum",["Roca"],yr(2022),"linea","linea_mensual"),
    e("q187","Roca 2022 cancelaciones","D","trenes_cancelados","sum",["Roca"],yr(2022),"linea","linea_mensual"),
]

# ── CATEGORY E: Ranking / comparación cross-línea ─────────────────────────
NEW += [
    # max/min across all lines — granularidad upgrades to "linea"
    e("q188","qué línea tuvo más pasajeros en 2023","E","pax_pagos","max",[],yr(2023),"linea","linea_mensual"),
    e("q189","cuál fue la línea con más pasajeros en 2022","E","pax_pagos","max",[],yr(2022),"linea","linea_mensual"),
    e("q190","la línea con mayor cantidad de pasajeros en 2021","E","pax_pagos","max",[],yr(2021),"linea","linea_mensual"),
    e("q191","qué línea anduvo peor en puntualidad en 2022","E","regularidad_absoluta","min",[],yr(2022),"linea","linea_mensual"),
    e("q192","la línea menos puntual en 2023","E","regularidad_absoluta","min",[],yr(2023),"linea","linea_mensual"),
    e("q193","qué línea tuvo más cancelaciones en 2022","E","trenes_cancelados","max",[],yr(2022),"linea","linea_mensual"),
    e("q194","cuál fue la línea con menos cancelaciones en 2023","E","trenes_cancelados","min",[],yr(2023),"linea","linea_mensual"),
    e("q195","la línea con más ingresos en 2023","E","recaudacion_pesos","max",[],yr(2023),"linea","linea_mensual"),
    e("q196","qué línea corrió más trenes en 2022","E","trenes_corridos","max",[],yr(2022),"linea","linea_mensual"),
    e("q197","la línea con mejor puntualidad en 2024","E","regularidad_absoluta","max",[],yr(2024),"linea","linea_mensual"),
    e("q198","qué línea tuvo la mayor tasa de cancelación en 2022","E","tasa_cancelacion","max",[],yr(2022),"linea","linea_mensual"),
    e("q199","cuál es la línea más larga","E","km_linea","max",[],None,"linea","linea_mensual"),
    e("q200","qué línea tiene más estaciones","E","estaciones","max",[],None,"linea","linea_mensual"),
    e("q218","cuál es la línea más corta","E","km_linea","min",[],None,"linea","linea_mensual"),
    e("q219","qué línea es la más corta","E","km_linea","min",[],None,"linea","linea_mensual"),
    e("q201","la peor línea en regularidad en 2021","E","regularidad_absoluta","min",[],yr(2021),"linea","linea_mensual"),
    e("q202","qué línea transportó menos pasajeros en 2020","E","pax_pagos","min",[],yr(2020),"linea","linea_mensual"),
]

# ── CATEGORY F: Casos OOD (fuera de dominio) ──────────────────────────────
NEW += [
    e("q203","qué color son los trenes del Mitre","F","","sum",[],None,"red","red_mensual",tipo_esperado="ood"),
    e("q204","cuánto cuesta un boleto a Bariloche","F","","sum",[],None,"red","red_mensual",tipo_esperado="ood"),
    e("q205","pasajeros del subte línea D en 2023","F","","sum",[],None,"red","red_mensual",tipo_esperado="ood"),
    e("q206","hola","F","","sum",[],None,"red","red_mensual",tipo_esperado="ood"),
    e("q207","qué hacés","F","","sum",[],None,"red","red_mensual",tipo_esperado="ood"),
    e("q208","cuál es la mejor aerolínea argentina","F","","sum",[],None,"red","red_mensual",tipo_esperado="ood"),
    e("q209","cómo llego a Constitución","F","","sum",[],None,"red","red_mensual",tipo_esperado="ood"),
    e("q210","gracias por la respuesta","F","","sum",[],None,"red","red_mensual",tipo_esperado="ood"),
]

# ── CATEGORY G: Filtros de servicio y tracción ────────────────────────────
NEW += [
    e("q211","pasajeros eléctricos del Mitre en 2023","G","pax_pagos","sum",["Mitre"],yr(2023),"servicio","servicio_mensual",filtros_traccion=["Eléctrico"]),
    e("q212","trenes diesel cancelados del Roca en 2022","G","trenes_cancelados","sum",["Roca"],yr(2022),"servicio","servicio_mensual",filtros_traccion=["Diésel"]),
    e("q213","regularidad de trenes eléctricos del Sarmiento en 2023","G","regularidad_absoluta","mean",["Sarmiento"],yr(2023),"servicio","servicio_mensual",filtros_traccion=["Eléctrico"]),
    e("q214","pasajeros km eléctricos del Mitre en 2022","G","pax_km","sum",["Mitre"],yr(2022),"servicio","servicio_mensual",filtros_traccion=["Eléctrico"]),
    e("q215","tasa de cancelación de trenes diesel del Roca en 2021","G","tasa_cancelacion","mean",["Roca"],yr(2021),"servicio","servicio_mensual",filtros_traccion=["Diésel"]),
]


# ---------------------------------------------------------------------------
# Assembly & validation
# ---------------------------------------------------------------------------

def build() -> None:
    campos_validos = _load_campos()

    # Add "categoria" to existing base items (mark as baseline).
    # Exclude IDs already defined in NEW so re-running is idempotent.
    new_ids = {item["id"] for item in NEW}
    base_with_cat = []
    for item in BASE:
        if item["id"] in new_ids:
            continue
        item_copy = dict(item)
        if "categoria" not in item_copy:
            item_copy["categoria"] = "baseline"
        base_with_cat.append(item_copy)

    gold = base_with_cat + NEW

    errors: list[str] = []
    seen_ids: set[str] = set()

    for item in gold:
        qid = item["id"]
        if qid in seen_ids:
            errors.append(f"Duplicate id: {qid}")
        seen_ids.add(qid)

        if item.get("tipo_esperado") == "ood":
            continue  # no validation for OOD entries

        esp = item.get("esperado")
        if esp is None:
            continue

        metrica = esp.get("metrica", "")
        if metrica and metrica not in campos_validos:
            errors.append(f"[{qid}] metrica inválida: {metrica!r}")

        agg = esp.get("agregacion", "")
        if agg not in {"sum", "mean", "max", "min", "none"}:
            errors.append(f"[{qid}] agregacion inválida: {agg!r}")

        gran = esp.get("granularidad", "")
        if gran not in {"red", "linea", "servicio"}:
            errors.append(f"[{qid}] granularidad inválida: {gran!r}")

        tabla = esp.get("tabla", "")
        if tabla not in {"red_mensual", "linea_mensual", "servicio_mensual"}:
            errors.append(f"[{qid}] tabla inválida: {tabla!r}")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=__import__("sys").stderr)
        raise SystemExit(1)

    out_path = _GOLD_OUT
    out_path.write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")
    n_ood = sum(1 for item in gold if item.get("tipo_esperado") == "ood")
    n_normal = len(gold) - n_ood
    print(f"Written {len(gold)} items ({n_normal} in-domain, {n_ood} OOD) -> {out_path}")


if __name__ == "__main__":
    build()
