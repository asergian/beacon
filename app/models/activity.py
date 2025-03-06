"""User activity tracking models and functions.

This module contains the UserActivity model for tracking user actions in the system,
as well as helper functions for logging these activities.
"""

from datetime import datetime
import logging
from typing import Dict, Optional

from sqlalchemy.dialects.postgresql import JSONB

from . import db

class UserActivity(db.Model):
    """Model for tracking user activity in the application.
    
    This model records various user activities and actions in the system
    for analytics, debugging, and audit purposes.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to the users table
        activity_type: Type/category of activity
        description: Human-readable description of the activity
        activity_metadata: Additional activity-specific data (JSONB)
        created_at: Timestamp when the activity was recorded
        user: Relationship to the User model
    """
    
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
        """Return a string representation of the UserActivity.
        
        Returns:
            String representation with activity type and user email
        """
        return f'<UserActivity {self.activity_type} by {self.user.email}>'


def log_activity(user_id: int, activity_type: str, description: str = None, metadata: Optional[Dict] = None) -> UserActivity:
    """Helper function to log user activity.
    
    Args:
        user_id: ID of the user performing the activity
        activity_type: Type/category of activity
        description: Human-readable description of the activity
        metadata: Additional activity-specific data
        
    Returns:
        UserActivity: The created activity record
        
    Raises:
        ValueError: If user_id is None
        Exception: If there's an error logging the activity
    """
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