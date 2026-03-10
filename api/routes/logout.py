from fastapi import APIRouter, Depends, Response

from database.models import User
from dependencies import get_current_active_user

router = APIRouter()


@router.post("/auth/logout")
def logout(
    response: Response,
    _current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out"}
