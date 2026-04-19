from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from core.logging import get_logger
from database.models import User, UserType
from database.session import get_db
from dependencies import get_current_active_user
from schemas.auth import LoginRequest, RegisterRequest, UserResponse, UserTypeSchema
from services.auth_service import AuthService

router = APIRouter()
logger = get_logger(__name__)
TOKEN_MAX_AGE_SECONDS = 1800

USER_TYPE_MAP = {
    UserTypeSchema.STUDENT: UserType.STUDENT,
    UserTypeSchema.INSTRUCTOR: UserType.INSTRUCTOR,
    UserTypeSchema.ADMIN: UserType.ADMIN,
}


def _school_email(first_name: str, last_name: str, user_type: UserType) -> str:
    if not first_name.strip() or not last_name.strip():
        raise ValueError("First name and last name are required")
    domain = "bilgiedu.net" if user_type == UserType.STUDENT else "bilgi.edu.tr"
    return f"{first_name.strip()[0].lower()}.{last_name.strip().lower()}@{domain}"


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=TOKEN_MAX_AGE_SECONDS,
    )


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    auth = AuthService(db)
    user_type = USER_TYPE_MAP[request.user_type]

    try:
        user = auth.register_user(
            email=_school_email(request.first_name, request.last_name, user_type),
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            user_type=user_type,
        )
    except ValueError as exc:
        logger.warning("Registration failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _set_auth_cookie(response, auth.create_user_token(user))
    return UserResponse.from_orm(user)


@router.post("/auth/login", response_model=UserResponse)
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserResponse:
    auth = AuthService(db)
    user = auth.authenticate_user(request.email, request.password)
    if user is None:
        logger.warning("Login failed for email=%s", request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _set_auth_cookie(response, auth.create_user_token(user))
    return UserResponse.from_orm(user)


@router.get("/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_active_user)) -> UserResponse:
    return UserResponse.from_orm(current_user)


@router.post("/auth/refresh", response_model=UserResponse)
def refresh_token(
    response: Response,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    _set_auth_cookie(response, AuthService(db).create_user_token(current_user))
    return UserResponse.from_orm(current_user)
