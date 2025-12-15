"""Add verification fields to VennResult table

Revision ID: 004_add_venn_result_verification
Revises: 003_add_venn_results
Create Date: 2025-01-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_venn_verification'
down_revision: Union[str, None] = '003_add_venn_results'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy.dialects import postgresql
    
    # Create VennResultStatus enum type using raw SQL
    op.execute("DO $$ BEGIN CREATE TYPE vennresultstatus AS ENUM ('PENDING', 'VERIFIED', 'REJECTED', 'MODIFIED'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Create scraping_sessions table (required for scraped_data)
    op.create_table(
        'scraping_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), server_default='in_progress'),
        sa.Column('total_urls', sa.Integer(), server_default='0'),
        sa.Column('urls_processed', sa.Integer(), server_default='0'),
        sa.Column('variables_found', sa.Integer(), server_default='0'),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scraping_sessions_id', 'scraping_sessions', ['id'])
    op.create_index('ix_scraping_sessions_organization_id', 'scraping_sessions', ['organization_id'])
    
    # Create scraped_data table
    op.create_table(
        'scraped_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('variable_key', sa.String(100), nullable=False),
        sa.Column('variable_value', sa.JSON(), nullable=False),
        sa.Column('source_url', sa.String(500), nullable=False),
        sa.Column('source_context', sa.Text(), nullable=True),
        sa.Column('auto_verified', sa.Boolean(), server_default='false'),
        sa.Column('auto_verification_score', sa.Float(), nullable=True),
        sa.Column('auto_verification_reason', sa.Text(), nullable=True),
        sa.Column('manually_verified', sa.Boolean(), nullable=True),
        sa.Column('verified_by', sa.String(100), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['session_id'], ['scraping_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scraped_data_id', 'scraped_data', ['id'])
    op.create_index('ix_scraped_data_session_id', 'scraped_data', ['session_id'])
    op.create_index('ix_scraped_data_organization_id', 'scraped_data', ['organization_id'])
    op.create_index('ix_scraped_data_variable_key', 'scraped_data', ['variable_key'])
    
    # Add verification columns to venn_results table
    op.add_column(
        'venn_results',
        sa.Column(
            'verification_status', 
            postgresql.ENUM('PENDING', 'VERIFIED', 'REJECTED', 'MODIFIED', name='vennresultstatus', create_type=False),
            nullable=False,
            server_default='PENDING'
        )
    )
    op.add_column(
        'venn_results',
        sa.Column('verified_by', sa.String(100), nullable=True)
    )
    op.add_column(
        'venn_results',
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'venn_results',
        sa.Column('verification_notes', sa.Text(), nullable=True)
    )
    op.add_column(
        'venn_results',
        sa.Column('original_value', sa.Boolean(), nullable=True)
    )
    op.add_column(
        'venn_results',
        sa.Column('original_score', sa.Float(), nullable=True)
    )
    
    # Create index on verification_status for efficient filtering
    op.create_index(
        'ix_venn_results_verification_status', 
        'venn_results', 
        ['verification_status']
    )


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_venn_results_verification_status', table_name='venn_results')
    
    # Drop columns from venn_results
    op.drop_column('venn_results', 'original_score')
    op.drop_column('venn_results', 'original_value')
    op.drop_column('venn_results', 'verification_notes')
    op.drop_column('venn_results', 'verified_at')
    op.drop_column('venn_results', 'verified_by')
    op.drop_column('venn_results', 'verification_status')
    
    # Drop scraped_data table and indexes
    op.drop_index('ix_scraped_data_variable_key', table_name='scraped_data')
    op.drop_index('ix_scraped_data_organization_id', table_name='scraped_data')
    op.drop_index('ix_scraped_data_session_id', table_name='scraped_data')
    op.drop_index('ix_scraped_data_id', table_name='scraped_data')
    op.drop_table('scraped_data')
    
    # Drop scraping_sessions table and indexes
    op.drop_index('ix_scraping_sessions_organization_id', table_name='scraping_sessions')
    op.drop_index('ix_scraping_sessions_id', table_name='scraping_sessions')
    op.drop_table('scraping_sessions')
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS vennresultstatus;")
