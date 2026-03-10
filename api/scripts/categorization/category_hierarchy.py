"""
Category hierarchy definition.

TREE maps parent_category → [child categories].
Leaf categories are the values already stored in knowledge_base.category.
Parent categories are virtual groupings used for broad search scoping.

Search traversal:
  - Narrow:  WHERE category = 'faculty_engineering'
  - Mid:     WHERE parent_category = 'academic'
  - Broad:   no filter
"""

TREE: dict[str, list[str]] = {
    "academic": [
        "faculty_engineering",
        "faculty_engineering_dept",
        "faculty_engineering_programs",
        "faculty_engineering_research",
        "faculty_communication",
        "faculty_communication_dept",
        "faculty_communication_programs",
        "faculty_communication_research",
        "faculty_social_sciences",
        "faculty_social_sciences_dept",
        "faculty_social_sciences_programs",
        "faculty_social_sciences_research",
        "faculty_business",
        "faculty_business_dept",
        "faculty_business_programs",
        "faculty_business_research",
        "faculty_health",
        "faculty_health_dept",
        "faculty_health_programs",
        "faculty_health_research",
        "faculty_applied_sciences",
        "faculty_applied_sciences_dept",
        "faculty_applied_sciences_programs",
        "faculty_applied_sciences_research",
        "faculty_architecture",
        "faculty_architecture_dept",
        "faculty_architecture_programs",
        "faculty_architecture_research",
        "faculty_law",
        "faculty_law_dept",
        "faculty_law_programs",
        "faculty_law_research",
        "faculty_informatics",
        "faculty_informatics_dept",
        "faculty_informatics_programs",
        "faculty_informatics_research",
        "faculty_general_ed",
        "faculty_other",
        "program_graduate_tr",
        "program_graduate_en",
        "program_vocational_tr",
        "program_vocational_en",
        "language_program",
        "course_catalog",
        "staff_profile",
    ],
    "content": [
        "news_tr",
        "news_en",
        "event_tr",
        "event_en",
    ],
    "regulation": [
        "regulation",
        "regulation_document",
    ],
    "document": [
        "doc_erasmus",
        "doc_petition",
        "doc_thesis",
        "doc_internship",
        "doc_brochure",
        "doc_psychology",
        "doc_club",
        "doc_report",
        "doc_form",
        "document",
    ],
    "institutional": [
        "university",
        "quality",
        "research",
        "tenders",
        "hr",
        "career",
        "alumni",
        "distance_ed",
    ],
    "campus_life": [
        "student_life",
        "international",
    ],
}

# Derived: child → parent lookup
PARENT: dict[str, str] = {
    child: parent
    for parent, children in TREE.items()
    for child in children
}


def get_parent(category: str) -> str | None:
    return PARENT.get(category)


def get_children(parent: str) -> list[str]:
    return TREE.get(parent, [])


def get_scope(category: str) -> list[str]:
    """Return category + all siblings (i.e. the full parent bucket) for broad search."""
    parent = PARENT.get(category)
    if parent:
        return TREE[parent]
    return [category]
