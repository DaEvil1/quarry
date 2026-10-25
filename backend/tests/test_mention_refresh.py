"""When names change, only the texts the change can reach are rescanned (mentions.refresh_names). Whatever changes,
the stored mentions must be exactly what a scan of every text from scratch finds."""

from __future__ import annotations

import os
import random

import pytest
from sqlalchemy import select

from quarry.mentions import _scan, _texts, matcher_for, refresh_names
from quarry.models import Entity, Mention, World

from .conftest import Client

W = "/api/worlds/coast"

SYL = ["ar", "bel", "cor", "dan", "el", "fen", "gar", "hal", "is", "jor", "kel", "lan", "mor", "nes", "or", "pel"]
PROSE = "the of and to a in was he she it that with as on for at by from had but light sea wind harbour stone".split()


@pytest.fixture
def world(signed_in: Client) -> Client:
    signed_in.post("/api/worlds", json={"name": "Coast"})
    signed_in.post(f"{W}/projects", json={"name": "Book One"})
    return signed_in


def stored(db) -> set[tuple]:
    db.expire_all()
    return {(m.source_table, m.source_id, m.entity_id, m.start, m.end, m.matched_text, m.kind)
            for m in db.scalars(select(Mention))}


def from_scratch(db) -> set[tuple]:
    db.expire_all()
    world = db.scalar(select(World))
    m = matcher_for(db, world.id)
    return {(t, sid, f.entity_id, f.start, f.end, f.matched[:200], f.kind)
            for t, sid, body in _texts(db, world.id) for f in _scan(m, t, sid, body)}


@pytest.mark.parametrize("seed", [int(x) for x in os.environ.get("QUARRY_FUZZ_SEEDS", "7,11,23").split(",")])
def test_name_changes_keep_mentions_as_a_full_rescan_would(world: Client, db, seed: int):
    rnd = random.Random(seed)

    def word(n: int = 2) -> str:
        return "".join(rnd.choice(SYL) for _ in range(n)).capitalize()

    pool = [f"{word()} {word()}" for _ in range(12)] + [word(3) for _ in range(6)] + ["Old Harbour", "the Lamp Guild"]

    def misspelt(name: str) -> str:
        i = rnd.randrange(len(name))
        return name[:i] + rnd.choice("aeiou") + name[i + 1:]

    def prose() -> str:
        out = []
        for _ in range(30):
            w = [rnd.choice(PROSE) for _ in range(8)]
            name = rnd.choice(pool)
            w.insert(rnd.randrange(8), rnd.choice([name, name.split()[0], name + "'s", misspelt(name)]))
            s = " ".join(w)
            out.append(s[0].upper() + s[1:] + ".")
        return " ".join(out)

    for i in range(4):
        r = world.post(f"{W}/projects/book-one/chapters", json={"title": f"Ch {i}", "body": prose()})
        assert r.status_code == 201, r.text
    for _ in range(3):
        assert world.post(f"{W}/items", json={"body": prose()}).status_code == 201

    live: dict[str, dict] = {}
    ops = ["add", "add", "add", "rename", "alias", "case", "exclude", "kind", "delete", "ignore", "unignore", "body"]
    for step in range(70):
        op = rnd.choice(ops)
        change: dict = {}
        if op == "add" or not live:
            r = world.post(f"{W}/entities", json={"name": rnd.choice(pool),
                                                  "kind": rnd.choice(["character", "place", "faction"]),
                                                  "body": prose() if rnd.random() < .3 else ""})
            if r.status_code == 201:
                live[r.json()["id"]] = r.json()
        elif op == "delete":
            eid = rnd.choice(list(live))
            assert world.delete(f"{W}/entities/{eid}").status_code == 204
            del live[eid]
        elif op == "ignore":
            world.post(f"{W}/name-ignores", json={"token": misspelt(rnd.choice(pool).split()[0])})
        elif op == "unignore":
            for token in world.get(f"{W}/name-ignores").json()[:1]:
                world.delete(f"{W}/name-ignores/{token}")
        else:
            eid = rnd.choice(list(live))
            e = live[eid]
            change = {
                "rename": {"name": rnd.choice(pool), "keep_old_name": rnd.random() < .5},
                "alias": {"aliases": [rnd.choice(pool).split()[-1]]},
                "case": {"match_case": not e["match_case"]},
                "exclude": {"exclusions": [f"{e['name'].split()[0].lower()}'s"]},
                "kind": {"kind": rnd.choice(["character", "place"])},
                "body": {"body": prose()},
            }[op]
            r = world.patch(f"{W}/entities/{eid}", json={"base_version": e["version"], **change})
            if r.status_code == 200:
                live[eid] = r.json()
        assert stored(db) == from_scratch(db), (step, op, change)


def test_a_new_name_rescans_only_the_texts_it_can_reach(world: Client, db):
    for i, body in enumerate(["Isolde walked to the harbour.", "Nobody here.", "Mordoch was late. Isolde too.",
                              "A word from Mordock."]):
        world.post(f"{W}/projects/book-one/chapters", json={"title": f"Ch {i}", "body": body})
    world.post(f"{W}/entities", json={"name": "Isolde"})
    w = db.scalar(select(World))
    before = matcher_for(db, w.id)
    db.add(Entity(world_id=w.id, name="Mordoch", kind="character", aliases=[], body="", created_by=w.created_by,
                  updated_by=w.created_by))
    db.flush()
    # the chapter that names it, and the one with a near miss of it ("Mordock")
    assert refresh_names(db, w.id, before) == 2
    db.commit()
    assert stored(db) == from_scratch(db)
    assert ("Mordock", "near_miss") in {(m[5], m[6]) for m in stored(db)}
