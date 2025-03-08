"""initial schema

Revision ID: initial_schema
Revises: 
Create Date: 2024-02-19 22:25:00.000000

This migration creates the initial database schema for the application,
including the users, user_activities, and user_settings tables.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create the initial database schema.
    
    This function creates three main tables:
    - users: Stores user account information
    - user_activities: Tracks user actions and events
    - user_settings: Stores user-specific settings and preferences
    
    It also creates necessary indexes and constraints.
    """
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('picture', sa.String(500)),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('last_login', sa.DateTime()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('roles', postgresql.JSONB(), default=lambda: ['user']),
        sa.Column('settings', postgresql.JSONB()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='users_email_key')
    )

    # Create user_activities table
    op.create_table(
        'user_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('description', sa.String(500)),
        sa.Column('activity_metadata', postgresql.JSONB(), default={}),
        sa.Column('created_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='user_activities_user_id_fkey')
    )

    # Create user_settings table
    op.create_table(
        'user_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='user_settings_user_id_fkey'),
        sa.UniqueConstraint('user_id', 'key', name='unique_user_setting')
    )

    # Create index for user_settings
    op.create_index('idx_user_settings_user_key', 'user_settings', ['user_id', 'key'])


def downgrade():
    """Revert the initial schema creation.
    
    This function drops all tables and indexes created in the upgrade function,
    in the correct order to handle foreign key dependencies.
    """
    op.drop_index('idx_user_settings_user_key')
    op.drop_table('user_settings')
    op.drop_table('user_activities')
    op.drop_table('users') 