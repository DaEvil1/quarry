"""The decisions log."""

from __future__ import annotations

from datetime import date

from .conftest import Client

W = "/api/worlds/coast"


def test_add_list_edit_and_delete(signed_in: Client):
    c = signed_in
    c.post("/api/worlds", json={"name": "Coast"})
    c.post(f"{W}/projects", json={"name": "Book One"})
    a = c.post(f"{W}/decisions", json={"text": "Chapter 3 is told by the sister", "decided_on": "2026-10-01",
                                       "project": "book-one"}).json()
    b = c.post(f"{W}/decisions", json={"text": "The sea god is silent"}).json()
    assert b["decided_on"] == date.today().isoformat()
    assert [d["id"] for d in c.get(f"{W}/decisions").json()] == [b["id"], a["id"]]
    assert [d["id"] for d in c.get(f"{W}/decisions?project=book-one").json()] == [a["id"]]
    assert [d["id"] for d in c.get(f"{W}/decisions?project=-").json()] == [b["id"]]

    r = c.patch(f"{W}/decisions/{b['id']}", json={"text": "The sea god speaks once", "project": "book-one"})
    assert (r.json()["text"], r.json()["project"]) == ("The sea god speaks once", "book-one")
    assert c.patch(f"{W}/decisions/{b['id']}", json={"text": ""}).status_code == 422

    assert c.delete(f"{W}/decisions/{a['id']}").status_code == 204
    assert [d["id"] for d in c.get(f"{W}/decisions").json()] == [b["id"]]
    assert c.delete(f"{W}/decisions/{a['id']}").status_code == 404


def test_blank_and_foreign_item_refused(signed_in: Client):
    c = signed_in
    c.post("/api/worlds", json={"name": "Coast"})
    assert c.post(f"{W}/decisions", json={"text": "   "}).status_code == 422
    c.post("/api/worlds", json={"name": "Other"})
    other_item = c.post("/api/worlds/other/items", json={"body": "x"}).json()
    r = c.post(f"{W}/decisions", json={"text": "y", "item_id": other_item["id"]})
    assert r.status_code == 422
