"""Phase 12d, the chart (SPEC §13.7): pins relative to their container, kept per place and container, reset (all, or
inside some places) with what it removed for Undo, the settings (shapes for the world's own types), the demo's places,
and export/restore of the chart."""

from __future__ import annotations

import io
import zipfile

import yaml

from .conftest import Client
from .test_bible_views import W, entity, fact, relate, world  # noqa: F401

C = f"{W}/chart"


def pin(c: Client, place: dict, container: dict | None, x: float, y: float) -> dict:
    r = c.put(f"{C}/pins/{place['id']}", json={"container_id": container["id"] if container else None, "x": x, "y": y})
    assert r.status_code == 200, r.text
    return r.json()


def test_pins_are_kept_per_place_and_container(world: Client):
    assert world.get(C).json() == {"pins": [], "settings": {"shapes": {}}}
    vale, harbour, greywick = entity(world, "The Iron Vale", "place"), entity(world, "Old Harbour", "place"), entity(
        world, "Greywick", "place")
    pin(world, greywick, vale, 10.5, -4)
    # dragged again: the same pin moves
    pin(world, greywick, vale, 12, -3)
    # in another container (as of another chapter, say), a pin of its own; the old one stays
    pin(world, greywick, harbour, 1, 1)
    pin(world, vale, None, 0, 0)
    pins = {(p["place_id"], p["container_id"]): (p["x"], p["y"]) for p in world.get(C).json()["pins"]}
    assert pins == {(greywick["id"], vale["id"]): (12, -3), (greywick["id"], harbour["id"]): (1, 1),
                    (vale["id"], None): (0, 0)}
    # only places, never inside itself, numbers only
    seyla = entity(world, "Seyla")
    assert world.put(f"{C}/pins/{seyla['id']}", json={"x": 0, "y": 0}).status_code == 404
    assert world.put(f"{C}/pins/{vale['id']}", json={"container_id": vale["id"], "x": 0, "y": 0}).status_code == 422
    assert world.put(f"{C}/pins/{vale['id']}", json={"x": "inf", "y": 0}).status_code == 422
    # a place removed from the bible loses its pins, and so does everything pinned inside it
    assert world.delete(f"{W}/entities/{harbour['id']}").status_code in (200, 204)
    assert {p["container_id"] for p in world.get(C).json()["pins"]} == {vale["id"], None}


def test_reset_inside_a_place_and_undo(world: Client):
    vale, harbour, greywick, wrens = (entity(world, n, "place") for n in ("The Iron Vale", "Old Harbour", "Greywick",
                                                                          "Isle of Wrens"))
    quay = entity(world, "The Quay", "place")
    pin(world, greywick, vale, 5, 5)
    pin(world, quay, harbour, 2, 2)
    pin(world, wrens, None, 50, 0)
    # Reset inside the Iron Vale: the chart sends the Vale and the places it draws inside it
    r = world.delete(f"{C}/pins", params=[("container", vale["id"]), ("container", harbour["id"])])
    removed = r.json()["removed"]
    assert {p["place_id"] for p in removed} == {greywick["id"], quay["id"]}
    assert [p["place_id"] for p in world.get(C).json()["pins"]] == [wrens["id"]]
    # Undo puts them back
    world.post(f"{C}/pins", json={"pins": removed})
    assert len(world.get(C).json()["pins"]) == 3
    # Reset layout: everything
    assert len(world.delete(f"{C}/pins").json()["removed"]) == 3
    assert world.get(C).json()["pins"] == []


def test_settings_map_the_worlds_own_types_to_shapes(world: Client):
    r = world.put(f"{C}/settings", json={"shapes": {" Duchy ": "hexagon", "hold": "circle"}})
    assert r.json()["settings"] == {"shapes": {"duchy": "hexagon", "hold": "circle"}}
    assert world.put(f"{C}/settings", json={"shapes": {"duchy": "star"}}).status_code == 422


def test_export_and_restore_keep_the_chart(world: Client):
    vale, greywick = entity(world, "The Iron Vale", "place"), entity(world, "Greywick", "place")
    relate(world, greywick, "inside", vale)
    pin(world, greywick, vale, 7.25, -1.5)
    pin(world, vale, None, 3, 4)
    world.put(f"{C}/settings", json={"shapes": {"duchy": "hexagon"}})
    data = world.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    meta = yaml.safe_load(z.read("lamp-coast/world.md").decode().split("---\n")[1])
    assert meta["chart"]["settings"] == {"shapes": {"duchy": "hexagon"}}
    assert {(p["place"], p["container"], p["x"]) for p in meta["chart"]["pins"]} == {
        (greywick["id"], vale["id"], 7.25), (vale["id"], None, 3)}
    r = world.post("/api/worlds/restore", files={"file": ("w.zip", data, "application/zip")})
    R = f"/api/worlds/{r.json()['slug']}"
    ents = {e["name"]: e["id"] for e in world.get(f"{R}/entities").json()}
    chart = world.get(f"{R}/chart").json()
    assert chart["settings"] == {"shapes": {"duchy": "hexagon"}}
    # relinked to the restored places by id
    assert {(p["place_id"], p["container_id"], p["x"], p["y"]) for p in chart["pins"]} == {
        (ents["Greywick"], ents["The Iron Vale"], 7.25, -1.5), (ents["The Iron Vale"], None, 3, 4)}
    # an export from before the chart has none: laid out automatically
    old = io.BytesIO()
    with zipfile.ZipFile(old, "w") as out:
        for name in z.namelist():
            body = z.read(name).decode()
            if name.endswith("world.md"):
                head = yaml.safe_load(body.split("---\n")[1])
                head.pop("chart")
                body = "---\n" + yaml.safe_dump(head, allow_unicode=True, sort_keys=False) + "---\n"
            out.writestr(name, body)
    r = world.post("/api/worlds/restore", files={"file": ("old.zip", old.getvalue(), "application/zip")})
    assert r.status_code in (200, 201), r.text
    assert world.get(f"/api/worlds/{r.json()['slug']}/chart").json() == {"pins": [], "settings": {"shapes": {}}}


def test_demo_world_is_charted(signed_in: Client):
    demo = signed_in.post("/api/worlds/demo").json()
    D = f"/api/worlds/{demo['slug']}"
    cards = {c["name"]: c for c in signed_in.get(f"{D}/cards").json()}
    types = {n: next((f["value"] for f in c["facts"] if f["label"] == "type"), None) for n, c in cards.items()
             if c["kind"] == "place"}
    assert types["The Ninefold Delta"] == "land"
    assert types["The Outer Sound"] == "sea" and types["The Salt Flats"] == "island"
    assert {types["Carrow Ferry"], types["Greywater"]} == {"village", "town"}
    labels = {(r["label"], r["other"]["name"]) for r in cards["Greywater"]["relations"]}
    assert ("road to", "Carrow Ferry") in labels and ("north of", "Carrow Ferry") in labels
    assert ("borders", "The Outer Sound") in {(r["label"], r["other"]["name"]) for r in cards["The Ninefold Delta"]["relations"]}
    # two places pinned inside the delta, the rest laid out automatically
    pins = signed_in.get(f"{D}/chart").json()["pins"]
    assert sorted((p["place_id"], p["container_id"]) for p in pins) == sorted(
        (cards[n]["id"], cards["The Ninefold Delta"]["id"]) for n in ("Greywater", "Marrow Locks"))
