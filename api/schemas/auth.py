from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from enum import Enum

class UserTypeSchema(str, Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=3)

class RegisterRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=3)
    user_type: UserTypeSchema

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    user_type: UserTypeSchema
    is_active: bool
    # Added this field so the frontend can receive the token!
    access_token: Optional[str] = None 
    
    class Config:
        from_attributes = True