"""Initial migration - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2024-12-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create associations table
    op.create_table(
        'associations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_associations_id'), 'associations', ['id'], unique=False)
    op.create_index(op.f('ix_associations_name'), 'associations', ['name'], unique=False)

    # Create variables table
    op.create_table(
        'variables',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('association_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('source_url', sa.String(length=500), nullable=True),
        sa.Column('verified', sa.Boolean(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['association_id'], ['associations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('association_id', 'key', name='uq_association_variable_key')
    )
    op.create_index(op.f('ix_variables_association_id'), 'variables', ['association_id'], unique=False)
    op.create_index(op.f('ix_variables_id'), 'variables', ['id'], unique=False)
    op.create_index(op.f('ix_variables_key'), 'variables', ['key'], unique=False)
    op.create_index(op.f('ix_variables_verified'), 'variables', ['verified'], unique=False)

    # Create locations table
    op.create_table(
        'locations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('association_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('geojson', sa.JSON(), nullable=False),
        sa.Column('properties', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['association_id'], ['associations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_locations_association_id'), 'locations', ['association_id'], unique=False)
    op.create_index(op.f('ix_locations_id'), 'locations', ['id'], unique=False)

    # Create scrape_logs table
    op.create_table(
        'scrape_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('association_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('variables_found', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['association_id'], ['associations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scrape_logs_association_id'), 'scrape_logs', ['association_id'], unique=False)
    op.create_index(op.f('ix_scrape_logs_id'), 'scrape_logs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_scrape_logs_id'), table_name='scrape_logs')
    op.drop_index(op.f('ix_scrape_logs_association_id'), table_name='scrape_logs')
    op.drop_table('scrape_logs')
    
    op.drop_index(op.f('ix_locations_id'), table_name='locations')
    op.drop_index(op.f('ix_locations_association_id'), table_name='locations')
    op.drop_table('locations')
    
    op.drop_index(op.f('ix_variables_verified'), table_name='variables')
    op.drop_index(op.f('ix_variables_key'), table_name='variables')
    op.drop_index(op.f('ix_variables_id'), table_name='variables')
    op.drop_index(op.f('ix_variables_association_id'), table_name='variables')
    op.drop_table('variables')
    
    op.drop_index(op.f('ix_associations_name'), table_name='associations')
    op.drop_index(op.f('ix_associations_id'), table_name='associations')
    op.drop_table('associations')
