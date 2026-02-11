from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
import bcrypt
from sqlalchemy.orm import Session
import os

from database.models import User
from database.repositories.user_repository import UserRepository

# Config
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-this")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

class AuthService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def verify_password(self, plain_password, hashed_password):
        # bcrypt requires bytes, so we encode strings to utf-8
        if not plain_password or not hashed_password:
            return False
            
        p_bytes = plain_password.encode('utf-8')
        h_bytes = hashed_password.encode('utf-8')
        
        try:
            return bcrypt.checkpw(p_bytes, h_bytes)
        except ValueError:
            # This happens if the DB contains a plain text password (not a hash)
            # or a hash from a different algorithm.
            print("⚠️ Error: Password in DB is not a valid bcrypt hash.")
            return False

    def get_password_hash(self, password):
        p_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(p_bytes, salt).decode('utf-8')

    def authenticate_user(self, email: str, password: str):
        user = self.user_repo.get_by_email(email)
        if not user:
            return False
        # Verify the password using the new direct method
        if not self.verify_password(password, user.password_hash):
            return False
        return user

    def register_user(self, email: str, password: str, first_name: str, last_name: str, user_type: str):
        # Check if user exists
        if self.user_repo.get_by_email(email):
            raise ValueError("Email already registered")

        # Hash password
        hashed_password = self.get_password_hash(password)
        
        new_user = User(
            email=email,
            password_hash=hashed_password,
            first_name=first_name,
            last_name=last_name,
            user_type=user_type, 
            is_active=True
        )
        
        return self.user_repo.create(new_user)

    def create_user_token(self, user: User) -> str:
        """Generates the JWT"""
        data = {
            "sub": user.email,
            "type": str(user.user_type),
            "id": str(user.id)
        }
        return self.create_access_token(data)

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None