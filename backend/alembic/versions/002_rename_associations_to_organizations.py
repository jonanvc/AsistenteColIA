"""
Rename associations table to organizations

Revision ID: 002
Revises: 001_initial
Create Date: 2024-01-15

This migration renames the 'associations' table to 'organizations'
and updates all related foreign keys and constraints.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_rename_to_organizations'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy.dialects import postgresql
    
    # Create TerritorialScope enum
    op.execute("DO $$ BEGIN CREATE TYPE territorialscope AS ENUM ('MUNICIPAL', 'DEPARTAMENTAL', 'REGIONAL', 'NACIONAL'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Create OrganizationApproach enum
    op.execute("DO $$ BEGIN CREATE TYPE organizationapproach AS ENUM ('BOTTOM_UP', 'TOP_DOWN', 'MIXED', 'UNKNOWN'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Rename the main table
    op.rename_table('associations', 'organizations')
    
    # Update indexes on organizations table
    op.drop_index('ix_associations_id', table_name='organizations')
    op.drop_index('ix_associations_name', table_name='organizations')
    op.create_index('ix_organizations_id', 'organizations', ['id'], unique=False)
    op.create_index('ix_organizations_name', 'organizations', ['name'], unique=False)
    
    # Add new columns for women-led peace organizations
    op.add_column('organizations', sa.Column('years_active', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('women_count', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('leader_is_woman', sa.Boolean(), nullable=True, default=True))
    op.add_column('organizations', sa.Column('leader_name', sa.String(200), nullable=True))
    op.add_column('organizations', sa.Column('approach', postgresql.ENUM('BOTTOM_UP', 'TOP_DOWN', 'MIXED', 'UNKNOWN', name='organizationapproach', create_type=False), nullable=True))
    
    # Add territorial scope columns
    op.add_column('organizations', sa.Column('territorial_scope', postgresql.ENUM('MUNICIPAL', 'DEPARTAMENTAL', 'REGIONAL', 'NACIONAL', name='territorialscope', create_type=False), nullable=True))
    op.add_column('organizations', sa.Column('department_code', sa.String(10), nullable=True))
    op.add_column('organizations', sa.Column('municipality_code', sa.String(10), nullable=True))
    op.add_column('organizations', sa.Column('department_codes', sa.JSON(), nullable=True))
    op.add_column('organizations', sa.Column('is_peace_building', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('organizations', sa.Column('verified', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('organizations', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    
    # Create indexes for new columns
    op.create_index('ix_organizations_territorial_scope', 'organizations', ['territorial_scope'])
    op.create_index('ix_organizations_department_code', 'organizations', ['department_code'])
    
    # Rename foreign key columns in related tables
    
    # Variables table
    op.alter_column('variables', 'association_id', new_column_name='organization_id')
    op.drop_index('ix_variables_association_id', table_name='variables')
    op.create_index('ix_variables_organization_id', 'variables', ['organization_id'], unique=False)
    # Drop and recreate the unique constraint and foreign key
    op.drop_constraint('uq_association_variable_key', 'variables', type_='unique')
    op.drop_constraint('variables_association_id_fkey', 'variables', type_='foreignkey')
    op.create_unique_constraint('uq_organization_variable_key', 'variables', ['organization_id', 'key'])
    op.create_foreign_key('variables_organization_id_fkey', 'variables', 'organizations', ['organization_id'], ['id'])
    
    # Locations table
    op.alter_column('locations', 'association_id', new_column_name='organization_id')
    op.drop_index('ix_locations_association_id', table_name='locations')
    op.create_index('ix_locations_organization_id', 'locations', ['organization_id'], unique=False)
    op.drop_constraint('locations_association_id_fkey', 'locations', type_='foreignkey')
    op.create_foreign_key('locations_organization_id_fkey', 'locations', 'organizations', ['organization_id'], ['id'])
    
    # Scrape_logs table
    op.alter_column('scrape_logs', 'association_id', new_column_name='organization_id')
    op.drop_index('ix_scrape_logs_association_id', table_name='scrape_logs')
    op.create_index('ix_scrape_logs_organization_id', 'scrape_logs', ['organization_id'], unique=False)
    op.drop_constraint('scrape_logs_association_id_fkey', 'scrape_logs', type_='foreignkey')
    op.create_foreign_key('scrape_logs_organization_id_fkey', 'scrape_logs', 'organizations', ['organization_id'], ['id'])


def downgrade() -> None:
    # Reverse all changes
    
    # Scrape_logs table
    op.drop_constraint('scrape_logs_organization_id_fkey', 'scrape_logs', type_='foreignkey')
    op.drop_index('ix_scrape_logs_organization_id', table_name='scrape_logs')
    op.alter_column('scrape_logs', 'organization_id', new_column_name='association_id')
    op.create_index('ix_scrape_logs_association_id', 'scrape_logs', ['association_id'], unique=False)
    op.create_foreign_key('scrape_logs_association_id_fkey', 'scrape_logs', 'associations', ['association_id'], ['id'])
    
    # Locations table
    op.drop_constraint('locations_organization_id_fkey', 'locations', type_='foreignkey')
    op.drop_index('ix_locations_organization_id', table_name='locations')
    op.alter_column('locations', 'organization_id', new_column_name='association_id')
    op.create_index('ix_locations_association_id', 'locations', ['association_id'], unique=False)
    op.create_foreign_key('locations_association_id_fkey', 'locations', 'associations', ['association_id'], ['id'])
    
    # Variables table
    op.drop_constraint('variables_organization_id_fkey', 'variables', type_='foreignkey')
    op.drop_constraint('uq_organization_variable_key', 'variables', type_='unique')
    op.drop_index('ix_variables_organization_id', table_name='variables')
    op.alter_column('variables', 'organization_id', new_column_name='association_id')
    op.create_index('ix_variables_association_id', 'variables', ['association_id'], unique=False)
    op.create_unique_constraint('uq_association_variable_key', 'variables', ['association_id', 'key'])
    op.create_foreign_key('variables_association_id_fkey', 'variables', 'associations', ['association_id'], ['id'])
    
    # Drop indexes for new columns
    op.drop_index('ix_organizations_department_code', table_name='organizations')
    op.drop_index('ix_organizations_territorial_scope', table_name='organizations')
    
    # Drop new columns
    op.drop_column('organizations', 'verified_at')
    op.drop_column('organizations', 'verified')
    op.drop_column('organizations', 'is_peace_building')
    op.drop_column('organizations', 'department_codes')
    op.drop_column('organizations', 'municipality_code')
    op.drop_column('organizations', 'department_code')
    op.drop_column('organizations', 'territorial_scope')
    op.drop_column('organizations', 'approach')
    op.drop_column('organizations', 'leader_name')
    op.drop_column('organizations', 'leader_is_woman')
    op.drop_column('organizations', 'women_count')
    op.drop_column('organizations', 'years_active')
    
    # Rename the main table back
    op.drop_index('ix_organizations_id', table_name='organizations')
    op.drop_index('ix_organizations_name', table_name='organizations')
    op.rename_table('organizations', 'associations')
    op.create_index('ix_associations_id', 'associations', ['id'], unique=False)
    op.create_index('ix_associations_name', 'associations', ['name'], unique=False)
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS organizationapproach;")
    op.execute("DROP TYPE IF EXISTS territorialscope;")
