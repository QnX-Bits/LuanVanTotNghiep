from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..auth import DEMO_PASSCODE, USERS, clear_session, current_user, set_session, verify_csrf
from ..schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/demo-users")
def demo_users():
    return {"users": [{"key": key, "name": value["name"], "role": value["role"], "locale": value["locale"]} for key, value in USERS.items()]}


@router.get("/session")
def session(user: dict = Depends(current_user)):
    # Never expose internal user keys in Investor responses.
    return {"authenticated": True, "name": user["name"], "role": user["role"], "locale": user["locale"]}


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    if not hmac.compare_digest(payload.passcode.encode(), DEMO_PASSCODE.encode()):
        raise HTTPException(status_code=401, detail="Mã demo không chính xác")
    if payload.user_id not in USERS:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ demo")
    set_session(response, payload.user_id)
    user = USERS[payload.user_id]
    return {"authenticated": True, "name": user["name"], "role": user["role"], "locale": user["locale"]}


@router.post("/logout")
def logout(request: Request, response: Response, user: dict = Depends(current_user)):
    verify_csrf(request)
    clear_session(response)
    return {"authenticated": False}
