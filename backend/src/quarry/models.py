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
    ForeignKey,
    Index,
    Boolean,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

PROJECT_KINDS = ("novel", "novella", "short", "other")
MEMBER_ROLES = ("owner",)
CHALLENGE_PURPOSES = ("setup", "login", "add_passkey")
# "experiment" items arrive with the editor (phase 4); the column accepts them already
ITEM_KINDS = ("spark", "question", "task", "experiment")
ITEM_STATUSES = ("open", "accepted", "rejected", "harvested", "deferred")
ENTITY_KINDS = ("character", "place", "faction", "culture", "event", "object", "term", "other")
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
REVISION_DOCS = ("chapter",)
MENTION_KINDS = ("exact", "alias", "near_miss")


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
    )

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
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
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


# one entry per name in a world, whatever the capitals
Index("uq_entities_world_name", Entity.world_id, func.lower(Entity.name), unique=True)


class ItemLink(Base):
    """An item tagged with what it is about: a bible entry or a chapter."""

    __tablename__ = "item_links"
    __table_args__ = (CheckConstraint("target_table IN ('entity', 'chapter')", name="ck_item_links_target"),)

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    target_table: Mapped[str] = mapped_column(String(20), primary_key=True)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, index=True)
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

    current: in the book, ordered by position. experiment: an alternate draft, tied to the experiment item that
    tracks it and to the chapter it would replace (if any). retired: salvage, kept with its harvest notes.
    """

    __tablename__ = "chapters"
    __table_args__ = (CheckConstraint(_in("state", CHAPTER_STATES), name="ck_chapters_state"),)

    id: Mapped[uuid.UUID] = _id()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
                                                  index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="current")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pov_entity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"))
    experiment_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"))
    replaces_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    __table_args__ = (CheckConstraint(_in("standing", STANDINGS), name="ck_facts_standing"),)

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False,
                                                 index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    from_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    until_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    standing: Mapped[str] = mapped_column(String(20), nullable=False, default="canon")
    established_in_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id",
                                                                                  ondelete="SET NULL"))
    evidence: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


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


class Relationship(Base):
    """Two entries joined by a type: A <label> B, read back from B as B <reverse> A."""

    __tablename__ = "relationships"
    __table_args__ = (CheckConstraint(_in("standing", STANDINGS), name="ck_relationships_standing"),)

    id: Mapped[uuid.UUID] = _id()
    world_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True)
    type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("relation_types.id", ondelete="RESTRICT"), nullable=False)
    a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    from_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    until_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id", ondelete="SET NULL"))
    standing: Mapped[str] = mapped_column(String(20), nullable=False, default="canon")
    established_in_chapter_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chapters.id",
                                                                                  ondelete="SET NULL"))
    evidence: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


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
