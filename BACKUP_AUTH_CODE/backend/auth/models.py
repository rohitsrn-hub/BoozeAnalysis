"""
Authentication Models for FastAPI

Pydantic models for user authentication and authorization.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid

class User(BaseModel):
    """Complete User model for database storage"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    full_name: str
    role: str  # "admin", "urc_clk", "dashboard_viewer"
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None

class UserCreate(BaseModel):
    """User creation request model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    role: str
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    """User login request model"""
    username: str
    password: str

class Token(BaseModel):
    """JWT token response model"""
    access_token: str
    token_type: str
    user_info: Dict[str, Any]

class UserResponse(BaseModel):
    """Safe user data response model (no password)"""
    id: str
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

class UserUpdate(BaseModel):
    """User update model"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

class PasswordChange(BaseModel):
    """Password change request model"""
    current_password: str
    new_password: str = Field(..., min_length=6)

class TokenPayload(BaseModel):
    """JWT token payload model"""
    sub: str  # username
    exp: datetime
    iat: datetime