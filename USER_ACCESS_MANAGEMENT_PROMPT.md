# Complete User Access Management System - Implementation Prompt

Use this prompt to create a complete user access management system in any FastAPI + React + MongoDB application:

---

## PROMPT:

I need you to implement a complete user access management system with role-based access control (RBAC) for my FastAPI + React + MongoDB application.

### **System Requirements:**

#### **1. Three User Roles with Permissions:**

Create three distinct user roles with the following permission levels:

**Administrator (admin):**
- Full access to all features
- Can create, view, edit, activate/deactivate, and delete users
- Can access user management dashboard
- Can perform all data operations (upload, edit, delete, backup, reset)
- Can generate and export all reports

**Manager (urc_clk):**
- Can upload and edit data
- Can add brands and update rates
- Can view analytics and dashboard
- Can generate and export reports
- **Cannot** access user management
- **Cannot** perform system backups or resets

**Viewer (dashboard_viewer):**
- Read-only access to dashboard and analytics
- Can view all data and charts
- Can export reports (Excel/PDF)
- **Cannot** upload or edit data
- **Cannot** access user management
- **Cannot** add brands or update rates

#### **2. Backend Implementation (FastAPI):**

Create a complete authentication module with the following structure:

**File Structure:**
```
/backend/auth/
├── __init__.py
├── config.py          # Configuration, roles, and permissions
├── models.py          # Pydantic models
├── routes.py          # API endpoints
└── utils.py           # Helper functions (JWT, password hashing)
```

**Required Backend Endpoints:**

1. `POST /api/auth/login` - User login with JWT token generation
2. `POST /api/auth/register` - Create new user (admin only)
3. `GET /api/auth/me` - Get current user info
4. `GET /api/auth/users` - List all users (admin only)
5. `PUT /api/auth/users/{user_id}` - Update user (admin only)
6. `PUT /api/auth/users/{user_id}/toggle` - Activate/deactivate user (admin only)
7. `DELETE /api/auth/users/{user_id}` - Delete user (admin only)
8. `POST /api/auth/change-password` - Change own password (all users)
9. `POST /api/auth/create-default-admin` - Create default admin (API only, not in UI)

**Authentication Features:**
- JWT token-based authentication
- Password hashing with bcrypt
- Token expiry: 8 hours (480 minutes)
- Role-based middleware for route protection
- Permission matrix enforcement

**Models Required:**
- User (complete model with id, username, email, full_name, role, hashed_password, is_active, created_at, last_login)
- UserCreate (registration)
- UserLogin (login)
- Token (JWT response)
- UserResponse (safe response without password)
- UserUpdate
- PasswordChange

#### **3. Frontend Implementation (React):**

**File Structure:**
```
/frontend/src/auth/
├── components/
│   ├── LoginPage.js           # Full-page login interface
│   ├── LoginForm.js           # Reusable login form
│   ├── UserManagement.js      # User management dashboard
│   └── AuthGuard.js           # Protected route wrapper
├── contexts/
│   └── SimpleAuthContext.js   # Auth context provider
├── hooks/
│   └── useAuth.js             # Auth hook
├── utils/
│   └── api.js                 # API helper functions
├── config.js                  # Frontend auth config
└── types.js                   # TypeScript types (if using TS)
```

**Required Components:**

**1. LoginPage Component:**
- Clean, professional login interface
- Username and password fields
- Sign in button with loading state
- Error handling with user-friendly messages
- User roles information display
- NO "Create Default Admin" button (this should only be accessible via API)

**2. UserManagement Component:**
- Visible only to admin users
- User creation form with:
  - Username, email, full name, role selector
  - Password and confirm password fields
  - Show/hide password toggle (eye icon)
  - Form validation (password min 6 chars, passwords match)
- User list display showing:
  - User avatar/icon
  - Full name, username, email
  - Role badge with color coding
  - Active/inactive status
  - Last login date
  - Activate/Deactivate button
- Beautiful card-based layout with proper spacing

**3. Change Password Dialog:**
- Accessible to ALL authenticated users
- Button in header near user info
- Dialog form with:
  - Current password field
  - New password field (min 6 characters)
  - Confirm new password field
  - Show/hide toggle for all password fields
  - Password validation (match check, length check)
- Success/error toast notifications

**4. User Header Display:**
- Show logged-in user's name and role
- Change Password button
- Logout button
- Styled with gradient background and proper colors

**5. Role-Based UI Control:**
Implement permission-based button visibility throughout the app:

**For All Roles:**
- View dashboard and analytics
- Refresh button
- Help button
- History tab
- Change Password button
- Logout button

**For Admin Only:**
- Users tab
- All data management buttons
- Backups button
- Reset Stock button
- Full Monthly upload
- Add Brand
- Update Rates

**For Manager (urc_clk):**
- Upload Today's Data
- Full Monthly upload
- Add Brand
- Update Rates
- Export Excel
- Generate PDF

**For Viewer:**
- Export Excel
- Generate PDF

#### **4. Authentication Flow:**

**Initial Setup:**
1. First-time users must call API endpoint to create default admin (backend API only, not UI button)
2. Default admin: username="admin", password="admin"
3. Admin should change password immediately after first login

**Login Flow:**
1. User enters credentials on LoginPage
2. Frontend calls `/api/auth/login`
3. Backend validates credentials and returns JWT token + user info
4. Token stored in localStorage
5. User redirected to dashboard
6. User info displayed in header with role

**Protected Routes:**
1. All routes except login require valid JWT token
2. Token included in Authorization header for all API calls
3. Backend validates token and role permissions
4. Invalid token redirects to login page

**User Management Flow (Admin Only):**
1. Admin clicks "Users" tab in dashboard
2. UserManagement component loads user list
3. Admin clicks "Add User" button
4. Modal opens with user creation form
5. Admin fills form (username, email, name, role, password, confirm password)
6. Frontend validates (password match, length check)
7. Backend creates user with hashed password
8. User list refreshes with new user

**Change Password Flow (All Users):**
1. User clicks "Change Password" button in header
2. Dialog opens with password form
3. User enters current password, new password, confirm new password
4. Frontend validates passwords match and meet requirements
5. Backend verifies current password and updates to new password
6. Success message shown, dialog closes

#### **5. Security Requirements:**

**Password Security:**
- Minimum 6 characters (configurable)
- Hashed with bcrypt before storage
- Never returned in API responses
- Requires confirmation on creation/change

**JWT Security:**
- Signed with secret key (store in .env)
- 8-hour expiry
- Includes username and role
- Validated on every protected route

**Role Security:**
- Permission matrix defined in config
- Enforced on both backend (routes) and frontend (UI)
- Admin cannot delete own account
- Inactive users cannot login

#### **6. UI/UX Requirements:**

**Design Style:**
- Modern, clean interface
- Use Tailwind CSS for styling
- Shadcn UI components (Card, Button, Input, Dialog, Badge, etc.)
- Color-coded role badges:
  - Admin: Red (bg-red-100 text-red-800)
  - Manager: Blue (bg-blue-100 text-blue-800)
  - Viewer: Green (bg-green-100 text-green-800)

**Icons (using lucide-react):**
- Users icon for user management
- Shield icon for admin role
- Edit icon for manager role
- Eye icon for viewer role and show/hide password
- EyeOff icon for hide password
- Key icon for change password
- UserCheck/UserX icons for activate/deactivate
- Lock icon for password fields

**Notifications:**
- Use toast notifications (sonner library)
- Success: Green toast for successful actions
- Error: Red toast for errors
- Info: Blue toast for information

**Form Validation:**
- Real-time validation feedback
- Clear error messages
- Disable submit button when form invalid
- Loading states on all async actions

#### **7. Integration with Existing App:**

**In main App.js:**
1. Accept `user` and `onLogout` props from AuthWrapper
2. Add helper functions:
   ```javascript
   const hasPermission = (permission) => {
     if (!user || !user.role) return false;
     const allowedRoles = PERMISSIONS[permission] || [];
     return allowedRoles.includes(user.role);
   };
   
   const isAdmin = () => user && user.role === 'admin';
   ```
3. Wrap all action buttons with permission checks:
   ```javascript
   {hasPermission('CAN_UPLOAD_DATA') && (
     <Button>Upload Data</Button>
   )}
   ```
4. Add Users tab (admin only):
   ```javascript
   {isAdmin() && (
     <TabsTrigger value="user-management">Users</TabsTrigger>
   )}
   ```
5. Add user header display with Change Password button
6. Import and use UserManagement component

**In index.js:**
1. Wrap App with AuthProvider
2. Use AuthWrapper to control login/dashboard display

#### **8. Testing Requirements:**

**Backend Testing:**
- Test all authentication endpoints
- Test role-based access control
- Test JWT token generation and validation
- Test password hashing and verification
- Test user activation/deactivation
- Test permission enforcement (403 Forbidden for unauthorized)

**Frontend Testing:**
- Test login flow
- Test user creation by admin
- Test role-based button visibility for all roles
- Test change password functionality
- Test logout functionality
- Test inactive user cannot login
- Test UI updates after user actions

#### **9. Configuration:**

**Backend .env Variables:**
```
JWT_SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=480
MONGO_URL=your-mongodb-connection-string
```

**Frontend .env Variables:**
```
REACT_APP_BACKEND_URL=your-backend-url
```

#### **10. Permissions Matrix:**

Define in `backend/auth/config.py`:
```python
PERMISSIONS = {
    'CAN_UPLOAD_DATA': ['admin', 'urc_clk'],
    'CAN_DELETE_DATA': ['admin'],
    'CAN_EDIT_DATA': ['admin', 'urc_clk'],
    'CAN_VIEW_DATA': ['admin', 'urc_clk', 'dashboard_viewer'],
    'CAN_CREATE_USERS': ['admin'],
    'CAN_MANAGE_USERS': ['admin'],
    'CAN_VIEW_USERS': ['admin'],
    'CAN_VIEW_ANALYTICS': ['admin', 'urc_clk', 'dashboard_viewer'],
    'CAN_EXPORT_REPORTS': ['admin', 'urc_clk', 'dashboard_viewer'],
    'CAN_GENERATE_REPORTS': ['admin', 'urc_clk'],
    'CAN_ACCESS_SETTINGS': ['admin'],
    'CAN_BACKUP_DATA': ['admin'],
    'CAN_RESET_SYSTEM': ['admin']
}
```

#### **11. Additional Features:**

**Password Fields:**
- Must have show/hide password toggle (eye icon)
- Toggle each field independently
- Password confirmation on creation and change
- Visual feedback for password requirements

**User Status Management:**
- Admin can activate/deactivate users
- Inactive users cannot login (backend blocks)
- Status clearly shown in user list with badge
- Toggle button changes based on current status

**Error Handling:**
- Proper error messages from backend
- User-friendly error display in frontend
- Handle token expiry gracefully (redirect to login)
- Handle network errors
- Form validation before submission

---

## DELIVERABLES:

1. Complete backend authentication module (`/backend/auth/`)
2. Complete frontend authentication module (`/frontend/src/auth/`)
3. Integration with main App.js
4. User management dashboard (admin only)
5. Change password feature (all users)
6. Role-based UI control throughout app
7. Professional login page
8. User header with info and controls
9. Working permission enforcement on backend and frontend
10. Password show/hide toggles on all password fields
11. Password confirmation on user creation and password change

---

## SUCCESS CRITERIA:

✅ Admin can create users with all three roles
✅ All three roles can login successfully
✅ Manager sees limited buttons (no admin features)
✅ Viewer sees minimal buttons (read-only)
✅ All users can change their own password
✅ Password fields have show/hide toggles
✅ User creation requires password confirmation
✅ Admin can view, activate, deactivate users
✅ Inactive users cannot login
✅ Permission checks work on both backend (403) and frontend (hidden buttons)
✅ JWT tokens work for 8 hours then expire
✅ Beautiful, professional UI with proper styling
✅ All forms have validation and error handling
✅ No "Create Default Admin" button on login page (API only)

---

**Implementation Note:** This is a production-ready user access management system. All components are modular, reusable, and follow best practices for security and UX. The system is fully tested and working in a real application.
