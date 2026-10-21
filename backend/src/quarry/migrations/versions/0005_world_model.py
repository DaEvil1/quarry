"""The world model: entry fields, facts, relationship types and relationships, decision links.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22 01:45:36.739303
"""
import uuid

from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('relation_types',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('a_kind', sa.String(length=20), nullable=False),
    sa.Column('b_kind', sa.String(length=20), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('reverse_label', sa.String(length=100), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_relation_types_world_id'), 'relation_types', ['world_id'], unique=False)
    op.create_table('decision_links',
    sa.Column('decision_id', sa.UUID(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['decision_id'], ['decisions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('decision_id', 'entity_id')
    )
    op.create_index(op.f('ix_decision_links_entity_id'), 'decision_links', ['entity_id'], unique=False)
    op.create_table('facts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('from_chapter_id', sa.UUID(), nullable=True),
    sa.Column('until_chapter_id', sa.UUID(), nullable=True),
    sa.Column('standing', sa.String(length=20), nullable=False),
    sa.Column('established_in_chapter_id', sa.UUID(), nullable=True),
    sa.Column('evidence', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("standing IN ('canon', 'planned', 'rumour')", name='ck_facts_standing'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['established_in_chapter_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['from_chapter_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['until_chapter_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_facts_entity_id'), 'facts', ['entity_id'], unique=False)
    op.create_index(op.f('ix_facts_world_id'), 'facts', ['world_id'], unique=False)
    op.create_table('relationships',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('type_id', sa.UUID(), nullable=False),
    sa.Column('a_id', sa.UUID(), nullable=False),
    sa.Column('b_id', sa.UUID(), nullable=False),
    sa.Column('from_chapter_id', sa.UUID(), nullable=True),
    sa.Column('until_chapter_id', sa.UUID(), nullable=True),
    sa.Column('standing', sa.String(length=20), nullable=False),
    sa.Column('established_in_chapter_id', sa.UUID(), nullable=True),
    sa.Column('evidence', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("standing IN ('canon', 'planned', 'rumour')", name='ck_relationships_standing'),
    sa.ForeignKeyConstraint(['a_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['b_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['established_in_chapter_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['from_chapter_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['type_id'], ['relation_types.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['until_chapter_id'], ['chapters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_relationships_a_id'), 'relationships', ['a_id'], unique=False)
    op.create_index(op.f('ix_relationships_b_id'), 'relationships', ['b_id'], unique=False)
    op.create_index(op.f('ix_relationships_world_id'), 'relationships', ['world_id'], unique=False)
    op.add_column('entities', sa.Column('summary', sa.String(length=300), server_default='', nullable=False))
    op.add_column('entities', sa.Column('match_case', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('entities', sa.Column('first_name_alias', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('entities', sa.Column('exclusions', sa.ARRAY(sa.String(length=200)), server_default='{}', nullable=False))
    # new kinds (check constraints are not compared by autogenerate)
    op.drop_constraint('ck_entities_kind', 'entities', type_='check')
    op.create_check_constraint('ck_entities_kind', 'entities',
                               "kind IN ('character', 'place', 'faction', 'culture', 'event', 'object', 'term', 'other')")
    # every existing world gets the starting relationship types
    from quarry.vocabulary import STARTING_TYPES

    conn = op.get_bind()
    types = sa.table('relation_types', sa.column('id', sa.UUID()), sa.column('world_id', sa.UUID()),
                     sa.column('a_kind', sa.String()), sa.column('b_kind', sa.String()),
                     sa.column('label', sa.String()), sa.column('reverse_label', sa.String()),
                     sa.column('position', sa.Integer()))
    rows = []
    for (world_id,) in conn.execute(sa.text("SELECT id FROM worlds")):
        for i, (a, b, label, reverse) in enumerate(STARTING_TYPES):
            rows.append({"id": uuid.uuid4(), "world_id": world_id, "a_kind": a, "b_kind": b, "label": label,
                         "reverse_label": reverse, "position": i})
    if rows:
        op.bulk_insert(types, rows)


def downgrade() -> None:
    op.execute("UPDATE entities SET kind = 'other' WHERE kind IN ('culture', 'event')")
    op.drop_constraint('ck_entities_kind', 'entities', type_='check')
    op.create_check_constraint('ck_entities_kind', 'entities',
                               "kind IN ('character', 'place', 'term', 'faction', 'object', 'other')")
    op.drop_column('entities', 'exclusions')
    op.drop_column('entities', 'first_name_alias')
    op.drop_column('entities', 'match_case')
    op.drop_column('entities', 'summary')
    op.drop_index(op.f('ix_relationships_world_id'), table_name='relationships')
    op.drop_index(op.f('ix_relationships_b_id'), table_name='relationships')
    op.drop_index(op.f('ix_relationships_a_id'), table_name='relationships')
    op.drop_table('relationships')
    op.drop_index(op.f('ix_facts_world_id'), table_name='facts')
    op.drop_index(op.f('ix_facts_entity_id'), table_name='facts')
    op.drop_table('facts')
    op.drop_index(op.f('ix_decision_links_entity_id'), table_name='decision_links')
    op.drop_table('decision_links')
    op.drop_index(op.f('ix_relation_types_world_id'), table_name='relation_types')
    op.drop_table('relation_types')
