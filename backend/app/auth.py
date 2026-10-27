from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, HTTPException, Request, Response

DEMO_PASSCODE = os.getenv("DEMO_PASSCODE", "UEH2026")
SESSION_COOKIE = "pvn_demo_session"
CSRF_COOKIE = "pvn_csrf"
SESSION_TTL_SECONDS = 8 * 60 * 60
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() in {"1", "true", "yes"}
# Browsers drop SameSite=None cookies that are not Secure, so plain-HTTP localhost uses Lax.
COOKIE_SAMESITE = "none" if COOKIE_SECURE else "lax"
SESSION_SECRET = os.getenv("DEMO_SESSION_SECRET") or hashlib.sha256((DEMO_PASSCODE + ":portfoliovn-demo-session-v1").encode()).hexdigest()

USERS = {
    "an": {"name": "An Nguyễn", "role": "investor", "locale": "vi"},
    "binh": {"name": "Bình Trần", "role": "investor", "locale": "en"},
    "reviewer": {"name": "Hội đồng Reviewer", "role": "reviewer", "locale": "vi"},
    "admin": {"name": "Admin", "role": "admin", "locale": "vi"},
}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest())


def make_session(user_key: str, now: int | None = None) -> str:
    body = json.dumps({"u": user_key, "exp": (now or int(time.time())) + SESSION_TTL_SECONDS}, separators=(",", ":"))
    payload = _b64(body.encode())
    return f"{payload}.{_sign(payload)}"


def resolve_session(token: str | None, now: int | None = None) -> dict | None:
    if not token or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    try:
        info = json.loads(_unb64(payload))
        user_key = info["u"]
        expiry = int(info["exp"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
    if expiry < (now or int(time.time())) or user_key not in USERS:
        return None
    return {"key": user_key, **USERS[user_key]}


def set_session(response: Response, user_key: str) -> None:
    response.set_cookie(SESSION_COOKIE, make_session(user_key), max_age=SESSION_TTL_SECONDS, httponly=True, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/")
    csrf = _b64(os.urandom(24))
    response.set_cookie(CSRF_COOKIE, csrf, max_age=SESSION_TTL_SECONDS, httponly=False, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/")


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, httponly=True)
    response.delete_cookie(CSRF_COOKIE, path="/", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)


def current_user(request: Request) -> dict:
    user = resolve_session(request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_roles(*roles: str) -> Callable:
    def dependency(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Role does not allow this operation")
        return user
    return dependency


require_investor = require_roles("investor")
require_reviewer = require_roles("reviewer")
require_admin = require_roles("admin")
require_user = current_user


def verify_csrf(request: Request) -> None:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
