"""
Comprehensive tests for all repository functionality
Tests academic catalog, enrollment, LMS, and authorization features
"""

import os
import sys
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database import models
from database.repositories.course_repository import CourseRepository
from database.repositories.student_repository import StudentRepository
from database.repositories.enrollment_repository import EnrollmentRepository
from database.repositories.section_repository import SectionRepository
from database.repositories.term_repository import TermRepository
from database.repositories.assignment_repository import AssignmentRepository
from database.repositories.user_repository import UserRepository
from database.repositories.instructor_repository import InstructorRepository


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()
    engine.dispose()


@pytest.fixture
def sample_courses(db_session):
    """Create sample courses with prerequisites"""
    cs101 = models.Course(
        code="CS101",
        name="Intro to Programming",
        description="Basic programming concepts",
        keywords="programming, python, basics"
    )
    cs102 = models.Course(
        code="CS102",
        name="Data Structures",
        description="Advanced data structures",
        keywords="algorithms, data structures"
    )
    cs201 = models.Course(
        code="CS201",
        name="Algorithms",
        description="Algorithm design",
        keywords="algorithms, complexity"
    )
    
    db_session.add_all([cs101, cs102, cs201])
    db_session.commit()
    
    # Set prerequisites: CS201 requires CS102, CS102 requires CS101
    cs102.prerequisites.append(cs101)
    cs201.prerequisites.append(cs102)
    db_session.commit()
    
    return {'cs101': cs101, 'cs102': cs102, 'cs201': cs201}


@pytest.fixture
def sample_term(db_session):
    """Create a sample academic term"""
    term = models.AcademicTerm(
        code="FALL2024",
        term_type=models.TermType.FALL,
        year=2024,
        start_date=date(2024, 9, 1),
        end_date=date(2024, 12, 20),
        is_active=True
    )
    db_session.add(term)
    db_session.commit()
    return term


@pytest.fixture
def sample_student(db_session):
    """Create a sample student with user"""
    user = models.User(
        email="john.doe@bilgiedu.net",
        password_hash="hashed",
        first_name="John",
        last_name="Doe",
        user_type=models.UserType.STUDENT
    )
    db_session.add(user)
    db_session.commit()
    
    student = models.Student(
        user_id=user.id,
        student_id="STU001",
        gpa=Decimal("3.5")
    )
    db_session.add(student)
    db_session.commit()
    
    return student


@pytest.fixture
def sample_instructor(db_session):
    """Create a sample instructor with user"""
    user = models.User(
        email="prof.smith@bilgi.edu.tr",
        password_hash="hashed",
        first_name="Jane",
        last_name="Smith",
        user_type=models.UserType.INSTRUCTOR
    )
    db_session.add(user)
    db_session.commit()
    
    instructor = models.Instructor(
        user_id=user.id,
        employee_id="EMP001",
        title="Professor",
        is_active=True
    )
    db_session.add(instructor)
    db_session.commit()
    
    return instructor


# ============================================================================
# COURSE REPOSITORY TESTS
# ============================================================================

class TestCourseRepository:
    
    def test_get_syllabus(self, db_session, sample_courses):
        """Test retrieving course syllabus"""
        course = sample_courses['cs101']
        
        # Add course content
        content1 = models.CourseContent(course_id=course.id, week_number=1, topic="Introduction")
        content2 = models.CourseContent(course_id=course.id, week_number=2, topic="Variables")
        content3 = models.CourseContent(course_id=course.id, week_number=3, topic="Functions")
        db_session.add_all([content1, content2, content3])
        db_session.commit()
        
        repo = CourseRepository()
        syllabus = repo.get_syllabus(db_session, course.id)
        
        assert len(syllabus) == 3
        assert syllabus[0].week_number == 1
        assert syllabus[0].topic == "Introduction"
        assert syllabus[2].week_number == 3
    
    def test_check_prerequisites_satisfied(self, db_session, sample_courses):
        """Test prerequisite checking when all are completed"""
        repo = CourseRepository()
        
        # Student completed CS101 and CS102
        completed = {sample_courses['cs101'].id, sample_courses['cs102'].id}
        
        result = repo.check_prerequisites(db_session, sample_courses['cs201'].id, completed)
        
        assert result['satisfied'] is True
        assert len(result['missing']) == 0
    
    def test_check_prerequisites_missing(self, db_session, sample_courses):
        """Test prerequisite checking when some are missing"""
        repo = CourseRepository()
        
        # Student only completed CS101
        completed = {sample_courses['cs101'].id}
        
        result = repo.check_prerequisites(db_session, sample_courses['cs201'].id, completed)
        
        assert result['satisfied'] is False
        assert 'CS102' in result['missing']
    
    def test_check_prerequisites_recursive(self, db_session, sample_courses):
        """Test recursive prerequisite checking"""
        repo = CourseRepository()
        
        # Student completed nothing
        completed = set()
        
        result = repo.check_prerequisites(db_session, sample_courses['cs201'].id, completed)
        
        assert result['satisfied'] is False
        # Should catch both CS102 and CS101 (recursive)
        assert 'CS102' in result['missing']
        assert 'CS101' in result['missing']
    
    def test_search_by_code_or_keyword(self, db_session, sample_courses):
        """Test keyword and code search"""
        repo = CourseRepository()
        
        # Search by code
        results = repo.search_by_code_or_keyword(db_session, "CS101")
        assert len(results) == 1
        assert results[0].code == "CS101"
        
        # Search by keyword
        results = repo.search_by_code_or_keyword(db_session, "algorithms")
        assert len(results) >= 2  # CS102 and CS201 both have "algorithms"
    
    def test_get_by_code(self, db_session, sample_courses):
        """Test getting course by code"""
        repo = CourseRepository()
        course = repo.get_by_code(db_session, "CS101")
        
        assert course is not None
        assert course.name == "Intro to Programming"


# ============================================================================
# TERM REPOSITORY TESTS
# ============================================================================

class TestTermRepository:
    
    def test_get_active_term(self, db_session, sample_term):
        """Test getting currently active term"""
        repo = TermRepository(db_session)
        
        # Set current date within term range
        current_date = date(2024, 10, 15)
        active_term = repo.get_active_term(current_date)
        
        assert active_term is not None
        assert active_term.code == "FALL2024"
    
    def test_get_active_term_outside_range(self, db_session, sample_term):
        """Test when no term is active"""
        repo = TermRepository(db_session)
        
        # Date outside term range
        current_date = date(2025, 1, 15)
        active_term = repo.get_active_term(current_date)
        
        assert active_term is None
    
    def test_get_by_term_and_year(self, db_session, sample_term):
        """Test getting term by type and year"""
        repo = TermRepository(db_session)
        
        term = repo.get_by_term_and_year(models.TermType.FALL, 2024)
        
        assert term is not None
        assert term.code == "FALL2024"
    
    def test_is_term_active(self, db_session, sample_term):
        """Test checking if term is currently active"""
        repo = TermRepository(db_session)
        
        # Mock today to be within term
        is_active = repo.is_term_active(sample_term.id)
        
        assert isinstance(is_active, bool)


# ============================================================================
# STUDENT REPOSITORY TESTS
# ============================================================================

class TestStudentRepository:
    
    def test_calculate_gpa(self, db_session, sample_student, sample_courses, sample_term):
        """Test GPA calculation from completed courses"""
        # Create section
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01",
            crn="CRN001"
        )
        db_session.add(section)
        db_session.commit()
        
        # Create completed enrollment with grade
        enrollment = models.Enrollment(
            student_id=sample_student.id,
            section_id=section.id,
            status=models.EnrollmentStatus.COMPLETED,
            final_grade_numeric=Decimal("3.75")
        )
        db_session.add(enrollment)
        db_session.commit()
        
        repo = StudentRepository(db_session)
        gpa = repo.calculate_gpa(sample_student.id)
        
        assert gpa == 3.75
    
    def test_get_transcript(self, db_session, sample_student, sample_courses, sample_term):
        """Test transcript generation"""
        # Create sections and enrollments
        section1 = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01",
            crn="CRN001"
        )
        section2 = models.CourseSection(
            course_id=sample_courses['cs102'].id,
            term_id=sample_term.id,
            section_number="01",
            crn="CRN002"
        )
        db_session.add_all([section1, section2])
        db_session.commit()
        
        enrollment1 = models.Enrollment(
            student_id=sample_student.id,
            section_id=section1.id,
            status=models.EnrollmentStatus.COMPLETED,
            final_grade_numeric=Decimal("3.5"),
            final_grade_letter="A-"
        )
        enrollment2 = models.Enrollment(
            student_id=sample_student.id,
            section_id=section2.id,
            status=models.EnrollmentStatus.COMPLETED,
            final_grade_numeric=Decimal("4.0"),
            final_grade_letter="A"
        )
        db_session.add_all([enrollment1, enrollment2])
        db_session.commit()
        
        repo = StudentRepository(db_session)
        transcript = repo.get_transcript(sample_student.id)
        
        assert len(transcript) == 2
        assert transcript[0]['course_code'] in ['CS101', 'CS102']
        assert transcript[0]['grade_letter'] in ['A-', 'A']
    
    def test_check_academic_standing_good(self, db_session, sample_student):
        """Test student in good academic standing"""
        repo = StudentRepository(db_session)
        result = repo.check_academic_standing(sample_student.id)
        
        assert result['eligible'] is True
        assert 'good standing' in result['reason'].lower()
    
    def test_check_academic_standing_low_gpa(self, db_session):
        """Test student with low GPA"""
        user = models.User(
            email="low.gpa@bilgiedu.net",
            password_hash="hash",
            first_name="Low",
            last_name="GPA",
            user_type=models.UserType.STUDENT
        )
        db_session.add(user)
        db_session.commit()
        
        student = models.Student(
            user_id=user.id,
            student_id="STU002",
            gpa=Decimal("1.5")
        )
        db_session.add(student)
        db_session.commit()
        
        repo = StudentRepository(db_session)
        result = repo.check_academic_standing(student.id)
        
        assert result['eligible'] is False
        assert 'GPA' in result['reason']
    
    def test_check_already_enrolled(self, db_session, sample_student, sample_courses, sample_term):
        """Test duplicate enrollment prevention"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01"
        )
        db_session.add(section)
        db_session.commit()
        
        enrollment = models.Enrollment(
            student_id=sample_student.id,
            section_id=section.id
        )
        db_session.add(enrollment)
        db_session.commit()
        
        repo = StudentRepository(db_session)
        is_enrolled = repo.check_already_enrolled(sample_student.id, section.id)
        
        assert is_enrolled is True
        
        # Check non-enrolled section
        is_enrolled_other = repo.check_already_enrolled(sample_student.id, 9999)
        assert is_enrolled_other is False


# ============================================================================
# SECTION REPOSITORY TESTS
# ============================================================================

class TestSectionRepository:
    
    def test_check_capacity_available(self, db_session, sample_courses, sample_term):
        """Test checking section capacity when seats available"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01",
            max_enrollment=30,
            current_enrollment=15
        )
        db_session.add(section)
        db_session.commit()
        
        repo = SectionRepository(db_session)
        has_capacity = repo.check_capacity(section.id)
        
        assert has_capacity is True
    
    def test_check_capacity_full(self, db_session, sample_courses, sample_term):
        """Test checking section capacity when full"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01",
            max_enrollment=30,
            current_enrollment=30
        )
        db_session.add(section)
        db_session.commit()
        
        repo = SectionRepository(db_session)
        has_capacity = repo.check_capacity(section.id)
        
        assert has_capacity is False
    
    def test_get_section_roster(self, db_session, sample_courses, sample_term, sample_student):
        """Test getting active students in a section"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01"
        )
        db_session.add(section)
        db_session.commit()
        
        enrollment = models.Enrollment(
            student_id=sample_student.id,
            section_id=section.id,
            status=models.EnrollmentStatus.ENROLLED
        )
        db_session.add(enrollment)
        db_session.commit()
        
        repo = SectionRepository(db_session)
        roster = repo.get_section_roster(section.id)
        
        assert len(roster) == 1
        assert roster[0].id == sample_student.id
    
    def test_validate_section_status(self, db_session, sample_courses, sample_term):
        """Test section status validation"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01",
            status=models.SectionStatus.ACTIVE
        )
        db_session.add(section)
        db_session.commit()
        
        repo = SectionRepository(db_session)
        is_active = repo.validate_section_status(section.id, models.SectionStatus.ACTIVE)
        
        assert is_active is True
        
        is_cancelled = repo.validate_section_status(section.id, models.SectionStatus.CANCELLED)
        assert is_cancelled is False


# ============================================================================
# ENROLLMENT REPOSITORY TESTS
# ============================================================================

class TestEnrollmentRepository:
    
    def test_register_student_success(self, db_session, sample_student, sample_courses, sample_term):
        """Test successful student registration"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01",
            max_enrollment=30,
            current_enrollment=0
        )
        db_session.add(section)
        db_session.commit()
        
        repo = EnrollmentRepository(db_session)
        enrollment = repo.register_student(sample_student.id, section.id)
        
        assert enrollment is not None
        assert enrollment.student_id == sample_student.id
        assert enrollment.status == models.EnrollmentStatus.ENROLLED
        
        # Check enrollment count incremented
        db_session.refresh(section)
        assert section.current_enrollment == 1
    
    def test_register_student_full_section(self, db_session, sample_student, sample_courses, sample_term):
        """Test registration fails when section is full"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01",
            max_enrollment=1,
            current_enrollment=1
        )
        db_session.add(section)
        db_session.commit()
        
        repo = EnrollmentRepository(db_session)
        enrollment = repo.register_student(sample_student.id, section.id)
        
        assert enrollment is None
    
    def test_withdraw_student(self, db_session, sample_student, sample_courses, sample_term):
        """Test withdrawing a student from section"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01",
            current_enrollment=1
        )
        db_session.add(section)
        db_session.commit()
        
        enrollment = models.Enrollment(
            student_id=sample_student.id,
            section_id=section.id,
            status=models.EnrollmentStatus.ENROLLED
        )
        db_session.add(enrollment)
        db_session.commit()
        
        repo = EnrollmentRepository(db_session)
        success = repo.withdraw_student(sample_student.id, section.id)
        
        assert success is True
        
        db_session.refresh(enrollment)
        assert enrollment.status == models.EnrollmentStatus.DROPPED
        
        db_session.refresh(section)
        assert section.current_enrollment == 0
    
    def test_get_completed_courses(self, db_session, sample_student, sample_courses, sample_term):
        """Test getting list of completed course IDs"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01"
        )
        db_session.add(section)
        db_session.commit()
        
        enrollment = models.Enrollment(
            student_id=sample_student.id,
            section_id=section.id,
            status=models.EnrollmentStatus.COMPLETED
        )
        db_session.add(enrollment)
        db_session.commit()
        
        repo = EnrollmentRepository(db_session)
        completed = repo.get_completed_courses(sample_student.id)
        
        assert sample_courses['cs101'].id in completed


# ============================================================================
# ASSIGNMENT REPOSITORY TESTS
# ============================================================================

class TestAssignmentRepository:
    
    def test_publish_assignment(self, db_session, sample_courses, sample_term):
        """Test publishing an assignment"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01"
        )
        db_session.add(section)
        db_session.commit()
        
        assignment = models.Assignment(
            section_id=section.id,
            title="Homework 1",
            due_date=datetime.utcnow() + timedelta(days=7),
            max_points=Decimal("100"),
            is_published=False
        )
        db_session.add(assignment)
        db_session.commit()
        
        repo = AssignmentRepository(db_session)
        updated = repo.publish(assignment.id)
        
        assert updated.is_published is True
    
    def test_get_pending_assignments(self, db_session, sample_student, sample_courses, sample_term):
        """Test getting pending assignments for a student"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01"
        )
        db_session.add(section)
        db_session.commit()
        
        enrollment = models.Enrollment(
            student_id=sample_student.id,
            section_id=section.id,
            status=models.EnrollmentStatus.ENROLLED
        )
        db_session.add(enrollment)
        db_session.commit()
        
        future_assignment = models.Assignment(
            section_id=section.id,
            title="Future HW",
            due_date=datetime.utcnow() + timedelta(days=7),
            max_points=Decimal("100"),
            is_published=True
        )
        past_assignment = models.Assignment(
            section_id=section.id,
            title="Past HW",
            due_date=datetime.utcnow() - timedelta(days=1),
            max_points=Decimal("100"),
            is_published=True
        )
        db_session.add_all([future_assignment, past_assignment])
        db_session.commit()
        
        repo = AssignmentRepository(db_session)
        pending = repo.get_pending_assignments(sample_student.id)
        
        assert len(pending) == 1
        assert pending[0].title == "Future HW"
    
    def test_validate_submission_window_open(self, db_session, sample_courses, sample_term):
        """Test submission window validation when open"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01"
        )
        db_session.add(section)
        db_session.commit()
        
        assignment = models.Assignment(
            section_id=section.id,
            title="Open HW",
            due_date=datetime.utcnow() + timedelta(hours=1),
            max_points=Decimal("100")
        )
        db_session.add(assignment)
        db_session.commit()
        
        repo = AssignmentRepository(db_session)
        result = repo.validate_submission_window(assignment.id)
        
        assert result['open'] is True
    
    def test_validate_submission_window_closed(self, db_session, sample_courses, sample_term):
        """Test submission window validation when closed"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01"
        )
        db_session.add(section)
        db_session.commit()
        
        assignment = models.Assignment(
            section_id=section.id,
            title="Closed HW",
            due_date=datetime.utcnow() - timedelta(hours=1),
            max_points=Decimal("100")
        )
        db_session.add(assignment)
        db_session.commit()
        
        repo = AssignmentRepository(db_session)
        result = repo.validate_submission_window(assignment.id)
        
        assert result['open'] is False
        assert 'passed' in result['message'].lower()
    
    def test_get_assignment_rubric(self, db_session, sample_courses, sample_term):
        """Test getting assignment rubric"""
        section = models.CourseSection(
            course_id=sample_courses['cs101'].id,
            term_id=sample_term.id,
            section_number="01"
        )
        db_session.add(section)
        db_session.commit()
        
        assignment = models.Assignment(
            section_id=section.id,
            title="Test HW",
            description="Do the thing",
            due_date=datetime.utcnow() + timedelta(days=7),
            max_points=Decimal("100")
        )
        db_session.add(assignment)
        db_session.commit()
        
        repo = AssignmentRepository(db_session)
        rubric = repo.get_assignment_rubric(assignment.id)
        
        assert rubric is not None
        assert rubric['title'] == "Test HW"
        assert rubric['description'] == "Do the thing"
        assert rubric['max_points'] == 100.0


# ============================================================================
# USER & AUTHORIZATION TESTS
# ============================================================================

class TestUserRepository:
    
    def test_resolve_user_role_student(self, db_session, sample_student):
        """Test resolving user role for a student"""
        repo = UserRepository(db_session)
        result = repo.resolve_user_role(sample_student.user_id)
        
        assert result is not None
        assert result['role'] == 'student'
        assert result['entity_id'] == sample_student.id
    
    def test_resolve_user_role_instructor(self, db_session, sample_instructor):
        """Test resolving user role for an instructor"""
        repo = UserRepository(db_session)
        result = repo.resolve_user_role(sample_instructor.user_id)
        
        assert result is not None
        assert result['role'] == 'instructor'
        assert result['entity_id'] == sample_instructor.id
    
    def test_resolve_user_role_no_profile(self, db_session):
        """Test resolving user role when no student/instructor profile"""
        user = models.User(
            email="admin@bilgi.edu.tr",
            password_hash="hash",
            first_name="Admin",
            last_name="User",
            user_type=models.UserType.ADMIN
        )
        db_session.add(user)
        db_session.commit()
        
        repo = UserRepository(db_session)
        result = repo.resolve_user_role(user.id)
        
        assert result is not None
        assert result['role'] is None
        assert result['user_type'] == 'admin'


class TestInstructorRepository:
    
    def test_check_validity_active(self, db_session, sample_instructor):
        """Test instructor validity check for active instructor"""
        repo = InstructorRepository(db_session)
        is_valid = repo.check_validity(sample_instructor.id)
        
        assert is_valid is True
    
    def test_check_validity_inactive(self, db_session):
        """Test instructor validity check for inactive instructor"""
        user = models.User(
            email="inactive@bilgi.edu.tr",
            password_hash="hash",
            first_name="Inactive",
            last_name="Prof",
            user_type=models.UserType.INSTRUCTOR
        )
        db_session.add(user)
        db_session.commit()
        
        instructor = models.Instructor(
            user_id=user.id,
            employee_id="EMP999",
            is_active=False
        )
        db_session.add(instructor)
        db_session.commit()
        
        repo = InstructorRepository(db_session)
        is_valid = repo.check_validity(instructor.id)
        
        assert is_valid is False


if __name__ == "__main__":
    pytest.main(["-v", __file__])
