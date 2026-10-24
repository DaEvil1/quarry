"""Phase 12c, species, roles and vocabulary (SPEC §13.3–§13.5): the ninth kind and its starting types, describing a
species with suggested facts and values, the cards carrying what a character is, roles on relationships of types that
have one (suggestions, a promotion as a new span, the Labels page's roles), the one-at-a-time check and its fix, the
new starting types (possesses, ancestor of, the directions), the migration for existing worlds, and export/restore."""

from __future__ import annotations

import io
import uuid
import zipfile

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from .conftest import Client
from .test_bible_views import W, chapter, checks, entity, fact, relate, types, world  # noqa: F401


def test_a_new_world_starts_with_the_species_types(world: Client):
    t = types(world)
    assert (t["is a"]["a_kind"], t["is a"]["b_kind"], t["is a"]["reverse_label"]) == ("character", "species", "includes")
    assert t["appears as"]["reverse_label"] == "the guise of"
    assert t["native to"]["reverse_label"] == "home of"
    labels = {(x["a_kind"], x["b_kind"], x["label"], x["reverse_label"]) for x in world.get(f"{W}/relation-types").json()}
    assert {("species", "species", "descended from", "ancestor of"), ("species", "species", "related to", None),
            ("species", "species", "preys on", "prey of"), ("species", "place", "native to", "home of"),
            ("culture", "species", "culture of", "has culture"), ("faction", "species", "made up of", "makes up"),
            ("character", "character", "possesses", "possessed by"),
            ("character", "character", "ancestor of", "descendant of"),
            ("place", "place", "north of", "south of"), ("place", "place", "east of", "west of")} <= labels
    # "has a role" starts on for member of, leads, serves and works at, and nothing else
    assert {x["label"] for x in world.get(f"{W}/relation-types").json() if x["has_role"]} == {
        "member of", "leads", "serves", "works at"}


def test_species_is_a_kind_described_with_facts(world: Client):
    selkie = entity(world, "selkie", "species")
    assert selkie["kind"] == "species"
    assert [e["name"] for e in world.get(f"{W}/entities?kind=species").json()] == ["selkie"]
    sug = world.get(f"{W}/fact-suggestions").json()
    assert sug["species"]["labels"][:7] == ["form", "sapient", "size", "lifespan", "habitat", "diet", "reproduction"]
    # name meaning on every kind; a term keeps its meaning too
    assert all("name meaning" in sug[k]["labels"] for k in sug)
    assert "meaning" in sug["term"]["labels"]
    # starting values, after the values in use and without counts
    fact(world, selkie, "form", "aquatic")
    forms = world.get(f"{W}/fact-suggestions").json()["species"]["values"]["form"]
    assert forms[0] == {"value": "aquatic", "count": 1}
    assert {"value": "humanoid", "count": 0} in forms and sum(v["value"] == "aquatic" for v in forms) == 1
    places = world.get(f"{W}/fact-suggestions").json()["place"]["values"]["type"]
    assert {"value": "plane", "count": 0} in places and {"value": "reef", "count": 0} in places
    events = world.get(f"{W}/fact-suggestions").json()["event"]["values"]["type"]
    assert [v["value"] for v in events][:3] == ["era", "war", "battle"]
    # a species label can be expected on every species, like any label
    assert world.put(f"{W}/labels/species/lifespan", json={"expected": True}).json()["expected"]
    page = world.get(f"{W}/labels").json()
    assert [x["label"] for x in next(k for k in page["kinds"] if k["kind"] == "species")["labels"]] == ["form", "lifespan"]


def test_cards_carry_what_a_character_is(world: Client):
    one, three, nine = chapter(world, "One"), chapter(world, "Three"), chapter(world, "Nine")
    seyla, selkie, human = entity(world, "Seyla"), entity(world, "selkie", "species"), entity(world, "human", "species")
    # many relationships first, so the species ones come after the card's first sixteen
    for i in range(18):
        relate(world, seyla, "knows", entity(world, f"Friend {i}"))
    relate(world, seyla, "is a", selkie)
    relate(world, seyla, "appears as", human, from_chapter_id=three["id"], until_chapter_id=nine["id"])
    card = next(c for c in world.get(f"{W}/cards").json() if c["name"] == "Seyla")
    kinds = {r["label"]: r for r in card["relations"] if r["other"]["kind"] == "species"}
    assert kinds["is a"]["other"]["name"] == "selkie"
    assert (kinds["appears as"]["from"], kinds["appears as"]["until"]) == (three["id"], nine["id"])
    del one


def test_roles_on_relationships(world: Client):
    guild = entity(world, "The Lamp Guild", "faction")
    varren, isolde = entity(world, "Varren"), entity(world, "Isolde")
    r = relate(world, varren, "member of", guild, role="  Captain ")
    assert (r["role"], r["has_role"]) == ("Captain", True)
    relate(world, isolde, "member of", guild, role="captain")
    # a type without a role ignores one
    assert relate(world, varren, "friend of", isolde, role="Captain")["role"] is None
    # shown from both sides
    rels = world.get(f"{W}/entities/{guild['id']}").json()["relationships"]
    assert {(x["reads"], x["other"]["name"], x["role"]) for x in rels} == {("has member", "Varren", "Captain"),
                                                                           ("has member", "Isolde", "captain")}
    # suggestions: per type, most used first with counts, and the groups they are used in
    sug = world.get(f"{W}/role-suggestions").json()[types(world)["member of"]["id"]]
    assert sug == [{"role": "Captain", "count": 2, "groups": [guild["id"]]}]
    # the card carries the role
    card = next(c for c in world.get(f"{W}/cards").json() if c["name"] == "Varren")
    assert any(x.get("role") == "Captain" for x in card["relations"])
    # editing and clearing it
    r = world.patch(f"{W}/relationships/{r['id']}", json={"base_version": r["version"], "role": "Treasurer"}).json()
    assert r["role"] == "Treasurer"
    assert world.patch(f"{W}/relationships/{r['id']}", json={"base_version": r["version"], "role": ""}).json()["role"] is None


def test_change_role_from_here_is_a_new_span(world: Client):
    one, two, three = chapter(world, "One"), chapter(world, "Two"), chapter(world, "Three")
    guild, varren = entity(world, "The Lamp Guild", "faction"), entity(world, "Varren")
    r = relate(world, varren, "member of", guild, role="Mate")
    out = world.post(f"{W}/relationships/{r['id']}/change-role",
                     json={"base_version": r["version"], "role": "Captain", "from_chapter_id": three["id"]})
    assert out.status_code == 201, out.text
    ended, started = out.json()["ended"], out.json()["started"]
    assert (ended["role"], ended["from_chapter_id"], ended["until_chapter_id"]) == ("Mate", None, two["id"])
    assert (started["role"], started["from_chapter_id"], started["until_chapter_id"]) == ("Captain", three["id"], None)
    # a stale version is refused
    assert world.post(f"{W}/relationships/{r['id']}/change-role",
                      json={"base_version": r["version"], "role": "Cook", "from_chapter_id": one["id"]}).status_code == 409
    del one


def test_one_at_a_time_role_clash_and_its_fix(world: Client):
    chs = [chapter(world, f"Chapter {i}") for i in range(1, 8)]
    guild, varren, isolde = entity(world, "The Lamp Guild", "faction"), entity(world, "Varren"), entity(world, "Isolde")
    v = relate(world, varren, "member of", guild, role="Captain", until_chapter_id=chs[3]["id"])
    i = relate(world, isolde, "member of", guild, role="Captain", from_chapter_id=chs[4]["id"])
    clash = lambda: [c for c in checks(world) if c["rule"] == "role_clash"]  # noqa: E731
    # off by default: no finding even when they overlap
    v = world.patch(f"{W}/relationships/{v['id']}", json={"base_version": v["version"],
                                                           "until_chapter_id": chs[5]["id"]}).json()
    assert clash() == []
    assert world.put(f"{W}/labels/roles/captain", json={"one_at_a_time": True}).json() == {
        "role": "captain", "one_at_a_time": True}
    [c] = clash()
    assert c["message"] == ("The Lamp Guild has two Captains in “Chapter 5”: Varren (from the start) and Isolde "
                            "(from “Chapter 5”).")
    assert c["chapter"]["title"] == "Chapter 5"
    assert c["end"]["id"] == v["id"] and c["before"]["id"] == i["id"]
    # planned and rumoured roles don't clash
    world.patch(f"{W}/relationships/{i['id']}", json={"base_version": i["version"], "standing": "planned"})
    assert clash() == []
    i = world.get(f"{W}/relationships").json()
    i = next(x for x in i if x["a"]["name"] == "Isolde")
    world.patch(f"{W}/relationships/{i['id']}", json={"base_version": i["version"], "standing": "canon"})
    # End Varren's before Isolde's: a handover, which is not a clash
    fixed = world.post(f"{W}/relationships/{v['id']}/end-before/{i['id']}").json()
    assert fixed["until_chapter_id"] == chs[4]["id"]
    assert clash() == []
    # the switch is on the Labels page's roles, with counts
    roles = world.get(f"{W}/labels").json()["roles"]
    assert roles == [{"role": "Captain", "count": 2, "one_at_a_time": True, "types": ["member of"],
                      "groups": [{"id": guild["id"], "name": "The Lamp Guild", "kind": "faction"}]}]


def test_rename_and_merge_roles_with_undo(world: Client):
    guild = entity(world, "The Lamp Guild", "faction")
    a = relate(world, entity(world, "Varren"), "member of", guild, role="Capt.")
    relate(world, entity(world, "Isolde"), "member of", guild, role="Captain")
    world.put(f"{W}/labels/roles/Capt.", json={"one_at_a_time": True})
    done = world.post(f"{W}/labels/roles/rename", json={"old": "capt.", "new": "Captain"}).json()
    assert done["message"] == "Changed 1 relationship."
    roles = world.get(f"{W}/labels").json()["roles"]
    # merged, and the merged role keeps the switch
    assert [(r["role"], r["count"], r["one_at_a_time"]) for r in roles] == [("Captain", 2, True)]
    undone = world.post(f"{W}/labels/roles/undo", json=done).json()
    assert undone == {"restored": 1, "skipped": 0}
    rel = next(r for r in world.get(f"{W}/relationships").json() if r["id"] == a["id"])
    assert rel["role"] == "Capt."


def test_ancestor_of_counts_for_their_own_ancestor(world: Client):
    a, b = entity(world, "Mirelle"), entity(world, "Old Mirelle")
    relate(world, b, "ancestor of", a)
    relate(world, a, "parent of", b)
    found = [c for c in checks(world) if c["rule"] == "own_ancestor"]
    assert len(found) == 1


def test_export_and_restore_keep_species_and_roles(world: Client):
    guild, varren, selkie = entity(world, "The Lamp Guild", "faction"), entity(world, "Varren"), entity(world, "selkie", "species")
    relate(world, varren, "member of", guild, role="Captain")
    relate(world, varren, "is a", selkie)
    world.put(f"{W}/labels/roles/Captain", json={"one_at_a_time": True})
    t = types(world)["is a"]
    world.patch(f"{W}/relation-types/{t['id']}", json={"has_role": True})
    data = world.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    assert "lamp-coast/Bible/Species/selkie.md" in z.namelist()
    wmeta = yaml.safe_load(z.read("lamp-coast/world.md").decode().split("---\n")[1])
    assert wmeta["roles"] == [{"role": "Captain", "one_at_a_time": True}]
    r = world.post("/api/worlds/restore", files={"file": ("w.zip", data, "application/zip")})
    assert r.status_code == 201, r.text
    R = f"/api/worlds/{r.json()['slug']}"
    rels = {(x["a"]["name"], x["label"], x["b"]["name"], x["role"]) for x in world.get(f"{R}/relationships").json()}
    assert {("Varren", "member of", "The Lamp Guild", "Captain"), ("Varren", "is a", "selkie", None)} <= rels
    assert next(x for x in world.get(f"{R}/relation-types").json() if x["label"] == "is a")["has_role"]
    assert world.get(f"{R}/labels").json()["roles"][0]["one_at_a_time"]
    assert next(e for e in world.get(f"{R}/entities").json() if e["name"] == "selkie")["kind"] == "species"


def test_an_older_export_gets_species_types_and_roles_by_label(world: Client):
    """An export from before phase 12: its own vocabulary is kept, with the species types added (the kind didn't
    exist) and "has a role" by label."""
    data = world.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    files = {n: z.read(n).decode() for n in z.namelist()}
    meta = yaml.safe_load(files["lamp-coast/world.md"].split("---\n")[1])
    meta["relation_types"] = [{"a": "character", "b": "faction", "label": "Member Of", "reverse": "has member"},
                              {"a": "culture", "b": "place", "label": "native to", "reverse": "home of"},
                              {"a": "character", "b": "character", "label": "friend of", "reverse": None}]
    meta.pop("roles")
    files["lamp-coast/world.md"] = "---\n" + yaml.safe_dump(meta) + "---\n\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as out:
        for n, t in files.items():
            out.writestr(n, t)
    r = world.post("/api/worlds/restore", files={"file": ("w.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 201, r.text
    listed = world.get(f"/api/worlds/{r.json()['slug']}/relation-types").json()
    assert [(x["label"], x["has_role"]) for x in listed][:3] == [("Member Of", True), ("native to", False),
                                                                  ("friend of", False)]
    assert {(x["a_kind"], x["b_kind"], x["label"]) for x in listed[3:]} == {
        ("character", "species", "is a"), ("character", "species", "appears as"),
        ("species", "species", "descended from"), ("species", "species", "related to"),
        ("species", "species", "preys on"), ("species", "place", "native to"), ("culture", "species", "culture of"),
        ("faction", "species", "made up of")}
    # no possesses or ancestor of: Restore keeps an export's own vocabulary
    assert not any(x["label"] == "possesses" for x in listed)


def test_existing_world_gets_the_new_types_from_the_migration(db_url: str):
    """Upgrade a world made before phase 12: each new type goes at the end of its pair, unless the world has one
    reading the same; "has a role" goes on by label."""
    from alembic import command
    from alembic.config import Config

    from quarry.app import PKG

    base = make_url(db_url)
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    name = "quarry_test_upgrade12"
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = base.set(database=name).render_as_string(hide_password=False)
    cfg = Config()
    cfg.set_main_option("script_location", str(PKG / "migrations"))
    cfg.attributes["connection_url"] = url
    command.upgrade(cfg, "0009")
    e = create_engine(url)
    user, wid = uuid.uuid4(), uuid.uuid4()
    with e.begin() as c:
        c.execute(text("INSERT INTO users (id, display_name) VALUES (:u, 'W')"), {"u": user})
        c.execute(text("INSERT INTO worlds (id, name, slug, created_by, updated_by) VALUES (:w, 'Old', 'old', :u, :u)"),
                  {"w": wid, "u": user})
        rows = [("character", "character", "parent of", "child of"), ("character", "character", "Possessed By", None),
                ("character", "faction", "MEMBER OF", "has member"), ("place", "place", "inside", "contains"),
                ("faction", "place", "controls", "controlled by")]
        for i, (a, b, label, reverse) in enumerate(rows):
            c.execute(text("INSERT INTO relation_types (id, world_id, a_kind, b_kind, label, reverse_label, position) "
                           "VALUES (:id, :w, :a, :b, :l, :r, :p)"),
                      {"id": uuid.uuid4(), "w": wid, "a": a, "b": b, "l": label, "r": reverse, "p": i})
    command.upgrade(cfg, "head")
    with e.connect() as c:
        listed = [tuple(r) for r in c.execute(text(
            "SELECT label, a_kind, b_kind, has_role FROM relation_types WHERE world_id = :w ORDER BY position"),
            {"w": wid})]
    assert listed[:7] == [("parent of", "character", "character", False),
                          ("Possessed By", "character", "character", False),
                          ("ancestor of", "character", "character", False),
                          ("MEMBER OF", "character", "faction", True),
                          ("inside", "place", "place", False), ("north of", "place", "place", False),
                          ("east of", "place", "place", False)]
    assert listed[7] == ("controls", "faction", "place", False)
    assert [x[0] for x in listed[8:]] == ["is a", "appears as", "descended from", "related to", "preys on",
                                          "native to", "culture of", "made up of"]
    e.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def test_demo_world_shows_species_roles_and_an_ancestor(signed_in: Client):
    world = signed_in.post("/api/worlds/demo").json()
    D = f"/api/worlds/{world['slug']}"
    entities = {e["name"]: e for e in signed_in.get(f"{D}/entities").json()}
    assert {n for n, e in entities.items() if e["kind"] == "species"} == {"human", "dog", "marsh-wight"}
    rels = {(r["a"]["name"], r["label"], r["b"]["name"]) for r in signed_in.get(f"{D}/relationships").json()}
    assert {("Brother Cade", "is a", "marsh-wight"), ("Brother Cade", "appears as", "human"),
            ("marsh-wight", "native to", "The Ninefold Delta"), ("Moss", "is a", "dog"),
            ("Wenna the Ferrywoman", "ancestor of", "Agathe Vey")} <= rels
    [clash] = [c for c in signed_in.get(f"{D}/checks").json() if c["rule"] == "role_clash"]
    assert clash["message"] == ("The River Wardens has two Warden-Captains in “The Locks”: Ilse Marrow (from the start) "
                                "and Harl Brenner (from “The Locks”).")
