"""Phase 12a, time and restructuring (SPEC §13.1, §13.6): chapters set in time with marks and outside time, happened
order (the clock), facts and relationships bounded by time, the Continuity checks on the clock and the age check;
experiments over a range of chapters (and ones that only add), the review before chapters are retired with Undo and
Reinstate, evidence in Salvage, the migration of existing experiments, and export/restore."""

from __future__ import annotations

import io
import uuid
import zipfile
from types import SimpleNamespace

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from quarry.clock import Clock, number_text, time_text

from .conftest import Client
from .test_bible_views import W, checks, entity, fact, relate, types, world  # noqa: F401

P = f"{W}/projects/ninefold"


def chapter(c: Client, title: str, body: str = "", project: str = "ninefold") -> dict:
    r = c.post(f"{W}/projects/{project}/chapters", json={"title": title, "body": body})
    assert r.status_code == 201, r.text
    return r.json()


def about(c: Client, ch: dict, **changes) -> dict:
    r = c.patch(f"{W}/chapters/{ch['id']}/about", json=changes)
    assert r.status_code == 200, r.text
    return r.json()


def rules(c: Client, rule: str) -> list[dict]:
    return [x for x in checks(c) if x["rule"] == rule]


def book(c: Client, n: int = 15, names: str = "Seyla swims.") -> list[dict]:
    """Chapters 1..n (index 0 unused), each naming Seyla."""
    return [{}] + [chapter(c, f"Chapter {i}", f"{names}\n") for i in range(1, n + 1)]


# the clock, as a unit ---------------------------------------------------------------------------------------------


def _chs(*specs):  # type: ignore[no-untyped-def]
    """Fake chapters in book order: (time_at, told_as, outside)."""
    out = []
    for i, (t, mark, outside) in enumerate(specs):
        c = SimpleNamespace(id=uuid.UUID(int=i + 1), title=f"C{i + 1}", time_at=t, time_end=None, time_label=None,
                            time_approx=False, outside_time=outside, told_as=mark)
        out.append((c, SimpleNamespace(id=uuid.UUID(int=99))))
    return out


def test_happened_order_and_carrying_on():
    # 1–3 in 312, a tale in −800, 5 unset (carries on from 3, not the tale), outside time, 7 unset (from 5's source)
    clock = Clock(_chs((312, None, False), (None, None, False), (312, None, False), (-800, "tale", False),
                       (None, None, False), (None, None, True), (None, None, False)))
    assert [x.title for x in clock.happened] == ["C4", "C1", "C2", "C3", "C5", "C7"]
    assert clock.by_id[uuid.UUID(int=5)].set_time == 312 and clock.by_id[uuid.UUID(int=6)].place is None
    # an unset chapter before the first one with a time shares its time
    clock = Clock(_chs((None, None, False), (300, None, False)))
    assert clock.by_id[uuid.UUID(int=1)].set_time == 300
    # a tale with no time is set before the story; no times at all is book order
    clock = Clock(_chs((None, None, False), (None, "flashback", False), (None, None, False)))
    assert [x.title for x in clock.happened] == ["C2", "C1", "C3"] and clock.by_id[uuid.UUID(int=2)].early
    # only tales have times: the others keep book order after them
    clock = Clock(_chs((None, None, False), (-50, "tale", False), (None, None, False)))
    assert [x.title for x in clock.happened] == ["C2", "C1", "C3"]


def test_spans_on_the_clock():
    clock = Clock(_chs((305, None, False), (312, None, False), (300, "flashback", False), (308, "flashback", False)))
    c = [uuid.UUID(int=i) for i in range(1, 5)]
    married = SimpleNamespace(from_chapter_id=c[0], until_chapter_id=c[1], from_time=None, until_time=None,
                              outside_time=False)
    # a flashback set before the wedding is outside the span though it comes later in the book; one in 308 is inside
    assert not clock.holds(married, c[2]) and clock.holds(married, c[3])
    born = SimpleNamespace(from_chapter_id=None, until_chapter_id=None, from_time=310.0, until_time=None,
                           outside_time=False)
    # a chapter set exactly at a time bound counts as inside
    assert clock.holds(born, c[1]) and not clock.holds(born, c[0])
    assert clock.backwards(SimpleNamespace(from_chapter_id=c[1], until_chapter_id=None, from_time=None,
                                           until_time=306.0))
    assert time_text("year", "years", -800.0, approx=True) == "about year −800"
    assert time_text("year", "years", 300.0, 302.0) == "years 300–302" and number_text(312.5) == "312.5"
    assert time_text("year", "years", 1.0, outside=True) == "outside time"


# 13.1 chapters in time --------------------------------------------------------------------------------------------


def test_chapter_time_and_mark_are_labels(world: Client):
    ch = chapter(world, "The Drowned Bell", "Seyla sang.")
    out = about(world, ch, time_at=-800, time_label="800 years before the Founding", told_as="tale")
    assert (out["time_at"], out["time_label"], out["told_as"], out["version"]) == (-800, "800 years before the Founding",
                                                                                   "tale", ch["version"])
    # outside time has no number; a span ends after it starts
    out = about(world, ch, outside_time=True)
    assert (out["outside_time"], out["time_at"], out["time_label"]) == (True, None, None)
    assert world.patch(f"{W}/chapters/{ch['id']}/about", json={"time_at": 5, "time_end": 2}).status_code == 422
    tl = world.get(f"{W}/timeline").json()
    assert (tl[0]["outside_time"], tl[0]["clock"], tl[0]["told_as"]) == (True, None, "tale")
    # the world names its unit
    w = world.patch(W, json={"time_unit": "day", "time_units": "days"}).json()
    assert (w["time_unit"], w["time_units"]) == ("day", "days")


def test_done_when_the_tale_and_the_dead(world: Client):
    """§13.1 done when: chapters 1–13 in year 312, Seyla dead from 9 and married to Varren from 3, chapter 14 a tale in
    year −800 that names her: no finding there; 15 carries on and names her after her death."""
    chs = book(world)
    for i in range(1, 14):
        about(world, chs[i], time_at=312)
    about(world, chs[14], time_at=-800, told_as="tale")
    seyla, varren = entity(world, "Seyla"), entity(world, "Varren")
    fact(world, seyla, "status", "dead", from_chapter_id=chs[9]["id"])
    relate(world, varren, "married to", seyla, from_chapter_id=chs[3]["id"])
    tl = world.get(f"{W}/timeline").json()
    assert [c["title"] for c in sorted(tl, key=lambda c: c["clock"])] == [
        "Chapter 14", *[f"Chapter {i}" for i in range(1, 14)], "Chapter 15"]
    assert tl[14]["set_time"] == 312 and tl[13]["set_time"] == -800
    dead = {x["chapter"]["title"] for x in rules(world, "dead_mentioned")}
    assert "Chapter 14" not in dead and {"Chapter 10", "Chapter 15"} <= dead
    # removing the tale's time but keeping the mark: still no finding there
    about(world, chs[14], time_at=None)
    assert "Chapter 14" not in {x["chapter"]["title"] for x in rules(world, "dead_mentioned")}
    assert world.get(f"{W}/timeline").json()[13]["early"]
    # born from year 278: a time bound, shown back as such
    born = fact(world, seyla, "born", "", from_time=278)
    assert (born["from_time"], born["from_chapter_id"]) == (278, None)


def test_a_bound_is_a_chapter_or_a_time(world: Client):
    one, two = chapter(world, "One"), chapter(world, "Two")
    about(world, one, time_at=100)
    about(world, two, time_at=200)
    seyla = entity(world, "Seyla")
    r = world.post(f"{W}/entities/{seyla['id']}/facts", json={"label": "title", "value": "x", "from_chapter_id": one["id"],
                                                              "from_time": 3})
    assert r.status_code == 422
    # from must come before until, on the clock, mixing a chapter and a time
    r = world.post(f"{W}/entities/{seyla['id']}/facts", json={"label": "title", "value": "x",
                                                              "from_chapter_id": two["id"], "until_time": 150})
    assert r.status_code == 422
    f = fact(world, seyla, "title", "Lady", from_chapter_id=one["id"], until_time=150, until_approx=True)
    assert (f["until_time"], f["until_approx"]) == (150, True)
    # a time sent replaces the chapter on that side; outside time clears every bound
    f = world.patch(f"{W}/facts/{f['id']}", json={"base_version": f["version"], "from_time": 90}).json()
    assert (f["from_time"], f["from_chapter_id"]) == (90, None)
    f = world.patch(f"{W}/facts/{f['id']}", json={"base_version": f["version"], "outside_time": True}).json()
    assert (f["outside_time"], f["from_time"], f["until_time"]) == (True, None, None)
    # setting a chapter's time can make a span run backwards: Checks lists it
    g = fact(world, seyla, "home", "Old Harbour", from_chapter_id=two["id"], until_time=250)
    about(world, two, time_at=300)
    assert [x["key"] for x in rules(world, "span_backwards")] == [g["id"]]


def test_done_when_outside_time(world: Client):
    """§13.1.8: a chapter outside time names the dead with no finding; an outside-time title doesn't clash with one in
    time; the chapter after it carries on from the last timed one before it."""
    chs = book(world, 22)
    for i in range(1, 21):
        about(world, chs[i], time_at=312)
    about(world, chs[20], time_at=320)
    about(world, chs[21], outside_time=True)
    seyla = entity(world, "Seyla")
    fact(world, seyla, "status", "dead", from_chapter_id=chs[9]["id"])
    fact(world, seyla, "title", "Lady of Old Harbour")
    fact(world, seyla, "title", "Queen of the Hollow Court", outside_time=True)
    assert "Chapter 21" not in {x["chapter"]["title"] for x in rules(world, "dead_mentioned")}
    assert rules(world, "fact_conflict") == []
    tl = {c["title"]: c for c in world.get(f"{W}/timeline").json()}
    assert tl["Chapter 21"]["clock"] is None and tl["Chapter 22"]["set_time"] == 320


def test_born_and_arrives_on_the_clock_introduced_in_book_order(world: Client):
    one, two, three = chapter(world, "One", "Tamsin."), chapter(world, "Two", "Tamsin."), chapter(world, "Three", "Tamsin.")
    about(world, one, time_at=10)
    about(world, two, time_at=-50, told_as="flashback")
    about(world, three, time_at=11)
    tamsin = entity(world, "Tamsin")
    fact(world, tamsin, "born", "", from_time=0)
    # the flashback in year −50 names her before her birth
    assert [x["chapter"]["title"] for x in rules(world, "before_start")] == ["Two"]
    # introduced is about the reader: book order
    hesper = entity(world, "Hesper")
    world.patch(f"{W}/chapters/{one['id']}", json={"base_version": one["version"], "body": "Tamsin. Hesper."})
    fact(world, hesper, "introduced", "", from_chapter_id=three["id"])
    assert {x["message"].split(" is")[0] for x in rules(world, "before_start")} == {"Tamsin", "Hesper"}


def test_age_disagreeing_with_a_birth_is_a_finding(world: Client):
    one, two = chapter(world, "The Crossing", "Tamsin rows."), chapter(world, "Later", "Tamsin rows.")
    about(world, one, time_at=412)
    about(world, two, time_at=413)
    tamsin = entity(world, "Tamsin", gender="female")
    fact(world, tamsin, "born", "", from_time=390)
    age = fact(world, tamsin, "age", "17", until_chapter_id=one["id"])
    [f] = rules(world, "age_conflict")
    assert f["message"] == "Tamsin is 17 in “The Crossing” by her age, but born in year 390 makes her 22."
    # within one unit is no clash; a value that isn't a number is never compared
    world.patch(f"{W}/facts/{age['id']}", json={"base_version": age["version"], "value": "21"})
    assert rules(world, "age_conflict") == []
    fact(world, tamsin, "age", "in her twenties", from_chapter_id=two["id"])
    assert rules(world, "age_conflict") == []
    # with "about", a tenth of the age more
    about_age = entity(world, "Bram")
    fact(world, about_age, "born", "", from_time=352)
    fact(world, about_age, "age", "about 55")
    world.patch(f"{W}/chapters/{one['id']}", json={"base_version": world.get(f"{W}/chapters/{one['id']}").json()["version"],
                                                    "body": "Tamsin rows. Bram waits."})
    assert rules(world, "age_conflict") == []


def test_roles_compare_on_the_clock_and_change_at_a_time(world: Client):
    one, two, three = chapter(world, "One"), chapter(world, "Two"), chapter(world, "Three")
    for ch, t in ((one, 10), (two, 20), (three, 30)):
        about(world, ch, time_at=t)
    guild, varren, isolde = entity(world, "The Lamp Guild", "faction"), entity(world, "Varren"), entity(world, "Isolde")
    world.put(f"{W}/labels/roles/Captain", json={"one_at_a_time": True})
    v = relate(world, varren, "member of", guild, role="Captain", until_time=20)
    relate(world, isolde, "member of", guild, role="Captain", from_time=20)
    # ending and starting at the same time is a handover
    assert rules(world, "role_clash") == []
    v = world.patch(f"{W}/relationships/{v['id']}", json={"base_version": v["version"], "until_time": 25}).json()
    [c] = rules(world, "role_clash")
    assert c["chapter"]["title"] == "Two" and "(from year 20)" in c["message"]
    out = world.post(f"{W}/relationships/{v['id']}/change-role",
                     json={"base_version": v["version"], "role": "Admiral", "from_time": 15}).json()
    assert (out["ended"]["until_time"], out["started"]["from_time"]) == (15, 15)


# 13.6.1 experiments across several chapters -----------------------------------------------------------------------


def test_done_when_a_new_beginning(world: Client):
    chs = [chapter(world, f"Chapter {i}", f"Text of chapter {i}.") for i in range(1, 8)]
    words = world.get(P + "/chapters").json()["words"]
    r = world.post(f"{P}/experiments", json={"title": "New beginning", "start": "copy",
                                              "range": [c["id"] for c in chs[:5]]})
    assert r.status_code == 201, r.text
    exp = r.json()
    assert [d["title"] for d in exp["drafts"]] == [f"Chapter {i}" for i in range(1, 6)]
    # a sixth draft, and a new order
    six = world.post(f"{W}/experiments/{exp['id']}/drafts", json={"title": "A new opening"}).json()
    ids = [six["id"], *[d["id"] for d in exp["drafts"]]]
    world.put(f"{W}/experiments/{exp['id']}/drafts", json={"ids": ids})
    m = world.get(P + "/chapters").json()
    assert [c["title"] for c in m["chapters"]] == [f"Chapter {i}" for i in range(1, 8)] and m["words"] == words
    [x] = m["experiments"]
    assert ([r["title"] for r in x["range"]], len(x["drafts"]), x["drafts"][0]["title"]) == (
        [f"Chapter {i}" for i in range(1, 6)], 6, "A new opening")
    z = zipfile.ZipFile(io.BytesIO(world.get(f"{W}/export").content))
    manuscript = z.read("lamp-coast/Projects/Ninefold/manuscript.md").decode()
    assert "A new opening" not in manuscript and "Chapter 5" in manuscript
    # the drafts are read where the range stands
    points = world.get(f"{W}/draft-clock").json()
    assert {p["id"] for p in points} == set(ids) and all(p["clock"] == -0.5 for p in points)
    # accepting: the six drafts at the start, the five old chapters in Salvage, with their notes
    done = world.post(f"{W}/experiments/{exp['id']}/close", json={
        "outcome": "accepted", "notes": {chs[0]["id"]: "the old first line"}}).json()
    assert done["first"] == six["id"]
    m = world.get(P + "/chapters").json()
    assert [c["title"] for c in m["chapters"]] == ["A new opening", *[f"Chapter {i}" for i in range(1, 8)]]
    assert [c["id"] for c in m["chapters"][1:6]] == [d["id"] for d in exp["drafts"]] and m["experiments"] == []
    salvage = world.get(P + "/salvage").json()
    assert {s["id"] for s in salvage} == {c["id"] for c in chs[:5]}
    assert next(s for s in salvage if s["id"] == chs[0]["id"])["harvest_notes"][0]["body"] == "the old first line"


def test_done_when_a_new_prologue_only_adds(world: Client):
    first = chapter(world, "Chapter 1", "one")
    chapter(world, "Chapter 2", "two")
    exp = world.post(f"{P}/experiments", json={"title": "New prologue",
                                               "insert": {"chapter_id": first["id"], "side": "before"}}).json()
    assert exp["insert"]["side"] == "before" and exp["range"] == [] and len(exp["drafts"]) == 1
    world.post(f"{W}/experiments/{exp['id']}/drafts", json={"title": "Prologue, part two"})
    # a draft can be copied in from any chapter, Salvage too
    assert world.get(f"{W}/chapters/ties?ids={first['id']}").json() == {"rows": []}
    world.post(f"{W}/experiments/{exp['id']}/close", json={"outcome": "accepted"})
    m = world.get(P + "/chapters").json()
    assert [c["title"] for c in m["chapters"]] == ["New prologue", "Prologue, part two", "Chapter 1", "Chapter 2"]
    assert world.get(P + "/salvage").json() == []


def test_another_experiment_on_lost_chapters_says_so(world: Client):
    a, b = chapter(world, "A", "a"), chapter(world, "B", "b")
    one = world.post(f"{P}/experiments", json={"title": "First try", "range": [a["id"], b["id"]]}).json()
    two = world.post(f"{P}/experiments", json={"title": "Second try", "start": "scratch", "range": [b["id"]]}).json()
    world.post(f"{W}/experiments/{one['id']}/close", json={"outcome": "accepted"})
    x = world.get(f"{W}/experiments/{two['id']}").json()
    assert (x["lost"], x["replaced_by"]) == (["B"], "First try")
    new = world.get(P + "/chapters").json()["chapters"][1]
    x = world.put(f"{W}/experiments/{two['id']}/range", json={"range": [new["id"]]}).json()
    assert (x["lost"], [r["title"] for r in x["range"]]) == ([], ["B"])
    # a range must be a run of chapters in the book
    c = chapter(world, "C", "c")
    assert world.put(f"{W}/experiments/{two['id']}/range", json={"range": [new["id"], c["id"]]}).status_code == 200
    first = world.get(P + "/chapters").json()["chapters"][0]
    assert world.put(f"{W}/experiments/{two['id']}/range", json={"range": [first["id"], c["id"]]}).status_code == 422


# 13.6.2 the review before retiring --------------------------------------------------------------------------------


def _ninth(world: Client, all_312: bool) -> tuple[list[dict], dict]:
    chs = book(world, 13, "Seyla and Varren.")
    if all_312:
        for i in range(1, 14):
            about(world, chs[i], time_at=312)
    else:
        about(world, chs[9], time_at=312)
        about(world, chs[8], time_at=311)
        about(world, chs[10], time_at=313)
    seyla, varren, harbour = entity(world, "Seyla"), entity(world, "Varren"), entity(world, "Old Harbour", "place")
    dead = fact(world, seyla, "status", "dead", from_chapter_id=chs[9]["id"])
    married = relate(world, varren, "married to", seyla, until_chapter_id=chs[9]["id"])
    for who in (seyla, varren):
        world.put(f"{W}/chapters/{chs[9]['id']}/presence/{who['id']}", json={"place_id": harbour["id"]})
    world.post(f"{W}/items", json={"kind": "spark", "body": "the storm scene", "chapter_id": chs[9]["id"]})
    return chs, {"dead": dead, "married": married, "seyla": seyla, "varren": varren}


def test_done_when_retiring_chapter_nine(world: Client):
    chs, x = _ninth(world, all_312=False)
    rows = world.get(f"{W}/chapters/ties?ids={chs[9]['id']}").json()["rows"]
    assert sorted(r["kind"] for r in rows) == ["fact", "link", "presence", "presence", "relationship"]
    dead = next(r for r in rows if r["kind"] == "fact")
    married = next(r for r in rows if r["kind"] == "relationship")
    assert (dead["keep_text"], dead["warn"], dead["default"]) == ("from year 312", None, "keep")
    # move on the second preselects chapter 8
    assert married["move_to"]["title"] == "Chapter 8" and dead["move_to"]["title"] == "Chapter 10"
    is_at = [r for r in rows if r["kind"] == "presence"]
    out = world.post(f"{W}/chapters/retire", json={"ids": [chs[9]["id"]], "review": [
        {"key": dead["key"], "action": "keep"}, {"key": married["key"], "action": "move"},
        {"key": is_at[0]["key"], "action": "drop"}]}).json()
    assert out["summary"] == {"keep": 3, "move": 1, "planned": 0, "drop": 1}
    f = world.get(f"{W}/entities/{x['seyla']['id']}").json()["facts"][0]
    assert (f["from_chapter_id"], f["from_time"]) == (None, 312)
    rel = next(r for r in world.get(f"{W}/relationships").json() if r["id"] == x["married"]["id"])
    assert rel["until_chapter_id"] == chs[8]["id"]
    assert len(world.get(f"{W}/chapters/{chs[9]['id']}/presence").json()) == 1
    # Salvage says what the review did
    s = next(s for s in world.get(P + "/salvage").json() if s["id"] == chs[9]["id"])
    assert (s["review"]["keep"], s["review"]["move"], s["review"]["drop"], s["still_tied"]) == (3, 1, 1, None)
    # Undo puts everything back with the chapter
    assert world.post(f"{W}/retire-reviews/{out['id']}/undo").json() == {"restored": 3, "skipped": 0}
    f = world.get(f"{W}/entities/{x['seyla']['id']}").json()["facts"][0]
    assert (f["from_chapter_id"], f["from_time"]) == (chs[9]["id"], None)
    rel = next(r for r in world.get(f"{W}/relationships").json() if r["id"] == x["married"]["id"])
    assert rel["until_chapter_id"] == chs[9]["id"]
    assert len(world.get(f"{W}/chapters/{chs[9]['id']}/presence").json()) == 2
    assert [c["id"] for c in world.get(P + "/chapters").json()["chapters"]][8] == chs[9]["id"]


def test_keep_warns_when_others_share_the_time(world: Client):
    chs, _ = _ninth(world, all_312=True)
    rows = world.get(f"{W}/chapters/ties?ids={chs[9]['id']}").json()["rows"]
    dead = next(r for r in rows if r["kind"] == "fact")
    assert (dead["warn"], dead["default"]) == ("chapters 1–13 are all set in year 312", "move")
    # a chapter with no time: keep holds throughout on that side
    plain = chapter(world, "Plain", "x", project="the-salt-road")
    f = fact(world, entity(world, "Isolde"), "home", "Old Harbour", from_chapter_id=plain["id"])
    assert world.get(f"{W}/timeline").json()[-1]["set_time"] == 312
    del f


def test_retiring_three_at_once_is_one_review(world: Client):
    chs = book(world, 5, "Isolde.")
    isolde = entity(world, "Isolde")
    for i in (2, 3, 4):
        fact(world, isolde, f"mood {i}", "x", from_chapter_id=chs[i]["id"])
    rows = world.get(f"{W}/chapters/ties?ids={chs[2]['id']},{chs[3]['id']},{chs[4]['id']}").json()["rows"]
    assert len(rows) == 3 and {r["move_to"]["title"] for r in rows} == {"Chapter 5"}
    out = world.post(f"{W}/chapters/retire", json={"ids": [chs[i]["id"] for i in (2, 3, 4)]}).json()
    assert len(out["chapters"]) == 3 and out["summary"]["keep"] == 3
    assert [c["title"] for c in world.get(P + "/chapters").json()["chapters"]] == ["Chapter 1", "Chapter 5"]
    world.post(f"{W}/retire-reviews/{out['id']}/undo")
    assert len(world.get(P + "/chapters").json()["chapters"]) == 5


def test_marked_planned_and_reinstate(world: Client):
    chs = book(world, 3, "Isolde.")
    isolde = entity(world, "Isolde")
    f = fact(world, isolde, "mood", "grim", from_chapter_id=chs[2]["id"], evidence="Isolde.",
             established_in_chapter_id=chs[2]["id"])
    rows = world.get(f"{W}/chapters/ties?ids={chs[2]['id']}").json()["rows"]
    assert {r["field"] for r in rows} == {"from", "established"}
    world.post(f"{W}/chapters/retire", json={"ids": [chs[2]["id"]], "review": [
        {"key": r["key"], "action": "planned" if r["field"] == "from" else "keep"} for r in rows]})
    got = world.get(f"{W}/entities/{isolde['id']}").json()["facts"][0]
    assert got["standing"] == "planned" and got["from_chapter_id"] is None
    # Reinstate puts the rows back as they were
    assert world.post(f"{W}/chapters/{chs[2]['id']}/reinstate-review").json()["restored"] == 1
    got = world.get(f"{W}/entities/{isolde['id']}").json()["facts"][0]
    assert (got["standing"], got["from_chapter_id"]) == ("canon", chs[2]["id"])
    del f


def test_a_chapter_retired_before_reviews_is_still_tied(world: Client):
    chs = book(world, 2, "Isolde.")
    isolde = entity(world, "Isolde")
    fact(world, isolde, "mood", "x", from_chapter_id=chs[2]["id"])
    from quarry.db import session_factory
    from quarry.models import Chapter

    # retired the old way (as before phase 12): no review
    with session_factory()() as db:
        c = db.get(Chapter, uuid.UUID(chs[2]["id"]))
        c.state = "retired"
        db.commit()
    s = world.get(P + "/salvage").json()[0]
    assert s["still_tied"] == {"facts": 1, "relationships": 0, "is_at": 0, "items": 0, "notes": 0}
    world.post(f"{W}/chapters/{chs[2]['id']}/review", json={"review": []})
    s = world.get(P + "/salvage").json()[0]
    assert s["still_tied"] is None and s["review"]["keep"] == 1


# 13.6.3 evidence in Salvage --------------------------------------------------------------------------------------


def test_done_when_evidence_in_a_retired_chapter(world: Client):
    old = chapter(world, "The Storm", "The river kept him.")
    chapter(world, "Two", "x")
    oskar = entity(world, "Oskar")
    f = fact(world, oskar, "status", "dead", evidence="The river kept him.", established_in_chapter_id=old["id"])
    exp = world.post(f"{P}/experiments", json={"title": "Storm, again", "range": [old["id"]]}).json()
    world.post(f"{W}/chapters/retire", json={"ids": [old["id"]]})
    [x] = world.get(f"{W}/evidence-retired").json()
    assert x["message"] == "Oskar: “status: dead” rests on a passage in a retired chapter, “The Storm”."
    # Re-anchor offers the draft where the passage is now
    assert [c["id"] for c in x["found"]] == [exp["drafts"][0]["id"]]
    world.post(f"{W}/evidence/re-anchor", json={"kind": "fact", "id": f["id"], "chapter_id": x["found"][0]["id"]})
    assert world.get(f"{W}/evidence-retired").json() == []
    # Dismiss keeps one out for good
    g = fact(world, oskar, "age", "50", evidence="The river kept him.", established_in_chapter_id=old["id"])
    world.put(f"{W}/resolutions", json={"rule": "evidence_retired", "key": f"fact:{g['id']}", "outcome": "intentional"})
    assert world.get(f"{W}/evidence-retired").json() == []


# export, restore, the migration -----------------------------------------------------------------------------------


def test_export_and_restore_keep_times_marks_and_experiments(world: Client):
    one, two = chapter(world, "One", "a"), chapter(world, "Two", "b")
    about(world, one, time_at=312, time_end=313, time_label="the long ice", time_approx=True)
    about(world, two, outside_time=True, told_as="tale")
    world.patch(W, json={"time_unit": "reign", "time_units": "reigns"})
    seyla = entity(world, "Seyla")
    fact(world, seyla, "born", "", from_time=-1000, from_approx=True)
    fact(world, seyla, "title", "Queen", outside_time=True)
    relate(world, entity(world, "Varren"), "married to", seyla, from_chapter_id=one["id"], until_time=320)
    world.post(f"{P}/experiments", json={"title": "New beginning", "range": [one["id"], two["id"]]})
    world.post(f"{P}/experiments", json={"title": "New prologue", "insert": {"chapter_id": one["id"], "side": "before"}})
    data = world.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    meta = yaml.safe_load(z.read("lamp-coast/Projects/Ninefold/Manuscript/02 Two.md").decode().split("---\n")[1])
    assert (meta["time"], meta["told_as"]) == ("outside", "tale")
    r = world.post("/api/worlds/restore", files={"file": ("w.zip", data, "application/zip")})
    assert r.status_code == 201, r.text
    assert (r.json()["time_unit"], r.json()["time_units"]) == ("reign", "reigns")
    R = f"/api/worlds/{r.json()['slug']}"
    tl = world.get(f"{R}/timeline").json()
    assert [(c["time_at"], c["time_end"], c["time_label"], c["time_approx"], c["outside_time"], c["told_as"]) for c in tl] \
        == [(312, 313, "the long ice", True, False, None), (None, None, None, False, True, "tale")]
    e = next(x for x in world.get(f"{R}/entities").json() if x["name"] == "Seyla")
    facts = {f["label"]: f for f in world.get(f"{R}/entities/{e['id']}").json()["facts"]}
    assert (facts["born"]["from_time"], facts["born"]["from_approx"], facts["title"]["outside_time"]) == (-1000, True, True)
    rel = world.get(f"{R}/relationships").json()[0]
    assert (rel["from_chapter_id"], rel["until_time"]) == (tl[0]["id"], 320)
    exps = world.get(f"{R}/projects/ninefold/chapters").json()["experiments"]
    assert {x["title"]: ([c["title"] for c in x["range"]], x["insert"] and x["insert"]["side"]) for x in exps} == {
        "New beginning": (["One", "Two"], None), "New prologue": ([], "before")}


def test_existing_experiments_get_a_range_from_the_migration(db_url: str):
    from alembic import command
    from alembic.config import Config

    from quarry.app import PKG

    base = make_url(db_url)
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    name = "quarry_test_upgrade12a"
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    cfg = Config()
    cfg.set_main_option("script_location", str(PKG / "migrations"))
    cfg.attributes["connection_url"] = url
    command.upgrade(cfg, "0010")
    e = create_engine(url)
    user, wid, pid, item, old, draft = (uuid.uuid4() for _ in range(6))
    with e.begin() as c:
        c.execute(text("INSERT INTO users (id, display_name) VALUES (:u, 'W')"), {"u": user})
        c.execute(text("INSERT INTO worlds (id, name, slug, created_by, updated_by) VALUES (:w, 'Old', 'old', :u, :u)"),
                  {"w": wid, "u": user})
        c.execute(text("INSERT INTO projects (id, world_id, name, slug, kind, position, created_by, updated_by) "
                       "VALUES (:p, :w, 'Book', 'book', 'novel', 0, :u, :u)"), {"p": pid, "w": wid, "u": user})
        c.execute(text("INSERT INTO items (id, world_id, project_id, kind, body, status, version, created_by, updated_by)"
                       " VALUES (:i, :w, :p, 'experiment', 'x', 'open', 1, :u, :u)"),
                  {"i": item, "w": wid, "p": pid, "u": user})
        for cid, state, rep in ((old, "current", None), (draft, "experiment", old)):
            c.execute(text("INSERT INTO chapters (id, project_id, title, body, state, position, version, created_by, "
                           "updated_by, experiment_item_id, replaces_id) VALUES (:c, :p, 'T', '', :s, 0, 1, :u, :u, "
                           ":i, :r)"), {"c": cid, "p": pid, "s": state, "u": user,
                                        "i": item if state == "experiment" else None, "r": rep})
    command.upgrade(cfg, "head")
    with e.connect() as c:
        assert [tuple(r) for r in c.execute(text("SELECT item_id, chapter_id, position FROM experiment_ranges"))] == [
            (item, old, 0)]
        assert c.execute(text("SELECT count(*) FROM chapters WHERE time_at IS NOT NULL OR told_as IS NOT NULL")).scalar() == 0
    e.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def test_demo_world_shows_time_and_restructuring(signed_in: Client):
    world = signed_in.post("/api/worlds/demo").json()
    D = f"/api/worlds/{world['slug']}"
    tl = {c["title"]: c for c in signed_in.get(f"{D}/timeline").json()}
    assert (tl["The Crossing"]["set_time"], tl["Ash Season"]["set_time"]) == (412, 413)
    tale = tl["The Ferryman's Tale"]
    assert (tale["told_as"], tale["set_time"], tale["clock"]) == ("tale", 372, 0)
    found = signed_in.get(f"{D}/checks").json()
    # Oskar is named in the tale, set before his death: no finding there; Pell's age disagrees with his birth
    assert not any(c["rule"] == "dead_mentioned" and c["chapter"]["title"] == "The Ferryman's Tale" for c in found)
    assert any(c["rule"] == "age_conflict" and "Pell" in c["message"] for c in found)
    ash = signed_in.get(f"{D}/projects/ash-season/chapters").json()
    [x] = ash["experiments"]
    assert ([r["title"] for r in x["range"]], len(x["drafts"])) == (["Ash Season", "The Cartographer"], 2)
    [prologue] = signed_in.get(f"{D}/projects/the-ferrymans-daughter/salvage").json()
    assert prologue["still_tied"]["facts"] == 1
    [evidence] = signed_in.get(f"{D}/evidence-retired").json()
    assert evidence["chapter"]["title"] == "Prologue: The Delta Remembers"
