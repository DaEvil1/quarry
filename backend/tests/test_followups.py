"""Phase 14, decisions with follow-ups (docs/SPEC.md §16): planned facts and relationships and tasks that carry a
decision out, made from it or attached; its state worked out from them; the gap a written chapter shows; the filter and
the front page; and export and Restore keeping all of it."""

from __future__ import annotations

import io
import zipfile

import pytest

from .conftest import Client

W = "/api/worlds/delta"
DEATH = "Varren dies at the end of chapter 9"


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Delta"})
    signed_in.post(f"{W}/projects", json={"name": "The Salt Road"})
    return signed_in


def add(c: Client, name: str, kind: str = "character") -> dict:
    r = c.post(f"{W}/entities", json={"name": name, "kind": kind})
    assert r.status_code == 201, r.text
    return r.json()


def chapters(c: Client, n: int = 10, project: str = "the-salt-road", text: dict[int, str] | None = None) -> list[dict]:
    """Chapters 1..n; the ninth is The Drowned Bell. Only those in `text` (by number) have prose."""
    out = []
    for i in range(1, n + 1):
        title = "The Drowned Bell" if i == 9 else f"Part {i}"
        r = c.post(f"{W}/projects/{project}/chapters", json={"title": title, "body": (text or {}).get(i, "")})
        assert r.status_code == 201, r.text
        out.append(r.json())
    return out


def write(c: Client, ch: dict, body: str) -> dict:
    now = c.get(f"{W}/chapters/{ch['id']}").json()
    r = c.patch(f"{W}/chapters/{ch['id']}", json={"base_version": now["version"], "body": body})
    assert r.status_code == 200, r.text
    return r.json()


def decide(c: Client, text: str = DEATH, entities: list[dict] | None = None, project: str | None = "the-salt-road",
           day: str = "2026-10-12") -> dict:
    r = c.post(f"{W}/decisions", json={"text": text, "decided_on": day, "project": project,
                                        "entities": [e["id"] for e in entities or []]})
    assert r.status_code == 201, r.text
    return r.json()


def follow(c: Client, d: dict, **body) -> dict:
    r = c.post(f"{W}/decisions/{d['id']}/followups", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def counts(c: Client, d: dict) -> dict | None:
    return c.get(f"{W}/decisions/{d['id']}").json()["followups"]


def listing(c: Client, d: dict) -> list[dict]:
    return c.get(f"{W}/decisions/{d['id']}/followups").json()


def planned_death(c: Client, d: dict, varren: dict, ch9: dict) -> dict:
    return follow(c, d, fact={"entity_id": varren["id"], "label": "status", "value": "dead", "standing": "planned",
                              "from_chapter_id": ch9["id"]})


def types(c: Client) -> dict[str, dict]:
    return {t["label"]: t for t in c.get(f"{W}/relation-types").json()}


# the chapters a decision names (§16.1) --------------------------------------------------------------------------


def test_a_decision_offers_the_chapters_it_names(world: Client):
    chapters(world)
    d = decide(world)
    named = world.get(f"{W}/decisions/{d['id']}/chapters").json()
    assert [x["label"] for x in named] == ["chapter 9, The Drowned Bell"]
    for text in ("Chapter Nine is where Varren dies", "In ch. 9 he dies", "ch 9", "Varren dies in the drowned bell"):
        x = decide(world, text)
        assert [c["n"] for c in world.get(f"{W}/decisions/{x['id']}/chapters").json()] == [9], text
    # in the order they appear, at most three; a short one-word title is never matched
    x = decide(world, "chapter 2, then chapter 4, chapter 1 and chapter 3")
    assert [c["n"] for c in world.get(f"{W}/decisions/{x['id']}/chapters").json()] == [2, 4, 1]
    assert world.get(f"{W}/decisions/{decide(world, 'chapter 11 is long')['id']}/chapters").json() == []


def test_a_decision_with_no_project_offers_a_chapter_per_project(world: Client):
    chapters(world)
    world.post(f"{W}/projects", json={"name": "Ash Road"})
    chapters(world, 9, "ash-road")
    world.post(f"{W}/projects", json={"name": "Short"})
    chapters(world, 3, "short")
    d = decide(world, project=None)
    named = world.get(f"{W}/decisions/{d['id']}/chapters").json()
    assert [(x["project"], x["n"]) for x in named] == [("the-salt-road", 9), ("ash-road", 9)]
    assert named[0]["label"] == "chapter 9, The Drowned Bell (The Salt Road)"


# follow-ups (§16.1) ---------------------------------------------------------------------------------------------


def test_a_planned_fact_follows_the_decision(world: Client):
    chs = chapters(world)
    varren, isolde = add(world, "Varren"), add(world, "Isolde")
    d = decide(world, entities=[varren, isolde])
    assert d["followups"] is None  # settled: no pill
    out = planned_death(world, d, varren, chs[8])
    assert out["made"]["table"] == "fact"
    assert out["followup"]["state"] == "todo"
    assert out["followup"]["text"] == "Varren · status: dead · from chapter 9, The Drowned Bell"
    assert out["counts"] == {"todo": 1, "done": 0, "dropped": 0}
    page = world.get(f"{W}/entities/{varren['id']}").json()
    fact = next(f for f in page["facts"] if f["label"] == "status")
    assert fact["standing"] == "planned"
    assert fact["follows"] == [{"id": d["id"], "decided_on": "2026-10-12", "text": DEATH,
                                "followup_id": out["followup"]["id"]}]
    # the pill everywhere a decision's line is
    assert world.get(f"{W}/decisions").json()[0]["followups"] == {"todo": 1, "done": 0, "dropped": 0}
    assert page["decisions"][0]["followups"]["todo"] == 1
    plan = world.get(f"{W}/planning", params={"entity": varren["id"]}).json()
    assert plan["decisions"][0]["followups"]["todo"] == 1
    assert world.get(f"{W}/front").json()["decisions"][0]["followups"]["todo"] == 1
    # one row follows a decision once
    r = world.post(f"{W}/decisions/{d['id']}/followups", json={"attach": {"table": "fact", "id": fact["id"]}})
    assert r.status_code == 409


def test_a_task_lists_in_the_chapter_it_is_ticked_for(world: Client):
    chs = chapters(world)
    varren, isolde = add(world, "Varren"), add(world, "Isolde")
    d = decide(world, entities=[varren, isolde])
    out = follow(world, d, item={"body": "Plant the bell's crack in chapter 4", "entities": [varren["id"], isolde["id"]],
                                 "chapters": []})
    item = world.get(f"{W}/items/{out['made']['id']}").json()
    assert item["kind"] == "task" and item["project"] == "the-salt-road"
    assert sorted(e["name"] for e in item["entities"]) == ["Isolde", "Varren"]
    assert item["follows"][0]["text"] == DEATH
    assert world.get(f"{W}/chapters/{chs[8]['id']}/items").json() == []
    # once chapter 9 is ticked, the task is in its Loose ends
    out = follow(world, d, item={"body": "Ring the bell", "entities": [], "chapters": [chs[8]["id"]]})
    assert [i["body"] for i in world.get(f"{W}/chapters/{chs[8]['id']}/items").json()] == ["Ring the bell"]
    r = world.post(f"{W}/decisions/{d['id']}/followups", json={"item": {"body": "  "}})
    assert r.status_code == 422


def test_attach_offers_planned_rows_and_open_tasks(world: Client):
    chapters(world, 2)
    varren, isolde, bell = add(world, "Varren"), add(world, "Isolde"), add(world, "the Bell", "object")
    d = decide(world, entities=[isolde])
    knows = types(world)["knows about"]
    planned = world.post(f"{W}/relationships", json={"type_id": knows["id"], "a_id": isolde["id"], "b_id": varren["id"],
                                                     "standing": "planned"}).json()
    canon = world.post(f"{W}/relationships", json={"type_id": knows["id"], "a_id": varren["id"], "b_id": bell["id"]}).json()
    world.post(f"{W}/entities/{bell['id']}/facts", json={"label": "cracked", "standing": "planned"})
    task = world.post(f"{W}/items", json={"body": "Check the tides", "kind": "task"}).json()
    closed = world.post(f"{W}/items", json={"body": "Done already", "kind": "task"}).json()
    world.post(f"{W}/items/{closed['id']}/close", json={"status": "accepted"})
    offered = world.get(f"{W}/followup-candidates", params={"decision": d["id"]}).json()
    # planned rows on the decision's tagged entries first, then the rest, then open tasks; no canon, no closed
    assert [x["text"] for x in offered] == ["Isolde knows about Varren · planned", "the Bell · cracked · planned",
                                            "Check the tides · task"]
    out = follow(world, d, attach={"table": "relationship", "id": planned["id"]})
    assert out["made"] is None and out["followup"]["state"] == "todo"
    assert out["followup"]["text"] == "Isolde knows about Varren"
    assert world.get(f"{W}/followup-candidates", params={"decision": d["id"]}).json()[0]["table"] == "fact"
    r = world.post(f"{W}/decisions/{d['id']}/followups", json={"attach": {"table": "relationship", "id": canon["id"]}})
    assert r.status_code == 422
    follow(world, d, attach={"table": "item", "id": task["id"]})
    assert counts(world, d) == {"todo": 2, "done": 0, "dropped": 0}


def test_drop_detach_and_deleting_a_row(world: Client):
    chs = chapters(world)
    varren = add(world, "Varren")
    d = decide(world, entities=[varren])
    fact = planned_death(world, d, varren, chs[8])
    fid = fact["followup"]["id"]
    # Drop keeps the follow-up as dropped, dated; the row stays as it is
    r = world.post(f"{W}/decisions/{d['id']}/followups/{fid}/drop").json()
    assert r["followup"]["state"] == "dropped" and r["followup"]["dropped_on"]
    assert r["counts"] == {"todo": 0, "done": 0, "dropped": 1}
    assert world.get(f"{W}/entities/{varren['id']}").json()["facts"][0]["standing"] == "planned"
    assert world.post(f"{W}/decisions/{d['id']}/followups/{fid}/undrop").json()["followup"]["state"] == "todo"
    # deleting the planned fact drops it, keeping its words
    assert world.delete(f"{W}/facts/{fact['made']['id']}").status_code == 204
    [gone] = listing(world, d)
    assert gone["state"] == "dropped" and gone["dropped_on"] and gone["kind"] is None
    assert gone["what"] == "Varren · status: dead · from chapter 9"
    # Detach removes it altogether; the row stays
    rel = follow(world, d, relationship={"type_id": types(world)["knows about"]["id"], "a_id": varren["id"],
                                         "b_id": add(world, "Isolde")["id"], "standing": "planned"})
    out = world.delete(f"{W}/decisions/{d['id']}/followups/{rel['followup']['id']}").json()
    assert out["attach"] == {"table": "relationship", "id": rel["made"]["id"], "any": True}
    assert len(listing(world, d)) == 1
    assert len(world.get(f"{W}/relationships").json()) == 1
    # and Undo puts it back
    follow(world, d, attach=out["attach"])
    assert len(listing(world, d)) == 2


def test_an_entry_deleted_leaves_the_follow_up_dropped_without_a_date(world: Client):
    chs = chapters(world)
    varren = add(world, "Varren")
    d = decide(world, entities=[varren])
    planned_death(world, d, varren, chs[8])
    assert world.get(f"{W}/entities/{varren['id']}").json()["follows"] == {"facts": 1, "relationships": 0}
    world.delete(f"{W}/entities/{varren['id']}")
    [x] = listing(world, d)
    assert x["state"] == "dropped" and x["dropped_on"] is None
    assert x["what"] == "Varren · status: dead · from chapter 9"


def test_the_words_follow_the_row_as_it_changes(world: Client):
    chs = chapters(world)
    varren = add(world, "Varren")
    d = decide(world, entities=[varren])
    fact = planned_death(world, d, varren, chs[8])
    world.patch(f"{W}/facts/{fact['made']['id']}", json={"base_version": 1, "from_chapter_id": chs[9]["id"]})
    task = follow(world, d, item={"body": "Ring it"})
    item = world.get(f"{W}/items/{task['made']['id']}").json()
    world.patch(f"{W}/items/{item['id']}", json={"base_version": item["version"], "body": "Ring the bell twice"})
    world.delete(f"{W}/facts/{fact['made']['id']}")
    assert [x["what"] for x in listing(world, d)] == ["task: Ring the bell twice",
                                                      "Varren · status: dead · from chapter 10"]


def test_deleting_a_decision_keeps_its_rows_and_undoing_a_close_deletes_those_made(world: Client):
    chs = chapters(world)
    varren = add(world, "Varren")
    q = world.post(f"{W}/items", json={"body": "When does Varren die?", "kind": "question"}).json()
    closed = world.post(f"{W}/items/{q['id']}/close", json={"status": "accepted", "decision": DEATH}).json()
    d = {"id": closed["decision_id"]}
    made = planned_death(world, d, varren, chs[8])
    task = world.post(f"{W}/items", json={"body": "Old task", "kind": "task"}).json()
    attached = follow(world, d, attach={"table": "item", "id": task["id"]})
    r = world.delete(f"{W}/decisions/{d['id']}", params={"made": [made["followup"]["id"]]})
    assert r.status_code == 204
    assert world.get(f"{W}/entities/{varren['id']}").json()["facts"] == []
    assert world.get(f"{W}/items/{task['id']}").json()["follows"] == []
    assert attached["made"] is None
    # without `made`, only the links go
    d2 = decide(world, entities=[varren])
    planned_death(world, d2, varren, chs[8])
    world.delete(f"{W}/decisions/{d2['id']}")
    assert world.get(f"{W}/entities/{varren['id']}").json()["facts"][0]["follows"] == []


# the worked-out state (§16.2) -----------------------------------------------------------------------------------


def test_the_state_is_worked_out_from_the_rows(world: Client):
    chs = chapters(world)
    varren, isolde = add(world, "Varren"), add(world, "Isolde")
    d = decide(world, entities=[varren, isolde])
    fact = planned_death(world, d, varren, chs[8])
    assert counts(world, d) == {"todo": 1, "done": 0, "dropped": 0}
    # made canon here: done
    r = world.post(f"{W}/entities/{varren['id']}/facts", json={"label": "status", "make_canon": fact["made"]["id"],
                                                               "established_in_chapter_id": chs[8]["id"]})
    assert r.status_code == 201, r.text
    assert counts(world, d) == {"todo": 0, "done": 1, "dropped": 0}
    # a task makes it 1 of 2 to do again; deferring leaves it to do
    task = follow(world, d, item={"body": "Plant the bell's crack in chapter 4"})["made"]["id"]
    assert counts(world, d) == {"todo": 1, "done": 1, "dropped": 0}
    world.post(f"{W}/items/{task}/close", json={"status": "deferred"})
    assert counts(world, d)["todo"] == 1
    # rejected: counts toward done, listed as dropped, dated its close
    world.post(f"{W}/items/{task}/close", json={"status": "rejected"})
    assert counts(world, d) == {"todo": 0, "done": 1, "dropped": 1}
    rows = listing(world, d)
    assert [(x["state"], x["kind"]) for x in rows] == [("done", "fact"), ("dropped", "task")]
    assert rows[1]["status"] == "rejected" and rows[1]["closed_at"]
    # reopening makes it to do again
    world.post(f"{W}/items/{task}/reopen")
    assert counts(world, d) == {"todo": 1, "done": 1, "dropped": 0}
    # a relationship set to rumour stays to do
    knows = types(world)["knows about"]
    rel = follow(world, d, relationship={"type_id": knows["id"], "a_id": isolde["id"], "b_id": varren["id"],
                                         "standing": "planned"})["made"]["id"]
    world.patch(f"{W}/relationships/{rel}", json={"base_version": 1, "standing": "rumour"})
    assert counts(world, d)["todo"] == 2
    # setting the canon fact back to planned makes it to do again
    f = world.get(f"{W}/entities/{varren['id']}").json()["facts"][0]
    world.patch(f"{W}/facts/{f['id']}", json={"base_version": f["version"], "standing": "planned"})
    assert counts(world, d) == {"todo": 3, "done": 0, "dropped": 0}
    # to do first, then done, then dropped; nowhere to tick a decision done
    assert "done" not in world.patch(f"{W}/decisions/{d['id']}", json={"done": True}).json()


# the gap in a chapter (§16.4) -----------------------------------------------------------------------------------


def test_the_gap_line_shows_once_the_chapter_has_text(world: Client):
    chs = chapters(world, 10, text={10: "Isolde rings the bell."})
    varren = add(world, "Varren")
    d = decide(world, entities=[varren])
    fact = planned_death(world, d, varren, chs[8])
    gaps = lambda ch: world.get(f"{W}/chapters/{ch['id']}/gaps").json()  # noqa: E731
    assert gaps(chs[8]) == []
    # a margin note is not text
    write(world, chs[8], "%% he dies here\n")
    assert gaps(chs[8]) == []
    write(world, chs[8], "The bell rang over the water.\n")
    [line] = gaps(chs[8])
    assert line["what"] == "Varren · status: dead, from this chapter"
    assert line["decision"] == {"id": d["id"], "decided_on": "2026-10-12", "text": DEATH}
    assert line["not_yet"] is None and line["others_todo"] == 0
    # Not yet: a resolution keyed by follow-up and chapter; the decision stays to do
    res = world.put(f"{W}/resolutions", json={"rule": "followup_gap", "key": line["key"], "outcome": "later"}).json()
    assert gaps(chs[8])[0]["not_yet"] == res["id"]
    assert counts(world, d)["todo"] == 1
    # moved to chapter 10 (which has text), it shows there; back in 9, still put off until Show again
    world.patch(f"{W}/facts/{fact['made']['id']}", json={"base_version": 1, "from_chapter_id": chs[9]["id"]})
    assert gaps(chs[8]) == [] and gaps(chs[9])[0]["not_yet"] is None
    world.patch(f"{W}/facts/{fact['made']['id']}", json={"base_version": 2, "from_chapter_id": chs[8]["id"]})
    assert gaps(chs[8])[0]["not_yet"] == res["id"]
    world.delete(f"{W}/resolutions/{res['id']}")
    assert gaps(chs[8])[0]["not_yet"] is None
    # made canon here with a sentence: established in chapter 9 with it, and the decision done
    r = world.post(f"{W}/entities/{varren['id']}/facts", json={
        "label": "status", "make_canon": fact["made"]["id"], "established_in_chapter_id": chs[8]["id"],
        "evidence": "The bell rang over the water."})
    f = r.json()
    assert f["standing"] == "canon" and f["established_in_chapter_id"] == chs[8]["id"]
    assert f["evidence"] == "The bell rang over the water." and f["from_chapter_id"] == chs[8]["id"]
    assert gaps(chs[8]) == [] and counts(world, d) == {"todo": 0, "done": 1, "dropped": 0}


def test_a_change_bounded_by_a_time_shows_in_each_chapter_set_then(world: Client):
    chs = chapters(world, 4, text={1: "One.", 2: "Two.", 3: "Three.", 4: "Four."})
    for ch, at in zip(chs[:3], (412, 412, 413)):
        now = world.get(f"{W}/chapters/{ch['id']}").json()
        r = world.patch(f"{W}/chapters/{ch['id']}/about", json={"base_version": now["version"], "time_at": at})
        assert r.status_code == 200, r.text
    # chapter 4 carries on from 413; a fifth chapter outside time is tied to nothing
    varren = add(world, "Varren")
    d = decide(world, "Varren dies in year 412", entities=[varren])
    follow(world, d, fact={"entity_id": varren["id"], "label": "status", "value": "dead", "standing": "planned",
                           "from_time": 412})
    shown = [len(world.get(f"{W}/chapters/{c['id']}/gaps").json()) for c in chs]
    assert shown == [1, 1, 0, 0]
    [line] = world.get(f"{W}/chapters/{chs[0]['id']}/gaps").json()
    assert line["what"] == "Varren · status: dead, from year 412"


def test_a_finding_on_a_planned_row_names_its_decision(world: Client):
    chs = chapters(world, 10, text={10: "Varren walks in."})
    varren = add(world, "Varren")
    d = decide(world, entities=[varren])
    planned_death(world, d, varren, chs[8])
    off = world.get(f"{W}/checks").json()
    on = world.get(f"{W}/checks", params={"planned": 1}).json()
    assert all("decided" not in x for x in off)
    found = [x for x in on if x["planned"]]
    assert found and found[0]["decided"] == {"id": d["id"], "decided_on": "2026-10-12", "text": DEATH}
    # the gap line is not a finding, and Checks' resolutions leave it out on the device
    assert not any(x["rule"] == "followup_gap" for x in on)


# surfacing (§16.5) ----------------------------------------------------------------------------------------------


def test_open_follow_ups_are_found_on_the_decisions_page_and_the_front_page(world: Client):
    chs = chapters(world, 10, text={9: "The bell rang."})
    varren, isolde = add(world, "Varren"), add(world, "Isolde")
    late = decide(world, "Isolde leaves in chapter 10", entities=[isolde], day="2026-10-20")
    early = decide(world, entities=[varren], day="2026-10-12")
    decide(world, "Settled, nothing to do", day="2026-10-15")
    planned_death(world, early, varren, chs[8])
    task = follow(world, late, item={"body": "Pack her bags"})["made"]["id"]
    listed = world.get(f"{W}/decisions", params={"followups": "open"}).json()
    assert [x["text"] for x in listed] == [DEATH, "Isolde leaves in chapter 10"]
    front = world.get(f"{W}/front").json()["follow_through"]
    assert front["count"] == 2
    assert [(x["text"], (x["written"] or {}).get("n")) for x in front["decisions"]] == [
        (DEATH, 9), ("Isolde leaves in chapter 10", None)]
    world.post(f"{W}/items/{task}/close", json={"status": "accepted"})
    f = world.get(f"{W}/entities/{varren['id']}").json()["facts"][0]
    world.patch(f"{W}/facts/{f['id']}", json={"base_version": f["version"], "standing": "canon"})
    assert world.get(f"{W}/front").json()["follow_through"] == {"decisions": [], "count": 0}
    assert world.get(f"{W}/decisions", params={"followups": "open"}).json() == []


# export and Restore (§16.6) -------------------------------------------------------------------------------------


def test_export_and_restore_keep_every_follow_up(world: Client):
    chs = chapters(world, 11)
    varren, isolde = add(world, "Varren"), add(world, "Isolde")
    d = decide(world, entities=[varren, isolde])
    other = decide(world, "Isolde knows by chapter 11", entities=[isolde], day="2026-10-13")
    planned_death(world, d, varren, chs[8])
    task = follow(world, d, item={"body": "Plant the bell's crack in chapter 4", "entities": [varren["id"]],
                                  "chapters": [chs[3]["id"]]})["made"]["id"]
    world.post(f"{W}/items/{task}/close", json={"status": "accepted"})
    knows = types(world)["knows about"]
    rel = follow(world, d, relationship={"type_id": knows["id"], "a_id": isolde["id"], "b_id": varren["id"],
                                         "standing": "planned", "from_chapter_id": chs[10]["id"]})
    world.delete(f"{W}/relationships/{rel['made']['id']}")
    # one row following two decisions, dropped by hand on one of them
    shared = follow(world, other, item={"body": "Ask Isolde"})
    follow(world, d, attach={"table": "item", "id": shared["made"]["id"]})
    world.post(f"{W}/decisions/{other['id']}/followups/{shared['followup']['id']}/drop")
    rejected = follow(world, other, item={"body": "Cut the bell"})["made"]["id"]
    world.post(f"{W}/items/{rejected}/close", json={"status": "rejected"})

    data = world.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    decisions = z.read(next(n for n in z.namelist() if n.endswith("Decisions.md"))).decode()
    lines = decisions.splitlines()
    at = next(i for i, x in enumerate(lines) if DEATH in x)
    assert lines[at].startswith("- 2026-10-12 · [the-salt-road] Varren dies at the end of chapter 9 <!-- id=")
    assert lines[at + 1:at + 5] == [
        "  - to do: Varren · status: dead · from chapter 9 (planned fact)",
        "  - to do: Ask Isolde (task, open)",
        "  - done: Plant the bell's crack in chapter 4 (task, accepted)",
        f"  - dropped {rel_day(world, d)}: Isolde knows about Varren · from chapter 11",
    ]

    def look(slug: str) -> list:
        base = f"/api/worlds/{slug}"
        out = []
        for x in world.get(f"{base}/decisions").json():
            rows = world.get(f"{base}/decisions/{x['id']}/followups").json()
            # within a state, the order they were made in isn't kept
            out.append((x["text"], x["followups"],
                        sorted((r["state"], r["what"], r["dropped_on"] or "", r["kind"] or "") for r in rows)))
        return out

    before = look("delta")
    r = world.post("/api/worlds/restore", files={"file": ("export.zip", data, "application/zip")})
    assert r.status_code == 201, r.text
    assert look(r.json()["slug"]) == before


def rel_day(c: Client, d: dict) -> str:
    return next(x["dropped_on"] for x in listing(c, d) if x["state"] == "dropped")


def test_an_older_export_restores_its_decisions_settled(world: Client):
    chapters(world, 2)
    decide(world, "Something settled")
    data = world.get(f"{W}/export").content
    r = world.post("/api/worlds/restore", files={"file": ("export.zip", data, "application/zip")})
    assert [x["followups"] for x in world.get(f"/api/worlds/{r.json()['slug']}/decisions").json()] == [None]


# the demo world (§16.7) -----------------------------------------------------------------------------------------


def test_the_demo_shows_all_three_states(signed_in: Client):
    slug = signed_in.post("/api/worlds/demo").json()["slug"]
    base = f"/api/worlds/{slug}"
    states = {x["text"]: x["followups"] for x in signed_in.get(f"{base}/decisions").json()}
    assert states["Oskar dies in chapter 2, not chapter 1."] is None
    assert states["Hesper is a cartographer, and Ash Season shows her at her maps"] == {"todo": 0, "done": 1, "dropped": 0}
    assert states["Brother Cade dies at Saltreach, in What the River Kept"] == {"todo": 1, "done": 1, "dropped": 0}
    chs = signed_in.get(f"{base}/projects/the-ferrymans-daughter/chapters").json()["chapters"]
    third = next(c for c in chs if c["title"] == "What the River Kept")
    [line] = signed_in.get(f"{base}/chapters/{third['id']}/gaps").json()
    assert line["what"] == "Brother Cade · status: dead, from this chapter"
    front = signed_in.get(f"{base}/front").json()["follow_through"]
    assert [(x["text"], x["written"]["n"]) for x in front["decisions"]] == [
        ("Brother Cade dies at Saltreach, in What the River Kept", 3)]
    cade = next(x for x in signed_in.get(f"{base}/decisions").json() if x["text"].startswith("Brother Cade"))
    named = signed_in.get(f"{base}/decisions/{cade['id']}/chapters").json()
    assert [x["label"] for x in named] == ["chapter 3, What the River Kept"]
    # Include planned still turns his planned death into Ash Season's finding, now naming the decision
    found = [x for x in signed_in.get(f"{base}/checks", params={"planned": 1}).json() if x.get("decided")]
    assert found and all(x["decided"]["id"] == cade["id"] for x in found)
