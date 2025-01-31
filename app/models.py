"""Database models for the application."""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text
import logging

db = SQLAlchemy()

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
    
    # User settings stored as JSON
    settings = db.Column(JSONB, default={
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
    })
    
    # Relationships
    activities = db.relationship('UserActivity', back_populates='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def update_last_login(self):
        """Update the last login timestamp."""
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def update_settings(self, new_settings):
        """Update user settings, merging with existing ones."""
        self.settings = {**self.settings, **new_settings}
        db.session.commit()
    
    def has_role(self, role):
        """Check if user has a specific role."""
        return role in (self.roles or ['user'])
    
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