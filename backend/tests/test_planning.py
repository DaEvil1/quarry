"""Phase 13a, the Journal as a workplace (docs/SPEC.md §14.1–§14.3): journal entries saved like chapters, with
revisions and the offline copy; what was planned in the Journal kept beside what is canon in the book; the planning
reading's items and decisions; items made from a passage; and export and Restore keeping all of it."""

from __future__ import annotations

import pytest

from .conftest import Client

W = "/api/worlds/delta"


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Delta"})
    signed_in.post(f"{W}/projects", json={"name": "The Salt Road"})
    return signed_in


def add(c: Client, name: str, kind: str = "character", **extra) -> dict:
    r = c.post(f"{W}/entities", json={"name": name, "kind": kind, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def entry(c: Client, body: str, title: str = "What the Guild wants", day: str = "2019-03-02", **extra) -> dict:
    r = c.post(f"{W}/journal", json={"title": title, "body": body, "entry_date": day, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def chapter(c: Client, title: str, body: str) -> dict:
    r = c.post(f"{W}/projects/the-salt-road/chapters", json={"title": title, "body": body})
    assert r.status_code == 201, r.text
    return r.json()


def types(c: Client) -> dict[str, dict]:
    return {t["label"]: t for t in c.get(f"{W}/relation-types").json()}


GUILD = "The Lamp Guild has kept the Lamp lit for three hundred years. Varren knows it; Isolde doesn't."


# journal entries in the editor (§14.1.1) -----------------------------------------------------------------------


def test_an_entry_is_saved_like_a_chapter(world: Client):
    add(world, "Varren")
    j = entry(world, "Varren thinks.")
    assert j["version"] == 1 and j["words"] == 2
    assert [m["entity_name"] for m in j["mentions"]] == ["Varren"]
    # autosave with the version it started from; a stale version answers with the newer entry
    r = world.patch(f"{W}/journal/{j['id']}", json={"base_version": 1, "body": "Varren thinks again."})
    assert r.status_code == 200 and r.json()["version"] == 2
    stale = world.patch(f"{W}/journal/{j['id']}", json={"base_version": 1, "body": "Lost?"})
    assert stale.status_code == 409 and stale.json()["entry"]["body"] == "Varren thinks again."
    # snapshots: an automatic one is skipped when nothing changed; a checkpoint keeps its label
    assert world.post(f"{W}/journal/{j['id']}/revisions", json={"reason": "autosnap"}).json()["skipped"] is False
    assert world.post(f"{W}/journal/{j['id']}/revisions", json={"reason": "autosnap"}).json()["skipped"] is True
    world.patch(f"{W}/journal/{j['id']}", json={"base_version": 2, "body": "Varren knows."})
    world.post(f"{W}/journal/{j['id']}/revisions", json={"reason": "checkpoint", "label": "first idea"})
    world.post(f"{W}/journal/{j['id']}/revisions", json={"reason": "conflict", "body": "Lost?"})
    revs = world.get(f"{W}/journal/{j['id']}/revisions").json()
    assert [(r["reason"], r["label"]) for r in revs] == [("conflict", None), ("checkpoint", "first idea"),
                                                         ("autosnap", None)]
    old = next(r for r in revs if r["reason"] == "autosnap")
    assert world.get(f"{W}/revisions/{old['id']}").json()["body"] == "Varren thinks again."
    # restore keeps the text it replaces
    back = world.post(f"{W}/journal/{j['id']}/restore", json={"revision_id": old["id"]}).json()
    assert back["body"] == "Varren thinks again." and back["version"] == 4
    assert world.get(f"{W}/journal/{j['id']}/revisions").json()[0]["reason"] == "restore"
    # the date and project are labels: no new version, so another device's save isn't a conflict
    about = world.patch(f"{W}/journal/{j['id']}/about", json={"entry_date": "2020-01-01", "project": "the-salt-road"})
    assert (about.json()["entry_date"], about.json()["project"], about.json()["version"]) == (
        "2020-01-01", "the-salt-road", 4)
    # journal revisions never count as words written in the book
    assert world.get(f"{W}/projects/the-salt-road/word-history").json()["revisions"] == []


def test_an_entry_made_offline_brings_its_id(world: Client):
    j = {"id": "2c6f1a52-6b5d-4d7c-9f0e-1a2b3c4d5e6f", "title": "On the train", "entry_date": "2026-10-25"}
    first = world.post(f"{W}/journal", json=j)
    again = world.post(f"{W}/journal", json=j)
    assert first.status_code == 201 and again.json()["id"] == j["id"]
    assert len(world.get(f"{W}/journal").json()) == 1


def test_the_offline_copy_carries_journal_entries(world: Client):
    j = entry(world, "Notes.")
    world.post(f"{W}/journal/{j['id']}/revisions", json={"reason": "checkpoint", "label": "kept"})
    pack = world.get(f"{W}/offline").json()
    assert [x["id"] for x in pack["journal"]] == [j["id"]] and pack["journal_ids"] == [j["id"]]
    assert [(r["chapter_id"], r["label"]) for r in pack["revisions"]] == [(j["id"], "kept")]
    later = world.get(f"{W}/offline", params={"since": pack["now"]}).json()
    assert later["journal"] == [] and later["journal_ids"] == [j["id"]]
    world.delete(f"{W}/journal/{j['id']}")
    assert world.get(f"{W}/offline", params={"since": pack["now"]}).json()["journal_ids"] == []


# planned in the Journal, canon in the book (§14.1.2) -----------------------------------------------------------


def test_a_fact_planned_in_the_journal(world: Client):
    guild = add(world, "the Lamp Guild", "faction")
    j = entry(world, GUILD)
    passage = "the Lamp Guild has kept the Lamp lit for three hundred years"
    f = world.post(f"{W}/entities/{guild['id']}/facts", json={
        "label": "age", "value": "three hundred years", "standing": "planned",
        "planned_in_journal_id": j["id"], "planned_evidence": passage}).json()
    assert (f["standing"], f["planned_in_journal_id"], f["planned_evidence"]) == ("planned", j["id"], passage)
    d = world.get(f"{W}/entities/{guild['id']}").json()
    assert d["journal_entries"][j["id"]]["date"] == "2019-03-02"
    assert d["journal_entries"][j["id"]]["title"] == "What the Guild wants"
    # the cards carry planned facts apart, for cards in the Journal
    card = next(c for c in world.get(f"{W}/cards").json() if c["id"] == guild["id"])
    assert card["facts"] == [] and [x["value"] for x in card["planned"]] == ["three hundred years"]
    assert world.post(f"{W}/entities/{guild['id']}/facts", json={
        "label": "x", "planned_in_journal_id": "2c6f1a52-6b5d-4d7c-9f0e-1a2b3c4d5e6f"}).status_code == 422


def test_make_it_canon_here(world: Client):
    seyla = add(world, "Seyla")
    j = entry(world, "Seyla dies at the flood.", title="Endings")
    nine = chapter(world, "The Flood", "The water took Seyla.")
    planned = world.post(f"{W}/entities/{seyla['id']}/facts", json={
        "label": "status", "value": "dead", "standing": "planned", "planned_in_journal_id": j["id"],
        "planned_evidence": "Seyla dies at the flood."}).json()
    made = world.post(f"{W}/entities/{seyla['id']}/facts", json={
        "label": "status", "value": "dead", "make_canon": planned["id"], "established_in_chapter_id": nine["id"],
        "evidence": "The water took Seyla.", "from_chapter_id": nine["id"]}).json()
    assert made["id"] == planned["id"]
    assert (made["standing"], made["established_in_chapter_id"], made["evidence"], made["from_chapter_id"]) == (
        "canon", nine["id"], "The water took Seyla.", nine["id"])
    # where it was planned stays
    assert (made["planned_in_journal_id"], made["planned_evidence"]) == (j["id"], "Seyla dies at the flood.")
    assert len(world.get(f"{W}/entities/{seyla['id']}").json()["facts"]) == 1
    # a relationship too: the same two, either way round
    varren = add(world, "Varren")
    t = types(world)["friend of"]
    rel = world.post(f"{W}/relationships", json={"type_id": t["id"], "a_id": varren["id"], "b_id": seyla["id"],
                                                 "standing": "planned", "planned_in_journal_id": j["id"]}).json()
    canon = world.post(f"{W}/relationships", json={"type_id": t["id"], "a_id": seyla["id"], "b_id": varren["id"],
                                                   "make_canon": rel["id"], "established_in_chapter_id": nine["id"],
                                                   "evidence": "x"}).json()
    assert (canon["id"], canon["standing"], canon["planned_in_journal_id"]) == (rel["id"], "canon", j["id"])
    other = add(world, "Isolde")
    assert world.post(f"{W}/relationships", json={"type_id": t["id"], "a_id": other["id"], "b_id": seyla["id"],
                                                  "make_canon": rel["id"]}).status_code == 422


def test_deleting_an_entry_keeps_what_was_planned_in_it(world: Client):
    guild = add(world, "the Lamp Guild", "faction")
    varren = add(world, "Varren")
    j = entry(world, GUILD)
    world.post(f"{W}/entities/{guild['id']}/facts", json={"label": "age", "value": "old", "standing": "planned",
                                                          "planned_in_journal_id": j["id"], "planned_evidence": "kept"})
    t = types(world)["member of"]
    world.post(f"{W}/relationships", json={"type_id": t["id"], "a_id": varren["id"], "b_id": guild["id"],
                                           "standing": "planned", "planned_in_journal_id": j["id"]})
    world.post(f"{W}/events/record", json={"name": "The Founding", "journal_id": j["id"], "passage": GUILD,
                                           "taking": [{"entity_id": guild["id"]}]})
    world.post(f"{W}/items", json={"body": "Why three hundred?", "kind": "question", "journal_id": j["id"],
                                   "passage": "three hundred years"})
    assert world.get(f"{W}/journal/{j['id']}/ties").json() == {"facts": 1, "relationships": 2, "notes": 1, "items": 1}
    assert world.delete(f"{W}/journal/{j['id']}").status_code == 204
    f = world.get(f"{W}/entities/{guild['id']}").json()["facts"][0]
    assert (f["planned_in_journal_id"], f["planned_evidence"]) == (None, "kept")
    item = world.get(f"{W}/items").json()[0]
    assert item["origin"] is None


def test_record_as_event_from_the_journal(world: Client):
    guild = add(world, "the Lamp Guild", "faction")
    varren = add(world, "Varren")
    j = entry(world, GUILD)
    r = world.post(f"{W}/events/record", json={"name": "The Founding", "journal_id": j["id"], "passage": GUILD,
                                               "taking": [{"entity_id": guild["id"]}, {"entity_id": varren["id"]}]})
    assert r.status_code == 201, r.text
    done = r.json()
    page = world.get(f"{W}/entities/{done['event_id']}").json()
    # the passage is a note (Noted in), not a telling
    assert page["tellings"] == []
    assert [(n["passage"], n["journal"]["date"], n["at"]) for n in page["notes"]] == [(GUILD, "2019-03-02", 0)]
    # participants are planned, planned in the entry
    assert sorted((x["standing"], x["planned_in_journal_id"], x["established_in_chapter_id"])
                  for x in page["relationships"]) == [("planned", j["id"], None)] * 2
    # the Timeline's told view reads tellings only; the card counts the notes
    chrono = world.get(f"{W}/chronology").json()
    assert chrono["tellings"] == [] and chrono["notes"] == {done["event_id"]: 1}
    # a chapter or an entry, not both and not neither
    ch = chapter(world, "One", "x")
    assert world.post(f"{W}/events/record", json={"name": "X", "journal_id": j["id"], "chapter_id": ch["id"],
                                                  "passage": "x"}).status_code == 422
    assert world.post(f"{W}/events/record", json={"name": "X", "passage": "x"}).status_code == 422
    # undo removes the note and what it added
    world.post(f"{W}/events/record/undo", json=done)
    assert world.get(f"{W}/chronology").json()["notes"] == {}


def test_names_in_the_journal_are_never_findings(world: Client):
    seyla = add(world, "Seyla")
    one = chapter(world, "One", "Seyla walks.")
    chapter(world, "Two", "Rain.")
    world.post(f"{W}/entities/{seyla['id']}/facts", json={"label": "status", "value": "dead", "from_chapter_id": one["id"]})
    entry(world, "Seyla again, Seyla everywhere.")
    dead = lambda: [f["rule"] for f in world.get(f"{W}/checks").json() if f["rule"] == "dead_mentioned"]  # noqa: E731
    assert dead() == []
    # the same name in a later chapter is one
    chapter(world, "Three", "Seyla returns.")
    assert dead() == ["dead_mentioned"]


# sparks and questions from a passage (§14.3) -------------------------------------------------------------------


def test_an_item_made_from_a_passage(world: Client):
    guild = add(world, "the Lamp Guild", "faction")
    j = entry(world, GUILD)
    q = world.post(f"{W}/items", json={"body": "Who lit it first?\n\n> the Lamp lit", "kind": "question",
                                       "entities": [guild["id"]], "journal_id": j["id"],
                                       "passage": "the Lamp lit"}).json()
    assert q["origin"] == {"table": "journal", "id": j["id"], "title": "What the Guild wants", "date": "2019-03-02",
                           "passage": "the Lamp lit"}
    assert [e["name"] for e in q["entities"]] == ["the Lamp Guild"]
    parked = world.post(f"{W}/items", json={"body": "A lamp that never goes out", "journal_id": j["id"],
                                            "passage": "kept the Lamp", "status": "deferred"}).json()
    assert parked["status"] == "deferred"
    # the entry's Loose ends list its open items with their passages
    assert [(i["kind"], i["passage"]) for i in world.get(f"{W}/journal/{j['id']}/items").json()] == [
        ("question", "the Lamp lit")]
    ch = chapter(world, "The Quay", "Isolde waited on the quay.")
    s = world.post(f"{W}/items", json={"body": "Why wait?", "chapter_id": ch["id"], "passage": "Isolde waited"}).json()
    assert (s["origin"]["table"], s["origin"]["title"], s["origin"]["passage"]) == ("chapter", "The Quay", "Isolde waited")
    assert [i["passage"] for i in world.get(f"{W}/chapters/{ch['id']}/items").json()] == ["Isolde waited"]


def test_the_planning_reading_reads_items_and_decisions(world: Client):
    varren = add(world, "Varren")
    isolde = add(world, "Isolde")
    world.post(f"{W}/items", json={"body": "How old is Varren?", "kind": "question",
                                   "captured_at": "2016-05-01T10:00:00+00:00"})
    tagged = world.post(f"{W}/items", json={"body": "The keeper's age", "entities": [varren["id"]]}).json()
    world.post(f"{W}/items", json={"body": "Varren and Isolde meet", "kind": "spark"})
    world.post(f"{W}/items", json={"body": "Nothing to do with anyone"})
    world.post(f"{W}/decisions", json={"text": "Varren stays", "decided_on": "2019-06-01"})
    world.post(f"{W}/decisions", json={"text": "The flood comes early", "decided_on": "2021-01-01",
                                       "entities": [varren["id"]]})
    p = world.get(f"{W}/planning", params={"entity": [varren["id"]]}).json()
    assert [i["body"] for i in p["items"]] == ["How old is Varren?", "The keeper's age", "Varren and Isolde meet"]
    mark = next(i for i in p["items"] if i["id"] == tagged["id"])
    assert (mark["names"], mark["tagged"]) == ([], [varren["id"]])
    assert [(d["text"], bool(d["tagged"])) for d in p["decisions"]] == [("Varren stays", False),
                                                                        ("The flood comes early", True)]
    both = world.get(f"{W}/planning", params={"entity": [varren["id"], isolde["id"]]}).json()
    meet = next(i for i in both["items"] if i["body"] == "Varren and Isolde meet")
    assert sorted(meet["names"]) == sorted([varren["id"], isolde["id"]])


# export and restore -------------------------------------------------------------------------------------------


def test_export_and_restore_keep_the_planning(world: Client):
    guild = add(world, "the Lamp Guild", "faction")
    varren = add(world, "Varren")
    j = entry(world, GUILD)
    ch = chapter(world, "The Quay", "Varren waits on the quay.")
    world.post(f"{W}/entities/{guild['id']}/facts", json={"label": "age", "value": "three hundred years",
                                                          "standing": "planned", "planned_in_journal_id": j["id"],
                                                          "planned_evidence": "three hundred years"})
    t = types(world)["member of"]
    world.post(f"{W}/relationships", json={"type_id": t["id"], "a_id": varren["id"], "b_id": guild["id"],
                                           "standing": "planned", "planned_in_journal_id": j["id"],
                                           "planned_evidence": "Varren knows it"})
    world.post(f"{W}/events/record", json={"name": "The Founding", "journal_id": j["id"], "passage": GUILD})
    world.post(f"{W}/items", json={"body": "Why?", "kind": "question", "journal_id": j["id"], "passage": "the Lamp lit"})
    world.post(f"{W}/items", json={"body": "Waiting", "chapter_id": ch["id"], "passage": "waits on the quay"})

    def look(slug: str) -> dict:
        base = f"/api/worlds/{slug}"
        ents = {e["name"]: e["id"] for e in world.get(f"{base}/entities").json()}
        journal = {x["id"]: x["title"] for x in world.get(f"{base}/journal").json()}
        g = world.get(f"{base}/entities/{ents['the Lamp Guild']}").json()
        founding = world.get(f"{base}/entities/{ents['The Founding']}").json()
        return {
            "facts": [(f["label"], f["standing"], journal.get(f["planned_in_journal_id"]), f["planned_evidence"])
                      for f in g["facts"]],
            "rels": [(r["reads"], r["standing"], journal.get(r["planned_in_journal_id"]), r["planned_evidence"])
                     for r in g["relationships"]],
            "notes": [(n["passage"], n["journal"]["title"]) for n in founding["notes"]],
            "tellings": founding["tellings"],
            "items": sorted(((i["origin"] or {}).get("table"), (i["origin"] or {}).get("title"),
                             (i["origin"] or {}).get("passage")) for i in world.get(f"{base}/items").json()),
        }

    before = look("delta")
    assert before["notes"] == [(GUILD, "What the Guild wants")]
    data = world.get(f"{W}/export").content
    r = world.post("/api/worlds/restore", files={"file": ("export.zip", data, "application/zip")})
    assert r.status_code == 201, r.text
    assert look(r.json()["slug"]) == before
