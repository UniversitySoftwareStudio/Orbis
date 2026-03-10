from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.models import Course, CourseContent


class CourseRepository:
    def vector_search(self, db: Session, query_embedding: list[float], limit: int = 5) -> list[Course]:
        rows = (
            db.query(Course, Course.embedding.cosine_distance(query_embedding).label("distance"))
            .filter(Course.embedding.isnot(None))
            .order_by("distance")
            .limit(limit)
            .all()
        )

        courses: list[Course] = []
        for course, distance in rows:
            course.distance = distance
            courses.append(course)
        return courses

    def get_by_code(self, db: Session, code: str) -> Course | None:
        return db.scalars(select(Course).where(Course.code == code)).first()

    def search_by_keyword(self, db: Session, keyword: str, limit: int = 10) -> list[Course]:
        stmt = select(Course).where(Course.keywords.contains(keyword)).limit(limit)
        return list(db.scalars(stmt).all())

    def get_courses_with_embeddings(self, db: Session) -> list[Course]:
        return list(db.scalars(select(Course).where(Course.embedding.isnot(None))).all())

    def get_syllabus(self, db: Session, course_id: int) -> list[CourseContent]:
        stmt = (
            select(CourseContent)
            .where(CourseContent.course_id == course_id)
            .order_by(CourseContent.week_number)
        )
        return list(db.scalars(stmt).all())

    def get_with_prerequisites(self, db: Session, course_id: int) -> Course | None:
        stmt = (
            select(Course)
            .options(joinedload(Course.prerequisites))
            .where(Course.id == course_id)
        )
        return db.scalars(stmt).first()

    def check_prerequisites(
        self,
        db: Session,
        course_id: int,
        completed_course_ids: set[int],
    ) -> dict[str, object]:
        course = self.get_with_prerequisites(db, course_id)
        if course is None:
            return {"satisfied": False, "missing": ["Course not found"]}

        missing: list[str] = []

        def walk(prerequisite: Course) -> None:
            if prerequisite.id not in completed_course_ids:
                missing.append(prerequisite.code)
            for nested in prerequisite.prerequisites:
                walk(nested)

        for prerequisite in course.prerequisites:
            walk(prerequisite)

        return {"satisfied": not missing, "missing": missing}

    def search_by_code_or_keyword(self, db: Session, search_term: str, limit: int = 10) -> list[Course]:
        stmt = (
            select(Course)
            .where(
                (Course.code.ilike(f"%{search_term}%"))
                | (Course.keywords.ilike(f"%{search_term}%"))
                | (Course.name.ilike(f"%{search_term}%"))
            )
            .limit(limit)
        )
        return list(db.scalars(stmt).all())


def get_course_repository() -> CourseRepository:
    return CourseRepository()
