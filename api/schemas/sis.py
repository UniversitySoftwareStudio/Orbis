from datetime import date, time

from pydantic import BaseModel


class CalendarEntryResponse(BaseModel):
    id: int
    title_tr: str
    title_en: str | None
    start_date: date
    end_date: date | None
    entry_type: str
    applies_to: str
    academic_year: str
    notes: str | None

    class Config:
        from_attributes = True


class ScheduleSlotResponse(BaseModel):
    course_code: str
    course_name: str
    section_number: str
    section_type: str
    instructor_name: str | None
    day_of_week: str | None
    start_time: time | None
    end_time: time | None
    location: str | None
    is_online: bool | None

    class Config:
        from_attributes = True
