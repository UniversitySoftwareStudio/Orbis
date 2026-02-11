from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, UserType
from services.auth_service import AuthService
from dependencies import get_current_active_user
from schemas.auth import LoginRequest, RegisterRequest, UserResponse, UserTypeSchema

router = APIRouter()

@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    try:
        user_type_map = {
            UserTypeSchema.STUDENT: UserType.STUDENT,
            UserTypeSchema.INSTRUCTOR: UserType.INSTRUCTOR,
            UserTypeSchema.ADMIN: UserType.ADMIN
        }
        user_type = user_type_map[request.user_type]
        
        # Determine email format
        first_initial = request.first_name[0].lower()
        last_name_lower = request.last_name.lower()
        if user_type == UserType.STUDENT:
            email = f"{first_initial}.{last_name_lower}@bilgiedu.net"
        else:
            email = f"{first_initial}.{last_name_lower}@bilgi.edu.tr"
        
        user = auth_service.register_user(
            email=email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            user_type=user_type
        )
        
        access_token = auth_service.create_user_token(user)
        
        # Set Cookie (for browser safety)
        response.set_cookie(key="access_token", value=access_token, httponly=True, samesite="lax")
        
        # Return Token (for frontend app)
        resp_data = UserResponse.from_orm(user)
        resp_data.access_token = access_token
        return resp_data
    
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/auth/login", response_model=UserResponse)
def login(request: LoginRequest, response: Response, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    user = auth_service.authenticate_user(request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.create_user_token(user)
    
    # Set Cookie
    response.set_cookie(key="access_token", value=access_token, httponly=True, samesite="lax")
    
    # Return Token
    resp_data = UserResponse.from_orm(user)
    resp_data.access_token = access_token
    return resp_data

@router.get("/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    return UserResponse.from_orm(current_user)

@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out"}