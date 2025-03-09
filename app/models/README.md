# Models Module

The Models module defines the application's data structures, ORM models, and database relationships.

## Overview

This module contains the SQLAlchemy models that represent the application's data entities and their relationships. It provides object-relational mapping (ORM) for database tables, defining schema, relationships, and model-specific methods for business logic.

## Directory Structure

```
models/
├── __init__.py        # Database initialization and exports
├── activity.py        # User activity and logging models
├── settings.py        # User settings and preferences
├── user.py            # User account models
└── README.md          # This documentation
```

## Components

### User Model
Represents user accounts with authentication information, profile data, and role-based permissions. Includes methods for password management, role verification, and account status.

### Activity Model
Tracks user activities and system events for auditing and analytics. Provides functionality for logging various types of events with relevant context.

### Settings Model
Manages user preferences and application settings. Supports different setting types (e.g., boolean, string, JSON) and provides default values.

## Usage Examples

```python
# Creating a new user
from app.models.user import User
from app.models import db

new_user = User(
    email="user@example.com",
    name="Example User"
)
new_user.set_password("secure_password")
db.session.add(new_user)
db.session.commit()

# Logging user activity
from app.models.activity import log_activity

log_activity(
    user_id=current_user.id,
    action="email_read",
    data={"email_id": email.id}
)

# Managing user settings
from app.models.settings import get_user_setting, set_user_setting

# Get a setting with default fallback
theme = get_user_setting(user_id, "theme", default="light")

# Update a setting
set_user_setting(user_id, "theme", "dark")
```

## Internal Design

The models module follows these design principles:
- Clean separation between database schema and business logic
- Consistent relationship definitions
- Proper validation and type checking
- Efficient database access patterns
- Clear documentation of model fields and relationships

## Dependencies

Internal:
- None (models are a foundational module)

External:
- `flask_sqlalchemy`: For ORM functionality
- `sqlalchemy`: For database modeling
- `werkzeug.security`: For password hashing
- `datetime`: For timestamp handling

## Additional Resources

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Flask-SQLAlchemy Documentation](https://flask-sqlalchemy.palletsprojects.com/)
- [API Reference]({doc}`api`) 