import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from jose import JWTError, jwt


load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day


def create_access_token(
    user_id: int,
    access_token_version: int,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": str(user_id),
        "access_token_version": access_token_version,
        "exp": expire,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> tuple[int, int] | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        access_token_version = payload.get("access_token_version")

        if user_id is None or access_token_version is None:
            return None

        return int(user_id), int(access_token_version)

    except (JWTError, TypeError, ValueError):
        return None