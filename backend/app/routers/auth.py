import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User
from ..security import COOKIE, create_token, current_user, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
_attempts = defaultdict(list)          # ip -> timestamps (in memory, brute-force protection)


class LoginIn(BaseModel):
    email: str
    password: str


def _out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email}


@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "?")
    now = time.time()
    _attempts[ip] = [t for t in _attempts[ip] if now - t < 600]
    if len(_attempts[ip]) >= 10:
        raise HTTPException(429, "Too many login attempts. Try again in a few minutes.")
    user = db.scalar(select(User).where(User.email == data.email.strip().lower()))
    if not user or not verify_password(data.password, user.password_hash):
        _attempts[ip].append(now)
        raise HTTPException(401, "Invalid email or password")
    response.set_cookie(COOKIE, create_token(user.id), httponly=True, samesite="lax",
                        secure=settings.cookie_secure, max_age=settings.jwt_hours * 3600, path="/")
    return _out(user)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return _out(user)
