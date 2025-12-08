/**
 * Authentication Module Configuration
 * 
 * This file contains all configurable settings for the authentication module.
 * Customize these values to match your project requirements.
 */

export const AUTH_CONFIG = {
  // API Configuration
  API_BASE_URL: process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001',
  API_PREFIX: '/api',
  
  // Token Configuration
  TOKEN_STORAGE_KEY: 'token',
  TOKEN_EXPIRY_MINUTES: 480, // 8 hours
  
  // Available User Roles
  ROLES: {
    ADMIN: 'admin',
    MANAGER: 'urc_clk', // You can rename this to suit your project
    VIEWER: 'dashboard_viewer'
  },
  
  // Role Display Names
  ROLE_LABELS: {
    admin: 'Administrator',
    urc_clk: 'Manager', // Customize as needed
    dashboard_viewer: 'Viewer'
  },
  
  // Role Colors for Badges
  ROLE_COLORS: {
    admin: 'bg-red-100 text-red-800',
    urc_clk: 'bg-blue-100 text-blue-800',
    dashboard_viewer: 'bg-green-100 text-green-800'
  },
  
  // Default Admin Credentials (for initial setup)
  DEFAULT_ADMIN: {
    username: 'admin',
    password: 'admin123',
    email: 'admin@example.com',
    full_name: 'System Administrator'
  },
  
  // UI Configuration
  APP_NAME: 'Liquor Sales Dashboard', // Customize for your app
  APP_DESCRIPTION: 'Analytics & Inventory Management', // Customize description
  
  // Routes (if using React Router)
  ROUTES: {
    LOGIN: '/login',
    DASHBOARD: '/',
    USERS: '/users'
  },
  
  // Feature Flags
  FEATURES: {
    REMEMBER_ME: false, // Not implemented in current version
    PASSWORD_RESET: false, // Not implemented in current version
    EMAIL_VERIFICATION: false, // Not implemented in current version
    MULTI_FACTOR_AUTH: false // Not implemented in current version
  }
};

// Permission Matrices - Define what each role can do
export const PERMISSIONS = {
  // Data Management
  CAN_UPLOAD_DATA: ['admin', 'urc_clk'],
  CAN_DELETE_DATA: ['admin'],
  CAN_EDIT_DATA: ['admin', 'urc_clk'],
  CAN_VIEW_DATA: ['admin', 'urc_clk', 'dashboard_viewer'],
  
  // User Management
  CAN_CREATE_USERS: ['admin'],
  CAN_MANAGE_USERS: ['admin'],
  CAN_VIEW_USERS: ['admin'],
  
  // Reports & Analytics
  CAN_VIEW_ANALYTICS: ['admin', 'urc_clk', 'dashboard_viewer'],
  CAN_EXPORT_REPORTS: ['admin', 'urc_clk', 'dashboard_viewer'],
  CAN_GENERATE_REPORTS: ['admin', 'urc_clk'],
  
  // System Administration
  CAN_ACCESS_SETTINGS: ['admin'],
  CAN_BACKUP_DATA: ['admin'],
  CAN_RESET_SYSTEM: ['admin']
};

export default AUTH_CONFIG;