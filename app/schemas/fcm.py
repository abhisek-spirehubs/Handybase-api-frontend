# app/schemas/fcm.py
from pydantic import BaseModel
from typing import Optional

class TokenRegisterRequest(BaseModel):
    token: str
    device_id: Optional[str] = None
    platform: Optional[str] = None

class TokenRegisterResponse(BaseModel):
    success: bool
    message: str