from fastapi import APIRouter, Response, Depends
from dependencies import get_current_active_user
from database.models import User

router = APIRouter()

@router.post("/auth/logout")
def logout(
    response: Response, 
    # FIX: Explicitly use Depends() here
    current_user: User = Depends(get_current_active_user)
):
    """
    Logout by clearing the httpOnly cookie.
    """
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out"}