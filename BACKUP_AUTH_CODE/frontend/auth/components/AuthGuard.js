/**
 * Authentication Guard Component
 * 
 * Provides route protection and conditional rendering based on authentication state.
 * Can be used to protect entire pages or individual components.
 */

import React from 'react';
import { useAuth } from '../hooks/useAuth';
import LoginPage from './LoginPage';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { Shield, AlertTriangle } from 'lucide-react';

/**
 * Protects routes/components that require authentication
 */
export const AuthGuard = ({ 
  children, 
  fallback, 
  showLoginPage = true,
  loadingComponent,
  requiredRoles = []
}) => {
  const { isAuthenticated, loading, hasPermission, user } = useAuth();

  // Show loading state
  if (loading) {
    if (loadingComponent) return loadingComponent;
    
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // User not authenticated
  if (!isAuthenticated) {
    if (fallback) return fallback;
    if (showLoginPage) return <LoginPage />;
    
    return (
      <Alert>
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          You must be logged in to access this content.
        </AlertDescription>
      </Alert>
    );
  }

  // Check role-based permissions
  if (requiredRoles.length > 0 && !hasPermission(requiredRoles)) {
    return (
      <Alert className="border-red-200 bg-red-50">
        <Shield className="h-4 w-4 text-red-600" />
        <AlertDescription className="text-red-800">
          You don't have permission to access this content. 
          Required roles: {requiredRoles.join(', ')}
        </AlertDescription>
      </Alert>
    );
  }

  return children;
};

/**
 * Conditional component renderer based on authentication
 */
export const AuthConditional = ({ 
  authenticated, 
  unauthenticated,
  loading: loadingComponent,
  roles = []
}) => {
  const { isAuthenticated, loading, hasPermission } = useAuth();

  if (loading && loadingComponent) {
    return loadingComponent;
  }

  if (!isAuthenticated) {
    return unauthenticated || null;
  }

  // Check role permissions if specified
  if (roles.length > 0 && !hasPermission(roles)) {
    return null;
  }

  return authenticated || null;
};

/**
 * Higher-order component for route protection
 */
export const withAuth = (Component, options = {}) => {
  const {
    requiredRoles = [],
    fallback,
    showLoginPage = true,
    loadingComponent
  } = options;

  return function AuthenticatedComponent(props) {
    return (
      <AuthGuard
        requiredRoles={requiredRoles}
        fallback={fallback}
        showLoginPage={showLoginPage}
        loadingComponent={loadingComponent}
      >
        <Component {...props} />
      </AuthGuard>
    );
  };
};

/**
 * Permission-based component renderer
 */
export const PermissionGate = ({ 
  roles = [], 
  children, 
  fallback,
  operator = 'OR' // 'OR' or 'AND'
}) => {
  const { hasPermission, user } = useAuth();

  if (!user) {
    return fallback || null;
  }

  let hasAccess = false;

  if (operator === 'AND') {
    // User must have ALL specified roles
    hasAccess = roles.every(role => hasPermission([role]));
  } else {
    // User must have ANY of the specified roles (OR)
    hasAccess = hasPermission(roles);
  }

  if (!hasAccess) {
    return fallback || null;
  }

  return children;
};

export default AuthGuard;