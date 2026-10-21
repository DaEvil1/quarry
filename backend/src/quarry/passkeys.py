"""WebAuthn ceremonies around py_webauthn.

Each ceremony has two halves. ``begin_*`` stores a one-time challenge and returns the browser options plus the
challenge id; ``finish_*`` takes the id and the browser's answer, verifies it and consumes the challenge.
Passkeys are discoverable (resident) credentials with user verification, so signing in needs no user name.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, options_to_json_dict
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .config import get_settings
from .models import AuthChallenge, Passkey
from .security import now

CHALLENGE_TTL = timedelta(minutes=5)
RP_NAME = "Quarry"


class PasskeyError(Exception):
    """The browser's answer did not check out. The message is safe to show."""


@dataclass
class Registered:
    credential_id: bytes
    public_key: bytes
    sign_count: int
    transports: list[str]


def _store(db: Session, purpose: str, challenge: bytes, user_id: uuid.UUID | None, data: dict | None = None) -> str:
    db.execute(delete(AuthChallenge).where(AuthChallenge.expires_at < now()))
    ch = AuthChallenge(purpose=purpose, challenge=challenge, user_id=user_id, data=data or {},
                       expires_at=now() + CHALLENGE_TTL)
    db.add(ch)
    db.flush()
    return str(ch.id)


def take_challenge(db: Session, challenge_id: str, purpose: str) -> AuthChallenge:
    """Fetch and delete a pending challenge; it can be answered once."""
    try:
        cid = uuid.UUID(challenge_id)
    except (ValueError, TypeError):
        raise PasskeyError("This sign-in attempt is not valid. Start again.") from None
    ch = db.get(AuthChallenge, cid)
    if ch is None or ch.purpose != purpose or ch.expires_at < now():
        raise PasskeyError("This sign-in attempt has expired. Start again.")
    db.delete(ch)
    db.flush()
    return ch


def begin_registration(db: Session, purpose: str, user_id: uuid.UUID, user_name: str,
                       existing: list[Passkey] | None = None, data: dict | None = None) -> dict[str, Any]:
    s = get_settings()
    opts = generate_registration_options(
        rp_id=s.rp_id,
        rp_name=RP_NAME,
        user_id=user_id.bytes,
        user_name=user_name,
        user_display_name=user_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        # the same authenticator should not be registered twice for one person
        exclude_credentials=[PublicKeyCredentialDescriptor(id=p.credential_id) for p in existing or []],
    )
    cid = _store(db, purpose, opts.challenge, user_id, data)
    return {"challenge_id": cid, "options": options_to_json_dict(opts)}


def finish_registration(challenge: AuthChallenge, credential: dict[str, Any]) -> Registered:
    s = get_settings()
    try:
        v = verify_registration_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=s.rp_id,
            expected_origin=s.origin,
            require_user_verification=True,
        )
    except (InvalidRegistrationResponse, ValueError, KeyError, TypeError) as e:
        raise PasskeyError("The passkey could not be registered.") from e
    transports = credential.get("response", {}).get("transports") or []
    return Registered(credential_id=v.credential_id, public_key=v.credential_public_key, sign_count=v.sign_count,
                      transports=[str(t)[:20] for t in transports if isinstance(t, str)][:8])


def begin_login(db: Session) -> dict[str, Any]:
    s = get_settings()
    opts = generate_authentication_options(rp_id=s.rp_id, user_verification=UserVerificationRequirement.REQUIRED)
    cid = _store(db, "login", opts.challenge, None)
    return {"challenge_id": cid, "options": options_to_json_dict(opts)}


def finish_login(db: Session, challenge: AuthChallenge, credential: dict[str, Any]) -> Passkey:
    s = get_settings()
    try:
        raw_id = base64url_to_bytes(str(credential.get("rawId") or credential.get("id") or ""))
    except (ValueError, TypeError):
        raise PasskeyError("That passkey is not recognised.") from None
    pk = db.scalars(select(Passkey).where(Passkey.credential_id == raw_id)).first()
    if pk is None:
        raise PasskeyError("That passkey is not recognised.")
    try:
        v = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=s.rp_id,
            expected_origin=s.origin,
            credential_public_key=pk.public_key,
            credential_current_sign_count=pk.sign_count,
            require_user_verification=True,
        )
    except (InvalidAuthenticationResponse, ValueError, KeyError, TypeError) as e:
        raise PasskeyError("The passkey could not be verified.") from e
    pk.sign_count = v.new_sign_count
    pk.last_used_at = now()
    return pk
