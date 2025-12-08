/**
 * Complete Login Page Component
 * 
 * This provides a full-page login interface with role information.
 * Use this for standalone login pages.
 */

import React from 'react';
import { Card, CardContent } from '../../components/ui/card';
import LoginForm from './LoginForm';
import { useAuth } from '../../contexts/SimpleAuthContext';
import { AUTH_CONFIG } from '../config';

const LoginPage = ({ onLoginSuccess }) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        <LoginForm 
          onLoginSuccess={onLoginSuccess}
          showAppInfo={true}
          showCreateAdmin={false}
        />

        {/* User Roles Info */}
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="pt-6">
            <h3 className="font-semibold text-blue-900 mb-3">User Roles:</h3>
            <div className="space-y-2 text-sm text-blue-800">
              <div>
                <strong>{AUTH_CONFIG.ROLE_LABELS[AUTH_CONFIG.ROLES.ADMIN]}:</strong> Full access to all features
              </div>
              <div>
                <strong>{AUTH_CONFIG.ROLE_LABELS[AUTH_CONFIG.ROLES.MANAGER]}:</strong> Can update data and view analytics
              </div>
              <div>
                <strong>{AUTH_CONFIG.ROLE_LABELS[AUTH_CONFIG.ROLES.VIEWER]}:</strong> Read-only access to reports
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default LoginPage;