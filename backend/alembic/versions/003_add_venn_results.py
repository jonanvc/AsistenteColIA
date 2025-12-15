"""Add VennResult table

Revision ID: 003_add_venn_results
Revises: 002_rename_associations_to_organizations
Create Date: 2025-01-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_venn_results'
down_revision: Union[str, None] = '002_rename_to_organizations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create VennResultSource enum type using raw SQL (checkfirst)
    op.execute("DO $$ BEGIN CREATE TYPE vennresultsource AS ENUM ('MANUAL', 'AUTOMATIC', 'MIXED'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    from sqlalchemy.dialects import postgresql
    
    # Create venn_variables table first (required for foreign key)
    op.create_table(
        'venn_variables',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('data_type', sa.String(50), server_default='list'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_venn_variables_id', 'venn_variables', ['id'])
    op.create_index('ix_venn_variables_name', 'venn_variables', ['name'], unique=True)
    
    # Create venn_proxies table
    op.create_table(
        'venn_proxies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('venn_variable_id', sa.Integer(), nullable=False),
        sa.Column('term', sa.String(255), nullable=False),
        sa.Column('is_regex', sa.Boolean(), server_default='false'),
        sa.Column('weight', sa.Float(), server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['venn_variable_id'], ['venn_variables.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_venn_proxies_id', 'venn_proxies', ['id'])
    op.create_index('ix_venn_proxies_venn_variable_id', 'venn_proxies', ['venn_variable_id'])
    
    # Create venn_results table
    op.create_table(
        'venn_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('venn_variable_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.Boolean(), nullable=False, default=False),
        sa.Column('source', postgresql.ENUM('MANUAL', 'AUTOMATIC', 'MIXED', name='vennresultsource', create_type=False), nullable=False, server_default='MANUAL'),
        sa.Column('search_score', sa.Float(), nullable=True),
        sa.Column('matched_proxies', sa.JSON(), nullable=True),
        sa.Column('source_urls', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['venn_variable_id'], ['venn_variables.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'venn_variable_id', name='uq_venn_result_org_var')
    )
    
    # Create indexes
    op.create_index('ix_venn_results_id', 'venn_results', ['id'])
    op.create_index('ix_venn_results_organization_id', 'venn_results', ['organization_id'])
    op.create_index('ix_venn_results_venn_variable_id', 'venn_results', ['venn_variable_id'])


def downgrade() -> None:
    # Drop venn_results indexes and table
    op.drop_index('ix_venn_results_venn_variable_id', table_name='venn_results')
    op.drop_index('ix_venn_results_organization_id', table_name='venn_results')
    op.drop_index('ix_venn_results_id', table_name='venn_results')
    op.drop_table('venn_results')
    
    # Drop venn_proxies indexes and table
    op.drop_index('ix_venn_proxies_venn_variable_id', table_name='venn_proxies')
    op.drop_index('ix_venn_proxies_id', table_name='venn_proxies')
    op.drop_table('venn_proxies')
    
    # Drop venn_variables indexes and table
    op.drop_index('ix_venn_variables_name', table_name='venn_variables')
    op.drop_index('ix_venn_variables_id', table_name='venn_variables')
    op.drop_table('venn_variables')
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS vennresultsource;")
