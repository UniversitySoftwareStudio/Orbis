from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from enum import Enum


class UserTypeSchema(str, Enum):
    """Pydantic schema for UserType enum"""
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str = Field(..., min_length=3)


class RegisterRequest(BaseModel):
    """User registration request schema"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=3)
    user_type: UserTypeSchema


class UserResponse(BaseModel):
    """User information response schema"""
    id: int
    email: str
    first_name: str
    last_name: str
    user_type: UserTypeSchema
    is_active: bool
    
    class Config:
        from_attributes = True