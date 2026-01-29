"""
Application Configuration
Secure settings management for the AI Blog platform
"""
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()


def parse_database_url(url):
    """Parse DATABASE_URL into individual components for psycopg2"""
    if not url:
        return None
    # Heroku uses postgres:// but psycopg2 needs postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    parsed = urlparse(url)
    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'database': parsed.path[1:],  # Remove leading /
        'user': parsed.username,
        'password': parsed.password
    }


class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
    
    # PostgreSQL Database settings
    # Support both Heroku's DATABASE_URL and individual env vars
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if DATABASE_URL:
        _db_config = parse_database_url(DATABASE_URL)
        DB_HOST = _db_config['host']
        DB_PORT = str(_db_config['port'])
        DB_NAME = _db_config['database']
        DB_USER = _db_config['user']
        DB_PASSWORD = _db_config['password']
    else:
        DB_HOST = os.environ.get('DB_HOST', 'localhost')
        DB_PORT = os.environ.get('DB_PORT', '5432')
        DB_NAME = os.environ.get('DB_NAME', 'ai_blog')
        DB_USER = os.environ.get('DB_USER', 'postgres')
        DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    
    # ============== Native API Keys ==============
    # OpenAI (ChatGPT)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
    # Anthropic (Claude)
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    
    # Google (Gemini)
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    
    # Together AI (Llama) - hosts open-source models
    TOGETHER_API_KEY = os.environ.get('TOGETHER_API_KEY')
    
    # xAI (Grok)
    XAI_API_KEY = os.environ.get('XAI_API_KEY')
    
    # Jasper AI
    JASPER_API_KEY = os.environ.get('JASPER_API_KEY')
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    
    # Rate limiting
    RATELIMIT_DEFAULT = "100 per hour"
    
    # Email settings (for notifications)
    # MAIL_PROVIDER options: 'gmail', 'outlook', 'sendgrid', 'mailgun', 'ses', 'custom'
    MAIL_PROVIDER = os.environ.get('MAIL_PROVIDER', 'custom')
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'AI Blog <noreply@aiblog.com>')
    MAIL_ENABLED = os.environ.get('MAIL_ENABLED', 'false').lower() == 'true'
    
    # SendGrid specific
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
    
    # Mailgun specific
    MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY', '')
    MAILGUN_DOMAIN = os.environ.get('MAILGUN_DOMAIN', '')
    
    # AWS SES specific
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    AWS_SES_REGION = os.environ.get('AWS_SES_REGION', 'us-east-1')
    
    # SMTP Provider Presets (used when MAIL_PROVIDER is set)
    SMTP_PROVIDERS = {
        'gmail': {
            'server': 'smtp.gmail.com',
            'port': 587,
            'use_tls': True,
            'use_ssl': False,
            'note': 'Requires App Password (not regular password). Enable 2FA first.'
        },
        'outlook': {
            'server': 'smtp.office365.com',
            'port': 587,
            'use_tls': True,
            'use_ssl': False,
            'note': 'Use your Microsoft 365 account credentials.'
        },
        'yahoo': {
            'server': 'smtp.mail.yahoo.com',
            'port': 587,
            'use_tls': True,
            'use_ssl': False,
            'note': 'Requires App Password. Enable "Allow less secure apps" or generate app password.'
        },
        'sendgrid': {
            'server': 'smtp.sendgrid.net',
            'port': 587,
            'use_tls': True,
            'use_ssl': False,
            'note': 'Use "apikey" as username and your API key as password.'
        },
        'mailgun': {
            'server': 'smtp.mailgun.org',
            'port': 587,
            'use_tls': True,
            'use_ssl': False,
            'note': 'Use postmaster@yourdomain as username.'
        },
        'ses': {
            'server': 'email-smtp.{region}.amazonaws.com',
            'port': 587,
            'use_tls': True,
            'use_ssl': False,
            'note': 'Use SMTP credentials from AWS SES console (not IAM credentials).'
        },
        'zoho': {
            'server': 'smtp.zoho.com',
            'port': 587,
            'use_tls': True,
            'use_ssl': False,
            'note': 'Use your Zoho email and password or app-specific password.'
        },
        'postmark': {
            'server': 'smtp.postmarkapp.com',
            'port': 587,
            'use_tls': True,
            'use_ssl': False,
            'note': 'Use your Server API Token as both username and password.'
        }
    }
    
    # In-app notification settings
    NOTIFICATIONS_ENABLED = os.environ.get('NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
    NOTIFICATIONS_MAX_AGE_DAYS = int(os.environ.get('NOTIFICATIONS_MAX_AGE_DAYS', 30))
    
    # Scheduler settings
    SCHEDULER_ENABLED = os.environ.get('SCHEDULER_ENABLED', 'true').lower() == 'true'
    
    # Site settings
    SITE_URL = os.environ.get('SITE_URL', 'http://localhost:5000')
    SITE_NAME = 'AI Blog'
    
    # AI Tools configuration with native providers
    AI_TOOLS = {
        'chatgpt': {
            'name': 'ChatGPT (GPT-4o)',
            'provider': 'openai',
            'model': 'gpt-4o',
            'prompt_style': 'quick, well-researched, and draft-focused for efficient content creation'
        },
        'claude': {
            'name': 'Claude Sonnet 4', 
            'provider': 'anthropic',
            'model': 'claude-sonnet-4-20250514',
            'prompt_style': 'nuanced, long-form, editorial, with careful attention to detail and editing'
        },
        'gemini': {
            'name': 'Gemini 2.0 Flash',
            'provider': 'google',
            'model': 'gemini-2.0-flash',
            'prompt_style': 'data-driven, research-oriented, with deep contextual understanding'
        },
        'llama': {
            'name': 'Llama 3.1 405B',
            'provider': 'together',
            'model': 'meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo',
            'prompt_style': 'technical, logic-driven, precise, with open-source transparency',
            'coming_soon': True
        },
        'grok': {
            'name': 'Grok 3',
            'provider': 'xai',
            'model': 'grok-3',
            'prompt_style': 'witty, irreverent, truth-seeking with a sense of humor'
        }
    }
