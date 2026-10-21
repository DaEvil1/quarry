"""Creating, renaming and ordering worlds and projects, and keeping them to their members."""

from __future__ import annotations

import uuid

from .conftest import Client


def test_create_world_and_projects(signed_in: Client):
    r = signed_in.post("/api/worlds", json={"name": "  The   Grey Coast "})
    assert r.status_code == 201, r.text
    w = r.json()
    assert (w["name"], w["slug"], w["role"], w["projects"]) == ("The Grey Coast", "the-grey-coast", "owner", [])

    a = signed_in.post("/api/worlds/the-grey-coast/projects", json={"name": "First Light"}).json()
    b = signed_in.post("/api/worlds/the-grey-coast/projects", json={"name": "Ebb", "kind": "novella"}).json()
    assert (a["slug"], a["kind"], a["position"]) == ("first-light", "novel", 0)
    assert (b["slug"], b["kind"], b["position"]) == ("ebb", "novella", 1)

    me = signed_in.get("/api/me").json()
    assert [p["name"] for p in me["worlds"][0]["projects"]] == ["First Light", "Ebb"]


def test_slugs_are_unique_and_ascii(signed_in: Client):
    one = signed_in.post("/api/worlds", json={"name": "Ærø Øst"}).json()
    two = signed_in.post("/api/worlds", json={"name": "Aero Ost"}).json()
    three = signed_in.post("/api/worlds", json={"name": "!!!"}).json()
    assert (one["slug"], two["slug"]) == ("aero-ost", "aero-ost-2")
    assert three["slug"] == "world"
    p1 = signed_in.post(f"/api/worlds/{three['slug']}/projects", json={"name": "Book"}).json()
    p2 = signed_in.post(f"/api/worlds/{three['slug']}/projects", json={"name": "Book"}).json()
    assert (p1["slug"], p2["slug"]) == ("book", "book-2")


def test_rename_world_and_change_its_address(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Draft World"})
    signed_in.post("/api/worlds", json={"name": "Taken"})
    r = signed_in.patch("/api/worlds/draft-world", json={"name": "Final World", "slug": "final"})
    assert r.json()["name"] == "Final World" and r.json()["slug"] == "final"
    assert signed_in.get("/api/worlds/draft-world").status_code == 404
    assert signed_in.patch("/api/worlds/final", json={"slug": "taken"}).status_code == 409
    assert signed_in.patch("/api/worlds/final", json={"slug": "Bad Slug"}).status_code == 422


def test_update_project(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "W"})
    signed_in.post("/api/worlds/w/projects", json={"name": "One"})
    signed_in.post("/api/worlds/w/projects", json={"name": "Two"})
    r = signed_in.patch("/api/worlds/w/projects/one", json={"name": "Uno", "kind": "short", "slug": "uno"})
    assert (r.json()["name"], r.json()["kind"], r.json()["slug"]) == ("Uno", "short", "uno")
    assert signed_in.patch("/api/worlds/w/projects/uno", json={"slug": "two"}).status_code == 409
    assert signed_in.patch("/api/worlds/w/projects/uno", json={"kind": "epic"}).status_code == 422
    assert signed_in.patch("/api/worlds/w/projects/missing", json={"name": "x"}).status_code == 404


def test_reorder_projects(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "W"})
    ids = [signed_in.post("/api/worlds/w/projects", json={"name": n}).json()["id"] for n in ("A", "B", "C")]
    r = signed_in.put("/api/worlds/w/project-order", json={"ids": [ids[2], ids[0], ids[1]]})
    assert [p["name"] for p in r.json()] == ["C", "A", "B"]
    assert [p["name"] for p in signed_in.get("/api/worlds/w").json()["projects"]] == ["C", "A", "B"]
    assert signed_in.put("/api/worlds/w/project-order", json={"ids": ids[:2]}).status_code == 422
    assert signed_in.put("/api/worlds/w/project-order",
                         json={"ids": [ids[0], ids[1], str(uuid.uuid4())]}).status_code == 422


def test_blank_names_are_refused(signed_in: Client):
    assert signed_in.post("/api/worlds", json={"name": "   "}).status_code == 422
    assert signed_in.post("/api/worlds", json={"name": ""}).status_code == 422


def test_worlds_are_private_to_their_members(signed_in: Client, db):
    from quarry.models import User, World, WorldMember

    signed_in.post("/api/worlds", json={"name": "Mine"})
    other = User(display_name="Someone else")
    db.add(other)
    db.flush()
    theirs = World(name="Theirs", slug="theirs", created_by=other.id, updated_by=other.id)
    db.add(theirs)
    db.flush()
    db.add(WorldMember(world_id=theirs.id, user_id=other.id, role="owner"))
    db.commit()

    assert [w["slug"] for w in signed_in.get("/api/worlds").json()] == ["mine"]
    assert signed_in.get("/api/worlds/theirs").status_code == 404
    assert signed_in.post("/api/worlds/theirs/projects", json={"name": "x"}).status_code == 404
    assert signed_in.patch("/api/worlds/theirs", json={"name": "x"}).status_code == 404


def test_rename_myself(signed_in: Client):
    r = signed_in.patch("/api/me", json={"display_name": "  New   Name "})
    assert r.json()["display_name"] == "New Name"
