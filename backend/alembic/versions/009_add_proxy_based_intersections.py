"""Add proxy-based intersection support

Revision ID: 009_add_proxy_intersections
Revises: 008_add_venn_match_evidence
Create Date: 2025-12-15

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '009_add_proxy_intersections'
down_revision = '008_add_venn_match_evidence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add proxy-based intersection columns to venn_intersections table
    op.add_column('venn_intersections', 
        sa.Column('include_proxy_ids', sa.JSON(), nullable=True)
    )
    op.add_column('venn_intersections', 
        sa.Column('exclude_proxy_ids', sa.JSON(), nullable=True)
    )
    op.add_column('venn_intersections', 
        sa.Column('use_proxies', sa.Boolean(), nullable=True, server_default='false')
    )


def downgrade() -> None:
    op.drop_column('venn_intersections', 'use_proxies')
    op.drop_column('venn_intersections', 'exclude_proxy_ids')
    op.drop_column('venn_intersections', 'include_proxy_ids')
