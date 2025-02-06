from flask import current_app
from app import create_app
from migrations.remove_notifications import migrate_user_settings

app = create_app()
with app.app_context():
    migrate_user_settings() 