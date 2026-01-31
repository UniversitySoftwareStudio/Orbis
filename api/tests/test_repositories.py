import os
import sys
import logging
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

# Ensure package imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, StatementError, DataError, PendingRollbackError

# Application Imports
from database import models
from database.repositories.user_repository import UserRepository
from database.repositories.section_repository import SectionRepository
from database.repositories.enrollment_repository import EnrollmentRepository

# ============================================================================
# CONFIGURATION & FIXTURES
# ============================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tests.final")

@pytest.fixture(scope="function")
def strict_session():
    """
    Creates an SQLite session with STRICT enforcement enabled.
    """
    engine = create_engine("sqlite:///:memory:")
    
    # 1. Enforce Foreign Keys (SQLite default is OFF)
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()

# ============================================================================
# VERIFICATION TESTS (Expecting Failures)
# ============================================================================

def test_verify_term_date_constraint(strict_session):
    """
    VERIFICATION: The DB MUST reject a term ending before it starts.
    """
    bad_term = models.AcademicTerm(
        code="BAD_TERM", 
        term_type=models.TermType.SUMMER, 
        year=2025, 
        start_date=date(2025, 12, 1), 
        end_date=date(2025, 1, 1) # INVALID: End is before Start
    )
    strict_session.add(bad_term)
    
    # We EXPECT an IntegrityError here. 
    # If this block finishes without error, the test fails (DB is weak).
    with pytest.raises(IntegrityError):
        strict_session.commit()
    
    logger.info("SUCCESS: Database blocked invalid date range.")

def test_verify_enum_string_validation(strict_session):
    """
    VERIFICATION: The Model MUST reject invalid strings for Enum columns.
    """
    # Note: validation often happens at flush time or assignment time depending on config.
    # We catch generic Exception because SQLAlchemy wrappers vary (LookupError, StatementError).
    
    with pytest.raises((StatementError, LookupError, DataError, IntegrityError)):
        bad_user = models.User(
            email="badenum@t.com", 
            password_hash="x", 
            first_name="A", 
            last_name="B",
            user_type="SUPER_ADMIN_GOD_MODE" # INVALID STRING
        )
        strict_session.add(bad_user)
        strict_session.commit()
    
    logger.info("SUCCESS: Model rejected invalid Enum string.")

def test_verify_double_enrollment_prevention(strict_session):
    """
    VERIFICATION: The DB MUST reject double booking a student in the same section.
    """
    # 1. Setup Data
    u = models.User(email="e@t.com", password_hash="x", first_name="E", last_name="E", user_type=models.UserType.STUDENT)
    strict_session.add(u)
    strict_session.commit()
    
    stu = models.Student(user_id=u.id, student_id="STU1")
    c = models.Course(code="MATH", name="M", description=".")
    t = models.AcademicTerm(code="T1", term_type=models.TermType.FALL, year=2025, start_date=date(2025,9,1), end_date=date(2025,12,1))
    strict_session.add_all([c, t])
    strict_session.commit()
    
    sec = models.CourseSection(course_id=c.id, term_id=t.id, section_number="1", crn="1000")
    strict_session.add(sec)
    strict_session.commit()
    
    strict_session.add(stu)
    strict_session.commit()

    # 2. First Enrollment (Should Succeed)
    e1 = models.Enrollment(student_id=stu.id, section_id=sec.id)
    strict_session.add(e1)
    strict_session.commit()

    # 3. Second Enrollment (MUST FAIL)
    e2 = models.Enrollment(student_id=stu.id, section_id=sec.id)
    strict_session.add(e2)
    
    with pytest.raises(IntegrityError):
        strict_session.commit()
        
    logger.info("SUCCESS: Database blocked double enrollment.")

def test_verify_gpa_range_constraint(strict_session):
    """
    VERIFICATION: GPA must be between 0.00 and 4.00.
    """
    u = models.User(email="gpa@t.com", password_hash="x", first_name="G", last_name="P", user_type=models.UserType.STUDENT)
    strict_session.add(u)
    strict_session.commit()

    # Try 5.5 GPA
    s = models.Student(user_id=u.id, student_id="S_HIGH", gpa=5.5)
    strict_session.add(s)
    
    with pytest.raises(IntegrityError):
        strict_session.commit()

    logger.info("SUCCESS: Database blocked invalid GPA.")

def test_verify_email_uniqueness(strict_session):
    """
    VERIFICATION: Cannot create duplicate emails.
    """
    u1 = models.User(email="dupe@t.com", password_hash="x", first_name="A", last_name="B", user_type=models.UserType.STUDENT)
    strict_session.add(u1)
    strict_session.commit()

    u2 = models.User(email="dupe@t.com", password_hash="y", first_name="C", last_name="D", user_type=models.UserType.STUDENT)
    strict_session.add(u2)
    
    with pytest.raises(IntegrityError):
        strict_session.commit()

def test_happy_path_crud(strict_session):
    """
    CONTROL: Ensure valid data still works!
    """
    # Create valid hierarchy
    u = models.User(email="valid@t.com", password_hash="x", first_name="V", last_name="V", user_type=models.UserType.INSTRUCTOR)
    strict_session.add(u)
    strict_session.commit()
    
    ins = models.Instructor(user_id=u.id, employee_id="EMP1")
    strict_session.add(ins)
    strict_session.commit()
    
    c = models.Course(code="OK101", name="Okay", description=".")
    t = models.AcademicTerm(code="OK25", term_type=models.TermType.SPRING, year=2025, start_date=date(2025,1,1), end_date=date(2025,5,1))
    strict_session.add_all([c, t])
    strict_session.commit()
    
    sec = models.CourseSection(course_id=c.id, term_id=t.id, instructor_id=ins.id, section_number="01", crn="OKCRN")
    strict_session.add(sec)
    strict_session.commit()
    
    assert sec.id is not None
    logger.info("SUCCESS: Valid data accepted.")

if __name__ == "__main__":
    # Run tests directly and show logs (-s disables pytest capture)
    logger.info("Running tests in test_repositories.py directly")
    import pytest as _pytest
    raise SystemExit(_pytest.main(["-q", "-s", __file__]))
