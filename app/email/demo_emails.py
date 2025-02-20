"""Demo email content with rich HTML bodies."""

def get_demo_email_bodies():
    """Return a dictionary of demo email bodies with rich HTML content."""
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
        """
        # Add more email bodies as needed...
    } 