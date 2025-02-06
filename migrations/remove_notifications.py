from app.models import db, User
from sqlalchemy import text

def migrate_user_settings():
    """Remove notifications from user settings and ensure correct structure."""
    
    try:
        # Get all users
        users = User.query.all()
        
        for user in users:
            if user.settings is None:
                # Initialize with default settings if None
                user.settings = {
                    'theme': 'light',
                    'email_preferences': {
                        'priority_threshold': 50,
                        'days_to_analyze': 1,
                        'vip_senders': [],
                        'urgency_keywords': ['urgent', 'asap', 'deadline', 'immediate', 'priority']
                    },
                    'ai_features': {
                        'enable_ai_summarization': True,
                        'summary_length': 'medium',
                        'action_item_detection': True
                    }
                }
            else:
                # Remove notifications if present
                if 'notifications' in user.settings:
                    user.settings.pop('notifications')
                
                # Ensure ai_features exists with correct structure
                if 'ai_features' not in user.settings:
                    user.settings['ai_features'] = {
                        'enable_ai_summarization': True,
                        'summary_length': 'medium',
                        'action_item_detection': True
                    }
                
                # Ensure email_preferences exists with correct structure
                if 'email_preferences' not in user.settings:
                    user.settings['email_preferences'] = {
                        'priority_threshold': 50,
                        'days_to_analyze': 1,
                        'vip_senders': [],
                        'urgency_keywords': ['urgent', 'asap', 'deadline', 'immediate', 'priority']
                    }
                
                # Ensure theme exists
                if 'theme' not in user.settings:
                    user.settings['theme'] = 'light'
        
        # Commit all changes
        db.session.commit()
        print("Successfully migrated user settings")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error during migration: {e}")
        raise

if __name__ == "__main__":
    migrate_user_settings() 