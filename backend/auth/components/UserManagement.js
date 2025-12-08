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
import { Users, Plus, Shield, Eye, Edit, UserCheck, UserX, Calendar, Mail } from 'lucide-react';
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
    password: ''
  });

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
    if (!newUser.username || !newUser.email || !newUser.full_name || !newUser.password) {
      toast.error('Please fill all required fields');
      return;
    }

    const result = await register(newUser);
    if (result.success) {
      setNewUser({
        username: '',
        email: '',
        full_name: '',
        role: AUTH_CONFIG.ROLES.VIEWER,
        password: ''
      });
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
                <Input
                  id="password"
                  name="password"
                  type="password"
                  value={newUser.password}
                  onChange={handleInputChange}
                  placeholder="Enter password"
                  required
                />
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
    </div>
  );
};

export default UserManagement;