"""User settings model for storing user preferences.

This module contains the UserSetting model for storing user configuration
options and preferences as key-value pairs.
"""

from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import JSONB

from . import db

class UserSetting(db.Model):
    """Key-value store for user settings.
    
    This model provides a flexible storage mechanism for user settings
    as key-value pairs, with JSONB values to support complex data structures.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to the users table
        key: Setting name/identifier
        value: Setting value stored as JSONB
        created_at: Timestamp when setting was created
        updated_at: Timestamp when setting was last updated
        user: Relationship to the User model
    """
    
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
        """Get a single setting value for a user.
        
        Args:
            user_id: ID of the user
            key: Setting key to retrieve
            default: Default value if setting doesn't exist
            
        Returns:
            The setting value or the default if not found
        """
        setting = cls.query.filter_by(user_id=user_id, key=key).first()
        return setting.value if setting else default
    
    @classmethod
    def set_setting(cls, user_id: int, key: str, value: Any) -> None:
        """Set a single setting value for a user.
        
        Args:
            user_id: ID of the user
            key: Setting key to set
            value: Value to store
            
        Updates existing setting or creates a new one if it doesn't exist.
        """
        setting = cls.query.filter_by(user_id=user_id, key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = cls(user_id=user_id, key=key, value=value)
            db.session.add(setting)
        db.session.commit() 