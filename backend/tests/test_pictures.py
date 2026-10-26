"""Pictures (docs/SPEC.md §17): upload, sizes and metadata, galleries, picture lines, where a picture is used, and
pictures in the export and Restore. Every picture here is drawn by the test (made-up shapes), never a photo."""

from __future__ import annotations

import io
import zipfile

import yaml
from PIL import Image, ImageDraw

from .conftest import Client

W = "/api/worlds/coast"


def drawn(w: int, h: int, fmt: str = "JPEG", *, alpha: bool = False, exif=None) -> bytes:  # type: ignore[no-untyped-def]
    """A made-up picture: two coloured blocks, so its orientation can be seen."""
    img = Image.new("RGBA" if alpha else "RGB", (w, h), (0, 0, 0, 0) if alpha else (200, 210, 220))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w // 2, h // 3), fill=(180, 40, 40, 255) if alpha else (180, 40, 40))
    buf = io.BytesIO()
    kw = {"exif": exif} if exif is not None else {}
    img.save(buf, fmt, **kw)
    return buf.getvalue()


def upload(c: Client, data: bytes, name: str = "harbour-at-dusk.jpg", world: str = W):  # type: ignore[no-untyped-def]
    return c.post(f"{world}/pictures", files={"file": (name, data, "application/octet-stream")})


def opened(c: Client, picture_id: str, kind: str) -> Image.Image:
    r = c.get(f"/api/pictures/{picture_id}/{kind}")
    assert r.status_code == 200
    return Image.open(io.BytesIO(r.content))


def test_upload_scales_turns_and_strips(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Coast"})
    exif = Image.Exif()
    exif[0x8825] = {2: (59.0, 54.0, 0.0)}  # a location
    exif[0x0110] = "Made-up Camera"
    r = upload(signed_in, drawn(4000, 3000, exif=exif))
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["name"], p["format"], p["width"], p["height"]) == ("harbour-at-dusk", "jpeg", 2400, 1800)
    full = opened(signed_in, p["id"], "full")
    assert full.size == (2400, 1800) and full.format == "JPEG"
    assert not full.getexif()
    assert opened(signed_in, p["id"], "view").size == (1600, 1200)
    thumb = opened(signed_in, p["id"], "thumb")
    assert thumb.size == (400, 300) and thumb.format == "WEBP"
    r = signed_in.get(f"/api/pictures/{p['id']}/view")
    assert r.headers["content-type"] == "image/webp"
    assert r.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-disposition"].startswith("inline")
    assert "content-encoding" not in r.headers

    # taken sideways: kept upright, the orientation tag gone with the rest
    sideways = Image.Exif()
    sideways[0x0112] = 6
    p = upload(signed_in, drawn(800, 600, exif=sideways), "sideways.jpg").json()
    assert (p["width"], p["height"]) == (600, 800)
    img = opened(signed_in, p["id"], "full")
    assert img.size == (600, 800) and 0x0112 not in img.getexif()
    # a small picture isn't scaled up
    p = upload(signed_in, drawn(300, 200, "PNG"), "small.png").json()
    assert opened(signed_in, p["id"], "view").size == (300, 200)


def test_png_keeps_its_transparency(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Coast"})
    p = upload(signed_in, drawn(600, 400, "PNG", alpha=True), "mark.png").json()
    assert p["format"] == "png"
    full = opened(signed_in, p["id"], "full")
    assert full.mode == "RGBA" and full.getpixel((590, 390))[3] == 0
    assert opened(signed_in, p["id"], "view").mode == "RGBA"
    w = upload(signed_in, drawn(500, 500, "WEBP"), "web.webp").json()
    assert w["format"] == "webp"


def test_what_isnt_taken(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Coast"})
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    for data, name in ((svg, "x.svg"), (b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64, "x.heic"),
                       (b"just some text", "notes.jpg"), (drawn(40, 40, "GIF"), "x.gif")):
        r = upload(signed_in, data, name)
        assert r.status_code == 422, name
        assert r.json()["detail"] == "Quarry takes JPEG, PNG or WebP pictures."
    r = upload(signed_in, b"\xff\xd8" + b"\x00" * (30 * 1024 * 1024), "huge.jpg")
    assert r.status_code == 413
    assert signed_in.get(f"{W}/pictures").json()["count"] == 0


def test_a_picture_of_another_world_is_not_found(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Coast"})
    p = upload(signed_in, drawn(50, 50)).json()
    signed_in.post("/api/worlds", json={"name": "Inland"})
    assert signed_in.get("/api/pictures/00000000-0000-4000-8000-000000000000/view").status_code == 404
    # it is ours; another writer's world isn't reachable at all (members only): the join makes it 404
    assert signed_in.get(f"/api/pictures/{p['id']}/thumb").status_code == 200
    assert signed_in.get(f"/api/pictures/{p['id']}/other").status_code == 404
    where = signed_in.get(f"/api/worlds/inland/pictures/whereabouts?ids={p['id']},00000000-0000-4000-8000-000000000000").json()
    assert where == {p["id"]: "elsewhere", "00000000-0000-4000-8000-000000000000": "deleted"}


def test_another_writers_picture_answers_404(signed_in: Client, app, passkey):
    from .conftest import Client as C
    from .softauth import SoftPasskey

    signed_in.post("/api/worlds", json={"name": "Coast"})
    p = upload(signed_in, drawn(50, 50)).json()
    # a second person, signed in on their own: setup is done, so they can't be made through the API; their
    # session is a stranger's
    other = C(app)
    assert other.get(f"/api/pictures/{p['id']}/view").status_code == 401
    assert isinstance(passkey, SoftPasskey)


def test_gallery_uses_rename_and_delete(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Salt Road"})
    greywick = signed_in.post(f"{W}/entities", json={"name": "Greywick", "kind": "place"}).json()
    one = upload(signed_in, drawn(800, 600), "harbour.jpg").json()
    two = upload(signed_in, drawn(600, 800), "gate.jpg").json()
    r = signed_in.put(f"{W}/entities/{greywick['id']}/pictures",
                      json=[{"picture": two["id"], "caption": "The gate"}, {"picture": one["id"], "caption": " The  harbour "}])
    assert r.status_code == 200
    assert [(g["name"], g["caption"]) for g in r.json()] == [("gate", "The gate"), ("harbour", "The harbour")]
    detail = signed_in.get(f"{W}/entities/{greywick['id']}").json()
    assert [g["id"] for g in detail["pictures"]] == [two["id"], one["id"]]
    card = next(c for c in signed_in.get(f"{W}/cards").json() if c["name"] == "Greywick")
    assert card["picture"] == two["id"]
    # a picture twice, or one from nowhere, is refused
    assert signed_in.put(f"{W}/entities/{greywick['id']}/pictures",
                         json=[{"picture": one["id"]}, {"picture": one["id"]}]).status_code == 422
    assert signed_in.put(f"{W}/entities/{greywick['id']}/pictures",
                         json=[{"picture": "00000000-0000-4000-8000-000000000000"}]).status_code == 422

    ch = signed_in.post(f"{W}/projects/salt-road/chapters",
                        json={"title": "The Drowned Bell", "body": f"Isolde waits.\n\n![](picture:{one['id']})\n"}).json()
    listing = signed_in.get(f"{W}/pictures?uses=1").json()
    assert listing["count"] == 2 and listing["bytes"] == one["size"] + two["size"]
    uses = {p["name"]: p["uses"] for p in listing["pictures"]}
    assert [e["name"] for e in uses["harbour"]["entities"]] == ["Greywick"]
    assert [(t["table"], t["title"]) for t in uses["harbour"]["texts"]] == [("chapter", "The Drowned Bell")]
    assert uses["gate"]["texts"] == []

    r = signed_in.delete(f"/api/pictures/{one['id']}")
    assert r.status_code == 409 and r.json()["uses"]["texts"][0]["id"] == ch["id"]
    assert signed_in.patch(f"/api/pictures/{one['id']}", json={"name": "harbour at dusk"}).json()["name"] == "harbour at dusk"
    # out of the gallery, the picture stays in the world, used nowhere, and can go
    signed_in.put(f"{W}/entities/{greywick['id']}/pictures", json=[{"picture": one["id"]}])
    assert signed_in.delete(f"/api/pictures/{two['id']}").status_code == 204
    assert signed_in.get(f"/api/pictures/{two['id']}/thumb").status_code == 404
    # deleting the entry takes its gallery, not its pictures
    signed_in.delete(f"{W}/entities/{greywick['id']}")
    assert [p["name"] for p in signed_in.get(f"{W}/pictures").json()["pictures"]] == ["harbour at dusk"]


def test_a_picture_line_is_a_note(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Salt Road"})
    signed_in.post(f"{W}/entities", json={"name": "Isolde"})
    p = upload(signed_in, drawn(80, 60)).json()
    line = f"  ![Isolde at the harbour, waving](picture:{p['id']}) "
    plain = signed_in.post(f"{W}/projects/salt-road/chapters", json={"title": "Plain", "body": "Isolde waits.\n"}).json()
    pic = signed_in.post(f"{W}/projects/salt-road/chapters",
                         json={"title": "Pictured", "body": f"{line}\nIsolde waits.\n"}).json()
    inline = signed_in.post(f"{W}/projects/salt-road/chapters",
                            json={"title": "Inline", "body": f"Isolde ![x](picture:{p['id']}) waits.\n"}).json()
    chapters = {c["title"]: c for c in signed_in.get(f"{W}/projects/salt-road/chapters").json()["chapters"]}
    assert chapters["Plain"]["words"] == chapters["Pictured"]["words"] == 2
    # inside a sentence it is only text
    assert chapters["Inline"]["words"] > 2
    mentions = lambda ch: [(m["matched_text"], m["start"]) for m in signed_in.get(f"{W}/chapters/{ch['id']}").json()["mentions"]]  # noqa: E731
    assert len(mentions(pic)) == 1 and len(mentions(plain)) == 1
    # in a journal entry and an entry's notes too
    j = signed_in.post(f"{W}/journal", json={"title": "Pics", "body": f"{line}\nIsolde again.", "entry_date": "2026-10-20"}).json()
    assert signed_in.get(f"{W}/journal/{j['id']}").json()["words"] == 2
    ent = signed_in.post(f"{W}/entities", json={"name": "Greywick", "kind": "place", "body": f"{line}\nA town."}).json()
    isolde = next(e for e in signed_in.get(f"{W}/entities").json() if e["name"] == "Isolde")
    sources = {m["source_table"] for m in signed_in.get(f"{W}/entities/{isolde['id']}").json()["mentions"]}
    assert "entity" not in sources and ent["name"] == "Greywick"
    # the compiled manuscript leaves it out
    data = signed_in.get(f"{W}/export").content
    compiled = zipfile.ZipFile(io.BytesIO(data)).read("coast/Projects/Salt Road/manuscript.md").decode()
    assert "Isolde at the harbour" not in compiled and "Pictures/" not in compiled


def build(c: Client) -> dict:
    c.post("/api/worlds", json={"name": "Coast"})
    c.post(f"{W}/projects", json={"name": "Salt Road"})
    greywick = c.post(f"{W}/entities", json={"name": "Greywick", "kind": "place"}).json()
    gate = upload(c, drawn(900, 600), "Harbour at Dusk.jpg").json()
    plan = upload(c, drawn(500, 500, "PNG", alpha=True), "plan.png").json()
    bell = upload(c, drawn(300, 400, "WEBP"), "bell.webp").json()
    spare = upload(c, drawn(200, 100), "spare.jpg").json()
    c.put(f"{W}/entities/{greywick['id']}/pictures", json=[{"picture": gate["id"], "caption": "The harbour at dusk"},
                                                            {"picture": plan["id"], "caption": "From above"}])
    for _ in range(8):
        c.post(f"{W}/projects/salt-road/chapters", json={"title": "Filler", "body": "x"})
    ch = c.post(f"{W}/projects/salt-road/chapters",
                json={"title": "The Drowned Bell", "body": f"![Where Isolde lands](picture:{gate['id']})\n\nThe bell rang.\n"}).json()
    c.post(f"{W}/journal", json={"title": "Bells", "body": f"Ideas.\n\n![](picture:{bell['id']})\n", "entry_date": "2026-10-20"})
    return {"gate": gate, "plan": plan, "bell": bell, "spare": spare, "chapter": ch}


def test_export_and_restore_pictures(signed_in: Client):
    made = build(signed_in)
    data = signed_in.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    pics = sorted(n for n in z.namelist() if "/Pictures/" in n)
    gate8 = made["gate"]["id"][:8]
    assert pics == sorted([f"coast/Pictures/harbour-at-dusk-{gate8}.jpg", f"coast/Pictures/plan-{made['plan']['id'][:8]}.png",
                           f"coast/Pictures/bell-{made['bell']['id'][:8]}.webp", f"coast/Pictures/spare-{made['spare']['id'][:8]}.jpg"])
    assert all(z.getinfo(n).compress_type == zipfile.ZIP_STORED for n in pics)
    chapter = z.read("coast/Projects/Salt Road/Manuscript/09 The Drowned Bell.md").decode()
    assert f"![Where Isolde lands](../../../Pictures/harbour-at-dusk-{gate8}.jpg)" in chapter
    journal = next(n for n in z.namelist() if "/Journal/" in n)
    assert f"](../Pictures/bell-{made['bell']['id'][:8]}.webp)" in z.read(journal).decode()
    meta = yaml.safe_load(z.read("coast/Bible/Places/Greywick.md").decode().split("---\n")[1])
    assert meta["pictures"] == [{"file": f"Pictures/harbour-at-dusk-{gate8}.jpg", "caption": "The harbour at dusk"},
                                {"file": f"Pictures/plan-{made['plan']['id'][:8]}.png", "caption": "From above"}]
    world = yaml.safe_load(z.read("coast/world.md").decode().split("---\n")[1])
    assert {p["name"] for p in world["pictures"]} == {"Harbour at Dusk", "plan", "bell", "spare"}

    r = signed_in.post("/api/worlds/restore", files={"file": ("export.zip", data, "application/zip")})
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["pictures"] == 4 and out["skipped"] == []
    base = f"/api/worlds/{out['slug']}"
    listing = signed_in.get(f"{base}/pictures?uses=1").json()
    by_name = {p["name"]: p for p in listing["pictures"]}
    assert set(by_name) == {"Harbour at Dusk", "plan", "bell", "spare"}
    assert by_name["spare"]["uses"] == {"entities": [], "texts": []}
    assert opened(signed_in, by_name["plan"]["id"], "full").mode == "RGBA"
    grey = next(e for e in signed_in.get(f"{base}/entities").json() if e["name"] == "Greywick")
    gallery = signed_in.get(f"{base}/entities/{grey['id']}").json()["pictures"]
    assert [(g["name"], g["caption"]) for g in gallery] == [("Harbour at Dusk", "The harbour at dusk"), ("plan", "From above")]
    bell = next(c for c in signed_in.get(f"{base}/projects/salt-road/chapters").json()["chapters"] if c["title"] == "The Drowned Bell")
    body = signed_in.get(f"{base}/chapters/{bell['id']}").json()["body"]
    assert body.startswith(f"![Where Isolde lands](picture:{by_name['Harbour at Dusk']['id']})")
    assert [t["table"] for t in by_name["bell"]["uses"]["texts"]] == ["journal"]


def test_a_hand_made_zip(signed_in: Client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("w/world.md", "---\nquarry_export: 1\nname: Handmade\n---\n")
        z.writestr("w/Projects/Book/project.md", "---\nname: Book\nslug: book\n---\n")
        z.writestr("w/Projects/Book/Manuscript/01 One.md",
                   "---\nid: c1\ntitle: One\nposition: 0\n---\n\n![](<../../../Pictures/old map.png>)\n\n"
                   "![Spaced](../../../Pictures/old%20map.png)\n\n![](../../../Pictures/missing.png)\n\n"
                   "![web](https://example.com/x.png)\n\nText ![inline](../../../Pictures/old map.png) here.\n")
        z.writestr("w/Pictures/maps/old map.png", drawn(120, 80, "PNG"))
        z.writestr("w/Pictures/notes.txt", "not a picture")
        z.writestr("w/Pictures/fake.jpg", "not a jpeg either")
    r = signed_in.post("/api/worlds/restore", files={"file": ("x.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 201, r.text
    # the picture is made, but the links point at Pictures/old map.png and the file is in maps/: they stay as written
    assert r.json()["pictures"] == 1
    assert sorted(r.json()["skipped"]) == ["Pictures/fake.jpg", "Pictures/notes.txt"]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("w/world.md", "---\nquarry_export: 1\nname: Handmade\n---\n")
        z.writestr("w/Projects/Book/project.md", "---\nname: Book\nslug: book\n---\n")
        z.writestr("w/Projects/Book/Manuscript/01 One.md",
                   "---\nid: c1\ntitle: One\nposition: 0\n---\n\n![](<../../../Pictures/old map.png>)\n\n"
                   "![Spaced](../../../Pictures/old%20map.png)\n\n![](../../../Pictures/missing.png)\n\n"
                   "![web](https://example.com/x.png)\n\n![from the world folder](Pictures/old map.png)\n")
        z.writestr("w/Pictures/old map.png", drawn(120, 80, "PNG"))
    out = signed_in.post("/api/worlds/restore", files={"file": ("x.zip", buf.getvalue(), "application/zip")}).json()
    assert out["pictures"] == 1
    base = f"/api/worlds/{out['slug']}"
    pid = signed_in.get(f"{base}/pictures").json()["pictures"][0]["id"]
    ch = signed_in.get(f"{base}/projects/book/chapters").json()["chapters"][0]
    body = signed_in.get(f"{base}/chapters/{ch['id']}").json()["body"]
    assert body.split("\n\n") == [f"![](picture:{pid})", f"![Spaced](picture:{pid})", "![](../../../Pictures/missing.png)",
                                  "![web](https://example.com/x.png)", f"![from the world folder](picture:{pid})\n"]


def test_an_export_from_before_pictures_restores_as_before(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Salt Road"})
    data = signed_in.get(f"{W}/export").content
    assert not any("/Pictures/" in n for n in zipfile.ZipFile(io.BytesIO(data)).namelist())
    out = signed_in.post("/api/worlds/restore", files={"file": ("x.zip", data, "application/zip")}).json()
    assert out["pictures"] == 0 and out["skipped"] == []


def test_offline_copy_has_the_pictures(signed_in: Client):
    made = build(signed_in)
    pack = signed_in.get(f"{W}/offline").json()
    assert {(p["id"], p["width"], p["height"]) for p in pack["pictures"]} >= {(made["gate"]["id"], 900, 600)}


def test_demo_pictures(signed_in: Client):
    world = signed_in.post("/api/worlds/demo").json()
    base = f"/api/worlds/{world['slug']}"
    pictures = signed_in.get(f"{base}/pictures?uses=1").json()
    assert pictures["count"] == 3
    cards = {c["name"]: c for c in signed_in.get(f"{base}/cards").json()}
    locks = signed_in.get(f"{base}/entities/{cards['Marrow Locks']['id']}").json()["pictures"]
    assert [g["caption"] for g in locks] == ["The upper gate", "The locks from above"]
    assert cards["Marrow Locks"]["picture"] == locks[0]["id"]
    assert cards["The Brass Compass"]["picture"] is not None
    third = next(c for c in signed_in.get(f"{base}/projects/the-ferrymans-daughter/chapters").json()["chapters"]
                 if c["title"] == "What the River Kept")
    body = signed_in.get(f"{base}/chapters/{third['id']}").json()["body"]
    assert body.startswith(f"![The brass compass](picture:{cards['The Brass Compass']['picture']})")


def test_large_pictures(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Coast"})
    # a large JPEG is decoded at a reduced scale and still comes out at 2400 px
    p = upload(signed_in, drawn(7200, 4800), "wide.jpg").json()
    assert (p["width"], p["height"]) == (2400, 1600)
    # a PNG over 30 megapixels would be decoded whole: refused
    r = upload(signed_in, drawn(6000, 5100, "PNG"), "huge.png")
    assert r.status_code == 422 and "megapixels" in r.json()["detail"]
