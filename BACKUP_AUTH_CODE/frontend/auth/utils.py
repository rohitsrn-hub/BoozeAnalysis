"""
Authentication Utilities for FastAPI

Helper functions for password hashing, JWT tokens, and permission checking.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import auth_config, PERMISSIONS
from .models import User

# Initialize password context
pwd_context = CryptContext(
    schemes=["bcrypt"], 
    deprecated="auto"
)

# Initialize HTTP Bearer security
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    import bcrypt
    try:
        # Handle both string and bytes for hashed_password
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)
    except Exception:
        # Fallback to passlib for existing hashes
        return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    import bcrypt
    # Ensure password is properly encoded and within bcrypt limits
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    })
    encoded_jwt = jwt.encode(to_encode, auth_config.SECRET_KEY, algorithm=auth_config.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, auth_config.SECRET_KEY, algorithms=[auth_config.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def validate_role(role: str) -> bool:
    """Validate if a role is valid"""
    return role in auth_config.VALID_ROLES

def check_permission(user_role: str, required_permissions: List[str]) -> bool:
    """Check if user role has any of the required permissions"""
    if not user_role:
        return False
    
    for permission in required_permissions:
        allowed_roles = PERMISSIONS.get(permission, [])
        if user_role in allowed_roles:
            return True
    
    return False

def check_role_permission(user_role: str, required_roles: List[str]) -> bool:
    """Check if user role is in the list of required roles"""
    return user_role in required_roles

class AuthDependency:
    """Authentication dependency class"""
    
    def __init__(self, db_collection):
        self.db = db_collection
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
        """Get current authenticated user"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = verify_token(credentials.credentials)
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        
        user_doc = await self.db.find_one({"username": username})
        if user_doc is None:
            raise credentials_exception
        
        return User(**user_doc)
    
    async def get_current_active_user(self, current_user: User = None) -> User:
        """Get current active user"""
        if current_user is None:
            current_user = await self.get_current_user()
        
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user
    
    def require_roles(self, required_roles: List[str]):
        """Create a dependency that requires specific roles"""
        async def role_checker(current_user: User = Depends(self.get_current_active_user)):
            if not check_role_permission(current_user.role, required_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not enough permissions. Required roles: {required_roles}"
                )
            return current_user
        return role_checker
    
    def require_permissions(self, required_permissions: List[str]):
        """Create a dependency that requires specific permissions"""
        async def permission_checker(current_user: User = Depends(self.get_current_active_user)):
            if not check_permission(current_user.role, required_permissions):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not enough permissions. Required permissions: {required_permissions}"
                )
            return current_user
        return permission_checker