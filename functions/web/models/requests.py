"""
Pydantic models for API request validation
"""
from pydantic import BaseModel, EmailStr, Field, ValidationError
from typing import Optional, List, Dict, Any


class LoginRequest(BaseModel):
    """Request model for user login"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")


class SignupRequest(BaseModel):
    """Request model for user signup"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="Optional username")


class CreateVideoRequest(BaseModel):
    """Request model for video creation"""
    topic: str = Field(..., min_length=1, description="Video topic/title")
    duration: Optional[int] = Field(None, ge=1, le=600, description="Video duration in seconds (1-600)")
    include_avatar: Optional[bool] = Field(True, description="Include talking avatar")
    include_logo: Optional[bool] = Field(True, description="Include logo overlay")


class UpdateVideoRequest(BaseModel):
    """Request model for updating video metadata"""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="Video title")
    description: Optional[str] = Field(None, max_length=5000, description="Video description")
    tags: Optional[List[str]] = Field(None, max_items=50, description="Video tags")


class PostProcessRequest(BaseModel):
    """Request model for video post-processing"""
    video_filename: Optional[str] = Field(None, description="Video filename (if using existing file)")
    intro_text: Optional[str] = Field(None, description="Custom intro text")
    outro_text: Optional[str] = Field(None, description="Custom outro text")
    use_did: Optional[bool] = Field(True, description="Use D-ID for talking avatar")
    avatar_id: Optional[str] = Field(None, description="Specific avatar ID to use")
    include_logo: Optional[bool] = Field(True, description="Include logo overlay")


class PlatformPublishRequest(BaseModel):
    """Request model for platform publishing"""
    video_filename: str = Field(..., min_length=1, description="Video filename")
    platforms: List[str] = Field(..., min_items=1, description="Platforms to publish to")
    title: str = Field(..., min_length=1, max_length=200, description="Video title")
    description: Optional[str] = Field(None, max_length=5000, description="Video description")
    tags: Optional[List[str]] = Field(None, max_items=50, description="Video tags")
    scheduled_time: Optional[str] = Field(None, description="Scheduled publish time (ISO format)")
    thumbnail_path: Optional[str] = Field(None, description="Thumbnail file path")
