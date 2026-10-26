"""Margin notes: a line of a chapter starting with %% is a note to yourself. It stays in the chapter (and in its
exported file) but is not part of the story: not counted, not matched for names, not compiled
(docs/WORLD-MODEL.md §7).

Picture lines (docs/SPEC.md §17.3): a line with an image link to a picture and nothing else is treated as a margin
note is, in chapters, journal entries and entries' notes alike. The pattern has a twin in the frontend
(frontend/src/pictures.ts)."""

from __future__ import annotations

import re

MARGIN_RE = re.compile(r"^[ \t]*%%[^\n]*", re.M)
PICTURE_RE = re.compile(r"^[ \t]*!\[([^\]\n]*)\]\(picture:([0-9a-f-]{36})\)[ \t]*$", re.M)


def _blank(m: re.Match) -> str:
    return " " * len(m.group(0))


def without_pictures(text: str) -> str:
    """The text with its picture lines blanked out, keeping every other character where it was."""
    return PICTURE_RE.sub(_blank, text)


def story_text(text: str) -> str:
    """The chapter with its margin notes and picture lines blanked out, keeping every other character where it was."""
    return without_pictures(MARGIN_RE.sub(_blank, text))


def is_picture_line(line: str) -> bool:
    return PICTURE_RE.fullmatch(line) is not None


def without_margin_notes(text: str) -> str:
    """The chapter with its margin-note and picture lines removed, for the compiled manuscript."""
    return "\n".join(line for line in text.split("\n")
                     if not line.lstrip(" \t").startswith("%%") and not is_picture_line(line))


def picture_ids(text: str) -> set[str]:
    """The pictures a text's picture lines show, by id."""
    return {m.group(2) for m in PICTURE_RE.finditer(text)}
