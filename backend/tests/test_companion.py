"""The companion: continuity checks over recorded data, resolutions, session notes, thoughts tied to a chapter, and
margin notes (%% lines) left out of the story."""

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


def chapter(c: Client, title: str, body: str, **extra) -> dict:
    r = c.post(f"{W}/projects/book-one/chapters", json={"title": title, "body": body, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def fact(c: Client, entity: dict, label: str, value: str, **extra) -> dict:
    r = c.post(f"{W}/entities/{entity['id']}/facts", json={"label": label, "value": value, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def rules(c: Client, **q) -> list[tuple[str, str]]:
    return [(f["rule"], f["message"]) for f in c.get(f"{W}/checks", params=q).json()]


def test_dead_but_named_and_before_being_born(world: Client):
    v, i = add(world, "Varren"), add(world, "Isolde")
    one = chapter(world, "One", "Varren sails. Isolde waves.")
    two = chapter(world, "Two", "Varren drowns.")
    three = chapter(world, "Three", "Varren is remembered.")
    fact(world, v, "status", "dead", from_chapter_id=two["id"])
    fact(world, i, "born", "", from_chapter_id=two["id"])
    found = rules(world)
    assert ("dead_mentioned", "Varren is named in “Three”, after being recorded dead from “Two”.") in found
    # named in the chapter they die in is fine
    assert not any("“Two”, after" in m for _, m in found)
    assert ("before_start", "Isolde is named in “One”, before “born” from “Two”.") in found
    assert [f["chapter"]["title"] for f in world.get(f"{W}/checks", params={"chapter": three["id"]}).json()] == ["Three"]
    assert one


def test_pov_absent_cycles_and_conflicting_facts(world: Client):
    v = add(world, "Varren")
    a, b = add(world, "Upper Town", "place"), add(world, "Lower Town", "place")
    one = chapter(world, "One", "Nobody here.", pov_entity_id=v["id"])
    two = chapter(world, "Two", "Rain.")
    t = {x["label"]: x["id"] for x in world.get(f"{W}/relation-types").json()}
    world.post(f"{W}/relationships", json={"type_id": t["inside"], "a_id": a["id"], "b_id": b["id"]})
    world.post(f"{W}/relationships", json={"type_id": t["inside"], "a_id": b["id"], "b_id": a["id"]})
    fact(world, v, "eye colour", "grey")
    fact(world, v, "eye colour", "brown")
    # a later value with an open-ended earlier one takes over: not a conflict
    fact(world, v, "hair", "black")
    fact(world, v, "hair", "white", from_chapter_id=two["id"])
    # an explicit end that runs past the next start is
    fact(world, v, "home", "the pier", until_chapter_id=two["id"])
    fact(world, v, "home", "the tower", from_chapter_id=two["id"])
    found = rules(world)
    assert ("pov_absent", "“One” is told from Varren's point of view, but never names Varren.") in found
    assert any(r == "place_cycle" and "Upper Town" in m and "Lower Town" in m for r, m in found)
    assert ("fact_conflict", "Varren: “eye colour” is both “grey” and “brown” in “One”.") in found
    assert ("fact_conflict", "Varren: “home” is both “the pier” and “the tower” in “Two”.") in found
    assert not any("hair" in m for _, m in found)
    assert one


def test_spans_that_end_up_backwards_after_a_reorder(world: Client):
    v = add(world, "Varren")
    one, two = chapter(world, "One", "a"), chapter(world, "Two", "b")
    fact(world, v, "mood", "calm", from_chapter_id=one["id"], until_chapter_id=two["id"])
    world.put(f"{W}/projects/book-one/chapter-order", json={"ids": [two["id"], one["id"]]})
    assert ("span_backwards", "Varren: “mood: calm” runs from “One” until “Two”, which comes earlier in the story.") in rules(world)


def test_resolutions(world: Client):
    v = add(world, "Varren")
    chapter(world, "One", "Nobody.", pov_entity_id=v["id"])
    f = world.get(f"{W}/checks").json()[0]
    r = world.put(f"{W}/resolutions", json={"rule": f["rule"], "key": f["key"], "outcome": "later"}).json()
    assert world.get(f"{W}/checks").json()[0]["later"] is True
    world.put(f"{W}/resolutions", json={"rule": f["rule"], "key": f["key"], "outcome": "intentional", "note": "on purpose"})
    assert world.get(f"{W}/checks").json() == []
    assert [(x["outcome"], x["note"]) for x in world.get(f"{W}/resolutions").json()] == [("intentional", "on purpose")]
    assert world.delete(f"{W}/resolutions/{r['id']}").status_code == 204
    assert len(world.get(f"{W}/checks").json()) == 1
    # the browser's own findings are resolved the same way
    pair = world.put(f"{W}/resolutions", json={"rule": "unrecorded", "key": "a:b", "outcome": "not_connected"})
    assert pair.status_code == 200
    assert world.put(f"{W}/resolutions", json={"rule": "x", "key": "y", "outcome": "nonsense"}).status_code == 422


def test_session_note_and_stashed_thoughts(world: Client):
    one = chapter(world, "One", "Text.")
    assert world.get(f"{W}/chapters/{one['id']}/session-note").json()["note"] == ""
    world.put(f"{W}/chapters/{one['id']}/session-note", json={"note": "Next: the storm", "cursor": 5})
    n = world.get(f"{W}/chapters/{one['id']}/session-note").json()
    assert (n["note"], n["cursor"]) == ("Next: the storm", 5)

    world.post(f"{W}/items", json={"body": "Should the gull come back?", "chapter_id": one["id"]})
    world.post(f"{W}/items", json={"body": "Unrelated."})
    items = world.get(f"{W}/chapters/{one['id']}/items").json()
    assert [i["body"] for i in items] == ["Should the gull come back?"]


def test_margin_notes_are_not_story(world: Client):
    v = add(world, "Varren")
    body = "Varren waits.\n%% Varren should be angrier here\nThe end."
    ch = chapter(world, "One", body)
    assert ch["words"] == 4
    m = world.get(f"{W}/chapters/{ch['id']}").json()["mentions"]
    assert [(x["start"], x["entity_name"]) for x in m] == [(0, "Varren")]
    export = world.get(f"{W}/export")
    assert export.status_code == 200
    import io
    import zipfile

    z = zipfile.ZipFile(io.BytesIO(export.content))
    compiled = next(n for n in z.namelist() if n.endswith("manuscript.md"))
    assert "%%" not in z.read(compiled).decode()
    chapter_file = next(n for n in z.namelist() if "/Manuscript/" in n)
    assert "%% Varren should be angrier here" in z.read(chapter_file).decode()
    assert v
