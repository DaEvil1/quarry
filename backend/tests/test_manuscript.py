"""Chapters, order, autosave with version checks, revisions and restore, retire/reinstate, experiments, salvage."""

from __future__ import annotations

import pytest

from .conftest import Client

W = "/api/worlds/coast"
P = f"{W}/projects/book-one"


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Book One"})
    return signed_in


def chapter(c: Client, title: str, body: str = "", **extra) -> dict:
    r = c.post(f"{P}/chapters", json={"title": title, "body": body, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_chapters_in_order_with_words_and_pov(world: Client):
    v = world.post(f"{W}/entities", json={"name": "Varren"}).json()
    s = world.post(f"{W}/entities", json={"name": "Isolde"}).json()
    a = chapter(world, "Arrival", "The boat comes in. Varren waits.", pov_entity_id=v["id"])
    b = chapter(world, "The lamp", "Isolde climbs the stairs.", pov_entity_id=s["id"])
    c = chapter(world, "Storm", "Rain, rain, rain.", pov_entity_id=v["id"])
    m = world.get(f"{P}/chapters").json()
    assert [(x["title"], x["position"], x["words"], x["pov"]["name"]) for x in m["chapters"]] == [
        ("Arrival", 0, 6, "Varren"), ("The lamp", 1, 4, "Isolde"), ("Storm", 2, 3, "Varren")]
    assert m["words"] == 13
    assert m["pov_tally"] == [{"name": "Varren", "chapters": 2}, {"name": "Isolde", "chapters": 1}]

    r = world.put(f"{P}/chapter-order", json={"ids": [c["id"], a["id"], b["id"]]})
    assert [x["title"] for x in r.json()] == ["Storm", "Arrival", "The lamp"]
    assert world.put(f"{P}/chapter-order", json={"ids": [a["id"]]}).status_code == 422


def test_autosave_with_version_check_and_mentions(world: Client):
    world.post(f"{W}/entities", json={"name": "Mordoch"})
    ch = chapter(world, "One", "draft")
    r = world.patch(f"{W}/chapters/{ch['id']}", json={"base_version": 1, "body": "Modroch sails at dawn."})
    saved = r.json()
    assert saved["version"] == 2
    assert [(m["matched_text"], m["kind"]) for m in saved["mentions"]] == [("Modroch", "near_miss")]
    # another device still on version 1
    r = world.patch(f"{W}/chapters/{ch['id']}", json={"base_version": 1, "body": "older text"})
    assert r.status_code == 409 and r.json()["chapter"]["body"] == "Modroch sails at dawn."
    # the name check fixes chapters too, and keeps the text before the fix
    entity = world.get(f"{W}/entities").json()[0]
    world.post(f"{W}/near-misses/replace", json={"token": "Modroch", "entity_id": entity["id"]})
    fixed = world.get(f"{W}/chapters/{ch['id']}").json()
    assert fixed["body"] == "Mordoch sails at dawn." and fixed["version"] == 3
    assert world.get(f"{W}/chapters/{ch['id']}/revisions").json()[0]["reason"] == "autosnap"


def test_revisions_skip_duplicates_and_restore_keeps_the_current_text(world: Client):
    ch = chapter(world, "One", "first words")
    cid = ch["id"]
    assert world.post(f"{W}/chapters/{cid}/revisions", json={"reason": "autosnap"}).json()["skipped"] is False
    assert world.post(f"{W}/chapters/{cid}/revisions", json={"reason": "autosnap"}).json()["skipped"] is True
    world.patch(f"{W}/chapters/{cid}", json={"base_version": 1, "body": "second words"})
    world.post(f"{W}/chapters/{cid}/revisions", json={"reason": "checkpoint", "label": "before the split"})
    revs = world.get(f"{W}/chapters/{cid}/revisions").json()
    assert [(r["reason"], r["label"], r["words"]) for r in revs] == [
        ("checkpoint", "before the split", 2), ("autosnap", None, 2)]
    first = world.get(f"{W}/revisions/{revs[1]['id']}").json()
    assert first["body"] == "first words"

    restored = world.post(f"{W}/chapters/{cid}/restore", json={"revision_id": revs[1]["id"]}).json()
    assert restored["body"] == "first words"
    revs = world.get(f"{W}/chapters/{cid}/revisions").json()
    assert revs[0]["reason"] == "restore"
    assert world.get(f"{W}/revisions/{revs[0]['id']}").json()["body"] == "second words"


def test_conflict_copy_keeps_the_losing_text(world: Client):
    ch = chapter(world, "One", "server text")
    r = world.post(f"{W}/chapters/{ch['id']}/revisions", json={"reason": "conflict", "body": "my offline text"})
    rev = world.get(f"{W}/revisions/{r.json()['id']}").json()
    assert (rev["reason"], rev["body"]) == ("conflict", "my offline text")
    assert world.post(f"{W}/chapters/{ch['id']}/revisions", json={"reason": "checkpoint", "body": "x"}).status_code == 422


def test_retire_reinstate_and_salvage_search(world: Client):
    a = chapter(world, "Arrival", "The boat comes in.")
    b = chapter(world, "Old opening", "A gull over the harbour.")
    c = chapter(world, "Storm", "Rain.")
    r = world.post(f"{W}/chapters/{b['id']}/retire", json={"note": "the gull image is worth keeping"})
    assert r.json()["state"] == "retired"
    m = world.get(f"{P}/chapters").json()
    assert [(x["title"], x["position"]) for x in m["chapters"]] == [("Arrival", 0), ("Storm", 1)]
    assert m["retired"] == 1
    salvage = world.get(f"{P}/salvage").json()
    assert [(s["title"], [n["body"] for n in s["harvest_notes"]]) for s in salvage] == [
        ("Old opening", ["the gull image is worth keeping"])]
    assert world.get(f"{P}/salvage?q=harbour").json()[0]["match"]["match"] == "harbour"
    assert len(world.get(f"{P}/salvage?q=worth keeping").json()) == 1
    assert world.get(f"{P}/salvage?q=nothing").json() == []
    assert world.post(f"{W}/chapters/{b['id']}/retire", json={}).status_code == 409

    back = world.post(f"{W}/chapters/{b['id']}/reinstate").json()
    assert (back["state"], back["position"]) == ("current", 2)
    assert [x["title"] for x in world.get(f"{P}/chapters").json()["chapters"]] == ["Arrival", "Storm", "Old opening"]
    assert a and c


def test_only_empty_chapters_can_be_deleted(world: Client):
    empty = chapter(world, "Oops")
    full = chapter(world, "Real", "words")
    assert world.delete(f"{W}/chapters/{full['id']}").status_code == 409
    assert world.delete(f"{W}/chapters/{empty['id']}").status_code == 204
    assert [x["position"] for x in world.get(f"{P}/chapters").json()["chapters"]] == [0]


def test_experiment_accepted_takes_the_old_place(world: Client):
    chapter(world, "One", "first")
    two = chapter(world, "Two", "the old second chapter")
    chapter(world, "Three", "third")
    exp = world.post(f"{W}/chapters/{two['id']}/experiments", json={"start": "scratch"}).json()
    assert (exp["state"], exp["body"], exp["replaces_title"], exp["experiment_status"]) == (
        "experiment", "", "Two", "open")
    # it shows up in the manuscript and as an experiment item in the inbox
    m = world.get(f"{P}/chapters").json()
    assert [x["title"] for x in m["experiments"]] == ["Two"]
    items = world.get(f"{W}/items?kind=experiment").json()
    assert len(items) == 1 and "from scratch" in items[0]["body"]
    # an experiment item can't be closed from the inbox, only from its chapter
    assert world.post(f"{W}/items/{items[0]['id']}/close", json={"status": "accepted"}).status_code == 409

    world.patch(f"{W}/chapters/{exp['id']}", json={"base_version": exp["version"], "body": "a new second chapter"})
    done = world.post(f"{W}/chapters/{exp['id']}/close-experiment", json={
        "outcome": "accepted", "note": "kept the opening line", "decision": "Chapter two starts at sea"}).json()
    assert (done["state"], done["position"]) == ("current", 1)
    m = world.get(f"{P}/chapters").json()
    assert [(x["title"], x["state"]) for x in m["chapters"]] == [("One", "current"), ("Two", "current"), ("Three", "current")]
    assert m["chapters"][1]["id"] == exp["id"] and m["experiments"] == []
    salvage = world.get(f"{P}/salvage").json()
    assert [(s["id"], s["harvest_notes"][0]["body"]) for s in salvage] == [(two["id"], "kept the opening line")]
    assert world.get(f"{W}/items/{items[0]['id']}").json()["status"] == "accepted"
    assert [d["text"] for d in world.get(f"{W}/decisions").json()] == ["Chapter two starts at sea"]


def test_experiment_harvested_or_rejected_leaves_the_book_alone(world: Client):
    one = chapter(world, "One", "original")
    exp = world.post(f"{W}/chapters/{one['id']}/experiments", json={"start": "copy", "title": "One, again"}).json()
    assert exp["body"] == "original" and exp["title"] == "One, again"
    done = world.post(f"{W}/chapters/{exp['id']}/close-experiment",
                      json={"outcome": "harvested", "note": "the second paragraph"}).json()
    assert done["state"] == "retired"
    m = world.get(f"{P}/chapters").json()
    assert [x["id"] for x in m["chapters"]] == [one["id"]] and m["experiments"] == []
    assert world.post(f"{W}/chapters/{exp['id']}/close-experiment", json={"outcome": "accepted"}).status_code == 409
    assert world.post(f"{W}/chapters/{exp['id']}/experiments", json={}).status_code == 409


def test_first_appearance_on_the_bible_page(world: Client):
    v = world.post(f"{W}/entities", json={"name": "Varren"}).json()
    chapter(world, "One", "Nobody here.")
    two = chapter(world, "Two", "Varren arrives.")
    chapter(world, "Three", "Varren again.")
    d = world.get(f"{W}/entities/{v['id']}").json()
    assert [(f["project"], f["title"]) for f in d["first_appearance"]] == [("book-one", "Two")]
    assert d["mentions"][0]["source_table"] == "chapter"
    assert two


def test_chapters_belong_to_their_world(world: Client):
    ch = chapter(world, "One", "x")
    world.post("/api/worlds", json={"name": "Other"})
    assert world.get(f"/api/worlds/other/chapters/{ch['id']}").status_code == 404
    assert world.get("/api/worlds/other/projects/book-one/chapters").status_code == 404


def test_offline_pack(world: Client):
    import time

    a = chapter(world, "One", "first")
    b = chapter(world, "Two", "second")
    for i in range(33):
        world.patch(f"{W}/chapters/{a['id']}", json={"base_version": i + 1, "body": f"version {i}"})
        world.post(f"{W}/chapters/{a['id']}/revisions", json={"reason": "autosnap"})
    full = world.get(f"{W}/offline").json()
    assert {c["title"] for c in full["chapters"]} == {"One", "Two"}
    assert len([r for r in full["revisions"] if r["chapter_id"] == a["id"]]) == 30
    assert set(full["chapter_ids"]) == {a["id"], b["id"]}
    assert all(r["body"].startswith("version") for r in full["revisions"])

    # later: only what changed since, including a chapter that only gained a revision
    since = full["now"]
    time.sleep(0.05)
    world.post(f"{W}/chapters/{b['id']}/revisions", json={"reason": "checkpoint", "label": "kept"})
    later = world.get(f"{W}/offline", params={"since": since}).json()
    assert [c["title"] for c in later["chapters"]] == ["Two"]
    assert [r["label"] for r in later["revisions"]] == ["kept"]
    assert set(later["chapter_ids"]) == {a["id"], b["id"]}


def test_offline_restore_keeps_the_replaced_text(world: Client):
    ch = chapter(world, "One", "now")
    r = world.post(f"{W}/chapters/{ch['id']}/revisions", json={"reason": "restore", "body": "text written offline"})
    rev = world.get(f"{W}/revisions/{r.json()['id']}").json()
    assert (rev["reason"], rev["body"]) == ("restore", "text written offline")
