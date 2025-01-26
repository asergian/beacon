"""Flask application entry point.

This module serves as the main entry point for the Flask application.
It creates and runs the Flask application instance using the factory pattern.

Typical usage:
    $ python app.py

Raises:
    ImportError: If the Flask application factory cannot be imported.
    Exception: Any unexpected errors during application startup.
"""
from app import create_app

try:
    app = create_app()
except ImportError as e:
    print(f"Failed to import application factory: {e}")
    raise
except Exception as e:
    print(f"Failed to create application instance: {e}")
    raise

if __name__ == "__main__":
    try:
        print('App starting...')
        app.run(debug=True)
    except Exception as e:
        print(f"Failed to start application: {e}")
        raise