from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database.models import User, UserType
from database.repositories.user_repository import UserRepository
from database.session import get_db
from services.auth_service import AuthService


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    token = request.cookies.get("access_token")
    if token is None:
        raise unauthorized

    payload = AuthService.decode_token(token)
    if payload is None:
        raise unauthorized

    email = payload.get("sub")
    if not isinstance(email, str) or not email:
        raise unauthorized

    user = UserRepository(db).get_by_email(email)
    if user is None:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user


def require_user_types(allowed_types: list[UserType]) -> Callable[..., User]:
    allowed = {user_type for user_type in allowed_types}

    def user_type_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.user_type not in allowed:
            expected = ", ".join(sorted(user_type.value for user_type in allowed))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required user types: {expected}",
            )
        return current_user

    return user_type_checker


def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.user_type != UserType.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_instructor(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.user_type not in {UserType.INSTRUCTOR, UserType.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor or Admin access required",
        )
    return current_user


def require_student(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.user_type not in {UserType.STUDENT, UserType.INSTRUCTOR, UserType.ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access required")
    return current_user
