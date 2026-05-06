from pydantic import Field, field_serializer, field_validator,ConfigDict
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from beanie import PydanticObjectId
from app.schemas.base import MongoBaseModel
from app.schemas.common import StatusEnum


class ReviewCreate(MongoBaseModel):
    rating:  float          = Field(..., ge=1, le=5)
    comment: Optional[str]  = Field(None, max_length=1000)

    @field_validator("rating")
    @classmethod
    def round_rating(cls, v: float) -> float:
        return round(v, 1)


class ReviewUpdate(MongoBaseModel):
    rating:  Optional[float] = Field(None, ge=1, le=5)
    comment: Optional[str]   = Field(None, max_length=1000)

    @field_validator("rating")
    @classmethod
    def round_rating(cls, v: Optional[float]) -> Optional[float]:
        return round(v, 1) if v is not None else v

class ReviewResponse(BaseModel):
    id: PydanticObjectId = Field(alias="_id")
    client_id: str
    provider_id: str
    service_id: str
    booking_id: str
    rating: float
    comment: Optional[str] = None
    media_urls: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    # optional fields for enriched data
    client_name: Optional[str] = None
    provider_name: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    @field_serializer("id")
    def serialize_id(self, value: PydanticObjectId) -> str:
        return str(value)


class ReviewModerationResponse(ReviewResponse):
    status: StatusEnum
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    # inherited fields already