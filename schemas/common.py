from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    total: int
    page: int
    size: int

    model_config = ConfigDict(from_attributes=True)

class ErrorResponse(BaseModel):
    detail: str
    code: str

    model_config = ConfigDict(from_attributes=True)
