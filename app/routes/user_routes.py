"""User settings and analytics routes.

This module provides routes for user settings management and analytics
data collection and display. It includes endpoints for updating user preferences,
viewing analytics dashboards, and retrieving analytics data.

Typical usage example:
    app.register_blueprint(user_bp, url_prefix='/user')
"""

from flask import Blueprint, jsonify, request, session, render_template
from app.models.user import User
from app.models.activity import UserActivity, log_activity
from ..auth.decorators import login_required, admin_required
import logging
from datetime import datetime
from app.models import db

user_bp = Blueprint('user', __name__)
logger = logging.getLogger(__name__)

# Common timezones list for the dropdown
COMMON_TIMEZONES = [
    'UTC',
    'US/Pacific',
    'US/Eastern', 
    'US/Central',
    'US/Mountain',
    'US/Hawaii',
    'US/Alaska',
    'Europe/London',
    'Europe/Paris',
    'Europe/Berlin',
    'Europe/Moscow',
    'Asia/Tokyo',
    'Asia/Shanghai',
    'Asia/Singapore',
    'Asia/Dubai',
    'Australia/Sydney',
    'Pacific/Auckland',
    'America/Toronto',
    'America/Vancouver',
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'America/Phoenix',
    'America/Anchorage',
    'America/Honolulu',
]

@user_bp.route('/analytics')
@admin_required
def analytics_dashboard():
    """Display the analytics dashboard.
    
    Admin-only route for viewing application usage analytics.
    
    Returns:
        Flask response: Rendered analytics dashboard template.
    """
    return render_template('analytics.html')

@user_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Handle settings page and updates.
    
    GET requests render the settings page with current user settings.
    POST requests update a single setting and return the updated value.
    
    Returns:
        Flask response: For GET: rendered settings page with user preferences.
                       For POST: JSON response with update status and values.
        
    Raises:
        Exception: If there's an error processing the settings, returns a 500 error.
    """
    try:
        user = User.query.get(session['user']['id'])
        if not user:
            logger.error(f"User not found for ID: {session['user']['id']}")
            return render_template('settings.html', user_settings=User.DEFAULT_SETTINGS)

        if request.method == 'POST':
            logger.info(f"Processing POST request for user {user.id}")
            
            try:
                # Get the setting key and value from the request
                if not request.json or len(request.json) != 1:
                    raise ValueError("Request must contain exactly one setting update")
                
                key = next(iter(request.json))  # Get the only key
                value = request.json[key]
                
                logger.info(f"Updating setting {key} to: {value}")
                
                # Get current value for logging
                current_value = user.get_setting(key)
                logger.info(f"Current value of {key}: {current_value}")
                
                # Update the setting
                user.set_setting(key, value)
                
                # Get the updated value for verification
                updated_value = user.get_setting(key)
                logger.info(f"Updated value of {key}: {updated_value}")
                
                # Get the group name for the setting (if any)
                group = key.split('.')[0] if '.' in key else None
                
                # Log the activity
                log_activity(
                    user_id=user.id,
                    activity_type='settings_update',
                    description=f"Updated setting: {key}",
                    metadata={
                        'key': key,
                        'old_value': current_value,
                        'new_value': updated_value,
                        'group': group
                    }
                )
                
                # Return the updated settings group if it exists, otherwise just the updated value
                response_data = {
                    "status": "success",
                    "message": "Setting updated successfully",
                    "value": updated_value
                }
                
                if group:
                    response_data["group"] = user.get_settings_group(group)
                
                return jsonify(response_data)
                
            except Exception as e:
                logger.error(f"Failed to update setting: {e}", exc_info=True)
                return jsonify({"error": str(e)}), 500
            
        # GET request - display settings page
        logger.info(f"Processing GET request for user {user.id}")
        
        # Get all user settings
        user_settings = user.get_all_settings()
            
        logger.info(f"Retrieved settings for display: {user_settings}")
            
        return render_template('settings.html', 
                               user_settings=user_settings,
                               common_timezones=COMMON_TIMEZONES)
        
    except Exception as e:
        logger.error(f"Failed to handle settings request: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@user_bp.route('/api/analytics')
@admin_required
def get_analytics():
    """Get user activity analytics data.
    
    Admin-only endpoint that retrieves and processes all user activities
    to generate analytics about application usage, including LLM, email,
    and NLP statistics.
    
    Returns:
        JSON response: Processed analytics data for all system users.
        
    Raises:
        Exception: If analytics processing fails, returns a 404 or 500 error.
    """
    try:
        admin_user = User.query.get(session['user']['id'])
        if not admin_user:
            logger.error(f"Admin user not found for ID: {session['user']['id']}")
            return jsonify({"error": "Admin user not found"}), 404
        
        # For admins, get all activities across all users using db.session
        activities = db.session.query(UserActivity).join(User).order_by(UserActivity.created_at.desc()).all()
        
        # Debug logging for user distribution
        user_activity_counts = {}
        for activity in activities:
            user_activity_counts[activity.user.email] = user_activity_counts.get(activity.user.email, 0) + 1
        
        logger.debug(f"Activity distribution by user: {user_activity_counts}")
        logger.info(f"Processing {len(activities)} activities from {len(user_activity_counts)} users")
        
        # Initialize statistics
        llm_stats = {
            'total_tokens': 0,
            'total_cost_cents': 0,
            'total_requests': 0,
            'avg_tokens_per_request': 0,
            'avg_cost_cents_per_request': 0,
            'avg_processing_time_ms': 0,
            'models_used': set(),
            'success_rate': 0,
            'requests_by_model': {},
            'tokens_by_model': {}
        }
        
        email_stats = {
            'total_fetched': 0,
            'new_emails': 0,
            'successfully_parsed': 0,
            'successfully_analyzed': 0,
            'failed_parsing': 0,
            'failed_analysis': 0,
            'needs_action': 0,
            'has_deadline': 0,
            'categories': {
                'Work': 0,
                'Personal': 0,
                'Promotions': 0,
                'Informational': 0
            },
            'priority_levels': {
                'HIGH': 0,
                'MEDIUM': 0,
                'LOW': 0
            }
        }
        
        nlp_stats = {
            'total_entities': 0,
            'total_emails': 0,
            'urgent_emails': 0,
            'avg_sentences_per_email': 0,
            'avg_processing_time': 0,
            'total_processed': 0,
            'entity_types': {
                'PERSON': 0,
                'ORG': 0,
                'DATE': 0,
                'LOC': 0,
                'MISC': 0
            }
        }
        
        # Track unique users for reporting
        unique_users = set()
        
        # Process activities to build stats
        for activity in activities:
            try:
                metadata = activity.activity_metadata or {}
                unique_users.add(activity.user_id)
                
                if activity.activity_type == 'llm_request':
                    # Get total tokens and cost
                    total_tokens = metadata.get('total_tokens', 0)
                    cost_cents = metadata.get('cost_cents', round(metadata.get('cost', 0) * 100, 2))
                    processing_time = metadata.get('processing_time_ms', round(metadata.get('processing_time', 0) * 1000))
                    
                    # Update totals
                    llm_stats['total_tokens'] += total_tokens
                    llm_stats['total_cost_cents'] += cost_cents
                    llm_stats['total_requests'] += 1
                    
                    # Update averages with running calculation
                    n = llm_stats['total_requests']
                    if n > 0:  # Prevent division by zero
                        llm_stats['avg_tokens_per_request'] = round(llm_stats['total_tokens'] / n)
                        llm_stats['avg_cost_cents_per_request'] = round(llm_stats['total_cost_cents'] / n, 2)
                        llm_stats['avg_processing_time_ms'] = round(
                            (llm_stats['avg_processing_time_ms'] * (n - 1) + processing_time) / n
                        )
                    
                    # Model tracking
                    model = str(metadata.get('model', 'unknown'))  # Ensure model is a string
                    llm_stats['models_used'].add(model)
                    llm_stats['requests_by_model'][model] = llm_stats['requests_by_model'].get(model, 0) + 1
                    
                    # Track tokens by model
                    if model not in llm_stats['tokens_by_model']:
                        llm_stats['tokens_by_model'][model] = {
                            'total_tokens': 0,
                            'avg_tokens_per_request': 0,
                            'avg_cost_cents_per_request': 0
                        }
                    
                    model_stats = llm_stats['tokens_by_model'][model]
                    model_stats['total_tokens'] += total_tokens
                    
                    model_requests = llm_stats['requests_by_model'][model]
                    if model_requests > 0:
                        model_stats['avg_tokens_per_request'] = round(model_stats['total_tokens'] / model_requests)
                        model_stats['avg_cost_cents_per_request'] = round(
                            (model_stats.get('total_cost_cents', 0) + cost_cents) / model_requests, 2
                        )
                    
                    # Success rate - count requests that completed without errors
                    successes = sum(1 for a in activities 
                        if a.activity_type == 'llm_request' and 
                        (a.activity_metadata or {}).get('status') == 'success' or 
                        'error' not in (a.activity_metadata or {}))
                    llm_stats['success_rate'] = round((successes * 100 / n), 1) if n > 0 else 0
                    logger.debug(f"LLM success rate: {llm_stats['success_rate']}% ({successes}/{n})")
                
                elif activity.activity_type in ['email_processing', 'pipeline_processing', 'email_analysis']:
                    # Handle both old and new metadata structures
                    if 'analysis_stats' in metadata:
                        stats = metadata['analysis_stats']
                    elif 'stats' in metadata:
                        stats = metadata['stats']
                    else:
                        stats = metadata
                    
                    # Update email stats
                    for key in ['total_fetched', 'new_emails', 'successfully_parsed', 'successfully_analyzed', 
                              'failed_parsing', 'failed_analysis', 'needs_action', 'has_deadline']:
                        email_stats[key] += stats.get(key, 0)
                    
                    # Update category and priority distributions
                    categories = stats.get('categories', {})
                    if isinstance(categories, dict):
                        for category, count in categories.items():
                            if category and category in email_stats['categories']:
                                email_stats['categories'][category] += count
                    
                    priority_levels = stats.get('priority_levels', {})
                    if isinstance(priority_levels, dict):
                        for level, count in priority_levels.items():
                            if level and level in email_stats['priority_levels']:
                                email_stats['priority_levels'][level] += count
                
                elif activity.activity_type == 'nlp_processing':
                    nlp_stats['total_processed'] += 1
                    nlp_stats['total_emails'] += 1
                    nlp_stats['total_entities'] += len(metadata.get('entities', {}))
                    
                    if metadata.get('is_urgent', False):
                        nlp_stats['urgent_emails'] += 1
                    
                    # Update running averages
                    n = nlp_stats['total_processed']
                    if n > 0:
                        nlp_stats['avg_sentences_per_email'] = (
                            (nlp_stats['avg_sentences_per_email'] * (n - 1) + 
                             metadata.get('sentence_count', 0)) / n
                        )
                        if 'processing_time' in metadata:
                            nlp_stats['avg_processing_time'] = (
                                (nlp_stats['avg_processing_time'] * (n - 1) +
                                 metadata['processing_time']) / n
                            )
                    
                    # Update entity types
                    entities = metadata.get('entities', {})
                    if isinstance(entities, dict):
                        for entity_type in entities:
                            if entity_type and entity_type in nlp_stats['entity_types']:
                                nlp_stats['entity_types'][entity_type] += 1
                            
            except Exception as e:
                logger.error(f"Error processing activity {activity.id}: {e}")
                continue
        
        # Get user statistics
        total_users = db.session.query(User).count()
        active_today = db.session.query(UserActivity.user_id).distinct().filter(
            UserActivity.created_at >= datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        ).count()
        
        # Prepare response data
        llm_stats['models_used'] = list(llm_stats['models_used'])
        response_data = {
            'llm_stats': llm_stats,
            'email_stats': email_stats,
            'nlp_stats': nlp_stats,
            'user_stats': {
                'total_users': total_users,
                'active_users': len(unique_users),
                'active_today': active_today
            },
            'recent_activities': [
                {
                    'type': activity.activity_type,
                    'description': activity.description,
                    'created_at': activity.created_at.isoformat(),
                    'metadata': activity.activity_metadata or {},
                    'user_email': activity.user.email,
                    'user_name': activity.user.name
                }
                for activity in activities[:10]
            ]
        }
        
        logger.info(f"Analytics summary: {total_users} total users, {len(unique_users)} active users, {active_today} active today")
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Failed to get user analytics: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@user_bp.route('/api/debug/activities')
@admin_required
def debug_activities():
    """Debug endpoint to inspect raw activities.
    
    Admin-only endpoint for retrieving detailed information about the most
    recent user activities for debugging purposes.
    
    Returns:
        JSON response: The last 50 user activities with detailed metadata.
        
    Raises:
        Exception: If there's an error fetching the activities, returns a 500 error.
    """
    try:
        logger.info("Fetching debug activities")
        # Get last 50 activities
        activities = db.session.query(UserActivity).join(User).order_by(UserActivity.created_at.desc()).limit(50).all()
        
        logger.info(f"Found {len(activities)} activities")
        
        activity_data = []
        for activity in activities:
            logger.info(f"Processing activity: {activity.activity_type} from {activity.user.email}")
            activity_data.append({
                'id': activity.id,
                'type': activity.activity_type,
                'description': activity.description,
                'created_at': activity.created_at.isoformat(),
                'metadata': activity.activity_metadata,
                'user_email': activity.user.email
            })
            
        response = {
            'activities': activity_data,
            'count': len(activity_data)
        }
        logger.info(f"Returning {len(activity_data)} activities")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Failed to get debug activities: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@user_bp.route('/api/settings', methods=['GET', 'POST'])
@login_required
def get_user_settings():
    """Get or update user settings API endpoint.
    
    GET requests return all user settings.
    POST requests update a single setting specified in the request body.
    
    Args:
        For POST requests, requires JSON with 'setting' and 'value' keys.
    
    Returns:
        JSON response: For GET: All user settings
                      For POST: Updated setting value or group
                      
    Raises:
        Exception: If there's an error processing the request, returns a 400, 404, or 500 error.
    """
    try:
        user = User.query.get(session['user']['id'])
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
        
        # Handle POST request to update settings
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'setting' not in data or 'value' not in data:
                return jsonify({
                    'status': 'error',
                    'message': 'Missing required parameters'
                }), 400
            
            setting = data['setting']
            value = data['value']
            
            # Get current value for logging
            current_value = user.get_setting(setting)
            logger.info(f"API: Updating setting {setting} from {current_value} to: {value}")
            
            # Update the setting
            user.set_setting(setting, value)
            
            # Get the updated value for verification
            updated_value = user.get_setting(setting)
            
            # Get the group name for the setting (if any)
            group = setting.split('.')[0] if '.' in setting else None
            
            # Log the activity
            log_activity(
                user_id=user.id,
                activity_type='settings_update',
                description=f"Updated setting: {setting}",
                metadata={
                    'key': setting,
                    'old_value': current_value,
                    'new_value': updated_value,
                    'group': group,
                    'source': 'api'
                }
            )
            
            # Prepare response
            response_data = {
                "status": "success",
                "message": "Setting updated successfully",
                "value": updated_value
            }
            
            # Include the entire group if applicable
            if group:
                response_data["group"] = user.get_settings_group(group)
            
            return jsonify(response_data)
        
        # Handle GET request to retrieve settings
        settings = user.get_all_settings()
        return jsonify({
            'status': 'success',
            'settings': settings
        })
    except Exception as e:
        logger.error(f"Failed to handle user settings: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 