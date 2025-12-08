/**
 * Authentication Module Type Definitions
 * 
 * This file contains all type definitions and interfaces for the auth module.
 * Useful for both TypeScript projects and as documentation for JavaScript projects.
 */

/**
 * User Object Structure
 * @typedef {Object} User
 * @property {string} id - Unique user identifier
 * @property {string} username - User's login username
 * @property {string} email - User's email address
 * @property {string} full_name - User's display name
 * @property {string} role - User's role (admin, urc_clk, dashboard_viewer)
 * @property {boolean} is_active - Whether user account is active
 * @property {string} created_at - Account creation timestamp
 * @property {string|null} last_login - Last login timestamp
 */

/**
 * User Creation Request
 * @typedef {Object} UserCreate
 * @property {string} username - Desired username
 * @property {string} email - User's email address
 * @property {string} full_name - User's full name
 * @property {string} role - Assigned role
 * @property {string} password - User's password
 */

/**
 * Login Request
 * @typedef {Object} LoginRequest
 * @property {string} username - Username or email
 * @property {string} password - User's password
 */

/**
 * Authentication Token Response
 * @typedef {Object} AuthToken
 * @property {string} access_token - JWT access token
 * @property {string} token_type - Token type (usually "bearer")
 * @property {User} user_info - User information object
 */

/**
 * Authentication Context Value
 * @typedef {Object} AuthContextValue
 * @property {User|null} user - Current authenticated user
 * @property {string|null} token - Current JWT token
 * @property {boolean} loading - Whether auth is loading
 * @property {boolean} isAuthenticated - Whether user is logged in
 * @property {Function} login - Login function
 * @property {Function} logout - Logout function  
 * @property {Function} register - User registration function
 * @property {Function} createDefaultAdmin - Create default admin function
 * @property {Function} hasPermission - Check user permissions
 * @property {Function} canEdit - Check edit permissions
 * @property {Function} canViewOnly - Check view permissions
 * @property {Function} isAdmin - Check admin permissions
 */

/**
 * API Response Structure
 * @typedef {Object} ApiResponse
 * @property {boolean} success - Whether operation was successful
 * @property {*} data - Response data
 * @property {string} error - Error message if failed
 */

// Export empty object to make this a valid module
export default {};