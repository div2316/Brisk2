"""Cookie-session JSON API used by the web UI (mounted under /api).

httpOnly session cookie (only its SHA-256 is stored) + CSRF token echoed in X-CSRF-Token on non-GET requests.
This module does not use `from __future__ import annotations` so FastAPI can resolve the closure annotations.
"""
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .auth import (LoginThrottle, hash_password, validate_email, validate_name,
                   validate_password, verify_password)
from .db import Database, DuplicateEmail
from .report import build_pdf
from .schemas import ForgotRequest, LoginRequest, ResetRequest, SignUpRequest
from .utils import to_builtin

log = logging.getLogger("brisk.api")
SESSION_COOKIE = "cvd_session"
CSRF_COOKIE = "cvd_csrf"
_DUMMY_HASH = hash_password("dummy-password-1")


def build_router(settings, db: Database, throttle: LoginThrottle) -> APIRouter:
    router = APIRouter(prefix="/api")

    def set_cookies(response: Response, token: str, csrf: str):
        age = settings.session_days * 86400
        response.set_cookie(SESSION_COOKIE, token, max_age=age, httponly=True, samesite="lax",
                            secure=settings.cookie_secure, path="/")
        response.set_cookie(CSRF_COOKIE, csrf, max_age=age, httponly=False, samesite="lax",
                            secure=settings.cookie_secure, path="/")

    def clear_cookies(response: Response):
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")

    def current(request: Request) -> dict:
        session = db.get_session(request.cookies.get(SESSION_COOKIE))
        if not session:
            raise HTTPException(status_code=401, detail="Please sign in.")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            supplied = request.headers.get("X-CSRF-Token", "")
            if not hmac.compare_digest(supplied.encode(), session["csrf"].encode()):
                raise HTTPException(status_code=403, detail="Security check failed. Refresh and try again.")
        return session

    def service(request: Request):
        svc = request.app.state.service
        if svc is None:
            raise HTTPException(status_code=503, detail=request.app.state.load_error or "The prediction service is not ready.")
        return svc

    def public_user(s: dict) -> dict:
        return {"id": s["user_id"], "name": s["name"], "email": s["email"]}

    # ------------------------------------------------------------------ health / auth
    @router.get("/health")
    def health(request: Request):
        return {"status": "ok", "model_loaded": request.app.state.service is not None}

    @router.post("/auth/signup", status_code=201)
    def signup(body: SignUpRequest):
        if not body.accept_terms:
            raise HTTPException(status_code=422, detail="You must accept the research-use terms.")
        try:
            name, email = validate_name(body.name), validate_email(body.email)
            password = validate_password(body.password)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        try:
            user_id = db.create_user(email, name, hash_password(password))
        except DuplicateEmail:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        db.audit(user_id, "signup")
        return {"ok": True}

    @router.post("/auth/login")
    def login(body: LoginRequest, request: Request, response: Response):
        ip = request.client.host if request.client else "?"
        key = f"{body.email.strip().lower()}|{ip}"
        wait = throttle.blocked(key)
        if wait:
            raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {wait} seconds.")
        user = db.get_user_by_email(body.email)
        ok = verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)
        if not (user and ok):
            throttle.failure(key)
            raise HTTPException(status_code=401, detail="Incorrect email or password.")
        throttle.success(key)
        token, csrf = db.create_session(user["id"], settings.session_days)
        set_cookies(response, token, csrf)
        db.audit(user["id"], "login")
        return {"user": {"id": user["id"], "name": user["name"], "email": user["email"]}}

    @router.post("/auth/logout")
    def logout(request: Request, response: Response):
        db.delete_session(request.cookies.get(SESSION_COOKIE))
        clear_cookies(response)
        return {"ok": True}

    @router.get("/auth/me")
    def me(request: Request):
        session = db.get_session(request.cookies.get(SESSION_COOKIE))
        return {"user": public_user(session) if session else None}

    @router.post("/auth/forgot-password")
    def forgot(body: ForgotRequest):
        user = db.get_user_by_email(body.email) if body.email else None
        if user:
            token = db.create_reset_token(user["id"])
            # No e-mail service in this prototype: the reset link is written to the server log.
            log.warning("PASSWORD RESET LINK for %s: /reset-password?token=%s", user["email"], token)
            db.audit(user["id"], "password_reset_requested")
        return {"ok": True}  # same answer whether or not the account exists

    @router.post("/auth/reset-password")
    def reset(body: ResetRequest):
        try:
            password = validate_password(body.password)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        user_id = db.consume_reset_token(body.token or "")
        if not user_id:
            raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
        db.set_password(user_id, hash_password(password))
        db.audit(user_id, "password_reset")
        return {"ok": True}

    # ------------------------------------------------------------------ form + prediction
    @router.get("/schema")
    def schema(_: dict = Depends(current), svc=Depends(service)):
        return {"fields": svc.form_schema()}

    @router.post("/predict")
    def predict(body: dict, session: dict = Depends(current), svc=Depends(service)):
        try:
            pred = svc.predict_one(body)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        patient = {k: body[k] for k in svc.features}
        aid = db.add_assessment(session["user_id"], pred["risk_pct"], pred["stratum"],
                                {"patient": patient, "prediction": pred})
        db.audit(session["user_id"], "assessment", f"#{aid}")
        return to_builtin({"id": aid, **pred})

    @router.get("/patient")
    def latest(session: dict = Depends(current)):
        row = db.latest_assessment(session["user_id"])
        if not row:
            return {"patient": None, "prediction": None}
        return {"id": row["id"], "created_at": row["created_at"], **row["payload"]}

    @router.get("/reliability")
    def reliability(session: dict = Depends(current), svc=Depends(service)):
        row = db.latest_assessment(session["user_id"])
        info = svc.model_info()
        if not row:
            return {"available": False, "model": info}
        res = svc.reliability(row["payload"]["patient"], db.list_patients(session["user_id"]))
        return to_builtin({"available": True, "model": info, **res})

    @router.get("/assessments")
    def history(session: dict = Depends(current)):
        return {"items": db.list_assessments(session["user_id"], 100)}

    @router.get("/assessments/{assessment_id}")
    def one(assessment_id: int, session: dict = Depends(current)):
        row = db.get_assessment(session["user_id"], assessment_id)
        if not row:
            raise HTTPException(status_code=404, detail="Assessment not found.")
        return {"id": row["id"], "created_at": row["created_at"], **row["payload"]}

    @router.get("/report/{assessment_id}.pdf")
    def report(assessment_id: int, session: dict = Depends(current)):
        row = db.get_assessment(session["user_id"], assessment_id)
        if not row:
            raise HTTPException(status_code=404, detail="Assessment not found.")
        pdf = build_pdf({"name": session["name"], "email": session["email"]}, row)
        db.audit(session["user_id"], "report_download", f"#{assessment_id}")
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="BRISK2_report_{assessment_id}.pdf"'})

    @router.delete("/patient")
    def clear(session: dict = Depends(current)):
        n = db.delete_assessments(session["user_id"])
        db.audit(session["user_id"], "clear_assessments", f"{n} deleted")
        return {"deleted": n}

    # ------------------------------------------------------------------ account
    @router.get("/audit")
    def audit(session: dict = Depends(current)):
        return {"items": db.list_audit(session["user_id"])}

    @router.delete("/account")
    def delete_account(response: Response, session: dict = Depends(current)):
        db.delete_user(session["user_id"])
        clear_cookies(response)
        return {"ok": True}

    return router
