"""Demo mode functionality package.

This package centralizes all demo-related functionality for the Beacon application.
It provides sample email data, pre-generated analysis, routes, and authentication
for demonstration purposes without requiring actual email credentials.

Modules:
    data: Demo email content and sample data generators
    analysis: Demo email analysis functionality
    routes: Demo routes for UI and API endpoints
    auth: Demo authentication functionality
"""

from flask import Blueprint

# Create blueprint for demo routes
demo_bp = Blueprint('demo', __name__)

# Import routes to register them with the blueprint
from . import routes

# Make key components available at package level
from .analysis import DemoAnalysis, load_analysis_cache
from .data import get_demo_email_bodies

__all__ = [
    'demo_bp',
    'DemoAnalysis',
    'load_analysis_cache',
    'get_demo_email_bodies'
] 