"""
Security event logging for MSS application
"""
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger('security')

# File handler for security log (optional)
security_log_file = os.getenv('SECURITY_LOG_FILE', 'logs/security.log')

def setup_security_logging():
    """Setup dedicated security logging"""
    try:
        log_dir = os.path.dirname(security_log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(security_log_file)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s [SECURITY] %(levelname)s: %(message)s')
        )
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[SECURITY] Failed to setup file logging: {e}")


def log_failed_login(email: str, ip_address: str, reason: str = "Invalid credentials"):
    """Log failed login attempt"""
    logger.warning(
        f"Failed login attempt - Email: {email}, IP: {ip_address}, Reason: {reason}",
        extra={
            'event': 'failed_login',
            'email': email,
            'ip_address': ip_address,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        }
    )


def log_successful_login(email: str, ip_address: str, user_id: int):
    """Log successful login"""
    logger.info(
        f"Successful login - Email: {email}, IP: {ip_address}, User ID: {user_id}",
        extra={
            'event': 'successful_login',
            'email': email,
            'ip_address': ip_address,
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat()
        }
    )


def log_suspicious_activity(event: str, user_id: Optional[int], details: Dict[str, Any]):
    """Log suspicious activity"""
    logger.warning(
        f"Suspicious activity: {event} - User ID: {user_id}",
        extra={
            'event': 'suspicious_activity',
            'activity': event,
            'user_id': user_id,
            'details': details,
            'timestamp': datetime.utcnow().isoformat()
        }
    )


def log_file_upload_violation(filename: str, reason: str, ip_address: str):
    """Log file upload security violation"""
    logger.warning(
        f"File upload violation - Filename: {filename}, Reason: {reason}, IP: {ip_address}",
        extra={
            'event': 'upload_violation',
            'filename': filename,
            'reason': reason,
            'ip_address': ip_address,
            'timestamp': datetime.utcnow().isoformat()
        }
    )


def log_rate_limit_exceeded(endpoint: str, ip_address: str, count: int):
    """Log rate limit exceeded"""
    logger.warning(
        f"Rate limit exceeded - Endpoint: {endpoint}, IP: {ip_address}, Count: {count}",
        extra={
            'event': 'rate_limit_exceeded',
            'endpoint': endpoint,
            'ip_address': ip_address,
            'count': count,
            'timestamp': datetime.utcnow().isoformat()
        }
    )


def log_sql_injection_attempt(query: str, ip_address: str):
    """Log potential SQL injection attempt"""
    logger.error(
        f"Potential SQL injection attempt - Query: {query[:100]}, IP: {ip_address}",
        extra={
            'event': 'sql_injection_attempt',
            'query': query[:500],  # Truncate for logging
            'ip_address': ip_address,
            'timestamp': datetime.utcnow().isoformat()
        }
    )


# Initialize security logging on import
try:
    setup_security_logging()
except Exception:
    pass  # Continue without file logging if setup fails

