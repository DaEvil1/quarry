"""First-run setup, signing in and out, and managing passkeys and recovery codes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Passkey, User
from ..passkeys import PasskeyError, begin_login, begin_registration, finish_login, finish_registration, take_challenge
from ..security import (
    SESSION_COOKIE,
    end_session,
    new_recovery_codes,
    recovery_codes_left,
    start_session,
    tokens_match,
    use_recovery_code,
)
from .deps import clear_session_cookie, current_user, rate_limited, set_session_cookie

router = APIRouter(prefix="/api")


def _agent(request: Request) -> str:
    return request.headers.get("user-agent", "")


def _has_users(db: Session) -> bool:
    return bool(db.scalar(select(exists().where(User.id.isnot(None)))))


class Answer(BaseModel):
    challenge_id: str
    credential: dict[str, Any]


class NewPasskey(Answer):
    label: str = Field(default="Passkey", max_length=100)


# setup ---------------------------------------------------------------------------------------------------------


class SetupStart(BaseModel):
    token: str = Field(max_length=500)
    display_name: str = Field(min_length=1, max_length=100)


@router.get("/setup")
def setup_status(db: Session = Depends(get_db)) -> dict[str, bool]:
    return {"needed": not _has_users(db), "enabled": bool(get_settings().setup_token)}


@router.post("/setup/begin", dependencies=[Depends(rate_limited)])
def setup_begin(body: SetupStart, db: Session = Depends(get_db)) -> dict[str, Any]:
    if _has_users(db):
        raise HTTPException(409, "Quarry is already set up. Sign in instead.")
    token = get_settings().setup_token
    if not token:
        raise HTTPException(403, "Setup is turned off. Set QUARRY_SETUP_TOKEN on the server and restart.")
    if not tokens_match(body.token.strip(), token):
        raise HTTPException(403, "That setup token is not right.")
    name = body.display_name.strip()
    if not name:
        raise HTTPException(422, "Enter your name.")
    out = begin_registration(db, "setup", uuid.uuid4(), name, data={"display_name": name})
    db.commit()
    return out


@router.post("/setup/finish", dependencies=[Depends(rate_limited)])
def setup_finish(body: NewPasskey, request: Request, response: Response,
                 db: Session = Depends(get_db)) -> dict[str, Any]:
    # one setup at a time, so two browsers racing cannot both create a first user
    db.execute(text("SELECT pg_advisory_xact_lock(7712001)"))
    if _has_users(db):
        raise HTTPException(409, "Quarry is already set up. Sign in instead.")
    try:
        ch = take_challenge(db, body.challenge_id, "setup")
        reg = finish_registration(ch, body.credential)
    except PasskeyError as e:
        db.commit()
        raise HTTPException(400, str(e)) from None
    assert ch.user_id is not None
    user = User(id=ch.user_id, display_name=str(ch.data.get("display_name") or "Writer"))
    db.add(user)
    db.flush()
    db.add(Passkey(user_id=user.id, credential_id=reg.credential_id, public_key=reg.public_key,
                   sign_count=reg.sign_count, transports=reg.transports, label=body.label.strip() or "Passkey"))
    codes = new_recovery_codes(db, user.id)
    token = start_session(db, user.id, _agent(request))
    db.commit()
    set_session_cookie(response, token)
    return {"recovery_codes": codes}


# sign in and out -----------------------------------------------------------------------------------------------


class RecoverIn(BaseModel):
    code: str = Field(max_length=50)


@router.post("/auth/login/begin", dependencies=[Depends(rate_limited)])
def login_begin(db: Session = Depends(get_db)) -> dict[str, Any]:
    out = begin_login(db)
    db.commit()
    return out


@router.post("/auth/login/finish", dependencies=[Depends(rate_limited)])
def login_finish(body: Answer, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    try:
        ch = take_challenge(db, body.challenge_id, "login")
        pk = finish_login(db, ch, body.credential)
    except PasskeyError as e:
        db.commit()
        raise HTTPException(400, str(e)) from None
    token = start_session(db, pk.user_id, _agent(request))
    db.commit()
    set_session_cookie(response, token)
    return {"ok": True}


@router.post("/auth/recover", dependencies=[Depends(rate_limited)])
def recover(body: RecoverIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    user_id = use_recovery_code(db, body.code)
    if user_id is None:
        raise HTTPException(400, "That code is not valid or has already been used.")
    token = start_session(db, user_id, _agent(request))
    db.commit()
    set_session_cookie(response, token)
    return {"codes_left": recovery_codes_left(db, user_id)}


@router.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get(SESSION_COOKIE, "")
    if token:
        end_session(db, token)
        db.commit()
    clear_session_cookie(response)
    return {"ok": True}


# passkeys ------------------------------------------------------------------------------------------------------


class PasskeyOut(BaseModel):
    id: uuid.UUID
    label: str
    created_at: datetime
    last_used_at: datetime | None


class PasskeyRename(BaseModel):
    label: str = Field(min_length=1, max_length=100)


def _own_passkey(db: Session, user: User, passkey_id: uuid.UUID) -> Passkey:
    pk = db.get(Passkey, passkey_id)
    if pk is None or pk.user_id != user.id:
        raise HTTPException(404, "No such passkey.")
    return pk


@router.get("/auth/passkeys")
def list_passkeys(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[PasskeyOut]:
    rows = db.scalars(select(Passkey).where(Passkey.user_id == user.id).order_by(Passkey.created_at)).all()
    return [PasskeyOut(id=p.id, label=p.label, created_at=p.created_at, last_used_at=p.last_used_at) for p in rows]


@router.post("/auth/passkeys/begin")
def add_passkey_begin(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    existing = list(db.scalars(select(Passkey).where(Passkey.user_id == user.id)).all())
    out = begin_registration(db, "add_passkey", user.id, user.display_name, existing)
    db.commit()
    return out


@router.post("/auth/passkeys/finish", status_code=201)
def add_passkey_finish(body: NewPasskey, user: User = Depends(current_user),
                       db: Session = Depends(get_db)) -> PasskeyOut:
    try:
        ch = take_challenge(db, body.challenge_id, "add_passkey")
        if ch.user_id != user.id:
            raise PasskeyError("This passkey request belongs to someone else.")
        reg = finish_registration(ch, body.credential)
    except PasskeyError as e:
        db.commit()
        raise HTTPException(400, str(e)) from None
    pk = Passkey(user_id=user.id, credential_id=reg.credential_id, public_key=reg.public_key,
                 sign_count=reg.sign_count, transports=reg.transports, label=body.label.strip() or "Passkey")
    db.add(pk)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That passkey is already registered.") from None
    return PasskeyOut(id=pk.id, label=pk.label, created_at=pk.created_at, last_used_at=pk.last_used_at)


@router.patch("/auth/passkeys/{passkey_id}")
def rename_passkey(passkey_id: uuid.UUID, body: PasskeyRename, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> PasskeyOut:
    pk = _own_passkey(db, user, passkey_id)
    pk.label = body.label.strip()
    db.commit()
    return PasskeyOut(id=pk.id, label=pk.label, created_at=pk.created_at, last_used_at=pk.last_used_at)


@router.delete("/auth/passkeys/{passkey_id}", status_code=204)
def delete_passkey(passkey_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    pk = _own_passkey(db, user, passkey_id)
    count = db.scalar(select(func.count()).select_from(Passkey).where(Passkey.user_id == user.id))
    if count == 1:
        raise HTTPException(409, "This is your only passkey. Add another before removing it.")
    db.delete(pk)
    db.commit()


# recovery codes ------------------------------------------------------------------------------------------------


@router.get("/auth/recovery-codes")
def recovery_status(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, int]:
    return {"left": recovery_codes_left(db, user.id)}


@router.post("/auth/recovery-codes")
def regenerate_recovery_codes(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    codes = new_recovery_codes(db, user.id)
    db.commit()
    return {"recovery_codes": codes}
