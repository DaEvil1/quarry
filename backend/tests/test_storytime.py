"""Story time: chapters in story order across projects, spans that run forwards, "is at", and where everyone is."""

from __future__ import annotations

import pytest

from .conftest import Client

W = "/api/worlds/coast"


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Book One"})
    signed_in.post(f"{W}/projects", json={"name": "Book Two"})
    return signed_in


def add(c: Client, name: str, kind: str = "character") -> dict:
    r = c.post(f"{W}/entities", json={"name": name, "kind": kind})
    assert r.status_code == 201, r.text
    return r.json()


def chapter(c: Client, project: str, title: str, body: str = "") -> dict:
    r = c.post(f"{W}/projects/{project}/chapters", json={"title": title, "body": body})
    assert r.status_code == 201, r.text
    return r.json()


def test_timeline_runs_through_the_projects_in_order(world: Client):
    chapter(world, "book-two", "Return")
    chapter(world, "book-one", "Arrival")
    chapter(world, "book-one", "Storm")
    t = world.get(f"{W}/timeline").json()
    assert [(x["title"], x["project"], x["index"]) for x in t] == [
        ("Arrival", "book-one", 0), ("Storm", "book-one", 1), ("Return", "book-two", 2)]


def test_spans_must_run_forwards(world: Client):
    one, two = chapter(world, "book-one", "One"), chapter(world, "book-one", "Two")
    v = add(world, "Varren")
    r = world.post(f"{W}/entities/{v['id']}/facts",
                   json={"label": "status", "value": "dead", "from_chapter_id": two["id"], "until_chapter_id": one["id"]})
    assert r.status_code == 422
    r = world.post(f"{W}/entities/{v['id']}/facts", json={"label": "status", "value": "dead", "from_chapter_id": two["id"]})
    assert r.status_code == 201
    f = r.json()
    r = world.patch(f"{W}/facts/{f['id']}", json={"base_version": f["version"], "until_chapter_id": one["id"]})
    assert r.status_code == 422
    card = next(c for c in world.get(f"{W}/cards").json() if c["name"] == "Varren")
    assert card["facts"] == [{"label": "status", "value": "dead", "from": two["id"], "until": None}]


def test_is_at_and_where_everyone_is(world: Client):
    v, i = add(world, "Varren"), add(world, "Isolde")
    harbour, lamp = add(world, "Old Harbour", "place"), add(world, "Lamphouse", "place")
    storm = add(world, "The Storm", "event")
    one = chapter(world, "book-one", "One", "Varren walked to Old Harbour.\n\nIsolde slept.")
    two = chapter(world, "book-one", "Two", "Isolde waited. The Storm came.")

    r = world.put(f"{W}/chapters/{two['id']}/presence/{i['id']}", json={"place_id": lamp["id"]})
    assert r.status_code == 200 and r.json()["place"]["name"] == "Lamphouse"
    assert world.put(f"{W}/chapters/{two['id']}/presence/{i['id']}", json={"place_id": v["id"]}).status_code == 422

    grid = world.get(f"{W}/where").json()
    assert [c["title"] for c in grid["chapters"]] == ["One", "Two"]
    rows = {r["entity"]["name"]: r["cells"] for r in grid["rows"]}
    assert list(rows) == ["Varren", "Isolde"]
    assert rows["Varren"][one["id"]]["derived"]["name"] == "Old Harbour"
    # a place in another paragraph doesn't count
    assert rows["Isolde"][one["id"]] == {"count": 1, "recorded": None, "note": None, "derived": None, "present": True,
                                        "people": []}
    assert rows["Isolde"][two["id"]]["recorded"]["name"] == "Lamphouse"
    assert two["id"] not in rows["Varren"]
    assert grid["events"] == {two["id"]: [{"id": storm["id"], "name": "The Storm", "kind": "event"}]}

    assert [p["entity_id"] for p in world.get(f"{W}/chapters/{two['id']}/presence").json()] == [i["id"]]
    assert world.delete(f"{W}/chapters/{two['id']}/presence/{i['id']}").status_code == 204
    rows = {r["entity"]["name"]: r["cells"] for r in world.get(f"{W}/where").json()["rows"]}
    assert rows["Isolde"][two["id"]]["recorded"] is None

    # a project at a time
    assert world.get(f"{W}/where?project=book-two").json()["rows"] == []
