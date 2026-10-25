"""The chart (SPEC §13.7): pins for places dragged on it, relative to their container, and the chart's settings on the
world (shapes for the world's own place types).

Nothing changes for existing data: no place is pinned, so every chart starts laid out automatically, and the settings
start empty. The direction types (north of / south of, east of / west of) came with 0010.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-26 12:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('worlds', sa.Column('chart', postgresql.JSONB(astext_type=sa.Text()), server_default='{}',
                                      nullable=False))
    op.create_table('chart_pins',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('world_id', sa.UUID(), nullable=False),
    sa.Column('place_id', sa.UUID(), nullable=False),
    sa.Column('container_id', sa.UUID(), nullable=True),
    sa.Column('x', sa.Float(), nullable=False),
    sa.Column('y', sa.Float(), nullable=False),
    sa.Column('updated_by', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['container_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['place_id'], ['entities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['world_id'], ['worlds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chart_pins_world_id'), 'chart_pins', ['world_id'], unique=False)
    op.create_index(op.f('ix_chart_pins_place_id'), 'chart_pins', ['place_id'], unique=False)
    op.create_index(op.f('ix_chart_pins_container_id'), 'chart_pins', ['container_id'], unique=False)
    op.execute("CREATE UNIQUE INDEX uq_chart_pins_place_container ON chart_pins "
               "(place_id, coalesce(container_id, '00000000-0000-0000-0000-000000000000'::uuid))")


def downgrade() -> None:
    op.drop_index('uq_chart_pins_place_container', table_name='chart_pins')
    op.drop_index(op.f('ix_chart_pins_container_id'), table_name='chart_pins')
    op.drop_index(op.f('ix_chart_pins_place_id'), table_name='chart_pins')
    op.drop_index(op.f('ix_chart_pins_world_id'), table_name='chart_pins')
    op.drop_table('chart_pins')
    op.drop_column('worlds', 'chart')
