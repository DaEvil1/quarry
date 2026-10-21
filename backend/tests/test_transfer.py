"""Export a world as Markdown, restore it into a new world, and get the same world back."""

from __future__ import annotations

import io
import zipfile

import yaml

from .conftest import Client

W = "/api/worlds/coast"


def build_world(c: Client) -> None:
    c.post("/api/worlds", json={"name": "Coast"})
    c.post(f"{W}/projects", json={"name": "Book One"})
    c.post(f"{W}/projects", json={"name": "Novella", "kind": "novella"})
    v = c.post(f"{W}/entities", json={"name": "Varren", "aliases": ["the Grey Keeper"], "body": "Keeper of the light."}).json()
    c.post(f"{W}/entities", json={"name": "Old Harbour", "kind": "place"})
    one = c.post(f"{W}/projects/book-one/chapters", json={"title": "Arrival", "body": "Varren waits.\n\nThe boat comes.",
                                                          "pov_entity_id": v["id"]}).json()
    two = c.post(f"{W}/projects/book-one/chapters", json={"title": "Old opening", "body": "A gull."}).json()
    c.post(f"{W}/projects/book-one/chapters", json={"title": "Storm", "body": "Rain at Old Harbour."})
    c.post(f"{W}/chapters/{two['id']}/retire", json={"note": "the gull"})
    c.post(f"{W}/chapters/{one['id']}/experiments", json={"start": "copy", "title": "Arrival, at night"})
    item = c.post(f"{W}/items", json={"body": "Why does Varren stay?", "kind": "question", "project": "book-one",
                                      "entities": [v["id"]]}).json()
    c.post(f"{W}/items/{item['id']}/close", json={"status": "accepted", "decision": "He stays for a promise",
                                                  "decided_on": "2026-10-20"})
    c.post(f"{W}/items", json={"body": "Moon tides", "kind": "spark"})
    c.post(f"{W}/journal", json={"title": "What now?", "body": "Thinking about the Grey Keeper.",
                                 "entry_date": "2026-10-19", "project": "novella"})
    c.post(f"{W}/decisions", json={"text": "The world has two moons", "decided_on": "2026-10-18"})
    c.post(f"{W}/name-ignores", json={"token": "Thursday"})


def snapshot(c: Client, slug: str) -> dict:
    """Everything a person sees in a world, without ids or timestamps."""
    base = f"/api/worlds/{slug}"
    world = c.get(base).json()
    out: dict = {"projects": [(p["name"], p["slug"], p["kind"]) for p in world["projects"]]}
    out["entities"] = [(e["name"], e["kind"], e["aliases"], e["body"], e["mention_count"]) for e in c.get(f"{base}/entities").json()]
    for p in world["projects"]:
        m = c.get(f"{base}/projects/{p['slug']}/chapters").json()
        out[p["slug"]] = {
            "chapters": [(x["title"], x["position"], x["words"], (x["pov"] or {}).get("name")) for x in m["chapters"]],
            "experiments": [x["title"] for x in m["experiments"]],
            "salvage": [(s["title"], [n["body"] for n in s["harvest_notes"]])
                        for s in c.get(f"{base}/projects/{p['slug']}/salvage").json()],
        }
        out[p["slug"]]["bodies"] = [c.get(f"{base}/chapters/{x['id']}").json()["body"] for x in m["chapters"]]
    out["items"] = sorted((i["body"], i["kind"], i["status"], i["project"], [e["name"] for e in i["entities"]])
                          for i in c.get(f"{base}/items?status=all").json())
    out["journal"] = [(j["entry_date"], j["title"], j["body"], j["project"]) for j in c.get(f"{base}/journal").json()]
    out["decisions"] = [(d["decided_on"], d["text"], d["project"], d["item_id"] is not None)
                        for d in c.get(f"{base}/decisions").json()]
    out["ignored"] = c.get(f"{base}/name-ignores").json()
    return out


def test_export_layout(signed_in: Client):
    build_world(signed_in)
    r = signed_in.get(f"{W}/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert 'filename="quarry-coast-' in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    assert "coast/world.md" in names
    assert "coast/Bible/Characters/Varren.md" in names and "coast/Bible/Places/Old Harbour.md" in names
    assert "coast/Projects/Book One/Manuscript/01 Arrival.md" in names
    assert "coast/Projects/Book One/Manuscript/02 Storm.md" in names
    assert any(n.startswith("coast/Projects/Book One/Salvage/Old opening (") for n in names)
    assert any(n.startswith("coast/Projects/Book One/Experiments/Arrival, at night (") for n in names)
    assert any(n.startswith("coast/Projects/Book One/Planning/accepted/") for n in names)
    assert any(n.startswith("coast/Planning/open/") for n in names)
    assert any(n.startswith("coast/Journal/2026-10-19 What now") for n in names)

    arrival = z.read("coast/Projects/Book One/Manuscript/01 Arrival.md").decode()
    meta = yaml.safe_load(arrival.split("---\n")[1])
    assert (meta["title"], meta["pov"], meta["state"]) == ("Arrival", "Varren", "current")
    assert arrival.endswith("\n\nVarren waits.\n\nThe boat comes.")
    compiled = z.read("coast/Projects/Book One/manuscript.md").decode()
    assert compiled.index("## Arrival") < compiled.index("## Storm") and "Old opening" not in compiled
    assert "- 2026-10-18 The world has two moons <!-- id=" in z.read("coast/Decisions.md").decode()


def test_export_then_restore_gives_the_same_world(signed_in: Client):
    build_world(signed_in)
    before = snapshot(signed_in, "coast")
    data = signed_in.get(f"{W}/export").content
    r = signed_in.post("/api/worlds/restore", files={"file": ("export.zip", data, "application/zip")})
    assert r.status_code == 201, r.text
    restored = r.json()
    assert (restored["name"], restored["slug"]) == ("Coast", "coast-2")
    assert snapshot(signed_in, "coast-2") == before


def test_restore_refuses_other_files(signed_in: Client):
    r = signed_in.post("/api/worlds/restore", files={"file": ("x.zip", b"not a zip", "application/zip")})
    assert r.status_code == 422
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("notes/readme.md", "hello")
    r = signed_in.post("/api/worlds/restore", files={"file": ("x.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 422 and "not a Quarry export" in r.json()["detail"]


def test_restore_ignores_paths_that_climb_out(signed_in: Client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("w/world.md", "---\nquarry_export: 1\nname: W\nslug: w\n---\n\n")
        z.writestr("w/Bible/Characters/../../../evil.md", "---\nname: Evil\nkind: character\n---\n\n")
    r = signed_in.post("/api/worlds/restore", files={"file": ("x.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 201
    assert signed_in.get("/api/worlds/w/entities").json() == []


def test_export_is_private(signed_in: Client, app):
    from .conftest import Client as C

    build_world(signed_in)
    assert C(app).get(f"{W}/export").status_code == 401
