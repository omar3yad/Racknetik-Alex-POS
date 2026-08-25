from datetime import datetime, timezone, timedelta
import bcrypt
from jose import jwt, JWTError
from config import Settings
from models.user import User
from repositories.user_repo import UserRepository
from schemas.auth import TokenPayload

DUMMY_HASH = "$2b$12$pqd1tgDPY04wL8zVySNatedgTHZLGictaEdPedhCa9M4sf/SnoK.y"

class AuthenticationError(Exception):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(message)
        self.message = message

class AuthService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def hash_password(self, plain: str) -> str:
        hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12))
        del plain
        return hashed.decode("utf-8")

    def verify_password(self, plain: str, hashed: str) -> bool:
        res = bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        del plain
        return res

    def create_access_token(self, user_id: int, role: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=self.settings.JWT_EXPIRE_HOURS)).timestamp()),
        }
        return jwt.encode(payload, self.settings.SECRET_KEY, algorithm=self.settings.JWT_ALGORITHM)

    def decode_token(self, token: str) -> TokenPayload:
        try:
            payload = jwt.decode(token, self.settings.SECRET_KEY, algorithms=[self.settings.JWT_ALGORITHM])
            return TokenPayload(**payload)
        except (JWTError, Exception):
            raise AuthenticationError("Token is invalid or expired")

    async def authenticate_user(
        self, username: str, password: str, user_repo: UserRepository
    ) -> User:
        user = await user_repo.get_by_username(username.strip())
        if not user:
            self.verify_password("dummy", DUMMY_HASH)
            raise AuthenticationError("Invalid credentials")
        
        if not self.verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid credentials")
            
        if not user.is_active:
            raise AuthenticationError("Invalid credentials")
            
        return user
