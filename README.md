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
- **Etapa 3 — Motor de consulta del agente** ✅ completada (2026-05-12)
- ✅ **Etapa 4** — Interfaz web del agente _(2026-05-13)_

---

## Etapa 1 — Procesamiento y limpieza de datos

### Fuentes de datos
| Archivo | Hoja(s) usada(s) | Cobertura | Grain |
|---|---|---|---|
| Ffcc_AMBA_cumplimiento_de_programa_2026-03.xlsx | TOTAL TAB + 8 hojas por línea | 1993–2026 (TDC 2015+) | mensual, red o línea |
| ffcc_AMBA_estadisticas_operativas_2026-03.xlsx | DATOS RED#TOTAL | 2005–2026 | mensual, servicio |
| ffcc_AMBA_pax_metropolitanos_2026-03.xlsx | DATOS Dash. FFCC | 1993–2026 | mensual, línea |

### Tablas analíticas (output de Etapa 1)
| Tabla | Grain | Cobertura |
|---|---|---|
| `servicio_mensual` | (periodo, línea, servicio, tracción) | 2005–2026 |
| `linea_mensual` | (periodo, línea) | 1993–2026 |
| `red_mensual` | (periodo) | 1993–2026 |
| `dim_lineas` | línea (8 filas) | estática |
| `dim_indicadores` | campo (20 filas) | diccionario de métricas |

### Consideraciones y decisiones de diseño
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

### Limitaciones conocidas
- Pre-2005 no existen datos de operador, servicio ni tracción (solo agregado por línea).
- Tren de la Costa solo tiene datos desde mayo 2015.
- "San Martin" sin tilde en el archivo de PAX (normalizado en ETL).
- Las hojas por línea del archivo CUMPL tienen un layout wide (6 bloques repetidos);
  el ETL usa solo el primer bloque (columnas 0–12), que contiene los datos canónicos.
- Recaudación en pesos corrientes (no ajustada por inflación).

### Notas de datos fuente
- 10 filas en `linea_mensual` tienen `cumplimiento_programa > 1` (máx 1.19):
  ocurre cuando se corrieron más trenes que los programados; es un fenómeno
  real en la operatoria ferroviaria argentina, no un error del ETL.
- 1 fila tiene `regularidad_absoluta > 1` (1.0205): idem.
- El operador es `NaN` para el 35.5% de las filas de `linea_mensual`
  (períodos pre-2005 donde no existe registro de concesionario en la fuente).

### Cómo correr la ETL

Desde la raíz del proyecto (requiere Python ≥ 3.10 con pandas, openpyxl, pyarrow):

```bash
python etl/build_dataset.py
```

Los archivos se generan en `data/processed/`. El script imprime un reporte
de nulos, advertencias de datos fuente (ej. `cumplimiento_programa > 1` en
algunos períodos CNRT) y una verificación cruzada PAX red vs suma de líneas.

---

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
    # Campos añadidos en Etapa 3:
    es_dominio: bool = True                   # False si la pregunta es OOD
    tipo: Literal["simple","comparacion_lineas","comparacion_periodos"] = "simple"
    rangos_temporales: list[RangoTemporal] = []  # solo en comparacion_periodos
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

### Cómo correr los tests (Etapa 2)

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

---

## Etapa 3 — Motor de consulta del agente

Ejecuta el `Intent` de Etapa 2 contra los parquets de Etapa 1, recalcula ratios correctamente y genera una respuesta en lenguaje natural usando Gemini (`gemini-2.5-flash`).

### Arquitectura

```
pregunta (español)
      │
      ▼
┌─────────────────┐
│  semantica.parse │  Etapa 2: reglas + Gemini → Intent
└─────────────────┘
      │
      ▼
┌──────────────────┐
│  OOD check       │── ood ──▶ Respuesta(tipo="ood") + 3 sugerencias
│  es_probable_ood │
└──────────────────┘
      │ dominio
      ▼
┌──────────────────┐
│  Cobertura       │── fuera de rango ──▶ Respuesta(tipo="sin_datos")
│  validación      │
└──────────────────┘
      │ válido
      ▼
┌──────────────────────────────────┐
│  Ejecutor                        │
│  simple → ejecutar_simple()      │  filtros, agregación,
│  comparación → ejecutar_compar() │  ratio recalculado
└──────────────────────────────────┘
      │
      ▼
┌──────────────────┐
│  generador_nl    │  Gemini grounded → texto_nl
│  fallback: plant.│  plantillas si sin LLM
└──────────────────┘
      │
      ▼
   Respuesta (tipo, texto_nl, dato|comparacion, intent, metadata)
```

### Modelo Respuesta

```python
class Respuesta(BaseModel):
    tipo: Literal["dato", "comparacion", "ood", "sin_datos", "error"]
    texto_nl: str          # siempre presente (nunca None)
    intent: Any            # Intent de Etapa 2 (trazabilidad)
    dato: Dato | None      # si tipo=="dato"
    comparacion: Comparacion | None  # si tipo=="comparacion"
    sugerencias: list[str] = []      # si tipo in {"ood","sin_datos"}
    advertencias: list[str] = []
    metadata: Metadata     # tabla, cobertura, fuente_nl, tiempo_ms
```

### Uso básico (Python)

```python
from motor import responder

# Dato simple
r = responder("Cuántos pasajeros tuvo Mitre en 2023")
print(r.tipo)           # "dato"
print(r.texto_nl)       # "La línea Mitre registró 39.5M pasajeros (suma) en 2023-01 a 2023-12."
print(r.dato.valor)     # 39515170.0
print(r.dato.unidad)    # "pasajeros"

# Comparación
r = responder("Comparar puntualidad Mitre vs Sarmiento en 2023")
print(r.tipo)                     # "comparacion"
print(r.comparacion.ranking)      # ["Mitre", "Sarmiento"]  (mejor primero)
print(r.comparacion.diferencias)  # [{"entre": ["Mitre","Sarmiento"], "delta": 0.05}]

# Fuera de dominio
r = responder("Cuál es la capital de Francia")
print(r.tipo)           # "ood"
print(r.sugerencias)    # 3 preguntas de ejemplo

# Sin datos en cobertura
r = responder("Datos del Mitre en 1985")
print(r.tipo)           # "sin_datos"
print(r.texto_nl)       # mensaje con cobertura disponible

# Acceso a metadatos
print(r.metadata.fuente_nl)   # "gemini" | "plantilla" | "ninguna"
print(r.metadata.tiempo_ms)   # tiempo total en ms
```

### CLI

```bash
# Respuesta en texto plano
python -m motor "Cuántos pasajeros tuvo Mitre en 2023"

# JSON estructurado (Respuesta completa)
python -m motor "Pasajeros Mitre 2023" --json

# Debug: muestra intent, dato y metadata
python -m motor "Pasajeros Mitre 2023" --debug

# Sin LLM para NL (modo offline, plantillas determinísticas)
python -m motor "Pasajeros Mitre 2023" --sin-llm-nl

# Forzar parser de reglas (sin Gemini para parsing)
python -m motor "Pasajeros Mitre 2023" --solo-reglas
```

| Flag | Descripción |
|------|-------------|
| `--json` | Salida como JSON parseable (`Respuesta.model_dump_json()`) |
| `--debug` | Texto + `[TIPO]` `[INTENT]` `[DATO]` `[METADATA]` |
| `--sin-llm-nl` | Usa plantillas en lugar de Gemini para generar texto |
| `--solo-reglas` | Parseo sin LLM (rápido, sin API key) |

### Política OOD (fuera de dominio)

Cuando una pregunta no trata sobre ferrocarriles/AMBA, el motor devuelve `tipo="ood"` con 3 preguntas de ejemplo:

- *¿Cuántos pasajeros transportó el Mitre en 2023?*
- *¿Cuál fue la puntualidad de la red ferroviaria en 2022?*
- *¿Cómo varió la recaudación del Sarmiento en el último año disponible?*

La detección OOD combina el flag `es_dominio` del parser semántico (Etapa 2) con una heurística defensiva en el motor.

### Manejo de cobertura

Cuando la consulta cae fuera de la cobertura disponible, el motor devuelve `tipo="sin_datos"` con un mensaje que cita el rango disponible:

> "No tengo datos para el período solicitado. Cobertura disponible: 1993-01 a 2026-03 para linea_mensual."

Caso especial: Tren de la Costa tiene datos de regularidad desde mayo 2015.

### Generación de lenguaje natural

- **Modelo:** `gemini-2.5-flash` con `temperature=0.1`
- **Grounding:** la respuesta usa EXCLUSIVAMENTE los números del bloque `DATOS` (el modelo nunca inventa valores)
- **Fallback:** si no hay `GEMINI_API_KEY` o Gemini falla → plantillas determinísticas en español rioplatense
- **`fuente_nl`** en `metadata`: `"gemini"` | `"plantilla"` | `"ninguna"`

### Cómo correr los tests (Etapa 3)

```bash
# Todos los tests (Etapas 1, 2 y 3)
pytest tests/ -v

# Solo tests del motor
pytest tests/test_almacen.py tests/test_cobertura.py tests/test_ejecutor.py \
       tests/test_ejecutor_comparacion.py tests/test_generador_nl.py \
       tests/test_plantillas.py tests/test_ood.py tests/test_orquestador.py \
       tests/test_cli.py tests/test_motor_integracion.py -v

# Gold set motor (16 casos: dato, comparacion, ood, sin_datos)
pytest tests/test_motor_integracion.py -v

# Tests con Gemini real (requiere GEMINI_API_KEY)
GEMINI_API_KEY="tu-clave" pytest tests/ -v -m gemini
```

---

## Etapa 4 — Interfaz web

Capa de interacción pública del agente: una aplicación web que expone el motor de consulta a través de una API REST y sirve un frontend HTML/JS vanilla con Tailwind CDN.

### Objetivo

Permitir a cualquier visitante consultar datos ferroviarios CNRT en español desde el navegador, sin instalar nada ni tocar código, usando el mismo motor de Etapa 3 como backend.

### Arquitectura

```
Browser (HTML + JS vanilla + Tailwind CDN)
        │  POST /api/preguntar {pregunta}
        ▼
FastAPI  web/app.py
  ├── GET  /              → index.html
  ├── GET  /healthz       → {"status":"ok"}
  ├── GET  /api/ejemplos  → 6 preguntas curadas
  ├── GET  /api/cobertura → rango de datos + Tren de la Costa
  └── POST /api/preguntar → motor.responder() [rate limit 8/min]
        │
        ▼
motor.responder(pregunta) → Respuesta
```

### Endpoints

| Ruta | Método | Descripción |
|---|---|---|
| `/` | GET | Sirve la interfaz web (index.html) |
| `/healthz` | GET | Health check para Render |
| `/api/ejemplos` | GET | 6 preguntas de ejemplo |
| `/api/cobertura` | GET | Rango temporal + casos especiales |
| `/api/preguntar` | POST | Consulta al motor (rate limit: 8/min por IP) |

### Cómo correr la web localmente

```bash
pip install -r requirements.txt
uvicorn web.app:app --reload --port 8000
# Abrir http://localhost:8000
```

**URL del deploy público:** _(pendiente de deploy en Render)_

### Rate limit y fallback

El endpoint `/api/preguntar` aplica un rate limit de 8 req/min por IP (via `slowapi`). Cuando Gemini no está disponible, el motor usa plantillas determinísticas como fallback offline transparente: la API responde igual, solo cambia `metadata.fuente_nl` de `"gemini"` a `"plantilla"`.

### Cómo correr los tests (Etapa 4)

```bash
pytest tests/test_web_app.py tests/test_web_rate_limit.py -v
```

---

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
  vocabulario.py    # cargar_vocabulario()
  fechas.py         # extraer_fecha()
  parser_reglas.py  # parse() determinístico
  parser_llm.py     # GeminiBackend, StubBackend
  parser.py         # orquestador híbrido
  __init__.py       # expone parse(), Intent, RangoTemporal
  evaluacion/
    gold_set.json   # 35 preguntas curadas
    run_eval.py     # mide accuracy por componente
motor/              # Etapa 3: motor de consulta
  __init__.py       # API pública: responder(), Respuesta, etc.
  __main__.py       # CLI: python -m motor "pregunta"
  respuesta.py      # modelos Pydantic (Respuesta, Dato, Comparacion, etc.)
  almacen.py        # singleton lazy de DataFrames parquet
  cobertura.py      # validadores de cobertura temporal
  ejecutor.py       # ejecutar_simple() con recálculo de ratios
  ejecutor_comparacion.py  # ejecutar_comparacion()
  generador_nl.py   # Gemini grounded + fallback plantillas
  plantillas.py     # templates determinísticos (modo offline)
  ood.py            # detección OOD + sugerencias canónicas
  orquestador.py    # pipeline responder()
web/              # Etapa 4: interfaz web
  app.py            # FastAPI: rutas y servidor
  rate_limit.py     # slowapi limiter (8 req/min por IP)
  ejemplos.py       # 6 preguntas curadas para /api/ejemplos
  cobertura_api.py  # lógica de /api/cobertura
  static/
    index.html      # frontend (HTML + JS vanilla + Tailwind CDN)
    styles.css      # estilos adicionales
    app.js          # lógica cliente
tests/
  # Etapa 2
  test_normalizacion.py
  test_vocabulario.py
  test_fechas.py
  test_parser_reglas.py
  test_parser_helpers.py
  test_parser_integracion.py
  # Etapa 3
  test_almacen.py
  test_cobertura.py
  test_ejecutor.py
  test_ejecutor_comparacion.py
  test_generador_nl.py
  test_plantillas.py
  test_ood.py
  test_orquestador.py
  test_cli.py
  test_motor_integracion.py
  gold_set_motor.json   # 16 casos: dato, comparacion, ood, sin_datos
  # Etapa 4
  test_web_app.py
  test_web_rate_limit.py
Dockerfile
render.yaml
README.md
requirements.txt
```
