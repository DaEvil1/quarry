"""The FastAPI application: the JSON API under /api, and the built Vue app for every other path."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from sqlalchemy import text
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from . import __version__
from .api import (
    auth,
    bible,
    chart,
    companion,
    decisions,
    front,
    demo,
    guide,
    history,
    items,
    journal,
    labels,
    manuscript,
    restructure,
    revising,
    storytime,
    transfer,
    views,
    world,
    worlds,
)
from .config import get_settings
from .db import engine

log = logging.getLogger("quarry")
PKG = Path(__file__).parent


class SameOriginWrites:
    """Refuse state-changing requests from other sites (CSRF): the Origin (or Referer) must be this app.

    The session cookie is also SameSite=Strict, so this is a second lock on the same door."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            origin = headers.get("origin") or headers.get("referer") or ""
            host = headers.get("x-forwarded-host") or headers.get("host", "")
            allowed = {host.lower(), urlsplit(get_settings().base_url).netloc.lower()}
            if not origin or urlsplit(origin).netloc.lower() not in allowed:
                resp = JSONResponse({"detail": "Cross-site request refused."}, status_code=403)
                await resp(scope, receive, send)
                return
        await self.app(scope, receive, send)


class SecurityHeaders:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")

        async def wrapped(message):  # type: ignore[no-untyped-def]
            if message["type"] == "http.response.start":
                h = list(message.get("headers", []))
                h += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"same-origin"),
                    # framed only by Quarry itself: the Guide shows the phone screens in a frame (docs/SPEC.md §15)
                    (b"x-frame-options", b"SAMEORIGIN"),
                    # styles stay inline-friendly: the editor (CodeMirror) injects its own style elements
                    (b"content-security-policy",
                     b"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                     b"script-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; "
                     b"frame-ancestors 'self'; base-uri 'self'; form-action 'self'"),
                ]
                if path.startswith("/assets/"):
                    h.append((b"cache-control", b"public, max-age=31536000, immutable"))
                elif path.startswith("/api/"):
                    h.append((b"cache-control", b"no-store"))
                else:
                    h.append((b"cache-control", b"no-cache"))
                message["headers"] = h
            await send(message)

        await self.app(scope, receive, wrapped)


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(PKG / "migrations"))
    cfg.attributes["connection_url"] = get_settings().database_url
    command.upgrade(cfg, "head")


class Compressed(GZipMiddleware):
    """Responses of a kilobyte or more, gzipped for a browser that takes it: a world's cards and its offline copy
    shrink five to seven times on the way to a phone. Not sign-in and setup, whose answers carry secrets (recovery
    codes), so nothing a page can make the server repeat is ever compressed beside them."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app, minimum_size=1024, compresslevel=6)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(("/api/auth", "/api/setup")):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


def rescan_mentions() -> None:
    """After an upgrade that reads texts differently, work out the stored mentions again (docs/SPEC.md §14.10)."""
    from .db import session_factory
    from .mentions import rescan_stale

    with session_factory()() as db:
        n = rescan_stale(db)
    if n:
        log.info("worked out the mentions again in %d world(s)", n)


def drop_stale_sandboxes() -> None:
    """The Guide's sandboxes left behind by a walkthrough that was never ended (docs/SPEC.md §15)."""
    from .api.guide import drop_stale_sandboxes as drop
    from .db import session_factory

    with session_factory()() as db:
        n = drop(db)
    if n:
        log.info("deleted %d guide sandbox(es) left behind", n)


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built frontend: real files as they are, any other path gets index.html (client-side routes)."""
    root = get_settings().web_path.resolve()
    index = root / "index.html"

    # HEAD too: uptime monitors check the front page that way
    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(path: str):  # type: ignore[no-untyped-def]
        if path.startswith("api/") or path == "api":
            return JSONResponse({"detail": "Not found."}, status_code=404)
        if path:
            f = (root / path).resolve()
            if f.is_relative_to(root) and f.is_file():
                return FileResponse(f)
        if index.is_file():
            return FileResponse(index)
        return PlainTextResponse("The frontend is not built. Run `npm run build` in frontend/, or use the "
                                 "Vite dev server.", status_code=503)


def create_app(run_bootstrap: bool = True) -> FastAPI:
    s = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if run_bootstrap and s.migrate_on_start:
            run_migrations()
            rescan_mentions()
            drop_stale_sandboxes()
        yield

    app = FastAPI(title="Quarry", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs" if s.docs else None, redoc_url=None,
                  openapi_url="/api/openapi.json" if s.docs else None)
    app.add_middleware(SameOriginWrites)
    app.add_middleware(SecurityHeaders)
    app.add_middleware(Compressed)

    @app.api_route("/healthz", methods=["GET", "HEAD"], include_in_schema=False)
    def healthz() -> PlainTextResponse:
        with engine().connect() as c:
            c.execute(text("SELECT 1"))
        return PlainTextResponse("ok")

    app.include_router(auth.router)
    app.include_router(worlds.router)
    app.include_router(items.router)
    app.include_router(decisions.router)
    app.include_router(bible.router)
    app.include_router(journal.router)
    app.include_router(front.router)
    # before the manuscript's /chapters/{id}: /chapters/ties and /chapters/retire
    app.include_router(restructure.router)
    app.include_router(manuscript.router)
    app.include_router(demo.router)
    app.include_router(guide.router)
    app.include_router(transfer.router)
    app.include_router(world.router)
    app.include_router(storytime.router)
    app.include_router(views.router)
    app.include_router(companion.router)
    app.include_router(revising.router)
    app.include_router(labels.router)
    app.include_router(history.router)
    app.include_router(chart.router)
    _mount_frontend(app)
    return app
