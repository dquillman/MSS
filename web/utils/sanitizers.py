"""
Input sanitization utilities for XSS prevention and security
"""
import re
import html
from urllib.parse import urlparse
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Try to import bleach for HTML sanitization (optional)
try:
    import bleach
    BLEACH_AVAILABLE = True
except ImportError:
    BLEACH_AVAILABLE = False
    logger.warning("[SANITIZER] bleach not installed. HTML sanitization will be basic.")


def sanitize_html(text: str, allowed_tags: Optional[list] = None) -> str:
    """
    Sanitize HTML to prevent XSS attacks
    
    Args:
        text: HTML string to sanitize
        allowed_tags: List of allowed HTML tags (None = strip all)
    
    Returns:
        Sanitized HTML string
    """
    if not text:
        return ""
    
    if BLEACH_AVAILABLE:
        # Use bleach for comprehensive sanitization
        if allowed_tags:
            cleaned = bleach.clean(text, tags=allowed_tags, strip=True)
        else:
            cleaned = bleach.clean(text, tags=[], strip=True)
        return cleaned
    else:
        # Basic sanitization without bleach
        # Escape all HTML entities
        cleaned = html.escape(text)
        return cleaned


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and other attacks
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename safe for filesystem use
    """
    if not filename:
        return "unnamed_file"
    
    # Remove path components
    filename = filename.split('/')[-1].split('\\')[-1]
    
    # Remove dangerous characters
    dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_len = 250 - len(ext) - 1 if ext else 250
        filename = name[:max_name_len] + ('.' + ext if ext else '')
    
    # Ensure it's not empty
    if not filename:
        filename = "unnamed_file"
    
    return filename


def sanitize_url(url: str) -> Optional[str]:
    """
    Validate and sanitize URLs
    
    Args:
        url: URL string to validate
    
    Returns:
        Sanitized URL or None if invalid
    
    Raises:
        ValueError: If URL is invalid
    """
    if not url:
        return None
    
    try:
        parsed = urlparse(url)
        
        # Only allow http and https schemes
        if parsed.scheme not in ['http', 'https']:
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
        
        # Reconstruct URL (removes dangerous fragments)
        sanitized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            sanitized += f"?{parsed.query}"
        
        return sanitized
    except Exception as e:
        logger.warning(f"[SANITIZER] URL validation failed: {e}")
        raise ValueError(f"Invalid URL: {url}")


def sanitize_email(email: str) -> Optional[str]:
    """
    Sanitize and validate email address
    
    Args:
        email: Email string
    
    Returns:
        Sanitized email or None if invalid
    """
    if not email:
        return None
    
    email = email.strip().lower()
    
    # Basic email validation regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(email_pattern, email):
        return email
    else:
        return None


def sanitize_text_input(text: str, max_length: int = 10000) -> str:
    """
    Sanitize general text input
    
    Args:
        text: Text to sanitize
        max_length: Maximum allowed length
    
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
    
    # Limit length
    if len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()






