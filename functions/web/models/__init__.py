"""
Request/Response models for MSS API using Pydantic
"""
from web.models.requests import (
    LoginRequest,
    SignupRequest,
    CreateVideoRequest,
    UpdateVideoRequest,
    PostProcessRequest,
    PlatformPublishRequest
)

__all__ = [
    'LoginRequest',
    'SignupRequest', 
    'CreateVideoRequest',
    'UpdateVideoRequest',
    'PostProcessRequest',
    'PlatformPublishRequest'
]

