"""
Authentication Module for FastAPI

This module provides complete authentication and authorization functionality
for FastAPI applications with MongoDB.

Usage:
    from auth import AuthModule, auth_config
    
    # Initialize auth module
    auth_module = AuthModule(db_collection)
    
    # Include in FastAPI app
    app.include_router(auth_module.router)
    
    # Use dependencies
    @app.get("/protected")
    async def protected_route(user = Depends(auth_module.get_current_user)):
        return {"message": f"Hello {user.username}"}
"""

from motor.motor_asyncio import AsyncIOMotorCollection
from fastapi import Depends

from .config import auth_config, PERMISSIONS, AuthConfig
from .models import User, UserCreate, UserLogin, Token, UserResponse, UserUpdate, PasswordChange
from .utils import (
    verify_password,
    get_password_hash, 
    create_access_token,
    verify_token,
    validate_role,
    check_permission,
    check_role_permission,
    AuthDependency
)
from .routes import create_auth_router

class AuthModule:
    """
    Main authentication module class
    
    This class provides a complete authentication system that can be
    easily integrated into any FastAPI application.
    """
    
    def __init__(self, db_collection: AsyncIOMotorCollection):
        """
        Initialize authentication module
        
        Args:
            db_collection: MongoDB collection for storing users
        """
        self.db_collection = db_collection
        self.auth_dep = AuthDependency(db_collection)
        self.router = create_auth_router(db_collection)
    
    # Expose commonly used dependencies
    def get_current_user(self):
        """Get current authenticated user dependency"""
        return Depends(self.auth_dep.get_current_user)
    
    def get_current_active_user(self):
        """Get current active user dependency"""
        return Depends(self.auth_dep.get_current_active_user)
    
    def require_roles(self, roles):
        """Require specific roles dependency"""
        return Depends(self.auth_dep.require_roles(roles))
    
    def require_permissions(self, permissions):
        """Require specific permissions dependency"""
        return Depends(self.auth_dep.require_permissions(permissions))
    
    def require_admin(self):
        """Require admin role dependency"""
        return self.require_roles([auth_config.ROLES['ADMIN']])
    
    def require_manager_or_admin(self):
        """Require manager or admin role dependency"""
        return self.require_roles([auth_config.ROLES['ADMIN'], auth_config.ROLES['MANAGER']])

# Export everything for easy importing
__all__ = [
    'AuthModule',
    'auth_config',
    'PERMISSIONS',
    'AuthConfig',
    'User',
    'UserCreate', 
    'UserLogin',
    'Token',
    'UserResponse',
    'UserUpdate',
    'PasswordChange',
    'verify_password',
    'get_password_hash',
    'create_access_token',
    'verify_token',
    'validate_role',
    'check_permission',
    'check_role_permission',
    'AuthDependency',
    'create_auth_router'
]