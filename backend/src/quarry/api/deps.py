"""Shared request dependencies: the signed-in user, the session cookie and the auth rate limit."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import User
from ..security import SESSION_COOKIE, SESSION_DAYS, auth_limiter, find_session, touch_session


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        secure=get_settings().cookie_secure, samesite="strict", path="/")


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=get_settings().cookie_secure,
                           samesite="strict")


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limited(request: Request) -> None:
    auth_limiter.limit = get_settings().auth_rate_limit
    if not auth_limiter.allow(client_ip(request)):
        raise HTTPException(429, "Too many attempts. Wait a few minutes and try again.")


def current_user(request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE, "")
    s = find_session(db, token)
    if s is None:
        raise HTTPException(401, "Sign in to continue.")
    if touch_session(s):
        db.commit()
        set_session_cookie(response, token)
    user = db.get(User, s.user_id)
    if user is None:
        raise HTTPException(401, "Sign in to continue.")
    return user
