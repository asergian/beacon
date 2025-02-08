"""migrate to key-value settings

Revision ID: migrate_to_kv_settings
Revises: update_user_settings
Create Date: 2024-02-05 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import json

# revision identifiers, used by Alembic.
revision = 'migrate_to_kv_settings'
down_revision = 'update_user_settings'
branch_labels = None
depends_on = None

def upgrade():
    # Create user_settings table
    op.create_table(
        'user_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'key', name='unique_user_setting')
    )
    
    # Create index for faster lookups
    op.create_index('idx_user_settings_user_key', 'user_settings', ['user_id', 'key'])
    
    # Get connection
    connection = op.get_bind()
    
    # Migrate existing settings
    users = connection.execute(sa.text('SELECT id, settings FROM users')).fetchall()
    
    # Define the mapping of old to new keys
    key_mapping = {
        'theme': 'theme',
        'email_preferences': {
            'priority_threshold': 'email_preferences.priority_threshold',
            'days_to_analyze': 'email_preferences.days_to_analyze',
            'vip_senders': 'email_preferences.vip_senders',
            'urgency_keywords': 'email_preferences.urgency_keywords'
        },
        'ai_features': {
            'enable_ai_summarization': 'ai_features.enable_ai_summarization',
            'summary_length': 'ai_features.summary_length',
            'action_item_detection': 'ai_features.action_item_detection'
        }
    }
    
    def flatten_settings(settings, prefix=''):
        """Recursively flatten nested settings."""
        flattened = {}
        if not settings:
            return flattened
            
        for key, value in settings.items():
            if isinstance(value, dict):
                if key in key_mapping and isinstance(key_mapping[key], dict):
                    # Use predefined mappings
                    for sub_key, sub_value in value.items():
                        if sub_key in key_mapping[key]:
                            new_key = key_mapping[key][sub_key]
                            flattened[new_key] = sub_value
                else:
                    # Fallback to automatic flattening
                    sub_prefix = f"{prefix}{key}." if prefix else f"{key}."
                    flattened.update(flatten_settings(value, sub_prefix))
            else:
                if key in key_mapping and isinstance(key_mapping[key], str):
                    new_key = key_mapping[key]
                else:
                    new_key = f"{prefix}{key}" if prefix else key
                flattened[new_key] = value
        return flattened
    
    # Migrate each user's settings
    for user_id, settings in users:
        if settings:
            try:
                # Ensure settings is a dictionary
                if isinstance(settings, str):
                    settings = json.loads(settings)
                
                # Flatten the settings
                flattened = flatten_settings(settings)
                
                # Insert each setting
                for key, value in flattened.items():
                    # Convert the value to a JSON string
                    json_value = json.dumps(value)
                    
                    # Use a properly parameterized query with cast
                    connection.execute(
                        sa.text("""
                            INSERT INTO user_settings (user_id, key, value)
                            VALUES (:user_id, :key, cast(:value AS jsonb))
                            ON CONFLICT (user_id, key) DO UPDATE
                            SET value = cast(:value AS jsonb)
                        """),
                        {
                            "user_id": user_id,
                            "key": key,
                            "value": json_value
                        }
                    )
            except Exception as e:
                print(f"Error migrating settings for user {user_id}: {e}")
                continue
    
    # Optionally, remove the old settings column
    # Commented out to keep as backup during transition
    # op.drop_column('users', 'settings')

def downgrade():
    # This is a complex downgrade as we need to reconstruct the nested structure
    connection = op.get_bind()
    
    # Get all settings
    settings = connection.execute(sa.text(
        'SELECT user_id, key, value FROM user_settings'
    )).fetchall()
    
    # Group settings by user
    user_settings = {}
    for user_id, key, value in settings:
        if user_id not in user_settings:
            user_settings[user_id] = {}
            
        # Split the key into parts
        parts = key.split('.')
        
        # Build nested structure
        current = user_settings[user_id]
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    
    # Update each user's settings
    for user_id, settings in user_settings.items():
        try:
            # Convert settings to JSON string
            json_settings = json.dumps(settings)
            
            # Use properly parameterized query with cast
            connection.execute(
                sa.text('UPDATE users SET settings = cast(:settings AS jsonb) WHERE id = :user_id'),
                {
                    "settings": json_settings,
                    "user_id": user_id
                }
            )
        except Exception as e:
            print(f"Error downgrading settings for user {user_id}: {e}")
            continue
    
    # Drop the user_settings table
    op.drop_table('user_settings') 