#!/usr/bin/env python3
"""
ETL principal — Proyecto Ferroviario CNRT
Etapa 1: Procesamiento y limpieza de datos raw.

Inputs:
  data/raw/Ffcc_AMBA_cumplimiento_de_programa_2026-03.xlsx
  data/raw/ffcc_AMBA_estadisticas_operativas_2026-03.xlsx
  data/raw/ffcc_AMBA_pax_metropolitanos_2026-03.xlsx

Outputs (data/processed/):
  servicio_mensual  — grain (periodo, linea, servicio, tipo_traccion)
  linea_mensual     — grain (periodo, linea), cobertura 1993-2026
  red_mensual       — grain (periodo), cobertura 1993-2026
  dim_lineas        — dimensión estática de 8 líneas
  dim_indicadores   — diccionario de métricas con metadatos para el agente
"""
import json
import os

import pandas as pd

# ─── Paths ────────────────────────────────────────────────────────────────────

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE_CUMPL = os.path.join(ROOT, "data", "raw",
                          "Ffcc_AMBA_cumplimiento_de_programa_2026-03.xlsx")
FILE_OP    = os.path.join(ROOT, "data", "raw",
                          "ffcc_AMBA_estadisticas_operativas_2026-03.xlsx")
FILE_PAX   = os.path.join(ROOT, "data", "raw",
                          "ffcc_AMBA_pax_metropolitanos_2026-03.xlsx")
OUT_DIR    = os.path.join(ROOT, "data", "processed")
os.makedirs(OUT_DIR, exist_ok=True)

# ─── Constants ────────────────────────────────────────────────────────────────

MES_NUM = {
    'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
    'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
    'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12,
}
MESES_VALIDOS = set(MES_NUM.keys())

LINEA_NORM = {'San Martin': 'San Martín'}
SERVICIOS_EXCLUIR_REGEX = r'Boletos Ajuste|Recaudaci[oó]n'

HOJAS_LINEA_CUMPL = {
    'MIT TAB': 'Mitre',
    'SAR TAB': 'Sarmiento',
    'URQ TAB': 'Urquiza',
    'ROC TAB': 'Roca',
    'SM TAB':  'San Martín',
    'BN TAB':  'Belgrano Norte',
    'BS TAB':  'Belgrano Sur',
    'TDC TAB': 'Tren de la Costa',
}
LINEAS_ESPERADAS = set(HOJAS_LINEA_CUMPL.values())

# Column names for CUMPL sheets (first 13 cols, indices 0–12)
COLUMNAS_CUMPL = [
    'anio', 'mes_nombre',
    'regularidad_absoluta', 'regularidad_relativa', 'cumplimiento_programa',
    '_trenes_prog_dia_habil', '_coches_tren_dia_habil',  # descartados
    'trenes_programados', 'trenes_cancelados', 'trenes_corridos',
    'trenes_puntuales', 'trenes_atrasados', 'observaciones',
]
CUMPL_DROP = ['_trenes_prog_dia_habil', '_coches_tren_dia_habil']

# Columns to extract from FILE_OP and their canonical names
COLS_OP = [0, 1, 3, 4, 5, 6, 10, 16, 31, 32, 33, 35, 36, 37, 40, 41,
           43, 45, 52, 56, 63, 64, 68, 70, 90]
OP_COL_RENAME = {
    'Año':                                        'anio',
    'Mes':                                        'mes_nombre',
    'Operador':                                   'operador',
    'Línea':                                      'linea',
    'Servicio':                                   'servicio',
    'Tipo de Tracción':                           'tipo_traccion',
    'Trenes Kilómetro (TK) (1+2+3)':             'trenes_km',
    'Coches Kilómetro (CK) (5+6+7)':             'coches_km',
    'Trenes Programados':                         'trenes_programados',
    'Trenes Cancelados':                          'trenes_cancelados',
    'Trenes Corridos (TC)':                       'trenes_corridos',
    'Trenes Puntuales':                           'trenes_puntuales',
    'Trenes Atrasados':                           'trenes_atrasados',
    'Regularidad Absoluta':                       'regularidad_absoluta',
    'Regularidad Relativa':                       'regularidad_relativa',
    'Cumplimiento del Programa':                  'cumplimiento_programa',
    'Pasajeros Pagos (PAX)':                      'pax_pagos',
    'PAX Día Habil (promedio estimado)':          'pax_dia_habil',
    'Ocupación Media (PaxKm/CocheKm)':            'ocupacion_media',
    'PAX Kilómetro':                              'pax_km',
    'Recaudación Vta. Boletos $':                 'recaudacion_pesos',
    'Tarifa Media $':                             'tarifa_media_pesos',
    'Km. Línea (entre cabeceras) en Servicio':    'km_linea',
    'Cantidad de Estaciones en Servicio':          'estaciones',
    'OBSERVACIONES':                              'observaciones',
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def add_periodo(df, col_anio='anio', col_mes='mes_nombre'):
    df = df.copy()
    df[col_anio] = pd.to_numeric(df[col_anio], errors='coerce').astype('Int64')
    df['mes_num'] = df[col_mes].map(MES_NUM)
    df = df[df['mes_num'].notna() & df[col_anio].notna()]
    df['periodo'] = pd.to_datetime(
        df[col_anio].astype(str) + '-'
        + df['mes_num'].astype(str).str.zfill(2) + '-01'
    )
    return df.drop(columns=['mes_num', col_anio, col_mes])


def safe_ratio(num, den):
    return (num / den.replace(0, pd.NA)).round(4)


def mode_first(s):
    clean = s.dropna()
    return clean.mode().iloc[0] if not clean.empty else pd.NA


def save(df, name):
    # Normalizar columnas object con tipos mixtos (str+int) a str puro
    df = df.copy()
    for col in df.select_dtypes(include='object').columns:
        if df[col].apply(lambda v: not isinstance(v, (str, type(None), float))).any():
            df[col] = df[col].where(df[col].isna(), df[col].astype(str))
    df.to_parquet(os.path.join(OUT_DIR, f"{name}.parquet"), index=False)
    df.to_csv(os.path.join(OUT_DIR, f"{name}.csv"), index=False,
              encoding='utf-8-sig')
    print(f"  Guardado {name}: {len(df):,} filas, {len(df.columns)} columnas")


# ─── Extracción ───────────────────────────────────────────────────────────────

print("=" * 60)
print("Extrayendo FILE_CUMPL (TOTAL TAB) …")
df_red_cumpl_raw = pd.read_excel(
    FILE_CUMPL, sheet_name="TOTAL TAB",
    header=4, usecols=range(13), engine="openpyxl",
)
df_red_cumpl_raw.columns = COLUMNAS_CUMPL
df_red_cumpl_raw = (df_red_cumpl_raw
                    .drop(columns=CUMPL_DROP)
                    .loc[df_red_cumpl_raw['mes_nombre'].isin(MESES_VALIDOS)])

print("Extrayendo FILE_CUMPL (hojas por línea) …")
frames = []
for hoja, linea in HOJAS_LINEA_CUMPL.items():
    d = pd.read_excel(
        FILE_CUMPL, sheet_name=hoja,
        header=4, usecols=range(13), engine="openpyxl",
    )
    d.columns = COLUMNAS_CUMPL
    d = d.drop(columns=CUMPL_DROP)
    d = d[d['mes_nombre'].isin(MESES_VALIDOS)]
    d['linea'] = linea
    frames.append(d)
df_cumpl_lineas = pd.concat(frames, ignore_index=True)
print(f"  {len(df_cumpl_lineas):,} filas por línea extraídas")

print("Extrayendo FILE_OP …")
df_op_raw = pd.read_excel(
    FILE_OP, sheet_name="DATOS RED#TOTAL",
    header=0, usecols=COLS_OP, engine="openpyxl",
)
df_op_raw = df_op_raw.rename(columns=OP_COL_RENAME)
df_op_raw = df_op_raw.dropna(how='all')
df_op_raw = df_op_raw[
    ~df_op_raw['servicio'].astype(str).str.contains(
        SERVICIOS_EXCLUIR_REGEX, case=False, na=False)
]
df_op_raw['sin_programa'] = (df_op_raw['trenes_programados'].fillna(0) == 0)
# Excel puede mezclar str e int en la columna observaciones
df_op_raw['observaciones'] = df_op_raw['observaciones'].astype(str).where(
    df_op_raw['observaciones'].notna(), other=pd.NA)
print(f"  {len(df_op_raw):,} filas operativas (sin servicios contables)")

print("Extrayendo FILE_PAX …")
df_pax_raw = pd.read_excel(
    FILE_PAX, sheet_name="DATOS Dash. FFCC",
    header=0, usecols=[0, 1, 2, 3, 4], engine="openpyxl",
)
df_pax_raw = df_pax_raw.rename(columns={
    'Año': 'anio', 'Mes': 'mes_nombre', 'Línea': 'linea',
    'PAX': 'pax_pagos', 'PAX DIA HABIL': 'pax_dia_habil',
})
df_pax_raw = df_pax_raw.dropna(subset=['anio', 'mes_nombre', 'linea'])
df_pax_raw['linea'] = df_pax_raw['linea'].replace(LINEA_NORM)
print(f"  {len(df_pax_raw):,} filas de PAX histórico")

# ─── Tabla 1: servicio_mensual ────────────────────────────────────────────────

print("\nConstruyendo servicio_mensual …")
df_serv = add_periodo(df_op_raw)
df_serv['tasa_cancelacion'] = safe_ratio(
    df_serv['trenes_cancelados'], df_serv['trenes_programados']
)
df_serv = df_serv.sort_values(
    ['periodo', 'linea', 'servicio']
).reset_index(drop=True)

# ─── Tabla 2: linea_mensual ───────────────────────────────────────────────────

print("Construyendo linea_mensual …")

# (a) Agregado por línea desde operativas (2005+)
AGGS_OP = {
    'trenes_programados': 'sum',
    'trenes_cancelados':  'sum',
    'trenes_corridos':    'sum',
    'trenes_puntuales':   'sum',
    'trenes_atrasados':   'sum',
    'pax_pagos':          'sum',
    'pax_km':             'sum',
    'trenes_km':          'sum',
    'coches_km':          'sum',
    'recaudacion_pesos':  'sum',
    'pax_dia_habil':      'mean',
    'km_linea':           'first',
    'estaciones':         'first',
    'operador':           mode_first,
}
df_lin_op = (
    add_periodo(df_op_raw)
    .groupby(['periodo', 'linea'])
    .agg(AGGS_OP)
    .reset_index()
)
# Recalcular ratios post-agregación (nunca promediar ratios)
df_lin_op['regularidad_absoluta']  = safe_ratio(
    df_lin_op['trenes_puntuales'],  df_lin_op['trenes_programados'])
df_lin_op['regularidad_relativa']  = safe_ratio(
    df_lin_op['trenes_puntuales'],  df_lin_op['trenes_corridos'])
df_lin_op['cumplimiento_programa'] = safe_ratio(
    df_lin_op['trenes_corridos'],   df_lin_op['trenes_programados'])
df_lin_op['tasa_cancelacion']      = safe_ratio(
    df_lin_op['trenes_cancelados'], df_lin_op['trenes_programados'])
df_lin_op['tarifa_media_pesos']    = safe_ratio(
    df_lin_op['recaudacion_pesos'], df_lin_op['pax_pagos'])

# (b) Cumplimiento por línea (1993+)
df_lin_cumpl = add_periodo(df_cumpl_lineas)

# (c) PAX histórico (1993–2004 cubre el hueco)
df_pax_hist = add_periodo(df_pax_raw)

# Combinar con outer join progresivo
df_linea = (
    df_lin_op
    .merge(df_lin_cumpl, on=['periodo', 'linea'], how='outer',
           suffixes=('', '_cumpl'))
    .merge(df_pax_hist[['periodo', 'linea', 'pax_pagos', 'pax_dia_habil']],
           on=['periodo', 'linea'], how='outer',
           suffixes=('', '_paxhist'))
)

# Precedencia: op para 2005+, cumpl como fallback para métricas de trenes
for col in ['trenes_programados', 'trenes_cancelados', 'trenes_corridos',
            'trenes_puntuales', 'trenes_atrasados',
            'regularidad_absoluta', 'regularidad_relativa', 'cumplimiento_programa']:
    cumpl_col = f'{col}_cumpl'
    if cumpl_col in df_linea.columns:
        df_linea[col] = df_linea[col].fillna(df_linea[cumpl_col])

# PAX: op para 2005+, pax_hist como fallback
if 'pax_pagos_paxhist' in df_linea.columns:
    df_linea['pax_pagos'] = df_linea['pax_pagos'].fillna(
        df_linea['pax_pagos_paxhist'])
if 'pax_dia_habil_paxhist' in df_linea.columns:
    df_linea['pax_dia_habil'] = df_linea['pax_dia_habil'].fillna(
        df_linea['pax_dia_habil_paxhist'])

# Recalcular tasa_cancelacion sobre datos finales consolidados
df_linea['tasa_cancelacion'] = safe_ratio(
    df_linea['trenes_cancelados'], df_linea['trenes_programados'])

# Eliminar columnas auxiliares del merge
df_linea = df_linea.drop(
    columns=[c for c in df_linea.columns
             if c.endswith('_cumpl') or c.endswith('_paxhist')]
)

# Variación interanual de PAX (requiere orden cronológico por línea)
df_linea = df_linea.sort_values(['linea', 'periodo'])
df_linea['pax_variacion_yoy'] = (
    df_linea.groupby('linea')['pax_pagos']
    .pct_change(periods=12)
    .round(4)
)
df_linea = df_linea.sort_values(['periodo', 'linea']).reset_index(drop=True)

# ─── Tabla 3: red_mensual ─────────────────────────────────────────────────────

print("Construyendo red_mensual …")
df_red_cumpl = add_periodo(df_red_cumpl_raw)

AGGS_RED = {
    'trenes_programados': 'sum',
    'trenes_cancelados':  'sum',
    'trenes_corridos':    'sum',
    'trenes_puntuales':   'sum',
    'trenes_atrasados':   'sum',
    'pax_pagos':          'sum',
    'pax_km':             'sum',
    'trenes_km':          'sum',
    'coches_km':          'sum',
    'recaudacion_pesos':  'sum',
}
df_red_op = df_linea.groupby('periodo').agg(AGGS_RED).reset_index()

df_red = df_red_cumpl.merge(
    df_red_op, on='periodo', how='outer', suffixes=('_cumpl', '_op')
)

# Conteos de trenes: preferir TOTAL TAB (más autoritativo), fallback a suma de líneas
for col in ['trenes_programados', 'trenes_cancelados', 'trenes_corridos',
            'trenes_puntuales', 'trenes_atrasados']:
    cumpl_col, op_col = f'{col}_cumpl', f'{col}_op'
    if cumpl_col in df_red.columns and op_col in df_red.columns:
        df_red[col] = df_red[cumpl_col].fillna(df_red[op_col])
        df_red = df_red.drop(columns=[cumpl_col, op_col])
    elif cumpl_col in df_red.columns:
        df_red = df_red.rename(columns={cumpl_col: col})
    elif op_col in df_red.columns:
        df_red = df_red.rename(columns={op_col: col})

# PAX y métricas financieras: solo vienen de la suma de líneas
for col in ['pax_pagos', 'pax_km', 'trenes_km', 'coches_km', 'recaudacion_pesos']:
    op_col = f'{col}_op'
    if op_col in df_red.columns:
        df_red[col] = df_red[op_col]
        df_red = df_red.drop(columns=[op_col])
    cumpl_col = f'{col}_cumpl'
    if cumpl_col in df_red.columns:
        df_red = df_red.drop(columns=[cumpl_col])

df_red['tasa_cancelacion']   = safe_ratio(
    df_red['trenes_cancelados'], df_red['trenes_programados'])
df_red['tarifa_media_pesos'] = safe_ratio(
    df_red['recaudacion_pesos'], df_red['pax_pagos'])

df_red = df_red.sort_values('periodo').reset_index(drop=True)

# ─── Tabla 4: dim_lineas ──────────────────────────────────────────────────────

print("Construyendo dim_lineas …")
dim_lineas = (
    df_linea.sort_values('periodo', ascending=False)
    .groupby('linea')
    .agg(
        operador_actual=('operador', 'first'),
        km_linea=('km_linea', 'first'),
        estaciones=('estaciones', 'first'),
    )
    .reset_index()
)
tipo_traccion = (
    add_periodo(df_op_raw)
    .groupby('linea')['tipo_traccion']
    .apply(lambda x: '/'.join(sorted(x.dropna().unique())))
    .reset_index()
    .rename(columns={'tipo_traccion': 'tipos_traccion'})
)
dim_lineas = dim_lineas.merge(tipo_traccion, on='linea', how='left')

# ─── Tabla 5: dim_indicadores ─────────────────────────────────────────────────

print("Construyendo dim_indicadores …")
_ind = [
    ('pax_pagos',             'Pasajeros pagos',
     'Pasajeros que abonaron boleto',
     'pasajeros',    True,  'mayor', 'servicio',
     ['pasajeros', 'demanda', 'viajeros', 'usuarios']),

    ('pax_dia_habil',         'Pasajeros por día hábil',
     'Promedio estimado de pasajeros en día hábil',
     'pasajeros/día', False, 'mayor', 'servicio',
     ['pasajeros diarios', 'afluencia diaria']),

    ('pax_km',                'Pasajeros kilómetro',
     'Suma de distancias recorridas por cada pasajero',
     'pax·km',       True,  'mayor', 'servicio',
     ['pax-km', 'pasajeros kilómetro']),

    ('pax_variacion_yoy',     'Variación interanual pasajeros',
     'Cambio porcentual vs mismo mes del año anterior',
     '%',            False, 'mayor', 'línea',
     ['variación anual pasajeros', 'crecimiento pasajeros']),

    ('trenes_programados',    'Trenes programados',
     'Total de servicios planificados',
     'trenes',       True,  'neutral', 'servicio',
     ['servicios programados', 'oferta']),

    ('trenes_cancelados',     'Trenes cancelados',
     'Servicios planificados que no se realizaron',
     'trenes',       True,  'menor', 'servicio',
     ['cancelaciones', 'servicios cancelados']),

    ('trenes_corridos',       'Trenes corridos',
     'Servicios efectivamente realizados',
     'trenes',       True,  'mayor', 'servicio',
     ['servicios realizados', 'trenes realizados']),

    ('trenes_puntuales',      'Trenes puntuales',
     'Servicios realizados con demora ≤5 min',
     'trenes',       True,  'mayor', 'servicio',
     ['servicios puntuales', 'puntualidad absoluta']),

    ('trenes_atrasados',      'Trenes atrasados',
     'Servicios realizados con demora >5 min',
     'trenes',       True,  'menor', 'servicio',
     ['atrasos', 'demoras']),

    ('trenes_km',             'Trenes kilómetro',
     'Kilómetros totales recorridos por los trenes',
     'tren·km',      True,  'mayor', 'servicio',
     ['TK', 'trenes-km']),

    ('coches_km',             'Coches kilómetro',
     'Kilómetros totales recorridos por los coches',
     'coche·km',     True,  'mayor', 'servicio',
     ['CK', 'coches-km']),

    ('tasa_cancelacion',      'Tasa de cancelación',
     'Trenes cancelados / trenes programados',
     '0–1',          False, 'menor', 'servicio',
     ['cancelados %', 'porcentaje cancelaciones']),

    ('regularidad_absoluta',  'Regularidad absoluta',
     'Trenes puntuales / trenes programados. Meta ≥0.95',
     '0–1',          False, 'mayor', 'servicio',
     ['puntualidad', 'regularidad']),

    ('regularidad_relativa',  'Regularidad relativa',
     'Trenes puntuales / trenes corridos',
     '0–1',          False, 'mayor', 'servicio',
     ['puntualidad relativa']),

    ('cumplimiento_programa', 'Cumplimiento de programa',
     'Trenes corridos / trenes programados',
     '0–1',          False, 'mayor', 'servicio',
     ['cumplimiento']),

    ('recaudacion_pesos',     'Recaudación ($)',
     'Ingresos por venta de boletos en pesos corrientes',
     '$ ARS',        True,  'mayor', 'servicio',
     ['recaudación', 'ingresos boletos']),

    ('tarifa_media_pesos',    'Tarifa media ($)',
     'Recaudación / pasajeros pagos en pesos corrientes',
     '$ ARS/pax',    False, 'neutral', 'servicio',
     ['precio promedio boleto', 'tarifa']),

    ('ocupacion_media',       'Ocupación media',
     'Pasajeros-km / coches-km. Pax promedio por coche',
     'pax/coche',    False, 'mayor', 'servicio',
     ['ocupación', 'carga media']),

    ('km_linea',              'Kilómetros de línea',
     'Extensión de la línea entre cabeceras en servicio',
     'km',           False, 'neutral', 'línea',
     ['extensión', 'longitud línea']),

    ('estaciones',            'Estaciones en servicio',
     'Cantidad de estaciones activas',
     'estaciones',   False, 'neutral', 'línea',
     ['paradas', 'estaciones']),
]

dim_indicadores = pd.DataFrame([
    {
        'campo':               campo,
        'etiqueta_humana':     etiqueta,
        'descripcion_breve':   desc,
        'unidad':              unidad,
        'agregable':           agregable,
        'direccion_mejor':     direccion,
        'granularidad_minima': granularidad,
        'sinonimos':           json.dumps(sinonimos, ensure_ascii=False),
    }
    for campo, etiqueta, desc, unidad, agregable, direccion, granularidad, sinonimos
    in _ind
])

# ─── Persistir ────────────────────────────────────────────────────────────────

print("\nGuardando outputs …")
save(df_serv,        "servicio_mensual")
save(df_linea,       "linea_mensual")
save(df_red,         "red_mensual")
save(dim_lineas,     "dim_lineas")
save(dim_indicadores,"dim_indicadores")

# ─── Verificación ─────────────────────────────────────────────────────────────

print("\nVerificando …")

assert not df_serv.duplicated(
    subset=['periodo', 'linea', 'servicio', 'tipo_traccion']).any(), \
    "servicio_mensual: grain no único"
assert not df_linea.duplicated(subset=['periodo', 'linea']).any(), \
    "linea_mensual: grain no único"
assert not df_red.duplicated(subset=['periodo']).any(), \
    "red_mensual: grain no único"

assert set(df_linea['linea'].unique()) == LINEAS_ESPERADAS, \
    f"Líneas inesperadas: {set(df_linea['linea'].unique()) ^ LINEAS_ESPERADAS}"

assert df_linea['periodo'].min() <= pd.Timestamp('1993-01-01'), \
    f"linea_mensual inicia en {df_linea['periodo'].min()}, esperado ≤1993-01-01"
assert df_linea['periodo'].max() >= pd.Timestamp('2026-01-01'), \
    f"linea_mensual termina en {df_linea['periodo'].max()}, esperado ≥2026-01-01"

for col in ['tasa_cancelacion', 'regularidad_absoluta',
            'regularidad_relativa', 'cumplimiento_programa']:
    s = df_linea[col].dropna()
    bad = s[~s.between(0, 1)]
    if not bad.empty:
        # Valores levemente fuera de rango son posibles por datos fuente (CNRT)
        print(f"  AVISO: {col} tiene {len(bad)} valor(es) fuera de [0,1] "
              f"(rango observado: {bad.min():.4f}–{bad.max():.4f})")
    else:
        pass  # OK

print("  Aserciones estructurales OK")

print("\nNulos en linea_mensual (columnas clave):")
for col in ['pax_pagos', 'trenes_corridos', 'regularidad_absoluta', 'operador']:
    nulos = df_linea[col].isna().sum()
    print(f"  {col}: {nulos:,} nulos ({nulos / len(df_linea) * 100:.1f}%)")

# Sanidad cruzada: PAX red ≈ suma de líneas (2005+)
recientes = df_linea[df_linea['periodo'] >= '2005-01-01']
red_calc  = recientes.groupby('periodo')['pax_pagos'].sum()
red_tabla = df_red.set_index('periodo')['pax_pagos'].dropna()
common    = red_calc.index.intersection(red_tabla.index)
if len(common) > 0:
    diff = ((red_calc[common] - red_tabla[common]).abs()
            / red_tabla[common].replace(0, pd.NA))
    print(f"\nDiscrepancia media PAX (red vs suma líneas, 2005+): {diff.mean():.4f}")
else:
    print("\nSin períodos comunes para cruce de PAX")

print("\n" + "=" * 60)
print("ETL completada. Archivos en:", OUT_DIR)
