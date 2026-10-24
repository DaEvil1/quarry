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
    # the world model: entry fields, facts, relationships, decision tags
    isolde = c.post(f"{W}/entities", json={"name": "Isolde Hale", "summary": "Keeper's daughter", "match_case": False,
                                           "exclusions": ["isolde's rest"]}).json()
    c.post(f"{W}/entities/{v['id']}/facts", json={"label": "eye colour", "value": "grey", "evidence": "grey eyes",
                                                  "established_in_chapter_id": one["id"]})
    c.post(f"{W}/entities/{v['id']}/facts", json={"label": "status", "value": "alive", "standing": "planned"})
    types = {t["label"]: t["id"] for t in c.get(f"{W}/relation-types").json()}
    c.post(f"{W}/relationships", json={"type_id": types["parent of"], "a_id": v["id"], "b_id": isolde["id"],
                                       "note": "she doesn't know yet", "established_in_chapter_id": one["id"]})
    harbour = next(e for e in c.get(f"{W}/entities").json() if e["name"] == "Old Harbour")
    c.post(f"{W}/relationships", json={"type_id": types["lives in"], "a_id": isolde["id"], "b_id": harbour["id"],
                                       "standing": "rumour"})
    c.patch(f"{W}/relation-types/{types['knows']}", json={"label": "is acquainted with"})
    c.put(f"{W}/chapters/{one['id']}/presence/{v['id']}", json={"place_id": harbour["id"], "note": "on the pier"})
    c.post(f"{W}/entities/{v['id']}/facts", json={"label": "status", "value": "dead", "from_chapter_id": one["id"]})
    c.post(f"{W}/decisions", json={"text": "Isolde stays", "decided_on": "2026-10-17", "entities": [isolde["id"]]})
    # revising: summaries and statuses (renamed and reordered), and the cuts bin
    statuses = c.get(f"{W}/projects/book-one/statuses").json()
    c.patch(f"{W}/statuses/{statuses[1]['id']}", json={"label": "second draft"})
    c.put(f"{W}/projects/book-one/status-order", json={"ids": [statuses[2]["id"], statuses[0]["id"], statuses[1]["id"]]})
    c.patch(f"{W}/chapters/{one['id']}/about", json={"summary": "Varren waits for the boat.", "status_id": statuses[1]["id"]})
    c.patch(f"{W}/chapters/{two['id']}/about", json={"summary": "The gull", "status_id": statuses[2]["id"]})
    c.post(f"{W}/cuts", json={"id": "6f1d3c0e-1111-4c1e-9a7a-0d8e2b3c4d5e", "chapter_id": one["id"], "body": "The lamp went out.",
                              "before": "Varren waits.", "after": "\n\nThe boat", "cut_at": "2026-10-19T10:00:00+00:00"})
    kept = "6f1d3c0e-2222-4c1e-9a7a-0d8e2b3c4d5e"
    c.post(f"{W}/cuts", json={"id": kept, "chapter_id": one["id"], "body": "A gull cried.", "cut_at": "2026-10-20T10:00:00+00:00"})
    c.post(f"{W}/cuts/{kept}/put-back", json={"chapter_id": one["id"]})
    c.post(f"{W}/projects/novella/statuses", json={"label": "outline"})
    # more views of the bible: a gap length, an entry in a project's own bible, a gender, the per-label switches
    c.patch(f"{W}/projects/novella", json={"gap_chapters": 8})
    c.post(f"{W}/entities", json={"name": "Mirelle", "project": "novella"})
    current = c.get(f"{W}/entities/{v['id']}").json()["entity"]
    c.patch(f"{W}/entities/{v['id']}", json={"base_version": current["version"], "gender": "male"})
    c.put(f"{W}/labels/character/eye colour", json={"several": True})
    c.put(f"{W}/labels/character/status", json={"expected": True})


def snapshot(c: Client, slug: str) -> dict:
    """Everything a person sees in a world, without ids or timestamps."""
    base = f"/api/worlds/{slug}"
    world = c.get(base).json()
    out: dict = {"projects": [(p["name"], p["slug"], p["kind"], p["gap_chapters"]) for p in world["projects"]]}
    out["entities"] = [(e["name"], e["kind"], e["aliases"], e["body"], e["mention_count"], e["summary"],
                        e["match_case"], e["first_name_alias"], e["exclusions"], e["project"], e["gender"])
                       for e in c.get(f"{base}/entities").json()]
    out["labels"] = sorted((k["kind"], x["label"], x["several"], x["expected"], x["asked"])
                           for k in c.get(f"{base}/labels").json()["kinds"] for x in k["labels"])
    chapter_titles = {}
    for p in world["projects"]:
        for x in c.get(f"{base}/projects/{p['slug']}/chapters").json()["chapters"]:
            chapter_titles[x["id"]] = x["title"]
    for e in c.get(f"{base}/entities").json():
        d = c.get(f"{base}/entities/{e['id']}").json()
        out[f"facts:{e['name']}"] = [(f["label"], f["value"], f["standing"], f["evidence"],
                                      chapter_titles.get(f["established_in_chapter_id"]),
                                      chapter_titles.get(f["from_chapter_id"])) for f in d["facts"]]
        out[f"rels:{e['name']}"] = sorted((r["reads"], r["other"]["name"], r["standing"], r["note"],
                                           chapter_titles.get(r["established_in_chapter_id"])) for r in d["relationships"])
    out["types"] = [(t["a_kind"], t["b_kind"], t["label"], t["reverse_label"]) for t in c.get(f"{base}/relation-types").json()]
    for p in world["projects"]:
        m = c.get(f"{base}/projects/{p['slug']}/chapters").json()
        out[p["slug"]] = {
            "chapters": [(x["title"], x["position"], x["words"], (x["pov"] or {}).get("name"), x["summary"],
                          (x["status"] or {}).get("label")) for x in m["chapters"]],
            "experiments": [x["title"] for x in m["experiments"]],
            "salvage": [(s["title"], [n["body"] for n in s["harvest_notes"]], s["summary"], (s["status"] or {}).get("label"))
                        for s in c.get(f"{base}/projects/{p['slug']}/salvage").json()],
            "statuses": [s["label"] for s in m["statuses"]],
            "cuts": [(x["body"], (x["chapter"] or {}).get("title"), x["chapter_title"], x["cut_at"], x["before"], x["after"],
                      (x["put_back_to"] or {}).get("title"), x["put_back_at"] is not None)
                     for x in c.get(f"{base}/projects/{p['slug']}/cuts?put_back=true").json()],
        }
        out[p["slug"]]["bodies"] = [c.get(f"{base}/chapters/{x['id']}").json()["body"] for x in m["chapters"]]
    out["items"] = sorted((i["body"], i["kind"], i["status"], i["project"], [e["name"] for e in i["entities"]])
                          for i in c.get(f"{base}/items?status=all").json())
    out["journal"] = [(j["entry_date"], j["title"], j["body"], j["project"]) for j in c.get(f"{base}/journal").json()]
    out["decisions"] = [(d["decided_on"], d["text"], d["project"], d["item_id"] is not None,
                         [e["name"] for e in d["entities"]]) for d in c.get(f"{base}/decisions").json()]
    out["ignored"] = c.get(f"{base}/name-ignores").json()
    out["where"] = sorted((r["entity"]["name"], chapter_titles[cid], (cell["recorded"] or {}).get("name"), cell["note"])
                          for r in c.get(f"{base}/where").json()["rows"] for cid, cell in r["cells"].items())
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
    assert (meta["summary"], meta["status"]) == ("Varren waits for the boat.", "second draft")
    project = yaml.safe_load(z.read("coast/Projects/Book One/project.md").decode().split("---\n")[1])
    assert project["statuses"] == ["polished", "raw", "second draft"]
    cuts = sorted(n for n in names if n.startswith("coast/Projects/Book One/Cuts/"))
    assert [n.rsplit("/", 1)[1][:19] for n in cuts] == ["2026-10-19 Arrival ", "2026-10-20 Arrival "]
    cut_meta, cut_body = z.read(cuts[0]).decode().split("---\n")[1:]
    assert yaml.safe_load(cut_meta)["chapter"] == meta["id"] and cut_body == "\nThe lamp went out."
    compiled = z.read("coast/Projects/Book One/manuscript.md").decode()
    assert compiled.index("## Arrival") < compiled.index("## Storm") and "Old opening" not in compiled
    assert "lamp went out" not in compiled and "Varren waits for the boat" not in compiled
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
