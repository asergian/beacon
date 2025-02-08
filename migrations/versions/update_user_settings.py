"""update user settings structure

Revision ID: update_user_settings
Revises: None
Create Date: 2024-02-05 16:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import table, column
import json

# revision identifiers, used by Alembic.
revision = 'update_user_settings'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    conn = op.get_bind()
    
    # Define the new default settings structure
    new_default_settings = {
        'theme': 'light',
        'email_preferences': {
            'priority_threshold': 50,
            'days_to_analyze': 1,
            'cache_duration_days': 7,
            'vip_senders': [],
            'urgency_keywords': ['urgent', 'asap', 'deadline', 'immediate', 'priority']
        },
        'ai_features': {
            'enable_ai_summarization': True,
            'summary_length': 'medium',
            'action_item_detection': True
        }
    }
    
    # First, get all users
    result = conn.execute(sa.text('SELECT id, settings FROM users'))
    for user_id, current_settings in result:
        if current_settings is None:
            current_settings = {}
            
        # Remove notifications if present
        if 'notifications' in current_settings:
            del current_settings['notifications']
            
        # Ensure email_preferences exists with defaults
        if 'email_preferences' not in current_settings:
            current_settings['email_preferences'] = new_default_settings['email_preferences']
            
        # Ensure ai_features exists with defaults
        if 'ai_features' not in current_settings:
            current_settings['ai_features'] = new_default_settings['ai_features']
            
        # Update theme if not present
        if 'theme' not in current_settings:
            current_settings['theme'] = new_default_settings['theme']
            
        # Update the user's settings using a parameterized query
        conn.execute(
            sa.text("UPDATE users SET settings = cast(:settings as jsonb) WHERE id = :id"),
            {"settings": json.dumps(current_settings), "id": user_id}
        )

def downgrade():
    conn = op.get_bind()
    
    # Define the old default settings structure
    old_default_settings = {
        'theme': 'light',
        'notifications': {
            'email': True,
            'web': True
        },
        'email_preferences': {
            'priority_threshold': 50,
            'days_to_analyze': 1,
            'vip_senders': [],
            'urgency_keywords': ['urgent', 'asap', 'deadline', 'immediate', 'priority']
        }
    }
    
    # First, get all users
    result = conn.execute(sa.text('SELECT id, settings FROM users'))
    for user_id, current_settings in result:
        if current_settings is None:
            current_settings = old_default_settings
        else:
            # Remove ai_features
            if 'ai_features' in current_settings:
                del current_settings['ai_features']
            # Restore notifications
            current_settings['notifications'] = old_default_settings['notifications']
            
        # Update the user's settings using a parameterized query
        conn.execute(
            sa.text("UPDATE users SET settings = cast(:settings as jsonb) WHERE id = :id"),
            {"settings": json.dumps(current_settings), "id": user_id}
        ) 