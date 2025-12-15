"""Add VennIntersection tables for logical combinations

Revision ID: 006_add_venn_intersections
Revises: 005_add_intl_scope
Create Date: 2025-12-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006_add_venn_intersections'
down_revision: Union[str, None] = '005_add_intl_scope'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create VennOperationType enum
    op.execute("""
        DO $$ BEGIN 
            CREATE TYPE vennoperationtype AS ENUM ('intersection', 'union', 'difference', 'exclusive'); 
        EXCEPTION 
            WHEN duplicate_object THEN null; 
        END $$;
    """)
    
    # Create venn_intersections table
    op.create_table(
        'venn_intersections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('display_label', sa.String(length=100), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('operation', postgresql.ENUM('intersection', 'union', 'difference', 'exclusive', name='vennoperationtype', create_type=False), nullable=False, server_default='intersection'),
        sa.Column('formula', sa.JSON(), nullable=True),
        sa.Column('variable_ids', sa.JSON(), nullable=True),
        sa.Column('include_ids', sa.JSON(), nullable=True),
        sa.Column('exclude_ids', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_venn_intersections_id'), 'venn_intersections', ['id'], unique=False)
    op.create_index(op.f('ix_venn_intersections_name'), 'venn_intersections', ['name'], unique=True)
    op.create_index(op.f('ix_venn_intersections_is_active'), 'venn_intersections', ['is_active'], unique=False)
    
    # Create venn_intersection_results table
    op.create_table(
        'venn_intersection_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('intersection_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('component_values', sa.JSON(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('is_stale', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('manual_override', sa.Boolean(), nullable=True),
        sa.Column('override_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['intersection_id'], ['venn_intersections.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'intersection_id', name='uq_venn_intersection_result')
    )
    op.create_index(op.f('ix_venn_intersection_results_id'), 'venn_intersection_results', ['id'], unique=False)
    op.create_index(op.f('ix_venn_intersection_results_organization_id'), 'venn_intersection_results', ['organization_id'], unique=False)
    op.create_index(op.f('ix_venn_intersection_results_intersection_id'), 'venn_intersection_results', ['intersection_id'], unique=False)
    op.create_index(op.f('ix_venn_intersection_results_is_stale'), 'venn_intersection_results', ['is_stale'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_venn_intersection_results_is_stale'), table_name='venn_intersection_results')
    op.drop_index(op.f('ix_venn_intersection_results_intersection_id'), table_name='venn_intersection_results')
    op.drop_index(op.f('ix_venn_intersection_results_organization_id'), table_name='venn_intersection_results')
    op.drop_index(op.f('ix_venn_intersection_results_id'), table_name='venn_intersection_results')
    op.drop_table('venn_intersection_results')
    
    op.drop_index(op.f('ix_venn_intersections_is_active'), table_name='venn_intersections')
    op.drop_index(op.f('ix_venn_intersections_name'), table_name='venn_intersections')
    op.drop_index(op.f('ix_venn_intersections_id'), table_name='venn_intersections')
    op.drop_table('venn_intersections')
    
    op.execute("DROP TYPE IF EXISTS vennoperationtype;")
