from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models import SectionSchedule
from .base import BaseRepository

DAY_ORDER = ["MON", "TUE", "WED", "THU", "FRI"]
DAY_LABELS_TR = {
    "MON": "PAZARTESİ",
    "TUE": "SALI",
    "WED": "ÇARŞAMBA",
    "THU": "PERŞEMBE",
    "FRI": "CUMA",
}


class SectionScheduleRepository(BaseRepository[SectionSchedule]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, SectionSchedule)

    def get_by_section_id(self, section_id: int) -> list[SectionSchedule]:
        stmt = (
            select(SectionSchedule)
            .where(SectionSchedule.section_id == section_id)
            .order_by(SectionSchedule.day_of_week, SectionSchedule.start_time)
        )
        return list(self.session.scalars(stmt).all())

    def get_student_schedule(self, student_id: int) -> list[dict]:
        query = text("""
            SELECT
                c.code as course_code,
                c.name as course_name,
                cs.section_number,
                cs.section_type,
                cs.instructor_name,
                cs.parent_section_id,
                ss.day_of_week,
                ss.start_time,
                ss.end_time,
                ss.location,
                ss.is_online
            FROM enrollments e
            JOIN course_sections cs ON e.section_id = cs.id
            JOIN courses c ON cs.course_id = c.id
            LEFT JOIN section_schedules ss ON ss.section_id = cs.id
            WHERE e.student_id = :student_id
              AND e.status = 'ENROLLED'
            ORDER BY ss.day_of_week, ss.start_time
        """)
        result = self.session.execute(query, {"student_id": student_id})
        return [dict(row._mapping) for row in result]

    def format_for_rag(self, schedule_rows: list[dict]) -> str:
        if not schedule_rows:
            return ""

        by_day: dict[str, list[dict]] = {}
        for row in schedule_rows:
            day = row.get("day_of_week")
            if day is None:
                continue
            by_day.setdefault(day, []).append(row)

        lines = ["=== ÖĞRENCİ HAFTALIK PROGRAMI ==="]

        for day_code in DAY_ORDER:
            if day_code not in by_day:
                continue
            lines.append(DAY_LABELS_TR[day_code] + ":")
            for row in by_day[day_code]:
                start = _format_time(row["start_time"])
                end = _format_time(row["end_time"])
                code = row["course_code"]
                name = row["course_name"]

                section_num = row["section_number"]
                section_type = row["section_type"]
                if section_type == "LAB":
                    type_label = f"Lab {section_num}"
                else:
                    type_label = f"Section {section_num}, Lecture"

                location = "Online" if row.get("is_online") else (row.get("location") or "TBA")

                # Use instructor_name directly (instructor_id may be null for demo sections)
                instructor = row.get("instructor_name") or ""

                parts = [f"{start}-{end}", f"{code} - {name} ({type_label})", location]
                if instructor:
                    parts.append(instructor)

                lines.append(" | ".join(parts))

        return "\n".join(lines)


def _format_time(t) -> str:
    if hasattr(t, "strftime"):
        return t.strftime("%H:%M")
    return str(t)[:5]
