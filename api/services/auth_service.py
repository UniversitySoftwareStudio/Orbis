import os
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database.models import User, UserType
from database.repositories.user_repository import UserRepository

pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

def _prime_passlib() -> None:
    try:
        pwd_context.hash("__passlib_init__")
    except (ValueError, AttributeError):
        return


_prime_passlib()


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)

    @staticmethod
    def _run_bcrypt(fn: Any, password: str, *args: str) -> Any:
        try:
            return fn(password, *args)
        except ValueError as exc:
            msg = str(exc)
            if "72 bytes" not in msg and "longer than 72 bytes" not in msg:
                raise
            safe = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
            return fn(safe, *args)

    @classmethod
    def hash_password(cls, password: str) -> str:
        return cls._run_bcrypt(pwd_context.hash, password)

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        return cls._run_bcrypt(pwd_context.verify, plain_password, hashed_password)

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
