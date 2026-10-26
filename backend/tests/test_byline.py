"""A byline (docs/SPEC.md §19): one optional line under a project's title, in the export and back. Made-up names."""

from __future__ import annotations

import io
import zipfile

import yaml

from .conftest import Client

W = "/api/worlds/coast"


def test_byline_set_shown_exported_and_restored(signed_in: Client):
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "The Salt Road"})
    signed_in.post(f"{W}/projects/the-salt-road/chapters", json={"title": "One", "body": "Isolde waits."})
    out = signed_in.patch(f"{W}/projects/the-salt-road", json={"byline": "  A  Salt Road   Tale "}).json()
    assert out["byline"] == "A Salt Road Tale"
    assert signed_in.get(W).json()["projects"][0]["byline"] == "A Salt Road Tale"

    data = signed_in.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    meta = yaml.safe_load(z.read("coast/Projects/The Salt Road/project.md").decode().split("---\n")[1])
    assert meta["byline"] == "A Salt Road Tale"
    compiled = z.read("coast/Projects/The Salt Road/manuscript.md").decode()
    assert compiled.startswith("# The Salt Road\n\n*A Salt Road Tale*\n\n## One")

    restored = signed_in.post("/api/worlds/restore", files={"file": ("x.zip", data, "application/zip")}).json()
    assert restored["projects"][0]["byline"] == "A Salt Road Tale"

    # an empty string clears it, and the export leaves it out
    assert signed_in.patch(f"{W}/projects/the-salt-road", json={"byline": ""}).json()["byline"] is None
    z = zipfile.ZipFile(io.BytesIO(signed_in.get(f"{W}/export").content))
    assert "byline" not in yaml.safe_load(z.read("coast/Projects/The Salt Road/project.md").decode().split("---\n")[1])
    assert z.read("coast/Projects/The Salt Road/manuscript.md").decode().startswith("# The Salt Road\n\n## One")


def test_an_older_export_has_no_byline(signed_in: Client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("w/world.md", "---\nquarry_export: 1\nname: Old\n---\n")
        z.writestr("w/Projects/Book/project.md", "---\nname: Book\nslug: book\n---\n")
    out = signed_in.post("/api/worlds/restore", files={"file": ("x.zip", buf.getvalue(), "application/zip")}).json()
    assert out["projects"][0]["byline"] is None
