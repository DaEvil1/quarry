"""Phase 13b, getting back in and checking (docs/SPEC.md §14.4–§14.9): the front page and the premise, the note for
next time in a journal entry, "since this was written", "Include planned" on the checks, an effect before its cause,
an entry of more than one kind, and the focus per world."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
    r = c.post(f"{W}/entities", json={"name": name, "kind": kind, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def chapter(c: Client, title: str, body: str) -> dict:
    return c.post(f"{W}/projects/the-salt-road/chapters", json={"title": title, "body": body}).json()


def types(c: Client) -> dict[str, dict]:
    return {t["label"]: t for t in c.get(f"{W}/relation-types").json()}


def rules(c: Client, **params) -> list[tuple]:
    return [(f["rule"], f["planned"], (f["chapter"] or {}).get("title"), f["message"]) for f in c.get(f"{W}/checks", params=params).json()]


def stamp(db, table: str, row_id: str, when: str, *columns: str) -> None:
    """Move a row's timestamps into the past (the tests can't wait years)."""
    sets = ", ".join(f"{c} = :w" for c in columns)
    db.execute(text(f"UPDATE {table} SET {sets} WHERE id = :id"), {"w": datetime.fromisoformat(when).replace(tzinfo=UTC), "id": uuid.UUID(row_id)})
    db.commit()


# the front page (§14.4) ---------------------------------------------------------------------------------------


def test_premise_and_the_front_page(world: Client):
    r = world.patch(W, json={"premise": "  A delta that   remembers.  "})
    assert r.json()["premise"] == "A delta that remembers."
    assert world.patch(W, json={"premise": "x" * 301}).status_code == 422
    v = add(world, "Varren")
    ch = chapter(world, "The Quay", "Varren waited.")
    world.put(f"{W}/chapters/{ch['id']}/session-note", json={"note": "Isolde has to find out before the flood", "cursor": 5})
    j = world.post(f"{W}/journal", json={"title": "What the Guild wants", "entry_date": "2019-03-02", "body": "Varren."}).json()
    world.put(f"{W}/journal/{j['id']}/session-note", json={"note": "the toll next", "cursor": 3})
    assert world.get(f"{W}/journal/{j['id']}/session-note").json()["note"] == "the toll next"
    for n in range(7):
        world.post(f"{W}/decisions", json={"text": f"Decision {n}", "decided_on": f"2020-01-0{n + 1}"})
    world.post(f"{W}/items", json={"body": "Why the flood?", "kind": "question", "captured_at": "2015-02-01T10:00:00+00:00"})
    world.post(f"{W}/items", json={"body": "Who rows?", "kind": "question"})
    world.post(f"{W}/entities/{v['id']}/facts", json={"label": "age", "value": "40"})
    front = world.get(f"{W}/front").json()
    assert front["premise"] == "A delta that remembers."
    assert [(n["source"], n["note"]) for n in front["notes"]] == [("journal", "the toll next"), ("chapter", "Isolde has to find out before the flood")]
    assert [d["text"] for d in front["decisions"]] == [f"Decision {n}" for n in (6, 5, 4, 3, 2)]
    assert front["questions"]["count"] == 2 and front["questions"]["oldest"].startswith("2015")
    assert front["questions"]["latest"][0]["body"] == "Who rows?"
    kinds = {e["kind"] for e in front["lately"]}
    assert {"words", "journal", "entity", "fact", "captured", "decision"} <= kinds
    assert front["projects"] == [{"slug": "the-salt-road", "words": 2, "chapters": 1, "last_written": front["projects"][0]["last_written"]}]


def test_the_focus_per_person_and_world(world: Client):
    assert world.get(W).json()["focus"] == "writing"
    assert world.put(f"{W}/focus", json={"focus": "planning"}).json()["focus"] == "planning"
    assert next(w for w in world.get("/api/worlds").json() if w["slug"] == "delta")["focus"] == "planning"
    assert world.put(f"{W}/focus", json={"focus": "dreaming"}).status_code == 422


# since this was written (§14.5) ----------------------------------------------------------------------------------


def test_since_this_was_written(world: Client, db):
    v = add(world, "Varren")
    g = add(world, "the Lamp Guild", "faction")
    i = add(world, "Isolde")
    old = world.post(f"{W}/journal", json={"title": "What the Guild wants", "entry_date": "2019-03-02",
                                           "body": "Varren and the Lamp Guild."}).json()
    for e in (v, g, i):
        stamp(db, "entities", e["id"], "2018-01-01", "created_at", "updated_at")
    d = world.post(f"{W}/decisions", json={"text": "The keeper stays", "decided_on": "2021-05-01", "entities": [v["id"]]}).json()
    world.post(f"{W}/decisions", json={"text": "Before it all", "decided_on": "2018-05-01", "entities": [v["id"]]})
    f = world.post(f"{W}/entities/{g['id']}/facts", json={"label": "age", "value": "old"}).json()
    stamp(db, "facts", f["id"], "2022-02-01", "created_at", "updated_at")
    t = types(world)
    r1 = world.post(f"{W}/relationships", json={"type_id": t["member of"]["id"], "a_id": v["id"], "b_id": g["id"]}).json()
    r2 = world.post(f"{W}/relationships", json={"type_id": t["friend of"]["id"], "a_id": v["id"], "b_id": i["id"]}).json()
    for r in (r1, r2):
        stamp(db, "relationships", r["id"], "2018-01-01", "created_at")
        stamp(db, "relationships", r["id"], "2024-03-03", "updated_at")
    later = world.post(f"{W}/journal", json={"title": "Later", "entry_date": "2023-01-01", "body": "Varren again."}).json()
    stamp(db, "journal", old["id"], "2019-03-02", "created_at", "updated_at")
    stamp(db, "journal", later["id"], "2023-01-01", "created_at", "updated_at")
    s = world.get(f"{W}/journal/{old['id']}/since").json()
    assert (s["decisions"], s["changes"], s["later"]) == (1, 3, 1)
    varren = next(x for x in s["entities"] if x["entity"]["name"] == "Varren")
    assert [x["text"] for x in varren["decisions"]] == ["The keeper stays"]
    assert {c["date"] for c in varren["changes"]} == {"2024-03-03"}
    guild = next(x for x in s["entities"] if x["entity"]["name"] == "the Lamp Guild")
    assert ("age: old recorded", "2022-02-01") in [(c["what"], c["date"]) for c in guild["changes"]]
    listed = {e["title"]: e["since"] for e in world.get(f"{W}/journal").json()}
    assert listed["What the Guild wants"] == 4
    # an entry written today shows nothing
    today = world.post(f"{W}/journal", json={"title": "Today", "body": "Varren and the Lamp Guild."}).json()
    assert world.get(f"{W}/journal/{today['id']}/since").json()["entities"] == []
    assert {e["title"]: e["since"] for e in world.get(f"{W}/journal").json()}["Today"] == 0
    assert d


# include planned (§14.6) -------------------------------------------------------------------------------------------


def test_include_planned(world: Client):
    seyla = add(world, "Seyla")
    chs = [chapter(world, f"Chapter {n}", "Seyla walks." if n == 12 else "Rain.") for n in range(1, 13)]
    world.post(f"{W}/entities/{seyla['id']}/facts", json={"label": "status", "value": "dead", "standing": "planned",
                                                          "from_chapter_id": chs[8]["id"]})
    assert [x for x in rules(world) if x[0] == "dead_mentioned"] == []
    found = [x for x in rules(world, planned=1) if x[0] == "dead_mentioned"]
    assert found == [("dead_mentioned", True, "Chapter 12", "Seyla is named in “Chapter 12”, but is planned dead from “Chapter 9”.")]
    # a rumoured death is never listed
    other = add(world, "Brann")
    world.post(f"{W}/entities/{other['id']}/facts", json={"label": "status", "value": "dead", "standing": "rumour",
                                                          "from_chapter_id": chs[0]["id"]})
    world.post(f"{W}/projects/the-salt-road/chapters", json={"title": "Chapter 13", "body": "Brann sings."})
    assert not any("Brann" in x[3] for x in rules(world, planned=1))


def test_include_planned_without_chapters_compares_times(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Delta"})
    v = add(signed_in, "Varren")
    for value, start, end in (("keeper", 300, 340), ("smith", 320, None)):
        signed_in.post(f"{W}/entities/{v['id']}/facts", json={"label": "trade", "value": value, "standing": "planned",
                                                              "from_time": start, **({"until_time": end} if end else {})})
    assert rules(signed_in) == []
    (f,) = rules(signed_in, planned=1)
    assert f[:3] == ("fact_conflict", True, None) and "keeper" in f[3] and "smith" in f[3]


# cause arrows and their check (§14.7) ------------------------------------------------------------------------------


def test_an_effect_before_its_cause(world: Client):
    founding = add(world, "The Founding", "event")
    wars = add(world, "The Lamp Wars", "event")
    t = types(world)
    caused = next((x for x in t.values() if x["label"] == "caused"), None)
    if caused is None:
        caused = world.post(f"{W}/relation-types", json={"a_kind": "event", "b_kind": "*", "label": "caused",
                                                         "reverse_label": "caused by"}).json()
    world.post(f"{W}/relationships", json={"type_id": caused["id"], "a_id": wars["id"], "b_id": founding["id"]})
    # not placed yet: skipped
    assert [x for x in rules(world) if x[0] == "cause_after_effect"] == []
    for e, at in ((wars, 40), (founding, 0)):
        cur = world.get(f"{W}/entities/{e['id']}").json()["entity"]
        world.patch(f"{W}/entities/{e['id']}", json={"base_version": cur["version"], "time_at": at})
    (f,) = [x for x in rules(world) if x[0] == "cause_after_effect"]
    assert f[2] is None and f[3] == "The Lamp Wars (year 40) caused The Founding (year 0), which comes before it."
    # the same time is not a finding
    cur = world.get(f"{W}/entities/{founding['id']}").json()["entity"]
    world.patch(f"{W}/entities/{founding['id']}", json={"base_version": cur["version"], "time_at": 40})
    assert [x for x in rules(world) if x[0] == "cause_after_effect"] == []


# an entry of more than one kind (§14.8) --------------------------------------------------------------------------


def test_an_entry_of_more_than_one_kind(world: Client):
    ash = add(world, "Ashgard Vale", "place")
    harbour = add(world, "Old Harbour", "place")
    guild = add(world, "the Lamp Guild", "faction")
    t = types(world)
    inside = next(x for x in t.values() if x["a_kind"] == "place" and x["b_kind"] == "place" and x["label"] in ("in", "inside", "part of"))
    world.post(f"{W}/relationships", json={"type_id": inside["id"], "a_id": harbour["id"], "b_id": ash["id"]})
    leads = t["leads"]
    assert world.post(f"{W}/relationships", json={"type_id": leads["id"], "a_id": ash["id"], "b_id": guild["id"]}).status_code == 422
    e = world.patch(f"{W}/entities/{ash['id']}", json={"base_version": ash["version"], "also_kinds": ["character", "place", "character"]}).json()
    assert e["also_kinds"] == ["character"]
    assert world.post(f"{W}/relationships", json={"type_id": leads["id"], "a_id": ash["id"], "b_id": guild["id"]}).status_code == 201
    assert "Ashgard Vale" in [x["name"] for x in world.get(f"{W}/entities", params={"kind": "character"}).json()]
    assert "Ashgard Vale" in [x["name"] for x in world.get(f"{W}/entities", params={"kind": "place"}).json()]
    # as a character it has a first name
    card = next(c for c in world.get(f"{W}/cards").json() if c["id"] == ash["id"])
    assert (card["first_name"], card["also_kinds"]) == ("Ashgard", ["character"])
    # Make main: the kinds swap places
    e = world.patch(f"{W}/entities/{ash['id']}", json={"base_version": e["version"], "kind": "character", "also_kinds": ["place"]}).json()
    assert (e["kind"], e["also_kinds"]) == ("character", ["place"])
    # export and restore keep both kinds in order, and the premise
    world.patch(W, json={"premise": "Lamps."})
    data = world.get(f"{W}/export").content
    r = world.post("/api/worlds/restore", files={"file": ("export.zip", data, "application/zip")})
    slug = r.json()["slug"]
    assert r.json()["premise"] == "Lamps."
    back = next(x for x in world.get(f"/api/worlds/{slug}/entities").json() if x["name"] == "Ashgard Vale")
    assert (back["kind"], back["also_kinds"]) == ("character", ["place"])
