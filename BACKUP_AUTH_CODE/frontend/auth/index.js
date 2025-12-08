/**
 * Authentication Module - Main Export
 * 
 * This is the main entry point for the authentication module.
 * Import everything you need from this single file.
 */

// Configuration
export { AUTH_CONFIG, PERMISSIONS } from './config';

// Types (useful for documentation)
export * from './types';

// Hooks
export { useAuth, useAuthState, AuthProvider } from './hooks/useAuth';

// API utilities
export { authAPI, tokenUtils, permissionUtils } from './utils/api';

// Components
export { default as LoginForm } from './components/LoginForm';
export { default as LoginPage } from './components/LoginPage';
export { default as UserManagement } from './components/UserManagement';
export { default as UserHeader } from './components/UserHeader';
export { 
  AuthGuard, 
  AuthConditional, 
  withAuth, 
  PermissionGate 
} from './components/AuthGuard';

// Re-export default AuthProvider for convenience
export { AuthProvider as default } from './hooks/useAuth';