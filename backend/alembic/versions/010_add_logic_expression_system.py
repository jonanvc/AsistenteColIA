"""Add logic expression system for Venn intersections

This migration adds support for complex boolean expressions with nested AND/OR operators.

The new system uses a JSON-based expression tree stored in the 'logic_expression' column.

Expression format:
{
    "type": "AND|OR|proxy|variable|NOT",
    "children": [...],  // For AND/OR/NOT operators
    "id": <int>,        // For proxy/variable types
    "negate": <bool>    // Optional, to negate the result
}

Examples:
- Simple AND: {"type": "AND", "children": [{"type": "proxy", "id": 1}, {"type": "proxy", "id": 2}]}
- (A OR B) AND C: {"type": "AND", "children": [{"type": "OR", "children": [A, B]}, C]}

Revision ID: 010_add_logic_expression
Revises: 009_add_proxy_based_intersections
Create Date: 2025-12-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010_add_logic_expression'
down_revision = '009_add_proxy_intersections'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new column for logic expressions (JSON tree structure)
    op.add_column('venn_intersections', sa.Column('logic_expression', sa.JSON(), nullable=True))
    
    # Add column to mark if using the new expression system
    op.add_column('venn_intersections', sa.Column('use_logic_expression', sa.Boolean(), server_default='false', nullable=False))
    
    # Add human-readable expression string for display
    op.add_column('venn_intersections', sa.Column('expression_display', sa.Text(), nullable=True))
    
    # Migrate existing intersections to new format
    # We'll do this in Python to have more control
    connection = op.get_bind()
    
    # Get all existing intersections
    result = connection.execute(sa.text("""
        SELECT id, operation, include_ids, exclude_ids, include_proxy_ids, exclude_proxy_ids, use_proxies
        FROM venn_intersections
    """))
    
    for row in result:
        inter_id = row[0]
        operation = row[1]  # 'INTERSECTION' or 'UNION'
        include_ids = row[2] or []
        exclude_ids = row[3] or []
        include_proxy_ids = row[4] or []
        exclude_proxy_ids = row[5] or []
        use_proxies = row[6] or False
        
        # Build the logic expression
        children = []
        
        if use_proxies and include_proxy_ids:
            # Proxy-based intersection
            for proxy_id in include_proxy_ids:
                children.append({"type": "proxy", "id": proxy_id})
        elif include_ids:
            # Variable-based intersection
            for var_id in include_ids:
                children.append({"type": "variable", "id": var_id})
        
        # Add exclusions as negated children
        if use_proxies and exclude_proxy_ids:
            for proxy_id in exclude_proxy_ids:
                children.append({"type": "proxy", "id": proxy_id, "negate": True})
        elif exclude_ids:
            for var_id in exclude_ids:
                children.append({"type": "variable", "id": var_id, "negate": True})
        
        if children:
            # Determine operator type
            op_type = "AND" if operation == "INTERSECTION" else "OR"
            
            logic_expr = {
                "type": op_type,
                "children": children
            }
            
            # Update the intersection
            import json
            connection.execute(sa.text("""
                UPDATE venn_intersections 
                SET logic_expression = :expr, use_logic_expression = true
                WHERE id = :id
            """), {"expr": json.dumps(logic_expr), "id": inter_id})


def downgrade() -> None:
    op.drop_column('venn_intersections', 'expression_display')
    op.drop_column('venn_intersections', 'use_logic_expression')
    op.drop_column('venn_intersections', 'logic_expression')
