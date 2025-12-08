import React from 'react';
import { AuthProvider, useAuth } from './contexts/SimpleAuthContext';
import LoginPage from './auth/components/LoginPage';
import App from './App';

function AuthWrapper() {
  return (
    <AuthProvider>
      <AuthContent />
    </AuthProvider>
  );
}

function AuthContent() {
  const { user, logout } = useAuth();

  if (!user) {
    return <LoginPage />;
  }

  return <App user={user} onLogout={logout} />;
}

export default AuthWrapper;
