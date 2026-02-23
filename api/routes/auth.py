from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, UserType
from services.auth_service import AuthService
from dependencies import get_current_active_user
from schemas.auth import (
    LoginRequest, 
    RegisterRequest, 
    UserResponse,
    UserTypeSchema
)

router = APIRouter()


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """
    Register a new user with email, password, and UserType (STUDENT, INSTRUCTOR, or ADMIN).
    Returns user info and JWT token.
    
    Email is automatically generated from first and last name:
    - STUDENT: {first_initial}.{last_name}@bilgiedu.net
    - INSTRUCTOR: {first_initial}.{last_name}@bilgi.edu.tr
    - ADMIN: {first_initial}.{last_name}@bilgi.edu.tr
    
    Example:
    ```json
    {
        "first_name": "John",
        "last_name": "Doe",
        "password": "securepass123",
        "user_type": "student"
    }
    ```
    
    Generated email will be: j.doe@bilgiedu.net
    """
    auth_service = AuthService(db)
    
    try:
        # Convert schema enum to model enum
        user_type_map = {
            UserTypeSchema.STUDENT: UserType.STUDENT,
            UserTypeSchema.INSTRUCTOR: UserType.INSTRUCTOR,
            UserTypeSchema.ADMIN: UserType.ADMIN
        }
        user_type = user_type_map[request.user_type]
        
        # Generate email from first and last name based on user type
        first_initial = request.first_name[0].lower()
        last_name_lower = request.last_name.lower()
        
        if user_type == UserType.STUDENT:
            email = f"{first_initial}.{last_name_lower}@bilgiedu.net"
        else:  # INSTRUCTOR or ADMIN
            email = f"{first_initial}.{last_name_lower}@bilgi.edu.tr"
        
        user = auth_service.register_user(
            email=email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            user_type=user_type
        )
        
        # Generate JWT token and set httpOnly cookie
        access_token = auth_service.create_user_token(user)
        
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=1800  # 30 minutes
        )
        
        return UserResponse.from_orm(user)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/auth/login", response_model=UserResponse)
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    Login with email and password. Returns JWT token with UserType embedded.
    
    Example:
    ```json
    {
        "email": "student@university.edu",
        "password": "securepass123"
    }
    ```
    """
    auth_service = AuthService(db)
    
    try:
        user = auth_service.authenticate_user(request.email, request.password)
    except ValueError as e:
        # Handle password backend/value errors (e.g. bcrypt 72-byte limit) as authentication failures
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate JWT token and set httpOnly cookie
    access_token = auth_service.create_user_token(user)
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=1800  # 30 minutes
    )
    
    return UserResponse.from_orm(user)


@router.get("/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    Get current authenticated user's information including UserType.
    Authentication via httpOnly cookie (automatic).
    """
    return UserResponse.from_orm(current_user)


@router.post("/auth/logout")
def logout(response: Response):
    """
    Logout by clearing the httpOnly cookie.
    """
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out"}


@router.post("/auth/refresh", response_model=UserResponse)
def refresh_token(response: Response, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Refresh JWT token for current user.
    Sets new token with updated expiration in httpOnly cookie.
    """
    auth_service = AuthService(db)
    access_token = auth_service.create_user_token(current_user)
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=1800  # 30 minutes
    )
    
    return UserResponse.from_orm(current_user)
