from typing import Any
from beanie import PydanticObjectId
from pydantic import BaseModel, Field, ConfigDict, field_serializer, field_validator


class MongoBaseModel(BaseModel):
    """
    Generic base schema for Mongo models.
    Automatically converts ObjectId fields to strings in JSON responses.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    @field_serializer("*", when_used="json")
    def serialize_objectid(self, value):
        if isinstance(value, PydanticObjectId):
            return str(value)
        return value


class MongoBaseResponse(BaseModel):
    """
    Base schema for API responses where MongoDB _id should be exposed as id.
    """

    id: Any = Field(alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        json_encoders={PydanticObjectId: str},
    )

    @field_validator("id", mode="before")
    @classmethod
    def convert_object_id(cls, v):
        if v is None:
            return v
        return str(v)