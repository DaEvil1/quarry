"""Database tables for phase 1: people, how they sign in, and the worlds and projects they write in.

Ids are UUIDs so that later phases can create rows on an offline phone and sync them up without clashes.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Boolean,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

PROJECT_KINDS = ("novel", "novella", "short", "other")
MEMBER_ROLES = ("owner",)
CHALLENGE_PURPOSES = ("setup", "login", "add_passkey")
# "experiment" items arrive with the editor (phase 4); the column accepts them already
ITEM_KINDS = ("spark", "question", "task", "experiment")
ITEM_STATUSES = ("open", "accepted", "rejected", "harvested", "deferred")
ENTITY_KINDS = ("character", "place", "faction", "culture", "species", "event", "object", "term", "other")
# canon: true in the book; planned: true in the author's head, not on the page yet; rumour: believed in the story
STANDINGS = ("canon", "planned", "rumour")
# texts that are scanned for mentions
MENTION_SOURCES = ("item", "decision", "entity", "journal", "chapter")
CHAPTER_STATES = ("current", "experiment", "retired")
# why a revision was taken: autosnap (idle, long session, leaving), checkpoint (Ctrl+S), state (retired, swapped
# in), restore (the text before a restore), conflict (a copy that lost to another device's save), start (the text a
# chapter began with: a restore, the demo, an experiment started as a copy; it counts as no words written)
REVISION_REASONS = ("autosnap", "checkpoint", "state", "restore", "conflict", "start")
# the statuses every project starts with (renamed, added, removed and ordered per project)
STARTING_STATUSES = ("raw", "rewritten", "polished")
# documents with revisions: chapters, and journal entries since they moved onto the editor (docs/SPEC.md §14.1.1)
REVISION_DOCS = ("chapter", "journal")
MENTION_KINDS = ("exact", "alias", "near_miss")
# what an item can be linked to: a bible entry, or the chapter or journal entry (with the passage) it came from
ITEM_LINK_TARGETS = ("entity", "chapter", "journal")
# a character's gender, read by the family tree for its words; NULL is "not set"
GENDERS = ("female", "male", "nonbinary")
# how a chapter is told, when not in the present of the story (docs/SPEC.md §13.1.2)
TOLD_AS = ("flashback", "tale")
INSERT_SIDES = ("before", "after")
# an era's colour (docs/SPEC.md §13.2.1): one of eight that work in both themes, each a pair of tokens
ERA_COLOURS = ("amber", "moss", "teal", "sky", "indigo", "plum", "rose", "rust")


def _time() -> Mapped[float | None]:
    """An in-world time: one sortable number (decimals and below zero allowed), never a calendar (SPEC §13.1.1)."""
    return mapped_column(Numeric(asdecimal=False))


class Base(DeclarativeBase):
    pass


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _updated() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _id()
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class World(Base):
    __tablename__ = "worlds"

    id: Mapped[uuid.UUID] = _id()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    # what in-world time is counted in, one and several ("year" / "years", "day" / "days")
    time_unit: Mapped[str] = mapped_column(String(40), nullable=False, default="year", server_default="year")
    time_units: Mapped[str] = mapped_column(String(40), nullable=False, default="years", server_default="years")
    # the chart's settings (docs/SPEC.md §13.7.2): {"shapes": {"duchy": "hexagon"}}, shapes for the world's own types
    chart: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    projects: Mapped[list[Project]] = relationship(
        back_populates="world", order_by="Project.position", cascade="all, delete-orphan"
    )


class WorldMember(Base):
    __tablename__ = "world_members"
    __table_args__ = (CheckConstraint(_in("role", MEMBER_ROLES), name="ck_world_members_role"),)

    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
                                               index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="owner")
    created_at: Mapped[datetime] = _created()


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("world_id", "slug", name="uq_projects_world_slug"),
        CheckConstraint(_in("kind", PROJECT_KINDS), name="ck_projects_kind"),
    )

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="novel")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # how many chapters without an entry, between two that name it, make a gap on its mentions strip
    gap_chapters: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    world: Mapped[World] = relationship(back_populates="projects")


class Passkey(Base):
    __tablename__ = "passkeys"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    credential_id: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transports: Mapped[list[str]] = mapped_column(ARRAY(String(20)), nullable=False, default=list)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = _created()
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = _created()
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # sha256 of the cookie value: a database leak does not hand out live sessions
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class AuthChallenge(Base):
    """A WebAuthn challenge waiting for its answer. Used once, then deleted; stale ones are swept."""

    __tablename__ = "auth_challenges"
    __table_args__ = (CheckConstraint(_in("purpose", CHALLENGE_PURPOSES), name="ck_auth_challenges_purpose"),)

    id: Mapped[uuid.UUID] = _id()
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    challenge: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Item(Base):
    """Anything that needs attention: a spark, a question, a task. Belongs to a world, and to a project or not."""

    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint(_in("kind", ITEM_KINDS), name="ck_items_kind"),
        CheckConstraint(_in("status", ITEM_STATUSES), name="ck_items_status"),
        CheckConstraint(_in("insert_side", INSERT_SIDES), name="ck_items_insert_side"),
    )

    # chosen by the client when it captures, so a capture replayed from an offline phone is not saved twice
    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="spark")
    title: Mapped[str | None] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    closed_note: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # an experiment that only adds chapters (docs/SPEC.md §13.6.1): its drafts go in before or after this chapter
    insert_at_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL",
                                                                             use_alter=True))
    insert_side: Mapped[str | None] = mapped_column(String(10))
    # where it came from: "phone", "desk", "share"
    source: Mapped[str | None] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    # when it was captured (an offline capture keeps its own time, not the time it synced)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Decision(Base):
    """A dated one-line verdict, optionally tied to the item it closed."""

    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    decided_on: Mapped[date] = mapped_column(Date, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Entity(Base):
    """A bible page of a world: a character, place, term, faction or object, with its other spellings."""

    __tablename__ = "entities"
    __table_args__ = (
        CheckConstraint(_in("kind", ENTITY_KINDS), name="ck_entities_kind"),
        CheckConstraint(_in("gender", GENDERS), name="ck_entities_gender"),
        CheckConstraint(_in("era_colour", ERA_COLOURS), name="ck_entities_era_colour"),
        CheckConstraint("NOT outside_time OR time_at IS NULL", name="ck_entities_outside_time"),
        CheckConstraint("time_chapter_id IS NULL OR (time_at IS NULL AND NOT outside_time)",
                        name="ck_entities_time_chapter"),
    )

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    # the level it lives at: one project's part of the bible, or NULL for the world's (shared by every project)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="character")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(200)), nullable=False, default=list)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # the one line shown on hover wherever the name appears
    summary: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    # off for names that are never ordinary words, so "isolde" counts too
    match_case: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # a character called "Varren Hale" is also matched as "Varren", unless another entry claims that word
    first_name_alias: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # "not in this sense": phrases where the name is an ordinary word ("rose garden")
    exclusions: Mapped[list[str]] = mapped_column(ARRAY(String(200)), nullable=False, default=list,
                                                  server_default="{}")
    # characters only (kept, unused, if the kind changes): female, male, nonbinary, or NULL for not set
    gender: Mapped[str | None] = mapped_column(String(20))
    # events (kept, unused, if the kind changes): when it happens (docs/SPEC.md §13.2.1): in a chapter (following its
    # time), a time, outside time, or none of them (not placed yet)
    time_at: Mapped[float | None] = _time()
    time_end: Mapped[float | None] = _time()
    time_label: Mapped[str | None] = mapped_column(String(200))
    time_approx: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    outside_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    time_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL",
                                                                        use_alter=True))
    # an era's colour (an event whose type is "era")
    era_colour: Mapped[str | None] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


# one entry per name in a world, whatever the capitals
Index("uq_entities_world_name", Entity.world_id, func.lower(Entity.name), unique=True)


class ItemLink(Base):
    """An item tagged with what it is about: a bible entry, or the chapter or journal entry it came from, with the
    passage it was made from (docs/SPEC.md §14.3)."""

    __tablename__ = "item_links"
    __table_args__ = (CheckConstraint(_in("target_table", ITEM_LINK_TARGETS), name="ck_item_links_target"),)

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    target_table: Mapped[str] = mapped_column(String(20), primary_key=True)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, index=True)
    # for a chapter or journal entry: the passage the item was made from
    passage: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class JournalEntry(Base):
    """Dated thinking on paper. Belongs to a world, and to a project or not."""

    __tablename__ = "journal"

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str | None] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Mention(Base):
    """Where a bible name (or something close to one) appears in a text. Computed on save, never edited by hand."""

    __tablename__ = "mentions"
    __table_args__ = (
        CheckConstraint(_in("source_table", MENTION_SOURCES), name="ck_mentions_source"),
        CheckConstraint(_in("kind", MENTION_KINDS), name="ck_mentions_kind"),
        Index("ix_mentions_source", "source_table", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    source_table: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # for a near miss: the entity it is probably meant to be
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False,
                                                 index=True)
    start: Mapped[int] = mapped_column(Integer, nullable=False)
    end: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_text: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)


class NameIgnore(Base):
    """A word marked "not a typo": never flagged as a near miss in this world again."""

    __tablename__ = "name_ignores"

    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), primary_key=True)
    token: Mapped[str] = mapped_column(String(200), primary_key=True)
    created_at: Mapped[datetime] = _created()


class Chapter(Base):
    """A unit of manuscript prose in a project.

    current: in the book, ordered by position. experiment: a draft, tied to the experiment item that tracks it (its
    position is its place among the experiment's drafts; the chapters it would replace are the item's range).
    retired: salvage, kept with its harvest notes.
    """

    __tablename__ = "chapters"
    __table_args__ = (
        CheckConstraint(_in("state", CHAPTER_STATES), name="ck_chapters_state"),
        CheckConstraint(_in("told_as", TOLD_AS), name="ck_chapters_told_as"),
        CheckConstraint("NOT outside_time OR time_at IS NULL", name="ck_chapters_outside_time"),
    )

    id: Mapped[uuid.UUID] = _id()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
                                                  index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="current")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pov_entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"))
    experiment_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # when it is set (docs/SPEC.md §13.1): a time (number, optional end, free label, "about"), outside time, or neither
    time_at: Mapped[float | None] = _time()
    time_end: Mapped[float | None] = _time()
    time_label: Mapped[str | None] = mapped_column(String(200))
    time_approx: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    outside_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # told as a flashback or a tale, or NULL for the present of the story
    told_as: Mapped[str | None] = mapped_column(String(20))
    # one optional line about the chapter, and where it stands (the project's statuses)
    summary: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    status_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapter_statuses.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class ChapterStatus(Base):
    """One stage a chapter can be at in a project (raw, rewritten, polished …). Ordered; the label is shown on every
    chapter that has it, so renaming it renames them all."""

    __tablename__ = "chapter_statuses"

    id: Mapped[uuid.UUID] = _id()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
                                                  index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = _created()


class Cut(Base):
    """A passage cut from a chapter into the project's bin. Kept forever: putting it back marks it, never removes it.
    Not matched for names, not counted, not compiled."""

    __tablename__ = "cuts"

    # chosen by the device that cut it, so a cut sent again from an offline phone is kept once
    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
                                                  index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"), index=True)
    # the chapter's title when it was cut, for when the chapter is gone
    chapter_title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # up to 80 characters either side, to find the place again
    before: Mapped[str] = mapped_column(Text, nullable=False, default="")
    after: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cut_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    put_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    put_back_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


class Revision(Base):
    """An immutable snapshot of a document's text. Append-only, never pruned on the server."""

    __tablename__ = "revisions"
    __table_args__ = (
        CheckConstraint(_in("doc_table", REVISION_DOCS), name="ck_revisions_doc"),
        CheckConstraint(_in("reason", REVISION_REASONS), name="ck_revisions_reason"),
        Index("ix_revisions_doc", "doc_table", "doc_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _id()
    doc_table: Mapped[str] = mapped_column(String(20), nullable=False)
    doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


class HarvestNote(Base):
    """What was alive in a retired chapter or a closed experiment, so it can be found without rereading it."""

    __tablename__ = "harvest_notes"

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False,
                                                  index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


class Fact(Base):
    """A labelled value about an entry ("eye colour: grey"), optionally true only from/until a chapter, with the
    passage that established it."""

    __tablename__ = "facts"
    __table_args__ = (
        CheckConstraint(_in("standing", STANDINGS), name="ck_facts_standing"),
        CheckConstraint("from_chapter_id IS NULL OR from_time IS NULL", name="ck_facts_from"),
        CheckConstraint("until_chapter_id IS NULL OR until_time IS NULL", name="ck_facts_until"),
    )

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False,
                                                 index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    from_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    until_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    # a bound can be an in-world time instead of a chapter (one or the other); outside time has no bounds at all
    from_time: Mapped[float | None] = _time()
    from_approx: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    until_time: Mapped[float | None] = _time()
    until_approx: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    outside_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    standing: Mapped[str] = mapped_column(String(20), nullable=False, default="canon")
    established_in_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id",
                                                                                  ondelete="SET NULL"))
    evidence: Mapped[str | None] = mapped_column(Text)
    # where it was planned (docs/SPEC.md §14.1.2): a journal entry and the passage it was worked out in. Never a place
    # in the story: it bounds nothing, and the checks never read it
    planned_in_journal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal.id", ondelete="SET NULL"),
                                                                    index=True)
    planned_evidence: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class FactLabel(Base):
    """The per-label switches of a kind (docs/SPEC.md §12.6): whether the label holds several values at once, whether
    every entry of the kind is expected to have it, and whether the "expect it?" prompt has been shown. Labels and
    values themselves are read from the facts; a row exists only once a switch was set or the prompt shown."""

    __tablename__ = "fact_labels"

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    several: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    expected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    asked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


Index("uq_fact_labels_world_kind_label", FactLabel.world_id, FactLabel.kind, func.lower(FactLabel.label), unique=True)


class RelationType(Base):
    """One kind of connection a world uses, between a kind on each side ("*" for any)."""

    __tablename__ = "relation_types"

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    a_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    b_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    # how it reads from the B side; NULL means it reads the same both ways
    reverse_label: Mapped[str | None] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # its relationships carry a role in the group on the B side ("member of" the Lamp Guild · Captain)
    has_role: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class Relationship(Base):
    """Two entries joined by a type: A <label> B, read back from B as B <reverse> A."""

    __tablename__ = "relationships"
    __table_args__ = (
        CheckConstraint(_in("standing", STANDINGS), name="ck_relationships_standing"),
        CheckConstraint("from_chapter_id IS NULL OR from_time IS NULL", name="ck_relationships_from"),
        CheckConstraint("until_chapter_id IS NULL OR until_time IS NULL", name="ck_relationships_until"),
    )

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("relation_types.id", ondelete="RESTRICT"), nullable=False)
    a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    from_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    until_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    # a bound can be an in-world time instead of a chapter (one or the other); outside time has no bounds at all
    from_time: Mapped[float | None] = _time()
    from_approx: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    until_time: Mapped[float | None] = _time()
    until_approx: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    outside_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    standing: Mapped[str] = mapped_column(String(20), nullable=False, default="canon")
    established_in_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id",
                                                                                  ondelete="SET NULL"))
    evidence: Mapped[str | None] = mapped_column(Text)
    # where it was planned (docs/SPEC.md §14.1.2): a journal entry and the passage it was worked out in. Never a place
    # in the story: it bounds nothing, and the checks never read it
    planned_in_journal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal.id", ondelete="SET NULL"),
                                                                    index=True)
    planned_evidence: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    # the A side's role in the B side's group (for a type with a role): free text, time-bounded with the relationship
    role: Mapped[str | None] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class Role(Base):
    """A role's switch across the world (docs/SPEC.md §13.4): whether only one may hold it in a group at a time. Roles
    themselves are read from the relationships; a row exists only once the switch has been set."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    one_at_a_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


Index("uq_roles_world_role", Role.world_id, func.lower(Role.role), unique=True)


class DecisionLink(Base):
    """A decision tagged with the bible entries it is about."""

    __tablename__ = "decision_links"

    decision_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("decisions.id", ondelete="CASCADE"), primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True,
                                                 index=True)


class Presence(Base):
    """Where an entry (usually a character) is in a chapter: an explicit "is at", one place per chapter."""

    __tablename__ = "presence"
    __table_args__ = (UniqueConstraint("entity_id", "chapter_id", name="uq_presence_entity_chapter"),)

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    place_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False,
                                                  index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


RESOLUTION_OUTCOMES = ("intentional", "later", "not_connected")


class Resolution(Base):
    """How a companion finding was settled: intentional (never flagged again), later (kept on a list), or for an
    unrecorded connection, not connected. `key` names the finding within its rule (entries, chapter …)."""

    __tablename__ = "resolutions"
    __table_args__ = (
        UniqueConstraint("world_id", "rule", "key", name="uq_resolutions_world_rule_key"),
        CheckConstraint(_in("outcome", RESOLUTION_OUTCOMES), name="ck_resolutions_outcome"),
    )

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    rule: Mapped[str] = mapped_column(String(40), nullable=False)
    key: Mapped[str] = mapped_column(String(300), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


class SessionNote(Base):
    """Getting back into a chapter: where the writer stopped and the note they left for next time."""

    __tablename__ = "session_notes"

    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cursor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = _updated()


class ExperimentRange(Base):
    """The current chapters an experiment would replace, in order (docs/SPEC.md §13.6.1). None for one that only
    adds; one for a single-chapter experiment."""

    __tablename__ = "experiment_ranges"

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), primary_key=True,
                                                  index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RetireReview(Base):
    """What a review before retiring changed (docs/SPEC.md §13.6.2): each row kept, moved, marked planned or dropped,
    as it was before, for Undo and Reinstate. Bookkeeping, like resolutions: not exported."""

    __tablename__ = "retire_reviews"

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    changes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


class Telling(Base):
    """A passage that tells of an event (docs/SPEC.md §13.2.3): recorded from the prose with "Record as event". Names
    inside it don't count as appearing (telling of the dead is history). Recorded from a journal entry instead, it is
    a note (docs/SPEC.md §14.1.2): "Noted in", never a telling, and never a place in the story."""

    __tablename__ = "tellings"
    __table_args__ = (CheckConstraint("chapter_id IS NULL OR journal_id IS NULL", name="ck_tellings_source"),)

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False,
                                                index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"), index=True)
    journal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("journal.id", ondelete="SET NULL"), index=True)
    passage: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()


class ChartPin(Base):
    """Where a place was dragged to on the chart (docs/SPEC.md §13.7.3), relative to its container (none: the top
    level). A pin belongs to a place in a container, so a place that changes container keeps its old pin and is laid
    out fresh in the new one. The only thing the chart stores."""

    __tablename__ = "chart_pins"

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False,
                                                index=True)
    container_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = _updated()


Index("uq_chart_pins_place_container", ChartPin.place_id,
      func.coalesce(ChartPin.container_id, text("'00000000-0000-0000-0000-000000000000'::uuid")), unique=True)
