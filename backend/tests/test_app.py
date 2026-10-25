"""Serving the frontend, security headers, the cross-site guard, health and the CLI."""

from __future__ import annotations

from .conftest import Client
from .softauth import SoftPasskey


def test_cross_site_writes_are_refused(client: Client):
    r = client.post("/api/auth/login/begin", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/api/auth/login/begin", headers={"Origin": ""})
    assert r.status_code == 403


def test_security_headers(client: Client):
    r = client.get("/api/setup")
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert "frame-ancestors 'self'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_healthz(client: Client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.text == "ok"


def test_unknown_api_path_is_json_404(client: Client):
    r = client.get("/api/nothing-here")
    assert r.status_code == 404 and r.json()["detail"]


def test_frontend_routes_get_index_html(tmp_path, monkeypatch, engine):
    from quarry.app import create_app
    from quarry.config import get_settings

    (tmp_path / "index.html").write_text("<!doctype html><title>Quarry</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app-123.js").write_text("console.log(1)")
    (tmp_path.parent / "secret.txt").write_text("not for you")
    monkeypatch.setenv("QUARRY_WEB_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        c = Client(create_app(run_bootstrap=False))
        for path in ("/", "/w/some-world/p/some-project", "/settings/security"):
            r = c.get(path)
            assert r.status_code == 200 and "<title>Quarry</title>" in r.text
            assert r.headers["cache-control"] == "no-cache"
        r = c.get("/assets/app-123.js")
        assert r.text == "console.log(1)" and "immutable" in r.headers["cache-control"]
        assert "not for you" not in c.get("/../secret.txt").text
        assert "not for you" not in c.get("/%2e%2e/secret.txt").text
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_cli_passkey_reset(client: Client, passkey: SoftPasskey, capsys, db_url):
    from quarry.cli import main

    client.setup(passkey, name="Ada")
    assert main(["passkey", "reset", "ada"]) == 0
    out = capsys.readouterr().out
    codes = [line.strip() for line in out.splitlines() if line.startswith("  ")]
    assert len(codes) == 10
    # the session and the passkey are gone; a printed code works
    assert client.get("/api/me").status_code == 401
    assert client.sign_in(passkey).status_code == 400
    assert client.post("/api/auth/recover", json={"code": codes[0]}).status_code == 200
    assert main(["passkey", "reset", "nobody"]) == 2


def test_head_requests_are_answered(client: Client):
    assert client.head("/healthz").status_code == 200
    assert client.head("/").status_code in (200, 503)


def test_large_answers_are_gzipped_but_not_sign_in(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Coast"})
    for i in range(30):
        signed_in.post("/api/worlds/coast/entities", json={"name": f"Varren {i}", "summary": "Keeper of the lamp."})
    r = signed_in.get("/api/worlds/coast/cards", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.headers["content-encoding"] == "gzip" and len(r.json()) == 30
    assert "content-encoding" not in signed_in.get("/api/worlds/coast/cards", headers={"Accept-Encoding": ""}).headers
    r = signed_in.get("/api/auth/recovery-codes", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and "content-encoding" not in r.headers
