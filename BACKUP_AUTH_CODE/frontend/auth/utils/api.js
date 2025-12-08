/**
 * Authentication API Utilities
 * 
 * This module handles all authentication-related API calls.
 * It's framework-agnostic and can be used with any HTTP client.
 */

import axios from 'axios';
import { AUTH_CONFIG } from '../config';

// Create axios instance with base configuration
const createApiClient = (baseURL = AUTH_CONFIG.API_BASE_URL) => {
  const client = axios.create({
    baseURL: `${baseURL}${AUTH_CONFIG.API_PREFIX}`,
    timeout: 10000,
    headers: {
      'Content-Type': 'application/json'
    }
  });

  // Request interceptor to add auth token
  client.interceptors.request.use(
    (config) => {
      const token = localStorage.getItem(AUTH_CONFIG.TOKEN_STORAGE_KEY);
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  // Response interceptor to handle auth errors
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        // Token expired or invalid
        localStorage.removeItem(AUTH_CONFIG.TOKEN_STORAGE_KEY);
        delete axios.defaults.headers.common['Authorization'];
        
        // Redirect to login or emit event
        window.dispatchEvent(new CustomEvent('auth:logout'));
      }
      return Promise.reject(error);
    }
  );

  return client;
};

// Default API client
const api = createApiClient();

/**
 * Authentication API functions
 */
export const authAPI = {
  /**
   * Login user
   * @param {string} username - Username
   * @param {string} password - Password
   * @returns {Promise<AuthToken>} Authentication token and user info
   */
  login: async (username, password) => {
    const response = await api.post('/auth/login', { username, password });
    return response.data;
  },

  /**
   * Register new user (Admin only)
   * @param {UserCreate} userData - User registration data
   * @returns {Promise<User>} Created user information
   */
  register: async (userData) => {
    const response = await api.post('/auth/register', userData);
    return response.data;
  },

  /**
   * Get current user information
   * @returns {Promise<User>} Current user data
   */
  getCurrentUser: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },

  /**
   * Get all users (Admin only)
   * @returns {Promise<User[]>} List of all users
   */
  getUsers: async () => {
    const response = await api.get('/auth/users');
    return response.data;
  },

  /**
   * Toggle user active status (Admin only)
   * @param {string} userId - User ID to toggle
   * @returns {Promise<User>} Updated user data
   */
  toggleUserStatus: async (userId) => {
    const response = await api.put(`/auth/users/${userId}/toggle`);
    return response.data;
  },

  /**
   * Reset user password (Admin only)
   * @param {string} userId - User ID to reset password
   * @returns {Promise<Object>} Temporary password and username
   */
  resetUserPassword: async (userId) => {
    const response = await api.post(`/auth/users/${userId}/reset-password`);
    return response.data;
  },

  /**
   * Create default admin user
   * @returns {Promise<Object>} Default admin creation result
   */
  createDefaultAdmin: async () => {
    const response = await api.post('/auth/create-default-admin');
    return response.data;
  },

  /**
   * Logout (client-side token cleanup)
   */
  logout: () => {
    localStorage.removeItem(AUTH_CONFIG.TOKEN_STORAGE_KEY);
    delete axios.defaults.headers.common['Authorization'];
  }
};

/**
 * Token management utilities
 */
export const tokenUtils = {
  /**
   * Get stored token
   * @returns {string|null} Stored JWT token
   */
  getToken: () => localStorage.getItem(AUTH_CONFIG.TOKEN_STORAGE_KEY),

  /**
   * Set token in storage and axios headers
   * @param {string} token - JWT token to store
   */
  setToken: (token) => {
    localStorage.setItem(AUTH_CONFIG.TOKEN_STORAGE_KEY, token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  },

  /**
   * Remove token from storage and axios headers
   */
  removeToken: () => {
    localStorage.removeItem(AUTH_CONFIG.TOKEN_STORAGE_KEY);
    delete axios.defaults.headers.common['Authorization'];
  },

  /**
   * Check if token exists
   * @returns {boolean} Whether token exists in storage
   */
  hasToken: () => !!localStorage.getItem(AUTH_CONFIG.TOKEN_STORAGE_KEY)
};

/**
 * Permission utilities
 */
export const permissionUtils = {
  /**
   * Check if user has required permissions
   * @param {User} user - User object
   * @param {string[]} requiredRoles - Required roles
   * @returns {boolean} Whether user has permission
   */
  hasPermission: (user, requiredRoles) => {
    if (!user || !user.role) return false;
    return requiredRoles.includes(user.role);
  },

  /**
   * Check if user can edit data
   * @param {User} user - User object
   * @returns {boolean} Whether user can edit
   */
  canEdit: (user) => {
    return permissionUtils.hasPermission(user, [AUTH_CONFIG.ROLES.ADMIN, AUTH_CONFIG.ROLES.MANAGER]);
  },

  /**
   * Check if user can view data
   * @param {User} user - User object
   * @returns {boolean} Whether user can view
   */
  canView: (user) => {
    return permissionUtils.hasPermission(user, [
      AUTH_CONFIG.ROLES.ADMIN, 
      AUTH_CONFIG.ROLES.MANAGER, 
      AUTH_CONFIG.ROLES.VIEWER
    ]);
  },

  /**
   * Check if user is admin
   * @param {User} user - User object
   * @returns {boolean} Whether user is admin
   */
  isAdmin: (user) => {
    return permissionUtils.hasPermission(user, [AUTH_CONFIG.ROLES.ADMIN]);
  }
};

export default api;