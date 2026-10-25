"""Phase 13c, names shared by two entries (docs/SPEC.md §14.10), through the API: ambiguous until a choice line settles
them, counted only once settled, never a Continuity finding while ambiguous, and kept by export and Restore. The
matcher's own cases are in test_mentions.py (shared with the browser)."""

from __future__ import annotations

import io
import zipfile

import pytest
from sqlalchemy import text

from .conftest import Client

W = "/api/worlds/delta"


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Delta"})
    signed_in.post(f"{W}/projects", json={"name": "The Salt Road"})
    return signed_in


def add(c: Client, name: str, kind: str = "character", **extra) -> dict:
    return c.post(f"{W}/entities", json={"name": name, "kind": kind, **extra}).json()


def chapter(c: Client, title: str, body: str) -> dict:
    return c.post(f"{W}/projects/the-salt-road/chapters", json={"title": title, "body": body}).json()


def kinds_in(c: Client, chapter_id: str) -> list[tuple[str, str, str]]:
    return [(m["matched_text"], m["kind"], m["entity_name"]) for m in c.get(f"{W}/chapters/{chapter_id}").json()["mentions"]]


def test_a_shared_first_name_is_ambiguous_until_a_choice_line(world: Client):
    marr, senn = add(world, "Isolde Marr"), add(world, "Isolde Senn")
    one = chapter(world, "One", "Isolde Senn drowned.")
    world.post(f"{W}/entities/{senn['id']}/facts", json={"label": "status", "value": "dead", "from_chapter_id": one["id"]})
    two = chapter(world, "Two", "Isolde came to the quay.")
    assert kinds_in(world, two["id"]) == [("Isolde", "ambiguous", "Isolde Marr"), ("Isolde", "ambiguous", "Isolde Senn")]
    # ambiguous drives no Continuity finding, and counts for none
    assert [f for f in world.get(f"{W}/checks").json() if f["rule"] == "dead_mentioned"] == []
    page = world.get(f"{W}/entities/{marr['id']}").json()
    assert all(m["source_id"] != two["id"] for m in page["mentions"])
    assert [(u["title"], u["count"]) for u in page["unsettled"]] == [("Two", 1)]
    assert page["first_appearance"] == []
    # From here: Marr
    ch = world.get(f"{W}/chapters/{two['id']}").json()
    world.patch(f"{W}/chapters/{two['id']}", json={"base_version": ch["version"],
                                                   "body": "%% Isolde: Isolde Marr\nIsolde came to the quay. Isolde's lamp."})
    assert kinds_in(world, two["id"]) == [("Isolde", "alias", "Isolde Marr"), ("Isolde's", "alias", "Isolde Marr")]
    assert world.get(f"{W}/entities/{marr['id']}").json()["first_appearance"][0]["title"] == "Two"
    # the next chapter starts ambiguous again
    three = chapter(world, "Three", "Isolde waited.")
    assert {k for _, k, _ in kinds_in(world, three["id"])} == {"ambiguous"}
    # a later choice switches to Senn: now she is named after being recorded dead
    ch = world.get(f"{W}/chapters/{two['id']}").json()
    world.patch(f"{W}/chapters/{two['id']}", json={"base_version": ch["version"], "body": (
        "%% Isolde: Isolde Marr\nIsolde came to the quay.\n%% Isolde: Senn\nIsolde sang.\n%% Isolde: Marr, Senn\nIsolde.\n"
        "%% Isolde: ?\nIsolde slept.")})
    assert kinds_in(world, two["id"]) == [
        ("Isolde", "alias", "Isolde Marr"), ("Isolde", "alias", "Isolde Senn"),
        ("Isolde", "alias", "Isolde Marr"), ("Isolde", "alias", "Isolde Senn"),
        ("Isolde", "ambiguous", "Isolde Marr"), ("Isolde", "ambiguous", "Isolde Senn")]
    dead = [f for f in world.get(f"{W}/checks").json() if f["rule"] == "dead_mentioned"]
    assert [(f["chapter"]["title"], f["entities"][0]["name"]) for f in dead] == [("Two", "Isolde Senn")]
    # the lines are margin notes: not counted, not compiled
    detail = world.get(f"{W}/chapters/{two['id']}").json()
    assert detail["words"] == 10
    z = zipfile.ZipFile(io.BytesIO(world.get(f"{W}/export").content))
    compiled = z.read("delta/Projects/The Salt Road/manuscript.md").decode()
    assert "%% Isolde" not in compiled and "Isolde slept." in compiled


def test_an_other_name_given_to_two_entries_is_shared(world: Client):
    add(world, "Varren Hale", aliases=["the Warden"])
    add(world, "Ilse Brand", aliases=["the Warden"])
    ch = chapter(world, "One", "The Warden spoke.\n%% the Warden: Ilse Brand\nthe Warden left.")
    assert kinds_in(world, ch["id"]) == [
        ("The Warden", "ambiguous", "Ilse Brand"), ("The Warden", "ambiguous", "Varren Hale"),
        ("the Warden", "alias", "Ilse Brand")] or kinds_in(world, ch["id"]) == [
        ("The Warden", "ambiguous", "Varren Hale"), ("The Warden", "ambiguous", "Ilse Brand"),
        ("the Warden", "alias", "Ilse Brand")]


def test_a_choice_line_in_the_journal(world: Client):
    add(world, "Isolde Marr")
    add(world, "Isolde Senn")
    j = world.post(f"{W}/journal", json={"title": "Notes", "body": "%% Isolde: Senn\nIsolde knows.\n%% just a note"}).json()
    assert [(m["matched_text"], m["kind"], m["entity_name"]) for m in j["mentions"]] == [("Isolde", "alias", "Isolde Senn")]


def test_mentions_are_worked_out_again_after_an_upgrade(world: Client, db):
    from quarry.mentions import MENTIONS_VERSION, rescan_stale

    add(world, "Isolde Marr")
    add(world, "Isolde Senn")
    ch = chapter(world, "One", "Isolde waited.")
    db.execute(text("DELETE FROM mentions"))
    db.execute(text("UPDATE worlds SET mentions_version = 0"))
    db.commit()
    assert kinds_in(world, ch["id"]) == []
    assert rescan_stale(db) == 1
    assert {k for _, k, _ in kinds_in(world, ch["id"])} == {"ambiguous"}
    assert db.execute(text("SELECT mentions_version FROM worlds")).scalar() == MENTIONS_VERSION
    assert rescan_stale(db) == 0


def test_export_and_restore_keep_the_choices(world: Client):
    add(world, "Isolde Marr")
    add(world, "Isolde Senn")
    chapter(world, "One", "%% Isolde: Marr\nIsolde waited.")
    data = world.get(f"{W}/export").content
    slug = world.post("/api/worlds/restore", files={"file": ("e.zip", data, "application/zip")}).json()["slug"]
    chapters = world.get(f"/api/worlds/{slug}/projects/the-salt-road/chapters").json()["chapters"]
    restored = world.get(f"/api/worlds/{slug}/chapters/{chapters[0]['id']}").json()
    assert [(m["kind"], m["entity_name"]) for m in restored["mentions"]] == [("alias", "Isolde Marr")]
