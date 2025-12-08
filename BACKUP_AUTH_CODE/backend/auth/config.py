"""
Authentication Module Configuration for FastAPI

This file contains all configurable settings for the authentication module.
Customize these values to match your project requirements.
"""

import os
from typing import List, Dict

class AuthConfig:
    """Authentication configuration class"""
    
    # JWT Configuration
    SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', 480))  # 8 hours
    
    # Password Configuration
    PASSWORD_MIN_LENGTH = 6
    PASSWORD_HASH_SCHEMES = ["bcrypt"]
    
    # User Roles
    ROLES = {
        'ADMIN': 'admin',
        'MANAGER': 'urc_clk',  # Customize this name as needed
        'VIEWER': 'dashboard_viewer'
    }
    
    # Valid roles list
    VALID_ROLES = list(ROLES.values())
    
    # Default Admin Credentials
    DEFAULT_ADMIN = {
        'username': 'admin',
        'email': 'admin@example.com',
        'full_name': 'System Administrator',
        'password': 'admin123'
    }
    
    # Database Collection Names
    USERS_COLLECTION = 'users'
    
    # Rate Limiting (if needed)
    LOGIN_RATE_LIMIT = {
        'attempts': 5,
        'window_minutes': 15
    }

# Permission Matrices - Define what each role can access
PERMISSIONS: Dict[str, List[str]] = {
    # Data Management
    'CAN_UPLOAD_DATA': [AuthConfig.ROLES['ADMIN'], AuthConfig.ROLES['MANAGER']],
    'CAN_DELETE_DATA': [AuthConfig.ROLES['ADMIN']],
    'CAN_EDIT_DATA': [AuthConfig.ROLES['ADMIN'], AuthConfig.ROLES['MANAGER']],
    'CAN_VIEW_DATA': [AuthConfig.ROLES['ADMIN'], AuthConfig.ROLES['MANAGER'], AuthConfig.ROLES['VIEWER']],
    
    # User Management
    'CAN_CREATE_USERS': [AuthConfig.ROLES['ADMIN']],
    'CAN_MANAGE_USERS': [AuthConfig.ROLES['ADMIN']],
    'CAN_VIEW_USERS': [AuthConfig.ROLES['ADMIN']],
    
    # Reports & Analytics
    'CAN_VIEW_ANALYTICS': [AuthConfig.ROLES['ADMIN'], AuthConfig.ROLES['MANAGER'], AuthConfig.ROLES['VIEWER']],
    'CAN_EXPORT_REPORTS': [AuthConfig.ROLES['ADMIN'], AuthConfig.ROLES['MANAGER'], AuthConfig.ROLES['VIEWER']],
    'CAN_GENERATE_REPORTS': [AuthConfig.ROLES['ADMIN'], AuthConfig.ROLES['MANAGER']],
    
    # System Administration
    'CAN_ACCESS_SETTINGS': [AuthConfig.ROLES['ADMIN']],
    'CAN_BACKUP_DATA': [AuthConfig.ROLES['ADMIN']],
    'CAN_RESET_SYSTEM': [AuthConfig.ROLES['ADMIN']]
}

# Export config instance
auth_config = AuthConfig()