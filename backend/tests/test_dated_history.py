"""Dated earlier versions in the export and Restore (docs/SPEC.md §20): History/ files restored as revisions on their
dates and counted in the word history on their days; the export writing each day's last version and every labelled
checkpoint. Made-up texts."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime, timedelta

import yaml

from .conftest import Client

W = "/api/worlds/coast"


def handmade(history: list[tuple[str, str]], current: str = "Isolde came down to the quay at dusk.",
             journal: list[tuple[str, str]] | None = None) -> bytes:
    """A zip with one chapter (id c1) and its dated versions; `history` is (frontmatter lines, text)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("w/world.md", "---\nquarry_export: 1\nname: Handmade\n---\n")
        z.writestr("w/Projects/Book/project.md", "---\nname: Book\nslug: book\n---\n")
        z.writestr("w/Projects/Book/Manuscript/01 The Quay.md", f"---\nid: c1\ntitle: The Quay\nposition: 0\n---\n\n{current}\n")
        z.writestr("w/Journal/2026-03-01 Ideas.md", "---\nid: j1\ndate: 2026-03-01\ntitle: Ideas\n---\n\nA quay at dusk, maybe.\n")
        for i, (meta, text) in enumerate(history):
            z.writestr(f"w/History/Book/01 The Quay (c1)/{i:03d}.md", f"---\n{meta}\n---\n\n{text}\n")
        for i, (meta, text) in enumerate(journal or []):
            z.writestr(f"w/History/Journal/Ideas (j1)/{i:03d}.md", f"---\n{meta}\n---\n\n{text}\n")
        # one for a chapter that isn't in the zip: skipped
        z.writestr("w/History/Book/Gone (zz)/000.md", "---\nchapter: zz\nat: 2026-03-02\n---\n\nNothing.\n")
    return buf.getvalue()


def restore(c: Client, data: bytes) -> dict:
    r = c.post("/api/worlds/restore", files={"file": ("x.zip", data, "application/zip")})
    assert r.status_code == 201, r.text
    return r.json()


def history_of(c: Client, slug: str) -> tuple[list[tuple[str, int, int]], list[dict], str]:
    base = f"/api/worlds/{slug}"
    ch = c.get(f"{base}/projects/book/chapters").json()["chapters"][0]
    h = c.get(f"{base}/projects/book/word-history").json()
    days = sorted((r["at"][:10], r["added"], r["removed"]) for r in h["revisions"])
    revs = c.get(f"{base}/chapters/{ch['id']}/revisions").json()
    return days, revs, ch["id"]


def test_dated_versions_come_back_on_their_days(signed_in: Client):
    out = restore(signed_in, handmade([
        ("chapter: c1\nat: 2025-03-02", "Isolde came down."),
        ("chapter: c1\nat: 2025-03-05T22:10:00+01:00\nreason: checkpoint\nlabel: first draft done", "Isolde came down to the quay."),
        ("chapter: c1\nat: '2025-03-09T08:00:00Z'", "Isolde came down to the quay at dusk."),
    ]))
    days, revs, _ = history_of(signed_in, out["slug"])
    # the first counts from empty; each later one what changed; the file equals the last: no start today
    assert days == [("2025-03-02", 3, 0), ("2025-03-05", 3, 0), ("2025-03-09", 2, 0)]
    assert sorted((r["reason"], r["label"]) for r in revs) == [("autosnap", None), ("autosnap", None), ("checkpoint", "first draft done")]
    assert sorted(r["created_at"][:10] for r in revs) == ["2025-03-02", "2025-03-05", "2025-03-09"]
    assert out.get("history", 3) == 3


def test_a_start_counts_nothing_and_newer_text_is_a_start_of_today(signed_in: Client):
    out = restore(signed_in, handmade([
        ("chapter: c1\nat: 2025-03-02\nreason: start", "Isolde came down."),
        ("chapter: c1\nat: 2025-03-05", "Isolde came down to the quay."),
    ], current="Isolde came down to the quay at dusk, alone."))
    days, revs, _ = history_of(signed_in, out["slug"])
    assert days == [("2025-03-05", 3, 0)]
    today = datetime.now(UTC).date().isoformat()
    starts = sorted(r["created_at"][:10] for r in revs if r["reason"] == "start")
    assert starts == ["2025-03-02", today]


def test_a_journal_entrys_versions_fill_its_history(signed_in: Client):
    out = restore(signed_in, handmade([], journal=[("journal: j1\nat: 2025-01-10", "A quay."),
                                                   ("journal: j1\nat: 2025-02-10", "A quay at dusk, maybe.")]))
    base = f"/api/worlds/{out['slug']}"
    j = signed_in.get(f"{base}/journal").json()[0]
    revs = signed_in.get(f"{base}/journal/{j['id']}/revisions").json()
    assert sorted(r["created_at"][:10] for r in revs) == ["2025-01-10", "2025-02-10"]
    # the Journal never counts in the word history, and a chapter with no History restores as before
    days, crevs, _ = history_of(signed_in, out["slug"])
    assert days == [] and [r["reason"] for r in crevs] == ["start"]


def test_export_writes_each_days_last_version_and_the_checkpoints(signed_in: Client, db):
    from quarry.models import Revision

    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Book"})
    ch = signed_in.post(f"{W}/projects/book/chapters", json={"title": "The Quay", "body": ""}).json()
    version = ch["version"]
    for text, reason, label in (("Isolde came down.", "autosnap", None), ("Isolde came down to the quay.", "checkpoint", "draft"),
                                ("Isolde came down to the quay at dusk.", "autosnap", None)):
        version = signed_in.patch(f"{W}/chapters/{ch['id']}", json={"base_version": version, "body": text}).json()["version"]
        signed_in.post(f"{W}/chapters/{ch['id']}/revisions", json={"reason": reason, **({"label": label} if label else {})})
    signed_in.post(f"{W}/chapters/{ch['id']}/revisions", json={"reason": "conflict", "body": "Another device's text."})
    # the first two on one day (the checkpoint kept for its label), the last on the next
    revs = db.query(Revision).filter(Revision.doc_id == ch["id"]).order_by(Revision.created_at).all()
    two_days_ago = datetime.now(UTC) - timedelta(days=2)
    for r, at in zip(revs, [two_days_ago, two_days_ago + timedelta(hours=1), two_days_ago + timedelta(days=1)]):
        r.created_at = at
    db.commit()

    data = signed_in.get(f"{W}/export").content
    z = zipfile.ZipFile(io.BytesIO(data))
    hist = sorted(n for n in z.namelist() if "/History/" in n)
    metas = [yaml.safe_load(z.read(n).decode().split("---\n")[1]) for n in hist]
    texts = [z.read(n).decode().split("---\n", 2)[2].strip() for n in hist]
    assert texts == ["Isolde came down to the quay.", "Isolde came down to the quay at dusk."]
    assert metas[0]["reason"] == "checkpoint" and metas[0]["label"] == "draft" and metas[0]["chapter"] == ch["id"]

    out = restore(signed_in, data)
    days, revs2, _ = history_of(signed_in, out["slug"])
    d0, d1 = two_days_ago.date().isoformat(), (two_days_ago + timedelta(days=1)).date().isoformat()
    assert days == [(d0, 6, 0), (d1, 2, 0)]
    assert sorted(r["reason"] for r in revs2) == ["autosnap", "checkpoint"]


def test_an_export_without_history_restores_as_before(signed_in: Client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("w/world.md", "---\nquarry_export: 1\nname: Old\n---\n")
        z.writestr("w/Projects/Book/project.md", "---\nname: Book\nslug: book\n---\n")
        z.writestr("w/Projects/Book/Manuscript/01 One.md", "---\nid: c1\ntitle: One\nposition: 0\n---\n\nIsolde waits.\n")
    out = restore(signed_in, buf.getvalue())
    days, revs, _ = history_of(signed_in, out["slug"])
    assert days == [] and [r["reason"] for r in revs] == ["start"]
