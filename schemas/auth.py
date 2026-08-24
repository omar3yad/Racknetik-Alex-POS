from pydantic import BaseModel, Field
from models.user import UserRole

class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)

class LoginResponse(BaseModel):
    user_id: int
    role: UserRole
    full_name: str

class TokenPayload(BaseModel):
    sub: str
    role: str
    iat: int
    exp: int
