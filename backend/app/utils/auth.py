import asyncio
from passlib.context import CryptContext
from jose import JWTError, jwt, ExpiredSignatureError
from datetime import datetime, timedelta
from app.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


async def hash_password_async(password: str) -> str:
    """Async wrapper - runs bcrypt hash in thread pool to avoid blocking event loop"""
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Async wrapper - runs bcrypt verify in thread pool to avoid blocking event loop"""
    return await asyncio.to_thread(verify_password, plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify and decode JWT token
    
    Returns:
        dict: Token payload if valid
        
    Raises:
        ExpiredSignatureError: If token is expired
        JWTError: If token is invalid (malformed, wrong signature, etc.)
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except ExpiredSignatureError:
        # Re-raise to allow caller to handle expired tokens specifically
        raise
    except JWTError:
        # Re-raise other JWT errors (invalid signature, malformed, etc.)
        raise