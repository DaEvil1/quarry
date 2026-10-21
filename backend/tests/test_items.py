"""Capturing items, listing them, editing with version checks, and closing them in triage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from .conftest import Client

W = "/api/worlds/coast"


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Book One"})
    signed_in.post(f"{W}/projects", json={"name": "Novella", "kind": "novella"})
    return signed_in


def capture(c: Client, body: str = "an idea", **extra) -> dict:
    r = c.post(f"{W}/items", json={"body": body, **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_capture_defaults(world: Client):
    item = capture(world, "  The lighthouse keeper lies about the storm.  ")
    assert item["body"] == "The lighthouse keeper lies about the storm."
    assert (item["kind"], item["status"], item["project"], item["version"]) == ("spark", "open", None, 1)


def test_capture_into_a_project_with_kind_and_source(world: Client):
    item = capture(world, "Why does she stay?", kind="question", project="book-one", source="share")
    assert (item["kind"], item["project"], item["source"]) == ("question", "book-one", "share")


def test_capture_rejects_empty_and_unknown_project(world: Client):
    assert world.post(f"{W}/items", json={"body": "   "}).status_code == 422
    assert world.post(f"{W}/items", json={"body": "x", "project": "nope"}).status_code == 422
    assert world.post(f"{W}/items", json={"body": "x", "kind": "experiment"}).status_code == 422


def test_offline_capture_is_saved_once_and_keeps_its_time(world: Client):
    item_id = str(uuid.uuid4())
    when = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    first = world.post(f"{W}/items", json={"id": item_id, "body": "on the train", "captured_at": when})
    again = world.post(f"{W}/items", json={"id": item_id, "body": "on the train", "captured_at": when})
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"] == item_id
    assert datetime.fromisoformat(first.json()["created_at"]) < datetime.now(UTC) - timedelta(hours=2)
    assert len(world.get(f"{W}/items").json()) == 1


def test_capture_time_from_the_future_is_ignored(world: Client):
    later = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    item = capture(world, "x", captured_at=later)
    assert datetime.fromisoformat(item["created_at"]) < datetime.now(UTC) + timedelta(minutes=1)


def test_list_filters_and_order(world: Client):
    old = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    a = capture(world, "first", captured_at=old)
    b = capture(world, "second", project="book-one", kind="task")
    c = capture(world, "third", project="novella")
    assert [i["body"] for i in world.get(f"{W}/items").json()] == ["third", "second", "first"]
    assert [i["body"] for i in world.get(f"{W}/items?order=oldest").json()] == ["first", "second", "third"]
    assert [i["id"] for i in world.get(f"{W}/items?project=book-one").json()] == [b["id"]]
    assert [i["id"] for i in world.get(f"{W}/items?project=-").json()] == [a["id"]]
    assert [i["id"] for i in world.get(f"{W}/items?kind=task").json()] == [b["id"]]
    world.post(f"{W}/items/{c['id']}/close", json={"status": "deferred"})
    world.post(f"{W}/items/{a['id']}/close", json={"status": "rejected"})
    assert [i["id"] for i in world.get(f"{W}/items").json()] == [b["id"]]
    assert [i["id"] for i in world.get(f"{W}/items?status=deferred").json()] == [c["id"]]
    assert [i["id"] for i in world.get(f"{W}/items?status=closed").json()] == [a["id"]]
    assert len(world.get(f"{W}/items?status=all").json()) == 3


def test_counts(world: Client):
    capture(world, "a")
    capture(world, "b", project="book-one")
    capture(world, "c", project="book-one")
    d = capture(world, "d", project="novella")
    world.post(f"{W}/items/{d['id']}/close", json={"status": "deferred"})
    assert world.get(f"{W}/items/counts").json() == {
        "open": 3, "deferred": 1, "open_by_project": {"-": 1, "book-one": 2}}


def test_edit_with_version_check(world: Client):
    item = capture(world, "draft")
    r = world.patch(f"{W}/items/{item['id']}", json={"base_version": 1, "body": "better", "kind": "question",
                                                     "project": "novella", "title": "A title"})
    edited = r.json()
    assert (edited["body"], edited["kind"], edited["project"], edited["title"], edited["version"]) == (
        "better", "question", "novella", "A title", 2)
    # another device still holds version 1: refused, and handed the newer copy
    r = world.patch(f"{W}/items/{item['id']}", json={"base_version": 1, "body": "stale"})
    assert r.status_code == 409
    assert r.json()["item"]["body"] == "better"
    # moving it back to the whole world, and leaving the title alone when it isn't sent
    r = world.patch(f"{W}/items/{item['id']}", json={"base_version": 2, "project": None})
    assert (r.json()["project"], r.json()["title"]) == (None, "A title")


def test_close_with_decision_and_undo(world: Client):
    item = capture(world, "Make the storm real", project="book-one")
    r = world.post(f"{W}/items/{item['id']}/close", json={
        "status": "accepted", "decision": "  The storm  is real. ", "decided_on": "2026-10-20"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["item"]["status"], out["item"]["version"]) == ("accepted", 2)
    assert out["item"]["closed_at"]
    decisions = world.get(f"{W}/decisions").json()
    assert [(d["text"], d["decided_on"], d["project"], d["item_id"]) for d in decisions] == [
        ("The storm is real.", "2026-10-20", "book-one", item["id"])]

    assert world.post(f"{W}/items/{item['id']}/close", json={"status": "rejected"}).status_code == 409

    # undo: reopen, and the client removes the decision it just made
    reopened = world.post(f"{W}/items/{item['id']}/reopen").json()
    assert (reopened["status"], reopened["closed_at"]) == ("open", None)
    assert world.delete(f"{W}/decisions/{out['decision_id']}").status_code == 204
    assert world.get(f"{W}/decisions").json() == []


def test_deferred_items_can_be_closed_later(world: Client):
    item = capture(world, "later")
    world.post(f"{W}/items/{item['id']}/close", json={"status": "deferred"})
    assert world.post(f"{W}/items/{item['id']}/close", json={"status": "deferred"}).status_code == 409
    r = world.post(f"{W}/items/{item['id']}/close", json={"status": "harvested", "note": "kept the image"})
    assert (r.json()["item"]["status"], r.json()["item"]["closed_note"], r.json()["decision_id"]) == (
        "harvested", "kept the image", None)


def test_items_belong_to_their_world(world: Client):
    item = capture(world, "secret")
    world.post("/api/worlds", json={"name": "Other"})
    assert world.get(f"/api/worlds/other/items/{item['id']}").status_code == 404
    assert world.post(f"/api/worlds/other/items/{item['id']}/close", json={"status": "accepted"}).status_code == 404
    # reusing another world's item id is refused rather than moving or duplicating it
    r = world.post("/api/worlds/other/items", json={"id": item["id"], "body": "x"})
    assert r.status_code == 409


def test_removing_a_project_is_not_possible_but_items_survive_a_rename(world: Client):
    item = capture(world, "x", project="book-one")
    world.patch(f"{W}/projects/book-one", json={"slug": "first-book"})
    assert world.get(f"{W}/items/{item['id']}").json()["project"] == "first-book"
