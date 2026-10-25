"""The story's clock (docs/SPEC.md §13.1): when each chapter is set, and the happened order worked out from it.

Chapters have two orders. Told order is book order (projects in order, then chapters in theirs). Happened order sorts
them by their set time, then book order:

- a chapter's set time is its own time; else, unless it is marked as a tale or a flashback, the time of the nearest
  chapter before it in book order with a time of its own and no mark (an unset chapter carries on from the present it
  follows), or with none before it, the first such chapter after it;
- a tale or flashback with no time of its own is set sometime before the story: it sorts before every other chapter,
  and the time checks skip it;
- a chapter outside time is not on the clock at all (it is listed apart, and never carried on from);
- with no times and no marks, happened order is book order.

A bound on a fact or relationship is a chapter or a time. Both sit on the one clock: a chapter at its place in happened
order, a "from" time just before the chapters set at it, an "until" time just after them. A chapter with no set time
ignores time bounds. Nothing here is stored; it is worked out when read.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

INF = float("inf")
# where a position sorts: tales and flashbacks before the story, timed chapters by time, then unset ones
EARLY, TIMED, UNSET = 0, 1, 2


@dataclass
class Placed:
    id: uuid.UUID
    title: str
    project_id: uuid.UUID
    book: int
    own: float | None
    end: float | None
    label: str | None
    approx: bool
    outside: bool
    told_as: str | None
    set_time: float | None = None
    set_approx: bool = False
    early: bool = False
    place: int | None = None

    @property
    def comparable(self) -> bool:
        """On the clock at a known point: the time checks compare only these."""
        return self.place is not None and not self.early


def _num(x: Any) -> float | None:
    return None if x is None else float(x)


class Clock:
    """The current chapters (in book order, as `story_order` gives them) placed in happened order."""

    def __init__(self, order: list[tuple[Any, Any]]) -> None:
        self.chapters: list[Placed] = [
            Placed(id=c.id, title=c.title, project_id=p.id, book=i, own=_num(c.time_at), end=_num(c.time_end),
                   label=c.time_label, approx=bool(c.time_approx), outside=bool(c.outside_time), told_as=c.told_as)
            for i, (c, p) in enumerate(order)]
        present = [x for x in self.chapters if x.own is not None and x.told_as is None and not x.outside]
        for x in self.chapters:
            if x.outside:
                continue
            if x.own is not None:
                x.set_time, x.set_approx = x.own, x.approx
            elif x.told_as:
                x.early = True
            else:
                before = [y for y in present if y.book < x.book]
                after = [y for y in present if y.book > x.book]
                src = before[-1] if before else (after[0] if after else None)
                if src is not None:
                    x.set_time, x.set_approx = src.own, src.approx
        on = sorted((x for x in self.chapters if not x.outside), key=self._key)
        for i, x in enumerate(on):
            x.place = i
        self.happened: list[Placed] = on
        self.by_id: dict[uuid.UUID, Placed] = {x.id: x for x in self.chapters}

    @staticmethod
    def _key(x: Placed) -> tuple:
        if x.early:
            return (EARLY, 0.0, x.book)
        if x.set_time is not None:
            return (TIMED, x.set_time, x.book)
        return (UNSET, 0.0, x.book)

    @property
    def any_time(self) -> bool:
        return any(x.own is not None or x.outside or x.told_as for x in self.chapters)

    def get(self, chapter_id: uuid.UUID | None) -> Placed | None:
        return self.by_id.get(chapter_id) if chapter_id else None

    def pos(self, chapter_id: uuid.UUID | None) -> tuple | None:
        """A chapter's position on the clock, or None for one that isn't on it (outside time, retired, a draft)."""
        x = self.get(chapter_id)
        if x is None or x.place is None:
            return None
        if x.early:
            return (EARLY, 0.0, x.place)
        if x.set_time is not None:
            return (TIMED, x.set_time, x.place)
        return (UNSET, 0.0, x.place)

    def start(self, span: Any) -> tuple | None:
        """Where a span starts on the clock (None: from the start, or a bound that can't be placed)."""
        if getattr(span, "from_time", None) is not None:
            return (TIMED, float(span.from_time), -1)
        return self.pos(getattr(span, "from_chapter_id", None))

    def end(self, span: Any) -> tuple | None:
        """Where a span ends on the clock (None: to the end)."""
        if getattr(span, "until_time", None) is not None:
            return (TIMED, float(span.until_time), INF)
        return self.pos(getattr(span, "until_chapter_id", None))

    def holds(self, span: Any, chapter_id: uuid.UUID) -> bool:
        """Does a fact or relationship hold in this chapter? Outside time it always does (it is never compared); in a
        chapter outside time only what has no bounds holds. A chapter bound off the clock (retired, a draft) is
        ignored, as is a time bound in a chapter with no set time."""
        if getattr(span, "outside_time", False):
            return True
        x = self.get(chapter_id)
        if x is None:
            return True
        bounded = any(getattr(span, f, None) is not None
                      for f in ("from_chapter_id", "from_time", "until_chapter_id", "until_time"))
        if x.place is None:
            return not bounded
        f = self.get(getattr(span, "from_chapter_id", None))
        if f is not None and f.place is not None and x.place < f.place:
            return False
        u = self.get(getattr(span, "until_chapter_id", None))
        if u is not None and u.place is not None and x.place > u.place:
            return False
        if x.set_time is not None and not x.early:
            if getattr(span, "from_time", None) is not None and x.set_time < float(span.from_time):
                return False
            if getattr(span, "until_time", None) is not None and x.set_time > float(span.until_time):
                return False
        return True

    def backwards(self, span: Any) -> bool:
        """Does a span run backwards on the clock? Only when both ends can be compared."""
        if getattr(span, "from_time", None) is not None and getattr(span, "until_time", None) is not None:
            return float(span.from_time) > float(span.until_time)
        s, e = self.start(span), self.end(span)
        if s is None or e is None:
            return False
        # a time against a chapter with no set time can't be compared
        if (s[2] in (-1, INF) or e[2] in (-1, INF)) and (s[0] != TIMED or e[0] != TIMED):
            return False
        return s > e


def number_text(n: float) -> str:
    """312, 312.5, −800: whole numbers without decimals, a real minus sign."""
    s = f"{n:.6f}".rstrip("0").rstrip(".") if n != int(n) else str(int(n))
    return s.replace("-", "−")


def time_text(unit: str, units: str, at: float | None, end: float | None = None, label: str | None = None,
              approx: bool = False, outside: bool = False) -> str:
    """"year 312", "years 300–302", "about year −800", the label when there is one, or "outside time"."""
    if outside:
        return "outside time"
    if at is None:
        return ""
    if label:
        text = label
    elif end is not None and end != at:
        text = f"{units} {number_text(at)}–{number_text(end)}"
    else:
        text = f"{unit} {number_text(at)}"
    return f"about {text}" if approx and not label else text
