from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from app.models.user import UserRole


class AdminCreateUser(BaseModel):
    """
    Schema used by admin to create client or provider users.
    """

    fname: str = Field(..., min_length=1, max_length=50)
    lname: str = Field(..., min_length=1, max_length=50)

    email: EmailStr

    password: str = Field(..., min_length=8, max_length=128)

    phone: Optional[str] = None

    user_type: UserRole