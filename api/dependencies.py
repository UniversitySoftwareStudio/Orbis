from typing import Optional, List
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, UserType
from database.repositories.user_repository import UserRepository
from services.auth_service import AuthService


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from httpOnly cookie.
    Validates token and returns User object with UserType.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    
    # Get token from httpOnly cookie
    token = request.cookies.get("access_token")
    if not token:
        raise credentials_exception
    
    payload = AuthService.decode_token(token)
    
    if payload is None:
        raise credentials_exception
    
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(email)
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to ensure the current user is active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


def require_user_types(allowed_types: List[UserType]):
    """
    Factory function to create a dependency that restricts access based on UserType.
    
    Usage:
        @router.get("/admin-only")
        def admin_route(user: User = Depends(require_user_types([UserType.ADMIN]))):
            ...
    
        @router.get("/instructors-and-admins")
        def instructor_route(user: User = Depends(require_user_types([UserType.INSTRUCTOR, UserType.ADMIN]))):
            ...
    """
    def user_type_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.user_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required user types: {[t.value for t in allowed_types]}"
            )
        return current_user
    
    return user_type_checker


# Convenience dependencies for common role checks
def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Dependency to require ADMIN role"""
    if current_user.user_type != UserType.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_instructor(current_user: User = Depends(get_current_active_user)) -> User:
    """Dependency to require INSTRUCTOR or ADMIN role"""
    if current_user.user_type not in [UserType.INSTRUCTOR, UserType.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instructor or Admin access required"
        )
    return current_user


def require_student(current_user: User = Depends(get_current_active_user)) -> User:
    """Dependency to require STUDENT role (or higher privileges)"""
    if current_user.user_type not in [UserType.STUDENT, UserType.INSTRUCTOR, UserType.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required"
        )
    return current_user
