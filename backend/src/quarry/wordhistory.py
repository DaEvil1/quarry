"""Word history: how many words went into a chapter, and came out of it, between two of its revisions (SPEC §11.5).

Worked out once, when a revision is taken, and kept in the revision's `meta` (`added`, `removed`), so the project's
chart only sums. The comparison is a word diff of the story (margin notes left out), paragraph by paragraph first and
then word by word inside the paragraphs that changed. It is a rough picture by design: a passage moved between
chapters counts as cut in one and written in the other.

No database here: the migration that fills in the history of existing revisions uses it too.
"""

from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher

from .margin import story_text

WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")
# beyond this many word pairs a block is compared as two bags of words (fast, and still about right)
EXACT_LIMIT = 4_000_000


def _words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def _block(old: list[str], new: list[str]) -> tuple[int, int]:
    if not old:
        return len(new), 0
    if not new:
        return 0, len(old)
    if len(old) * len(new) > EXACT_LIMIT:
        a, b = Counter(old), Counter(new)
        return sum((b - a).values()), sum((a - b).values())
    added = removed = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return added, removed


def word_changes(old: str, new: str) -> tuple[int, int]:
    """Words added and words removed going from `old` to `new` (margin notes don't count)."""
    a = story_text(old).split("\n")
    b = story_text(new).split("\n")
    added = removed = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        plus, minus = _block(_words("\n".join(a[i1:i2])), _words("\n".join(b[j1:j2])))
        added += plus
        removed += minus
    return added, removed
