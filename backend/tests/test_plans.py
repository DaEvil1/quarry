"""A chapter's plan (docs/SPEC.md §18): marking a journal entry as a plan, linking it to chapters, a plan before its
chapter, items from a plan reaching its chapters, experiments, and plans in the export and Restore. Made-up names."""

from __future__ import annotations

import io
import zipfile

import yaml

from .conftest import Client

W = "/api/worlds/coast"


def build(c: Client) -> dict:
    c.post("/api/worlds", json={"name": "Coast"})
    c.post(f"{W}/projects", json={"name": "The Salt Road"})
    chapters = [c.post(f"{W}/projects/the-salt-road/chapters", json={"title": t, "body": f"{t} text."}).json()
                for t in ("One", "Two", "Three", "The Quay", "Five", "Six")]
    quay = c.post(f"{W}/journal", json={"title": "Plan: The Quay", "body": "Isolde at the quay.", "entry_date": "2026-10-03",
                                        "project": "the-salt-road"}).json()
    again = c.post(f"{W}/journal", json={"title": "The Quay again", "body": "Start at night.", "entry_date": "2026-10-14",
                                         "project": "the-salt-road"}).json()
    flood = c.post(f"{W}/journal", json={"title": "After the flood", "body": "The water goes down.",
                                         "entry_date": "2026-10-20", "project": "the-salt-road"}).json()
    return {"ch": chapters, "quay": quay, "again": again, "flood": flood}


def test_mark_link_and_list(signed_in: Client):
    b = build(signed_in)
    quay, four, five = b["quay"], b["ch"][3], b["ch"][4]
    out = signed_in.patch(f"{W}/journal/{quay['id']}/about", json={"is_plan": True}).json()
    assert out["is_plan"] and out["chapters"] == []
    out = signed_in.put(f"{W}/journal/{quay['id']}/chapters/{four['id']}").json()
    assert [(c["n"], c["title"]) for c in out["chapters"]] == [(4, "The Quay")]
    # linking an entry that isn't marked marks it; a plan can be for several chapters
    signed_in.put(f"{W}/journal/{b['again']['id']}/chapters/{four['id']}")
    signed_in.put(f"{W}/journal/{quay['id']}/chapters/{five['id']}")
    detail = signed_in.get(f"{W}/chapters/{four['id']}").json()
    assert [p["title"] for p in detail["plan_list"]] == ["The Quay again", "Plan: The Quay"]
    assert [p["title"] for p in signed_in.get(f"{W}/chapters/{five['id']}").json()["plan_list"]] == ["Plan: The Quay"]
    book = {c["title"]: c["plans"] for c in signed_in.get(f"{W}/projects/the-salt-road/chapters").json()["chapters"]}
    assert book["The Quay"] == 2 and book["Five"] == 1 and book["One"] == 0
    plans = signed_in.get(f"{W}/journal?plans=1").json()
    assert [p["title"] for p in plans] == ["The Quay again", "Plan: The Quay"]
    assert {p["title"]: len(p["chapters"]) for p in plans} == {"The Quay again": 1, "Plan: The Quay": 2}
    assert [j["title"] for j in signed_in.get(f"{W}/journal").json() if not j["is_plan"]] == ["After the flood"]
    # unlinking keeps the mark; unmarking removes the links
    signed_in.delete(f"{W}/journal/{quay['id']}/chapters/{five['id']}")
    assert signed_in.get(f"{W}/chapters/{five['id']}").json()["plan_list"] == []
    out = signed_in.patch(f"{W}/journal/{quay['id']}/about", json={"is_plan": False}).json()
    assert not out["is_plan"] and out["chapters"] == []
    assert [p["title"] for p in signed_in.get(f"{W}/chapters/{four['id']}").json()["plan_list"]] == ["The Quay again"]
    # the delete warning names the chapters; deleting the plan takes its links
    assert [c["title"] for c in signed_in.get(f"{W}/journal/{b['again']['id']}/ties").json()["plan_for"]] == ["The Quay"]
    signed_in.delete(f"{W}/journal/{b['again']['id']}")
    assert signed_in.get(f"{W}/chapters/{four['id']}").json()["plan_list"] == []


def test_a_plan_before_its_chapter(signed_in: Client):
    b = build(signed_in)
    flood, six = b["flood"], b["ch"][5]
    signed_in.patch(f"{W}/journal/{flood['id']}/about", json={"is_plan": True})
    waiting = signed_in.get(f"{W}/journal?plans=unlinked&project=the-salt-road").json()
    assert [p["title"] for p in waiting] == ["After the flood"]
    r = signed_in.post(f"{W}/journal/{flood['id']}/start-chapter", json={"project": "the-salt-road", "after": six["id"]})
    assert r.status_code == 201
    ch = r.json()
    assert (ch["title"], ch["position"], ch["body"], ch["state"]) == ("After the flood", 6, "", "current")
    assert [p["title"] for p in ch["plan_list"]] == ["After the flood"]
    assert signed_in.get(f"{W}/journal?plans=unlinked&project=the-salt-road").json() == []
    # after chapter 2: the chapters after it move down one
    two = b["ch"][1]
    mid = signed_in.post(f"{W}/journal/{b['quay']['id']}/start-chapter", json={"project": "the-salt-road", "after": two["id"]}).json()
    titles = [c["title"] for c in signed_in.get(f"{W}/projects/the-salt-road/chapters").json()["chapters"]]
    assert titles == ["One", "Two", "Plan: The Quay", "Three", "The Quay", "Five", "Six", "After the flood"]
    # Undo: the chapter is deleted while it is empty, and the plan waits again
    assert signed_in.delete(f"{W}/chapters/{ch['id']}").status_code == 204
    signed_in.delete(f"{W}/chapters/{mid['id']}")
    assert [p["title"] for p in signed_in.get(f"{W}/journal?plans=unlinked&project=the-salt-road").json()] == [
        "After the flood", "Plan: The Quay"]
    # at the end, by default
    end = signed_in.post(f"{W}/journal/{flood['id']}/start-chapter", json={"project": "the-salt-road"}).json()
    assert end["position"] == 6


def test_items_and_experiments_reach_the_chapter(signed_in: Client):
    b = build(signed_in)
    four, five = b["ch"][3], b["ch"][4]
    quay = b["quay"]
    signed_in.put(f"{W}/journal/{quay['id']}/chapters/{four['id']}")
    item = signed_in.post(f"{W}/items", json={"body": "Who rows her out?", "kind": "question", "journal_id": quay["id"],
                                              "passage": "Isolde at the quay", "chapter_ids": [four["id"]]}).json()
    assert [i["id"] for i in signed_in.get(f"{W}/chapters/{four['id']}/items").json()] == [item["id"]]
    assert [i["id"] for i in signed_in.get(f"{W}/journal/{quay['id']}/items").json()] == [item["id"]]
    # an experiment from a copy: its draft has the chapter's plans; accepting keeps the links, the old one in Salvage
    draft = signed_in.post(f"{W}/chapters/{four['id']}/experiments", json={"start": "copy", "title": "The Quay, at night"}).json()
    assert [p["title"] for p in draft["plan_list"]] == ["Plan: The Quay"]
    signed_in.post(f"{W}/chapters/{draft['id']}/close-experiment", json={"outcome": "accepted"})
    states = sorted(c["state"] for c in signed_in.get(f"{W}/journal/{quay['id']}").json()["chapters"])
    assert states == ["current", "retired"]
    # from scratch over a range: the plans of every chapter in it; an experiment that only adds links none
    signed_in.put(f"{W}/journal/{b['again']['id']}/chapters/{five['id']}")
    r = signed_in.post(f"{W}/projects/the-salt-road/experiments",
                       json={"title": "Four and five", "start": "scratch", "range": [draft["id"], five["id"]]}).json()
    plans = [p["title"] for p in signed_in.get(f"{W}/chapters/{r['first']}").json()["plan_list"]]
    assert sorted(plans) == ["Plan: The Quay", "The Quay again"]
    add = signed_in.post(f"{W}/projects/the-salt-road/experiments",
                         json={"title": "Adds", "start": "scratch", "insert": {"chapter_id": five["id"], "side": "after"}}).json()
    assert signed_in.get(f"{W}/chapters/{add['first']}").json()["plan_list"] == []


def test_plans_in_the_export_and_restore(signed_in: Client):
    b = build(signed_in)
    four, two = b["ch"][3], b["ch"][1]
    signed_in.put(f"{W}/journal/{b['quay']['id']}/chapters/{four['id']}")
    signed_in.put(f"{W}/journal/{b['again']['id']}/chapters/{two['id']}")
    signed_in.post(f"{W}/chapters/{two['id']}/retire", json={"note": ""})
    signed_in.patch(f"{W}/journal/{b['flood']['id']}/about", json={"is_plan": True})
    signed_in.post(f"{W}/items", json={"body": "Who rows her out?", "kind": "question", "journal_id": b["quay"]["id"],
                                       "passage": "Isolde at the quay", "chapter_ids": [four["id"]]})
    data = signed_in.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    quay = next(n for n in z.namelist() if "Plan The Quay" in n or "Plan_ The Quay" in n or "Plan  The Quay" in n)
    meta = yaml.safe_load(z.read(quay).decode().split("---\n")[1])
    assert meta["plan"] is True and meta["chapters"] == [four["id"]]

    out = signed_in.post("/api/worlds/restore", files={"file": ("x.zip", data, "application/zip")}).json()
    base = f"/api/worlds/{out['slug']}"
    plans = {p["title"]: p for p in signed_in.get(f"{base}/journal?plans=1").json()}
    assert set(plans) == {"Plan: The Quay", "The Quay again", "After the flood"}
    assert [c["title"] for c in plans["Plan: The Quay"]["chapters"]] == ["The Quay"]
    assert [(c["title"], c["state"]) for c in plans["The Quay again"]["chapters"]] == [("Two", "retired")]
    assert plans["After the flood"]["chapters"] == []
    new_four = plans["Plan: The Quay"]["chapters"][0]["id"]
    assert [i["body"] for i in signed_in.get(f"{base}/chapters/{new_four}/items").json()] == ["Who rows her out?"]


def test_a_hand_made_plan_with_an_unknown_chapter(signed_in: Client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("w/world.md", "---\nquarry_export: 1\nname: Handmade\n---\n")
        z.writestr("w/Projects/Book/project.md", "---\nname: Book\nslug: book\n---\n")
        z.writestr("w/Projects/Book/Manuscript/01 One.md", "---\nid: c1\ntitle: One\nposition: 0\n---\n\nText.\n")
        z.writestr("w/Journal/2026-10-01 Plan.md",
                   "---\nid: p1\ndate: 2026-10-01\ntitle: Plan\nproject: book\nplan: true\nchapters: [c1, nowhere]\n---\n\nIdeas.\n")
    out = signed_in.post("/api/worlds/restore", files={"file": ("x.zip", buf.getvalue(), "application/zip")}).json()
    plans = signed_in.get(f"/api/worlds/{out['slug']}/journal?plans=1").json()
    assert [(p["title"], [c["title"] for c in p["chapters"]]) for p in plans] == [("Plan", ["One"])]
