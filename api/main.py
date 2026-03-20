"""
api/main.py
============
FastAPI application entry point.

WHO OWNS THIS: Backend team
"""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import get_settings
from api.auth import router as auth_router
from api.routes.detect_routes import router as detect_router
from api.routes.dashboard_routes import router as dashboard_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger   = logging.getLogger("sentinel.main")
settings = get_settings()

app = FastAPI(
    title="SENTINEL-AI",
    version="0.1.0",
    description="AI-native threat intelligence platform — Hack4Impact 2026",
    docs_url="/docs",
    redoc_url=None,
)

# ── CORS: strict allowlist — never * ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Error handlers: no stack traces to client ─────────────────────────────────
@app.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code,
                        content={"detail": exc.detail},
                        headers=getattr(exc, "headers", None))

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router,      prefix="/api/v1/auth")
app.include_router(detect_router,    prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1/dashboard")

@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "version": app.version}