"""
Utility Functions Module
Common helper functions used across the application
"""
import re
import html
import bleach


# Allowed HTML tags and attributes for AI-generated blog content
ALLOWED_TAGS = [
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'strong', 'em', 'b', 'i',
    'a', 'code', 'pre', 'blockquote', 'br', 'hr',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'span', 'div', 'sub', 'sup',
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'th': ['colspan', 'rowspan'],
    'td': ['colspan', 'rowspan'],
}


def sanitize_html(content):
    """
    Sanitize HTML content to prevent XSS while preserving safe formatting.

    Strips dangerous tags (script, iframe, object, embed, form) and
    event handler attributes (onclick, onerror, etc.) while keeping
    standard blog formatting tags.

    Args:
        content: Raw HTML content string

    Returns:
        Sanitized HTML string safe for rendering with |safe filter
    """
    if not content:
        return content
    return bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )


def sanitize_input(text, max_length=None):
    """
    Sanitize user input to prevent XSS attacks.

    Args:
        text: Raw user input string
        max_length: Optional maximum length to enforce

    Returns:
        Escaped and stripped string, or None if input is None
    """
    if text is None:
        return None
    cleaned = html.escape(str(text).strip())
    if max_length and len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned


def validate_email(email):
    """
    Validate email format using regex pattern.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if email format is valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def calculate_reading_time(content):
    """
    Calculate estimated reading time for content.
    
    Args:
        content: HTML or plain text content
        
    Returns:
        Formatted string like "5 min read"
    """
    if not content:
        return "1 min read"
    # Strip HTML tags for accurate word count
    text = re.sub(r'<[^>]+>', '', content)
    word_count = len(text.split())
    # Average reading speed: 200 words per minute
    minutes = max(1, round(word_count / 200))
    return f"{minutes} min read"


def count_words(content):
    """
    Count words in content after stripping HTML.
    
    Args:
        content: HTML or plain text content
        
    Returns:
        Integer word count
    """
    if not content:
        return 0
    text = re.sub(r'<[^>]+>', '', content)
    return len(text.split())


def truncate_text(text, length=120, suffix='...'):
    """
    Truncate text to a specified length.
    
    Args:
        text: Text to truncate
        length: Maximum length
        suffix: String to append if truncated
        
    Returns:
        Truncated string with suffix if needed
    """
    if not text or len(text) <= length:
        return text
    return text[:length].rsplit(' ', 1)[0] + suffix
