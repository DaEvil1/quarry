"""Views: the graph read (relationships with spans, presence, co-occurrence by paragraph) and the cast per chapter."""

from __future__ import annotations

import pytest

from .conftest import Client

W = "/api/worlds/coast"


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Book One"})
    return signed_in


def add(c: Client, name: str, kind: str = "character") -> dict:
    r = c.post(f"{W}/entities", json={"name": name, "kind": kind})
    assert r.status_code == 201, r.text
    return r.json()


def test_graph_and_cast(world: Client):
    v, i, m = add(world, "Varren"), add(world, "Isolde"), add(world, "Mordoch")
    harbour = add(world, "Old Harbour", "place")
    one = world.post(f"{W}/projects/book-one/chapters", json={
        "title": "One", "body": "Varren and Isolde at Old Harbour. Varren again.\n\nMordoch alone."}).json()
    two = world.post(f"{W}/projects/book-one/chapters", json={"title": "Two", "body": "Isolde, Varren."}).json()
    t = {x["label"]: x for x in world.get(f"{W}/relation-types").json()}
    world.post(f"{W}/relationships", json={"type_id": t["parent of"]["id"], "a_id": v["id"], "b_id": i["id"],
                                           "from_chapter_id": two["id"]})
    world.put(f"{W}/chapters/{one['id']}/presence/{v['id']}", json={"place_id": harbour["id"]})

    g = world.get(f"{W}/graph").json()
    assert {n["name"] for n in g["nodes"]} == {"Varren", "Isolde", "Mordoch", "Old Harbour"}
    assert [(e["label"], e["reverse_label"], e["from_chapter_id"]) for e in g["edges"]] == [("parent of", "child of", two["id"])]
    assert g["presence"] == [{"entity_id": v["id"], "place_id": harbour["id"], "chapter_id": one["id"]}]
    assert g["cooccurrence"] == []

    co = world.get(f"{W}/graph?co=true").json()["cooccurrence"]
    pairs = {frozenset((c["a"], c["b"])): c["by_chapter"] for c in co}
    assert pairs[frozenset((v["id"], i["id"]))] == {one["id"]: 1, two["id"]: 1}
    assert pairs[frozenset((v["id"], harbour["id"]))] == {one["id"]: 1}
    # Mordoch is in his own paragraph
    assert not any(m["id"] in (c["a"], c["b"]) for c in co)

    cast = world.get(f"{W}/projects/book-one/chapters").json()["cast"]
    assert [(x["name"], x["count"]) for x in cast[one["id"]]] == [("Varren", 2), ("Isolde", 1), ("Mordoch", 1),
                                                                  ("Old Harbour", 1)]
    assert [x["name"] for x in cast[two["id"]]] == ["Isolde", "Varren"]
