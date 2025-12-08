/**
 * Authentication Hook
 * 
 * This is the main authentication hook that manages user state and authentication logic.
 * It can be used independently or with the AuthProvider context.
 */

import { useState, useEffect, createContext, useContext } from 'react';
import { authAPI, tokenUtils, permissionUtils } from '../utils/api';
import { AUTH_CONFIG, PERMISSIONS } from '../config';
import { toast } from 'sonner';

// Create Auth Context
const AuthContext = createContext();

/**
 * Custom hook to use auth context
 * @returns {AuthContextValue} Authentication context value
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

/**
 * Standalone authentication hook (can be used without provider)
 * @returns {AuthContextValue} Authentication state and functions
 */
export const useAuthState = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setTokenState] = useState(tokenUtils.getToken());

  // Initialize authentication state
  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = tokenUtils.getToken();
      if (storedToken) {
        try {
          tokenUtils.setToken(storedToken);
          const userData = await authAPI.getCurrentUser();
          setUser(userData);
          setTokenState(storedToken);
        } catch (error) {
          console.error('Error validating token:', error);
          tokenUtils.removeToken();
          setTokenState(null);
        }
      }
      setLoading(false);
    };

    initializeAuth();
  }, []);

  // Listen for logout events
  useEffect(() => {
    const handleLogout = () => {
      setUser(null);
      setTokenState(null);
    };

    window.addEventListener('auth:logout', handleLogout);
    return () => window.removeEventListener('auth:logout', handleLogout);
  }, []);

  /**
   * Login user
   * @param {string} username - Username
   * @param {string} password - Password
   * @returns {Promise<{success: boolean, error?: string}>}
   */
  const login = async (username, password) => {
    try {
      const response = await authAPI.login(username, password);
      const { access_token, user_info } = response;
      
      setTokenState(access_token);
      setUser(user_info);
      tokenUtils.setToken(access_token);
      
      toast.success(`Welcome back, ${user_info.full_name}!`);
      return { success: true };
    } catch (error) {
      console.error('Login error:', error);
      const errorMessage = error.response?.data?.detail || 'Login failed';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  /**
   * Logout user
   */
  const logout = () => {
    setUser(null);
    setTokenState(null);
    tokenUtils.removeToken();
    toast.success('Logged out successfully');
  };

  /**
   * Register new user (Admin only)
   * @param {UserCreate} userData - User data
   * @returns {Promise<{success: boolean, data?: User, error?: string}>}
   */
  const register = async (userData) => {
    try {
      const response = await authAPI.register(userData);
      toast.success(`User ${userData.username} created successfully`);
      return { success: true, data: response };
    } catch (error) {
      console.error('Registration error:', error);
      const errorMessage = error.response?.data?.detail || 'Registration failed';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  /**
   * Create default admin user
   * @returns {Promise<{success: boolean, data?: Object, error?: string}>}
   */
  const createDefaultAdmin = async () => {
    try {
      const response = await authAPI.createDefaultAdmin();
      toast.success('Default admin created successfully');
      return { success: true, data: response };
    } catch (error) {
      console.error('Error creating default admin:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to create default admin';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  // Permission checking functions
  const hasPermission = (requiredRoles) => permissionUtils.hasPermission(user, requiredRoles);
  const canEdit = () => permissionUtils.canEdit(user);
  const canView = () => permissionUtils.canView(user);
  const isAdmin = () => permissionUtils.isAdmin(user);

  /**
   * Check specific permission by name
   * @param {string} permissionName - Permission name from PERMISSIONS config
   * @returns {boolean} Whether user has the permission
   */
  const hasSpecificPermission = (permissionName) => {
    const requiredRoles = PERMISSIONS[permissionName];
    if (!requiredRoles) return false;
    return hasPermission(requiredRoles);
  };

  return {
    // State
    user,
    token,
    loading,
    isAuthenticated: !!user && !!token,

    // Actions
    login,
    logout,
    register,
    createDefaultAdmin,

    // Permissions
    hasPermission,
    hasSpecificPermission,
    canEdit,
    canView,
    isAdmin
  };
};

/**
 * Authentication Provider Component
 */
export const AuthProvider = ({ children }) => {
  const authState = useAuthState();

  return (
    <AuthContext.Provider value={authState}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;