"""
Application Configuration
Secure settings management for the AI Blog platform
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
    
    # PostgreSQL Database settings
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
    
    # Mistral AI
    MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY')
    
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
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')  # App password for Gmail
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'AI Blog <noreply@aiblog.com>')
    MAIL_ENABLED = os.environ.get('MAIL_ENABLED', 'false').lower() == 'true'
    
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
            'name': 'Claude 3.5 Sonnet', 
            'provider': 'anthropic',
            'model': 'claude-3-5-sonnet-20241022',
            'prompt_style': 'nuanced, long-form, editorial, with careful attention to detail and editing'
        },
        'gemini': {
            'name': 'Gemini 1.5 Pro',
            'provider': 'google',
            'model': 'gemini-1.5-pro',
            'prompt_style': 'data-driven, research-oriented, with deep contextual understanding'
        },
        'llama': {
            'name': 'Llama 3.1 405B',
            'provider': 'together',
            'model': 'meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo',
            'prompt_style': 'technical, logic-driven, precise, with open-source transparency'
        },
        'mistral': {
            'name': 'Mistral Large 2',
            'provider': 'mistral',
            'model': 'mistral-large-latest',
            'prompt_style': 'fast, efficient, multilingual, with European flair'
        },
        'jasper': {
            'name': 'Jasper',
            'provider': 'jasper',
            'model': 'jasper',
            'prompt_style': 'marketing-focused, brand-voice aware, persuasive and engaging'
        }
    }
