"""Database models package for user management and settings.

This package contains SQLAlchemy models for the core application database,
including User accounts, settings, and activity tracking.

Modules:
    user: User account model with associated methods
    settings: Key-value store for user settings
    activity: User activity tracking model and logging functions
"""

# Initialize SQLAlchemy
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

# Import and expose models
from .user import User
from .settings import UserSetting
from .activity import UserActivity, log_activity

__all__ = [
    'db',
    'User',
    'UserSetting',
    'UserActivity',
    'log_activity'
] 