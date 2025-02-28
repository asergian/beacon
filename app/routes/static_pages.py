"""Routes for static pages like Privacy Policy, Terms of Service, and Support."""

from flask import Blueprint, render_template

static_pages_bp = Blueprint('static_pages', __name__)

@static_pages_bp.route('/privacy-policy')
def privacy_policy():
    """Render the Privacy Policy page."""
    return render_template('static/privacy_policy.html')

@static_pages_bp.route('/terms-of-service')
def terms_of_service():
    """Render the Terms of Service page."""
    return render_template('static/terms_of_service.html')

@static_pages_bp.route('/support')
def support():
    """Render the Support page."""
    return render_template('static/support.html') 