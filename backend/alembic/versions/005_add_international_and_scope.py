"""Add is_international to organizations and data_scope to scraped_data

Revision ID: 005_add_international_and_scope
Revises: 004_add_venn_result_verification
Create Date: 2025-12-14 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_intl_scope'
down_revision: Union[str, None] = '004_add_venn_verification'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add INTERNACIONAL value to TerritorialScope enum
    # PostgreSQL requires creating a new type or altering the existing one
    op.execute("ALTER TYPE territorialscope ADD VALUE IF NOT EXISTS 'INTERNACIONAL'")
    
    # Add is_international column to organizations
    op.add_column(
        'organizations',
        sa.Column('is_international', sa.Boolean(), nullable=True, default=False)
    )
    op.create_index('ix_organizations_is_international', 'organizations', ['is_international'])
    
    # Add data_scope column to scraped_data (using existing territorialscope enum)
    op.add_column(
        'scraped_data',
        sa.Column(
            'data_scope',
            sa.Enum('MUNICIPAL', 'DEPARTAMENTAL', 'REGIONAL', 'NACIONAL', 'INTERNACIONAL', name='territorialscope', create_type=False),
            nullable=True
        )
    )
    op.create_index('ix_scraped_data_data_scope', 'scraped_data', ['data_scope'])
    
    # Add venn_variable_id column to scraped_data (links scraped data to Venn variables)
    op.add_column(
        'scraped_data',
        sa.Column('venn_variable_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_scraped_data_venn_variable',
        'scraped_data', 'venn_variables',
        ['venn_variable_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_scraped_data_venn_variable_id', 'scraped_data', ['venn_variable_id'])
    
    # Add confirms_venn_variable column to scraped_data
    op.add_column(
        'scraped_data',
        sa.Column('confirms_venn_variable', sa.Boolean(), nullable=True)
    )


def downgrade() -> None:
    # Drop confirms_venn_variable column
    op.drop_column('scraped_data', 'confirms_venn_variable')
    
    # Drop venn_variable_id foreign key and column
    op.drop_index('ix_scraped_data_venn_variable_id', table_name='scraped_data')
    op.drop_constraint('fk_scraped_data_venn_variable', 'scraped_data', type_='foreignkey')
    op.drop_column('scraped_data', 'venn_variable_id')
    
    # Drop data_scope column and index
    op.drop_index('ix_scraped_data_data_scope', table_name='scraped_data')
    op.drop_column('scraped_data', 'data_scope')
    
    # Drop is_international column and index
    op.drop_index('ix_organizations_is_international', table_name='organizations')
    op.drop_column('organizations', 'is_international')
    
    # Note: Cannot easily remove enum value in PostgreSQL, leaving 'internacional' in the enum
