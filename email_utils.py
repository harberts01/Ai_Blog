"""
Email Utilities
Handles sending email notifications for the AI Blog platform

Supports multiple SMTP providers:
- Gmail (requires App Password)
- Outlook/Office365
- SendGrid
- Mailgun
- AWS SES
- Yahoo
- Zoho
- Postmark
- Custom SMTP

Set MAIL_PROVIDER env var to use presets, or configure MAIL_SERVER/MAIL_PORT manually.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread
from config import Config

logger = logging.getLogger(__name__)


def get_smtp_settings():
    """
    Get SMTP settings based on provider preset or custom configuration.
    
    Returns:
        dict: SMTP configuration settings
    """
    provider = Config.MAIL_PROVIDER.lower() if Config.MAIL_PROVIDER else 'custom'
    
    # If using a preset provider
    if provider in Config.SMTP_PROVIDERS:
        preset = Config.SMTP_PROVIDERS[provider]
        settings = {
            'server': preset['server'],
            'port': preset['port'],
            'use_tls': preset['use_tls'],
            'use_ssl': preset.get('use_ssl', False),
        }
        
        # Handle region substitution for AWS SES
        if provider == 'ses':
            region = Config.AWS_SES_REGION or 'us-east-1'
            settings['server'] = settings['server'].replace('{region}', region)
        
        # Allow env var overrides
        if Config.MAIL_SERVER:
            settings['server'] = Config.MAIL_SERVER
        if Config.MAIL_PORT:
            settings['port'] = Config.MAIL_PORT
            
        return settings
    
    # Custom configuration
    return {
        'server': Config.MAIL_SERVER or 'smtp.gmail.com',
        'port': Config.MAIL_PORT or 587,
        'use_tls': Config.MAIL_USE_TLS,
        'use_ssl': Config.MAIL_USE_SSL,
    }


def get_smtp_credentials():
    """
    Get SMTP credentials based on provider.
    Some providers have special username requirements.
    
    Returns:
        tuple: (username, password)
    """
    provider = Config.MAIL_PROVIDER.lower() if Config.MAIL_PROVIDER else 'custom'
    username = Config.MAIL_USERNAME
    password = Config.MAIL_PASSWORD
    
    # SendGrid uses 'apikey' as username
    if provider == 'sendgrid' and Config.SENDGRID_API_KEY:
        username = 'apikey'
        password = Config.SENDGRID_API_KEY
    
    # Mailgun uses API key as password
    elif provider == 'mailgun' and Config.MAILGUN_API_KEY:
        password = Config.MAILGUN_API_KEY
    
    return username, password


def send_email_async(app, msg, recipients):
    """Send email in a background thread"""
    with app.app_context():
        _send_email(msg, recipients)


def _send_email(msg, recipients):
    """Internal function to send email via SMTP"""
    if not Config.MAIL_ENABLED:
        logger.info("Email disabled - would have sent to: %s", recipients)
        return False
    
    username, password = get_smtp_credentials()
    
    if not username or not password:
        logger.warning("Email credentials not configured")
        return False
    
    settings = get_smtp_settings()
    
    try:
        # Connect to SMTP server
        if settings['use_ssl']:
            server = smtplib.SMTP_SSL(settings['server'], settings['port'])
        else:
            server = smtplib.SMTP(settings['server'], settings['port'])
            if settings['use_tls']:
                server.starttls()
        
        server.login(username, password)
        
        # Send to each recipient
        for recipient in recipients:
            msg_copy = MIMEMultipart('alternative')
            msg_copy['Subject'] = msg['Subject']
            msg_copy['From'] = msg['From']
            msg_copy['To'] = recipient
            
            # Copy attachments
            for part in msg.walk():
                if part.get_content_type() in ['text/plain', 'text/html']:
                    msg_copy.attach(MIMEText(part.get_payload(), part.get_content_subtype()))
            
            server.sendmail(username, recipient, msg_copy.as_string())
            logger.info("Email sent to: %s", recipient)
        
        server.quit()
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error("SMTP authentication failed. Check credentials. Provider: %s", Config.MAIL_PROVIDER)
        return False
    except smtplib.SMTPException as e:
        logger.error("SMTP error: %s", str(e))
        return False
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


def test_email_connection():
    """
    Test SMTP connection without sending an email.
    Useful for verifying configuration.
    
    Returns:
        dict: Result with success status and message
    """
    if not Config.MAIL_ENABLED:
        return {'success': False, 'message': 'Email is disabled (MAIL_ENABLED=false)'}
    
    username, password = get_smtp_credentials()
    
    if not username or not password:
        return {'success': False, 'message': 'Email credentials not configured'}
    
    settings = get_smtp_settings()
    provider = Config.MAIL_PROVIDER or 'custom'
    
    try:
        if settings['use_ssl']:
            server = smtplib.SMTP_SSL(settings['server'], settings['port'], timeout=10)
        else:
            server = smtplib.SMTP(settings['server'], settings['port'], timeout=10)
            if settings['use_tls']:
                server.starttls()
        
        server.login(username, password)
        server.quit()
        
        return {
            'success': True, 
            'message': f'Successfully connected to {settings["server"]}:{settings["port"]} (provider: {provider})'
        }
        
    except smtplib.SMTPAuthenticationError:
        return {
            'success': False, 
            'message': f'Authentication failed for provider: {provider}. Check username/password.'
        }
    except smtplib.SMTPConnectError:
        return {
            'success': False, 
            'message': f'Could not connect to {settings["server"]}:{settings["port"]}'
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}


def get_provider_info():
    """
    Get information about configured email provider.
    
    Returns:
        dict: Provider configuration info (safe for display)
    """
    provider = Config.MAIL_PROVIDER or 'custom'
    settings = get_smtp_settings()
    username, _ = get_smtp_credentials()
    
    return {
        'provider': provider,
        'server': settings['server'],
        'port': settings['port'],
        'use_tls': settings['use_tls'],
        'use_ssl': settings.get('use_ssl', False),
        'username': username[:3] + '***' if username else None,
        'enabled': Config.MAIL_ENABLED,
        'note': Config.SMTP_PROVIDERS.get(provider, {}).get('note', '')
    }