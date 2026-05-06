from pydantic import BaseModel
from typing import List
from app.schemas.service import ClientServiceResponse


class PaginatedServiceResponse(BaseModel):
    items: List[ClientServiceResponse]
    total: int
    page: int
    limit: int
