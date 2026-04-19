from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..models import AcademicCalendarEntry
from .base import BaseRepository

TURKISH_MONTHS = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
    5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
    9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}

FALL_MONTHS = {9, 10, 11, 12, 1}
SPRING_MONTHS = {2, 3, 4, 5, 6, 7}


class AcademicCalendarRepository(BaseRepository[AcademicCalendarEntry]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AcademicCalendarEntry)

    def get_by_year(self, academic_year: str) -> list[AcademicCalendarEntry]:
        stmt = (
            select(AcademicCalendarEntry)
            .where(AcademicCalendarEntry.academic_year == academic_year)
            .order_by(AcademicCalendarEntry.start_date.asc())
        )
        return list(self.session.scalars(stmt).all())

    def get_by_year_and_applies_to(self, academic_year: str, applies_to: str) -> list[AcademicCalendarEntry]:
        stmt = (
            select(AcademicCalendarEntry)
            .where(
                AcademicCalendarEntry.academic_year == academic_year,
                AcademicCalendarEntry.applies_to == applies_to,
            )
            .order_by(AcademicCalendarEntry.start_date.asc())
        )
        return list(self.session.scalars(stmt).all())

    def get_active_year_entries(self) -> list[AcademicCalendarEntry]:
        max_year_subq = select(func.max(AcademicCalendarEntry.academic_year)).scalar_subquery()
        stmt = (
            select(AcademicCalendarEntry)
            .where(AcademicCalendarEntry.academic_year == max_year_subq)
            .order_by(AcademicCalendarEntry.start_date.asc())
        )
        return list(self.session.scalars(stmt).all())

    def format_for_rag(self, entries: list[AcademicCalendarEntry]) -> str:
        if not entries:
            return ""

        academic_year = entries[0].academic_year
        applies_to_set = {e.applies_to for e in entries}
        applies_label = ", ".join(sorted(applies_to_set)).title()

        fall_entries: list[AcademicCalendarEntry] = []
        spring_entries: list[AcademicCalendarEntry] = []

        for entry in entries:
            month = entry.start_date.month
            if month in FALL_MONTHS:
                fall_entries.append(entry)
            else:
                spring_entries.append(entry)

        lines = [f"=== AKADEMİK TAKVİM {academic_year} ({applies_label}) ==="]

        if fall_entries:
            lines.append("")
            lines.append("--- GÜZ YARIYILI ---")
            for entry in fall_entries:
                lines.append(self._format_entry(entry))

        if spring_entries:
            lines.append("")
            lines.append("--- BAHAR YARIYILI ---")
            for entry in spring_entries:
                lines.append(self._format_entry(entry))

        return "\n".join(lines)

    @staticmethod
    def _format_entry(entry: AcademicCalendarEntry) -> str:
        day = entry.start_date.day
        month_name = TURKISH_MONTHS[entry.start_date.month]

        if entry.end_date is None or entry.end_date == entry.start_date:
            date_str = f"{day} {month_name}"
        else:
            end_day = entry.end_date.day
            end_month_name = TURKISH_MONTHS[entry.end_date.month]
            if entry.start_date.month == entry.end_date.month:
                date_str = f"{day}-{end_day} {month_name}"
            else:
                date_str = f"{day} {month_name} - {end_day} {end_month_name}"

        return f"{date_str}: {entry.title_tr}"
