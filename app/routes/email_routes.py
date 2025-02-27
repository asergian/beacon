"""Email processing and viewing routes."""

from flask import Blueprint, current_app, render_template, jsonify, request, redirect, url_for, session, Response, stream_with_context
import logging
from ..auth.decorators import login_required
from ..email.models.analysis_command import AnalysisCommand
from ..models import log_activity
import asyncio
from functools import wraps
from ..models import User
import json
import time
from datetime import datetime, timedelta
import random
from ..email.demo_emails import get_demo_email_bodies
from ..email.demo_analysis import demo_analysis, load_analysis_cache
from ..utils.memory_utils import log_memory_cleanup
import gc

def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(f(*args, **kwargs))
    return wrapper

# Set up logger
logger = logging.getLogger(__name__)
email_bp = Blueprint('email', __name__)

@email_bp.route('/')
@login_required
def home():
    """Home page that loads email UI without waiting for data."""
    return render_template('email_summary.html', 
                         emails=[],
                         tiny_mce_api_key=current_app.config.get('TINYMCE_API_KEY', ''))

@email_bp.route('/api/user/settings')
@login_required
def get_user_settings():
    """Get user settings."""
    try:
        user = User.query.get(session['user']['id'])
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
            
        settings = user.get_all_settings()
        return jsonify({
            'status': 'success',
            'settings': settings
        })
    except Exception as e:
        logger.error(f"Failed to get user settings: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Note: We previously had a /api/emails/metadata endpoint here for fetching basic email data
# It has been replaced by /api/emails/cached which serves analyzed emails from cache
# This provides a better UX by showing full email analysis while waiting for fresh data

def get_demo_emails():
    """Generate demo email data."""
    logger.info("Generating demo emails...")
    now = datetime.utcnow()
    
    # Helper function to generate random past date within a range
    def random_past_date(min_days, max_days):
        days = random.uniform(min_days, max_days)
        return now - timedelta(days=days)
    
    # Get demo email bodies
    demo_bodies = get_demo_email_bodies()
    
    # Load pre-generated analysis if available
    try:
        # Ensure we're in an application context
        if not current_app:
            raise RuntimeError("This function must be called within a Flask application context")
            
        # Initialize OpenAI client if not already done
        if not hasattr(current_app, 'get_openai_client'):
            from .. import init_openai_client
            init_openai_client(current_app)
            
        load_analysis_cache()
    except Exception as e:
        logger.warning(f"Could not load analysis cache: {e}")
    
    demo_emails = [
        {
            "id": "demo1",
            "subject": "Welcome to Demo Mode",
            "sender": "demo-team@example.com",
            "recipient": "demo@example.com",
            "date": (now - timedelta(hours=1)).isoformat(),
            "body": demo_bodies["demo1"],
            "snippet": "Welcome to the demo mode of our email app! This is a sample email to show you how the app works.",
            "is_read": False,
            "labels": ["inbox", "important"],
            "entities": {
                "PRODUCT": ["email app"],
                "FEATURE": ["AI-powered analysis", "Smart prioritization", "Action detection"],
                "ORG": ["Demo Team"]
            },
            "key_phrases": [
                "demo mode exploration",
                "key features overview",
                "AI-powered functionality"
            ],
            "sentence_count": 8,
            "sentiment_indicators": {
                "positive": ["welcome", "explore", "smart", "powered"],
                "neutral": []
            },
            "structural_elements": {
                "verbs": ["welcome", "explore", "try", "let"],
                "named_entities": ["Demo Team", "AI"],
                "dependencies": ["subject", "object", "modifier"]
            },
            "needs_action": True,
            "category": "Informational",
            "action_items": [
                {
                    "description": "Explore app features and provide feedback",
                    "due_date": (now + timedelta(days=7)).strftime('%Y-%m-%d')
                }
            ],
            "summary": "Welcome email introducing the demo mode and its key features. The email highlights AI-powered analysis, smart prioritization, and action item detection. A request for feedback is included with a suggested timeline.",
            "priority": 75,
            "priority_level": "HIGH",
            "custom_categories": {
                "Type": "Onboarding",
                "Communication Style": "Instructional Friendly"
            }
        },
        {
            "id": "demo2",
            "subject": "Your Weekly Summary",
            "sender": "reports@example.com",
            "recipient": "demo@example.com",
            "date": (now - timedelta(days=1)).isoformat(),
            "body": demo_bodies["demo2"],
            "snippet": "Here's your weekly summary of activity. You had 5 important meetings and 3 deadlines completed.",
            "is_read": True,
            "labels": ["inbox"],
            "entities": {
                "PROJECT": ["Database optimization", "API documentation", "Frontend testing"],
                "EVENT": ["Client meeting", "Team sync"],
                "TIME": ["weekly", "tomorrow", "next week"]
            },
            "key_phrases": [
                "weekly activity summary",
                "completed tasks overview",
                "upcoming deadlines"
            ],
            "sentence_count": 12,
            "sentiment_indicators": {
                "positive": ["great progress", "momentum"],
                "neutral": ["review", "testing"]
            },
            "structural_elements": {
                "verbs": ["completed", "review", "testing"],
                "named_entities": ["API", "Frontend"],
                "dependencies": ["subject", "object", "temporal"]
            },
            "needs_action": True,
            "category": "Work",
            "action_items": [
                {
                    "description": "Review API documentation",
                    "due_date": (now + timedelta(days=1)).strftime('%Y-%m-%d')
                },
                {
                    "description": "Complete Frontend testing",
                    "due_date": (now + timedelta(days=7)).strftime('%Y-%m-%d')
                }
            ],
            "summary": "Weekly progress report highlighting 3 completed tasks including database optimization and team meetings. Two upcoming deadlines: API documentation review (due tomorrow) and frontend testing (next week).",
            "priority": 60,
            "priority_level": "MEDIUM",
            "custom_categories": {
                "Type": "Report",
                "Communication Style": "Formal Analytical"
            }
        },
        {
            "id": "demo3",
            "subject": "Team Meeting Notes",
            "sender": "team-lead@example.com",
            "recipient": "demo@example.com",
            "date": (now - timedelta(days=2)).isoformat(),
            "body": demo_bodies["demo3"],
            "snippet": "Notes from yesterday's team meeting: We discussed the upcoming project milestones and assigned tasks.",
            "is_read": True,
            "labels": ["inbox", "work"],
            "entities": {
                "COMPONENT": ["Backend service", "User authentication", "Analytics dashboard"],
                "TASK": ["deployment", "security audit", "user testing"],
                "PERSON": ["Team Lead"]
            },
            "key_phrases": [
                "project updates discussion",
                "task assignments",
                "next steps planning"
            ],
            "sentence_count": 15,
            "sentiment_indicators": {
                "neutral": ["update", "completed", "fixed"],
                "positive": ["prioritized", "progress"]
            },
            "structural_elements": {
                "verbs": ["update", "begin", "plan", "schedule"],
                "named_entities": ["Team Lead", "EOD"],
                "dependencies": ["subject", "object", "temporal"]
            },
            "needs_action": True,
            "category": "Work",
            "action_items": [
                {
                    "description": "Update tasks in project board",
                    "due_date": (now.strftime('%Y-%m-%d'))
                }
            ],
            "summary": "Team meeting notes covering completed backend deployment and bug fixes. New tasks include analytics dashboard development, security audit, and user testing. Action required: Update project board tasks by end of day.",
            "priority": 70,
            "priority_level": "MEDIUM",
            "custom_categories": {
                "Type": "Meeting",
                "Communication Style": "Formal Analytical"
            }
        },
        {
            "id": "demo4",
            "subject": "🎉 Special Weekend Sale - 50% Off All Products!",
            "sender": "marketing@example.com",
            "recipient": "demo@example.com",
            "date": (now - timedelta(days=3)).isoformat(),
            "body": """
            <div style="color: #333;">
                <h2 style="color: #ff6b6b;">🎉 Mega Weekend Sale!</h2>
                <p>Don't miss out on our biggest sale of the year:</p>
                <ul>
                    <li>50% off all products</li>
                    <li>Free shipping on orders over $50</li>
                    <li>Extra 10% off for premium members</li>
                </ul>
                <p><strong>Sale ends Sunday at midnight!</strong></p>
                <p><a href="#">Shop Now</a></p>
                <p style="font-size: 0.8em;">Terms and conditions apply. Unsubscribe.</p>
            </div>
            """,
            "snippet": "Don't miss out on our biggest sale of the year! 50% off all products, free shipping on orders over $50...",
            "is_read": True,
            "labels": ["promotions"],
            "entities": {
                "DISCOUNT": ["50% off", "10% off"],
                "CONDITION": ["orders over $50", "premium members"],
                "TIME": ["Weekend", "Sunday midnight"]
            },
            "key_phrases": [
                "weekend sale",
                "biggest sale of the year",
                "free shipping"
            ],
            "sentence_count": 8,
            "sentiment_indicators": {
                "positive": ["special", "biggest", "free"],
                "neutral": ["terms", "conditions"]
            },
            "structural_elements": {
                "verbs": ["miss", "shop", "ends"],
                "named_entities": ["Sunday"],
                "dependencies": ["subject", "object", "temporal"]
            },
            "needs_action": False,
            "category": "Promotions",
            "action_items": [],
            "summary": "Marketing email announcing a weekend sale with 50% off all products and free shipping on orders over $50. Additional 10% discount available for premium members. Sale ends Sunday at midnight.",
            "priority": 20,
            "priority_level": "LOW",
            "custom_categories": {
                "Type": "Marketing",
                "Communication Style": "Creative Enthusiastic"
            }
        },
        {
            "id": "demo5",
            "subject": "Family Dinner This Weekend?",
            "sender": "mom@example.com",
            "recipient": "demo@example.com",
            "date": (now - timedelta(days=4)).isoformat(),
            "body": """
            <div>
                <p>Hi sweetie,</p>
                <p>I hope you're doing well! Dad and I were thinking of having a family dinner this Saturday at 6 PM. Your sister will be in town, and it would be wonderful if you could join us.</p>
                <p>I'm planning to make your favorite lasagna! Let me know if you can make it.</p>
                <p>Love,<br>Mom</p>
            </div>
            """,
            "snippet": "Hi sweetie, I hope you're doing well! Dad and I were thinking of having a family dinner this Saturday...",
            "is_read": False,
            "labels": ["inbox"],
            "entities": {
                "PERSON": ["Mom", "Dad", "sister"],
                "TIME": ["Saturday", "6 PM"],
                "FOOD": ["lasagna"]
            },
            "key_phrases": [
                "family dinner",
                "weekend plans",
                "sister visiting"
            ],
            "sentence_count": 5,
            "sentiment_indicators": {
                "positive": ["wonderful", "favorite", "love"],
                "neutral": []
            },
            "structural_elements": {
                "verbs": ["hope", "thinking", "planning"],
                "named_entities": ["Saturday"],
                "dependencies": ["subject", "object", "temporal"]
            },
            "needs_action": True,
            "category": "Personal",
            "action_items": [
                {
                    "description": "Respond to Mom about family dinner",
                    "due_date": (now + timedelta(days=2)).strftime('%Y-%m-%d')
                }
            ],
            "summary": "Mom is organizing a family dinner this Saturday at 6 PM. Sister will be visiting, and Mom will make lasagna. Response needed to confirm attendance.",
            "priority": 65,
            "priority_level": "MEDIUM",
            "custom_categories": {
                "Type": "Family",
                "Communication Style": "Instructional Friendly"
            }
        },
        {
            "id": "demo6",
            "subject": "Your Account Security Alert",
            "sender": "security@example.com",
            "recipient": "demo@example.com",
            "date": (now - timedelta(days=5)).isoformat(),
            "body": """
            <div>
                <p><strong>Security Alert:</strong></p>
                <p>We detected a login attempt to your account from a new device:</p>
                <ul>
                    <li>Location: San Francisco, CA</li>
                    <li>Device: iPhone</li>
                    <li>Time: Today at 2:15 PM PST</li>
                </ul>
                <p>If this was you, no action is needed. If you don't recognize this activity, please secure your account immediately.</p>
                <p><a href="#">Review Account Activity</a></p>
            </div>
            """,
            "snippet": "Security Alert: We detected a login attempt to your account from a new device...",
            "is_read": True,
            "labels": ["inbox"],
            "entities": {
                "LOCATION": ["San Francisco", "CA"],
                "DEVICE": ["iPhone"],
                "TIME": ["2:15 PM PST"]
            },
            "key_phrases": [
                "security alert",
                "login attempt",
                "new device"
            ],
            "sentence_count": 6,
            "sentiment_indicators": {
                "neutral": ["detected", "secure"],
                "negative": ["alert"]
            },
            "structural_elements": {
                "verbs": ["detected", "secure", "review"],
                "named_entities": ["San Francisco", "CA", "iPhone"],
                "dependencies": ["subject", "object", "condition"]
            },
            "needs_action": False,
            "category": "Informational",
            "action_items": [],
            "summary": "Security notification about a new device login from San Francisco using an iPhone. No action needed if the login attempt was legitimate.",
            "priority": 55,
            "priority_level": "MEDIUM",
            "custom_categories": {
                "Type": "Security",
                "Communication Style": "Direct Authoritative"
            }
        },
        {
            "id": "demo7",
            "subject": "Quarterly Financial Report - Q3 2024",
            "sender": "finance@example.com",
            "recipient": "demo@example.com",
            "date": random_past_date(6, 7).isoformat(),
            "body": """
            <div>
                <p>Dear Team,</p>
                <p>Please find attached the Q3 2024 financial report. Key highlights:</p>
                <ul>
                    <li>Revenue increased by 15% YoY</li>
                    <li>Operating costs reduced by 8%</li>
                    <li>New market expansion on track</li>
                </ul>
                <p>The full report is available on the finance portal.</p>
                <p>Regards,<br>Finance Team</p>
            </div>
            """,
            "snippet": "Please find attached the Q3 2024 financial report. Key highlights: Revenue increased by 15% YoY...",
            "is_read": True,
            "labels": ["inbox"],
            "entities": {
                "METRIC": ["Revenue", "Operating costs"],
                "TIME": ["Q3 2024", "YoY"],
                "PERCENT": ["15%", "8%"]
            },
            "key_phrases": [
                "quarterly financial report",
                "revenue growth",
                "cost reduction"
            ],
            "sentence_count": 7,
            "sentiment_indicators": {
                "positive": ["increased", "reduced", "on track"],
                "neutral": ["report", "available"]
            },
            "structural_elements": {
                "verbs": ["find", "increased", "reduced"],
                "named_entities": ["Q3 2024", "Finance Team"],
                "dependencies": ["subject", "object", "modifier"]
            },
            "needs_action": False,
            "category": "Work",
            "action_items": [],
            "summary": "Q3 2024 financial report showing 15% YoY revenue growth and 8% reduction in operating costs. Full report available on finance portal.",
            "priority": 40,
            "priority_level": "LOW",
            "custom_categories": {
                "Type": "Report",
                "Communication Style": "Data Driven Analytical"
            }
        },
        {
            "id": "demo8",
            "subject": "🎨 Design Team Brainstorming Session",
            "sender": "creative-lead@example.com",
            "recipient": "demo@example.com",
            "date": random_past_date(7, 8).isoformat(),
            "body": """
            <div>
                <p>Hey creative minds! 🌟</p>
                <p>Let's get those creative juices flowing! I'm organizing a brainstorming session for our new brand identity project.</p>
                <p>Bring your wildest ideas - no idea is too crazy! We'll have snacks, music, and lots of colorful sticky notes.</p>
                <p>When: Tomorrow, 2 PM - 4 PM<br>Where: Rainbow Room<br>What to bring: Your imagination!</p>
                <p>Can't wait to see what we come up with together! 🎨✨</p>
                <p>Cheers,<br>Sarah</p>
            </div>
            """,
            "snippet": "Hey creative minds! 🌟 Let's get those creative juices flowing! I'm organizing a brainstorming session...",
            "is_read": False,
            "labels": ["inbox"],
            "entities": {
                "PERSON": ["Sarah"],
                "LOCATION": ["Rainbow Room"],
                "TIME": ["Tomorrow", "2 PM", "4 PM"]
            },
            "key_phrases": [
                "brainstorming session",
                "brand identity project",
                "creative ideas"
            ],
            "sentence_count": 8,
            "sentiment_indicators": {
                "positive": ["creative", "wildest", "exciting"],
                "neutral": ["bring", "organizing"]
            },
            "structural_elements": {
                "verbs": ["get", "bring", "come"],
                "named_entities": ["Sarah", "Rainbow Room"],
                "dependencies": ["subject", "object", "temporal"]
            },
            "needs_action": True,
            "category": "Work",
            "action_items": [
                {
                    "description": "Attend design team brainstorming session",
                    "due_date": (now + timedelta(days=1)).strftime('%Y-%m-%d')
                }
            ],
            "summary": "Creative team brainstorming session scheduled for tomorrow from 2-4 PM in the Rainbow Room for the new brand identity project. Participants encouraged to bring creative ideas.",
            "priority": 50,
            "priority_level": "MEDIUM",
            "custom_categories": {
                "Type": "Meeting",
                "Communication Style": "Creative Enthusiastic"
            }
        },
        {
            "id": "demo9",
            "subject": "📚 Book Club Discussion: 'The Innovation Mindset'",
            "sender": "bookclub@example.com",
            "recipient": "demo@example.com",
            "date": random_past_date(8, 9).isoformat(),
            "body": """
            <div>
                <p>Fellow readers,</p>
                <p>What an enlightening discussion we had about 'The Innovation Mindset' yesterday! Here are some key takeaways from our conversation:</p>
                <ul>
                    <li>The role of psychological safety in fostering innovation</li>
                    <li>How to build effective cross-functional teams</li>
                    <li>Practical exercises for developing creative thinking</li>
                </ul>
                <p>Next month's book: "Digital Transformation in the Modern Age"</p>
                <p>Happy reading!<br>Book Club Team</p>
            </div>
            """,
            "snippet": "What an enlightening discussion we had about 'The Innovation Mindset' yesterday! Here are some key takeaways...",
            "is_read": True,
            "labels": ["inbox"],
            "entities": {
                "WORK_OF_ART": ["The Innovation Mindset", "Digital Transformation in the Modern Age"],
                "TOPIC": ["innovation", "psychological safety", "creative thinking"]
            },
            "key_phrases": [
                "book club discussion",
                "innovation mindset",
                "key takeaways"
            ],
            "sentence_count": 6,
            "sentiment_indicators": {
                "positive": ["enlightening", "effective", "happy"],
                "neutral": ["discussion", "takeaways"]
            },
            "structural_elements": {
                "verbs": ["had", "build", "developing"],
                "named_entities": ["Book Club Team"],
                "dependencies": ["subject", "object", "modifier"]
            },
            "needs_action": False,
            "category": "Personal",
            "action_items": [],
            "summary": "Summary of book club discussion on 'The Innovation Mindset' with key takeaways and announcement of next month's book.",
            "priority": 30,
            "priority_level": "LOW",
            "custom_categories": {
                "Type": "Social",
                "Communication Style": "Intellectual Collaborative"
            }
        },
        {
            "id": "demo10",
            "subject": "🚨 System Maintenance Notice",
            "sender": "it-support@example.com",
            "recipient": "demo@example.com",
            "date": random_past_date(9, 10).isoformat(),
            "body": """
            <div style="font-family: Arial, sans-serif;">
                <p><strong>IMPORTANT NOTICE</strong></p>
                <p>Our systems will undergo critical maintenance tonight from 22:00 to 02:00 UTC.</p>
                <p>Impact:</p>
                <ul>
                    <li>Email services: 30 minutes downtime</li>
                    <li>Cloud storage: Read-only access</li>
                    <li>Internal tools: Intermittent availability</li>
                </ul>
                <p>Please save your work and log out before 21:45 UTC.</p>
                <p>Contact: IT Support (ext. 5555)</p>
            </div>
            """,
            "snippet": "IMPORTANT NOTICE: Our systems will undergo critical maintenance tonight from 22:00 to 02:00 UTC...",
            "is_read": False,
            "labels": ["inbox", "important"],
            "entities": {
                "TIME": ["22:00", "02:00", "21:45"],
                "ORGANIZATION": ["IT Support"],
                "CONTACT": ["ext. 5555"]
            },
            "key_phrases": [
                "system maintenance",
                "critical maintenance",
                "downtime"
            ],
            "sentence_count": 7,
            "sentiment_indicators": {
                "neutral": ["notice", "maintenance"],
                "negative": ["downtime", "critical"]
            },
            "structural_elements": {
                "verbs": ["undergo", "save", "log out"],
                "named_entities": ["UTC", "IT Support"],
                "dependencies": ["temporal", "object", "condition"]
            },
            "needs_action": True,
            "category": "Work",
            "action_items": [
                {
                    "description": "Save work and log out before maintenance",
                    "due_date": (now + timedelta(hours=4)).strftime('%Y-%m-%d')
                }
            ],
            "summary": "Critical system maintenance scheduled for tonight with various service impacts. Users must save work and log out before 21:45 UTC.",
            "priority": 80,
            "priority_level": "HIGH",
            "custom_categories": {
                "Type": "System",
                "Communication Style": "Direct Authoritative"
            }
        },
        {
            "id": "demo11",
            "subject": "🌱 Eco-Initiative: Office Plant Program Launch",
            "sender": "green-team@example.com",
            "recipient": "demo@example.com",
            "date": random_past_date(10, 11).isoformat(),
            "body": """
            <div>
                <p>Dear colleagues,</p>
                <p>We're excited to announce our new Office Plant Program! 🌿</p>
                <p>Studies show that plants in the workplace can:</p>
                <ul>
                    <li>Reduce stress by 37%</li>
                    <li>Increase productivity by 15%</li>
                    <li>Improve air quality significantly</li>
                </ul>
                <p>Want to participate? Fill out the plant preference form by Friday to get your desk plant!</p>
                <p>Green regards,<br>The Eco Team</p>
            </div>
            """,
            "snippet": "We're excited to announce our new Office Plant Program! 🌿 Studies show that plants in the workplace...",
            "is_read": True,
            "labels": ["inbox", "promotions"],
            "entities": {
                "PERCENT": ["37%", "15%"],
                "ORGANIZATION": ["Eco Team"],
                "TIME": ["Friday"]
            },
            "key_phrases": [
                "office plant program",
                "workplace benefits",
                "plant preference"
            ],
            "sentence_count": 8,
            "sentiment_indicators": {
                "positive": ["excited", "improve", "reduce stress"],
                "neutral": ["announce", "studies"]
            },
            "structural_elements": {
                "verbs": ["announce", "show", "improve"],
                "named_entities": ["Eco Team"],
                "dependencies": ["subject", "object", "temporal"]
            },
            "needs_action": True,
            "category": "Promotions",
            "action_items": [
                {
                    "description": "Fill out plant preference form",
                    "due_date": (now + timedelta(days=3)).strftime('%Y-%m-%d')
                }
            ],
            "summary": "Launch of new Office Plant Program with benefits explanation and invitation to participate by filling out preference form.",
            "priority": 35,
            "priority_level": "LOW",
            "custom_categories": {
                "Type": "Initiative",
                "Communication Style": "Informative Encouraging"
            }
        },
        {
            "id": "demo12",
            "subject": "Re: Project Timeline Discussion",
            "sender": "project-lead@example.com",
            "recipient": "demo@example.com",
            "date": random_past_date(11, 12).isoformat(),
            "body": """
            <div>
                <p>Thanks for your input during yesterday's meeting.</p>
                <p>After reviewing everyone's feedback, we've decided to:</p>
                <ol>
                    <li>Extend the research phase by two weeks</li>
                    <li>Combine phases 2 and 3 for efficiency</li>
                    <li>Keep the final delivery date unchanged</li>
                </ol>
                <p>Please update your team's schedules accordingly.</p>
                <p>Best,<br>Alex</p>
            </div>
            """,
            "snippet": "Thanks for your input during yesterday's meeting. After reviewing everyone's feedback, we've decided to...",
            "is_read": True,
            "labels": ["inbox"],
            "entities": {
                "PERSON": ["Alex"],
                "TIME": ["yesterday", "two weeks"],
                "PHASE": ["phase 2", "phase 3"]
            },
            "key_phrases": [
                "project timeline",
                "research phase",
                "team schedules"
            ],
            "sentence_count": 5,
            "sentiment_indicators": {
                "positive": ["thanks", "efficiency"],
                "neutral": ["update", "review"]
            },
            "structural_elements": {
                "verbs": ["review", "extend", "combine"],
                "named_entities": ["Alex"],
                "dependencies": ["temporal", "action", "object"]
            },
            "needs_action": True,
            "category": "Work",
            "action_items": [
                {
                    "description": "Update team schedules with new timeline",
                    "due_date": (now + timedelta(days=2)).strftime('%Y-%m-%d')
                }
            ],
            "summary": "Project timeline adjustments including extended research phase and combined phases 2-3, with final delivery date remaining unchanged.",
            "priority": 65,
            "priority_level": "MEDIUM",
            "custom_categories": {
                "Type": "Project",
                "Communication Style": "Professional Decisive"
            }
        },
        {
            "id": "demo13",
            "subject": "🎉 Weekend Tech Meetup Highlights",
            "sender": "community@tech-meetup.example.com",
            "recipient": "demo@example.com",
            "date": random_past_date(12, 13).isoformat(),
            "body": """
            <div>
                <p>Hey tech enthusiasts! 👋</p>
                <p>What an amazing weekend of learning and networking! Here's what you might have missed:</p>
                <ul>
                    <li>🚀 Keynote on "The Future of AI" by Dr. Smith</li>
                    <li>💡 Lightning talks on emerging technologies</li>
                    <li>🤝 Speed networking session with 50+ professionals</li>
                </ul>
                <p>Check out the event photos and presentations on our community portal!</p>
                <p>Stay awesome!<br>The Tech Meetup Team</p>
            </div>
            """,
            "snippet": "Hey tech enthusiasts! 👋 What an amazing weekend of learning and networking! Here's what you might have missed...",
            "is_read": True,
            "labels": ["inbox", "social"],
            "entities": {
                "PERSON": ["Dr. Smith"],
                "EVENT": ["The Future of AI", "Lightning talks"],
                "NUMBER": ["50+"]
            },
            "key_phrases": [
                "tech meetup",
                "learning",
                "networking"
            ],
            "sentence_count": 6,
            "sentiment_indicators": {
                "positive": ["amazing", "awesome"],
                "neutral": ["check out", "missed"]
            },
            "structural_elements": {
                "verbs": ["missed", "check"],
                "named_entities": ["Dr. Smith", "Tech Meetup Team"],
                "dependencies": ["subject", "object", "temporal"]
            },
            "needs_action": False,
            "category": "Personal",
            "action_items": [],
            "summary": "Recap of weekend tech meetup events including keynote speech, lightning talks, and networking session, with resources available on community portal.",
            "priority": 25,
            "priority_level": "LOW",
            "custom_categories": {
                "Type": "Community",
                "Communication Style": "Casual Enthusiastic"
            }
        },
        {
            "id": "demo14",
            "subject": "📊 Weekly Analytics Report",
            "sender": "analytics@example.com",
            "recipient": "demo@example.com",
            "date": random_past_date(13, 14).isoformat(),
            "body": """
            <div>
                <p>Weekly Analytics Summary:</p>
                <table>
                    <tr><td>User Growth:</td><td>+12.5%</td></tr>
                    <tr><td>Engagement Rate:</td><td>28.3%</td></tr>
                    <tr><td>Conversion Rate:</td><td>3.7%</td></tr>
                </table>
                <p>Key Insights:</p>
                <ul>
                    <li>Mobile usage increased by 15%</li>
                    <li>Peak activity: 2-4 PM EST</li>
                    <li>New feature adoption rate: 45%</li>
                </ul>
                <p>Full report available in the analytics dashboard.</p>
                <p>Regards,<br>Analytics Team</p>
            </div>
            """,
            "snippet": "Weekly Analytics Summary: User Growth: +12.5%, Engagement Rate: 28.3%, Conversion Rate: 3.7%...",
            "is_read": False,
            "labels": ["inbox"],
            "entities": {
                "PERCENT": ["12.5%", "28.3%", "3.7%", "15%", "45%"],
                "TIME": ["2-4 PM EST"],
                "METRIC": ["User Growth", "Engagement Rate", "Conversion Rate"]
            },
            "key_phrases": [
                "weekly analytics",
                "key insights",
                "mobile usage"
            ],
            "sentence_count": 5,
            "sentiment_indicators": {
                "positive": ["growth", "increased"],
                "neutral": ["summary", "report"]
            },
            "structural_elements": {
                "verbs": ["increased"],
                "named_entities": ["Analytics Team", "EST"],
                "dependencies": ["subject", "object", "temporal"]
            },
            "needs_action": False,
            "category": "Work",
            "action_items": [],
            "summary": "Weekly analytics report showing positive user growth, engagement metrics, and key insights about mobile usage and feature adoption.",
            "priority": 45,
            "priority_level": "MEDIUM",
            "custom_categories": {
                "Type": "Report",
                "Communication Style": "Data Driven Analytical"
            }
        },
        {
            "id": "demo15",
            "subject": "🎯 Personal Goal Check-in",
            "sender": "goals-tracker@example.com",
            "recipient": "demo@example.com",
            "date": random_past_date(14, 15).isoformat(),
            "body": """
            <div>
                <p>Hi there!</p>
                <p>Time for your monthly goal check-in! Here's your progress:</p>
                <ul>
                    <li>✅ Complete Python certification (Done!)</li>
                    <li>🏃‍♂️ Exercise 3x/week (On track)</li>
                    <li>📚 Read 2 books/month (1 book completed)</li>
                </ul>
                <p>Remember: Small steps lead to big achievements! 🌟</p>
                <p>Keep going!<br>Your Goals Assistant</p>
            </div>
            """,
            "snippet": "Time for your monthly goal check-in! Here's your progress: Complete Python certification (Done!)...",
            "is_read": True,
            "labels": ["inbox", "personal"],
            "entities": {
                "ACHIEVEMENT": ["Python certification"],
                "FREQUENCY": ["3x/week", "2 books/month"],
                "STATUS": ["Done", "On track"]
            },
            "key_phrases": [
                "goal check-in",
                "monthly progress",
                "personal development"
            ],
            "sentence_count": 6,
            "sentiment_indicators": {
                "positive": ["complete", "progress", "achievements"],
                "neutral": ["check-in", "remember"]
            },
            "structural_elements": {
                "verbs": ["complete", "exercise", "read"],
                "named_entities": ["Python"],
                "dependencies": ["subject", "object", "temporal"]
            },
            "needs_action": False,
            "category": "Personal",
            "action_items": [],
            "summary": "Monthly personal goal progress update showing completed Python certification, ongoing exercise routine, and reading progress.",
            "priority": 35,
            "priority_level": "LOW",
            "custom_categories": {
                "Type": "Personal Development",
                "Communication Style": "Motivational Supportive"
            }
        }
    ]
    
    logger.info(f"Generated {len(demo_emails)} demo emails")
    return demo_emails

@email_bp.route('/api/emails/cached')
@login_required
@async_route
async def get_cached_emails():
    """Get only cached emails without fetching from Gmail."""
    try:
        # Check if in demo mode
        if session.get('user', {}).get('is_demo', False):
            # Get user settings
            user = User.query.get(session['user']['id'])
            if not user:
                return jsonify({
                    'status': 'error',
                    'message': 'User not found'
                }), 404

            # Get demo emails
            demo_emails = get_demo_emails()

            # Apply user settings to demo emails
            settings = user.get_all_settings()
            
            # Check if AI features are enabled
            ai_enabled = settings.get('ai_features', {}).get('enabled', True)
            
            # Apply settings to each email
            for email in demo_emails:
                if not ai_enabled:
                    # If AI is disabled, remove AI-generated fields
                    email.pop('summary', None)
                    email.pop('priority', None)
                    email.pop('priority_level', None)
                    email.pop('category', None)
                    email.pop('custom_categories', None)
                    email.pop('entities', None)
                    email.pop('key_phrases', None)
                    email.pop('sentiment_indicators', None)
                    email.pop('needs_action', None)
                    email.pop('action_items', None)
                else:
                    # Get model type and context length settings
                    model_type = str(settings.get('ai_features', {}).get('model_type', 'gpt-4o-mini')).lower()
                    context_length = str(settings.get('ai_features', {}).get('context_length', '1000'))
                    summary_length = str(settings.get('ai_features', {}).get('summary_length', 'medium')).lower()

                    # Apply pre-generated analysis based on model and context length
                    email = demo_analysis.apply_analysis(email, model_type, context_length)
                    
                    # Apply additional enhancements based on model type
                    if model_type == 'gpt-4o':
                        # Enhanced analysis for premium model
                        email['analysis_quality'] = 'premium'
                        
                        # Enhance entities with relationships and context
                        if 'entities' in email:
                            enhanced_entities = {}
                            original_entities = dict(email['entities'])
                            for key, values in original_entities.items():
                                if isinstance(values, list):
                                    enhanced_entities[key] = list(values)
                                    enhanced_entities[f"{key}_context"] = [
                                        f"Impact: High relevance to {key.lower()}",
                                        f"Related Terms: {', '.join(values[:2])}"
                                    ]
                            email['entities'] = enhanced_entities
                        
                        # Add sophisticated key phrases with analysis
                        if 'key_phrases' in email:
                            original_phrases = email['key_phrases']
                            email['key_phrases'] = []
                            for phrase in original_phrases[:3]:
                                email['key_phrases'].extend([
                                    phrase,
                                    f"Analysis: {phrase} indicates significant business impact",
                                    f"Context: Frequently appears in important communications"
                                ])
                        
                        # Enhanced sentiment analysis
                        if 'sentiment_indicators' in email:
                            for tone, words in email['sentiment_indicators'].items():
                                if isinstance(words, list):
                                    email['sentiment_indicators'][tone] = [
                                        f"{word} (Confidence: High)" for word in words
                                    ]
                                    email['sentiment_indicators'][f"{tone}_analysis"] = [
                                        f"Strong {tone} sentiment detected",
                                        f"Impact on priority: Significant"
                                    ]
                        
                        # Detailed action items with business context
                        if email.get('action_items'):
                            for item in email['action_items']:
                                item['priority_reason'] = [
                                    "Based on comprehensive analysis",
                                    "Aligns with business objectives",
                                    "Time-sensitive nature"
                                ]
                                item['impact_assessment'] = [
                                    "Direct impact on project goals",
                                    "Affects multiple stakeholders",
                                    "Resource implications identified"
                                ]
                                item['suggested_delegates'] = [
                                    {"name": "Team Lead", "reason": "Technical expertise required"},
                                    {"name": "Project Manager", "reason": "Resource coordination needed"}
                                ]
                                
                        # Apply custom categories from user settings
                        if 'custom_categories' in email:
                            # Get custom categories from user settings
                            user_categories = settings.get('ai_features', {}).get('custom_categories', [])
                            if user_categories:
                                # Create a mapping of category names to their configurations
                                category_configs = {cat['name']: cat for cat in user_categories}
                                
                                # Update or filter custom categories based on user settings
                                updated_categories = {}
                                for cat_name, cat_value in email['custom_categories'].items():
                                    if cat_name in category_configs:
                                        # Ensure the value is in the allowed values for this category
                                        config = category_configs[cat_name]
                                        if cat_value in config['values']:
                                            updated_categories[cat_name] = cat_value
                                
                                email['custom_categories'] = updated_categories
                    else:
                        email['analysis_quality'] = 'standard'
                    
                    # Apply summary length with enhanced formatting
                    base_summary = email.get('summary', '')
                    if summary_length == 'short':
                        summary = base_summary.split('.')[0][:100]
                        if model_type == 'gpt-4o':
                            summary += "\n• Key Focus: " + ', '.join(email.get('key_phrases', [])[:1])
                        email['summary'] = summary + '...'
                    elif summary_length == 'medium':
                        sentences = base_summary.split('.')[:2]
                        summary = '. '.join(sentences)[:200]
                        if model_type == 'gpt-4o':
                            summary += "\n• Context: " + ', '.join(email.get('key_phrases', [])[:2])
                            summary += "\n• Impact: High relevance to ongoing projects"
                        email['summary'] = summary + '...'
                    else:  # long summary
                        if model_type == 'gpt-4o':
                            if context_length == '2000':
                                email['summary'] = f"{base_summary}\n\nDetailed Analysis:\n• Pattern: Part of ongoing communication thread\n• Business Impact: High\n• Stakeholder Relevance: Multiple teams affected"
                            else:
                                email['summary'] = f"{base_summary}\n\nKey Insights:\n• Significant communication\n• Requires attention\n• Follow-up recommended"
                    
                    # Apply priority threshold
                    threshold = str(settings.get('ai_features', {}).get('priority_threshold', '50')).lower()
                    priority = email.get('priority', 50)
                    
                    # Adjust priority level based on threshold setting
                    if threshold == '30':  # More permissive
                        if priority < 40:
                            email['priority_level'] = 'LOW'
                        elif priority < 65:
                            email['priority_level'] = 'MEDIUM'
                        else:
                            email['priority_level'] = 'HIGH'
                    elif threshold == '50':  # Balanced
                        if priority < 50:
                            email['priority_level'] = 'LOW'
                        elif priority < 70:
                            email['priority_level'] = 'MEDIUM'
                        else:
                            email['priority_level'] = 'HIGH'
                    else:  # high threshold - strict
                        if priority < 65:
                            email['priority_level'] = 'LOW'
                        elif priority < 75:
                            email['priority_level'] = 'MEDIUM'
                        else:
                            email['priority_level'] = 'HIGH'

            return jsonify({
                'status': 'success',
                'emails': demo_emails,
                'is_cached': True
            })
            
        # Original code for real users
        if not current_app.pipeline.cache:
            return jsonify({
                'status': 'error',
                'message': 'Cache not available'
            }), 404
            
        # Ensure user context
        if 'user' not in session or 'email' not in session['user']:
            return jsonify({
                'status': 'error',
                'message': 'No user found in session'
            }), 401
            
        user_email = session['user']['email']
        
        # Get user settings
        user = User.query.get(session['user']['id'])
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
            
        # Verify user email matches database
        if user.email != user_email:
            return jsonify({
                'status': 'error',
                'message': 'User email mismatch between session and database'
            }), 401
            
        # Get settings
        days_back = user.get_setting('email_preferences.days_to_analyze', 1)
        cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
            
        # Create command with user settings
        command = AnalysisCommand(
            days_back=days_back,
            cache_duration_days=cache_duration
        )
            
        # Get cached emails using command
        cached_emails = await current_app.pipeline.cache.get_recent(
            command.cache_duration_days,
            command.days_back,
            user_email
        )
        
        return jsonify({
            'status': 'success',
            'emails': [email.dict() for email in cached_emails],
            'is_cached': True
        })
    except Exception as e:
        logger.error(f"Failed to fetch cached emails: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@email_bp.route('/api/emails/analysis')
@login_required
@async_route
async def get_email_analysis():
    """Get analyzed emails in batches."""
    try:
        # Check if in demo mode
        if session.get('user', {}).get('is_demo', False):
            demo_emails = get_demo_emails()
            # Calculate actual stats from demo emails
            stats = {
                'total_analyzed': len(demo_emails),
                'categories': {},
                'sentiment_distribution': {}
            }
            
            # Calculate category distribution
            for email in demo_emails:
                category = email.get('category', 'Uncategorized')
                stats['categories'][category] = stats['categories'].get(category, 0) + 1
                
                # Calculate sentiment distribution based on sentiment_indicators
                sentiment = 'neutral'
                if email.get('sentiment_indicators'):
                    pos = len(email['sentiment_indicators'].get('positive', []))
                    neg = len(email['sentiment_indicators'].get('negative', []))
                    if pos > neg:
                        sentiment = 'positive'
                    elif neg > pos:
                        sentiment = 'negative'
                stats['sentiment_distribution'][sentiment] = stats['sentiment_distribution'].get(sentiment, 0) + 1
            
            return jsonify({
                'status': 'success',
                'emails': demo_emails,
                'stats': stats
            })
            
        # Original code for real users
        # Get user settings
        user = User.query.get(session['user']['id'])
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
            
        # Get settings
        days_back = user.get_setting('email_preferences.days_to_analyze', 1)
        cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
        
        command = AnalysisCommand(
            days_back=days_back,
            cache_duration_days=cache_duration,
            batch_size=20  # Process in small batches
        )
        result = await current_app.pipeline.get_analyzed_emails(command)
        
        # Force memory release after processing
        log_memory_cleanup(logger, "API Email Analysis Complete")
        
        return jsonify({
            'status': 'success',
            'emails': [email.dict() for email in result.emails],
            'stats': result.stats
        })
    except Exception as e:
        logger.error(f"Failed to fetch email analysis: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@email_bp.route('/stream')
def email_stream():
    def generate():
        for i in range(10):  # Simulating a stream
            yield f"data: Message {i}\n\n"
            time.sleep(1)  # Simulate processing delay

    response = Response(stream_with_context(generate()), content_type='text/event-stream')
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"  # Important for Nginx setups
    response.headers["Connection"] = "keep-alive"
    return response

# Deprecated routes below - will be removed in future versions
@email_bp.route('/emails')
@login_required
@async_route
async def get_emails():
    """Deprecated: Use /api/emails/analysis instead"""
    return redirect(url_for('email.get_email_analysis'))

@email_bp.route('/emails/refresh', methods=['POST'])
@login_required
@async_route
async def refresh_emails():
    """Refresh email cache"""
    try:
        # Get user settings
        user = User.query.get(session['user']['id'])
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
            
        # Get settings
        days_back = user.get_setting('email_preferences.days_to_analyze', 1)
        cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
        batch_size = int(request.args.get('batch_size', 100))
        
        # Create command with user settings
        command = AnalysisCommand(
            days_back=days_back,
            cache_duration_days=cache_duration,
            batch_size=batch_size
        )
        
        await current_app.pipeline.refresh_cache(days=command.days_back, batch_size=command.batch_size)
        
        return jsonify({
            'status': 'success',
            'message': f'Refreshed emails for the past {command.days_back} days'
        })
    except Exception as e:
        logger.error(f"Failed to refresh emails: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@email_bp.route('/api/user')
@login_required
def get_current_user():
    """Get current user ID from session."""
    try:
        if 'user' in session and 'email' in session['user']:
            return jsonify({
                'status': 'success',
                'user_id': session['user']['email']
            })
        return jsonify({
            'status': 'error',
            'message': 'No user found in session'
        }), 401
    except Exception as e:
        logger.error(f"Failed to get current user: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@email_bp.route('/api/emails/stream')
@login_required
def stream_email_analysis():
    """Stream analyzed emails as Server-Sent Events."""
    
    def generate():
        loop = None
        try:
            # Send initial connection message
            yield 'event: connected\ndata: {"status": "connected"}\n\n'
            
            # Check if in demo mode
            if session.get('user', {}).get('is_demo', False):
                logger.info("Starting demo email stream...")
                # Send initial status
                yield 'event: status\ndata: {"message": "Loading demo data..."}\n\n'
                time.sleep(1)  # Simulate loading
                
                # Get user settings
                user = User.query.get(session['user']['id'])
                if not user:
                    yield 'event: error\ndata: {"message": "User not found"}\n\n'
                    return
                
                # Get demo emails and user settings
                demo_emails = get_demo_emails()
                settings = user.get_all_settings()
                
                # Check if AI features are enabled
                ai_enabled = settings.get('ai_features', {}).get('enabled', True)
                
                # Apply settings to each email
                for email in demo_emails:
                    if not ai_enabled:
                        # If AI is disabled, remove AI-generated fields
                        email.pop('summary', None)
                        email.pop('priority', None)
                        email.pop('priority_level', None)
                        email.pop('category', None)
                        email.pop('custom_categories', None)
                        email.pop('entities', None)
                        email.pop('key_phrases', None)
                        email.pop('sentiment_indicators', None)
                        email.pop('needs_action', None)
                        email.pop('action_items', None)
                    else:
                        # Get model type and context length settings
                        model_type = str(settings.get('ai_features', {}).get('model_type', 'gpt-4o-mini')).lower()
                        context_length = str(settings.get('ai_features', {}).get('context_length', '1000'))
                        summary_length = str(settings.get('ai_features', {}).get('summary_length', 'medium')).lower()

                        # Apply pre-generated analysis based on model and context length
                        email = demo_analysis.apply_analysis(email, model_type, context_length)
                        
                        # Apply additional enhancements based on model type
                        if model_type == 'gpt-4o':
                            # Enhanced analysis for premium model
                            email['analysis_quality'] = 'premium'
                            
                            # Enhance entities with relationships and context
                            if 'entities' in email:
                                enhanced_entities = {}
                                original_entities = dict(email['entities'])
                                for key, values in original_entities.items():
                                    if isinstance(values, list):
                                        enhanced_entities[key] = list(values)
                                        enhanced_entities[f"{key}_context"] = [
                                            f"Impact: High relevance to {key.lower()}",
                                            f"Related Terms: {', '.join(values[:2])}"
                                        ]
                                email['entities'] = enhanced_entities
                            
                            # Add sophisticated key phrases with analysis
                            if 'key_phrases' in email:
                                original_phrases = email['key_phrases']
                                email['key_phrases'] = []
                                for phrase in original_phrases[:3]:
                                    email['key_phrases'].extend([
                                        phrase,
                                        f"Analysis: {phrase} indicates significant business impact",
                                        f"Context: Frequently appears in important communications"
                                    ])
                            
                            # Enhanced sentiment analysis
                            if 'sentiment_indicators' in email:
                                for tone, words in email['sentiment_indicators'].items():
                                    if isinstance(words, list):
                                        email['sentiment_indicators'][tone] = [
                                            f"{word} (Confidence: High)" for word in words
                                        ]
                                        email['sentiment_indicators'][f"{tone}_analysis"] = [
                                            f"Strong {tone} sentiment detected",
                                            f"Impact on priority: Significant"
                                        ]
                            
                            # Detailed action items with business context
                            if email.get('action_items'):
                                for item in email['action_items']:
                                    item['priority_reason'] = [
                                        "Based on comprehensive analysis",
                                        "Aligns with business objectives",
                                        "Time-sensitive nature"
                                    ]
                                    item['impact_assessment'] = [
                                        "Direct impact on project goals",
                                        "Affects multiple stakeholders",
                                        "Resource implications identified"
                                    ]
                                    item['suggested_delegates'] = [
                                        {"name": "Team Lead", "reason": "Technical expertise required"},
                                        {"name": "Project Manager", "reason": "Resource coordination needed"}
                                    ]
                                
                            # Apply custom categories from user settings
                            if 'custom_categories' in email:
                                # Get custom categories from user settings
                                user_categories = settings.get('ai_features', {}).get('custom_categories', [])
                                if user_categories:
                                    # Create a mapping of category names to their configurations
                                    category_configs = {cat['name']: cat for cat in user_categories}
                                    
                                    # Update or filter custom categories based on user settings
                                    updated_categories = {}
                                    for cat_name, cat_value in email['custom_categories'].items():
                                        if cat_name in category_configs:
                                            # Ensure the value is in the allowed values for this category
                                            config = category_configs[cat_name]
                                            if cat_value in config['values']:
                                                updated_categories[cat_name] = cat_value
                                
                                email['custom_categories'] = updated_categories
                        else:
                            email['analysis_quality'] = 'standard'
                        
                        # Apply summary length with enhanced formatting
                        base_summary = email.get('summary', '')
                        if summary_length == 'short':
                            summary = base_summary.split('.')[0][:100]
                            if model_type == 'gpt-4o':
                                summary += "\n• Key Focus: " + ', '.join(email.get('key_phrases', [])[:1])
                            email['summary'] = summary + '...'
                        elif summary_length == 'medium':
                            sentences = base_summary.split('.')[:2]
                            summary = '. '.join(sentences)[:200]
                            if model_type == 'gpt-4o':
                                summary += "\n• Context: " + ', '.join(email.get('key_phrases', [])[:2])
                                summary += "\n• Impact: High relevance to ongoing projects"
                            email['summary'] = summary + '...'
                        else:  # long summary
                            if model_type == 'gpt-4o':
                                if context_length == '2000':
                                    email['summary'] = f"{base_summary}\n\nDetailed Analysis:\n• Pattern: Part of ongoing communication thread\n• Business Impact: High\n• Stakeholder Relevance: Multiple teams affected"
                                else:
                                    email['summary'] = f"{base_summary}\n\nKey Insights:\n• Significant communication\n• Requires attention\n• Follow-up recommended"
                        
                        # Apply priority threshold
                        threshold = str(settings.get('ai_features', {}).get('priority_threshold', '50')).lower()
                        priority = email.get('priority', 50)
                        
                        # Adjust priority level based on threshold setting
                        if threshold == '30':  # More permissive
                            if priority < 40:
                                email['priority_level'] = 'LOW'
                            elif priority < 65:
                                email['priority_level'] = 'MEDIUM'
                            else:
                                email['priority_level'] = 'HIGH'
                        elif threshold == '50':  # Balanced
                            if priority < 50:
                                email['priority_level'] = 'LOW'
                            elif priority < 70:
                                email['priority_level'] = 'MEDIUM'
                            else:
                                email['priority_level'] = 'HIGH'
                        else:  # high threshold - strict
                            if priority < 65:
                                email['priority_level'] = 'LOW'
                            elif priority < 75:
                                email['priority_level'] = 'MEDIUM'
                            else:
                                email['priority_level'] = 'HIGH'

                logger.info(f"Retrieved {len(demo_emails)} demo emails for streaming")
                stats = {
                    'total_analyzed': len(demo_emails),
                    'categories': {},
                    'sentiment_distribution': {}
                }
                
                # Calculate actual stats from demo emails
                for email in demo_emails:
                    if ai_enabled:  # Only calculate AI stats if enabled
                        # Category distribution
                        category = email.get('category', 'Uncategorized')
                        stats['categories'][category] = stats['categories'].get(category, 0) + 1
                        
                        # Sentiment distribution
                        sentiment = 'neutral'
                        if email.get('sentiment_indicators'):
                            pos = len(email['sentiment_indicators'].get('positive', []))
                            neg = len(email['sentiment_indicators'].get('negative', []))
                            if pos > neg:
                                sentiment = 'positive'
                            elif neg > pos:
                                sentiment = 'negative'
                        stats['sentiment_distribution'][sentiment] = stats['sentiment_distribution'].get(sentiment, 0) + 1
                
                logger.info(f"Sending {len(demo_emails)} demo emails via SSE cached event")
                # Send cached data
                yield f'event: cached\ndata: {json.dumps({"emails": demo_emails})}\n\n'
                time.sleep(0.5)  # Simulate processing
                
                logger.info("Sending demo stats via SSE stats event")
                # Send stats
                yield f'event: stats\ndata: {json.dumps(stats)}\n\n'
                
                # Close connection
                yield 'event: close\ndata: {"message": "Demo data loaded"}\n\n'
                logger.info("Demo email stream completed")
                return
            
            # Original code for real users
            # Check user context
            if 'user' not in session:
                yield 'event: error\ndata: {"message": "No user found in session"}\n\n'
                return
                
            user_id = int(session['user'].get('id'))
            user_email = session['user'].get('email')
            if not user_email:
                yield 'event: error\ndata: {"message": "No user email found in session"}\n\n'
                return
            
            # Get user settings
            user = User.query.get(user_id)
            if not user:
                yield 'event: error\ndata: {"message": "User not found in database"}\n\n'
                return
            
            # Get user settings for email analysis
            cache_duration = user.get_setting('email_preferences.cache_duration_days', 7)
            days_back = user.get_setting('email_preferences.days_to_analyze', 1)
            
            command = AnalysisCommand(
                days_back=days_back,
                cache_duration_days=cache_duration,
                batch_size=5  # Process in smaller batches for streaming
            )
            
            # Create event loop for async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Get the email analysis generator
                analysis_gen = current_app.pipeline.get_analyzed_emails_stream(command)
                
                # Process all yields from the generator
                while True:
                    try:
                        result = loop.run_until_complete(analysis_gen.__anext__())
                        
                        # Handle different message types
                        if isinstance(result, dict):
                            msg_type = result.get('type')
                            msg_data = result.get('data', {})
                            
                            if msg_type == 'status':
                                yield f'event: status\ndata: {json.dumps(msg_data)}\n\n'
                            elif msg_type == 'cached':
                                yield f'event: cached\ndata: {json.dumps(msg_data)}\n\n'
                            elif msg_type == 'batch':
                                yield f'event: batch\ndata: {json.dumps(msg_data)}\n\n'
                            elif msg_type == 'initial_stats':
                                yield f'event: initial_stats\ndata: {json.dumps(msg_data)}\n\n'
                            elif msg_type == 'stats':
                                yield f'event: stats\ndata: {json.dumps(msg_data)}\n\n'
                                yield 'event: close\ndata: {"message": "Processing complete"}\n\n'
                                break
                            elif msg_type == 'error':
                                yield f'event: error\ndata: {json.dumps(msg_data)}\n\n'
                                break
                            
                    except StopAsyncIteration:
                        break
                    except Exception as batch_error:
                        current_app.logger.error(f"Batch processing error: {batch_error}")
                        yield f'event: error\ndata: {{"message": "Error processing batch: {str(batch_error)}"}}\n\n'
                        break
                
            except Exception as analysis_error:
                current_app.logger.error(f"Analysis error: {analysis_error}")
                yield f'event: error\ndata: {{"message": "Email analysis failed: {str(analysis_error)}"}}\n\n'
            
        except Exception as e:
            current_app.logger.error(f"Error in generator: {e}")
            yield f'event: error\ndata: {{"message": "Internal server error: {str(e)}"}}\n\n'
        finally:
            # Clean up resources - ensure all async clients are properly closed
            # This is crucial to prevent memory leaks in streaming responses
            try:
                if loop:
                    try:
                        # First ensure the pipeline connection is closed
                        if hasattr(current_app.pipeline.connection, 'disconnect'):
                            loop.run_until_complete(current_app.pipeline.connection.disconnect())
                        
                        # Ensure any OpenAI client connections are properly closed
                        # Get the OpenAI client and close it
                        if hasattr(current_app, 'get_openai_client'):
                            openai_client = current_app.get_openai_client()
                            if openai_client and hasattr(openai_client, 'close'):
                                loop.run_until_complete(openai_client.close())
                            elif openai_client and hasattr(openai_client.http_client, 'aclose'):
                                # If the client has an internal httpx client, close that too
                                loop.run_until_complete(openai_client.http_client.aclose()) 
                        
                        # Run a final garbage collection to clean up any remaining resources
                        gc.collect()
                    except Exception as cleanup_error:
                        current_app.logger.warning(f"Error during async resource cleanup: {cleanup_error}")
            except Exception as disconnect_error:
                current_app.logger.warning(f"Failed to disconnect clients: {disconnect_error}")
            
            # Force memory release before closing connection
            try:
                log_memory_cleanup(logger, "Stream Complete")
            except Exception as memory_error:
                logger.error(f"Error during memory cleanup: {memory_error}")
            
            # Now safe to close the loop since all connections have been properly closed
            if loop:
                # Run pending callbacks one more time to ensure everything is properly cleaned up
                try:
                    loop.run_until_complete(asyncio.sleep(0.1))
                except:
                    pass
                finally:
                    loop.close()
            
            # Send a final event to ensure the client knows we're done
            yield 'event: close\ndata: {"message": "Connection closed"}\n\n'

    response = Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Content-Type': 'text/event-stream; charset=utf-8'
        }
    )
    return response