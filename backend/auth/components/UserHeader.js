/**
 * User Header Component
 * 
 * Displays user information, role badge, and logout functionality.
 * Can be integrated into any app header or navigation.
 */

import React from 'react';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '../../components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarInitials } from '../../components/ui/avatar';
import { LogOut, User, Settings, ChevronDown } from 'lucide-react';
import { useAuth } from '../../contexts/SimpleAuthContext';
import { AUTH_CONFIG } from '../config';

const UserHeader = ({ 
  showDropdown = true,
  onSettingsClick,
  onProfileClick,
  className = "",
  compact = false
}) => {
  const { user, logout } = useAuth();

  if (!user) return null;

  const getRoleBadgeColor = (role) => {
    return AUTH_CONFIG.ROLE_COLORS[role] || 'bg-gray-100 text-gray-800';
  };

  const getUserInitials = (fullName) => {
    return fullName
      .split(' ')
      .map(name => name.charAt(0))
      .join('')
      .toUpperCase()
      .substring(0, 2);
  };

  // Compact version (just avatar and role)
  if (compact) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <div className="w-8 h-8 bg-indigo-100 text-indigo-800 rounded-full flex items-center justify-center text-sm font-medium">
          {getUserInitials(user.full_name)}
        </div>
        <Badge className={`text-xs ${getRoleBadgeColor(user.role)}`}>
          {AUTH_CONFIG.ROLE_LABELS[user.role] || user.role.toUpperCase()}
        </Badge>
      </div>
    );
  }

  // Full version with dropdown
  if (showDropdown) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className={`flex items-center space-x-3 ${className}`}>
            <div className="text-right">
              <p className="text-sm font-medium text-gray-900">{user.full_name}</p>
              <p className="text-xs text-gray-500">{user.email}</p>
            </div>
            <div className="w-8 h-8 bg-indigo-100 text-indigo-800 rounded-full flex items-center justify-center text-sm font-medium">
              {getUserInitials(user.full_name)}
            </div>
            <ChevronDown className="w-4 h-4 text-gray-400" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>
            <div className="flex flex-col space-y-1">
              <p className="text-sm font-medium">{user.full_name}</p>
              <p className="text-xs text-gray-500">{user.email}</p>
              <Badge className={`text-xs w-fit ${getRoleBadgeColor(user.role)}`}>
                {AUTH_CONFIG.ROLE_LABELS[user.role] || user.role.toUpperCase()}
              </Badge>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          
          {onProfileClick && (
            <DropdownMenuItem onClick={onProfileClick}>
              <User className="w-4 h-4 mr-2" />
              Profile
            </DropdownMenuItem>
          )}
          
          {onSettingsClick && (
            <DropdownMenuItem onClick={onSettingsClick}>
              <Settings className="w-4 h-4 mr-2" />
              Settings
            </DropdownMenuItem>
          )}
          
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={logout} className="text-red-600">
            <LogOut className="w-4 h-4 mr-2" />
            Logout
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  // Simple version without dropdown
  return (
    <div className={`flex items-center space-x-4 ${className}`}>
      <div className="text-right">
        <p className="text-sm font-medium text-gray-900">{user.full_name}</p>
        <p className="text-xs text-gray-500 capitalize">
          {AUTH_CONFIG.ROLE_LABELS[user.role] || user.role.replace('_', ' ')}
        </p>
      </div>
      <Badge className={getRoleBadgeColor(user.role)}>
        {AUTH_CONFIG.ROLE_LABELS[user.role] || user.role.replace('_', ' ').toUpperCase()}
      </Badge>
      <Button variant="outline" size="sm" onClick={logout}>
        <LogOut className="w-4 h-4 mr-2" />
        Logout
      </Button>
    </div>
  );
};

export default UserHeader;