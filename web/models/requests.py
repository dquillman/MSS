"""
Pydantic request models for input validation
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any


class LoginRequest(BaseModel):
    """Login request model"""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123"
            }
        }


class SignupRequest(BaseModel):
    """Signup request model"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Password must be 8-128 characters")
    username: Optional[str] = Field(None, max_length=50, description="Optional username")
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Basic password strength validation"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        # Optional: Add more strength checks
        # if not any(c.isupper() for c in v):
        #     raise ValueError('Password must contain at least one uppercase letter')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123",
                "username": "newuser"
            }
        }


class CreateVideoRequest(BaseModel):
    """Video creation request model"""
    topic: str = Field(..., min_length=5, max_length=200, description="Video topic")
    duration: Optional[int] = Field(60, ge=30, le=600, description="Video duration in seconds (30-600)")
    niche: Optional[str] = Field(None, max_length=100, description="Content niche")
    style: Optional[str] = Field(None, max_length=50, description="Video style")
    voice: Optional[str] = Field(None, max_length=50, description="Voice selection")
    
    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Top 10 Tech Trends in 2025",
                "duration": 60,
                "niche": "technology",
                "style": "professional"
            }
        }


class PostProcessRequest(BaseModel):
    """Video post-processing request model"""
    video_filename: str = Field(..., min_length=1, description="Video filename to process")
    include_logo: Optional[bool] = Field(True, description="Include logo overlay")
    logo_position: Optional[str] = Field("bottom-left", description="Logo position")
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_filename": "video_1234567890.mp4",
                "include_logo": True,
                "logo_position": "bottom-right"
            }
        }


class PublishRequest(BaseModel):
    """Platform publishing request model"""
    video_filename: str = Field(..., min_length=1, description="Video filename to publish")
    platform: str = Field(..., description="Target platform")
    title: Optional[str] = Field(None, max_length=100, description="Video title")
    description: Optional[str] = Field(None, max_length=5000, description="Video description")
    tags: Optional[List[str]] = Field(None, max_items=50, description="Video tags")
    thumbnail_filename: Optional[str] = Field(None, description="Thumbnail filename")
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_filename": "video_1234567890.mp4",
                "platform": "youtube",
                "title": "My Amazing Video",
                "description": "This is a great video",
                "tags": ["tech", "trending"]
            }
        }


class GenerateTopicsRequest(BaseModel):
    """Topic generation request model"""
    niche: Optional[str] = Field(None, max_length=100, description="Content niche")
    count: Optional[int] = Field(10, ge=1, le=50, description="Number of topics to generate")
    
    class Config:
        json_schema_extra = {
            "example": {
                "niche": "technology",
                "count": 10
            }
        }

