"""``quarry serve | migrate | users | passkey reset``."""

from __future__ import annotations

import argparse
import os
import sys


def _find_user(db, who: str):  # type: ignore[no-untyped-def]
    import uuid

    from sqlalchemy import func, select

    from .models import User

    try:
        u = db.get(User, uuid.UUID(who))
        if u is not None:
            return [u]
    except ValueError:
        pass
    return list(db.scalars(select(User).where(func.lower(User.display_name) == who.strip().lower())).all())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="quarry")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sv = sub.add_parser("serve", help="run the web server")
    sv.add_argument("--host", default=os.environ.get("QUARRY_HOST", "127.0.0.1"))
    sv.add_argument("--port", type=int, default=int(os.environ.get("QUARRY_PORT", "8000")))
    sv.add_argument("--reload", action="store_true")
    sub.add_parser("migrate", help="apply database migrations")
    sub.add_parser("users", help="list users")
    pk = sub.add_parser("passkey", help="passkey recovery")
    pk_sub = pk.add_subparsers(dest="action", required=True)
    reset = pk_sub.add_parser("reset", help="remove a user's passkeys and sessions and print new recovery codes")
    reset.add_argument("user", help="user id or display name")
    args = ap.parse_args(argv)

    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("quarry.main:app", host=args.host, port=args.port, reload=args.reload, workers=1,
                    proxy_headers=True, forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
                    access_log=os.environ.get("QUARRY_ACCESS_LOG", "0") == "1")
        return 0

    from .app import run_migrations
    from .db import session_scope

    run_migrations()
    if args.cmd == "migrate":
        print("migrations applied")
        return 0
    if args.cmd == "users":
        from sqlalchemy import select

        from .models import User

        with session_scope() as db:
            for u in db.scalars(select(User).order_by(User.created_at)):
                print(f"{u.id}  {u.display_name}")
        return 0
    if args.cmd == "passkey" and args.action == "reset":
        from sqlalchemy import delete

        from .models import Passkey
        from .security import end_all_sessions, new_recovery_codes

        with session_scope() as db:
            users = _find_user(db, args.user)
            if len(users) != 1:
                print("no such user" if not users else "several users have that name; use the id",
                      file=sys.stderr)
                return 2
            u = users[0]
            db.execute(delete(Passkey).where(Passkey.user_id == u.id))
            end_all_sessions(db, u.id)
            codes = new_recovery_codes(db, u.id)
        print(f"Removed every passkey and session for {u.display_name}.")
        print("Sign in with one of these recovery codes, then add a passkey under Settings:")
        for c in codes:
            print(f"  {c}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
