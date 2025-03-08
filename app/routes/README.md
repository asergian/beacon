# Routes Module

The Routes module provides all HTTP endpoint definitions and request handling for the Beacon application.

## Overview

This module defines all the API endpoints and web routes for the application, handling HTTP requests, implementing business logic, and returning appropriate responses. It's organized into logical groupings based on functionality such as email routes, user routes, and static pages.

## Directory Structure

```
routes/
├── __init__.py        # Route registration and initialization
├── email_routes.py    # Email-related endpoints
├── static_pages.py    # Static page rendering
├── test_routes.py     # Testing and debug endpoints
├── user_routes.py     # User management endpoints
└── README.md          # This documentation
```

## Components

### Email Routes
Implements endpoints for email management, including fetching, analyzing, categorizing, and managing emails. Provides both API endpoints for AJAX requests and page rendering for web views.

### User Routes
Handles user management functionality, including profile management, settings, and preferences. Implements both API endpoints and web views for user interactions.

### Static Pages
Renders application static pages like the dashboard, home page, and information pages. Handles page-specific data loading and rendering.

### Test Routes
Provides development and debugging endpoints for testing application functionality. These routes are only available in development/debug mode.

## Usage Examples

```python
# Registering the route blueprints
from app.routes import init_routes

def create_app():
    app = Flask(__name__)
    init_routes(app)
    return app

# Accessing routes from JavaScript
fetch('/api/emails')
  .then(response => response.json())
  .then(data => console.log(data));

# Server-side template rendering
@routes_bp.route('/')
def index():
    return render_template('index.html', user=current_user)
```

## Internal Design

The routes module follows these design principles:
- Blueprint-based organization for logical grouping
- Consistent API response formatting
- Proper separation between API endpoints and page rendering
- Authentication and authorization enforcement
- Input validation and error handling

## Dependencies

Internal:
- `app.email`: For email processing functionality
- `app.auth`: For authentication and authorization
- `app.models`: For data access
- `app.services`: For external service integration
- `app.utils`: For utility functions

External:
- `flask`: For route definitions and request handling
- `flask.blueprints`: For route organization
- `werkzeug`: For HTTP utilities
- `jinja2`: For template rendering

## Additional Resources

- [Flask Routing Documentation](https://flask.palletsprojects.com/en/2.0.x/quickstart/#routing)
- [Flask Blueprints Documentation](https://flask.palletsprojects.com/en/2.0.x/blueprints/)
- [API Reference](../../docs/sphinx/source/api.html#module-app.routes) 