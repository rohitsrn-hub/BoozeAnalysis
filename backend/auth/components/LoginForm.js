/**
 * Modular Login Form Component
 * 
 * This component provides a complete login interface with customizable styling.
 * It can be used standalone or integrated into larger layouts.
 */

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { Lock, User, AlertCircle, Database } from 'lucide-react';
import { useAuth } from '../../contexts/SimpleAuthContext';
import { AUTH_CONFIG } from '../config';

const LoginForm = ({ 
  onLoginSuccess,
  showCreateAdmin = true,
  showAppInfo = true,
  className = "",
  cardClassName = "",
  title,
  description
}) => {
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const [showCreateAdminForm, setShowCreateAdminForm] = useState(false);
  
  const { login, createDefaultAdmin } = useAuth();

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setCredentials(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!credentials.username || !credentials.password) {
      return;
    }

    setLoading(true);
    const result = await login(credentials.username, credentials.password);
    
    if (result.success && onLoginSuccess) {
      onLoginSuccess();
    }
    
    setLoading(false);
  };

  const handleCreateDefaultAdmin = async () => {
    setLoading(true);
    const result = await createDefaultAdmin();
    if (result.success) {
      setShowCreateAdminForm(false);
      setCredentials({
        username: AUTH_CONFIG.DEFAULT_ADMIN.username,
        password: AUTH_CONFIG.DEFAULT_ADMIN.password
      });
    }
    setLoading(false);
  };

  return (
    <div className={`w-full max-w-md space-y-6 ${className}`}>
      {/* App Info Header */}
      {showAppInfo && (
        <div className="text-center space-y-2">
          <div className="w-16 h-16 bg-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <Database className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">{AUTH_CONFIG.APP_NAME}</h1>
          <p className="text-gray-600">{AUTH_CONFIG.APP_DESCRIPTION}</p>
        </div>
      )}

      {/* Login Form Card */}
      <Card className={cardClassName}>
        <CardHeader>
          <CardTitle className="text-center">
            {title || 'Login'}
          </CardTitle>
          <CardDescription className="text-center">
            {description || 'Enter your credentials to access the dashboard'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <div className="relative">
                <User className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                <Input
                  id="username"
                  name="username"
                  type="text"
                  placeholder="Enter your username"
                  value={credentials.username}
                  onChange={handleInputChange}
                  className="pl-10"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                <Input
                  id="password"
                  name="password"
                  type="password"
                  placeholder="Enter your password"
                  value={credentials.password}
                  onChange={handleInputChange}
                  className="pl-10"
                  required
                />
              </div>
            </div>

            <Button 
              type="submit" 
              className="w-full bg-indigo-600 hover:bg-indigo-700" 
              disabled={loading || !credentials.username || !credentials.password}
            >
              {loading ? (
                <div className="flex items-center space-x-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  <span>Signing in...</span>
                </div>
              ) : (
                'Sign In'
              )}
            </Button>
          </form>

          {/* Create Default Admin Section */}
          {showCreateAdmin && (
            <div className="pt-4 border-t">
              {!showCreateAdminForm ? (
                <div className="text-center">
                  <p className="text-sm text-gray-600 mb-2">First time setup?</p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowCreateAdminForm(true)}
                    className="text-indigo-600 border-indigo-600 hover:bg-indigo-50"
                  >
                    Create Default Admin
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      This will create a default admin user with username "{AUTH_CONFIG.DEFAULT_ADMIN.username}" 
                      and password "{AUTH_CONFIG.DEFAULT_ADMIN.password}". 
                      Please change the password immediately after first login.
                    </AlertDescription>
                  </Alert>
                  <div className="flex space-x-2">
                    <Button
                      onClick={handleCreateDefaultAdmin}
                      disabled={loading}
                      className="flex-1 bg-green-600 hover:bg-green-700"
                    >
                      {loading ? 'Creating...' : 'Create Admin'}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setShowCreateAdminForm(false)}
                      disabled={loading}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default LoginForm;