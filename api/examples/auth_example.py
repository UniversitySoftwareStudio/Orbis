"""
Example demonstrating JWT authentication with UserType in FastAPI

This example shows how to:
1. Register users with different UserTypes (STUDENT, INSTRUCTOR, ADMIN)
2. Login and receive JWT tokens
3. Use JWT tokens to access protected endpoints
4. Implement role-based access control
"""

import requests
import json

BASE_URL = "http://localhost:8000/api"


def register_user(email: str, password: str, first_name: str, last_name: str, user_type: str):
    """Register a new user with UserType"""
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
            "user_type": user_type  # "student", "instructor", or "admin"
        }
    )
    return response.json()


def login(email: str, password: str):
    """Login and get JWT token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": email,
            "password": password
        }
    )
    return response.json()


def get_current_user(token: str):
    """Get current user info using JWT token"""
    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.json()


def search_courses(token: str, query: str):
    """Search courses (requires authentication)"""
    response = requests.get(
        f"{BASE_URL}/search",
        params={"q": query, "limit": 5},
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.json()


def ask_question(token: str, question: str):
    """Ask a question about regulations (requires authentication)"""
    response = requests.get(
        f"{BASE_URL}/regulations/ask",
        params={"q": question},
        headers={"Authorization": f"Bearer {token}"},
        stream=True
    )
    return response


def main():
    print("=" * 60)
    print("JWT Authentication with UserType Demo")
    print("=" * 60)
    
    # 1. Register a student
    print("\n1. Registering a STUDENT...")
    student_data = register_user(
        email="john.doe@university.edu",
        password="student123",
        first_name="John",
        last_name="Doe",
        user_type="student"
    )
    print(f"✓ Student registered: {student_data['user']['email']}")
    print(f"  User Type: {student_data['user']['user_type']}")
    student_token = student_data['access_token']
    
    # 2. Register an instructor
    print("\n2. Registering an INSTRUCTOR...")
    instructor_data = register_user(
        email="prof.smith@university.edu",
        password="instructor123",
        first_name="Jane",
        last_name="Smith",
        user_type="instructor"
    )
    print(f"✓ Instructor registered: {instructor_data['user']['email']}")
    print(f"  User Type: {instructor_data['user']['user_type']}")
    instructor_token = instructor_data['access_token']
    
    # 3. Register an admin
    print("\n3. Registering an ADMIN...")
    admin_data = register_user(
        email="admin@university.edu",
        password="admin123",
        first_name="Admin",
        last_name="User",
        user_type="admin"
    )
    print(f"✓ Admin registered: {admin_data['user']['email']}")
    print(f"  User Type: {admin_data['user']['user_type']}")
    admin_token = admin_data['access_token']
    
    # 4. Login as student
    print("\n4. Logging in as STUDENT...")
    login_data = login("john.doe@university.edu", "student123")
    print(f"✓ Login successful")
    print(f"  Token preview: {login_data['access_token'][:50]}...")
    
    # 5. Get current user info
    print("\n5. Getting current user info...")
    user_info = get_current_user(student_token)
    print(f"✓ Current user: {user_info['first_name']} {user_info['last_name']}")
    print(f"  Email: {user_info['email']}")
    print(f"  User Type: {user_info['user_type']}")
    print(f"  Active: {user_info['is_active']}")
    
    # 6. Search courses as student (requires authentication)
    print("\n6. Searching courses as STUDENT...")
    try:
        results = search_courses(student_token, "programming")
        print(f"✓ Search successful! Found {results['count']} results")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # 7. Try accessing without token (should fail)
    print("\n7. Trying to access without token...")
    try:
        response = requests.get(f"{BASE_URL}/search?q=programming")
        if response.status_code == 401:
            print("✗ Unauthorized (as expected)")
        else:
            print(f"Unexpected response: {response.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Demo completed!")
    print("=" * 60)
    
    print("\n📝 Summary:")
    print("- STUDENT can access: /search, /ask, /regulations/ask")
    print("- INSTRUCTOR can access: All of above + /regulations/chunk")
    print("- ADMIN can access: All endpoints")
    print("\nAll users receive JWT tokens with their UserType embedded.")


if __name__ == "__main__":
    main()
