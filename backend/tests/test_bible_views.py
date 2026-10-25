"""Phase 11, more views of the bible (SPEC §12): the data behind the mentions strip, the family tree's inputs and its
loop check, entries across chapters, world and project entries, witnessed / gender / pronunciation, and labels and
values (suggestions, the Labels page, several values, expected labels and the third-use prompt)."""

from __future__ import annotations

import io
import uuid
import zipfile

import pytest
import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from .conftest import Client

W = "/api/worlds/lamp-coast"


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Lamp Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Ninefold"})
    signed_in.post(f"{W}/projects", json={"name": "The Salt Road"})
    return signed_in


def entity(c: Client, name: str, kind: str = "character", **extra) -> dict:
    r = c.post(f"{W}/entities", json={"name": name, "kind": kind, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def chapter(c: Client, title: str, body: str = "", project: str = "ninefold", **extra) -> dict:
    r = c.post(f"{W}/projects/{project}/chapters", json={"title": title, "body": body, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def patch_entity(c: Client, e: dict, **changes) -> dict:
    current = c.get(f"{W}/entities/{e['id']}").json()["entity"]
    r = c.patch(f"{W}/entities/{e['id']}", json={"base_version": current["version"], **changes})
    assert r.status_code == 200, r.text
    return r.json()


def fact(c: Client, e: dict, label: str, value: str = "", **extra) -> dict:
    r = c.post(f"{W}/entities/{e['id']}/facts", json={"label": label, "value": value, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def types(c: Client) -> dict[str, dict]:
    return {t["label"]: t for t in c.get(f"{W}/relation-types").json()}


def relate(c: Client, a: dict, label: str, b: dict, **extra) -> dict:
    r = c.post(f"{W}/relationships", json={"type_id": types(c)[label]["id"], "a_id": a["id"], "b_id": b["id"], **extra})
    assert r.status_code == 201, r.text
    return r.json()


def checks(c: Client) -> list[dict]:
    return c.get(f"{W}/checks").json()


# 12.1 the mentions strip: the timeline carries each chapter's point of view and its project's gap length -----------


def test_timeline_has_pov_and_gap_length(world: Client):
    isolde = entity(world, "Isolde")
    one = chapter(world, "One", "Isolde wakes.", pov_entity_id=isolde["id"])
    chapter(world, "Two", "Rain.", project="the-salt-road")
    assert world.patch(f"{W}/projects/the-salt-road", json={"gap_chapters": 3}).json()["gap_chapters"] == 3
    assert world.patch(f"{W}/projects/the-salt-road", json={"gap_chapters": 0}).status_code == 422
    timeline = world.get(f"{W}/timeline").json()
    assert [(c["title"], c["pov"], c["gap_chapters"]) for c in timeline] == [("One", isolde["id"], 5), ("Two", None, 3)]
    assert [p["gap_chapters"] for p in world.get(W).json()["projects"]] == [5, 3]
    # the entry page already has each chapter that names the entry, with a count
    mentions = world.get(f"{W}/entities/{isolde['id']}").json()["mentions"]
    assert [(m["source_id"], m["count"]) for m in mentions if m["source_table"] == "chapter"] == [(one["id"], 1)]


# 12.2 the family tree: the graph carries gender; an ancestor loop is a Continuity check --------------------------


def test_graph_nodes_carry_gender_and_level(world: Client):
    varren = entity(world, "Varren")
    patch_entity(world, varren, gender="male")
    entity(world, "Mirelle", project="the-salt-road")
    nodes = {n["name"]: n for n in world.get(f"{W}/graph").json()["nodes"]}
    assert (nodes["Varren"]["gender"], nodes["Varren"]["project"]) == ("male", None)
    assert (nodes["Mirelle"]["gender"], nodes["Mirelle"]["project"]) == (None, "the-salt-road")


def test_own_ancestor_is_a_continuity_check(world: Client):
    varren, oswin, mirelle = entity(world, "Varren"), entity(world, "Oswin"), entity(world, "Mirelle")
    relate(world, varren, "parent of", oswin)
    relate(world, oswin, "parent of", mirelle)
    assert not [c for c in checks(world) if c["rule"] == "own_ancestor"]
    # an added type reading the other way round ("son of" / "father of") counts as parenthood too
    t = world.post(f"{W}/relation-types", json={"a_kind": "character", "b_kind": "character", "label": "son of",
                                                "reverse_label": "father of"}).json()
    world.post(f"{W}/relationships", json={"type_id": t["id"], "a_id": varren["id"], "b_id": mirelle["id"]})
    loop = [c for c in checks(world) if c["rule"] == "own_ancestor"]
    assert len(loop) == 1
    assert "their own ancestor" in loop[0]["message"]
    assert {e["name"] for e in loop[0]["entities"]} == {"Varren", "Oswin", "Mirelle"}
    # nothing worked out is stored: the world still has exactly the three relationships recorded
    assert len(world.get(f"{W}/relationships").json()) == 3


# 12.3 entries across chapters ---------------------------------------------------------------------------------


def test_where_takes_kinds_entities_and_a_project(world: Client):
    varren, isolde = entity(world, "Varren"), entity(world, "Isolde")
    logbook, guild = entity(world, "the logbook", "object"), entity(world, "the Lamp Guild", "faction")
    quay = entity(world, "the Quay", "place")
    ferryman = entity(world, "Ferryman Ott", project="the-salt-road")
    one = chapter(world, "One", "Varren opened the logbook at the Quay.\n\nIsolde read the logbook twice. The logbook.",
                  pov_entity_id=isolde["id"])
    two = chapter(world, "Two", "The Lamp Guild met. Ferryman Ott rowed.")
    three = chapter(world, "Three", "Varren and the logbook again.", project="the-salt-road")
    world.put(f"{W}/chapters/{two['id']}/presence/{isolde['id']}", json={"place_id": quay["id"]})

    # today's grid: characters only, by first appearance, a place derived from the paragraph
    grid = world.get(f"{W}/where").json()
    assert [r["entity"]["name"] for r in grid["rows"]] == ["Varren", "Isolde", "Ferryman Ott"]
    assert grid["chapters"][0]["pov"]["name"] == "Isolde"
    rows = {r["entity"]["name"]: r for r in grid["rows"]}
    assert rows["Varren"]["cells"][one["id"]]["derived"]["name"] == "the Quay"
    assert rows["Isolde"]["cells"][two["id"]]["recorded"]["name"] == "the Quay"

    # chosen entries of any kind, with counts; places count who is recorded there
    ids = ",".join(x["id"] for x in (varren, isolde, logbook, guild))
    grid = world.get(f"{W}/where", params={"kinds": "", "entities": ids}).json()
    rows = {r["entity"]["name"]: r for r in grid["rows"]}
    assert list(rows) == ["Varren", "the logbook", "Isolde", "the Lamp Guild"]
    assert all(r["added"] for r in rows.values())
    assert rows["the logbook"]["cells"][one["id"]]["count"] == 3
    assert rows["the logbook"]["cells"][three["id"]]["count"] == 1
    assert rows["the Lamp Guild"]["cells"][two["id"]]["count"] == 1
    grid = world.get(f"{W}/where", params={"kinds": "place"}).json()
    quay_row = grid["rows"][0]
    assert quay_row["entity"]["name"] == "the Quay"
    assert [p["name"] for p in quay_row["cells"][two["id"]]["people"]] == ["Isolde"]

    # limited to a project: other projects' entries leave the kind rows, entries added by hand stay
    grid = world.get(f"{W}/where", params={"project": "ninefold"}).json()
    assert [r["entity"]["name"] for r in grid["rows"]] == ["Varren", "Isolde"]
    grid = world.get(f"{W}/where", params={"project": "ninefold", "entities": ferryman["id"]}).json()
    assert [r["entity"]["name"] for r in grid["rows"]] == ["Varren", "Isolde", "Ferryman Ott"]
    assert world.get(f"{W}/where", params={"entities": "nope"}).status_code == 422


# 12.4 world entries and project entries --------------------------------------------------------------------------


def test_levels(world: Client):
    salt = chapter(world, "Salt one", "Mirelle on the road.", project="the-salt-road")
    nine = chapter(world, "Nine one", "Nobody here.")
    # a new name made from a Salt Road chapter starts in its bible; made anywhere else, in the world
    mirelle = entity(world, "Mirelle", project="the-salt-road")
    assert mirelle["project"] == "the-salt-road"
    assert entity(world, "Varren")["project"] is None
    assert world.post(f"{W}/entities", json={"name": "X", "project": "nope"}).status_code == 422
    listed = {e["name"]: e for e in world.get(f"{W}/entities").json()}
    assert listed["Mirelle"]["named_in"] == ["the-salt-road"] and listed["Varren"]["named_in"] == []
    # named in a Ninefold chapter too: both books name her now
    cur = world.get(f"{W}/chapters/{nine['id']}").json()
    world.patch(f"{W}/chapters/{nine['id']}", json={"base_version": cur["version"], "body": "Mirelle came."})
    assert {e["name"]: e for e in world.get(f"{W}/entities").json()}["Mirelle"]["named_in"] == ["ninefold", "the-salt-road"]
    # Share with the world: one PATCH moves her up
    assert patch_entity(world, mirelle, project=None)["project"] is None
    assert patch_entity(world, mirelle, project="ninefold")["project"] == "ninefold"
    # the cards carry the level too (for the Archivist, the pickers and new entries)
    card = next(c for c in world.get(f"{W}/cards").json() if c["name"] == "Mirelle")
    assert card["project"] == "ninefold"
    assert salt["id"]


def test_a_world_with_one_project_keeps_everything_in_the_world(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Lamp Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Ninefold"})
    assert entity(signed_in, "Mirelle", project="ninefold")["project"] is None


def test_restore_keeps_levels_and_an_older_export_means_the_world(world: Client):
    entity(world, "Mirelle", project="the-salt-road")
    entity(world, "Varren")
    data = world.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    meta = yaml.safe_load(z.read("lamp-coast/Bible/Characters/Mirelle.md").decode().split("---\n")[1])
    assert meta["project"] == "the-salt-road"
    restored = world.post("/api/worlds/restore", files={"file": ("x.zip", data, "application/zip")}).json()
    levels = {e["name"]: e["project"] for e in world.get(f"/api/worlds/{restored['slug']}/entities").json()}
    assert levels == {"Mirelle": "the-salt-road", "Varren": None}

    # an export from before phase 11: no project:, no gap_chapters, no gender, no fact_labels
    old = io.BytesIO()
    with zipfile.ZipFile(old, "w") as out:
        for name in z.namelist():
            body = z.read(name).decode()
            body = body.replace("project: the-salt-road\n", "").replace("gap_chapters: 5\n", "")
            out.writestr(name, body)
    restored = world.post("/api/worlds/restore", files={"file": ("x.zip", old.getvalue(), "application/zip")}).json()
    assert all(p["gap_chapters"] == 5 for p in restored["projects"])
    assert {e["project"] for e in world.get(f"/api/worlds/{restored['slug']}/entities").json()} == {None}


# 12.5 witnessed, gender, pronunciation ---------------------------------------------------------------------------


def test_witnessed_reads_back_from_the_event(world: Client):
    varren = entity(world, "Varren")
    burning = entity(world, "the Burning of the Quay", "event")
    t = types(world)["witnessed"]
    assert (t["a_kind"], t["b_kind"], t["reverse_label"]) == ("character", "event", "witnessed by")
    relate(world, varren, "witnessed", burning)
    rels = world.get(f"{W}/entities/{burning['id']}").json()["relationships"]
    assert [(r["reads"], r["other"]["name"]) for r in rels] == [("witnessed by", "Varren")]


def test_gender_is_a_field_on_characters(world: Client):
    varren, isolde = entity(world, "Varren"), entity(world, "Isolde")
    assert varren["gender"] is None
    assert patch_entity(world, varren, gender="male")["gender"] == "male"
    cards = {c["name"]: c for c in world.get(f"{W}/cards").json()}
    assert (cards["Varren"]["gender"], cards["Isolde"]["gender"]) == ("male", None)
    current = world.get(f"{W}/entities/{varren['id']}").json()["entity"]
    assert world.patch(f"{W}/entities/{varren['id']}", json={"base_version": current["version"],
                                                             "gender": "other"}).status_code == 422
    # back to not set; and a kind changed away from character keeps the value
    patch_entity(world, isolde, gender="female")
    assert patch_entity(world, isolde, kind="other")["gender"] == "female"
    assert patch_entity(world, varren, gender=None)["gender"] is None
    # never a suggested fact: pronouns is, for nuance
    suggestions = world.get(f"{W}/fact-suggestions").json()
    assert "gender" not in suggestions["character"]["labels"] and "pronouns" in suggestions["character"]["labels"]


def test_gender_round_trips_through_export(world: Client):
    varren = entity(world, "Varren")
    entity(world, "Isolde")
    patch_entity(world, varren, gender="nonbinary")
    data = world.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    assert yaml.safe_load(z.read("lamp-coast/Bible/Characters/Varren.md").decode().split("---\n")[1])["gender"] == "nonbinary"
    assert "gender" not in yaml.safe_load(z.read("lamp-coast/Bible/Characters/Isolde.md").decode().split("---\n")[1])
    restored = world.post("/api/worlds/restore", files={"file": ("x.zip", data, "application/zip")}).json()
    genders = {e["name"]: e["gender"] for e in world.get(f"/api/worlds/{restored['slug']}/entities").json()}
    assert genders == {"Varren": "nonbinary", "Isolde": None}


def test_suggested_facts_reach_every_world(world: Client):
    s = world.get(f"{W}/fact-suggestions").json()
    assert {"pronunciation", "pronouns"} <= set(s["character"]["labels"])
    assert "pronunciation" in s["place"]["labels"]
    assert "type" in s["event"]["labels"]


# 12.6.1 value suggestions ---------------------------------------------------------------------------------------


def test_value_suggestions_are_per_label_and_kind(world: Client):
    for i, value in enumerate(["Festival", "festival", "Festival ", "FESTIVAL", "Battle", "Battle", "Wedding"]):
        fact(world, entity(world, f"Event {i}", "event"), "type", value)
    for i in range(3):
        fact(world, entity(world, f"Town {i}", "place"), "Type", "City")
    s = world.get(f"{W}/fact-suggestions").json()
    # the values in use (the starting values of phase 12 follow them, without counts)
    used = lambda xs: [x for x in xs if x["count"]]  # noqa: E731
    assert used(s["event"]["values"]["type"]) == [{"value": "Festival", "count": 4}, {"value": "Battle", "count": 2},
                                                  {"value": "Wedding", "count": 1}]
    # places' types are their own
    assert used(s["place"]["values"]["type"]) == [{"value": "City", "count": 3}]
    # a label on three or more entries is common, and listed first
    assert s["event"]["common"] == ["type"] and s["event"]["labels"][0] == "type"
    assert s["place"]["labels"][0] == "Type"


# 12.6.3 the Labels page ------------------------------------------------------------------------------------------


def _labels(c: Client) -> dict[str, dict[str, dict]]:
    return {k["kind"]: {x["label"]: x for x in k["labels"]} for k in c.get(f"{W}/labels").json()["kinds"]}


def test_labels_page_rename_merge_and_undo(world: Client):
    events = [entity(world, f"Event {i}", "event") for i in range(6)]
    for e, v in zip(events, ["Festival", "Festival", "Feast", "feast", "Battle", "Battle"]):
        fact(world, e, "type", v)
    towns = [entity(world, f"Town {i}", "place") for i in range(3)]
    for t in towns:
        fact(world, t, "type", "City")
    place_feast = fact(world, entity(world, "Feast Hall", "place"), "type", "Feast")

    labels = _labels(world)
    assert [(v["value"], v["count"]) for v in labels["event"]["type"]["values"]] == [
        ("Battle", 2), ("Feast", 2), ("Festival", 2)]
    assert labels["event"]["type"]["count"] == 6
    assert [(v["value"], v["count"]) for v in labels["place"]["type"]["values"]] == [("City", 3), ("Feast", 1)]
    assert {e["name"] for e in labels["event"]["type"]["values"][1]["entries"]} == {"Event 2", "Event 3"}

    # merge Feast into Festival for events: only the events' facts change
    r = world.post(f"{W}/labels/values/rename", json={"kind": "event", "label": "type", "old": "feast", "new": "Festival"})
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["message"] == "Changed 2 facts on 2 events."
    labels = _labels(world)
    assert [(v["value"], v["count"]) for v in labels["event"]["type"]["values"]] == [("Festival", 4), ("Battle", 2)]
    assert [(v["value"], v["count"]) for v in labels["place"]["type"]["values"]] == [("City", 3), ("Feast", 1)]
    # a page open elsewhere gets the usual conflict instead of overwriting
    stale = world.get(f"{W}/entities/{events[2]['id']}").json()["facts"][0]
    assert world.patch(f"{W}/facts/{stale['id']}", json={"base_version": stale["version"] - 1, "value": "x"}).status_code == 409

    # Undo puts them back, except on a fact that changed since
    world.patch(f"{W}/facts/{stale['id']}", json={"base_version": stale["version"], "value": "Festival day"})
    undone = world.post(f"{W}/labels/undo", json={"changes": done["changes"], "rows": done["rows"]}).json()
    assert undone == {"restored": 1, "skipped": 1}
    values = {v["value"] for v in _labels(world)["event"]["type"]["values"]}
    assert values == {"Festival", "feast", "Festival day", "Battle"}
    assert world.get(f"{W}/entities/{towns[0]['id']}").json()["facts"][0]["value"] == "City"
    assert place_feast["value"] == "Feast"


def test_rename_a_label_merges_and_carries_its_switches(world: Client):
    v, i = entity(world, "Varren"), entity(world, "Isolde")
    fact(world, v, "colour of eyes", "green")
    fact(world, i, "colour of eyes", "grey")
    fact(world, i, "eye colour", "blue")
    fact(world, entity(world, "Old Harbour", "place"), "colour of eyes", "n/a")
    world.put(f"{W}/labels/character/colour of eyes", json={"several": True})
    r = world.post(f"{W}/labels/rename", json={"kind": "character", "old": "Colour of eyes", "new": "eye colour"}).json()
    assert r["message"] == "Changed 2 facts on 2 characters."
    labels = _labels(world)
    assert "colour of eyes" not in labels["character"]
    # Isolde had both: she keeps both facts
    assert labels["character"]["eye colour"]["count"] == 2 and labels["character"]["eye colour"]["several"]
    assert len(world.get(f"{W}/entities/{i['id']}").json()["facts"]) == 2
    # the place's label is its own, unless the tick extends the rename
    assert "colour of eyes" in labels["place"]
    r = world.post(f"{W}/labels/rename", json={"kind": "character", "old": "eye colour", "new": "eyes",
                                              "everywhere": True}).json()
    assert r["message"] == "Changed 3 facts on 2 characters."
    r = world.post(f"{W}/labels/rename", json={"kind": "place", "old": "colour of eyes", "new": "eyes",
                                              "everywhere": True}).json()
    assert r["message"] == "Changed 1 fact on 1 place."
    labels = _labels(world)
    assert set(labels["character"]) == {"eyes"} and set(labels["place"]) == {"eyes"}


# 12.6.4 labels that hold several values ---------------------------------------------------------------------------


def test_several_values_are_not_a_conflict(world: Client):
    varren = entity(world, "Varren")
    one = chapter(world, "One", "Varren.")
    fact(world, varren, "eye colour", "green", from_chapter_id=one["id"])
    fact(world, varren, "eye colour", "red", from_chapter_id=one["id"])
    assert [c["rule"] for c in checks(world)] == ["fact_conflict"]
    conflict = checks(world)[0]
    # the finding names its label and kind, for "Both are true (several values)"
    assert (conflict["label"], conflict["kind"]) == ("eye colour", "character")
    world.put(f"{W}/labels/character/{conflict['label']}", json={"several": True})
    assert checks(world) == []
    world.put(f"{W}/labels/character/Eye Colour", json={"several": False})
    assert [c["rule"] for c in checks(world)] == ["fact_conflict"]


# 12.6.5 suggestions that grow with use, and expected labels -------------------------------------------------------


def test_third_use_prompt_is_asked_once(world: Client):
    chars = [entity(world, n) for n in ("Varren", "Isolde", "Oswin", "Mirelle", "Seyla")]
    assert fact(world, chars[0], "eye colour", "green")["prompt"] is None
    assert fact(world, chars[1], "eye colour", "grey")["prompt"] is None
    # a second fact with the label on the same entry doesn't bring it to more entries
    assert fact(world, chars[1], "Eye colour", "blue")["prompt"] is None
    third = fact(world, chars[2], "eye colour", "brown")
    assert third["prompt"] == {"kind": "character", "label": "eye colour", "count": 3}
    # shown (or ignored) once: a fourth doesn't ask again, and the switch says it was asked
    assert fact(world, chars[3], "eye colour", "green")["prompt"] is None
    assert _labels(world)["character"]["eye colour"]["asked"] is True
    # no finding anywhere until it is expected
    assert _labels(world)["character"]["eye colour"]["without"] == []
    world.put(f"{W}/labels/character/eye colour", json={"expected": True})
    labels = _labels(world)["character"]["eye colour"]
    assert labels["expected"] and [e["name"] for e in labels["without"]] == ["Seyla"]
    # "Not for this one" is a resolution keyed by entry and label
    world.put(f"{W}/resolutions", json={"rule": "missing_label", "key": f"{chars[4]['id']}:eye colour",
                                        "outcome": "intentional"})
    assert _labels(world)["character"]["eye colour"]["without"] == [
        {"id": chars[4]["id"], "name": "Seyla", "kind": "character", "resolved": True}]
    # never asked for an expected label
    fact(world, entity(world, "Town", "place"), "type", "city")
    world.put(f"{W}/labels/place/type", json={"expected": True})
    fact(world, entity(world, "Town 2", "place"), "type", "city")
    assert fact(world, entity(world, "Town 3", "place"), "type", "city")["prompt"] is None


def test_existing_world_gets_witnessed_from_the_migration(db_url: str):
    """Upgrade a world made before phase 11: the data migration adds "witnessed" at the end of its character–event
    types, unless it already has one reading that way."""
    from alembic import command
    from alembic.config import Config

    from quarry.app import PKG

    base = make_url(db_url)
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    name = "quarry_test_upgrade"
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    cfg = Config()
    cfg.set_main_option("script_location", str(PKG / "migrations"))
    cfg.attributes["connection_url"] = url
    command.upgrade(cfg, "0008")
    e = create_engine(url)
    user, plain, has = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with e.begin() as c:
        c.execute(text("INSERT INTO users (id, display_name) VALUES (:u, 'W')"), {"u": user})
        for wid, slug in ((plain, "plain"), (has, "has")):
            c.execute(text("INSERT INTO worlds (id, name, slug, created_by, updated_by) VALUES (:w, :s, :s, :u, :u)"),
                      {"w": wid, "s": slug, "u": user})
        rows = [(plain, "character", "character", "parent of", "child of", 0),
                (plain, "character", "event", "attended", "attended by", 1),
                (plain, "place", "place", "inside", "contains", 2),
                (has, "event", "character", "Witnessed By", "WITNESSED", 0)]
        for wid, a, b, label, reverse, pos in rows:
            c.execute(text("INSERT INTO relation_types (id, world_id, a_kind, b_kind, label, reverse_label, position) "
                           "VALUES (:id, :w, :a, :b, :l, :r, :p)"),
                      {"id": uuid.uuid4(), "w": wid, "a": a, "b": b, "l": label, "r": reverse, "p": pos})
    # up to phase 11 (phase 12 adds more types after it)
    command.upgrade(cfg, "0009")
    with e.connect() as c:
        def listed(wid):  # type: ignore[no-untyped-def]
            return [tuple(r) for r in c.execute(text(
                "SELECT label, a_kind, b_kind FROM relation_types WHERE world_id = :w ORDER BY position"), {"w": wid})]
        assert listed(plain) == [("parent of", "character", "character"), ("attended", "character", "event"),
                                 ("witnessed", "character", "event"), ("inside", "place", "place")]
        assert listed(has) == [("Witnessed By", "event", "character")]
        assert c.execute(text("SELECT count(*) FROM projects")).scalar() == 0
    e.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def test_demo_world_shows_phase_eleven(signed_in: Client):
    world = signed_in.post("/api/worlds/demo").json()
    D = f"/api/worlds/{world['slug']}"
    entities = {e["name"]: e for e in signed_in.get(f"{D}/entities").json()}
    # a family of three generations, gender set for some of them
    assert entities["Tamsin Vey"]["gender"] == "female" and entities["Corin Dray"]["gender"] is None
    rels = {(r["a"]["name"], r["label"], r["b"]["name"]) for r in signed_in.get(f"{D}/relationships").json()}
    assert {("Agathe Vey", "parent of", "Oskar Vey"), ("Agathe Vey", "parent of", "Linnet Dray"),
            ("Linnet Dray", "parent of", "Corin Dray"), ("Oskar Vey", "parent of", "Tamsin Vey"),
            ("Mara Vey", "married to", "Oskar Vey"), ("Brother Cade", "witnessed", "The Flood of Lanterns")} <= rels
    # an entry in each book's own bible
    assert entities["Corin Dray"]["project"] == "ash-season"
    assert entities["The Gatehouse"]["project"] == "the-ferrymans-daughter"
    assert entities["Corin Dray"]["named_in"] == ["ash-season"]
    # a pronunciation, events with a type, a label with several values and one expected
    tamsin = signed_in.get(f"{D}/entities/{entities['Tamsin Vey']['id']}").json()
    assert ("pronunciation", "TAM-zin VAY") in {(f["label"], f["value"]) for f in tamsin["facts"]}
    labels = {k["kind"]: {x["label"]: x for x in k["labels"]} for k in signed_in.get(f"{D}/labels").json()["kinds"]}
    assert labels["event"]["type"]["expected"] and [e["name"] for e in labels["event"]["type"]["without"]] == [
        "The Mountain Fires"]
    assert labels["character"]["languages"]["several"]
    # the planted conflict (Ilse's eyes) stays; Hesper's two languages are not one
    conflicts = [c["message"] for c in signed_in.get(f"{D}/checks").json() if c["rule"] == "fact_conflict"]
    assert any("Ilse" in m for m in conflicts) and not any("Hesper" in m for m in conflicts)
    assert [p["gap_chapters"] for p in world["projects"]] == [3, 5]
