"""
Email service for sending daily opportunity digests.
"""

import os
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template
from loguru import logger

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Content
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False
    logger.warning("SendGrid not available")

from src.config import settings
from src.models.opportunity import OpportunityInDB, EmailDigest, OpportunityCategory
from src.database.mongodb import db_manager


class EmailService:
    """Service for sending opportunity digest emails."""
    
    def __init__(self):
        self.sendgrid_client = None
        self.template_env = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize email clients and template environment."""
        # Initialize SendGrid
        if SENDGRID_AVAILABLE and settings.sendgrid_api_key:
            try:
                self.sendgrid_client = SendGridAPIClient(api_key=settings.sendgrid_api_key)
                logger.info("SendGrid client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize SendGrid: {e}")
        
        # Initialize Jinja2 template environment
        try:
            template_dir = Path(__file__).parent.parent / "templates"
            template_dir.mkdir(exist_ok=True)
            self.template_env = Environment(
                loader=FileSystemLoader(template_dir),
                autoescape=True
            )
            logger.info("Template environment initialized")
        except Exception as e:
            logger.error(f"Failed to initialize template environment: {e}")
    
    async def generate_daily_digest(
        self, 
        opportunities_by_category: Dict[str, List[OpportunityInDB]],
        user_email: str
    ) -> EmailDigest:
        """Generate daily email digest from opportunities."""
        try:
            # Calculate total count
            total_count = sum(len(opps) for opps in opportunities_by_category.values())
            
            # Create digest object
            digest = EmailDigest(
                user_email=user_email,
                opportunities_by_category=opportunities_by_category,
                total_count=total_count
            )
            
            logger.info(f"Generated digest for {user_email}: {total_count} opportunities")
            return digest
            
        except Exception as e:
            logger.error(f"Error generating digest: {e}")
            raise
    
    def render_email_html(self, digest: EmailDigest) -> str:
        """Render HTML email content from digest."""
        try:
            # Try to load custom template first
            try:
                template = self.template_env.get_template('daily_digest.html')
            except:
                # Use default template if custom not found
                template = Template(self._get_default_template())
            
            # Render template
            html_content = template.render(
                digest=digest,
                current_date=datetime.now().strftime("%A, %B %d, %Y"),
                categories=OpportunityCategory
            )
            
            return html_content
            
        except Exception as e:
            logger.error(f"Error rendering email template: {e}")
            return self._get_fallback_html(digest)
    
    def _get_default_template(self) -> str:
        """Default HTML email template."""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Daily Opportunities - {{ current_date }}</title>
    <style>
        body {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 20px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
            font-size: 28px;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
        }
        .summary {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .category-section {
            background: white;
            margin-bottom: 25px;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .category-header {
            background: #f8f9fa;
            padding: 15px 20px;
            border-bottom: 2px solid #e9ecef;
        }
        .category-title {
            margin: 0;
            color: #495057;
            font-size: 18px;
            text-transform: capitalize;
        }
        .opportunity {
            padding: 20px;
            border-bottom: 1px solid #e9ecef;
        }
        .opportunity:last-child {
            border-bottom: none;
        }
        .opp-title {
            font-size: 16px;
            font-weight: 600;
            color: #2c3e50;
            margin: 0 0 8px 0;
        }
        .opp-title a {
            color: #3498db;
            text-decoration: none;
        }
        .opp-title a:hover {
            text-decoration: underline;
        }
        .opp-meta {
            font-size: 12px;
            color: #6c757d;
            margin-bottom: 10px;
        }
        .opp-description {
            color: #495057;
            line-height: 1.5;
        }
        .score-badge {
            display: inline-block;
            background: #28a745;
            color: white;
            padding: 2px 6px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }
        .deadline {
            color: #dc3545;
            font-weight: 500;
        }
        .footer {
            text-align: center;
            padding: 20px;
            color: #6c757d;
            font-size: 14px;
        }
        .no-opportunities {
            text-align: center;
            color: #6c757d;
            padding: 40px 20px;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Your Daily Opportunities</h1>
        <p>{{ current_date }}</p>
    </div>
    
    <div class="summary">
        <h2>📊 Today's Summary</h2>
        <p><strong>{{ digest.total_count }}</strong> new opportunities discovered</p>
        {% if digest.total_count > 0 %}
            <p>Opportunities by category:</p>
            <ul>
                {% for category, opportunities in digest.opportunities_by_category.items() %}
                    {% if opportunities %}
                    <li><strong>{{ category.title() }}:</strong> {{ opportunities|length }} opportunities</li>
                    {% endif %}
                {% endfor %}
            </ul>
        {% endif %}
    </div>
    
    {% if digest.total_count > 0 %}
        {% for category, opportunities in digest.opportunities_by_category.items() %}
            {% if opportunities %}
            <div class="category-section">
                <div class="category-header">
                    <h3 class="category-title">{{ category.replace('_', ' ').title() }} ({{ opportunities|length }})</h3>
                </div>
                
                {% for opp in opportunities %}
                <div class="opportunity">
                    <h4 class="opp-title">
                        <a href="{{ opp.link }}" target="_blank">{{ opp.title }}</a>
                    </h4>
                    
                    <div class="opp-meta">
                        📍 {{ opp.source }}
                        {% if opp.score %}
                            <span class="score-badge">{{ "%.0f" | format(opp.score * 100) }}% match</span>
                        {% endif %}
                        {% if opp.deadline %}
                            | <span class="deadline">⏰ Deadline: {{ opp.deadline.strftime('%B %d, %Y') }}</span>
                        {% endif %}
                        {% if opp.posted_at %}
                            | 📅 Posted: {{ opp.posted_at.strftime('%m/%d/%Y') }}
                        {% endif %}
                    </div>
                    
                    <div class="opp-description">
                        {{ opp.description[:300] }}{% if opp.description|length > 300 %}...{% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        {% endfor %}
    {% else %}
        <div class="no-opportunities">
            <h3>No new opportunities today</h3>
            <p>We didn't find any new opportunities matching your interests in the last 24 hours.</p>
            <p>Don't worry, we'll keep looking! 🔍</p>
        </div>
    {% endif %}
    
    <div class="footer">
        <p>This digest was generated by Opportunist AI</p>
        <p>You received this because you subscribed to daily opportunity updates.</p>
    </div>
</body>
</html>
        """
    
    def _get_fallback_html(self, digest: EmailDigest) -> str:
        """Simple fallback HTML if template rendering fails."""
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1>Your Daily Opportunities - {datetime.now().strftime('%B %d, %Y')}</h1>
            <p><strong>{digest.total_count}</strong> new opportunities found today.</p>
        """
        
        for category, opportunities in digest.opportunities_by_category.items():
            if opportunities:
                html += f"<h2>{category.replace('_', ' ').title()} ({len(opportunities)})</h2>"
                for opp in opportunities[:5]:  # Limit for fallback
                    html += f"""
                    <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0;">
                        <h3><a href="{opp.link}">{opp.title}</a></h3>
                        <p><strong>Source:</strong> {opp.source}</p>
                        <p>{opp.description[:200]}...</p>
                    </div>
                    """
        
        html += "</body></html>"
        return html
    
    async def send_email(
        self, 
        digest: EmailDigest,
        subject: str = None
    ) -> bool:
        """Send the email digest."""
        if not self.sendgrid_client:
            logger.error("SendGrid client not available")
            return False
        
        try:
            # Generate subject if not provided
            if not subject:
                subject = f"Your Daily Opportunities - {datetime.now().strftime('%B %d, %Y')} ({digest.total_count} new)"
            
            # Render HTML content
            html_content = self.render_email_html(digest)
            
            # Create email
            message = Mail(
                from_email=settings.sendgrid_from_email,
                to_emails=digest.user_email,
                subject=subject,
                html_content=html_content
            )
            
            # Send email
            response = self.sendgrid_client.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully to {digest.user_email}")
                
                # Update digest status
                digest.sent_at = datetime.utcnow()
                digest.delivery_status = "sent"
                
                return True
            else:
                logger.error(f"Failed to send email. Status: {response.status_code}")
                digest.delivery_status = "failed"
                return False
                
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            digest.delivery_status = "failed"
            return False
    
    async def send_daily_digests(self) -> Dict[str, Any]:
        """Send daily digests to all active users."""
        try:
            # Get active users
            users = await db_manager.get_active_users()
            
            if not users:
                logger.info("No active users found")
                return {"sent": 0, "failed": 0, "total_users": 0}
            
            stats = {"sent": 0, "failed": 0, "total_users": len(users)}
            
            for user in users:
                try:
                    # Get opportunities for this user
                    opportunities_by_category = await self._get_user_opportunities(user)
                    
                    # Generate digest
                    digest = await self.generate_daily_digest(
                        opportunities_by_category,
                        user.email
                    )
                    
                    # Send email
                    success = await self.send_email(digest)
                    
                    if success:
                        stats["sent"] += 1
                        # Update user's last email sent timestamp
                        # This would be implemented in the database layer
                    else:
                        stats["failed"] += 1
                        
                except Exception as e:
                    logger.error(f"Error processing digest for {user.email}: {e}")
                    stats["failed"] += 1
            
            logger.info(f"Daily digest summary: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error sending daily digests: {e}")
            return {"sent": 0, "failed": 0, "error": str(e)}
    
    async def _get_user_opportunities(self, user) -> Dict[str, List[OpportunityInDB]]:
        """Get opportunities for a specific user based on their preferences."""
        opportunities_by_category = {}
        
        # Get category limits from user preferences
        category_limits = user.category_limits
        
        for category_str, limit in category_limits.items():
            try:
                category = OpportunityCategory(category_str)
                opportunities = await db_manager.get_opportunities_by_category_and_score(
                    category=category,
                    min_score=settings.relevance_threshold,
                    limit=limit,
                    hours_back=24
                )
                
                if opportunities:
                    opportunities_by_category[category_str] = opportunities
                    
            except Exception as e:
                logger.error(f"Error fetching {category_str} opportunities: {e}")
        
        return opportunities_by_category


# Global email service instance
email_service = EmailService()


async def send_test_email(to_email: str) -> bool:
    """Send a test email to verify configuration."""
    test_opportunities = {
        "job": [
            OpportunityInDB(
                title="Test Software Engineer Position",
                description="This is a test opportunity to verify email functionality.",
                category=OpportunityCategory.JOB,
                link="https://example.com/job",
                source="test.com",
                score=0.85
            )
        ]
    }
    
    digest = EmailDigest(
        user_email=to_email,
        opportunities_by_category=test_opportunities,
        total_count=1
    )
    
    return await email_service.send_email(digest, "Test Email - Opportunist")
