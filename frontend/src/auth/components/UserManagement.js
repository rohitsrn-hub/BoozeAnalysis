/**
 * User Management Component
 * 
 * Provides complete user management interface for administrators.
 * Includes user creation, activation/deactivation, and role management.
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Users, Plus, Shield, Eye, EyeOff, Edit, UserCheck, UserX, Calendar, Mail, KeyRound, Copy } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/SimpleAuthContext';
import { authAPI } from '../utils/api';
import { AUTH_CONFIG } from '../config';

const UserManagement = ({ className = "", user }) => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddUser, setShowAddUser] = useState(false);
  const [newUser, setNewUser] = useState({
    username: '',
    email: '',
    full_name: '',
    role: AUTH_CONFIG.ROLES.VIEWER,
    password: '',
    confirmPassword: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [showPasswordResetDialog, setShowPasswordResetDialog] = useState(false);
  const [resetPasswordData, setResetPasswordData] = useState(null);

  // Simple role check function
  const isAdmin = () => user && user.role === 'admin';
  
  // Register function
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

  // Fetch all users
  const fetchUsers = async () => {
    try {
      const users = await authAPI.getUsers();
      setUsers(users);
    } catch (error) {
      console.error('Error fetching users:', error);
      toast.error('Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin()) {
      fetchUsers();
    }
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setNewUser(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleRoleChange = (value) => {
    setNewUser(prev => ({
      ...prev,
      role: value
    }));
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    if (!newUser.username || !newUser.email || !newUser.full_name || !newUser.password || !newUser.confirmPassword) {
      toast.error('Please fill all required fields');
      return;
    }

    if (newUser.password !== newUser.confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    if (newUser.password.length < 6) {
      toast.error('Password must be at least 6 characters long');
      return;
    }

    const result = await register(newUser);
    if (result.success) {
      setNewUser({
        username: '',
        email: '',
        full_name: '',
        role: AUTH_CONFIG.ROLES.VIEWER,
        password: '',
        confirmPassword: ''
      });
      setShowPassword(false);
      setShowConfirmPassword(false);
      setShowAddUser(false);
      fetchUsers(); // Refresh user list
    }
  };

  const toggleUserStatus = async (userId, currentStatus) => {
    try {
      await authAPI.toggleUserStatus(userId);
      toast.success(`User ${currentStatus ? 'deactivated' : 'activated'} successfully`);
      fetchUsers(); // Refresh user list
    } catch (error) {
      console.error('Error toggling user status:', error);
      toast.error('Failed to update user status');
    }
  };

  const handleResetPassword = async (userId, username) => {
    if (!window.confirm(`Are you sure you want to reset password for ${username}?\n\nA new temporary password will be generated.`)) {
      return;
    }

    try {
      const response = await authAPI.resetUserPassword(userId);
      setResetPasswordData({
        username: response.username,
        temporary_password: response.temporary_password
      });
      setShowPasswordResetDialog(true);
      toast.success('Password reset successfully!');
    } catch (error) {
      console.error('Error resetting password:', error);
      toast.error('Failed to reset password');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Password copied to clipboard!');
  };

  const getRoleIcon = (role) => {
    switch (role) {
      case AUTH_CONFIG.ROLES.ADMIN:
        return <Shield className="w-4 h-4" />;
      case AUTH_CONFIG.ROLES.MANAGER:
        return <Edit className="w-4 h-4" />;
      case AUTH_CONFIG.ROLES.VIEWER:
        return <Eye className="w-4 h-4" />;
      default:
        return <Users className="w-4 h-4" />;
    }
  };

  const getRoleBadgeColor = (role) => {
    return AUTH_CONFIG.ROLE_COLORS[role] || 'bg-gray-100 text-gray-800';
  };

  if (!isAdmin()) {
    return (
      <Alert className={className}>
        <AlertDescription>
          You don't have permission to access user management.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">User Management</h2>
          <p className="text-gray-600">Manage user accounts and permissions</p>
        </div>
        
        <Dialog open={showAddUser} onOpenChange={setShowAddUser}>
          <DialogTrigger asChild>
            <Button className="bg-indigo-600 hover:bg-indigo-700">
              <Plus className="w-4 h-4 mr-2" />
              Add User
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>Add New User</DialogTitle>
              <DialogDescription>
                Create a new user account with specified role and permissions.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleAddUser} className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label htmlFor="username">Username *</Label>
                <Input
                  id="username"
                  name="username"
                  value={newUser.username}
                  onChange={handleInputChange}
                  placeholder="Enter username"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email *</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  value={newUser.email}
                  onChange={handleInputChange}
                  placeholder="Enter email address"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="full_name">Full Name *</Label>
                <Input
                  id="full_name"
                  name="full_name"
                  value={newUser.full_name}
                  onChange={handleInputChange}
                  placeholder="Enter full name"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="role">Role *</Label>
                <Select value={newUser.role} onValueChange={handleRoleChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select role" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={AUTH_CONFIG.ROLES.VIEWER}>
                      {AUTH_CONFIG.ROLE_LABELS[AUTH_CONFIG.ROLES.VIEWER]}
                    </SelectItem>
                    <SelectItem value={AUTH_CONFIG.ROLES.MANAGER}>
                      {AUTH_CONFIG.ROLE_LABELS[AUTH_CONFIG.ROLES.MANAGER]}
                    </SelectItem>
                    <SelectItem value={AUTH_CONFIG.ROLES.ADMIN}>
                      {AUTH_CONFIG.ROLE_LABELS[AUTH_CONFIG.ROLES.ADMIN]}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password *</Label>
                <div className="relative">
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    value={newUser.password}
                    onChange={handleInputChange}
                    placeholder="Enter password (min 6 characters)"
                    required
                    minLength={6}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm Password *</Label>
                <div className="relative">
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    value={newUser.confirmPassword}
                    onChange={handleInputChange}
                    placeholder="Re-enter password"
                    required
                    minLength={6}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-4">
                <Button 
                  type="button" 
                  variant="outline" 
                  onClick={() => setShowAddUser(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700">
                  Create User
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Users List */}
      {loading ? (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-2 text-gray-600">Loading users...</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {users.map((user) => (
            <Card key={user.id}>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center">
                      {getRoleIcon(user.role)}
                    </div>
                    <div>
                      <div className="flex items-center space-x-2">
                        <h3 className="font-semibold text-gray-900">{user.full_name}</h3>
                        <Badge className={getRoleBadgeColor(user.role)}>
                          {AUTH_CONFIG.ROLE_LABELS[user.role] || user.role.toUpperCase()}
                        </Badge>
                        {!user.is_active && (
                          <Badge variant="destructive">Inactive</Badge>
                        )}
                      </div>
                      <div className="flex items-center space-x-4 mt-1 text-sm text-gray-600">
                        <div className="flex items-center space-x-1">
                          <Users className="w-3 h-3" />
                          <span>{user.username}</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <Mail className="w-3 h-3" />
                          <span>{user.email}</span>
                        </div>
                        {user.last_login && (
                          <div className="flex items-center space-x-1">
                            <Calendar className="w-3 h-3" />
                            <span>Last login: {new Date(user.last_login).toLocaleDateString()}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleResetPassword(user.id, user.username)}
                      className="border-orange-500 text-orange-600 hover:bg-orange-50"
                    >
                      <KeyRound className="w-4 h-4 mr-1" />
                      Reset Password
                    </Button>
                    <Button
                      variant={user.is_active ? "destructive" : "default"}
                      size="sm"
                      onClick={() => toggleUserStatus(user.id, user.is_active)}
                    >
                      {user.is_active ? (
                        <>
                          <UserX className="w-4 h-4 mr-1" />
                          Deactivate
                        </>
                      ) : (
                        <>
                          <UserCheck className="w-4 h-4 mr-1" />
                          Activate
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
          
          {users.length === 0 && (
            <Card>
              <CardContent className="text-center py-12">
                <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">No Users Found</h3>
                <p className="text-gray-600">Start by adding the first user to the system.</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Reset Password Dialog */}
      <Dialog open={showPasswordResetDialog} onOpenChange={setShowPasswordResetDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center space-x-2">
              <KeyRound className="w-5 h-5 text-orange-600" />
              <span>Password Reset Successful</span>
            </DialogTitle>
            <DialogDescription>
              Share this temporary password with the user
            </DialogDescription>
          </DialogHeader>
          
          {resetPasswordData && (
            <div className="space-y-4 mt-4">
              <Alert className="bg-orange-50 border-orange-200">
                <AlertDescription>
                  <div className="space-y-3">
                    <div>
                      <p className="text-sm font-semibold text-orange-900">Username:</p>
                      <p className="text-base font-mono text-orange-700">{resetPasswordData.username}</p>
                    </div>
                    
                    <div>
                      <p className="text-sm font-semibold text-orange-900">Temporary Password:</p>
                      <div className="flex items-center space-x-2 mt-1">
                        <p className="text-base font-mono bg-white px-3 py-2 rounded border border-orange-300 flex-1 text-orange-700">
                          {resetPasswordData.temporary_password}
                        </p>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => copyToClipboard(resetPasswordData.temporary_password)}
                          className="border-orange-500 text-orange-600 hover:bg-orange-50"
                        >
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                    
                    <div className="pt-2 text-xs text-orange-800 space-y-1">
                      <p>⚠️ <strong>Important:</strong></p>
                      <ul className="ml-4 space-y-1">
                        <li>• Copy this password immediately - it won't be shown again</li>
                        <li>• Share it securely with the user</li>
                        <li>• User should change this password after logging in</li>
                      </ul>
                    </div>
                  </div>
                </AlertDescription>
              </Alert>
              
              <div className="flex justify-end">
                <Button
                  onClick={() => {
                    setShowPasswordResetDialog(false);
                    setResetPasswordData(null);
                  }}
                  className="bg-indigo-600 hover:bg-indigo-700"
                >
                  Done
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UserManagement;