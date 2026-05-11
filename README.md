# Proyecto Ferroviario — Agente conversacional CNRT

## Objetivo general
Construir un agente conversacional en español que permita consultar datos
reales del sistema ferroviario argentino (AMBA, CNRT) mediante lenguaje
natural, sin necesidad de saber SQL ni manejar dashboards.

## Alcance por etapas
- **Etapa 1 — Procesamiento y limpieza de datos raw** ✅ completada
  - Input: 3 Excels de CNRT (cumplimiento, operativas, pasajeros).
  - Output: 5 tablas analíticas en parquet+csv (6,090 / 3,165 / 399 / 8 / 20 filas).
  - Cobertura temporal: 1993–2026.
- **Etapa 2 — Capa semántica** (futuro): mapeo lenguaje natural → métricas/dimensiones.
- **Etapa 3 — Motor de consulta del agente** (futuro).
- **Etapa 4 — Interfaz conversacional** (futuro).

## Fuentes de datos
| Archivo | Hoja(s) usada(s) | Cobertura | Grain |
|---|---|---|---|
| Ffcc_AMBA_cumplimiento_de_programa_2026-03.xlsx | TOTAL TAB + 8 hojas por línea | 1993–2026 (TDC 2015+) | mensual, red o línea |
| ffcc_AMBA_estadisticas_operativas_2026-03.xlsx | DATOS RED#TOTAL | 2005–2026 | mensual, servicio |
| ffcc_AMBA_pax_metropolitanos_2026-03.xlsx | DATOS Dash. FFCC | 1993–2026 | mensual, línea |

## Tablas analíticas (output de Etapa 1)
| Tabla | Grain | Cobertura |
|---|---|---|
| `servicio_mensual` | (periodo, línea, servicio, tracción) | 2005–2026 |
| `linea_mensual` | (periodo, línea) | 1993–2026 |
| `red_mensual` | (periodo) | 1993–2026 |
| `dim_lineas` | línea (8 filas) | estática |
| `dim_indicadores` | campo (20 filas) | diccionario de métricas |

## Consideraciones y decisiones de diseño (Etapa 1)
- Se aprovechan las 8 hojas por línea del archivo de cumplimiento para tener
  regularidad histórica por línea desde 1993 (extiende 12 años la cobertura).
- El operador se modela como columna mensual (no estática), preservando
  cambios de concesionario (TBA → SOFSE → Trenes Argentinos, etc.).
- Las filas con `trenes_programados=0` se conservan con flag `sin_programa=True`;
  no se imputan regularidades — el agente puede distinguir "no medido" de "mal desempeño".
- Servicios contables ("Boletos Ajuste", "Recaudación") se excluyen (~603 filas).
- Ratios (regularidad, cumplimiento, tasa de cancelación, tarifa media) se
  **recalculan post-agregación**, nunca se promedian.
- Para `linea_mensual`: fuentes de precedencia por métrica:
  - Conteos/regularidades 1993–2004: fuente CUMPL (hojas por línea).
  - Conteos/regularidades 2005+: fuente OPERATIVAS (recalculados).
  - PAX 1993–2004: fuente PAX histórico.
  - PAX 2005+: fuente OPERATIVAS.
- Para `red_mensual`: conteos y regularidades provienen de TOTAL TAB (más autoritativo);
  PAX, km y recaudación provienen de la agregación de líneas.
- Formato canónico: parquet (preserva tipos). CSV utf-8-sig para inspección.

## Limitaciones conocidas
- Pre-2005 no existen datos de operador, servicio ni tracción (solo agregado por línea).
- Tren de la Costa solo tiene datos desde mayo 2015.
- "San Martin" sin tilde en el archivo de PAX (normalizado en ETL).
- Las hojas por línea del archivo CUMPL tienen un layout wide (6 bloques repetidos);
  el ETL usa solo el primer bloque (columnas 0–12), que contiene los datos canónicos.
- Recaudación en pesos corrientes (no ajustada por inflación).

## Cómo correr la ETL

Desde la raíz del proyecto (requiere Python ≥ 3.10 con pandas, openpyxl, pyarrow):

```bash
python etl/build_dataset.py
```

Los archivos se generan en `data/processed/`. El script imprime un reporte
de nulos, advertencias de datos fuente (ej. `cumplimiento_programa > 1` en
algunos períodos CNRT) y una verificación cruzada PAX red vs suma de líneas.

## Notas de datos fuente (Etapa 1)
- 10 filas en `linea_mensual` tienen `cumplimiento_programa > 1` (máx 1.19):
  ocurre cuando se corrieron más trenes que los programados; es un fenómeno
  real en la operatoria ferroviaria argentina, no un error del ETL.
- 1 fila tiene `regularidad_absoluta > 1` (1.0205): idem.
- El operador es `NaN` para el 35.5% de las filas de `linea_mensual`
  (períodos pre-2005 donde no existe registro de concesionario en la fuente).

## Estructura de carpetas
```
data/
  raw/          # inputs CNRT (no modificar)
  processed/    # outputs de la ETL
etl/
  build_dataset.py
README.md
```
