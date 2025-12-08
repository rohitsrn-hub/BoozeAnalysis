import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const AuthContext = createContext();

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [authKey, setAuthKey] = useState(0); // Force re-renders

  // Setup axios interceptor for token
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common['Authorization'];
    }
  }, [token]);

  // Check if user is authenticated on app load
  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = localStorage.getItem('token');
      if (storedToken) {
        try {
          setToken(storedToken);
          axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
          
          const response = await axios.get(`${API}/auth/me`);
          setUser(response.data);
          console.log('User authenticated:', response.data);
        } catch (error) {
          console.error('Error validating token:', error);
          localStorage.removeItem('token');
          delete axios.defaults.headers.common['Authorization'];
          setToken(null);
        }
      }
      setLoading(false);
    };

    initializeAuth();
  }, []);

  const login = async (username, password, suppressToast = false) => {
    try {
      console.log('Attempting login with:', username);
      const response = await axios.post(`${API}/auth/login`, {
        username,
        password
      });

      const { access_token, user_info } = response.data;
      
      // Set token and user info synchronously
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      // Update both states together to trigger proper re-render
      setToken(access_token);
      setUser(user_info);
      setAuthKey(prev => prev + 1); // Force re-render
      
      console.log('Login successful:', user_info);
      console.log('Token stored:', access_token);
      console.log('Auth state updated, authKey incremented');
      
      if (!suppressToast) {
        toast.success(`Welcome back, ${user_info.full_name}!`);
      }
      
      return { success: true };
    } catch (error) {
      console.error('Login error:', error);
      const errorMessage = error.response?.data?.detail || 'Login failed. Please check your credentials.';
      
      if (!suppressToast) {
        toast.error(errorMessage);
      }
      
      return { success: false, error: errorMessage };
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    toast.success('Logged out successfully');
  };

  const register = async (userData) => {
    try {
      const response = await axios.post(`${API}/auth/register`, userData);
      toast.success(`User ${userData.username} created successfully`);
      return { success: true, data: response.data };
    } catch (error) {
      console.error('Registration error:', error);
      const errorMessage = error.response?.data?.detail || 'Registration failed';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  const createDefaultAdmin = async () => {
    try {
      const response = await axios.post(`${API}/auth/create-default-admin`);
      toast.success('Default admin created successfully');
      return { success: true, data: response.data };
    } catch (error) {
      console.error('Error creating default admin:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to create default admin';
      toast.error(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  // Role-based permission checks
  const hasPermission = (requiredRoles) => {
    if (!user || !user.role) return false;
    return requiredRoles.includes(user.role);
  };

  const canEdit = () => hasPermission(['admin', 'urc_clk']);
  const canViewOnly = () => hasPermission(['admin', 'urc_clk', 'dashboard_viewer']);
  const isAdmin = () => hasPermission(['admin']);

  const value = {
    user,
    token,
    loading,
    login,
    logout,
    register,
    createDefaultAdmin,
    hasPermission,
    canEdit,
    canViewOnly,
    isAdmin,
    isAuthenticated: !!user && !!token,
    authKey // Include authKey to force re-renders
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;