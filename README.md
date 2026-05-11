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
- **Etapa 2 — Capa semántica** ✅ completada (2026-05-11): parser de intención híbrido (reglas + Gemini) que traduce preguntas en español a objetos `Intent` estructurados.
- **Etapa 3 — Motor de consulta del agente** (futuro).
- **Etapa 4 — Interfaz conversacional** (futuro).

## Etapa 2 — Capa Semántica

Traduce preguntas en español sobre el sistema ferroviario AMBA a un objeto `Intent` estructurado, listo para que Etapa 3 ejecute la consulta contra los parquets.

### Arquitectura

**Enfoque híbrido:** el parser de reglas (matching determinístico) es el camino principal. Si la confianza es baja (< 0.70) o no se detecta métrica, se invoca el fallback con **Google Gemini** (`gemini-2.5-flash`) que usa structured output para devolver un `Intent` válido.

```
pregunta (español)
      │
      ▼
┌─────────────────────┐
│   parser_reglas     │  normalización + matching (ngrams, fuzzy)
│   confianza ≥ 0.70  │──── sí ───▶ Intent(origen="reglas")
│   y métrica hallada │
└─────────────────────┘
      │ no
      ▼
┌─────────────────────┐
│   parser_llm        │  Gemini 2.5 Flash, structured output
│   (Gemini backend)  │──────────────▶ Intent(origen="llm")
└─────────────────────┘
      │
      ▼
   _merge()           ▶ Intent(origen="hibrido")
```

### Uso básico

```python
from semantica import parse

intent = parse("¿Cuántos pasajeros transportó la línea Mitre en 2023?")
# Intent(metrica='pax_pagos', agregacion='sum', filtros_linea=['Mitre'],
#        rango_temporal=RangoTemporal(desde='2023-01', hasta='2023-12'),
#        granularidad='linea', tabla='linea_mensual', confianza=1.0, origen='reglas')

intent = parse("Regularidad promedio del Sarmiento en los últimos 3 años")
# Intent(metrica='regularidad_absoluta', agregacion='mean', filtros_linea=['Sarmiento'],
#        rango_temporal=RangoTemporal(desde='2023-05', hasta='2026-05'),
#        granularidad='linea', tabla='linea_mensual', confianza=1.0, origen='reglas')

intent = parse("Cancelaciones en Belgrano Norte y Urquiza entre 2018 y 2020")
# Intent(metrica='trenes_cancelados', agregacion='sum',
#        filtros_linea=['Belgrano Norte', 'Urquiza'],
#        rango_temporal=RangoTemporal(desde='2018-01', hasta='2020-12'),
#        granularidad='linea', tabla='linea_mensual', confianza=1.0, origen='reglas')

intent = parse("Qué tan puntual fue la red en marzo 2024")
# Confidence < 0.70 (métrica ambigua) → fallback a LLM
# Intent(metrica='regularidad_absoluta', agregacion='mean', filtros_linea=[],
#        rango_temporal=RangoTemporal(desde='2024-03', hasta='2024-03'),
#        granularidad='red', tabla='red_mensual', confianza=0.9, origen='hibrido')
```

Para forzar el fallback LLM directamente:
```python
intent = parse("...", forzar_llm=True)
```

### Schema del Intent

```python
class Intent(BaseModel):
    metrica: str                              # campo de dim_indicadores (ej. "pax_pagos")
    agregacion: Literal["sum","mean","max","min","none"]
    filtros_linea: list[str]                  # nombres canónicos (ej. ["Mitre","Roca"])
    filtros_servicio: list[str]               # filtra por servicio específico
    filtros_traccion: list[str]               # ["Diésel"] o ["Eléctrico"]
    rango_temporal: RangoTemporal | None      # desde/hasta en "YYYY-MM"
    granularidad: Literal["red","linea","servicio"]
    tabla: Literal["red_mensual","linea_mensual","servicio_mensual"]
    confianza: float                          # 0.0–1.0
    origen: Literal["reglas","llm","hibrido"]
    advertencias: list[str]
```

### Evaluación

```bash
# Solo parser de reglas (sin LLM):
python semantica/evaluacion/run_eval.py --solo-reglas
```

Resultados sobre el gold set de 35 preguntas curadas (mayo 2026):

| Componente       | Accuracy |
|------------------|----------|
| metrica          |   91.4%  |
| agregacion       |   85.7%  |
| filtros_linea    |  100.0%  |
| rango_temporal   |  100.0%  |
| granularidad     |  100.0%  |
| tabla            |  100.0%  |
| **GLOBAL**       | **80.0%**|

El 20% de fallos restantes corresponde a preguntas ambiguas (reformulaciones coloquiales, métricas implícitas) correctamente escaladas al fallback LLM.

### Variable de entorno para el fallback LLM

```bash
export GEMINI_API_KEY="tu-api-key"
# o también: GOOGLE_API_KEY
```

Sin la variable, el fallback usa un `StubBackend` que devuelve un Intent con `confianza=0.5`.

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

## Cómo correr los tests (Etapa 2)

Requiere Python ≥ 3.10 con las dependencias de `requirements.txt`:

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Para correr la evaluación del parser semántico:

```bash
# Parser de reglas (sin clave API):
python semantica/evaluacion/run_eval.py --solo-reglas

# Parser híbrido (requiere GEMINI_API_KEY):
GEMINI_API_KEY="tu-clave" python semantica/evaluacion/run_eval.py
```

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
  processed/    # outputs de la ETL (parquets + CSVs)
etl/
  build_dataset.py
semantica/          # Etapa 2: capa semántica
  intent.py         # modelos Pydantic (Intent, RangoTemporal)
  normalizacion.py  # normalizar() y tokenizar()
  vocabulario.py    # cargar_vocabulario() — carga dim_indicadores y dim_lineas
  fechas.py         # extraer_fecha() — parser de expresiones temporales
  parser_reglas.py  # parse() determinístico con rapidfuzz
  parser_llm.py     # GeminiBackend, StubBackend, LLMBackend (interfaz)
  parser.py         # orquestador híbrido (API pública: parse())
  __init__.py       # expone parse(), Intent, RangoTemporal
  evaluacion/
    gold_set.json   # 35 preguntas curadas con Intent esperado
    run_eval.py     # mide accuracy por componente
tests/
  test_normalizacion.py
  test_vocabulario.py
  test_fechas.py
  test_parser_reglas.py
  test_parser_integracion.py
README.md
requirements.txt
```
