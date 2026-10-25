"""Phase 12b, history and the Timeline (SPEC §13.2): an event's when (a chapter, a time, outside time), eras and their
colours, Record as event with its telling and Undo, tellings that don't count as appearing, ages from birth events,
events and tellings in the review before retiring and in Salvage, the chronology, and export/restore."""

from __future__ import annotations

import io
import zipfile

import yaml

from .conftest import Client
from .test_bible_views import W, checks, entity, fact, relate, world  # noqa: F401
from .test_time import about, chapter, rules

E = f"{W}/entities"


def when(c: Client, e: dict, **changes) -> dict:
    current = c.get(f"{E}/{e['id']}").json()["entity"]
    r = c.patch(f"{E}/{e['id']}", json={"base_version": current["version"], **changes})
    assert r.status_code == 200, r.text
    return r.json()


def test_an_event_happens_in_a_chapter_at_a_time_or_outside_time(world: Client):
    two = chapter(world, "Two")
    founding = entity(world, "The Founding", "event")
    assert founding["when"] is None
    out = when(world, founding, time_at=0, time_label="the Founding", time_approx=True)
    assert out["when"] == {"chapter": None, "at": 0, "end": None, "label": "the Founding", "approx": True,
                           "outside": False}
    # one of them: a chapter clears the time, outside time clears both
    out = when(world, founding, time_chapter_id=two["id"])
    assert (out["when"]["chapter"], out["when"]["at"], out["when"]["label"]) == (two["id"], None, None)
    out = when(world, founding, outside_time=True)
    assert (out["when"]["outside"], out["when"]["chapter"]) == (True, None)
    out = when(world, founding, outside_time=False, time_chapter_id=None, time_at=None)
    assert out["when"] is None
    current = world.get(f"{E}/{founding['id']}").json()["entity"]
    assert world.patch(f"{E}/{founding['id']}", json={"base_version": current["version"], "time_at": 5,
                                                       "time_end": 1}).status_code == 422
    # the cards carry it
    when(world, founding, time_at=-800)
    card = next(c for c in world.get(f"{W}/cards").json() if c["name"] == "The Founding")
    assert card["when"]["at"] == -800
    # "when" is a field now, not a suggested fact
    assert "when" not in world.get(f"{W}/fact-suggestions").json()["event"]["labels"]


def test_eras_take_the_next_colour(world: Client):
    one, two, three = entity(world, "The Lamp Years", "event"), entity(world, "The Long Ebb", "event"), entity(
        world, "The Burning", "event")
    fact(world, one, "type", "Era")
    fact(world, two, "type", "era")
    fact(world, three, "type", "battle")
    cards = {c["name"]: c for c in world.get(f"{W}/cards").json()}
    assert (cards["The Lamp Years"]["era_colour"], cards["The Long Ebb"]["era_colour"]) == ("amber", "moss")
    assert "era_colour" not in cards["The Burning"]
    # a colour can be picked, and the next era takes the next one not used
    when(world, one, era_colour="teal")
    four = entity(world, "The Quiet", "event")
    fact(world, four, "type", "era")
    assert next(c for c in world.get(f"{W}/cards").json() if c["name"] == "The Quiet")["era_colour"] == "amber"


def test_done_when_record_as_event(world: Client):
    """§13.2 done when: the passage in chapter 2 where Varren tells how the Lamp Guild was founded, recorded as The
    Founding in year 0 with its participants and the passage under Told in."""
    one = chapter(world, "One", "Seyla.")
    passage = "Varren told how the Lamp Guild was founded, with Seyla and Isolde at Old Harbour."
    two = chapter(world, "Two", f"Rain.\n{passage}\nMore rain.")
    guild, seyla, isolde = entity(world, "The Lamp Guild", "faction"), entity(world, "Seyla"), entity(world, "Isolde")
    harbour = entity(world, "Old Harbour", "place")
    r = world.post(f"{W}/events/record", json={
        "name": "The Founding", "chapter_id": two["id"], "passage": passage,
        "taking": [{"entity_id": guild["id"]}, {"entity_id": seyla["id"]}, {"entity_id": isolde["id"]},
                   {"entity_id": harbour["id"], "role": "place"}],
        "when": {"time_at": 0}})
    assert r.status_code == 201, r.text
    done = r.json()
    assert done["created"] and len(done["relationships"]) == 4
    ev = world.get(f"{E}/{done['event']['id']}").json()
    assert ev["entity"]["when"]["at"] == 0
    assert {(x["reads"], x["other"]["name"]) for x in ev["relationships"]} == {
        ("involved", "The Lamp Guild"), ("involved", "Seyla"), ("involved", "Isolde"), ("happened at", "Old Harbour")}
    assert all(x["established_in_chapter_id"] == two["id"] and x["evidence"] == passage for x in ev["relationships"])
    [told] = ev["tellings"]
    assert (told["passage"], told["chapter"]["title"], told["changed"]) == (passage, "Two", False)
    # recording again on the existing event: the telling is added, a participant once, a different time kept
    again = world.post(f"{W}/events/record", json={
        "event_id": done["event"]["id"], "chapter_id": one["id"], "passage": "Seyla.",
        "taking": [{"entity_id": seyla["id"]}], "when": {"time_at": 5}}).json()
    assert (again["created"], again["relationships"], again["time_differs"], again["when"]["at"]) == (False, [], True, 0)
    assert len(world.get(f"{E}/{done['event']['id']}").json()["tellings"]) == 2
    # Undo removes what that save added
    world.post(f"{W}/events/record/undo", json=again)
    assert len(world.get(f"{E}/{done['event']['id']}").json()["tellings"]) == 1
    world.post(f"{W}/events/record/undo", json=done)
    assert world.get(f"{E}/{done['event']['id']}").status_code == 404
    assert world.get(f"{W}/relationships").json() == []


def test_record_as_event_uses_linked_to_without_the_types(world: Client):
    one = chapter(world, "One", "Seyla wept.")
    seyla = entity(world, "Seyla")
    types = {t["label"]: t for t in world.get(f"{W}/relation-types").json()}
    for label in ("involved", "happened at"):
        world.delete(f"{W}/relation-types/{types[label]['id']}")
    done = world.post(f"{W}/events/record", json={"name": "The Weeping", "chapter_id": one["id"],
                                                  "passage": "Seyla wept.", "taking": [{"entity_id": seyla["id"]}]}).json()
    rel = world.get(f"{W}/relationships").json()[0]
    assert (rel["label"], done["when"]) == ("linked to", None)


def test_telling_is_not_appearing(world: Client):
    chs = [chapter(world, f"C{i}", "Seyla swam.") for i in range(1, 4)]
    seyla = entity(world, "Seyla")
    fact(world, seyla, "status", "dead", from_chapter_id=chs[0]["id"])
    passage = "Long ago Seyla sang to the drowned."
    three = chs[2]
    world.patch(f"{W}/chapters/{three['id']}", json={"base_version": three["version"], "body": f"{passage}\n"})
    assert "C3" in {x["chapter"]["title"] for x in rules(world, "dead_mentioned")}
    world.post(f"{W}/events/record", json={"name": "The Singing", "chapter_id": three["id"], "passage": passage,
                                           "taking": [{"entity_id": seyla["id"]}]})
    assert "C3" not in {x["chapter"]["title"] for x in rules(world, "dead_mentioned")}
    # the passage edited so it can't be found: the names count again, and the telling says the passage changed
    cur = world.get(f"{W}/chapters/{three['id']}").json()
    world.patch(f"{W}/chapters/{three['id']}", json={"base_version": cur["version"], "body": "Seyla sang, long ago.\n"})
    assert "C3" in {x["chapter"]["title"] for x in rules(world, "dead_mentioned")}
    ev = next(e for e in world.get(f"{W}/entities").json() if e["name"] == "The Singing")
    assert world.get(f"{E}/{ev['id']}").json()["tellings"][0]["changed"] is True


def test_a_birth_event_gives_an_age(world: Client):
    one = chapter(world, "The Crossing", "Tamsin rows.")
    about(world, one, time_at=412)
    tamsin = entity(world, "Tamsin", gender="female")
    birth = entity(world, "Tamsin's birth", "event")
    fact(world, birth, "type", "birth")
    when(world, birth, time_at=390)
    relate(world, birth, "involved", tamsin)
    fact(world, tamsin, "age", "17")
    [f] = rules(world, "age_conflict")
    assert "born in year 390 makes her 22" in f["message"]


def test_events_and_tellings_in_the_review(world: Client):
    one, two, three = chapter(world, "One", "a"), chapter(world, "Two", "Seyla wept."), chapter(world, "Three", "c")
    about(world, two, time_at=312)
    storm = entity(world, "The Storm", "event")
    when(world, storm, time_chapter_id=two["id"])
    seyla = entity(world, "Seyla")
    world.post(f"{W}/events/record", json={"name": "The Weeping", "chapter_id": two["id"], "passage": "Seyla wept.",
                                           "taking": [{"entity_id": seyla["id"]}]})
    rows = world.get(f"{W}/chapters/ties?ids={two['id']}").json()["rows"]
    ev = next(r for r in rows if r["kind"] == "event")
    told = next(r for r in rows if r["kind"] == "telling")
    assert (ev["keep_text"], told["evidence"]) == ("will be set in year 312", "Seyla wept.")
    out = world.post(f"{W}/chapters/retire", json={"ids": [two["id"]], "review": [
        {"key": ev["key"], "action": "keep"}, {"key": told["key"], "action": "drop"}]}).json()
    assert world.get(f"{E}/{storm['id']}").json()["entity"]["when"]["at"] == 312
    weeping = next(e for e in world.get(f"{W}/entities").json() if e["name"] == "The Weeping")
    assert world.get(f"{E}/{weeping['id']}").json()["tellings"] == []
    world.post(f"{W}/retire-reviews/{out['id']}/undo")
    assert world.get(f"{E}/{storm['id']}").json()["entity"]["when"]["chapter"] == two["id"]
    assert len(world.get(f"{E}/{weeping['id']}").json()["tellings"]) == 1
    # a telling kept in a retired chapter is the Archivist's
    world.post(f"{W}/chapters/retire", json={"ids": [two["id"]]})
    found = [x for x in world.get(f"{W}/evidence-retired").json() if x["kind"] == "telling"]
    assert [x["message"] for x in found] == ["The telling of The Weeping is a passage in a retired chapter, “Two”."]
    world.post(f"{W}/evidence/re-anchor", json={"kind": "telling", "id": found[0]["id"], "chapter_id": three["id"]})
    assert [x for x in world.get(f"{W}/evidence-retired").json() if x["kind"] == "telling"] == []
    del one


def test_chronology_and_export_restore(world: Client):
    one = chapter(world, "One", "Seyla wept at the Quay.")
    seyla, quay = entity(world, "Seyla"), entity(world, "The Quay", "place")
    world.put(f"{W}/chapters/{one['id']}/presence/{seyla['id']}", json={"place_id": quay["id"]})
    done = world.post(f"{W}/events/record", json={"name": "The Weeping", "chapter_id": one["id"],
                                                  "passage": "Seyla wept", "taking": [{"entity_id": seyla["id"]}]}).json()
    era = entity(world, "The Lamp Years", "event")
    fact(world, era, "type", "era")
    when(world, era, time_at=0, time_end=400)
    prophecy = entity(world, "The Second Lamp", "event")
    when(world, prophecy, outside_time=True)
    storm = entity(world, "The Storm", "event")
    when(world, storm, time_chapter_id=one["id"])
    chron = world.get(f"{W}/chronology").json()
    assert [p["place_id"] for p in chron["presence"]] == [quay["id"]]
    assert [(t["event_id"], t["passage"]) for t in chron["tellings"]] == [(done["event"]["id"], "Seyla wept")]
    data = world.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    meta = yaml.safe_load(z.read("lamp-coast/Bible/Events/The Lamp Years.md").decode().split("---\n")[1])
    assert (meta["when"], meta["colour"]) == ({"at": 0, "end": 400, "label": None, "approx": False}, "amber")
    r = world.post("/api/worlds/restore", files={"file": ("w.zip", data, "application/zip")})
    R = f"/api/worlds/{r.json()['slug']}"
    ents = {e["name"]: e for e in world.get(f"{R}/entities").json()}
    assert ents["The Lamp Years"]["when"]["end"] == 400 and ents["The Lamp Years"]["era_colour"] == "amber"
    assert ents["The Second Lamp"]["when"]["outside"] is True
    ch = world.get(f"{R}/timeline").json()[0]
    assert ents["The Storm"]["when"]["chapter"] == ch["id"]
    told = world.get(f"{R}/entities/{ents['The Weeping']['id']}").json()["tellings"]
    assert [(t["passage"], t["chapter"]["id"]) for t in told] == [("Seyla wept", ch["id"])]


def test_demo_world_shows_history(signed_in: Client):
    world = signed_in.post("/api/worlds/demo").json()
    D = f"/api/worlds/{world['slug']}"
    cards = {c["name"]: c for c in signed_in.get(f"{D}/cards").json()}
    eras = [c for c in cards.values() if c.get("era_colour")]
    assert {c["name"] for c in eras} == {"The Lock Years", "The Ash Summers", "The Open Water", "The Lock Works"}
    # a long era with one nested at its end, and five events close together before the raising of the locks
    assert (cards["The Open Water"]["when"]["at"], cards["The Open Water"]["when"]["end"]) == (320, 379)
    assert (cards["The Lock Works"]["when"]["at"], cards["The Lock Works"]["when"]["end"]) == (376, 379)
    cluster = sorted(n for n, c in cards.items() if c["kind"] == "event" and (c.get("when") or {}).get("at") in (378, 379))
    assert cluster == ["The Drowning of the Lock Diggers", "The Ferrymen's Petition",
                       "The Night the Lower Gates Were Shut Against the Spring Tide", "The Survey of the Nine Channels",
                       "The Toll-House Riots"]
    assert cards["The Opening of the Hand"]["when"]["outside"] is True
    assert cards["The Flood of Lanterns"]["when"]["chapter"]
    raising = signed_in.get(f"{D}/entities/{cards['The Raising of the Locks']['id']}").json()
    assert raising["tellings"][0]["chapter"]["title"] == "What the River Kept"
    assert not raising["tellings"][0]["changed"]
