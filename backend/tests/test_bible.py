"""The bible, mentions in saved texts, tags on items, the journal, and the name check's three fixes."""

from __future__ import annotations

import pytest

from .conftest import Client

W = "/api/worlds/coast"


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Book One"})
    return signed_in


def add(c: Client, name: str, kind: str = "character", **extra) -> dict:
    r = c.post(f"{W}/entities", json={"name": name, "kind": kind, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def capture(c: Client, body: str, **extra) -> dict:
    r = c.post(f"{W}/items", json={"body": body, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_list_and_unique_names(world: Client):
    add(world, "Varren", aliases=["the Grey Keeper", "Varren", "  "])
    add(world, "Old Harbour", "place")
    assert world.post(f"{W}/entities", json={"name": "varren"}).status_code == 409
    listed = world.get(f"{W}/entities").json()
    assert [(e["name"], e["kind"], e["aliases"]) for e in listed] == [
        ("Old Harbour", "place", []), ("Varren", "character", ["the Grey Keeper"])]
    assert [e["name"] for e in world.get(f"{W}/entities?kind=place").json()] == ["Old Harbour"]


def test_items_carry_their_mentions(world: Client):
    v = add(world, "Varren", aliases=["the Grey Keeper"])
    item = capture(world, "Varren meets the Grey Keeper. Varen? Odd.")
    found = [(m["matched_text"], m["kind"], m["entity_name"]) for m in item["mentions"]]
    assert found == [("Varren", "exact", "Varren"), ("the Grey Keeper", "alias", "Varren"), ("Varen", "near_miss", "Varren")]
    assert item["mentions"][0]["start"] == 0 and item["mentions"][0]["end"] == 6
    # editing the text rescans it
    edited = world.patch(f"{W}/items/{item['id']}", json={"base_version": 1, "body": "Nothing here."}).json()
    assert edited["mentions"] == []
    # a new entity rescans texts saved before it existed
    capture(world, "Isolde waits.")
    add(world, "Isolde")
    detail = world.get(f"{W}/entities/{v['id']}").json()
    assert detail["mentions"] == []


def test_entity_page_mentions_unlinked_and_tags(world: Client):
    v = add(world, "Varren")
    tagged = capture(world, "Varren lights the lamp.", entities=[v["id"]], project="book-one")
    loose = capture(world, "Why does Varren stay?")
    world.post(f"{W}/decisions", json={"text": "Varren never leaves the island."})
    world.post(f"{W}/journal", json={"body": "Thinking about Varren today.", "title": "Notes"})
    add(world, "Isolde", body="Varren's daughter.")

    assert [e["name"] for e in tagged["entities"]] == ["Varren"]
    d = world.get(f"{W}/entities/{v['id']}").json()
    assert d["entity"]["mention_count"] == 5
    assert {(m["source_table"], m["title"]) for m in d["mentions"]} == {
        ("item", "Varren lights the lamp."), ("item", "Why does Varren stay?"), ("decision", "Varren never leaves the island."),
        ("journal", "Notes"), ("entity", "Isolde")}
    assert [u["source_id"] for u in d["unlinked"]] == [loose["id"]]
    assert [i["id"] for i in d["linked_items"]] == [tagged["id"]]
    snip = next(m for m in d["mentions"] if m["source_table"] == "decision")["snippet"]
    assert snip == {"before": "", "match": "Varren", "after": " never leaves the island."}

    # tag the loose one from the entity page; it leaves "unlinked"
    r = world.post(f"{W}/items/{loose['id']}/links", json={"entity_id": v["id"]})
    assert [e["name"] for e in r.json()["entities"]] == ["Varren"]
    assert world.get(f"{W}/entities/{v['id']}").json()["unlinked"] == []
    r = world.delete(f"{W}/items/{loose['id']}/links/{v['id']}")
    assert r.json()["entities"] == []


def test_capture_skips_unknown_tags(world: Client):
    import uuid

    item = capture(world, "x", entities=[str(uuid.uuid4())])
    assert item["entities"] == []


def test_rename_and_aliases_rescan_everything(world: Client):
    v = add(world, "Varen")
    item = capture(world, "Varren and Varen")
    assert [m["kind"] for m in world.get(f"{W}/items/{item['id']}").json()["mentions"]] == ["near_miss", "exact"]
    world.patch(f"{W}/entities/{v['id']}", json={"base_version": 1, "name": "Varren", "aliases": ["Varen"]})
    assert [m["kind"] for m in world.get(f"{W}/items/{item['id']}").json()["mentions"]] == ["exact", "alias"]
    r = world.patch(f"{W}/entities/{v['id']}", json={"base_version": 1, "body": "stale"})
    assert r.status_code == 409 and r.json()["entity"]["name"] == "Varren"


def test_name_check_lists_and_fixes(world: Client):
    v = add(world, "Mordoch")
    i = add(world, "Isolde")
    a = capture(world, "Modroch sails. Modroch's ship.")
    capture(world, "Isolda writes to Modroch.")
    world.post(f"{W}/journal", json={"body": "Is Isolda the same as Isolde?"})

    groups = world.get(f"{W}/near-misses").json()
    assert [(g["token"], g["entity"]["name"], g["count"]) for g in groups] == [("Modroch", "Mordoch", 3), ("Isolda", "Isolde", 2)]
    assert world.get(f"{W}/near-misses/count").json() == {"words": 2}

    # fix 1: replace everywhere, keeping the possessive
    r = world.post(f"{W}/near-misses/replace", json={"token": "Modroch", "entity_id": v["id"]})
    assert r.json() == {"replaced": 3}
    fixed = world.get(f"{W}/items/{a['id']}").json()
    assert (fixed["body"], fixed["version"]) == ("Mordoch sails. Mordoch's ship.", 2)

    # fix 2: "not a typo" for one word, and it can be taken back
    world.post(f"{W}/name-ignores", json={"token": "Isolda"})
    assert world.get(f"{W}/near-misses").json() == []
    assert world.get(f"{W}/name-ignores").json() == ["Isolda"]
    world.delete(f"{W}/name-ignores/Isolda")
    assert [g["token"] for g in world.get(f"{W}/near-misses").json()] == ["Isolda"]

    # fix 3: add it as another spelling
    world.patch(f"{W}/entities/{i['id']}", json={"base_version": 1, "aliases": ["Isolda"]})
    assert world.get(f"{W}/near-misses").json() == []
    assert world.get(f"{W}/entities/{i['id']}").json()["entity"]["mention_count"] == 3


def test_replace_in_one_text_only(world: Client):
    v = add(world, "Mordoch")
    a = capture(world, "Modroch here")
    b = capture(world, "Modroch there")
    world.post(f"{W}/near-misses/replace", json={"token": "Modroch", "entity_id": v["id"], "source_table": "item",
                                                  "source_id": a["id"]})
    assert world.get(f"{W}/items/{a['id']}").json()["body"] == "Mordoch here"
    assert world.get(f"{W}/items/{b['id']}").json()["body"] == "Modroch there"


def test_deleting_an_entity_removes_its_mentions_and_tags(world: Client):
    v = add(world, "Varren")
    item = capture(world, "Varren", entities=[v["id"]])
    assert world.delete(f"{W}/entities/{v['id']}").status_code == 204
    after = world.get(f"{W}/items/{item['id']}").json()
    assert (after["entities"], after["mentions"]) == ([], [])
    assert world.get(f"{W}/entities/{v['id']}").status_code == 404


def test_journal(world: Client):
    e = world.post(f"{W}/journal", json={"title": "What now?", "body": "Long thoughts.", "entry_date": "2026-10-01",
                                         "project": "book-one"}).json()
    world.post(f"{W}/journal", json={"body": "Shorter."})
    assert [x["title"] for x in world.get(f"{W}/journal").json()] == [None, "What now?"]
    assert [x["id"] for x in world.get(f"{W}/journal?project=book-one").json()] == [e["id"]]
    r = world.patch(f"{W}/journal/{e['id']}", json={"base_version": 1, "body": "Longer thoughts.", "title": None})
    assert (r.json()["body"], r.json()["title"], r.json()["version"]) == ("Longer thoughts.", None, 2)
    assert world.patch(f"{W}/journal/{e['id']}", json={"base_version": 1, "body": "x"}).status_code == 409
    assert world.delete(f"{W}/journal/{e['id']}").status_code == 204
    assert world.get(f"{W}/journal/{e['id']}").status_code == 404


def test_bible_is_private_to_the_world(world: Client):
    v = add(world, "Varren")
    world.post("/api/worlds", json={"name": "Other"})
    assert world.get(f"/api/worlds/other/entities/{v['id']}").status_code == 404
    item = world.post("/api/worlds/other/items", json={"body": "Varren?"}).json()
    assert item["mentions"] == []
    r = world.post(f"/api/worlds/other/items/{item['id']}/links", json={"entity_id": v["id"]})
    assert r.status_code == 422
