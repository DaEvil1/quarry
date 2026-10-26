"""Phase 10, revising and salvaging (SPEC §11): renames that keep the old name, chapter summaries and statuses, the
cuts bin, word history, a checkpoint of every chapter, and find and replace across chapters."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from quarry.wordhistory import word_changes

from .conftest import Client

W = "/api/worlds/coast"
P = f"{W}/projects/book-one"


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Book One"})
    return signed_in


def chapter(c: Client, title: str, body: str = "", project: str = "book-one") -> dict:
    r = c.post(f"{W}/projects/{project}/chapters", json={"title": title, "body": body})
    assert r.status_code == 201, r.text
    return r.json()


def save(c: Client, ch: dict, body: str) -> dict:
    current = c.get(f"{W}/chapters/{ch['id']}").json()
    r = c.patch(f"{W}/chapters/{ch['id']}", json={"base_version": current["version"], "body": body})
    assert r.status_code == 200, r.text
    return r.json()


def entity(c: Client, name: str, **extra) -> dict:
    r = c.post(f"{W}/entities", json={"name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def rename(c: Client, e: dict, name: str, **extra) -> dict:
    current = c.get(f"{W}/entities/{e['id']}").json()["entity"]
    r = c.patch(f"{W}/entities/{e['id']}", json={"base_version": current["version"], "name": name, **extra})
    assert r.status_code == 200, r.text
    return r.json()


# 11.1 a rename keeps the old name ---------------------------------------------------------------------------------


def test_done_when_a_rename_keeps_the_old_name_and_remove_takes_it_away(world: Client):
    v = entity(world, "Varren", aliases=["the Grey Keeper"])
    ch = chapter(world, "One", "Varren waits on the pier.")
    out = rename(world, v, "Varran")
    assert out["kept_alias"] == "Varren" and out["aliases"] == ["the Grey Keeper", "Varren"]
    # the chapter that still says "Varren" stays linked to him
    mentions = world.get(f"{W}/chapters/{ch['id']}").json()["mentions"]
    assert [(m["matched_text"], m["entity_name"], m["kind"]) for m in mentions] == [("Varren", "Varran", "alias")]
    # Remove: one more save, and the old spelling is a possible misspelling again
    r = world.patch(f"{W}/entities/{v['id']}", json={"base_version": out["version"], "aliases": ["the Grey Keeper"]})
    assert r.json()["aliases"] == ["the Grey Keeper"] and r.json()["kept_alias"] is None
    mentions = world.get(f"{W}/chapters/{ch['id']}").json()["mentions"]
    assert [(m["matched_text"], m["kind"]) for m in mentions] == [("Varren", "near_miss")]


def test_a_rename_keeps_nothing_for_capitals_an_existing_name_or_another_entry(world: Client):
    v = entity(world, "varren")
    assert rename(world, v, "Varren")["kept_alias"] is None
    assert rename(world, v, "Varren")["aliases"] == []
    h = entity(world, "Hale", aliases=["Old Hale"])
    assert rename(world, h, "Hale the Elder", keep_old_name=True)["kept_alias"] == "Hale"
    # back to a name that is already one of its other names: it leaves the other names, nothing is added twice
    out = rename(world, h, "Hale")
    assert out["kept_alias"] == "Hale the Elder" and out["aliases"] == ["Old Hale", "Hale the Elder"]
    # the old name belongs to another entry too (it would match two entries)
    entity(world, "Isolde", aliases=["Mara"])
    m = entity(world, "Mara")
    assert rename(world, m, "Marra")["kept_alias"] is None
    # asked not to keep it
    t = entity(world, "Tamsin")
    assert rename(world, t, "Tamsyn", keep_old_name=False)["aliases"] == []


def test_promoting_another_name_puts_the_old_name_in_its_place(world: Client):
    v = entity(world, "Varren", aliases=["Grey Keeper", "Varren Hale", "Old V"])
    out = rename(world, v, "Varren Hale")
    assert out["name"] == "Varren Hale" and out["aliases"] == ["Grey Keeper", "Varren", "Old V"]
    assert out["kept_alias"] == "Varren"


# 11.2 a summary and a status per chapter --------------------------------------------------------------------------


def test_done_when_summaries_and_statuses_show_and_a_rename_reaches_every_pill(world: Client):
    one = chapter(world, "Arrival", "The boat comes in at dawn.")
    two = chapter(world, "Storm", "Rain.")
    chapter(world, "Ending", "Light.")
    statuses = world.get(f"{P}/statuses").json()
    assert [s["label"] for s in statuses] == ["raw", "rewritten", "polished"]
    raw, rewritten = statuses[0]["id"], statuses[1]["id"]
    v = world.get(f"{W}/chapters/{one['id']}").json()["version"]
    r = world.patch(f"{W}/chapters/{one['id']}/about", json={"summary": "  The boat  arrives. ", "status_id": rewritten})
    assert (r.json()["summary"], r.json()["status"]["label"]) == ("The boat arrives.", "rewritten")
    # a label, not text: the version (and so any other device's next save) is left alone
    assert world.get(f"{W}/chapters/{one['id']}").json()["version"] == v
    world.patch(f"{W}/chapters/{two['id']}/about", json={"status_id": rewritten})
    world.patch(f"{W}/chapters/{two['id']}/about", json={"summary": "Rain"})
    m = world.get(f"{P}/chapters").json()
    assert [(c["summary"], (c["status"] or {}).get("label")) for c in m["chapters"]] == [
        ("The boat arrives.", "rewritten"), ("Rain", "rewritten"), ("", None)]
    assert [(t["label"], t["chapters"], t["words"]) for t in m["status_tally"]] == [
        ("raw", 0, 0), ("rewritten", 2, 7), ("polished", 0, 0), (None, 1, 1)]

    # renaming "rewritten" renames every pill that says it
    world.patch(f"{W}/statuses/{rewritten}", json={"label": "second draft"})
    m = world.get(f"{P}/chapters").json()
    assert [(c["status"] or {}).get("label") for c in m["chapters"]] == ["second draft", "second draft", None]

    # added, ordered, removed (its chapters go back to none)
    added = world.post(f"{P}/statuses", json={"label": "final"}).json()
    assert [s["label"] for s in added] == ["raw", "second draft", "polished", "final"]
    ids = [s["id"] for s in added]
    ordered = world.put(f"{P}/status-order", json={"ids": [ids[3], ids[0], ids[1], ids[2]]}).json()
    assert [(s["label"], s["position"], s["chapters"]) for s in ordered] == [
        ("final", 0, 0), ("raw", 1, 0), ("second draft", 2, 2), ("polished", 3, 0)]
    left = world.delete(f"{W}/statuses/{rewritten}").json()
    assert [s["label"] for s in left] == ["final", "raw", "polished"]
    assert world.get(f"{W}/chapters/{one['id']}").json()["status"] is None
    assert raw


def test_a_status_must_be_the_projects_own(world: Client):
    world.post(f"{W}/projects", json={"name": "Novella"})
    other = world.get(f"{W}/projects/novella/statuses").json()[0]["id"]
    ch = chapter(world, "One", "x")
    assert world.patch(f"{W}/chapters/{ch['id']}/about", json={"status_id": other}).status_code == 422


def test_experiments_and_retired_chapters_keep_their_summary_and_status(world: Client):
    ch = chapter(world, "Old opening", "A gull.")
    st = world.get(f"{P}/statuses").json()[2]["id"]
    world.patch(f"{W}/chapters/{ch['id']}/about", json={"summary": "the gull", "status_id": st})
    world.post(f"{W}/chapters/{ch['id']}/retire", json={})
    s = world.get(f"{P}/salvage").json()[0]
    assert (s["summary"], s["status"]["label"]) == ("the gull", "polished")


# 11.3 the cuts bin ------------------------------------------------------------------------------------------------


def test_done_when_a_cut_is_in_the_bin_found_by_search_and_put_back(world: Client):
    ch = chapter(world, "Arrival", "Before.\n\nThe heron lifted from the reeds.\n\nAfter.")
    cut_id = str(uuid.uuid4())
    save(world, ch, "Before.\n\n\n\nAfter.")
    body = {"id": cut_id, "chapter_id": ch["id"], "body": "The heron lifted from the reeds.", "before": "Before.\n\n",
            "after": "\n\nAfter.", "cut_at": "2026-10-20T08:00:00+00:00"}
    r = world.post(f"{W}/cuts", json=body)
    assert r.status_code == 201, r.text
    # sent again (an offline phone retrying): kept once
    assert world.post(f"{W}/cuts", json=body).status_code == 201
    bin_ = world.get(f"{P}/cuts").json()
    assert len(bin_) == 1
    c = bin_[0]
    assert (c["chapter"]["title"], c["chapter_title"], c["words"], c["before"]) == ("Arrival", "Arrival", 6, "Before.\n\n")
    assert world.get(f"{P}/cuts?q=heron").json()[0]["match"]["match"] == "heron"
    assert world.get(f"{P}/cuts?q=gull").json() == []
    assert [x["id"] for x in world.get(f"{W}/chapters/{ch['id']}/cuts").json()] == [cut_id]
    # cuts are not names or words of the chapter
    assert world.get(f"{P}/chapters").json()["words"] == 2

    # put back: the editor makes the edit, the cut stays in the bin marked
    r = world.post(f"{W}/cuts/{cut_id}/put-back", json={"chapter_id": ch["id"]})
    assert r.json()["put_back_to"]["title"] == "Arrival" and r.json()["put_back_at"]
    assert world.get(f"{P}/cuts").json() == []
    assert len(world.get(f"{P}/cuts?put_back=true").json()) == 1
    assert world.get(f"{W}/chapters/{ch['id']}/cuts").json() == []


def test_undo_right_after_cutting_removes_the_cut(world: Client):
    ch = chapter(world, "One", "x")
    cut_id = str(uuid.uuid4())
    world.post(f"{W}/cuts", json={"id": cut_id, "chapter_id": ch["id"], "body": "a line"})
    assert world.delete(f"{W}/cuts/{cut_id}").status_code == 204
    assert world.get(f"{P}/cuts?put_back=true").json() == []
    world.post("/api/worlds", json={"name": "Other"})
    assert world.post("/api/worlds/other/cuts", json={"id": str(uuid.uuid4()), "chapter_id": ch["id"],
                                                      "body": "x"}).status_code == 404


# 11.5 word history ------------------------------------------------------------------------------------------------


def test_word_changes_counts_paragraph_then_word_and_skips_margin_notes():
    assert word_changes("", "One two three.") == (3, 0)
    assert word_changes("One two three.\n\nFour five.", "One two three.\n\nFour five.") == (0, 0)
    assert word_changes("The boat comes in.", "The small boat comes in late.") == (2, 0)
    assert word_changes("The boat comes in.\n\nA gull.", "The boat comes in.") == (0, 2)
    assert word_changes("A line.", "A line.\n%% a note to myself") == (0, 0)
    assert word_changes("One two.", "One three.") == (1, 1)


def test_done_when_two_days_of_writing_and_cutting_show_and_a_restore_shows_none(world: Client, db):
    from quarry.models import Revision

    a = chapter(world, "One")
    b = chapter(world, "Two")
    save(world, a, "The boat comes in at dawn.")
    world.post(f"{W}/chapters/{a['id']}/revisions", json={"reason": "autosnap"})
    save(world, b, "Rain on the harbour.")
    world.post(f"{W}/chapters/{b['id']}/revisions", json={"reason": "autosnap"})
    # the next day: a scene cut from the first chapter
    yesterday = datetime.now(UTC) - timedelta(days=1)
    for r in db.query(Revision).all():
        r.created_at = yesterday
    db.commit()
    save(world, a, "The boat comes in.")
    world.post(f"{W}/chapters/{a['id']}/revisions", json={"reason": "checkpoint", "label": "trimmed"})
    # and something typed today, not yet in a revision
    save(world, b, "Rain on the harbour. Wind too.")

    h = world.get(f"{P}/word-history").json()
    rows = sorted((r["at"][:10], h["chapters"][r["chapter_id"]], r["added"], r["removed"]) for r in h["revisions"])
    today, before = datetime.now(UTC).date().isoformat(), yesterday.date().isoformat()
    assert rows == sorted([(before, "One", 6, 0), (before, "Two", 4, 0), (today, "One", 0, 2)])
    assert [(h["chapters"][p["chapter_id"]], p["added"], p["removed"]) for p in h["pending"]] == [("Two", 2, 0)]

    # a restored world shows the same days (the export carries each day's last version, docs/SPEC.md §20), and
    # nothing on the day it was restored: text newer than the last version is its start
    data = world.get(f"{W}/export").content
    world.post("/api/worlds/restore", files={"file": ("export.zip", data, "application/zip")})
    again = world.get("/api/worlds/coast-2/projects/book-one/word-history").json()
    assert sorted((r["at"][:10], again["chapters"][r["chapter_id"]], r["added"], r["removed"]) for r in again["revisions"]) == rows
    assert again["pending"] == []
    restored = {c["title"]: c["id"] for c in world.get("/api/worlds/coast-2/projects/book-one/chapters").json()["chapters"]}
    reasons = lambda t: [r["reason"] for r in world.get(f"/api/worlds/coast-2/chapters/{restored[t]}/revisions").json()]  # noqa: E731
    assert sorted(reasons("One")) == ["autosnap", "checkpoint"] and sorted(reasons("Two")) == ["autosnap", "start"]


def test_an_experiment_from_a_copy_starts_at_no_words(world: Client):
    one = chapter(world, "One", "original words here")
    exp = world.post(f"{W}/chapters/{one['id']}/experiments", json={"start": "copy"}).json()
    revs = world.get(f"{W}/chapters/{exp['id']}/revisions").json()
    assert [r["reason"] for r in revs] == ["start"]
    h = world.get(f"{P}/word-history").json()
    assert all(p["chapter_id"] != exp["id"] for p in h["pending"])


def test_conflict_copies_are_not_the_chapters_line(world: Client):
    ch = chapter(world, "One", "server text")
    world.post(f"{W}/chapters/{ch['id']}/revisions", json={"reason": "autosnap"})
    world.post(f"{W}/chapters/{ch['id']}/revisions", json={"reason": "conflict", "body": "a lot of other text here"})
    save(world, ch, "server text and more")
    world.post(f"{W}/chapters/{ch['id']}/revisions", json={"reason": "autosnap"})
    h = world.get(f"{P}/word-history").json()
    assert sorted((r["added"], r["removed"]) for r in h["revisions"]) == [(2, 0), (2, 0)]


# 11.6 a checkpoint of every chapter -------------------------------------------------------------------------------


def test_checkpoint_every_chapter_with_one_label(world: Client):
    a = chapter(world, "One", "a")
    b = chapter(world, "Two", "b")
    gone = chapter(world, "Three", "c")
    world.post(f"{W}/chapters/{gone['id']}/retire", json={})
    exp = world.post(f"{W}/chapters/{b['id']}/experiments", json={"start": "scratch"}).json()
    r = world.post(f"{P}/checkpoint", json={"label": " before the  polish "})
    assert r.json() == {"chapters": 3, "label": "before the polish"}
    for c in (a, b, exp):
        revs = world.get(f"{W}/chapters/{c['id']}/revisions").json()
        assert (revs[0]["reason"], revs[0]["label"]) == ("checkpoint", "before the polish")
    assert all(r["label"] != "before the polish" for r in world.get(f"{W}/chapters/{gone['id']}/revisions").json())


# 11.7 find and replace across chapters ----------------------------------------------------------------------------


def test_done_when_a_replace_previews_every_hit_leaves_the_unticked_checkpoints_and_undoes(world: Client):
    one = chapter(world, "One", "Varren waits. Varren's boat is late.\n%% Varren needs a reason")
    two = chapter(world, "Two", "Nobody here but varren and Varrens.")
    three = chapter(world, "Three", "Varren sleeps. Varrenhold is far.")
    gone = chapter(world, "Old", "Varren in the old opening.")
    world.post(f"{W}/chapters/{gone['id']}/retire", json={})

    found = world.post(f"{P}/find", json={"find": "Varren"}).json()
    # whole words and capitals by default: not "varren", not "Varrens", not "Varrenhold"; margin notes included
    assert found["total"] == 4
    assert [(c["title"], len(c["hits"])) for c in found["chapters"]] == [("One", 3), ("Three", 1)]
    hit = found["chapters"][0]["hits"][1]
    assert (hit["before"], hit["match"], hit["after"]) == ("Varren waits. ", "Varren", "'s boat is late.")
    loose = world.post(f"{P}/find", json={"find": "varren", "match_case": False, "whole_words": False}).json()
    assert loose["total"] == 7

    # untick two: the second hit in One and the one in Three
    chosen = [{"id": c["id"], "version": c["version"],
               "hits": [h["start"] for h in c["hits"]][::2] if c["title"] == "One" else []}
              for c in found["chapters"]]
    done = world.post(f"{P}/replace", json={"find": "Varren", "replace": "Varran", "chapters": chosen}).json()
    assert done["replaced"] == 2 and [c["title"] for c in done["chapters"]] == ["One"]
    body = world.get(f"{W}/chapters/{one['id']}").json()["body"]
    assert body == "Varran waits. Varren's boat is late.\n%% Varran needs a reason"
    assert world.get(f"{W}/chapters/{three['id']}").json()["body"] == "Varren sleeps. Varrenhold is far."
    revs = world.get(f"{W}/chapters/{one['id']}/revisions").json()
    assert (revs[0]["reason"], revs[0]["label"]) == ("checkpoint", 'Before replacing "Varren" with "Varran"')

    # Undo puts every chapter back (the replaced text is kept, as with any restore)
    undo = world.post(f"{P}/replace/undo", json={"chapters": [
        {"id": c["id"], "revision_id": c["revision_id"], "version": c["version"]} for c in done["chapters"]]}).json()
    assert [c["title"] for c in undo["restored"]] == ["One"] and undo["skipped"] == []
    assert world.get(f"{W}/chapters/{one['id']}").json()["body"].startswith("Varren waits. Varren's")
    assert world.get(f"{W}/chapters/{one['id']}/revisions").json()[0]["reason"] == "restore"
    assert two


def test_a_chapter_changed_since_the_preview_is_skipped_and_undo_skips_one_changed_since(world: Client):
    a = chapter(world, "One", "Varren.")
    b = chapter(world, "Two", "Varren too.")
    found = world.post(f"{P}/find", json={"find": "Varren", "replace": ""}).json()
    save(world, b, "Varren too, and more.")
    chosen = [{"id": c["id"], "version": c["version"], "hits": [h["start"] for h in c["hits"]]} for c in found["chapters"]]
    done = world.post(f"{P}/replace", json={"find": "Varren", "replace": "", "chapters": chosen}).json()
    assert done["replaced"] == 1 and done["label"] == 'Before deleting "Varren"'
    assert done["skipped"] == [{"id": b["id"], "title": "Two", "reason": "changed since the preview"}]
    assert world.get(f"{W}/chapters/{a['id']}").json()["body"] == "."
    save(world, a, "Written after the replace.")
    undo = world.post(f"{P}/replace/undo", json={"chapters": [
        {"id": c["id"], "revision_id": c["revision_id"], "version": c["version"]} for c in done["chapters"]]}).json()
    assert undo["restored"] == [] and undo["skipped"][0]["reason"] == "changed since the replace"


def test_find_across_the_world_in_story_order(world: Client):
    world.post(f"{W}/projects", json={"name": "Novella"})
    chapter(world, "Later", "Isolde.", project="novella")
    first = chapter(world, "First", "Isolde?")
    world.post(f"{W}/chapters/{first['id']}/experiments", json={"start": "copy", "title": "First, again"})
    found = world.post(f"{P}/find", json={"find": "Isolde", "scope": "world"}).json()
    assert [(c["project"], c["title"], c["state"]) for c in found["chapters"]] == [
        ("book-one", "First", "current"), ("book-one", "First, again", "experiment"), ("novella", "Later", "current")]
    assert len(world.post(f"{P}/find", json={"find": "Isolde"}).json()["chapters"]) == 2
