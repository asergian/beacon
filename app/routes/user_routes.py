"""User settings and analytics routes."""

from flask import Blueprint, jsonify, request, session, render_template
from ..models import User, UserActivity, log_activity
from ..auth.decorators import login_required, admin_required
import logging
from datetime import datetime, timedelta
from .. import db, cache

user_bp = Blueprint('user', __name__)
logger = logging.getLogger(__name__)

@user_bp.route('/analytics')
@admin_required
def analytics_dashboard():
    """Display the analytics dashboard."""
    return render_template('analytics.html')

@user_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Handle settings page and updates."""
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
            
        return render_template('settings.html', user_settings=user_settings)
        
    except Exception as e:
        logger.error(f"Failed to handle settings request: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@user_bp.route('/api/analytics')
@admin_required
def get_analytics():
    """Get user activity analytics."""
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
                    model = metadata.get('model', 'unknown')
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
                        (a.activity_metadata.get('status') == 'success' or 
                         'error' not in a.activity_metadata))
                    llm_stats['success_rate'] = round((successes * 100 / n), 1) if n > 0 else 0
                    logger.debug(f"LLM success rate: {llm_stats['success_rate']}% ({successes}/{n})")
                
                elif activity.activity_type in ['email_processing', 'pipeline_processing']:
                    stats = metadata.get('stats', {})
                    
                    # Update email stats
                    for key in ['total_fetched', 'new_emails', 'successfully_parsed', 'successfully_analyzed', 
                              'failed_parsing', 'failed_analysis', 'needs_action', 'has_deadline']:
                        email_stats[key] += stats.get(key, 0)
                    
                    # Update category and priority distributions
                    for category, count in stats.get('categories', {}).items():
                        if category in email_stats['categories']:
                            email_stats['categories'][category] += count
                    
                    for level, count in stats.get('priority_levels', {}).items():
                        if level in email_stats['priority_levels']:
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
                    for entity_type in metadata.get('entities', {}).keys():
                        if entity_type in nlp_stats['entity_types']:
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
                    'metadata': activity.activity_metadata,
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
    """Debug endpoint to inspect raw activities."""
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