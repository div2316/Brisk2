"""FastAPI application factory."""
from __future__ import annotations

import logging
import secrets
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings, get_settings
from .auth import LoginThrottle
from .db import Database
from .schemas import AssessRequest, RecordsRequest
from .service import ArtifactError, CVDModelService
from .web import build_router

log = logging.getLogger("cvd.api")


def create_app(settings: Settings | None = None, service: CVDModelService | None = None,
               db: Database | None = None) -> FastAPI:
    settings = settings or get_settings()
    db = db or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = service
        app.state.load_error = None
        if app.state.service is None:
            try:
                app.state.service = CVDModelService(settings)
            except ArtifactError as exc:
                app.state.load_error = str(exc)
                log.error("Model failed to load: %s", exc)
        if settings.api_key is None:
            log.warning("API_KEY is not set: the API is unauthenticated.")
        yield

    app = FastAPI(title="Distribution-Shift-Aware CVD Risk API", version=__version__, lifespan=lifespan)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                           allow_credentials=True, allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                           allow_headers=["X-API-Key", "X-CSRF-Token", "Content-Type"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        log.info("%s %s -> %s %.1fms rid=%s", request.method, request.url.path,
                 response.status_code, (time.perf_counter() - start) * 1000, rid)
        return response

    @app.exception_handler(ValueError)
    async def value_error(_: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    def auth(request: Request):
        if settings.api_key is None:
            return
        supplied = request.headers.get("X-API-Key", "")
        if not secrets.compare_digest(supplied.encode(), settings.api_key.encode()):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    def get_service(request: Request) -> CVDModelService:
        svc = request.app.state.service
        if svc is None:
            raise HTTPException(status_code=503, detail=request.app.state.load_error or "Model not loaded")
        return svc

    def check_size(n: int):
        if n > settings.max_records:
            raise HTTPException(status_code=413, detail=f"Maximum {settings.max_records} records per request")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/ready")
    def ready(request: Request):
        if request.app.state.service is None:
            return JSONResponse(status_code=503, content={"status": "not_ready",
                                                          "detail": request.app.state.load_error})
        return {"status": "ready"}

    @app.get("/v1/metadata", dependencies=[Depends(auth)])
    def metadata(svc: CVDModelService = Depends(get_service)):
        return svc.metadata()

    @app.get("/v1/schema", dependencies=[Depends(auth)])
    def schema(svc: CVDModelService = Depends(get_service)):
        return svc.schema()

    @app.post("/v1/predict", dependencies=[Depends(auth)])
    def predict(body: RecordsRequest, svc: CVDModelService = Depends(get_service)):
        check_size(len(body.records))
        return svc.predict(body.records)

    @app.post("/v1/monitor", dependencies=[Depends(auth)])
    def monitor(body: RecordsRequest, svc: CVDModelService = Depends(get_service)):
        check_size(len(body.records))
        return svc.monitor_batch(body.records)

    @app.post("/v1/assess", dependencies=[Depends(auth)])
    def assess(body: AssessRequest, svc: CVDModelService = Depends(get_service)):
        check_size(len(body.records))
        return svc.assess(body.records, body.labels)

    app.include_router(build_router(settings, db, LoginThrottle()))
    return app


def get_app() -> FastAPI:
    return create_app()
