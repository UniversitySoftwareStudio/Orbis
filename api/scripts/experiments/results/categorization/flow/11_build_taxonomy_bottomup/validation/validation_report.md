# Taxonomy Validation Report

- leaves validated: **91**
- good: **0** | mixed: **0** | bad: **2**
- avg fit score: **0.200**
- provider: `outlier` / sample_size: `15`

## Leaves Needing Attention

| Verdict | Leaf | Top | Docs | Fit | Suggestion |
|---|---|---|---:|---:|---|
| `bad` | Academic Staff Profiles And Publications | people | 4,777 | 0.15 | split: This leaf is a catch-all for bilgi.edu.tr university  |
| `bad` | Accreditation And Institutional Evaluation Re | quality | 4,763 | 0.25 | split: Create a narrow leaf 'Institutional Internal Evaluati |

## Issue Details

### `people/academic_staff_profiles/Academic Staff Profiles And Publications`
- doc_count: 4,777 | fit: 0.15 | verdict: bad
- suggestion: split: This leaf is a catch-all for bilgi.edu.tr university pages. Only ~2-3 of 15 samples match 'Academic Staff Profiles' (e.g., Akademik Kadro pages). The rest should be split into separate leaves such as 'University Procurement/Tenders', 'International Office & Exchange Programs', 'Campus Services', 'Career & Talent Services', and 'Academic Programs'. Alternatively, relabel as a broader 'University Website Pages' leaf under an 'organizations' or 'education' top category.
- issues:
  - {'title': 'İstanbul Bilgi Üniversitesi - Bilgisayar Alım İhalesi', 'reason': 'Procurement/tender page, not academic staff profiles or publications'}
  - {'title': 'Staj Ofisi', 'reason': 'Internship office page, unrelated to academic staff profiles'}
  - {'title': 'Başvuru', 'reason': 'International exchange program application page, not academic staff'}
  - {'title': 'Etkinlikler', 'reason': 'International office events page, not academic staff profiles'}
  - {'title': 'English Language Skills Courses', 'reason': 'Language course page, not academic staff profiles'}
  - {'title': 'Kampüsler Çatı ve İzolasyon Yapımı İşleri İhalesi', 'reason': 'Construction tender page, entirely unrelated'}
  - {'title': 'Shuttle', 'reason': 'Campus transportation page, not academic staff profiles'}
  - {'title': 'Gelen Öğrenci', 'reason': 'Incoming student exchange page, not academic staff'}
  - {'title': 'BİLGİ Talent / Etkinlikler', 'reason': 'Career/talent events page, not academic staff profiles'}
  - {'title': 'Öğrenim Hareketliliği', 'reason': 'Erasmus learning mobility FAQ, not academic staff'}
  - {'title': 'Gelen Personel', 'reason': 'Incoming Erasmus staff mobility page, not staff profiles/publications'}
  - {'title': 'Giden Personel', 'reason': 'Outgoing Erasmus staff mobility page, not staff profiles/publications'}

### `quality/accreditation_and_evaluation_reports/Accreditation And Institutional Evaluation Reports`
- doc_count: 4,763 | fit: 0.25 | verdict: bad
- suggestion: split: Create a narrow leaf 'Institutional Internal Evaluation Reports (Kurum İç Değerlendirme Raporları)' for actual evaluation reports, and merge the remaining general university pages into a broader leaf like 'University Website Content' or 'merge:general_university_pages'. The current leaf is being used as a catch-all for bilgi.edu.tr content.
- issues:
  - {'title': '2022-2023 Undergraduate Student Handbook-Revised', 'reason': 'Student handbook, not an accreditation or evaluation report'}
  - {'title': 'Hakkında', 'reason': "Generic 'About' page for a university department (Genetics and Bioengineering), not an evaluation report"}
  - {'title': "Director's Office", 'reason': 'Administrative page for a vocational school, not an accreditation report'}
  - {'title': 'Academic Staff', 'reason': 'Staff listing page, not an accreditation or evaluation report'}
  - {'title': 'Enerji Sistemleri Mühendisliği Bölümü', 'reason': 'Department page for Energy Systems Engineering, not an evaluation report'}
  - {'title': 'About', 'reason': "Generic 'About' pages for vocational school departments, not accreditation reports (appears twice)"}
  - {'title': 'bilgi_2021_2022_ogrenci_el_kitabi_lisans_onlisans_e_4', 'reason': 'Student handbook, not an evaluation report'}
  - {'title': 'Yalnizlik', 'reason': "'Loneliness' - unclear relation to accreditation or evaluation"}
  - {'title': 'Dış Fonlu Öğrenci Projeleri', 'reason': 'Externally funded student projects page, not an evaluation report'}
  - {'title': '2019-2020 Bitirme Projeleri', 'reason': 'Graduation projects page, not an accreditation report'}
  - {'title': 'Kurum Ic Degerlendirme Raporu 2015', 'reason': 'Institutional internal evaluation report - this fits'}
  - {'title': 'Kurum Ic Degerlendirme Raporu 2016', 'reason': 'Institutional internal evaluation report - this fits'}
  - {'title': 'Kurum Ic Degerlendirme Raporu 2018', 'reason': 'Institutional internal evaluation report - this fits'}
  - {'title': 'Report Pdf', 'reason': "Likely an evaluation report based on URL containing 'kurum-ic-degerlendirme-raporu' - this fits"}

## All Leaves

| Verdict | Top | Sub | Leaf | Docs | Fit |
|---|---|---|---|---:|---:|
| ? `error` | academics | aviation_management_courses | Aviation Management And Cabin Services Course | 224 | — |
| ? `error` | academics | business_courses | Business Administration Course Catalog | 1,122 | — |
| ? `error` | academics | child_development_department | Child Development Department Programs And Eve | 310 | — |
| ? `error` | academics | clinical_psychology_program | Clinical Psychology Graduate Program | 728 | — |
| ? `error` | academics | cultural_management_programs | Arts Culture And Cultural Studies Programs An | 1,443 | — |
| ? `error` | academics | design_and_architecture_courses | Design And Architecture Course Catalog Turkis | 490 | — |
| ? `error` | academics | engineering_and_natural_sciences | Engineering And Natural Sciences Faculty Prog | 1,364 | — |
| ? `error` | academics | engineering_courses | Engineering And Computing Course Catalog | 986 | — |
| ? `error` | academics | english_language_programs | English Language And Literature Programs And  | 899 | — |
| ? `error` | academics | english_preparatory_program | English Preparatory Program Handbook | 426 | — |
| ? `error` | academics | faculty_of_applied_sciences | Applied Sciences Faculty Staff And Programs | 284 | — |
| ? `error` | academics | faculty_of_architecture | Faculty Of Architecture Programs | 1,244 | — |
| ? `error` | academics | faculty_of_business | Faculty Of Business Graduate Programs | 1,198 | — |
| ? `error` | academics | faculty_of_health_sciences | Faculty Of Health Sciences Staff And Programs | 438 | — |
| ? `error` | academics | faculty_of_law | Faculty Of Law Programs And Courses | 1,091 | — |
| ? `error` | academics | film_and_television_courses | Film Television And Media Programs And Course | 646 | — |
| ? `error` | academics | finance_and_economics_programs | Banking Finance And Economics Programs | 325 | — |
| ? `error` | academics | game_design_department | Digital Game Design Courses And Program | 180 | — |
| ? `error` | academics | gastronomy_and_culinary_courses | Gastronomy And Culinary Arts Courses | 338 | — |
| ? `error` | academics | graduate_programs | Phd In Business Administration Program | 1,242 | — |
| ? `error` | academics | health_services_courses | Vocational School Of Health Services Courses | 494 | — |
| ? `error` | academics | marketing_communication_program | Ma In Marketing Communication Program | 319 | — |
| ? `error` | academics | music_department | Music Department Courses And Programs | 249 | — |
| ? `error` | academics | nutrition_and_dietetics_courses | Nutrition And Dietetics Courses | 181 | — |
| ? `error` | academics | opticianry_program | Opticianry Program Courses And Info | 100 | — |
| ? `error` | academics | physiotherapy_program | Physiotherapy And Rehabilitation Department | 559 | — |
| ? `error` | academics | political_science_courses | International Relations And Political Science | 424 | — |
| ? `error` | academics | political_science_programs | Political Science Graduate Programs | 991 | — |
| ? `error` | academics | program_brochures | Academic Program Brochures | 989 | — |
| ? `error` | academics | psychology_programs | Organizational Psychology Program And Staff | 327 | — |
| ? `error` | academics | senior_design_projects | Engineering And Design Senior Project Courses | 632 | — |
| ? `error` | academics | social_responsibility_courses | Social Responsibility And Sustainability Cour | 392 | — |
| ? `error` | academics | sports_management_department | Sports Management Department News And Events | 175 | — |
| ? `error` | academics | trauma_and_mental_health_program | Trauma And Disaster Mental Health Graduate Pr | 212 | — |
| ? `error` | academics | turkish_german_law_program | Turkish German Economic Law Joint Llm Program | 248 | — |
| ? `error` | academics | university_overview | University Overview And General Academic Info | 1,655 | — |
| ? `error` | academics | vocational_school_programs | Vocational And Health Services School Program | 608 | — |
| ? `error` | administration | campus_planning_records | Campus Site Plans And Survey Records | 173 | — |
| ? `error` | administration | institutional_policies_and_forms | Institutional Policies Tenders And Consent Fo | 394 | — |
| ? `error` | admissions | english_language_admissions | English Language Programs Admission And Faq | 734 | — |
| ? `error` | admissions | international_student_admissions | International Student Admission Procedures | 86 | — |
| ? `error` | admissions | special_talent_exam_results | Special Talent Exam Results For Arts Programs | 130 | — |
| ? `error` | admissions | university_of_london_application | University Of London Honours Application Proc | 364 | — |
| ? `error` | events | academic_conferences | Academic Conferences And Events Archive | 976 | — |
| ? `error` | events | events_archive | All Events Archive | 558 | — |
| ? `error` | events | exhibitions | Art And Design Exhibitions | 305 | — |
| ? `error` | events | faculty_events | Sociology And Social Sciences Faculty Events | 531 | — |
| ? `error` | events | fashion_show | Bilgi Fashion Show Events | 209 | — |
| ? `error` | events | film_festival | International Crime And Punishment Film Festi | 298 | — |
| ? `error` | events | law_symposium | Mediation Symposium Proceedings | 157 | — |
| ? `error` | international | bilateral_exchange_programs | Partner Universities For Exchange Programs | 274 | — |
| ? `error` | international | erasmus_grant_agreements | Erasmus Grant Agreement For Multiple Benefici | 252 | — |
| ? `error` | international | erasmus_internship_mobility | Erasmus Internship And Traineeship Mobility | 478 | — |
| ? `error` | international | erasmus_language_exam | Erasmus English Language Exam Announcement | 88 | — |
| ? `error` | international | erasmus_mobility_results | Erasmus Mobility Application Results | 1,363 | — |
| ? `error` | international | erasmus_orientation | Erasmus Student Orientation Presentations | 499 | — |
| ? `error` | international | erasmus_programs | Erasmus Study Mobility Programs | 2,011 | — |
| ? `error` | international | erasmus_staff_mobility | Erasmus Outgoing Staff Mobility Programs | 240 | — |
| ? `error` | international | erasmus_study_quotas | Erasmus Study Mobility Quota Lists | 939 | — |
| ? `error` | people | academic_staff | Academic Staff Directory | 1,701 | — |
| ✗ `bad` | people | academic_staff_profiles | Academic Staff Profiles And Publications | 4,777 | 0.15 |
| ? `error` | people | research_assistant_evaluations | Research Assistant Evaluation Forms | 767 | — |
| ? `error` | people | staff_contact_information | Academic Staff Contact Information | 902 | — |
| ✗ `bad` | quality | accreditation_and_evaluation_reports | Accreditation And Institutional Evaluation Re | 4,763 | 0.25 |
| ? `error` | quality | administrative_unit_assessment_guide | Administrative Unit Learning Outcomes Assessm | 98 | — |
| ? `error` | quality | distance_education_quality_reports | Distance Education Quality And Evaluation Rep | 196 | — |
| ? `error` | quality | environmental_impact_assessment | Environmental And Community Service Impact As | 90 | — |
| ? `error` | quality | external_evaluation_reports | Project Evaluation And Assessment Reports | 219 | — |
| ? `error` | quality | learning_outcomes_assessment | Learning Outcomes Assessment Planning Guide | 306 | — |
| ? `error` | quality | program_evaluation_reports | Civil Society And Sectoral Collaboration Eval | 180 | — |
| ? `error` | quality | quality_assurance_guides | Quality Assurance And Institutional Reports | 498 | — |
| ? `error` | quality | teaching_effectiveness_guide | Teaching Effectiveness Guide | 441 | — |
| ? `error` | quality | wscuc_accreditation_reports | Wscuc Accreditation And Program Review Report | 555 | — |
| ? `error` | regulations | academic_regulations | Undergraduate And Graduate Academic Regulatio | 804 | — |
| ? `error` | regulations | double_major_minor_regulations | Double Major Minor And Honors Program Regulat | 586 | — |
| ? `error` | regulations | financial_contractual_terms | Financial And Contractual Terms And Condition | 132 | — |
| ? `error` | regulations | student_handbooks | Undergraduate And Graduate Student Handbooks | 1,075 | — |
| ? `error` | research | child_studies_impact_report | Child Studies Unit Impact Analysis Report | 128 | — |
| ? `error` | research | civil_society_studies | Civil Society Exchange Program Evaluation | 151 | — |
| ? `error` | research | frascati_manual | Frascati Manual And R&D Classification Guidel | 2,013 | — |
| ? `error` | research | funded_research_projects | Researchers And Funded Research Projects | 447 | — |
| ? `error` | research | gender_violence_training_report | Anti Discrimination And Violence Training Imp | 182 | — |
| ? `error` | research | law_publications | Legal Research Publications On Covid 19 | 958 | — |
| ? `error` | research | project_writing_guide | Lpe Project Writing Manual | 124 | — |
| ? `error` | research | social_incubation_center | Social Incubation Center Reports And Evaluati | 289 | — |
| ? `error` | research | thesis_writing_guide | Thesis Writing Manual For English Programs | 175 | — |
| ? `error` | student_life | community_service_projects | Community Service And Social Responsibility P | 1,264 | — |
| ? `error` | student_life | counseling_resources | Student Counseling And Wellness Resources | 1,009 | — |
| ? `error` | student_life | frequently_asked_questions | Student Frequently Asked Questions | 385 | — |
| ? `error` | student_life | internship_offers | Internship And Job Offers For Students | 349 | — |
| ? `error` | student_life | student_clubs | Student Clubs And Campus Life | 360 | — |
