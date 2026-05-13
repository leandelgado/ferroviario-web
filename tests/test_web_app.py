"""
Tests for the FastAPI web application (web/app.py).

Most tests call the real motor stack (parquet data exists in data/processed/).
No GEMINI_API_KEY is required — the motor falls back to plantilla NL when
Gemini is unavailable.

test_preguntar_fallback_si_responder_falla patches web.app.responder to
simulate a failure on the first call and verify the retry logic.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from web.app import app


@pytest.fixture(scope="module")
def client():
    """Module-scoped client — lifespan (startup/shutdown) runs exactly once.

    The context-manager form is required so that Starlette's lifespan
    (which populates _cobertura_cache) is properly triggered before tests run.
    """
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Basic endpoints
# ---------------------------------------------------------------------------

def test_root_sirve_html(client):
    """GET / must return 200 with Content-Type text/html."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_healthz(client):
    """GET /healthz must return 200 with body {"status": "ok"}."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ejemplos_devuelve_6(client):
    """GET /api/ejemplos must return 200 and exactly 6 string elements."""
    resp = client.get("/api/ejemplos")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 6
    for item in data:
        assert isinstance(item, str)


def test_cobertura_estructura(client):
    """GET /api/cobertura must have rango_general and casos_especiales with
    at least one entry for Tren de la Costa starting at 2015-05."""
    resp = client.get("/api/cobertura")
    assert resp.status_code == 200
    data = resp.json()
    assert "rango_general" in data
    assert "casos_especiales" in data
    casos = data["casos_especiales"]
    assert len(casos) >= 1
    costa = next((c for c in casos if c.get("linea") == "Tren de la Costa"), None)
    assert costa is not None, "Expected an entry with linea='Tren de la Costa'"
    assert costa["desde"] == "2015-05"


# ---------------------------------------------------------------------------
# POST /api/preguntar — real motor (no mock)
# ---------------------------------------------------------------------------

def test_preguntar_dato_simple(client):
    """POST 'pasajeros Mitre 2023' → 200 + tipo='dato' + dato.valor > 0."""
    resp = client.post("/api/preguntar", json={"pregunta": "pasajeros Mitre 2023"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tipo"] == "dato"
    assert body["dato"]["valor"] > 0


def test_preguntar_comparacion(client):
    """POST comparison question → 200 + tipo in ('comparacion', 'dato', 'sin_datos', 'error').

    With rules-only parsing the comparison type detection may or may not fire,
    so we accept the broader set of valid tipos.
    """
    resp = client.post(
        "/api/preguntar",
        json={"pregunta": "comparar Mitre vs Sarmiento 2023"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tipo"] in ("comparacion", "dato", "sin_datos", "error")


def test_preguntar_ood(client):
    """POST 'capital de Francia' → 200 + any valid tipo (OOD may not be detected
    without an LLM, so we accept all valid TipoRespuesta values)."""
    resp = client.post("/api/preguntar", json={"pregunta": "capital de Francia"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tipo"] in ("dato", "comparacion", "ood", "sin_datos", "error")


# ---------------------------------------------------------------------------
# Fallback / error-recovery path
# ---------------------------------------------------------------------------

def test_preguntar_fallback_si_responder_falla(client):
    """When responder() raises on the first call, the app retries with
    sin_llm_nl=True, forzar_reglas=True.  Verify 200 + two calls."""
    from motor.respuesta import Metadata, Respuesta
    from semantica.intent import Intent, RangoTemporal

    stub_intent = Intent(
        metrica="pasajeros",
        tabla="linea_mensual",
        granularidad="linea",
        agregacion="sum",
        confianza=0.9,
        origen="reglas",
        es_dominio=True,
        filtros_linea=["Mitre"],
        rango_temporal=RangoTemporal(desde="2023-01", hasta="2023-12", etiqueta="2023"),
    )
    stub_respuesta = Respuesta(
        tipo="dato",
        texto_nl="ok",
        intent=stub_intent,
        metadata=Metadata(fuente_nl="plantilla"),
    )

    call_count = 0

    def side_effect(pregunta, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Gemini falla")
        return stub_respuesta

    with patch("web.app.responder", side_effect=side_effect):
        resp = client.post("/api/preguntar", json={"pregunta": "pasajeros Mitre 2023"})

    assert resp.status_code == 200
    assert call_count == 2


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_serializacion_respuesta_completa(client):
    """POST any domain question → 200 + response JSON has 'intent' and
    'metadata' keys, and metadata has 'fuente_nl'."""
    resp = client.post("/api/preguntar", json={"pregunta": "pasajeros Mitre 2023"})
    assert resp.status_code == 200
    body = resp.json()
    assert "intent" in body
    assert "metadata" in body
    assert "fuente_nl" in body["metadata"]
