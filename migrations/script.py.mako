"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

This file is the template used by Alembic to generate new migration scripts.
The variables enclosed in ${...} are populated by Alembic when creating a migration.
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    """Implement the forward migration logic here.
    
    This function should implement all schema changes for this migration.
    It will be automatically populated with auto-generated migration code 
    when using 'flask db migrate'.
    """
    ${upgrades if upgrades else "pass"}


def downgrade():
    """Implement the rollback migration logic here.
    
    This function should revert all changes made in the upgrade function,
    in the correct order (reverse of upgrade).
    """
    ${downgrades if downgrades else "pass"}
