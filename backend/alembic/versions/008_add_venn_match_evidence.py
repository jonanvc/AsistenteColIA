"""Add VennMatchEvidence table for match traceability

Revision ID: 008_add_venn_match_evidence
Revises: 007_add_venn_proxy_territorial
Create Date: 2025-01-17

Adds the venn_match_evidence table to store detailed evidence of proxy matches.
This enables full traceability and manual verification of automatic results.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '008_add_venn_match_evidence'
down_revision = '007_add_venn_proxy_territorial'
branch_labels = None
depends_on = None


def upgrade():
    """Create venn_match_evidence table."""
    
    # Create source_type enum
    source_type = sa.Enum(
        'main_page', 'subpage', 'pdf', 'social_media', 'news',
        'government', 'registry', 'search_result', 'description', 'other',
        name='sourcetype'
    )
    source_type.create(op.get_bind(), checkfirst=True)
    
    # Create the evidence table
    op.create_table(
        'venn_match_evidence',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        
        # Links to VennResult and VennProxy
        sa.Column('venn_result_id', sa.Integer(), sa.ForeignKey('venn_results.id'), nullable=False, index=True),
        sa.Column('venn_proxy_id', sa.Integer(), sa.ForeignKey('venn_proxies.id'), nullable=False, index=True),
        
        # Source information
        sa.Column('source_url', sa.String(1000), nullable=False),
        sa.Column('source_type', source_type, nullable=False, server_default='main_page'),
        
        # Location within document
        sa.Column('text_fragment', sa.Text(), nullable=True),
        sa.Column('matched_text', sa.String(500), nullable=True),
        sa.Column('xpath', sa.String(500), nullable=True),
        sa.Column('css_selector', sa.String(500), nullable=True),
        sa.Column('paragraph_number', sa.Integer(), nullable=True),
        sa.Column('section_title', sa.String(255), nullable=True),
        
        # Match quality
        sa.Column('match_score', sa.Float(), default=1.0),
        sa.Column('is_exact_match', sa.Boolean(), default=True),
        
        # Scraping context
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('scraping_session_id', sa.Integer(), sa.ForeignKey('scraping_sessions.id'), nullable=True),
        sa.Column('page_title', sa.String(500), nullable=True),
        sa.Column('page_language', sa.String(10), nullable=True),
        
        # User validation
        sa.Column('is_valid', sa.Boolean(), nullable=True),
        sa.Column('validated_by', sa.String(100), nullable=True),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('validation_notes', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        comment='Stores evidence/proof of proxy matches for verification'
    )
    
    # Create indexes for common queries
    op.create_index('ix_venn_match_evidence_result_proxy', 'venn_match_evidence', ['venn_result_id', 'venn_proxy_id'])
    op.create_index('ix_venn_match_evidence_validation', 'venn_match_evidence', ['is_valid'])


def downgrade():
    """Remove venn_match_evidence table."""
    op.drop_index('ix_venn_match_evidence_validation', 'venn_match_evidence')
    op.drop_index('ix_venn_match_evidence_result_proxy', 'venn_match_evidence')
    op.drop_table('venn_match_evidence')
    
    # Drop enum type
    sa.Enum(name='sourcetype').drop(op.get_bind(), checkfirst=True)
