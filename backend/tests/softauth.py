"""A software passkey: answers WebAuthn registration and sign-in requests the way a phone or laptop would.

It produces real ES256 signatures and "none" attestation, so the server's verification code runs unmocked.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import struct
from typing import Any

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

# authenticator data flags
UP, UV, AT = 0x01, 0x04, 0x40


class SoftPasskey:
    def __init__(self, origin: str = "http://testserver") -> None:
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = secrets.token_bytes(16)
        self.sign_count = 0
        self.user_handle: bytes | None = None

    def _client_data(self, kind: str, challenge: str) -> bytes:
        return json.dumps({"type": kind, "challenge": challenge, "origin": self.origin,
                           "crossOrigin": False}, separators=(",", ":")).encode()

    def _cose_key(self) -> bytes:
        nums = self.key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")})

    def register(self, options: dict[str, Any], *, rp_id: str | None = None) -> dict[str, Any]:
        """Answer ``navigator.credentials.create()`` for the given options (as the server sends them)."""
        rp = rp_id or options["rp"]["id"]
        self.user_handle = base64url_to_bytes(options["user"]["id"])
        client_data = self._client_data("webauthn.create", options["challenge"])
        attested = bytes(16) + struct.pack(">H", len(self.credential_id)) + self.credential_id + self._cose_key()
        auth_data = hashlib.sha256(rp.encode()).digest() + bytes([UP | UV | AT]) + struct.pack(">I", 0) + attested
        att_obj = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        cid = bytes_to_base64url(self.credential_id)
        return {
            "id": cid,
            "rawId": cid,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(att_obj),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
        }

    def sign_in(self, options: dict[str, Any], *, rp_id: str | None = None, user_verified: bool = True) -> dict:
        """Answer ``navigator.credentials.get()`` for the given options."""
        rp = rp_id or options["rpId"]
        self.sign_count += 1
        client_data = self._client_data("webauthn.get", options["challenge"])
        flags = UP | (UV if user_verified else 0)
        auth_data = hashlib.sha256(rp.encode()).digest() + bytes([flags]) + struct.pack(">I", self.sign_count)
        sig = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        cid = bytes_to_base64url(self.credential_id)
        return {
            "id": cid,
            "rawId": cid,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(sig),
                "userHandle": bytes_to_base64url(self.user_handle or b""),
            },
            "clientExtensionResults": {},
        }
