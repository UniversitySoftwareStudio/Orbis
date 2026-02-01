"""
Example: Creating new routes with role-based access control using UserType

This file demonstrates how to create API endpoints with different
access levels based on UserType (STUDENT, INSTRUCTOR, ADMIN).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User, UserType
from dependencies import (
    get_current_active_user,
    require_student,
    require_instructor,
    require_admin,
    require_user_types
)

router = APIRouter()


# ============================================================================
# PUBLIC ENDPOINT (No authentication required)
# ============================================================================

@router.get("/public/info")
def public_info():
    """
    Public endpoint - no authentication required
    """
    return {"message": "This is a public endpoint"}


# ============================================================================
# AUTHENTICATED ENDPOINTS (Any authenticated user)
# ============================================================================

@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_active_user)):
    """
    Any authenticated user can access this endpoint
    Works for STUDENT, INSTRUCTOR, and ADMIN
    """
    return {
        "message": f"Hello {current_user.first_name}!",
        "user_type": current_user.user_type.value,
        "email": current_user.email
    }


# ============================================================================
# STUDENT ENDPOINTS (Students, Instructors, and Admins)
# ============================================================================

@router.get("/student/dashboard")
def student_dashboard(current_user: User = Depends(require_student)):
    """
    Accessible by STUDENT, INSTRUCTOR, and ADMIN
    Students can view their dashboard
    """
    return {
        "message": f"Student dashboard for {current_user.first_name}",
        "user_type": current_user.user_type.value
    }


@router.get("/student/enrollments")
def get_enrollments(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db)
):
    """
    Get student enrollments
    Accessible by STUDENT, INSTRUCTOR, and ADMIN
    """
    # In a real app, you'd fetch enrollments from database
    return {
        "student_id": current_user.id,
        "enrollments": []
    }


# ============================================================================
# INSTRUCTOR ENDPOINTS (Instructors and Admins only)
# ============================================================================

@router.get("/instructor/dashboard")
def instructor_dashboard(current_user: User = Depends(require_instructor)):
    """
    Accessible by INSTRUCTOR and ADMIN only
    """
    return {
        "message": f"Instructor dashboard for Professor {current_user.last_name}",
        "user_type": current_user.user_type.value
    }


@router.post("/instructor/grade-assignment")
def grade_assignment(
    assignment_id: int,
    student_id: int,
    grade: float,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db)
):
    """
    Grade a student's assignment
    Only INSTRUCTOR and ADMIN can grade
    """
    if current_user.user_type not in [UserType.INSTRUCTOR, UserType.ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return {
        "message": "Grade submitted",
        "assignment_id": assignment_id,
        "student_id": student_id,
        "grade": grade,
        "graded_by": current_user.email
    }


@router.get("/instructor/my-courses")
def get_instructor_courses(
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db)
):
    """
    Get courses taught by the instructor
    Only accessible by INSTRUCTOR and ADMIN
    """
    return {
        "instructor_id": current_user.id,
        "courses": []  # Would fetch from database
    }


# ============================================================================
# ADMIN ENDPOINTS (Admins only)
# ============================================================================

@router.get("/admin/dashboard")
def admin_dashboard(current_user: User = Depends(require_admin)):
    """
    Accessible by ADMIN only
    """
    return {
        "message": f"Admin dashboard for {current_user.first_name}",
        "user_type": current_user.user_type.value
    }


@router.post("/admin/create-course")
def create_course(
    course_code: str,
    course_name: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new course
    Only ADMIN can create courses
    """
    return {
        "message": "Course created",
        "course_code": course_code,
        "course_name": course_name,
        "created_by": current_user.email
    }


@router.delete("/admin/delete-user/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a user (soft delete)
    Only ADMIN can delete users
    """
    # In real app, perform soft delete
    return {
        "message": f"User {user_id} deleted",
        "deleted_by": current_user.email
    }


@router.get("/admin/all-users")
def get_all_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get all users in the system
    Only ADMIN can view all users
    """
    return {
        "message": "All users list",
        "users": []  # Would fetch from database
    }


# ============================================================================
# CUSTOM ROLE COMBINATIONS
# ============================================================================

@router.post("/course/{course_id}/manage")
def manage_course(
    course_id: int,
    current_user: User = Depends(require_user_types([UserType.INSTRUCTOR, UserType.ADMIN]))
):
    """
    Manage a specific course
    Only INSTRUCTOR and ADMIN can manage courses
    Uses custom role requirement
    """
    return {
        "message": f"Managing course {course_id}",
        "user_type": current_user.user_type.value,
        "user_email": current_user.email
    }


# ============================================================================
# CONDITIONAL ACCESS BASED ON USER TYPE
# ============================================================================

@router.get("/reports/{report_id}")
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a report with different access levels based on UserType
    - STUDENT: Can only see their own reports
    - INSTRUCTOR: Can see reports for their courses
    - ADMIN: Can see all reports
    """
    if current_user.user_type == UserType.STUDENT:
        # Return only user's own report
        return {
            "report_id": report_id,
            "message": "Student's own report",
            "data": "limited_data"
        }
    elif current_user.user_type == UserType.INSTRUCTOR:
        # Return reports for instructor's courses
        return {
            "report_id": report_id,
            "message": "Course report",
            "data": "course_data"
        }
    elif current_user.user_type == UserType.ADMIN:
        # Return full report
        return {
            "report_id": report_id,
            "message": "Full system report",
            "data": "complete_data"
        }


# ============================================================================
# HOW TO REGISTER THIS ROUTER IN main.py
# ============================================================================
"""
In your main.py, add:

from routes.example_routes import router as example_router

app.include_router(example_router, prefix="/api", tags=["examples"])
"""
