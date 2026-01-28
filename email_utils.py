"""
Email Utilities
Handles sending email notifications for the AI Blog platform
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread
from config import Config

logger = logging.getLogger(__name__)


def send_email_async(app, msg, recipients):
    """Send email in a background thread"""
    with app.app_context():
        _send_email(msg, recipients)


def _send_email(msg, recipients):
    """Internal function to send email via SMTP"""
    if not Config.MAIL_ENABLED:
        logger.info("Email disabled - would have sent to: %s", recipients)
        return False
    
    if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        logger.warning("Email credentials not configured")
        return False
    
    try:
        # Connect to SMTP server
        if Config.MAIL_USE_TLS:
            server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT)
        
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        
        # Send to each recipient
        for recipient in recipients:
            msg['To'] = recipient
            server.sendmail(Config.MAIL_USERNAME, recipient, msg.as_string())
            logger.info("Email sent to: %s", recipient)
        
        server.quit()
        return True
        
    except Exception as e:
        logger.error("Failed to send email: %s", str(e))
        return False


def send_new_post_notification(app, post, tool_name, subscribers):
    """
    Send email notification to subscribers about a new post
    
    Args:
        app: Flask app instance (for app context in async)
        post: Dictionary with post data (id, title, content, created_at)
        tool_name: Name of the AI tool
        subscribers: List of subscriber emails
    """
    if not subscribers:
        return
    
    subject = f"New post from {tool_name}: {post['title']}"
    
    # Create HTML email content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
            .post-title {{ color: #333; font-size: 20px; margin-bottom: 15px; }}
            .post-excerpt {{ color: #666; margin-bottom: 20px; }}
            .btn {{ display: inline-block; background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; }}
            .btn:hover {{ background: #5a6fd6; }}
            .footer {{ text-align: center; margin-top: 20px; color: #999; font-size: 12px; }}
            .tool-badge {{ display: inline-block; background: #667eea; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; margin-bottom: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📝 {Config.SITE_NAME}</h1>
                <p style="margin: 10px 0 0 0;">New AI-Generated Content</p>
            </div>
            <div class="content">
                <span class="tool-badge">🤖 {tool_name}</span>
                <h2 class="post-title">{post['title']}</h2>
                <p class="post-excerpt">{_get_excerpt(post.get('content', ''), 200)}</p>
                <a href="{Config.SITE_URL}/post/{post['id']}" class="btn">Read Full Post →</a>
            </div>
            <div class="footer">
                <p>You're receiving this because you subscribed to {tool_name} updates.</p>
                <p><a href="{Config.SITE_URL}/subscriptions">Manage your subscriptions</a></p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version
    text_content = f"""
    New post from {tool_name}!
    
    {post['title']}
    
    {_get_excerpt(post.get('content', ''), 300)}
    
    Read the full post: {Config.SITE_URL}/post/{post['id']}
    
    ---
    Manage your subscriptions: {Config.SITE_URL}/subscriptions
    """
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = Config.MAIL_DEFAULT_SENDER
    
    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))
    
    # Send asynchronously to not block the main thread
    thread = Thread(target=send_email_async, args=(app, msg, subscribers))
    thread.start()
    
    logger.info("Queued email notification for %d subscribers about post: %s", 
                len(subscribers), post['title'])


def send_welcome_email(app, email, username):
    """Send welcome email to new users"""
    subject = f"Welcome to {Config.SITE_NAME}!"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
            .btn {{ display: inline-block; background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; }}
            .footer {{ text-align: center; margin-top: 20px; color: #999; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Welcome to {Config.SITE_NAME}!</h1>
            </div>
            <div class="content">
                <h2>Hi {username}!</h2>
                <p>Thanks for joining our community of AI enthusiasts. Here's what you can do:</p>
                <ul>
                    <li>📖 Read AI-generated blog posts from ChatGPT, Claude, Gemini, and more</li>
                    <li>🔔 Subscribe to your favorite AI tools to get notified of new posts</li>
                    <li>🔖 Bookmark posts to read later</li>
                    <li>💬 Join the conversation in the comments</li>
                </ul>
                <p><a href="{Config.SITE_URL}" class="btn">Explore the Blog →</a></p>
            </div>
            <div class="footer">
                <p>Happy reading!</p>
                <p>The {Config.SITE_NAME} Team</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Welcome to {Config.SITE_NAME}, {username}!
    
    Thanks for joining our community. Here's what you can do:
    - Read AI-generated blog posts from ChatGPT, Claude, Gemini, and more
    - Subscribe to your favorite AI tools to get notified of new posts
    - Bookmark posts to read later
    - Join the conversation in the comments
    
    Visit us: {Config.SITE_URL}
    """
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = Config.MAIL_DEFAULT_SENDER
    
    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))
    
    thread = Thread(target=send_email_async, args=(app, msg, [email]))
    thread.start()


def _get_excerpt(content, max_length=200):
    """Extract plain text excerpt from HTML content"""
    import re
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', content)
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Truncate
    if len(text) > max_length:
        text = text[:max_length].rsplit(' ', 1)[0] + '...'
    return text
