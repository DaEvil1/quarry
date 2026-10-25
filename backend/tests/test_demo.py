"""The demo world loads, and everything it is meant to show is there."""

from __future__ import annotations

from .conftest import Client


def test_demo_world(signed_in: Client):
    r = signed_in.post("/api/worlds/demo")
    assert r.status_code == 201, r.text
    world = r.json()
    W = f"/api/worlds/{world['slug']}"
    assert world["name"] == "The Ninefold Delta (demo)"
    assert [p["name"] for p in world["projects"]] == ["The Ferryman's Daughter", "Ash Season"]

    entities = {e["name"]: e for e in signed_in.get(f"{W}/entities").json()}
    assert {e["kind"] for e in entities.values()} == {"character", "place", "faction", "culture", "species", "event", "object", "term"}
    # names are found in the text: the first name, an alias, a term in any case, and not "moss" the plant
    assert entities["Tamsin Vey"]["mention_count"] > 5
    assert entities["Tidecall"]["mention_count"] >= 2
    moss = signed_in.get(f"{W}/entities/{entities['Moss']['id']}").json()
    assert all("grew" not in m["snippet"]["after"][:6] for m in moss["mentions"])

    book = signed_in.get(f"{W}/projects/the-ferrymans-daughter/chapters").json()
    assert [c["title"] for c in book["chapters"]] == ["The Crossing", "Lanterns on the Water", "What the River Kept", "The Locks"]
    assert [c["title"] for c in book["experiments"]] == ["Lanterns on the Water (from the water)"]
    assert book["retired"] == 1
    assert {x["name"] for x in book["cast"][book["chapters"][0]["id"]]} >= {"Tamsin Vey", "Oskar Vey", "Ilse Marrow"}

    # the continuity checks it is planted with
    rules = {(c["rule"], c["chapter"]["title"] if c["chapter"] else None) for c in signed_in.get(f"{W}/checks").json()}
    assert ("dead_mentioned", "Ash Season") in rules
    assert ("before_start", "The Locks") in rules
    assert ("pov_absent", "The Locks") in rules
    assert any(r == "fact_conflict" for r, _ in rules)

    # relationships read both ways, story time, presence, the graph's co-occurrence
    tamsin = signed_in.get(f"{W}/entities/{entities['Tamsin Vey']['id']}").json()
    assert {r["reads"] for r in tamsin["relationships"]} >= {"child of", "friend of", "lives in", "owns", "student of"}
    where = signed_in.get(f"{W}/where").json()
    rows = {r["entity"]["name"]: r["cells"] for r in where["rows"]}
    assert any(c["recorded"] and c["recorded"]["name"] == "Saltreach Abbey" for c in rows["Tamsin Vey"].values())
    assert signed_in.get(f"{W}/graph?co=true").json()["cooccurrence"]

    # planning, and what an export doesn't carry
    assert len(signed_in.get(f"{W}/items?status=all").json()) == 10
    tagged = {e["name"] for d in signed_in.get(f"{W}/decisions").json() for e in d["entities"]}
    assert tagged == {"Oskar Vey", "The Brass Compass", "Tamsin Vey", "Hesper Quill"}
    journal = {j["title"]: j for j in signed_in.get(f"{W}/journal").json()}
    assert list(journal) == ["Ash as a clock", "Why a ferry?", "Loose threads", "What the Wardens want", "The first map"]
    third = book["chapters"][2]["id"]
    assert [(i["body"].split("\n")[0], i["passage"]) for i in signed_in.get(f"{W}/chapters/{third}/items").json()] == [
        ("How far upriver do the locks reach?", "Brother Cade said the River Wardens raised Marrow Locks"),
        ("How many lanterns does the abbey set out for its own dead?", None)]
    assert signed_in.get(f"{W}/chapters/{third}/session-note").json()["note"].startswith("Tamsin opens the compass")

    # planning before writing (docs/SPEC.md §14.1–§14.3): planned in the Journal, a note, a fact made canon, items
    # made from passages, and "??" markers
    wardens_entry = journal["What the Wardens want"]["id"]
    wardens = signed_in.get(f"{W}/entities/{entities['The River Wardens']['id']}").json()
    age = next(f for f in wardens["facts"] if f["label"] == "age")
    assert (age["standing"], age["planned_in_journal_id"]) == ("planned", wardens_entry)
    assert wardens["journal_entries"][wardens_entry]["date"] == "2019-03-02"
    toll = signed_in.get(f"{W}/entities/{entities['The First Toll']['id']}").json()
    assert toll["tellings"] == [] and toll["notes"][0]["journal"]["id"] == wardens_entry
    assert [(r["standing"], r["planned_in_journal_id"]) for r in toll["relationships"]] == [("planned", wardens_entry)]
    hesper = signed_in.get(f"{W}/entities/{entities['Hesper Quill']['id']}").json()
    trade = next(f for f in hesper["facts"] if f["label"] == "trade")
    assert trade["standing"] == "canon" and trade["established_in_chapter_id"] and trade["planned_in_journal_id"]
    parked = next(i for i in signed_in.get(f"{W}/items?status=deferred").json() if i["origin"])
    assert (parked["kind"], parked["origin"]["id"]) == ("spark", wardens_entry)
    assert "??" in journal["Loose threads"]["body"]

    # getting back in and checking (docs/SPEC.md §14.4–§14.9)
    front = signed_in.get(f"{W}/front").json()
    assert front["premise"].startswith("A ferry-girl")
    assert ("journal", "Settle Hesper's age before chapter two of Ash Season") in [(n["source"], n["note"]) for n in front["notes"]]
    assert signed_in.get(f"{W}/journal/{journal['The first map']['id']}/since").json()["decisions"] >= 1
    planned = {(c["rule"], c["planned"], (c["chapter"] or {}).get("title")) for c in signed_in.get(f"{W}/checks", params={"planned": 1}).json()}
    assert ("dead_mentioned", True, "Ash Season") in planned
    assert not any(c["rule"] == "dead_mentioned" and "Cade" in c["message"] for c in signed_in.get(f"{W}/checks").json())
    assert ("cause_after_effect", "Lanterns on the Water") in rules
    # two Linnets: "The Cartographer" settles the bare name with choice lines (docs/SPEC.md §14.10)
    two_book = signed_in.get(f"{W}/projects/ash-season/chapters").json()["chapters"]
    cartographer = signed_in.get(f"{W}/chapters/{next(c['id'] for c in two_book if c['title'] == 'The Cartographer')}").json()
    linnets = [(m["kind"], m["entity_name"]) for m in cartographer["mentions"] if m["matched_text"] == "Linnet"]
    assert linnets == [("ambiguous", "Linnet Dray"), ("ambiguous", "Linnet Sorrel"), ("alias", "Linnet Sorrel"),
                       ("alias", "Linnet Dray"), ("ambiguous", "Linnet Dray"), ("ambiguous", "Linnet Sorrel")]
    delta = next(e for e in signed_in.get(f"{W}/entities", params={"kind": "character"}).json() if e["name"] == "The Ninefold Delta")
    assert (delta["kind"], delta["also_kinds"]) == ("place", ["character"])

    # revising: summaries and statuses, a cut, and a few days of word history (and nothing for the day it loaded)
    assert all(c["summary"] and c["status"] for c in book["chapters"])
    assert [t["label"] for t in book["status_tally"]] == ["raw", "rewritten", "polished", None]
    assert [s["label"] for s in book["statuses"]] == ["raw", "rewritten", "polished"]
    two = signed_in.get(f"{W}/projects/ash-season/chapters").json()
    assert [s["label"] for s in two["statuses"]] == ["sketch", "draft", "clean"]
    cuts = signed_in.get(f"{W}/projects/the-ferrymans-daughter/cuts").json()
    assert len(cuts) == 1 and cuts[0]["chapter"]["title"] == "The Crossing"
    crossing = signed_in.get(f"{W}/chapters/{book['chapters'][0]['id']}").json()["body"]
    assert (cuts[0]["before"] + cuts[0]["after"]) in crossing and cuts[0]["body"] not in crossing
    history = signed_in.get(f"{W}/projects/the-ferrymans-daughter/word-history").json()
    days = {r["at"][:10] for r in history["revisions"]}
    assert len(days) >= 5 and history["pending"] == []
    assert any(r["removed"] >= 30 for r in history["revisions"])

    # a second copy gets its own address
    again = signed_in.post("/api/worlds/demo").json()
    assert again["slug"] != world["slug"]


def test_delete_a_world(signed_in: Client):
    world = signed_in.post("/api/worlds/demo").json()
    W = f"/api/worlds/{world['slug']}"
    assert signed_in.request("DELETE", W, json={"name": "the ninefold delta"}).status_code == 422
    assert signed_in.request("DELETE", W, json={"name": world["name"]}).status_code == 204
    assert signed_in.get(W).status_code == 404
    assert world["slug"] not in [w["slug"] for w in signed_in.get("/api/me").json()["worlds"]]
