import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database.models import User, UserType
from database.repositories.user_repository import UserRepository

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


def _to_bcrypt_safe(password: str) -> bytes:
    # passlib bcrypt_sha256 prehashes with sha256 to bypass the 72-byte limit
    digest = hmac.new(b"", password.encode("utf-8"), hashlib.sha256).digest()
    import base64
    return base64.b64encode(digest)


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)

    @classmethod
    def hash_password(cls, password: str) -> str:
        hashed = bcrypt.hashpw(_to_bcrypt_safe(password), bcrypt.gensalt(rounds=12))
        return hashed.decode("utf-8")

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        h = hashed_password.encode("utf-8")
        # Support both new plain-bcrypt hashes and legacy passlib bcrypt_sha256 hashes
        if hashed_password.startswith("$bcrypt-sha256$"):
            # passlib bcrypt_sha256: extract the inner bcrypt hash after the prefix
            # format: $bcrypt-sha256$v=2,t=2b,r=12$<salt>$<hash>
            # passlib prehashes password as: sha256_hmac -> base64 -> bcrypt
            try:
                from passlib.context import CryptContext
                ctx = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")
                return ctx.verify(plain_password, hashed_password)
            except Exception:
                pass
            return False
        try:
            return bcrypt.checkpw(_to_bcrypt_safe(plain_password), h)
        except Exception:
            return False

    def authenticate_user(self, email: str, password: str) -> User | None:
        user = self.users.get_by_email(email)
        if user is None or not user.is_active:
            return None
        return user if self.verify_password(password, user.password_hash) else None

    @staticmethod
    def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
        expire_at = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        return jwt.encode({**data, "exp": expire_at}, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict[str, Any] | None:
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError:
            return None

    def create_user_token(self, user: User) -> str:
        return self.create_access_token(
            {
                "sub": user.email,
                "user_id": user.id,
                "user_type": user.user_type.value,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

    def register_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        user_type: UserType,
    ) -> User:
        if self.users.get_by_email(email) is not None:
            raise ValueError("User with this email already exists")

        user = User(
            email=email,
            password_hash=self.hash_password(password),
            first_name=first_name,
            last_name=last_name,
            user_type=user_type,
            is_active=True,
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user
