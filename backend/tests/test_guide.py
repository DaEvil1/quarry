"""The Guide's sandbox (docs/SPEC.md §15): a fresh copy of the demo world per walkthrough, one at a time, marked so
the app can hide it, and gone when the walkthrough ends; the writer's own worlds are never touched."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from quarry.api.guide import drop_stale_sandboxes
from quarry.models import World

from .conftest import Client


def test_sandbox_is_a_demo_copy_one_at_a_time(signed_in: Client, db):
    own = signed_in.post("/api/worlds", json={"name": "The Grey Coast"}).json()
    demo = signed_in.post("/api/worlds/demo").json()

    first = signed_in.post("/api/guide/sandbox")
    assert first.status_code == 201, first.text
    sb = first.json()
    assert sb["sandbox"] is True and sb["slug"] == "guide-sandbox"
    assert sb["name"] == "The Ninefold Delta (guide sandbox)"
    assert [p["name"] for p in sb["projects"]] == ["The Ferryman's Daughter", "Ash Season"]
    W = f"/api/worlds/{sb['slug']}"
    # a walkthrough changes it as any world is changed
    assert signed_in.post(f"{W}/items", json={"kind": "spark", "body": "the abbey bell"}).status_code == 201

    # the next walkthrough starts from a fresh copy: the old one and what was done in it are gone
    again = signed_in.post("/api/guide/sandbox").json()
    assert again["id"] != sb["id"] and again["slug"] == "guide-sandbox"
    items = signed_in.get(f"{W}/items?status=all").json()
    assert not any(i["body"] == "the abbey bell" for i in items)

    worlds = {w["slug"]: w for w in signed_in.get("/api/me").json()["worlds"]}
    assert set(worlds) == {own["slug"], demo["slug"], "guide-sandbox"}
    assert not worlds[own["slug"]]["sandbox"] and not worlds[demo["slug"]]["sandbox"]

    # ending it deletes it, and only it
    assert signed_in.delete("/api/guide/sandbox").status_code == 204
    assert {w["slug"] for w in signed_in.get("/api/me").json()["worlds"]} == {own["slug"], demo["slug"]}
    assert signed_in.delete("/api/guide/sandbox").status_code == 204


def test_stale_sandboxes_go_at_startup(signed_in: Client, db):
    signed_in.post("/api/guide/sandbox")
    db.execute(update(World).where(World.sandbox.is_(True)).values(created_at=datetime.now(UTC) - timedelta(hours=13)))
    db.commit()
    signed_in.post("/api/worlds", json={"name": "The Grey Coast"})
    assert drop_stale_sandboxes(db) == 1
    assert db.scalars(select(World.slug)).all() == ["the-grey-coast"]
