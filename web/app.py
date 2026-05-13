import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi.errors import RateLimitExceeded
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from motor import responder
from web.rate_limit import limiter
from web.ejemplos import EJEMPLOS
from web.cobertura_api import obtener_cobertura

_log = logging.getLogger(__name__)

_cobertura_cache: dict = {}

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        _cobertura_cache.update(obtener_cobertura())
    except Exception:
        _log.warning("No se pudo cargar cobertura al inicio; /api/cobertura devolverá vacío")
    yield


async def _custom_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Demasiadas consultas. Intentá en un minuto.", "limite": "8/minuto"},
    )


app = FastAPI(title="Agente ferroviario CNRT", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _custom_rate_limit_handler)
# Render routes requests through a proxy; trust forwarded headers from any upstream
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class PreguntaIn(BaseModel):
    pregunta: str = Field(min_length=3, max_length=500)


@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/api/ejemplos")
async def ejemplos():
    return EJEMPLOS


@app.get("/api/cobertura")
async def cobertura():
    return _cobertura_cache


@app.post("/api/preguntar")
@limiter.limit("8/minute")
async def preguntar(request: Request, body: PreguntaIn):
    try:
        r = responder(body.pregunta)
    except Exception:
        _log.exception("responder() raised unexpectedly — retrying offline")
        r = responder(body.pregunta, sin_llm_nl=True, forzar_reglas=True)
    return r.model_dump(mode="json")
