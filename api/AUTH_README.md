# JWT Authentication Configuration

## Overview
This API now supports JWT (JSON Web Token) authentication with role-based access control using the `UserType` enum:
- **STUDENT**: Regular student access
- **INSTRUCTOR**: Instructor/faculty access with additional privileges
- **ADMIN**: Full administrative access

## Environment Variables
Add these to your `.env` file:

```env
# JWT Configuration
JWT_SECRET_KEY=your-secret-key-change-in-production-use-openssl-rand-hex-32
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Existing configuration
EMBEDDING_DIM=384
```

## API Endpoints

### Authentication Endpoints

#### 1. Register
**POST** `/api/auth/register`

Create a new user account with a specific UserType.

```json
{
  "email": "student@university.edu",
  "password": "securepass123",
  "first_name": "John",
  "last_name": "Doe",
  "user_type": "student"
}
```

Response:
```json
{
  "user": {
    "id": 1,
    "email": "student@university.edu",
    "first_name": "John",
    "last_name": "Doe",
    "user_type": "student",
    "is_active": true
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### 2. Login
**POST** `/api/auth/login`

Authenticate with email and password.

```json
{
  "email": "student@university.edu",
  "password": "securepass123"
}
```

Response: Same as register (includes user info and JWT token)

#### 3. Get Current User
**GET** `/api/auth/me`

Get information about the currently authenticated user.

Headers:
```
Authorization: Bearer <your-jwt-token>
```

#### 4. Refresh Token
**POST** `/api/auth/refresh`

Get a new JWT token with updated expiration.

Headers:
```
Authorization: Bearer <your-jwt-token>
```

### Protected Endpoints

All search and regulations endpoints now require authentication:

- **GET** `/api/search` - Requires any authenticated user
- **GET** `/api/ask` - Requires any authenticated user  
- **GET** `/api/regulations/ask` - Requires any authenticated user
- **POST** `/api/regulations/chunk` - Requires INSTRUCTOR or ADMIN

## Using JWT Tokens

### In curl:
```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "student@university.edu", "password": "securepass123"}'

# Use token in protected endpoint
curl http://localhost:8000/api/search?q=programming \
  -H "Authorization: Bearer <your-token-here>"
```

### In JavaScript/TypeScript:
```typescript
// Login
const response = await fetch('http://localhost:8000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'student@university.edu',
    password: 'securepass123'
  })
});

const { access_token, user } = await response.json();

// Use token
const searchResponse = await fetch('http://localhost:8000/api/search?q=programming', {
  headers: { 'Authorization': `Bearer ${access_token}` }
});
```

## Role-Based Access Control

### Using Built-in Dependencies

```python
from fastapi import APIRouter, Depends
from database.models import User
from dependencies import (
    get_current_active_user,  # Any authenticated user
    require_student,           # Student, Instructor, or Admin
    require_instructor,        # Instructor or Admin only
    require_admin              # Admin only
)

router = APIRouter()

@router.get("/student-endpoint")
def student_route(user: User = Depends(require_student)):
    # Accessible by students, instructors, and admins
    return {"message": f"Hello {user.first_name}"}

@router.get("/instructor-endpoint")
def instructor_route(user: User = Depends(require_instructor)):
    # Accessible by instructors and admins only
    return {"message": f"Hello Professor {user.last_name}"}

@router.get("/admin-endpoint")
def admin_route(user: User = Depends(require_admin)):
    # Accessible by admins only
    return {"message": "Admin access granted"}
```

### Custom Role Requirements

```python
from dependencies import require_user_types
from database.models import UserType

@router.get("/custom-endpoint")
def custom_route(user: User = Depends(require_user_types([UserType.INSTRUCTOR, UserType.ADMIN]))):
    # Custom combination of allowed user types
    return {"message": "Access granted"}
```

## UserType in JWT Token

The JWT token includes the user's UserType in the payload:

```json
{
  "sub": "student@university.edu",
  "user_id": 1,
  "user_type": "student",
  "first_name": "John",
  "last_name": "Doe",
  "exp": 1234567890
}
```

## Security Notes

1. **Never commit your JWT_SECRET_KEY** to version control
2. Use a strong random secret key in production:
   ```bash
   openssl rand -hex 32
   ```
3. Access tokens expire after 30 minutes (configurable)
4. Store tokens securely on the client side (httpOnly cookies or secure storage)
5. Always use HTTPS in production
6. The password is hashed using bcrypt before storage

## Installation

Install the new dependencies:

```bash
cd api
pip install -r requirements.txt
```

## Testing

```bash
# Create a test user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@university.edu",
    "password": "password123",
    "first_name": "Test",
    "last_name": "User",
    "user_type": "student"
  }'
```
