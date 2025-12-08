"""
Authentication Routes for FastAPI

Complete authentication and user management endpoints.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from motor.motor_asyncio import AsyncIOMotorCollection

from .config import auth_config, PERMISSIONS
from .models import User, UserCreate, UserLogin, Token, UserResponse, UserUpdate, PasswordChange
from .utils import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    validate_role,
    AuthDependency
)

def create_auth_router(db_collection: AsyncIOMotorCollection) -> APIRouter:
    """
    Create authentication router with database dependency
    
    Args:
        db_collection: MongoDB collection for users
        
    Returns:
        FastAPI router with all authentication endpoints
    """
    router = APIRouter(prefix="/auth", tags=["Authentication"])
    auth_dep = AuthDependency(db_collection)
    
    @router.post("/register", response_model=UserResponse)
    async def register_user(
        user_data: UserCreate, 
        current_user: User = Depends(auth_dep.require_roles([auth_config.ROLES['ADMIN']]))
    ):
        """Register a new user (Admin only)"""
        try:
            # Check if username already exists
            existing_user = await db_collection.find_one({"username": user_data.username})
            if existing_user:
                raise HTTPException(
                    status_code=400, 
                    detail="Username already registered"
                )
            
            # Check if email already exists
            existing_email = await db_collection.find_one({"email": user_data.email})
            if existing_email:
                raise HTTPException(
                    status_code=400, 
                    detail="Email already registered"
                )
            
            # Validate role
            if not validate_role(user_data.role):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid role. Must be one of: {auth_config.VALID_ROLES}"
                )
            
            # Create new user
            hashed_password = get_password_hash(user_data.password)
            new_user = User(
                username=user_data.username,
                email=user_data.email,
                full_name=user_data.full_name,
                role=user_data.role,
                hashed_password=hashed_password
            )
            
            # Insert user to database
            await db_collection.insert_one(new_user.dict())
            
            logging.info(f"New user registered: {user_data.username} by {current_user.username}")
            return UserResponse(**new_user.dict())
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error registering user: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error registering user: {str(e)}"
            )

    @router.post("/login", response_model=Token)
    async def login_user(form_data: UserLogin):
        """Login user and return access token"""
        try:
            # Find user
            user_doc = await db_collection.find_one({"username": form_data.username})
            if not user_doc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            user = User(**user_doc)
            
            # Verify password
            if not verify_password(form_data.password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Check if user is active
            if not user.is_active:
                raise HTTPException(status_code=400, detail="Inactive user")
            
            # Update last login
            await db_collection.update_one(
                {"username": form_data.username},
                {"$set": {"last_login": datetime.now(timezone.utc)}}
            )
            
            # Create access token
            access_token_expires = timedelta(minutes=auth_config.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user.username}, 
                expires_delta=access_token_expires
            )
            
            logging.info(f"User logged in: {user.username}")
            
            return Token(
                access_token=access_token,
                token_type="bearer",
                user_info={
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role
                }
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error during login: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Login error: {str(e)}"
            )

    @router.get("/me", response_model=UserResponse)
    async def get_current_user_info(
        current_user: User = Depends(auth_dep.get_current_active_user)
    ):
        """Get current user information"""
        return UserResponse(**current_user.dict())

    @router.get("/users", response_model=List[UserResponse])
    async def get_all_users(
        current_user: User = Depends(auth_dep.require_roles([auth_config.ROLES['ADMIN']]))
    ):
        """Get all users (Admin only)"""
        try:
            users = await db_collection.find().to_list(100)
            return [UserResponse(**user) for user in users]
        except Exception as e:
            logging.error(f"Error fetching users: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error fetching users: {str(e)}"
            )

    @router.put("/users/{user_id}/toggle", response_model=UserResponse)
    async def toggle_user_status(
        user_id: str,
        current_user: User = Depends(auth_dep.require_roles([auth_config.ROLES['ADMIN']]))
    ):
        """Toggle user active status (Admin only)"""
        try:
            user_doc = await db_collection.find_one({"id": user_id})
            if not user_doc:
                raise HTTPException(status_code=404, detail="User not found")
            
            new_status = not user_doc.get("is_active", True)
            await db_collection.update_one(
                {"id": user_id},
                {"$set": {"is_active": new_status}}
            )
            
            updated_user = await db_collection.find_one({"id": user_id})
            
            logging.info(f"User {user_id} status changed to {new_status} by {current_user.username}")
            return UserResponse(**updated_user)
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error toggling user status: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error toggling user status: {str(e)}"
            )

    @router.put("/users/{user_id}", response_model=UserResponse)
    async def update_user(
        user_id: str,
        user_update: UserUpdate,
        current_user: User = Depends(auth_dep.require_roles([auth_config.ROLES['ADMIN']]))
    ):
        """Update user information (Admin only)"""
        try:
            user_doc = await db_collection.find_one({"id": user_id})
            if not user_doc:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Prepare update data
            update_data = {}
            if user_update.full_name is not None:
                update_data["full_name"] = user_update.full_name
            if user_update.email is not None:
                update_data["email"] = user_update.email
            if user_update.is_active is not None:
                update_data["is_active"] = user_update.is_active
            
            if update_data:
                await db_collection.update_one(
                    {"id": user_id},
                    {"$set": update_data}
                )
            
            updated_user = await db_collection.find_one({"id": user_id})
            
            logging.info(f"User {user_id} updated by {current_user.username}")
            return UserResponse(**updated_user)
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error updating user: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error updating user: {str(e)}"
            )

    @router.post("/change-password")
    async def change_password(
        password_data: PasswordChange,
        current_user: User = Depends(auth_dep.get_current_active_user)
    ):
        """Change current user's password"""
        try:
            # Verify current password
            if not verify_password(password_data.current_password, current_user.hashed_password):
                raise HTTPException(
                    status_code=400,
                    detail="Incorrect current password"
                )
            
            # Hash new password
            new_hashed_password = get_password_hash(password_data.new_password)
            
            # Update password in database
            await db_collection.update_one(
                {"id": current_user.id},
                {"$set": {"hashed_password": new_hashed_password}}
            )
            
            logging.info(f"Password changed for user: {current_user.username}")
            return {"message": "Password changed successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error changing password: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error changing password: {str(e)}"
            )

    @router.delete("/users/{user_id}")
    async def delete_user(
        user_id: str,
        current_user: User = Depends(auth_dep.require_roles([auth_config.ROLES['ADMIN']]))
    ):
        """Delete user (Admin only)"""
        try:
            # Prevent self-deletion
            if user_id == current_user.id:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot delete your own account"
                )
            
            user_doc = await db_collection.find_one({"id": user_id})
            if not user_doc:
                raise HTTPException(status_code=404, detail="User not found")
            
            await db_collection.delete_one({"id": user_id})
            
            logging.info(f"User {user_id} deleted by {current_user.username}")
            return {"message": "User deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error deleting user: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error deleting user: {str(e)}"
            )

    @router.post("/create-default-admin")
    async def create_default_admin():
        """Create default admin user if no users exist"""
        try:
            # Check if any users exist
            user_count = await db_collection.count_documents({})
            if user_count > 0:
                raise HTTPException(
                    status_code=400, 
                    detail="Users already exist. Use normal registration."
                )
            
            # Create default admin
            default_admin = User(
                username="admin",
                email="admin@liquorsales.com",
                full_name="System Administrator",
                role="admin",
                hashed_password=get_password_hash("admin")
            )
            
            await db_collection.insert_one(default_admin.dict())
            
            logging.info("Default admin user created")
            
            return {
                "message": "Default admin created successfully",
                "username": "admin",
                "password": "admin",
                "note": "Please change this password immediately after first login"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logging.error(f"Error creating default admin: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Error creating default admin: {str(e)}"
            )

    return router