"""User account model for authentication and user management.

This module contains the User model that represents user accounts in the system,
along with methods for settings management and authentication.
"""

from datetime import datetime
import logging
from typing import Any, Dict, Optional

from sqlalchemy.dialects.postgresql import JSONB

from . import db
from .settings import UserSetting

class User(db.Model):
    """User model for storing user account information.
    
    This model represents a user account in the system and provides methods
    for user settings management and role-based access control.
    
    Attributes:
        id: Primary key
        email: User's email address (unique)
        name: User's display name
        picture: URL to user's profile picture
        created_at: Timestamp when account was created
        last_login: Timestamp of last login
        is_active: Flag indicating if account is active
        roles: List of roles assigned to the user (stored as JSONB)
        activities: Relationship to UserActivity records
        settings_entries: Relationship to UserSetting records
    """
    
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
            'custom_categories': [  # Default demo categories
                {
                    'name': 'Type',
                    'description': 'The type or purpose of the email communication',
                    'values': ['Onboarding', 'Report', 'Meeting', 'Security', 'Marketing', 'Community', 'Initiative', 'Project', 'Personal Development', 'System'],
                    'color': '#8B5CF6'
                },
                {
                    'name': 'Communication Style',
                    'description': 'The tone and style of the email communication',
                    'values': ['Instructional Friendly', 'Formal Analytical', 'Creative Enthusiastic', 'Direct Authoritative', 'Casual Enthusiastic', 'Data Driven Analytical', 'Motivational Supportive', 'Professional Decisive', 'Informative Encouraging'],
                    'color': '#EC4899'
                }
            ]
        },
        'timezone': 'US/Pacific'
    }
    
    def __repr__(self):
        """Return a string representation of the User.
        
        Returns:
            String representation with user email
        """
        return f'<User {self.email}>'
    
    def update_last_login(self):
        """Update the last login timestamp.
        
        Sets the last_login field to the current UTC time and commits
        the change to the database.
        """
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a single setting value with default fallback.
        
        Args:
            key: Setting key to retrieve (can be nested with dot notation)
            default: Default value if setting doesn't exist
            
        Returns:
            The setting value or an appropriate default
            
        For nested settings (using dot notation like 'email_preferences.days_to_analyze'),
        this method traverses the DEFAULT_SETTINGS structure to find the appropriate default.
        """
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
        """Set a single setting value.
        
        Args:
            key: Setting key to set (can be nested with dot notation)
            value: Value to store
        """
        # Log the setting update
        if key == 'ai_features.model_type':
            logging.info(f"Setting model_type - Key: {key}, Value: {value}")
            
        UserSetting.set_setting(self.id, key, value)
    
    def get_settings_group(self, prefix: str) -> Dict[str, Any]:
        """Get all settings with a specific prefix.
        
        Args:
            prefix: The settings group prefix (e.g., 'email_preferences')
            
        Returns:
            Dict containing all settings in the specified group
            
        This method retrieves all settings with keys that start with the
        given prefix, merging with default values as appropriate.
        """
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
        """Update multiple settings with a specific prefix.
        
        Args:
            prefix: The settings group prefix (e.g., 'email_preferences')
            values: Dictionary of settings to update
            
        Raises:
            Exception: If there's an error updating the settings
            
        This method uses a database transaction to ensure all settings
        are updated atomically.
        """
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
        """Check if user has a specific role.
        
        Args:
            role: Role name to check for
            
        Returns:
            Boolean indicating if user has the specified role
        """
        return role in (self.roles or ['user'])
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings with defaults.
        
        Returns:
            Dictionary containing all user settings with default fallbacks
        """
        settings = {}
        for key, default in self.DEFAULT_SETTINGS.items():
            if isinstance(default, dict):
                settings[key] = self.get_settings_group(key)
            else:
                settings[key] = self.get_setting(key, default)
        return settings
    
    @classmethod
    def get_or_create(cls, email, name=None, picture=None):
        """Get existing user or create a new one.
        
        Args:
            email: User's email address
            name: User's display name (optional)
            picture: URL to user's profile picture (optional)
            
        Returns:
            User: Existing or newly created user object
            
        This method searches for a user with the given email and creates a new
        user if none exists. For new users, default settings are initialized.
        """
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