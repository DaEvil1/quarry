"""The world model: entry fields, facts, relationship types and relationships, cards, decision tags."""

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


def types(c: Client) -> dict[str, dict]:
    return {f"{t['a_kind']}>{t['b_kind']}:{t['label']}": t for t in c.get(f"{W}/relation-types").json()}


def test_new_worlds_get_the_starting_vocabulary(world: Client):
    t = types(world)
    assert t["character>character:parent of"]["reverse_label"] == "child of"
    assert t["character>character:sibling of"]["reverse_label"] is None
    assert t["object>place:hidden in"]["reverse_label"] == "hides"
    assert t["*>*:linked to"]["used"] == 0
    assert len(t) > 60


def test_entry_fields_and_new_kinds(world: Client):
    e = add(world, "The Lamp Guild", "faction", summary="  Keepers   of the light ")
    assert (e["kind"], e["summary"], e["match_case"], e["first_name_alias"], e["exclusions"]) == (
        "faction", "Keepers of the light", True, True, [])
    add(world, "Sea Folk", "culture")
    add(world, "The Long Storm", "event")
    r = world.patch(f"{W}/entities/{e['id']}", json={"base_version": 1, "match_case": False,
                                                    "exclusions": ["lamp guild hall", " "]})
    assert (r.json()["match_case"], r.json()["exclusions"]) == (False, ["lamp guild hall"])


def test_matching_options_change_what_is_found(world: Client):
    hale = add(world, "Varren Hale")
    item = world.post(f"{W}/items", json={"body": "Varren and varren hale"}).json()
    assert [(m["matched_text"], m["kind"]) for m in item["mentions"]] == [("Varren", "alias")]
    world.patch(f"{W}/entities/{hale['id']}", json={"base_version": 1, "match_case": False})
    again = world.get(f"{W}/items/{item['id']}").json()
    assert [m["matched_text"] for m in again["mentions"]] == ["Varren", "varren hale"]
    assert all(m["entity_kind"] == "character" for m in again["mentions"])


def test_facts(world: Client):
    v = add(world, "Varren")
    world.post(f"{W}/projects/book-one/chapters", json={"title": "One", "body": "His grey eyes."})
    ch = world.get(f"{W}/projects/book-one/chapters").json()["chapters"][0]
    a = world.post(f"{W}/entities/{v['id']}/facts", json={"label": " eye  colour", "value": "grey ",
                                                          "evidence": "His grey eyes.",
                                                          "established_in_chapter_id": ch["id"]}).json()
    b = world.post(f"{W}/entities/{v['id']}/facts", json={"label": "status", "value": "alive"}).json()
    assert (a["label"], a["value"], a["position"], b["position"]) == ("eye colour", "grey", 0, 1)
    r = world.patch(f"{W}/facts/{a['id']}", json={"base_version": 1, "value": "storm grey", "evidence": None})
    assert (r.json()["value"], r.json()["evidence"], r.json()["version"]) == ("storm grey", None, 2)
    assert world.patch(f"{W}/facts/{a['id']}", json={"base_version": 1, "value": "x"}).status_code == 409
    order = world.put(f"{W}/entities/{v['id']}/fact-order", json={"ids": [b["id"], a["id"]]}).json()
    assert [f["label"] for f in order] == ["status", "eye colour"]
    d = world.get(f"{W}/entities/{v['id']}").json()
    assert [f["label"] for f in d["facts"]] == ["status", "eye colour"]
    assert world.delete(f"{W}/facts/{b['id']}").status_code == 204
    sugg = world.get(f"{W}/fact-suggestions").json()
    assert "status" in sugg["character"] and "eye colour" in sugg["character"]


def test_relationships_read_both_ways(world: Client):
    v = add(world, "Varren")
    i = add(world, "Isolde")
    h = add(world, "Old Harbour", "place")
    g = add(world, "Lamp Guild", "faction")
    t = types(world)
    world.post(f"{W}/relationships", json={"type_id": t["character>character:parent of"]["id"], "a_id": v["id"],
                                           "b_id": i["id"]})
    world.post(f"{W}/relationships", json={"type_id": t["character>place:lives in"]["id"], "a_id": v["id"],
                                           "b_id": h["id"]})
    world.post(f"{W}/relationships", json={"type_id": t["character>faction:member of"]["id"], "a_id": v["id"],
                                           "b_id": g["id"], "standing": "planned"})
    vd = world.get(f"{W}/entities/{v['id']}").json()
    assert sorted((r["reads"], r["other"]["name"], r["standing"]) for r in vd["relationships"]) == [
        ("lives in", "Old Harbour", "canon"), ("member of", "Lamp Guild", "planned"), ("parent of", "Isolde", "canon")]
    idet = world.get(f"{W}/entities/{i['id']}").json()
    assert [(r["reads"], r["other"]["name"], r["side"]) for r in idet["relationships"]] == [("child of", "Varren", "b")]
    hd = world.get(f"{W}/entities/{h['id']}").json()
    assert [r["reads"] for r in hd["relationships"]] == ["home of"]


def test_relationship_rules(world: Client):
    v = add(world, "Varren")
    h = add(world, "Old Harbour", "place")
    t = types(world)
    # the type must fit the kinds on each side; "*" fits anything; nothing relates to itself
    r = world.post(f"{W}/relationships", json={"type_id": t["character>character:parent of"]["id"], "a_id": v["id"],
                                               "b_id": h["id"]})
    assert r.status_code == 422
    assert world.post(f"{W}/relationships", json={"type_id": t["*>*:linked to"]["id"], "a_id": h["id"],
                                                  "b_id": v["id"]}).status_code == 201
    assert world.post(f"{W}/relationships", json={"type_id": t["*>*:linked to"]["id"], "a_id": v["id"],
                                                  "b_id": v["id"]}).status_code == 422
    rel = world.get(f"{W}/relationships").json()[0]
    r = world.patch(f"{W}/relationships/{rel['id']}", json={"base_version": 1, "standing": "rumour", "note": "said so"})
    assert (r.json()["standing"], r.json()["note"]) == ("rumour", "said so")
    assert world.patch(f"{W}/relationships/{rel['id']}", json={"base_version": 1, "note": "x"}).status_code == 409
    # a type in use can't be removed; a renamed type renames every relationship using it
    assert world.delete(f"{W}/relation-types/{t['*>*:linked to']['id']}").status_code == 409
    world.patch(f"{W}/relation-types/{t['*>*:linked to']['id']}", json={"label": "tied to"})
    assert world.get(f"{W}/relationships").json()[0]["label"] == "tied to"
    # deleting an entry takes its relationships with it
    world.delete(f"{W}/entities/{h['id']}")
    assert world.get(f"{W}/relationships").json() == []


def test_custom_types(world: Client):
    r = world.post(f"{W}/relation-types", json={"a_kind": "character", "b_kind": "object", "label": "fears",
                                                "reverse_label": "feared by"})
    assert r.status_code == 201
    assert world.post(f"{W}/relation-types", json={"a_kind": "dragon", "b_kind": "*", "label": "x"}).status_code == 422
    assert world.delete(f"{W}/relation-types/{r.json()['id']}").status_code == 204


def test_cards(world: Client):
    v = add(world, "Varren Hale", aliases=["the Grey Keeper"], summary="Lighthouse keeper")
    add(world, "Lord Mordoch")
    i = add(world, "Isolde")
    world.post(f"{W}/entities/{v['id']}/facts", json={"label": "status", "value": "alive"})
    world.post(f"{W}/entities/{v['id']}/facts", json={"label": "secret", "value": "x", "standing": "planned"})
    t = types(world)
    world.post(f"{W}/relationships", json={"type_id": t["character>character:parent of"]["id"], "a_id": v["id"],
                                           "b_id": i["id"]})
    cards = {c["name"]: c for c in world.get(f"{W}/cards").json()}
    vc = cards["Varren Hale"]
    assert (vc["kind"], vc["first_name"], vc["summary"], vc["aliases"]) == (
        "character", "Varren", "Lighthouse keeper", ["the Grey Keeper"])
    assert vc["facts"] == [{"label": "status", "value": "alive"}]
    assert [(r["label"], r["other"]["name"]) for r in vc["relations"]] == [("parent of", "Isolde")]
    assert [(r["label"], r["other"]["name"]) for r in cards["Isolde"]["relations"]] == [("child of", "Varren Hale")]
    assert cards["Lord Mordoch"]["first_name"] == "Mordoch"
    assert cards["Isolde"]["first_name"] is None


def test_decisions_tagged_with_entries(world: Client):
    v = add(world, "Varren")
    i = add(world, "Isolde")
    d = world.post(f"{W}/decisions", json={"text": "The keeper stays", "entities": [v["id"]]}).json()
    assert [e["name"] for e in d["entities"]] == ["Varren"]
    world.post(f"{W}/decisions", json={"text": "Isolde leaves in spring"})
    vd = world.get(f"{W}/entities/{v['id']}").json()
    assert [(x["text"], x["tagged"]) for x in vd["decisions"]] == [("The keeper stays", True)]
    idet = world.get(f"{W}/entities/{i['id']}").json()
    assert [(x["text"], x["tagged"]) for x in idet["decisions"]] == [("Isolde leaves in spring", False)]
    r = world.patch(f"{W}/decisions/{d['id']}", json={"entities": [v["id"], i["id"]]})
    assert [e["name"] for e in r.json()["entities"]] == ["Isolde", "Varren"]
