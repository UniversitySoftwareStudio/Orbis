"""
Step 2: Categorize URLs by deterministic prefix rules.

Outputs:
  url_clusters.json   — [{url, path, category}] for all 17k URLs
  cluster_samples.json — {category: [urls]} for review

KMeans sub-clustering can be applied later within any individual category
once the top-level categorization is applied to the DB.
"""

import json
import os
from collections import defaultdict

OUTPUT_DIR = os.path.dirname(__file__)
EMBEDDINGS_FILE = os.path.join(OUTPUT_DIR, "url_embeddings.json")
CLUSTERS_FILE = os.path.join(OUTPUT_DIR, "url_clusters.json")
SAMPLES_FILE = os.path.join(OUTPUT_DIR, "cluster_samples.json")


FACULTY_TR: dict[str, str] = {
    "muhendislik-ve-doga-bilimleri-fakultesi": "faculty_engineering",
    "iletisim-fakultesi": "faculty_communication",
    "sosyal-ve-beseri-bilimler-fakultesi": "faculty_social_sciences",
    "isletme-fakultesi": "faculty_business",
    "saglik-bilimleri-fakultesi": "faculty_health",
    "uygulamali-bilimler-fakultesi": "faculty_applied_sciences",
    "mimarlik-fakultesi": "faculty_architecture",
    "hukuk-fakultesi": "faculty_law",
    "bilisim-teknolojisi-yuksekokulu": "faculty_informatics",
    "genel-egitim-bolumu": "faculty_general_ed",
}

FACULTY_EN: dict[str, str] = {
    "faculty-of-engineering-and-natural-sciences": "faculty_engineering",
    "faculty-of-communication": "faculty_communication",
    "faculty-of-social-sciences-and-humanities": "faculty_social_sciences",
    "faculty-of-business": "faculty_business",
    "faculty-of-health-sciences": "faculty_health",
    "faculty-of-applied-sciences": "faculty_applied_sciences",
    "faculty-of-architecture": "faculty_architecture",
    "faculty-of-law": "faculty_law",
    "school-of-informatics-technology": "faculty_informatics",
    "general-education-department": "faculty_general_ed",
}

VOCATIONAL_TR = {
    "meslek-yuksekokulu",
    "saglik-hizmetleri-meslek-yuksekokulu",
    "adalet-meslek-yuksekokulu",
}
VOCATIONAL_EN = {
    "school-of-advanced-vocational-studies",
    "vocational-school-of-health-services",
    "vocational-school-of-justice",
}
LANG_PROGRAM = {
    "ingilizce-hazirlik-programi",
    "yabanci-dil-programlari",
    "english-language-programs",
    "foreign-language-programs",
}


# Path segments that unambiguously identify a regulations/policy page.
# Checked as exact segment matches to avoid false positives from news slugs.
REGULATION_SEGMENTS = {
    # EN
    "rules-and-regulations",
    "regulations-and-directives",
    "procedures-and-principles",
    "institutional-principles",
    "general-rules",
    "code-of-conduct-and-ethical-principles",
    "regulation",
    # TR
    "yonetmelik-ve-yonergeler",
    "usul-ve-esaslar",
    "kurumsal-ilkeler",
    "genel-kurallar",
    "davranis-ilkeleri-ve-etik-kurallar",
    "yonerge",          # standalone segment: /arastirma/*/yonerge/
    "arastirma-politikasi",
    "insan-kaynaklari-politikamiz",
}

# Keywords checked against the full URL for document (PDF) URLs only.
REGULATION_DOC_KEYWORDS = [
    "yonetmelik", "yönetmelik",
    "yonerge", "yönerge",
    "regulation",
    "handbook", "el-kitabi",
    "by-laws", "bylaw",
    "statute", "tuzuk", "tüzük",
    "kurallar",
]

# Sub-categories for document URLs — checked in order against the filename slug.
# First match wins.
DOC_SUBCATEGORIES: list[tuple[str, list[str]]] = [
    ("doc_erasmus", [
        "erasmus", "hareketlilik", "learning-agreement", "exchange-permission",
        "staff-exchange", "study-mobility", "ogrenim-hareketliligi",
        "staj-hareketliligi", "trainee", "traineeship",
        "kredi-transfer", "partner-universities", "erasmus-code",
        "ikili-degisim", "commitment-letter", "taahhutname",
        "mobility", "exchange",
    ]),
    ("doc_petition", [
        "petition", "dilekce", "dilekcesi", "mazeret-izni",
        "itiraz-dilekcesi", "kayit-sildirme", "kayit-actirma",
        "muafiyet-formu", "ders-ekleme", "ders-muafiyet",
        "add-and-drop", "add-course", "drop-course",
    ]),
    ("doc_thesis", [
        "thesis", "tez-", "-tez-", "doktora-programi", "doktora-yeterlik",
        "tezli-yuksek-lisans", "tezsiz-yuksek-lisans",
        "tez-izleme", "tez-savunma", "tez-konusu", "tez-teslim",
        "tez-juri", "tez-calismasi",
    ]),
    ("doc_internship", [
        "internship", "-staj-", "staj-degerlendirme",
        "mimarlik_stajlar", "work-placement", "klinik-rotasyon",
        "learning-traineeships", "staj-formlari",
    ]),
    ("doc_brochure", [
        "brosur", "brochure", "flyer", "tanitim", "katalog",
        "catalog", "presentation", "sunum", "orientation",
        "oryantasyon", "buddy-program",
    ]),
    ("doc_psychology", [
        "pdb", "psikoloji", "psychological", "counseling",
        "danismanlik", "mental", "anxiety", "depression",
        "motivasyon", "psikoegitim",
    ]),
    ("doc_club", [
        "kulubu", "_club", "student_club", "student-club",
        "sosyal-sorumluluk-kulupler", "sosyalsorumluluk",
        "genclik", "youth_", "_tog", "bilgitog", "kizilay",
    ]),
    ("doc_report", [
        "rapor", "-report", "sip-report", "ic-degerlendirme",
        "kurum-ic", "prme-", "annual-report",
    ]),
    ("doc_form", [
        "-form", "_form", "form-", "basvuru", "application-form",
        "application_form", "degerlendirme-formu", "on-deg",
        "ar-gor", "ogr-gor",
    ]),
]


def categorize_document(url_lower: str) -> str:
    """Sub-classify a document URL by filename keyword matching."""
    filename = url_lower.split("/")[-1]
    for sub_cat, keywords in DOC_SUBCATEGORIES:
        if any(kw in filename for kw in keywords):
            return sub_cat
    return "document"


_FACULTY_DEPT_SEGS = {
    "bolumler", "bolum", "departments", "department",
    "bolum-baskanligimiz",
}
_FACULTY_PROGRAM_SEGS = {
    "lisans-programlari", "undergraduate-programs", "lisans",
    "undergraduate", "onlisans-programlari",
}
_FACULTY_RESEARCH_SEGS = {
    "arastirma", "research", "arastirma-merkezleri",
    "research-centers", "projeler", "projects",
    "yayinlar", "publications",
}
_FACULTY_GENERAL_SEGS = {
    "hakkimizda", "about", "dekanlik", "iletisim", "contact",
    "harita", "brosur", "tanitim",
}


def _faculty_subpage(faculty: str, depth3: str, depth4: str) -> str:
    """Return faculty sub-category based on depth-3/4 path segments."""
    if depth3 in _FACULTY_DEPT_SEGS or depth4 in _FACULTY_DEPT_SEGS:
        return f"{faculty}_dept"
    if depth3 in _FACULTY_PROGRAM_SEGS or depth4 in _FACULTY_PROGRAM_SEGS:
        return f"{faculty}_programs"
    if depth3 in _FACULTY_RESEARCH_SEGS or depth4 in _FACULTY_RESEARCH_SEGS:
        return f"{faculty}_research"
    return faculty


def categorize(url: str) -> str:
    raw = url.replace("https://", "").replace("http://", "").split("?")[0]
    parts = raw.split("/")
    domain = parts[0]
    segs = [p for p in parts[1:] if p]

    if "ects.bilgi.edu.tr" in domain:
        return "course_catalog"

    if not segs:
        return "other"

    # Documents — PDFs/uploads
    if segs[0] in ("media", "site_media") or segs[0] == "upload":
        url_lower = raw.lower()
        if any(kw in url_lower for kw in REGULATION_DOC_KEYWORDS):
            return "regulation_document"
        return categorize_document(url_lower)

    # Web pages — check for regulation segments BEFORE other category rules
    # (overrides quality/university/student_life/faculty if a later segment matches)
    if any(seg in REGULATION_SEGMENTS for seg in segs):
        return "regulation"

    lang = segs[0]   # "tr" or "en"
    sec = segs[1] if len(segs) > 1 else ""
    sub = segs[2] if len(segs) > 2 else ""
    deep = segs[3] if len(segs) > 3 else ""

    # ── News & Events (split by language) ─────────────────────────────────────
    if sec in ("haber", "haberler-duyurular-arsivi"):
        return "news_tr"
    if sec in ("etkinlik", "etkinlikler-arsivi"):
        return "event_tr"
    if sec in ("news", "news-and-announcements-archive"):
        return "news_en"
    if sec in ("event", "events-archive"):
        return "event_en"

    # ── Staff (profile vs publications) ───────────────────────────────────────
    if sec == "staff":
        return "staff_publications" if deep == "publications" else "staff_profile"
    if sec == "akademik" and sub == "kadro":
        return "staff_publications" if deep == "yayimlar" else "staff_profile"
    if sec == "academic" and sub == "staff":
        return "staff_publications" if deep == "publications" else "staff_profile"

    # ── Graduate programs (by language) ───────────────────────────────────────
    if sec == "akademik" and sub == "lisansustu":
        return "program_graduate_tr"
    if sec == "academic" and sub == "graduate":
        return "program_graduate_en"

    # ── Vocational programs (by language) ─────────────────────────────────────
    if sec == "akademik" and sub in VOCATIONAL_TR:
        return "program_vocational_tr"
    if sec == "academic" and sub in VOCATIONAL_EN:
        return "program_vocational_en"

    # ── Language programs ─────────────────────────────────────────────────────
    if sec in ("akademik", "academic") and sub in LANG_PROGRAM:
        return "language_program"

    # ── Faculties (named) ─────────────────────────────────────────────────────
    if sec == "akademik" and sub in FACULTY_TR:
        fac = FACULTY_TR[sub]
        return _faculty_subpage(fac, deep, segs[4] if len(segs) > 4 else "")
    if sec == "academic" and sub in FACULTY_EN:
        fac = FACULTY_EN[sub]
        return _faculty_subpage(fac, deep, segs[4] if len(segs) > 4 else "")
    if sec in ("akademik", "academic"):
        return "faculty_other"

    # ── International ─────────────────────────────────────────────────────────
    if sec == "international":
        return "international"

    # ── Student life ──────────────────────────────────────────────────────────
    if sec in ("yasam", "life-at-bilgi", "student-life"):
        return "student_life"

    # ── University (institutional) ────────────────────────────────────────────
    if sec in ("universite", "university"):
        return "university"

    # ── Research ──────────────────────────────────────────────────────────────
    if sec == "arastirma":
        return "research"

    # ── Tenders ───────────────────────────────────────────────────────────────
    if sec == "ihaleler":
        return "tenders"

    # ── Quality ───────────────────────────────────────────────────────────────
    if sec in ("kalite", "quality"):
        return "quality"

    # ── HR ────────────────────────────────────────────────────────────────────
    if sec in ("ik", "calisan"):
        return "hr"

    # ── Alumni ────────────────────────────────────────────────────────────────
    if sec in ("mezun", "alumni"):
        return "alumni"

    # ── Talent / Career ───────────────────────────────────────────────────────
    if sec in ("talent", "is-olanaklari", "job-vacancies"):
        return "career"

    # ── Distance education ────────────────────────────────────────────────────
    if sec == "uzem":
        return "distance_ed"

    return "other"


def main():
    print("Loading URLs...")
    with open(EMBEDDINGS_FILE) as f:
        data = json.load(f)

    clusters_out = [
        {"url": d["url"], "path": d["path"], "category": categorize(d["url"])}
        for d in data
    ]

    with open(CLUSTERS_FILE, "w") as f:
        json.dump(clusters_out, f, indent=2, ensure_ascii=False)

    by_cat: defaultdict[str, list[str]] = defaultdict(list)
    for item in clusters_out:
        by_cat[item["category"]].append(item["url"])

    samples = {
        cat: sorted(set(lurls))
        for cat, lurls in sorted(by_cat.items())
    }
    with open(SAMPLES_FILE, "w") as f:
        json.dump(samples, f, indent=2, ensure_ascii=False)

    print("\nCategory sizes:")
    for cat, lurls in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        print(f"  {cat:<25s}: {len(set(lurls)):5d} URLs")
    print(f"\nTotal: {len(clusters_out)}")
    print(f"\nDone. Review {SAMPLES_FILE}, then run apply_categories.py.")


if __name__ == "__main__":
    main()
