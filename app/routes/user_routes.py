"""User settings and analytics routes."""

from flask import Blueprint, jsonify, request, session, render_template
from ..models import User, UserActivity, log_activity
from ..auth.decorators import login_required, admin_required
import logging
from datetime import datetime
from .. import db

user_bp = Blueprint('user', __name__)
logger = logging.getLogger(__name__)

@user_bp.route('/analytics')
@admin_required
def analytics_dashboard():
    """Display the analytics dashboard."""
    return render_template('analytics.html')

@user_bp.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    """Get user settings."""
    try:
        user = User.query.get(session['user']['id'])
        return jsonify(user.settings)
    except Exception as e:
        logger.error(f"Failed to get user settings: {e}")
        return jsonify({"error": str(e)}), 500

@user_bp.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    """Update user settings."""
    try:
        user = User.query.get(session['user']['id'])
        user.update_settings(request.json)
        log_activity(
            user_id=user.id,
            activity_type='settings_update',
            description="User settings updated",
            metadata=request.json
        )
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Failed to update user settings: {e}")
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
        
        logger.info(f"Activity distribution by user:")
        for email, count in user_activity_counts.items():
            logger.info(f"User {email}: {count} activities")
        
        logger.info(f"Found {len(activities)} total activities across {len(user_activity_counts)} users")
        
        # Aggregate LLM usage
        llm_stats = {
            'total_tokens': 0,
            'total_prompts': 0,
            'models_used': set(),
            'avg_prompt_length': 0,
            'total_cost': 0  # If you track costs
        }
        
        # Aggregate email processing stats
        email_stats = {
            'total_fetched': 0,
            'new_emails': 0,
            'successfully_parsed': 0,
            'successfully_analyzed': 0,
            'failed_parsing': 0,
            'failed_analysis': 0
        }
        
        # Aggregate NLP stats
        nlp_stats = {
            'entities_extracted': 0,
            'sentiment_analyses': 0,
            'keywords_extracted': 0,
            'avg_processing_time': 0,
            'total_processed': 0
        }
        
        # Track unique users for reporting
        unique_users = set()
        
        # Process activities to build stats
        for activity in activities:
            try:
                metadata = activity.activity_metadata or {}
                unique_users.add(activity.user_id)
                
                if activity.activity_type == 'llm_request':
                    llm_stats['total_tokens'] += metadata.get('total_tokens', 0)
                    llm_stats['total_prompts'] += 1
                    llm_stats['models_used'].add(metadata.get('model', 'unknown'))
                    llm_stats['total_cost'] += metadata.get('cost', 0)
                    if 'prompt_length' in metadata:
                        llm_stats['avg_prompt_length'] = (
                            (llm_stats['avg_prompt_length'] * (llm_stats['total_prompts'] - 1) +
                             metadata['prompt_length']) / llm_stats['total_prompts']
                        )
                
                elif activity.activity_type == 'email_processing':
                    email_stats['total_fetched'] += metadata.get('emails_fetched', 0)
                    email_stats['new_emails'] += metadata.get('new_emails', 0)
                    email_stats['successfully_parsed'] += metadata.get('successfully_parsed', 0)
                    email_stats['successfully_analyzed'] += metadata.get('successfully_analyzed', 0)
                    email_stats['failed_parsing'] += metadata.get('failed_parsing', 0)
                    email_stats['failed_analysis'] += metadata.get('failed_analysis', 0)
                
                elif activity.activity_type == 'nlp_processing':
                    nlp_stats['entities_extracted'] += metadata.get('entities_extracted', 0)
                    nlp_stats['sentiment_analyses'] += metadata.get('sentiment_analyses', 0)
                    nlp_stats['keywords_extracted'] += metadata.get('keywords_extracted', 0)
                    nlp_stats['total_processed'] += 1
                    if 'processing_time' in metadata:
                        nlp_stats['avg_processing_time'] = (
                            (nlp_stats['avg_processing_time'] * (nlp_stats['total_processed'] - 1) +
                             metadata['processing_time']) / nlp_stats['total_processed']
                        )
            except Exception as e:
                logger.error(f"Error processing activity {activity.id} for user {activity.user.email}: {e}")
                continue
        
        # Get total number of users in the system
        total_users = db.session.query(User).count()
        
        # Get active users today using db.session
        active_today = db.session.query(UserActivity.user_id).distinct().filter(
            UserActivity.created_at >= datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        ).count()
        
        # Convert sets to lists for JSON serialization
        llm_stats['models_used'] = list(llm_stats['models_used'])
        
        response_data = {
            'llm_stats': llm_stats,
            'email_stats': email_stats,
            'nlp_stats': nlp_stats,
            'user_stats': {
                'total_users': total_users,  # Use actual count from users table
                'active_users': len(unique_users),  # Users with any activity
                'active_today': active_today
            },
            'recent_activities': [
                {
                    'type': activity.activity_type,
                    'description': activity.description,
                    'created_at': activity.created_at.isoformat(),
                    'metadata': activity.activity_metadata,
                    'user_email': activity.user.email,  # Add user email for admin view
                    'user_name': activity.user.name  # Add user name for better identification
                }
                for activity in activities[:10]  # Last 10 activities
            ]
        }
        
        logger.info(f"Successfully compiled analytics. Stats: {total_users} total users, {len(unique_users)} active users, {active_today} active today")
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Failed to get user analytics: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500 