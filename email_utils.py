"""
Email Utilities
Handles sending email notifications for the AI Blog platform

Supports multiple SMTP providers:
- Gmail (requires App Password)
- Outlook/Office365
- SendGrid
- Mailgun (SMTP and HTTP API)
- AWS SES
- Yahoo
- Zoho
- Postmark
- Custom SMTP

Set MAIL_PROVIDER env var to use presets, or configure MAIL_SERVER/MAIL_PORT manually.
For Mailgun HTTP API (recommended), set MAILGUN_USE_API=true.
"""
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread
from config import Config

logger = logging.getLogger(__name__)


# ============== Mailgun HTTP API Functions ==============

def send_email_via_mailgun_api(to_emails, subject, html_content, text_content=None):
    """
    Send email using Mailgun's HTTP API (recommended over SMTP).
    
    This method is more reliable and provides better deliverability than SMTP.
    Supports both US and EU Mailgun regions.
    
    Args:
        to_emails: List of recipient email addresses
        subject: Email subject line
        html_content: HTML version of the email
        text_content: Plain text version (optional, will be generated from HTML if not provided)
        
    Returns:
        dict: Result with success status and message/error
    """
    if not Config.MAILGUN_API_KEY or not Config.MAILGUN_DOMAIN:
        logger.warning("Mailgun API credentials not configured")
        return {'success': False, 'error': 'Mailgun API credentials not configured'}
    
    if not to_emails:
        return {'success': False, 'error': 'No recipients specified'}
    
    # Determine API endpoint (US or EU region)
    api_base = getattr(Config, 'MAILGUN_API_BASE', 'https://api.mailgun.net/v3')
    api_url = f"{api_base}/{Config.MAILGUN_DOMAIN}/messages"
    
    # Generate plain text from HTML if not provided
    if not text_content:
        text_content = _strip_html(html_content)
    
    # Prepare email data
    data = {
        'from': Config.MAIL_DEFAULT_SENDER,
        'to': to_emails if isinstance(to_emails, list) else [to_emails],
        'subject': subject,
        'text': text_content,
        'html': html_content,
    }
    
    # Add tracking options if configured
    if getattr(Config, 'MAILGUN_TRACKING', True):
        data['o:tracking'] = 'yes'
        data['o:tracking-clicks'] = 'yes'
        data['o:tracking-opens'] = 'yes'
    
    try:
        response = requests.post(
            api_url,
            auth=('api', Config.MAILGUN_API_KEY),
            data=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Mailgun API: Email sent successfully. Message ID: {result.get('id', 'N/A')}")
            return {'success': True, 'message_id': result.get('id')}
        else:
            error_msg = f"Mailgun API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
            
    except requests.exceptions.Timeout:
        logger.error("Mailgun API request timed out")
        return {'success': False, 'error': 'Request timed out'}
    except requests.exceptions.RequestException as e:
        logger.error(f"Mailgun API request failed: {e}")
        return {'success': False, 'error': str(e)}


def send_email_via_mailgun_api_async(app, to_emails, subject, html_content, text_content=None):
    """Send email via Mailgun API in a background thread"""
    thread = Thread(
        target=_send_mailgun_api_async_worker, 
        args=(app, to_emails, subject, html_content, text_content)
    )
    thread.start()
    return thread


def _send_mailgun_api_async_worker(app, to_emails, subject, html_content, text_content):
    """Worker function for async Mailgun API email sending"""
    with app.app_context():
        result = send_email_via_mailgun_api(to_emails, subject, html_content, text_content)
        if result['success']:
            logger.info(f"Async email sent to {len(to_emails) if isinstance(to_emails, list) else 1} recipients")
        else:
            logger.error(f"Async email failed: {result.get('error')}")


def send_batch_emails_via_mailgun(recipients_data, subject_template, html_template, text_template=None):
    """
    Send batch personalized emails using Mailgun's batch sending feature.
    
    Mailgun supports up to 1000 recipients per API call with recipient variables.
    
    Args:
        recipients_data: List of dicts with 'email' and any personalization vars
                        e.g., [{'email': 'user@example.com', 'name': 'John', 'tool_name': 'ChatGPT'}]
        subject_template: Subject with %recipient.var% placeholders
        html_template: HTML content with %recipient.var% placeholders
        text_template: Plain text content (optional)
        
    Returns:
        dict: Result with success status
    """
    if not Config.MAILGUN_API_KEY or not Config.MAILGUN_DOMAIN:
        return {'success': False, 'error': 'Mailgun API credentials not configured'}
    
    if not recipients_data:
        return {'success': False, 'error': 'No recipients specified'}
    
    api_base = getattr(Config, 'MAILGUN_API_BASE', 'https://api.mailgun.net/v3')
    api_url = f"{api_base}/{Config.MAILGUN_DOMAIN}/messages"
    
    # Build recipient list and variables
    to_list = [r['email'] for r in recipients_data]
    recipient_variables = {
        r['email']: {k: v for k, v in r.items() if k != 'email'}
        for r in recipients_data
    }
    
    import json
    
    data = {
        'from': Config.MAIL_DEFAULT_SENDER,
        'to': to_list,
        'subject': subject_template,
        'html': html_template,
        'recipient-variables': json.dumps(recipient_variables),
    }
    
    if text_template:
        data['text'] = text_template
    
    try:
        response = requests.post(
            api_url,
            auth=('api', Config.MAILGUN_API_KEY),
            data=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Mailgun batch email sent to {len(to_list)} recipients")
            return {'success': True, 'message_id': result.get('id')}
        else:
            logger.error(f"Mailgun batch send failed: {response.status_code} - {response.text}")
            return {'success': False, 'error': response.text}
            
    except Exception as e:
        logger.error(f"Mailgun batch send exception: {e}")
        return {'success': False, 'error': str(e)}


def _strip_html(html_content):
    """Convert HTML to plain text by stripping tags"""
    import re
    # Remove style and script tags with content
    text = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Replace common block elements with newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Clean up whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = text.strip()
    return text


def test_mailgun_api_connection():
    """
    Test Mailgun API connection and configuration.
    
    Returns:
        dict: Result with success status and domain info
    """
    if not Config.MAILGUN_API_KEY or not Config.MAILGUN_DOMAIN:
        return {'success': False, 'message': 'Mailgun API credentials not configured'}
    
    api_base = getattr(Config, 'MAILGUN_API_BASE', 'https://api.mailgun.net/v3')
    api_url = f"{api_base}/domains/{Config.MAILGUN_DOMAIN}"
    
    try:
        response = requests.get(
            api_url,
            auth=('api', Config.MAILGUN_API_KEY),
            timeout=10
        )
        
        if response.status_code == 200:
            domain_info = response.json()
            return {
                'success': True,
                'message': f"Connected to Mailgun domain: {Config.MAILGUN_DOMAIN}",
                'domain': domain_info.get('domain', {})
            }
        elif response.status_code == 401:
            return {'success': False, 'message': 'Invalid Mailgun API key'}
        elif response.status_code == 404:
            return {'success': False, 'message': f'Domain not found: {Config.MAILGUN_DOMAIN}'}
        else:
            return {'success': False, 'message': f'Mailgun API error: {response.status_code}'}
            
    except Exception as e:
        return {'success': False, 'message': str(e)}


# ============== SMTP Settings Functions ==============

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
    
    safe_title = post['title'].replace('\r', '').replace('\n', ' ')
    subject = f"New post from {tool_name}: {safe_title}"
    
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


def send_premium_post_notification(app, post, tool_name, subscribers):
    """
    Send email notification to PREMIUM subscribers about a new post using Mailgun API.
    
    This is the premium-only email notification that uses Mailgun's HTTP API
    for reliable delivery. Only premium users who have subscribed to the AI tool
    will receive this notification.
    
    Args:
        app: Flask app instance (for app context in async)
        post: Dictionary with post data (id, title, content, created_at)
        tool_name: Name of the AI tool
        subscribers: List of premium subscriber emails
    """
    if not subscribers:
        logger.info("No premium subscribers to notify for post: %s", post.get('title'))
        return
    
    # Check if Mailgun API is configured (preferred for premium emails)
    use_mailgun_api = (
        Config.MAILGUN_API_KEY and 
        Config.MAILGUN_DOMAIN and 
        getattr(Config, 'MAILGUN_USE_API', True)
    )
    
    safe_title = post['title'].replace('\r', '').replace('\n', ' ')
    subject = f"🌟 New from {tool_name}: {safe_title}"
    
    # Premium email template with enhanced styling
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f4f4f4; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .header h1 {{ margin: 0; font-size: 24px; }}
            .premium-badge {{ display: inline-block; background: linear-gradient(135deg, #f5af19, #f12711); color: white; padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; text-transform: uppercase; margin-top: 10px; }}
            .content {{ background: #ffffff; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .tool-badge {{ display: inline-block; background: #667eea; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; margin-bottom: 15px; }}
            .post-title {{ color: #333; font-size: 22px; margin-bottom: 15px; font-weight: 600; }}
            .post-excerpt {{ color: #555; margin-bottom: 25px; font-size: 15px; line-height: 1.7; }}
            .btn {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px; }}
            .btn:hover {{ opacity: 0.9; }}
            .footer {{ text-align: center; margin-top: 25px; color: #888; font-size: 12px; padding: 20px; }}
            .footer a {{ color: #667eea; text-decoration: none; }}
            .divider {{ border-top: 1px solid #eee; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📝 {Config.SITE_NAME}</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">Fresh AI-Generated Content Just For You</p>
                <span class="premium-badge">⭐ Premium Member</span>
            </div>
            <div class="content">
                <span class="tool-badge">🤖 {tool_name}</span>
                <h2 class="post-title">{post['title']}</h2>
                <p class="post-excerpt">{_get_excerpt(post.get('content', ''), 250)}</p>
                <a href="{Config.SITE_URL}/post/{post['id']}" class="btn">Read Full Post →</a>
                <div class="divider"></div>
                <p style="color: #888; font-size: 13px;">
                    💎 As a premium member, you get instant notifications when your subscribed AI tools publish new content.
                </p>
            </div>
            <div class="footer">
                <p>You're receiving this premium notification because you subscribed to {tool_name}.</p>
                <p>
                    <a href="{Config.SITE_URL}/subscriptions">Manage Subscriptions</a> • 
                    <a href="{Config.SITE_URL}/account">Account Settings</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version
    text_content = f"""
    ⭐ PREMIUM NOTIFICATION
    
    New post from {tool_name}!
    
    {post['title']}
    
    {_get_excerpt(post.get('content', ''), 300)}
    
    Read the full post: {Config.SITE_URL}/post/{post['id']}
    
    ---
    As a premium member, you get instant notifications when your subscribed AI tools publish new content.
    
    Manage your subscriptions: {Config.SITE_URL}/subscriptions
    Account settings: {Config.SITE_URL}/account
    """
    
    if use_mailgun_api:
        # Use Mailgun HTTP API (recommended for reliability)
        send_email_via_mailgun_api_async(app, subscribers, subject, html_content, text_content)
        logger.info("Queued Mailgun API email for %d premium subscribers: %s", 
                    len(subscribers), post['title'])
    else:
        # Fallback to SMTP
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = Config.MAIL_DEFAULT_SENDER
        
        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))
        
        thread = Thread(target=send_email_async, args=(app, msg, subscribers))
        thread.start()
        
        logger.info("Queued SMTP email for %d premium subscribers: %s", 
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


def send_password_reset_email(app, email, username, reset_url):
    """
    Send password reset email to user

    Args:
        app: Flask app instance (for app context in async)
        email: User's email address
        username: User's username
        reset_url: Password reset URL with token
    """
    subject = f"Reset Your {Config.SITE_NAME} Password"

    # Check if Mailgun API is configured
    use_mailgun_api = (
        Config.MAILGUN_API_KEY and
        Config.MAILGUN_DOMAIN and
        getattr(Config, 'MAILGUN_USE_API', True)
    )

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
            .btn {{ display: inline-block; background: #667eea; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 20px; color: #999; font-size: 12px; }}
            .warning {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 15px 0; }}
            .code {{ background: #e9ecef; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset Request</h1>
            </div>
            <div class="content">
                <h2>Hi {username}!</h2>
                <p>We received a request to reset your password for your {Config.SITE_NAME} account.</p>
                <p>Click the button below to reset your password:</p>
                <p style="text-align: center;">
                    <a href="{reset_url}" class="btn">Reset Password</a>
                </p>
                <p>Or copy and paste this link into your browser:</p>
                <p class="code" style="word-break: break-all;">{reset_url}</p>
                <div class="warning">
                    <strong>⚠️ Security Notice:</strong>
                    <ul style="margin: 5px 0;">
                        <li>This link will expire in <strong>1 hour</strong></li>
                        <li>If you didn't request this reset, you can safely ignore this email</li>
                        <li>Your password won't change until you click the link and set a new one</li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>This is an automated security email from {Config.SITE_NAME}</p>
                <p>If you need help, contact us at {Config.MAIL_DEFAULT_SENDER}</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_content = f"""
    Password Reset Request

    Hi {username},

    We received a request to reset your password for your {Config.SITE_NAME} account.

    Click this link to reset your password:
    {reset_url}

    ⚠️ SECURITY NOTICE:
    - This link will expire in 1 hour
    - If you didn't request this reset, you can safely ignore this email
    - Your password won't change until you click the link and set a new one

    ---
    This is an automated security email from {Config.SITE_NAME}
    If you need help, contact us at {Config.MAIL_DEFAULT_SENDER}
    """

    if use_mailgun_api:
        # Use Mailgun HTTP API (recommended for reliability)
        send_email_via_mailgun_api_async(app, [email], subject, html_content, text_content)
        logger.info("Queued password reset email via Mailgun API for: %s", email)
    else:
        # Fallback to SMTP
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = Config.MAIL_DEFAULT_SENDER

        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))

        thread = Thread(target=send_email_async, args=(app, msg, [email]))
        thread.start()
        logger.info("Queued password reset email via SMTP for: %s", email)


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


def send_compare_challenge_email(app, matchup_data, recipients):
    """
    Send a compare challenge email for a featured matchup.

    Args:
        app: Flask app instance (for context)
        matchup_data: dict with keys: topic, matchup_url, vote_count, preview_a, preview_b, site_url
        recipients: list of email addresses
    """
    if not Config.MAIL_ENABLED:
        logger.info("Email disabled — skipping compare challenge send")
        return False

    safe_topic = matchup_data.get('topic', 'New Matchup').replace('\r', '').replace('\n', ' ')
    subject = f"AI Head-to-Head: {safe_topic} — Which AI nailed it?"

    # Read and populate template
    import os
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'emails', 'compare_challenge.html')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        logger.error(f"Compare challenge email template not found at {template_path}")
        return False

    # Replace template variables
    for key, value in matchup_data.items():
        html_content = html_content.replace('{{' + key + '}}', str(value))

    text_content = (
        f"AI Head-to-Head: {matchup_data.get('topic', 'New Matchup')}\n\n"
        f"Two AI tools wrote about the same topic. Read both and vote on which one nailed it.\n\n"
        f"Vote now: {matchup_data.get('matchup_url', '')}\n\n"
        f"{matchup_data.get('vote_count', 0)} people have voted so far.\n"
    )

    use_mailgun_api = (
        Config.MAILGUN_API_KEY and Config.MAILGUN_DOMAIN
        and getattr(Config, 'MAILGUN_USE_API', True)
    )

    if use_mailgun_api:
        send_email_via_mailgun_api_async(app, recipients, subject, html_content, text_content)
        return True
    else:
        logger.info("Compare challenge email: Mailgun API not configured, skipping.")
        return False