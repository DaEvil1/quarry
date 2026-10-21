"""First-run setup, passkey sign-in, recovery codes and passkey management."""

from __future__ import annotations

from .conftest import SETUP_TOKEN, Client
from .softauth import SoftPasskey


def test_setup_status_before_and_after(client: Client, passkey: SoftPasskey):
    assert client.get("/api/setup").json() == {"needed": True, "enabled": True}
    client.setup(passkey)
    assert client.get("/api/setup").json()["needed"] is False


def test_setup_creates_user_codes_and_session(client: Client, passkey: SoftPasskey):
    codes = client.setup(passkey, name="Ada")
    assert len(codes) == 10 and len(set(codes)) == 10
    assert all(len(c) == 11 and c[5] == "-" for c in codes)
    me = client.get("/api/me").json()
    assert me["user"]["display_name"] == "Ada"
    assert me["worlds"] == []
    keys = client.get("/api/auth/passkeys").json()
    assert [k["label"] for k in keys] == ["Laptop"]


def test_setup_needs_the_token(client: Client):
    r = client.post("/api/setup/begin", json={"token": "wrong", "display_name": "Ada"})
    assert r.status_code == 403


def test_setup_runs_once(client: Client, passkey: SoftPasskey):
    client.setup(passkey)
    r = client.post("/api/setup/begin", json={"token": SETUP_TOKEN, "display_name": "Eve"})
    assert r.status_code == 409


def test_setup_finish_refused_after_someone_else_finished(client: Client, app):
    # two browsers start setup; the first to finish wins, the second is refused
    first, second = SoftPasskey(), SoftPasskey()
    b1 = client.post("/api/setup/begin", json={"token": SETUP_TOKEN, "display_name": "One"}).json()
    b2 = client.post("/api/setup/begin", json={"token": SETUP_TOKEN, "display_name": "Two"}).json()
    r1 = client.post("/api/setup/finish", json={"challenge_id": b1["challenge_id"], "label": "a",
                                                "credential": first.register(b1["options"])})
    assert r1.status_code == 200
    other = Client(app)
    r2 = other.post("/api/setup/finish", json={"challenge_id": b2["challenge_id"], "label": "b",
                                               "credential": second.register(b2["options"])})
    assert r2.status_code == 409


def test_setup_turned_off_without_token(client: Client, monkeypatch):
    from quarry.config import get_settings

    monkeypatch.setenv("QUARRY_SETUP_TOKEN", "")
    get_settings.cache_clear()
    try:
        assert client.get("/api/setup").json() == {"needed": True, "enabled": False}
        r = client.post("/api/setup/begin", json={"token": "", "display_name": "Ada"})
        assert r.status_code == 403
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_api_needs_sign_in(client: Client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/worlds").status_code == 401


def test_sign_out_and_back_in_with_passkey(signed_in: Client, passkey: SoftPasskey):
    assert signed_in.post("/api/auth/logout").status_code == 200
    assert signed_in.get("/api/me").status_code == 401
    r = signed_in.sign_in(passkey)
    assert r.status_code == 200, r.text
    assert signed_in.get("/api/me").status_code == 200


def test_unknown_passkey_is_refused(signed_in: Client):
    signed_in.post("/api/auth/logout")
    r = signed_in.sign_in(SoftPasskey())
    assert r.status_code == 400
    assert signed_in.get("/api/me").status_code == 401


def test_challenge_is_single_use(signed_in: Client, passkey: SoftPasskey):
    signed_in.post("/api/auth/logout")
    begin = signed_in.post("/api/auth/login/begin").json()
    answer = passkey.sign_in(begin["options"])
    body = {"challenge_id": begin["challenge_id"], "credential": answer}
    assert signed_in.post("/api/auth/login/finish", json=body).status_code == 200
    signed_in.post("/api/auth/logout")
    assert signed_in.post("/api/auth/login/finish", json=body).status_code == 400


def test_sign_in_without_user_verification_is_refused(signed_in: Client, passkey: SoftPasskey):
    signed_in.post("/api/auth/logout")
    begin = signed_in.post("/api/auth/login/begin").json()
    r = signed_in.post("/api/auth/login/finish", json={
        "challenge_id": begin["challenge_id"], "credential": passkey.sign_in(begin["options"], user_verified=False)})
    assert r.status_code == 400


def test_wrong_origin_answer_is_refused(signed_in: Client, passkey: SoftPasskey):
    signed_in.post("/api/auth/logout")
    passkey.origin = "https://evil.example"
    r = signed_in.sign_in(passkey)
    assert r.status_code == 400


def test_recovery_code_signs_in_once(client: Client, passkey: SoftPasskey):
    codes = client.setup(passkey)
    client.post("/api/auth/logout")
    r = client.post("/api/auth/recover", json={"code": codes[0].lower().replace("-", " ")})
    assert r.status_code == 200, r.text
    assert r.json()["codes_left"] == 9
    client.post("/api/auth/logout")
    assert client.post("/api/auth/recover", json={"code": codes[0]}).status_code == 400
    assert client.post("/api/auth/recover", json={"code": "nope"}).status_code == 400


def test_regenerating_recovery_codes_replaces_the_old_ones(client: Client, passkey: SoftPasskey):
    old = client.setup(passkey)
    new = client.post("/api/auth/recovery-codes").json()["recovery_codes"]
    assert set(old).isdisjoint(new)
    assert client.get("/api/auth/recovery-codes").json() == {"left": 10}
    client.post("/api/auth/logout")
    assert client.post("/api/auth/recover", json={"code": old[1]}).status_code == 400
    assert client.post("/api/auth/recover", json={"code": new[1]}).status_code == 200


def test_add_rename_and_remove_passkeys(signed_in: Client, passkey: SoftPasskey):
    phone = SoftPasskey()
    begin = signed_in.post("/api/auth/passkeys/begin").json()
    # the existing passkey is excluded, so the same device is not registered twice
    excluded = [c["id"] for c in begin["options"]["excludeCredentials"]]
    assert excluded == [phone_id(passkey)]
    r = signed_in.post("/api/auth/passkeys/finish", json={"challenge_id": begin["challenge_id"], "label": "Phone",
                                                          "credential": phone.register(begin["options"])})
    assert r.status_code == 201, r.text
    new_id = r.json()["id"]
    r = signed_in.patch(f"/api/auth/passkeys/{new_id}", json={"label": "Android"})
    assert r.json()["label"] == "Android"
    keys = signed_in.get("/api/auth/passkeys").json()
    assert [k["label"] for k in keys] == ["Laptop", "Android"]

    # the new passkey signs in too
    signed_in.post("/api/auth/logout")
    assert signed_in.sign_in(phone).status_code == 200

    assert signed_in.delete(f"/api/auth/passkeys/{keys[0]['id']}").status_code == 204
    r = signed_in.delete(f"/api/auth/passkeys/{new_id}")
    assert r.status_code == 409, "the last passkey cannot be removed"


def test_registering_the_same_passkey_twice_is_refused(signed_in: Client, passkey: SoftPasskey):
    begin = signed_in.post("/api/auth/passkeys/begin").json()
    r = signed_in.post("/api/auth/passkeys/finish", json={"challenge_id": begin["challenge_id"], "label": "Again",
                                                          "credential": passkey.register(begin["options"])})
    assert r.status_code == 409


def test_auth_endpoints_are_rate_limited(client: Client):
    codes = [client.post("/api/auth/recover", json={"code": "AAAAA-AAAAA"}).status_code for _ in range(25)]
    assert codes[0] == 400 and codes[-1] == 429


def test_session_cookie_is_strict_and_http_only(client: Client, passkey: SoftPasskey):
    begin = client.post("/api/setup/begin", json={"token": SETUP_TOKEN, "display_name": "Ada"}).json()
    r = client.post("/api/setup/finish", json={"challenge_id": begin["challenge_id"], "label": "x",
                                               "credential": passkey.register(begin["options"])})
    cookie = r.headers["set-cookie"].lower()
    assert "quarry_session=" in cookie and "httponly" in cookie and "samesite=strict" in cookie


def phone_id(p: SoftPasskey) -> str:
    from webauthn.helpers import bytes_to_base64url

    return bytes_to_base64url(p.credential_id)
