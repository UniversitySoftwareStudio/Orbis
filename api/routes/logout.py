from fastapi import APIRouter, Response
from dependencies import get_current_active_user
from database.models import User

router = APIRouter()

@router.post("/auth/logout")
def logout(response: Response, current_user: User = get_current_active_user):
    """
    Logout by clearing the httpOnly cookie.
    """
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out"}
