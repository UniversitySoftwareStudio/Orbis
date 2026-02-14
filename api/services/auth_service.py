import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from database.models import User, UserType
from database.repositories.user_repository import UserRepository

# Password hashing
# Prefer bcrypt_sha256 to avoid bcrypt's 72-byte password limit,
# but keep plain bcrypt as a fallback to verify any existing bcrypt hashes.
pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")

# Ensure passlib's bcrypt backend initializes using a short secret so
# backend detection doesn't attempt to process long passwords during
# initialization (which can trigger bcrypt's 72-byte limit).
try:
    pwd_context.hash("__passlib_init__")
except Exception:
    # If initialization fails, we still keep going; errors will surface
    # when hashing/verifying at runtime and can be handled there.
    pass

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


class AuthService:
    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        try:
            return pwd_context.hash(password)
        except ValueError as e:
            if "72 bytes" in str(e) or "longer than 72 bytes" in str(e):
                truncated = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
                return pwd_context.hash(truncated)
            raise
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash"""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except ValueError as e:
            if "72 bytes" in str(e) or "longer than 72 bytes" in str(e):
                truncated = plain_password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
                return pwd_context.verify(truncated, hashed_password)
            raise
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password"""
        user = self.user_repo.get_by_email(email)
        if not user:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            return None
        return user
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token with UserType"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and verify a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None
    
    def create_user_token(self, user: User) -> str:
        """Create a token for a user with their UserType"""
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(
            data={
                "sub": user.email,
                "user_id": user.id,
                "user_type": user.user_type.value,  # Include UserType in token
                "first_name": user.first_name,
                "last_name": user.last_name
            },
            expires_delta=access_token_expires
        )
        return access_token
    
    def register_user(
        self, 
        email: str, 
        password: str, 
        first_name: str, 
        last_name: str, 
        user_type: UserType
    ) -> User:
        """Register a new user with UserType"""
        # Check if user already exists
        existing_user = self.user_repo.get_by_email(email)
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Create new user
        hashed_password = self.hash_password(password)
        user = User(
            email=email,
            password_hash=hashed_password,
            first_name=first_name,
            last_name=last_name,
            user_type=user_type,
            is_active=True
        )
        
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        
        return user
