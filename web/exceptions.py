"""
Custom exceptions for MSS application
"""
class MSSException(Exception):
    """Base exception for MSS application"""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

class VideoGenerationError(MSSException):
    """Video creation or processing failed"""
    pass

class APIError(MSSException):
    """External API call failed"""
    pass

class ValidationError(MSSException):
    """Input validation failed"""
    pass

class AuthenticationError(MSSException):
    """Authentication failed"""
    pass

class DatabaseError(MSSException):
    """Database operation failed"""
    pass

class FileUploadError(MSSException):
    """File upload failed"""
    pass

class RateLimitError(MSSException):
    """Rate limit exceeded"""
    pass

