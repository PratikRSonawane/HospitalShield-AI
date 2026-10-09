"""FastAPI application: structured errors, CORS, body-size guard (S3).

Every 4xx uses the documented shape
{"error": {"code", "message", "details": [{"field", "reason"}]}}.
The catch-all 500 returns a generic body with a request id, never a trace.
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routers import hospitals, meta, scenarios, simulations, tier2
from app.simulation import MODEL_VERSION, InfeasibleInterventionError, SimulationValidationError

logger = logging.getLogger("hospitalshield")
MAX_BODY_BYTES = 1_000_000

ROOT = Path(__file__).resolve().parents[2]


def _error_payload(code: str, message: str, details: list[dict[str, str]] | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


def _pydantic_details(errors: list[dict]) -> list[dict[str, str]]:
    details = []
    for err in errors:
        field = ".".join(str(loc) for loc in err.get("loc", []) if loc != "body") or "body"
        details.append({"field": field, "reason": err.get("msg", "invalid value")})
    return details


def create_app() -> FastAPI:
    app = FastAPI(
        title="HospitalShield AI API",
        version=MODEL_VERSION,
        description="Climate-resilient hospital digital twin (HC-03 planning prototype, synthetic data).",
    )

    origins = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
    app_env = os.environ.get("APP_ENV", "development")
    if app_env == "production" and "*" in origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS must not contain * when APP_ENV=production")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def body_size_guard(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_BODY_BYTES:
            return JSONResponse(status_code=413,
                                content=_error_payload("PAYLOAD_TOO_LARGE", "request body exceeds 1 MB"))
        response = await call_next(request)
        response.headers["x-request-id"] = response.headers.get("x-request-id", str(uuid.uuid4())[:8])
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content=_error_payload(
            "VALIDATION_ERROR", "request payload failed validation", _pydantic_details(exc.errors())))

    @app.exception_handler(SimulationValidationError)
    async def engine_validation_handler(request: Request, exc: SimulationValidationError):
        return JSONResponse(status_code=422, content=_error_payload(
            "VALIDATION_ERROR", "scenario validation failed", [i.to_dict() for i in exc.issues]))

    @app.exception_handler(InfeasibleInterventionError)
    async def infeasible_handler(request: Request, exc: InfeasibleInterventionError):
        return JSONResponse(status_code=422, content=_error_payload(
            "INFEASIBLE_INTERVENTION", "one or more interventions are infeasible",
            [i.to_dict() for i in exc.issues]))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # structured detail dicts (e.g. hospital upload validation) pass through
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE",
                415: "UNSUPPORTED_MEDIA_TYPE"}.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(status_code=exc.status_code,
                            content=_error_payload(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def catch_all_handler(request: Request, exc: Exception):
        request_id = str(uuid.uuid4())[:8]
        logger.exception("unhandled error request_id=%s", request_id)
        return JSONResponse(status_code=500, content=_error_payload(
            "INTERNAL_ERROR", f"unexpected server error (request id {request_id})"))

    app.include_router(meta.router)
    app.include_router(scenarios.router)
    app.include_router(simulations.router)
    app.include_router(tier2.router)
    app.include_router(hospitals.router)
    return app


app = create_app()
