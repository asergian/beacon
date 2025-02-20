from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text
import logging
import json
from sqlalchemy import func
from typing import Any, Dict, Optional

"""User and activity models."""

db = SQLAlchemy()

class UserSetting(db.Model):
    """Key-value store for user settings."""
    
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(JSONB, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='settings_entries')
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'key', name='unique_user_setting'),
    )
    
    @classmethod
    def get_setting(cls, user_id: int, key: str, default: Any = None) -> Any:
        """Get a single setting value."""
        setting = cls.query.filter_by(user_id=user_id, key=key).first()
        return setting.value if setting else default
    
    @classmethod
    def set_setting(cls, user_id: int, key: str, value: Any) -> None:
        """Set a single setting value."""
        setting = cls.query.filter_by(user_id=user_id, key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = cls(user_id=user_id, key=key, value=value)
            db.session.add(setting)
        db.session.commit()

class User(db.Model):
    """User model for storing user account information."""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    picture = db.Column(db.String(500))  # URL to profile picture
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    roles = db.Column(JSONB, default=['user'])  # List of roles: ['user', 'admin']
    
    # Relationships
    activities = db.relationship('UserActivity', back_populates='user', lazy='dynamic')
    settings_entries = db.relationship('UserSetting', back_populates='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def update_last_login(self):
        """Update the last login timestamp."""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    # Default settings structure that matches the template expectations
    DEFAULT_SETTINGS = {
        'theme': 'light',
        'email_preferences': {
            'days_to_analyze': 1,  # Default to 1 day for a minimal initial view
            'cache_duration_days': 1  # Default to 1 day for minimal caching
        },
        'ai_features': {
            'enabled': True,  # Main AI toggle
            'model_type': 'gpt-4o-mini',  # Default to standard model
            'context_length': '1000',  # Default to medium context
            'priority_threshold': 50,  # Default to Medium (50)
            'summary_length': 'medium',  # Default summary length
            'custom_categories': []  # List of custom category objects with format:
                                   # {
                                   #   'name': str,
                                   #   'description': str,
                                   #   'values': List[str],
                                   #   'color': str  # Hex color code
                                   # }
        }
    }
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a single setting value with default fallback."""
        # Split the key into parts for nested settings
        parts = key.split('.')
        
        # For nested settings, traverse the DEFAULT_SETTINGS
        default_value = self.DEFAULT_SETTINGS
        for part in parts:
            if isinstance(default_value, dict) and part in default_value:
                default_value = default_value[part]
            else:
                default_value = default
                break
        
        # Get the setting from the database
        setting = UserSetting.get_setting(self.id, key, None)
        
        # Only log AI settings once per session using a class variable
        if key.startswith('ai_features.'):
            if not hasattr(User, '_logged_settings'):
                User._logged_settings = set()
            if key not in User._logged_settings:
                logging.debug(f"AI Setting {key} - DB value: {setting}, Default: {default_value}")
                User._logged_settings.add(key)
            
        return setting if setting is not None else default_value
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set a single setting value."""
        # Log the setting update
        if key == 'ai_features.model_type':
            logging.info(f"Setting model_type - Key: {key}, Value: {value}")
            
        UserSetting.set_setting(self.id, key, value)
    
    def get_settings_group(self, prefix: str) -> Dict[str, Any]:
        """Get all settings with a specific prefix."""
        if prefix not in self.DEFAULT_SETTINGS:
            logging.warning(f"Prefix {prefix} not found in DEFAULT_SETTINGS")
            return {}
            
        # Get default values for the group
        defaults = self.DEFAULT_SETTINGS[prefix]
        if not isinstance(defaults, dict):
            value = self.get_setting(prefix)
            logging.info(f"Getting non-dict settings group {prefix}: {value}")
            return {prefix: value}
            
        # Build the settings dictionary
        settings = {}
        for key, default in defaults.items():
            full_key = f"{prefix}.{key}"
            value = self.get_setting(full_key, default)
            settings[key] = value
            
        # Log AI features group retrieval
        if prefix == 'ai_features':
            logging.debug(f"Getting complete AI features group: {settings}")
            
        return settings
    
    def update_settings_group(self, prefix: str, values: Dict[str, Any]) -> None:
        """Update multiple settings with a specific prefix."""
        try:
            db.session.begin_nested()
            
            for key, value in values.items():
                full_key = f"{prefix}.{key}" if prefix else key
                self.set_setting(full_key, value)
            
            db.session.commit()
        except Exception as e:
            logging.error(f"Failed to update settings group: {e}")
            db.session.rollback()
            raise

    def has_role(self, role):
        """Check if user has a specific role."""
        return role in (self.roles or ['user'])
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings with defaults."""
        settings = {}
        for key, default in self.DEFAULT_SETTINGS.items():
            if isinstance(default, dict):
                settings[key] = self.get_settings_group(key)
            else:
                settings[key] = self.get_setting(key, default)
        return settings
    
    @classmethod
    def get_or_create(cls, email, name=None, picture=None):
        """Get existing user or create a new one."""
        user = cls.query.filter_by(email=email).first()
        if user is None:
            user = cls(
                email=email,
                name=name,
                picture=picture,
                roles=['user']
            )
            # Special case for admin
            if email == 'alex.sergian@gmail.com':
                user.roles = ['user', 'admin']
            db.session.add(user)
            db.session.commit()
            
            # Initialize default settings
            for key, value in cls.DEFAULT_SETTINGS.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        full_key = f"{key}.{sub_key}"
                        UserSetting.set_setting(user.id, full_key, sub_value)
                else:
                    UserSetting.set_setting(user.id, key, value)
                
        return user

class UserActivity(db.Model):
    """Model for tracking user activity in the application."""
    
    __tablename__ = 'user_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # e.g., 'login', 'email_analysis', 'settings_update'
    description = db.Column(db.String(500))
    activity_metadata = db.Column(JSONB, default={})  # Additional activity-specific data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='activities')
    
    def __repr__(self):
        return f'<UserActivity {self.activity_type} by {self.user.email}>'

def log_activity(user_id: int, activity_type: str, description: str = None, metadata: dict = None) -> UserActivity:
    """Helper function to log user activity."""
    if user_id is None:
        raise ValueError("user_id cannot be None")
    
    try:
        # Only log at debug level for detailed activity tracking
        logging.debug(f"Activity: {activity_type} for user {user_id}")
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            description=description,
            activity_metadata=metadata or {}
        )
        db.session.add(activity)
        db.session.commit()  # Commit the transaction
        return activity
    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to log activity: {e}")
        raise 