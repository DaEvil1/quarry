"""Margin notes: a line of a chapter starting with %% is a note to yourself. It stays in the chapter (and in its
exported file) but is not part of the story: not counted, not matched for names, not compiled
(docs/WORLD-MODEL.md §7)."""

from __future__ import annotations

import re

MARGIN_RE = re.compile(r"^[ \t]*%%[^\n]*", re.M)


def story_text(text: str) -> str:
    """The chapter with its margin notes blanked out, keeping every other character where it was."""
    return MARGIN_RE.sub(lambda m: " " * len(m.group(0)), text)


def without_margin_notes(text: str) -> str:
    """The chapter with its margin-note lines removed, for the compiled manuscript."""
    return "\n".join(line for line in text.split("\n") if not line.lstrip(" \t").startswith("%%"))
