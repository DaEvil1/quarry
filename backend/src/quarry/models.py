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
ENTITY_KINDS = ("character", "place", "term", "faction", "object", "other")
# texts that are scanned for mentions; "chapter" joins with the editor (phase 4)
MENTION_SOURCES = ("item", "decision", "entity", "journal")
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
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


# one entry per name in a world, whatever the capitals
Index("uq_entities_world_name", Entity.world_id, func.lower(Entity.name), unique=True)


class ItemLink(Base):
    """An item tagged with what it is about. Targets are entities now; chapters join in phase 4."""

    __tablename__ = "item_links"
    __table_args__ = (CheckConstraint("target_table IN ('entity')", name="ck_item_links_target"),)

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
