"""Add territorial fields to VennProxy

Revision ID: 007_add_venn_proxy_territorial
Revises: 006_add_venn_intersections
Create Date: 2025-01-17

Adds applicable_scopes and location_restriction fields to venn_proxies table
for territorial validation in proxy matching.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '007_add_venn_proxy_territorial'
down_revision = '006_add_venn_intersections'
branch_labels = None
depends_on = None


def upgrade():
    """Add territorial restriction fields to venn_proxies."""
    # Add applicable_scopes column (JSON array of TerritorialScope values)
    op.add_column(
        'venn_proxies',
        sa.Column('applicable_scopes', sa.JSON, nullable=True)
    )
    
    # Add location_restriction column (JSON with department/municipality codes)
    op.add_column(
        'venn_proxies',
        sa.Column('location_restriction', sa.JSON, nullable=True)
    )
    
    # Add a comment explaining the fields
    # Note: applicable_scopes = null means proxy applies to ALL scopes
    # Example values: ["MUNICIPAL"], ["DEPARTAMENTAL", "REGIONAL"], etc.
    # location_restriction example: {"department_code": "05", "municipality_code": "05001"}


def downgrade():
    """Remove territorial restriction fields from venn_proxies."""
    op.drop_column('venn_proxies', 'location_restriction')
    op.drop_column('venn_proxies', 'applicable_scopes')
