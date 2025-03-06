"""Demo email data module.

This module provides sample email content for the demo mode of the Beacon application.
It contains rich HTML email templates that showcase various email styles and content
types to demonstrate the application's analysis capabilities.

Functions:
    get_demo_email_bodies: Returns a dictionary of demo email bodies with rich HTML content.
"""

from typing import Dict, Any
from datetime import datetime, timedelta
import random


def get_demo_email_bodies() -> Dict[str, str]:
    """Return a dictionary of demo email bodies with rich HTML content.
    
    Provides sample email bodies for demonstration purposes. Each email has a unique
    format and content type to showcase different analysis capabilities of the system.
    
    Returns:
        Dict[str, str]: A dictionary mapping email IDs to their HTML content.
    """
    return {
        "demo1": """
            <div style="font-family: Arial, sans-serif; color: #2D3748; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667EEA 0%, #764BA2 100%); padding: 20px; border-radius: 8px; color: white; margin-bottom: 20px;">
                    <h2 style="margin: 0;">🎉 Welcome to Beacon's Demo Mode!</h2>
                </div>
                
                <p style="font-size: 16px; line-height: 1.6;">We're excited to show you how Beacon transforms your email experience. This demo contains a curated set of emails that showcase our AI-powered features.</p>
                
                <div style="background: #F7FAFC; border-left: 4px solid #4A5568; padding: 15px; margin: 20px 0;">
                    <h3 style="color: #2D3748; margin-top: 0;">Key Features to Explore:</h3>
                    <ul style="list-style-type: none; padding: 0;">
                        <li style="margin: 10px 0;">
                            <span style="color: #4C51BF;">🤖 AI-powered Analysis</span><br>
                            <span style="color: #718096;">Watch how our AI understands email context and intent</span>
                        </li>
                        <li style="margin: 10px 0;">
                            <span style="color: #4C51BF;">📊 Smart Prioritization</span><br>
                            <span style="color: #718096;">See emails automatically ranked by importance</span>
                        </li>
                        <li style="margin: 10px 0;">
                            <span style="color: #4C51BF;">✅ Action Item Detection</span><br>
                            <span style="color: #718096;">Never miss important tasks and deadlines</span>
                        </li>
                        <li style="margin: 10px 0;">
                            <span style="color: #4C51BF;">🎯 Sentiment Analysis</span><br>
                            <span style="color: #718096;">Understand the tone and urgency of messages</span>
                        </li>
                    </ul>
                </div>
                
                <div style="background: #EBF8FF; padding: 15px; border-radius: 8px; margin-top: 20px;">
                    <p style="margin: 0; color: #2B6CB0;">
                        <strong>Pro Tip:</strong> Try using the filters above to sort emails by priority, category, or action items!
                    </p>
                </div>
                
                <p style="margin-top: 20px;">Ready to explore? Browse through the demo emails to see Beacon in action!</p>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #E2E8F0;">
                    <p style="color: #718096; font-size: 14px;">Best regards,<br>The Beacon Team</p>
                </div>
            </div>
        """,
        
        "demo2": """
            <div style="font-family: Arial, sans-serif; color: #2D3748; padding: 20px;">
                <div style="background: #F7FAFC; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                    <h2 style="color: #2D3748; margin-top: 0;">📊 Weekly Performance Summary</h2>
                    <p style="color: #4A5568;">Period: Feb 12 - Feb 18, 2024</p>
                </div>
                
                <div style="margin: 20px 0;">
                    <h3 style="color: #2D3748;">🎯 Key Achievements</h3>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0;">
                        <div style="background: #F0FFF4; padding: 15px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 24px; color: #2F855A;">↑ 15%</div>
                            <div style="color: #48BB78;">Revenue Growth</div>
                        </div>
                        <div style="background: #EBF8FF; padding: 15px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 24px; color: #2B6CB0;">98%</div>
                            <div style="color: #4299E1;">Client Satisfaction</div>
                        </div>
                        <div style="background: #F0F5FF; padding: 15px; border-radius: 8px; text-align: center;">
                            <div style="font-size: 24px; color: #4C51BF;">+12</div>
                            <div style="color: #667EEA;">New Clients</div>
                        </div>
                    </div>
                </div>
                
                <div style="margin: 30px 0;">
                    <h3 style="color: #2D3748;">📈 Project Updates</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="background: #F7FAFC;">
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #E2E8F0;">Project</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #E2E8F0;">Status</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #E2E8F0;">Progress</th>
                        </tr>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">Database Optimization</td>
                            <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">
                                <span style="background: #C6F6D5; color: #2F855A; padding: 4px 8px; border-radius: 4px;">Completed</span>
                            </td>
                            <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">100%</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">API Documentation</td>
                            <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">
                                <span style="background: #FEFCBF; color: #B7791F; padding: 4px 8px; border-radius: 4px;">In Progress</span>
                            </td>
                            <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">75%</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">Frontend Testing</td>
                            <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">
                                <span style="background: #FED7D7; color: #C53030; padding: 4px 8px; border-radius: 4px;">Blocked</span>
                            </td>
                            <td style="padding: 12px; border-bottom: 1px solid #E2E8F0;">45%</td>
                        </tr>
                    </table>
                </div>
                
                <div style="background: #FFF5F5; border-left: 4px solid #F56565; padding: 15px; margin: 20px 0;">
                    <h4 style="color: #C53030; margin-top: 0;">⚠️ Action Required</h4>
                    <ul style="color: #4A5568; margin: 10px 0;">
                        <li>Review and approve API documentation by EOD tomorrow</li>
                        <li>Schedule meeting with DevOps to unblock frontend testing</li>
                    </ul>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #E2E8F0;">
                    <p style="color: #718096;">
                        Next team sync: Thursday, 10:00 AM PST<br>
                        Please update your tasks in the project board before the meeting.
                    </p>
                    <p style="color: #718096; margin-top: 20px;">
                        Best regards,<br>
                        Project Management Team
                    </p>
                </div>
            </div>
        """,
        
        "demo3": """
            <div style="font-family: Arial, sans-serif; color: #2D3748; padding: 20px;">
                <div style="background: #EBF8FF; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <h2 style="color: #2B6CB0; margin-top: 0;">📝 Team Meeting Notes</h2>
                    <p style="color: #4A5568;">Date: February 19, 2024 | Duration: 45 minutes | Attendees: 8</p>
                </div>
                
                <div style="margin: 20px 0;">
                    <h3 style="color: #2D3748; border-bottom: 2px solid #E2E8F0; padding-bottom: 10px;">
                        🎯 Key Discussion Points
                    </h3>
                    
                    <div style="margin: 20px 0;">
                        <h4 style="color: #4A5568;">1. Project Milestones</h4>
                        <ul style="color: #4A5568; line-height: 1.6;">
                            <li>Backend service deployment successfully completed ahead of schedule</li>
                            <li>User authentication system upgraded with enhanced security features</li>
                            <li>New feature requests prioritized based on user feedback analysis</li>
                        </ul>
                    </div>
                    
                    <div style="margin: 20px 0;">
                        <h4 style="color: #4A5568;">2. Technical Updates</h4>
                        <div style="background: #F7FAFC; padding: 15px; border-radius: 8px;">
                            <ul style="color: #4A5568; line-height: 1.6;">
                                <li>Database performance improved by 40% after optimization</li>
                                <li>API response time reduced to under 100ms</li>
                                <li>Mobile app crash rate decreased to 0.1%</li>
                            </ul>
                        </div>
                    </div>
                    
                    <div style="margin: 20px 0;">
                        <h4 style="color: #4A5568;">3. Upcoming Features</h4>
                        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                            <div style="background: #F0FFF4; padding: 15px; border-radius: 8px;">
                                <h5 style="color: #2F855A; margin-top: 0;">Analytics Dashboard</h5>
                                <p style="color: #4A5568; margin: 0;">Real-time metrics and customizable reports</p>
                            </div>
                            <div style="background: #F0F5FF; padding: 15px; border-radius: 8px;">
                                <h5 style="color: #4C51BF; margin-top: 0;">Integration Hub</h5>
                                <p style="color: #4A5568; margin: 0;">Connect with popular third-party services</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div style="background: #FFFAF0; border: 1px solid #F6AD55; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h4 style="color: #C05621; margin-top: 0;">⚡ Action Items</h4>
                    <ul style="color: #4A5568;">
                        <li>Begin development of analytics dashboard (Team: Frontend)</li>
                        <li>Schedule security audit for next week (Team: DevOps)</li>
                        <li>Prepare user testing plan for new features (Team: QA)</li>
                        <li>Update project documentation with recent changes (Team: All)</li>
                    </ul>
                </div>
                
                <div style="background: #F0FFF4; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h4 style="color: #2F855A; margin-top: 0;">🎉 Team Achievements</h4>
                    <ul style="color: #4A5568;">
                        <li>Sarah completed the AWS certification</li>
                        <li>Mobile team achieved 99.9% test coverage</li>
                        <li>Backend team's optimization efforts recognized by leadership</li>
                    </ul>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #E2E8F0;">
                    <p style="color: #718096;">
                        Next Meeting: Tuesday, February 26 @ 10:00 AM PST<br>
                        Location: Rainbow Room + Zoom
                    </p>
                    <p style="color: #718096; margin-top: 20px; font-style: italic;">
                        "Great teams don't just happen - they're built with purpose, passion, and persistence."
                    </p>
                    <p style="color: #718096;">
                        Best regards,<br>
                        Team Lead
                    </p>
                </div>
            </div>
        """,
        
        "demo4": """
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
        
        "demo5": """
            <div>
                <p>Hi sweetie,</p>
                <p>I hope you're doing well! Dad and I were thinking of having a family dinner this Saturday at 6 PM. Your sister will be in town, and it would be wonderful if you could join us.</p>
                <p>I'm planning to make your favorite lasagna! Let me know if you can make it.</p>
                <p>Love,<br>Mom</p>
            </div>
        """,
        
        "demo6": """
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
        
        "demo7": """
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
        
        "demo8": """
            <div>
                <p>Hey creative minds! 🌟</p>
                <p>Let's get those creative juices flowing! I'm organizing a brainstorming session for our new brand identity project.</p>
                <p>Bring your wildest ideas - no idea is too crazy! We'll have snacks, music, and lots of colorful sticky notes.</p>
                <p>When: Tomorrow, 2 PM - 4 PM<br>Where: Rainbow Room<br>What to bring: Your imagination!</p>
                <p>Can't wait to see what we come up with together! 🎨✨</p>
                <p>Cheers,<br>Sarah</p>
            </div>
        """,
        
        "demo9": """
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
        
        "demo10": """
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
        
        "demo11": """
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
        
        "demo12": """
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
        
        "demo13": """
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
        
        "demo14": """
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
        
        "demo15": """
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
        """
    }


def generate_demo_metadata() -> Dict[str, Any]:
    """Generate metadata for demo emails.
    
    Creates sample metadata like dates, senders, subjects for demo emails.
    This is a helper function to provide realistic email attributes.
    
    Returns:
        Dict[str, Any]: A dictionary of demo email metadata.
    """
    now = datetime.utcnow()
    
    # Helper function to generate random past date within a range
    def random_past_date(min_days: int, max_days: int) -> datetime:
        """Generate a random date in the past within the specified range.
        
        Args:
            min_days: Minimum number of days in the past
            max_days: Maximum number of days in the past
            
        Returns:
            datetime: A random datetime between min_days and max_days ago
        """
        days_ago = random.randint(min_days, max_days)
        return now - timedelta(days=days_ago, 
                              hours=random.randint(0, 23),
                              minutes=random.randint(0, 59))
    
    # Demo email metadata (could be expanded as needed)
    return {
        "demo1": {
            "date": now - timedelta(hours=1),
            "sender": "demo-team@example.com",
            "recipient": "demo@example.com",
            "subject": "Welcome to Demo Mode",
            "is_unread": True
        },
        "demo2": {
            "date": now - timedelta(days=1),
            "sender": "reports@example.com",
            "recipient": "demo@example.com",
            "subject": "Your Weekly Summary",
            "is_unread": True
        },
        "demo3": {
            "date": now - timedelta(days=2),
            "sender": "team-lead@example.com",
            "recipient": "demo@example.com",
            "subject": "Team Meeting Notes",
            "is_unread": False
        },
        "demo4": {
            "date": now - timedelta(days=3),
            "sender": "marketing@example.com",
            "recipient": "demo@example.com",
            "subject": "🎉 Special Weekend Sale - 50% Off All Products!",
            "is_unread": True
        },
        "demo5": {
            "date": now - timedelta(days=4),
            "sender": "mom@example.com",
            "recipient": "demo@example.com",
            "subject": "Family Dinner This Weekend?",
            "is_unread": False
        },
        "demo6": {
            "date": now - timedelta(days=5),
            "sender": "security@example.com",
            "recipient": "demo@example.com",
            "subject": "Your Account Security Alert",
            "is_unread": True
        },
        "demo7": {
            "date": random_past_date(6, 7),
            "sender": "finance@example.com",
            "recipient": "demo@example.com",
            "subject": "Quarterly Financial Report - Q3 2024",
            "is_unread": False
        },
        "demo8": {
            "date": random_past_date(7, 8),
            "sender": "creative-lead@example.com",
            "recipient": "demo@example.com",
            "subject": "🎨 Design Team Brainstorming Session",
            "is_unread": True
        },
        "demo9": {
            "date": random_past_date(8, 9),
            "sender": "bookclub@example.com",
            "recipient": "demo@example.com",
            "subject": "📚 Book Club Discussion: 'The Innovation Mindset'",
            "is_unread": False
        },
        "demo10": {
            "date": random_past_date(9, 10),
            "sender": "it-support@example.com",
            "recipient": "demo@example.com",
            "subject": "🚨 System Maintenance Notice",
            "is_unread": True
        },
        "demo11": {
            "date": random_past_date(10, 11),
            "sender": "green-team@example.com",
            "recipient": "demo@example.com",
            "subject": "🌱 Eco-Initiative: Office Plant Program Launch",
            "is_unread": False
        },
        "demo12": {
            "date": random_past_date(11, 12),
            "sender": "project-lead@example.com",
            "recipient": "demo@example.com",
            "subject": "Re: Project Timeline Discussion",
            "is_unread": True
        },
        "demo13": {
            "date": random_past_date(12, 13),
            "sender": "community@tech-meetup.example.com",
            "recipient": "demo@example.com",
            "subject": "🎉 Weekend Tech Meetup Highlights",
            "is_unread": False
        },
        "demo14": {
            "date": random_past_date(13, 14),
            "sender": "analytics@example.com",
            "recipient": "demo@example.com",
            "subject": "📊 Weekly Analytics Report",
            "is_unread": True
        },
        "demo15": {
            "date": random_past_date(14, 15),
            "sender": "goals-tracker@example.com",
            "recipient": "demo@example.com",
            "subject": "🎯 Personal Goal Check-in",
            "is_unread": False
        }
    } 