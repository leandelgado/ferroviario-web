"""
Tests for the rate-limiting behaviour of POST /api/preguntar.

slowapi uses an in-memory storage whose counter persists across requests.
Both autouse fixtures below run for every test:
  - mock_responder: avoids calling the real motor for 9 requests
  - reset_rate_limit: resets slowapi's counter so each test starts clean
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Reset slowapi's in-memory storage before each test."""
    from web.rate_limit import limiter
    limiter._storage.reset()
    yield


@pytest.fixture(autouse=True)
def mock_responder():
    """Replace motor.responder with a lightweight stub for all rate-limit tests."""
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
    stub = Respuesta(
        tipo="dato",
        texto_nl="ok",
        intent=stub_intent,
        metadata=Metadata(fuente_nl="plantilla"),
    )
    with patch("web.app.responder", return_value=stub):
        yield


@pytest.fixture
def client():
    """Fresh TestClient for each test (shares the already-started app)."""
    from web.app import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_rate_limit_permite_8_requests(client):
    """8 consecutive POSTs should all succeed (2xx)."""
    for i in range(8):
        resp = client.post("/api/preguntar", json={"pregunta": "pasajeros Mitre 2023"})
        assert resp.status_code in (200, 201), (
            f"Request {i + 1} expected 2xx, got {resp.status_code}"
        )


def test_rate_limit_bloquea_9o(client):
    """After 8 requests, the 9th must return 429."""
    for _ in range(8):
        client.post("/api/preguntar", json={"pregunta": "pasajeros Mitre 2023"})

    resp = client.post("/api/preguntar", json={"pregunta": "pasajeros Mitre 2023"})
    assert resp.status_code == 429


def test_rate_limit_handler_estructura(client):
    """The 429 response body must match the custom error format."""
    for _ in range(8):
        client.post("/api/preguntar", json={"pregunta": "pasajeros Mitre 2023"})

    resp = client.post("/api/preguntar", json={"pregunta": "pasajeros Mitre 2023"})
    assert resp.status_code == 429
    body = resp.json()
    assert body == {
        "detail": "Demasiadas consultas. Intentá en un minuto.",
        "limite": "8/minuto",
    }
