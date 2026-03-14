"""
Seed script for 2025-2026 Undergraduate Academic Calendar (Istanbul Bilgi University).
Run once: python scripts/seed_academic_calendar.py
Data source: Official academic calendar page (lisans-onlisans 2025-2026).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from database.session import SessionLocal

ENTRIES = [
    # --- 2025 ---
    {
        "title_tr": "Güz Yarıyılı için Çift Anadal/Yandal/Bölüm Değişikliği Başvuruları",
        "title_en": "Double Major / Minor / Department Change Applications for Fall Semester",
        "start_date": "2025-07-21", "end_date": "2025-08-22",
        "entry_type": "other", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Tatil - Zafer Bayramı",
        "title_en": "Holiday - Victory Day",
        "start_date": "2025-08-30", "end_date": None,
        "entry_type": "holiday", "applies_to": "all", "academic_year": "2025-2026",
    },
    {
        "title_tr": "ÖSYS Kayıtları",
        "title_en": "ÖSYS (University Entrance) Registrations",
        "start_date": "2025-09-01", "end_date": "2025-09-05",
        "entry_type": "registration", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "BİLET I (BİLGİ İngilizce Testi)",
        "title_en": "BİLET I (BİLGİ English Test)",
        "start_date": "2025-09-08", "end_date": "2025-09-09",
        "entry_type": "exam_period", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "BİLET I Sonuçlarının İlanı",
        "title_en": "BİLET I Results Announcement",
        "start_date": "2025-09-15", "end_date": None,
        "entry_type": "grade_announcement", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "BİLET II Yazılı Sınavı",
        "title_en": "BİLET II Written Exam",
        "start_date": "2025-09-17", "end_date": None,
        "entry_type": "exam_period", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "BİLET II Konuşma Sınavı",
        "title_en": "BİLET II Speaking Exam",
        "start_date": "2025-09-18", "end_date": None,
        "entry_type": "exam_period", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "BİLET II Sonuçlarının İlanı",
        "title_en": "BİLET II Results Announcement",
        "start_date": "2025-09-25", "end_date": None,
        "entry_type": "grade_announcement", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "İngilizce Hazırlık Programı Dersliklerinin İlanı",
        "title_en": "English Prep Program Classroom Announcement",
        "start_date": "2025-09-27", "end_date": None,
        "entry_type": "other", "applies_to": "prep", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Güz Yarıyılı için Ders Kayıtları",
        "title_en": "Course Registration for Fall Semester",
        "start_date": "2025-09-22", "end_date": "2025-09-26",
        "entry_type": "registration", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Güz Yarıyılı Başlangıcı",
        "title_en": "Fall Semester Start",
        "start_date": "2025-09-29", "end_date": None,
        "entry_type": "semester_start", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Kayıt Dondurma Başvuru Dönemi (Güz)",
        "title_en": "Leave of Absence Application Period (Fall)",
        "start_date": "2025-09-29", "end_date": "2025-11-14",
        "entry_type": "freeze_period", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Ders Ekleme/Bırakma Dönemi (Güz)",
        "title_en": "Add/Drop Period (Fall)",
        "start_date": "2025-10-06", "end_date": "2025-10-08",
        "entry_type": "add_drop", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Ders Şube Değişikliği (Güz)",
        "title_en": "Section Change Period (Fall)",
        "start_date": "2025-10-09", "end_date": "2025-10-24",
        "entry_type": "section_change", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Tatil - Cumhuriyet Bayramı (28 Ekim Yarım Gün Salı)",
        "title_en": "Holiday - Republic Day (Oct 28 Half Day Tuesday)",
        "start_date": "2025-10-28", "end_date": "2025-10-29",
        "entry_type": "holiday", "applies_to": "all", "academic_year": "2025-2026",
        "notes": "28 Ekim Yarım Gün",
    },
    {
        "title_tr": "Ara Sınavlar (Güz)",
        "title_en": "Midterm Exams (Fall)",
        "start_date": "2025-11-15", "end_date": "2025-11-23",
        "entry_type": "exam_period", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Dersten Çekilme için Son Gün (Güz)",
        "title_en": "Last Day to Withdraw from a Course (Fall)",
        "start_date": "2025-12-05", "end_date": None,
        "entry_type": "withdrawal_deadline", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    # --- 2026 ---
    {
        "title_tr": "Tatil - Yeni Yıl",
        "title_en": "Holiday - New Year's Day",
        "start_date": "2026-01-01", "end_date": None,
        "entry_type": "holiday", "applies_to": "all", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Güz Yarıyılı Derslerinin Son Günü",
        "title_en": "Last Day of Fall Semester Classes",
        "start_date": "2026-01-02", "end_date": None,
        "entry_type": "semester_end", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Final Sınavları (Güz)",
        "title_en": "Final Exams (Fall)",
        "start_date": "2026-01-05", "end_date": "2026-01-17",
        "entry_type": "exam_period", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Not Teslim ve İlanı - Final Sınavları (Güz)",
        "title_en": "Grade Submission and Announcement - Finals (Fall)",
        "start_date": "2026-01-21", "end_date": None,
        "entry_type": "grade_announcement", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Bahar için Çift Anadal/Yandal/Bölüm Değişikliği Başvuruları",
        "title_en": "Double Major / Minor / Department Change Applications for Spring",
        "start_date": "2026-01-21", "end_date": "2026-02-04",
        "entry_type": "other", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Bütünleme Sınavları (Güz)",
        "title_en": "Makeup/Resit Exams (Fall)",
        "start_date": "2026-01-27", "end_date": "2026-02-01",
        "entry_type": "makeup_exam", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Not İlanı - Bütünleme Sınavları (Güz)",
        "title_en": "Grade Announcement - Resit Exams (Fall)",
        "start_date": "2026-02-04", "end_date": None,
        "entry_type": "grade_announcement", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Mazeret Başvurularının Son Günü (Güz Bütünleme)",
        "title_en": "Excuse Application Deadline (Fall Resit)",
        "start_date": "2026-02-04", "end_date": None,
        "entry_type": "other", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Mazeret Komisyonu (Güz)",
        "title_en": "Excuse Committee Meeting (Fall)",
        "start_date": "2026-02-09", "end_date": None,
        "entry_type": "other", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Mazeret Sınavları (Güz)",
        "title_en": "Excuse Exams (Fall)",
        "start_date": "2026-02-11", "end_date": "2026-02-12",
        "entry_type": "makeup_exam", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Mazeret Sınavları Not Teslim ve İlanı (Güz)",
        "title_en": "Excuse Exam Grade Submission and Announcement (Fall)",
        "start_date": "2026-02-16", "end_date": None,
        "entry_type": "grade_announcement", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    # --- Spring Semester ---
    {
        "title_tr": "Bahar Yarıyılı için Ders Kayıtları ve Oryantasyon",
        "title_en": "Course Registration and Orientation for Spring Semester",
        "start_date": "2026-02-16", "end_date": "2026-02-20",
        "entry_type": "registration", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Bahar Yarıyılı Başlangıcı",
        "title_en": "Spring Semester Start",
        "start_date": "2026-02-23", "end_date": None,
        "entry_type": "semester_start", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Kayıt Dondurma Başvuru Dönemi (Bahar)",
        "title_en": "Leave of Absence Application Period (Spring)",
        "start_date": "2026-02-23", "end_date": "2026-04-10",
        "entry_type": "freeze_period", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Ders Ekleme/Bırakma Dönemi (Bahar)",
        "title_en": "Add/Drop Period (Spring)",
        "start_date": "2026-03-02", "end_date": "2026-03-04",
        "entry_type": "add_drop", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Ders Şube Değişikliği (Bahar)",
        "title_en": "Section Change Period (Spring)",
        "start_date": "2026-03-05", "end_date": "2026-03-20",
        "entry_type": "section_change", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Tatil - Ramazan Bayramı (19 Mart Yarım Gün)",
        "title_en": "Holiday - Eid al-Fitr (March 19 Half Day)",
        "start_date": "2026-03-19", "end_date": "2026-03-22",
        "entry_type": "holiday", "applies_to": "all", "academic_year": "2025-2026",
        "notes": "19 Mart Yarım Gün",
    },
    {
        "title_tr": "Ara Sınavlar (Bahar)",
        "title_en": "Midterm Exams (Spring)",
        "start_date": "2026-04-11", "end_date": "2026-04-19",
        "entry_type": "exam_period", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Tatil - Ulusal Egemenlik ve Çocuk Bayramı",
        "title_en": "Holiday - National Sovereignty and Children's Day",
        "start_date": "2026-04-23", "end_date": None,
        "entry_type": "holiday", "applies_to": "all", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Tatil - Emek ve Dayanışma Günü",
        "title_en": "Holiday - Labour Day",
        "start_date": "2026-05-01", "end_date": None,
        "entry_type": "holiday", "applies_to": "all", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Dersten Çekilme için Son Gün (Bahar)",
        "title_en": "Last Day to Withdraw from a Course (Spring)",
        "start_date": "2026-05-08", "end_date": None,
        "entry_type": "withdrawal_deadline", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Tatil - Atatürk'ü Anma, Gençlik ve Spor Bayramı",
        "title_en": "Holiday - Commemoration of Atatürk, Youth and Sports Day",
        "start_date": "2026-05-19", "end_date": None,
        "entry_type": "holiday", "applies_to": "all", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Tatil - Kurban Bayramı (26 Mayıs Yarım Gün Salı)",
        "title_en": "Holiday - Eid al-Adha (May 26 Half Day Tuesday)",
        "start_date": "2026-05-26", "end_date": "2026-05-30",
        "entry_type": "holiday", "applies_to": "all", "academic_year": "2025-2026",
        "notes": "26 Mayıs Yarım Gün",
    },
    {
        "title_tr": "Bahar Yarıyılı Derslerinin Son Günü",
        "title_en": "Last Day of Spring Semester Classes",
        "start_date": "2026-06-05", "end_date": None,
        "entry_type": "semester_end", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "İstanbul Bilgi Üniversitesi Kuruluş Günü",
        "title_en": "Istanbul Bilgi University Foundation Day",
        "start_date": "2026-06-07", "end_date": None,
        "entry_type": "other", "applies_to": "all", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Bahar Yarıyılı Final Sınavları",
        "title_en": "Spring Semester Final Exams",
        "start_date": "2026-06-08", "end_date": "2026-06-20",
        "entry_type": "exam_period", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Not Teslim ve İlanı - Final Sınavları (Bahar)",
        "title_en": "Grade Submission and Announcement - Finals (Spring)",
        "start_date": "2026-06-24", "end_date": None,
        "entry_type": "grade_announcement", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Bütünleme Sınavları (Bahar)",
        "title_en": "Resit Exams (Spring)",
        "start_date": "2026-06-30", "end_date": "2026-07-05",
        "entry_type": "makeup_exam", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Not Teslim ve İlanı - Bütünleme Sınavları (Bahar)",
        "title_en": "Grade Submission and Announcement - Resit Exams (Spring)",
        "start_date": "2026-07-08", "end_date": None,
        "entry_type": "grade_announcement", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Mazeret Başvurularının Son Günü (Bahar Bütünleme)",
        "title_en": "Excuse Application Deadline (Spring Resit)",
        "start_date": "2026-07-08", "end_date": None,
        "entry_type": "other", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Mazeret Komisyonu (Bahar)",
        "title_en": "Excuse Committee Meeting (Spring)",
        "start_date": "2026-07-13", "end_date": None,
        "entry_type": "other", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Yaz Okulu Başlangıcı",
        "title_en": "Summer School Start",
        "start_date": "2026-07-13", "end_date": None,
        "entry_type": "summer_school", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Tatil - Demokrasi ve Milli Birlik Günü",
        "title_en": "Holiday - Democracy and National Unity Day",
        "start_date": "2026-07-15", "end_date": None,
        "entry_type": "holiday", "applies_to": "all", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Mazeret Sınavları (Bahar)",
        "title_en": "Excuse Exams (Spring)",
        "start_date": "2026-07-16", "end_date": "2026-07-17",
        "entry_type": "makeup_exam", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Mezuniyet Törenleri (Tahmini)",
        "title_en": "Graduation Ceremonies (Estimated)",
        "start_date": "2026-07-16", "end_date": "2026-07-19",
        "entry_type": "graduation", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
    {
        "title_tr": "Mazeret Sınavları Not Teslim ve İlanı (Bahar)",
        "title_en": "Excuse Exam Grade Submission and Announcement (Spring)",
        "start_date": "2026-07-20", "end_date": None,
        "entry_type": "grade_announcement", "applies_to": "undergraduate", "academic_year": "2025-2026",
    },
]


def run():
    db = SessionLocal()
    try:
        from sqlalchemy import text
        # Wipe existing data for this academic year to allow safe re-runs
        db.execute(text(
            "DELETE FROM academic_calendar_entries WHERE academic_year = '2025-2026' AND applies_to = 'undergraduate'"
        ))
        db.commit()

        for entry in ENTRIES:
            db.execute(text("""
                INSERT INTO academic_calendar_entries
                    (title_tr, title_en, start_date, end_date, entry_type, applies_to, academic_year, notes)
                VALUES
                    (:title_tr, :title_en, :start_date, :end_date, :entry_type, :applies_to, :academic_year, :notes)
            """), {**entry, "notes": entry.get("notes")})
        db.commit()
        print(f"✅  Seeded {len(ENTRIES)} academic calendar entries for 2025-2026 (undergraduate).")
    finally:
        db.close()


if __name__ == "__main__":
    run()