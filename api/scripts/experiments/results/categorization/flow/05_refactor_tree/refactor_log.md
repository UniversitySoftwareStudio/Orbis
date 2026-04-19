# Step 05 — Taxonomy Refactor Log

## Summary

- input: `scripts/experiments/results/categorization/flow/05_refactor_tree/refined_tree.json`
- LLM provider: `outlier` / model: `claude-opus-4-6`
- iterations run: `1`
- ai_calls: `1` errors: `1`
- initial tree: `10` top / `91` sub / `91` leaves / `60,516` docs
- final tree:   `10` top / `91` sub / `91` leaves / `60,516` docs

## Iteration 1

- before: `10` top / `91` sub / `91` leaves
- after:  `10` top / `91` sub / `91` leaves
- quality_assessment: AI error: outlier_error:Remote end closed connection without response
- **AI error**: `outlier_error:Remote end closed connection without response`

*(no operations)*

## Final Tree

| Top | Sub | Leaf | Docs |
|---|---|---|---:|
| `academics` | `aviation_management_courses` | Aviation Management And Cabin Services Courses | 224 |
| `academics` | `business_courses` | Business Administration Course Catalog | 1,122 |
| `academics` | `child_development_department` | Child Development Department Programs And Events | 310 |
| `academics` | `clinical_psychology_program` | Clinical Psychology Graduate Program | 728 |
| `academics` | `cultural_management_programs` | Arts Culture And Cultural Studies Programs And Courses | 1,443 |
| `academics` | `design_and_architecture_courses` | Design And Architecture Course Catalog Turkish | 490 |
| `academics` | `engineering_and_natural_sciences` | Engineering And Natural Sciences Faculty Programs And Projects | 1,364 |
| `academics` | `engineering_courses` | Engineering And Computing Course Catalog | 986 |
| `academics` | `english_language_programs` | English Language And Literature Programs And Courses | 899 |
| `academics` | `english_preparatory_program` | English Preparatory Program Handbook | 426 |
| `academics` | `faculty_of_applied_sciences` | Applied Sciences Faculty Staff And Programs | 284 |
| `academics` | `faculty_of_architecture` | Faculty Of Architecture Programs | 1,244 |
| `academics` | `faculty_of_business` | Faculty Of Business Graduate Programs | 1,198 |
| `academics` | `faculty_of_health_sciences` | Faculty Of Health Sciences Staff And Programs | 438 |
| `academics` | `faculty_of_law` | Faculty Of Law Programs And Courses | 1,091 |
| `academics` | `film_and_television_courses` | Film Television And Media Programs And Courses | 646 |
| `academics` | `finance_and_economics_programs` | Banking Finance And Economics Programs | 325 |
| `academics` | `game_design_department` | Digital Game Design Courses And Program | 180 |
| `academics` | `gastronomy_and_culinary_courses` | Gastronomy And Culinary Arts Courses | 338 |
| `academics` | `graduate_programs` | Phd In Business Administration Program | 1,242 |
| `academics` | `health_services_courses` | Vocational School Of Health Services Courses | 494 |
| `academics` | `marketing_communication_program` | Ma In Marketing Communication Program | 319 |
| `academics` | `music_department` | Music Department Courses And Programs | 249 |
| `academics` | `nutrition_and_dietetics_courses` | Nutrition And Dietetics Courses | 181 |
| `academics` | `opticianry_program` | Opticianry Program Courses And Info | 100 |
| `academics` | `physiotherapy_program` | Physiotherapy And Rehabilitation Department | 559 |
| `academics` | `political_science_courses` | International Relations And Political Science Courses | 424 |
| `academics` | `political_science_programs` | Political Science Graduate Programs | 991 |
| `academics` | `program_brochures` | Academic Program Brochures | 989 |
| `academics` | `psychology_programs` | Organizational Psychology Program And Staff | 327 |
| `academics` | `senior_design_projects` | Engineering And Design Senior Project Courses | 632 |
| `academics` | `social_responsibility_courses` | Social Responsibility And Sustainability Courses | 392 |
| `academics` | `sports_management_department` | Sports Management Department News And Events | 175 |
| `academics` | `trauma_and_mental_health_program` | Trauma And Disaster Mental Health Graduate Program | 212 |
| `academics` | `turkish_german_law_program` | Turkish German Economic Law Joint Llm Program | 248 |
| `academics` | `university_overview` | University Overview And General Academic Information | 1,655 |
| `academics` | `vocational_school_programs` | Vocational And Health Services School Programs And Info | 608 |
| `administration` | `campus_planning_records` | Campus Site Plans And Survey Records | 173 |
| `administration` | `institutional_policies_and_forms` | Institutional Policies Tenders And Consent Forms | 394 |
| `admissions` | `english_language_admissions` | English Language Programs Admission And Faq | 734 |
| `admissions` | `international_student_admissions` | International Student Admission Procedures | 86 |
| `admissions` | `special_talent_exam_results` | Special Talent Exam Results For Arts Programs | 130 |
| `admissions` | `university_of_london_application` | University Of London Honours Application Process | 364 |
| `events` | `academic_conferences` | Academic Conferences And Events Archive | 976 |
| `events` | `events_archive` | All Events Archive | 558 |
| `events` | `exhibitions` | Art And Design Exhibitions | 305 |
| `events` | `faculty_events` | Sociology And Social Sciences Faculty Events | 531 |
| `events` | `fashion_show` | Bilgi Fashion Show Events | 209 |
| `events` | `film_festival` | International Crime And Punishment Film Festival | 298 |
| `events` | `law_symposium` | Mediation Symposium Proceedings | 157 |
| `international` | `bilateral_exchange_programs` | Partner Universities For Exchange Programs | 274 |
| `international` | `erasmus_grant_agreements` | Erasmus Grant Agreement For Multiple Beneficiaries | 252 |
| `international` | `erasmus_internship_mobility` | Erasmus Internship And Traineeship Mobility | 478 |
| `international` | `erasmus_language_exam` | Erasmus English Language Exam Announcement | 88 |
| `international` | `erasmus_mobility_results` | Erasmus Mobility Application Results | 1,363 |
| `international` | `erasmus_orientation` | Erasmus Student Orientation Presentations | 499 |
| `international` | `erasmus_programs` | Erasmus Study Mobility Programs | 2,011 |
| `international` | `erasmus_staff_mobility` | Erasmus Outgoing Staff Mobility Programs | 240 |
| `international` | `erasmus_study_quotas` | Erasmus Study Mobility Quota Lists | 939 |
| `people` | `academic_staff` | Academic Staff Directory | 1,701 |
| `people` | `academic_staff_profiles` | Academic Staff Profiles And Publications | 4,777 |
| `people` | `research_assistant_evaluations` | Research Assistant Evaluation Forms | 767 |
| `people` | `staff_contact_information` | Academic Staff Contact Information | 902 |
| `quality` | `accreditation_and_evaluation_reports` | Accreditation And Institutional Evaluation Reports | 4,763 |
| `quality` | `administrative_unit_assessment_guide` | Administrative Unit Learning Outcomes Assessment Guide | 98 |
| `quality` | `distance_education_quality_reports` | Distance Education Quality And Evaluation Reports | 196 |
| `quality` | `environmental_impact_assessment` | Environmental And Community Service Impact Assessment | 90 |
| `quality` | `external_evaluation_reports` | Project Evaluation And Assessment Reports | 219 |
| `quality` | `learning_outcomes_assessment` | Learning Outcomes Assessment Planning Guide | 306 |
| `quality` | `program_evaluation_reports` | Civil Society And Sectoral Collaboration Evaluations | 180 |
| `quality` | `quality_assurance_guides` | Quality Assurance And Institutional Reports | 498 |
| `quality` | `teaching_effectiveness_guide` | Teaching Effectiveness Guide | 441 |
| `quality` | `wscuc_accreditation_reports` | Wscuc Accreditation And Program Review Reports | 555 |
| `regulations` | `academic_regulations` | Undergraduate And Graduate Academic Regulations | 804 |
| `regulations` | `double_major_minor_regulations` | Double Major Minor And Honors Program Regulations | 586 |
| `regulations` | `financial_contractual_terms` | Financial And Contractual Terms And Conditions | 132 |
| `regulations` | `student_handbooks` | Undergraduate And Graduate Student Handbooks | 1,075 |
| `research` | `child_studies_impact_report` | Child Studies Unit Impact Analysis Report | 128 |
| `research` | `civil_society_studies` | Civil Society Exchange Program Evaluation | 151 |
| `research` | `frascati_manual` | Frascati Manual And R&D Classification Guidelines | 2,013 |
| `research` | `funded_research_projects` | Researchers And Funded Research Projects | 447 |
| `research` | `gender_violence_training_report` | Anti Discrimination And Violence Training Impact Report | 182 |
| `research` | `law_publications` | Legal Research Publications On Covid 19 | 958 |
| `research` | `project_writing_guide` | Lpe Project Writing Manual | 124 |
| `research` | `social_incubation_center` | Social Incubation Center Reports And Evaluation | 289 |
| `research` | `thesis_writing_guide` | Thesis Writing Manual For English Programs | 175 |
| `student_life` | `community_service_projects` | Community Service And Social Responsibility Projects | 1,264 |
| `student_life` | `counseling_resources` | Student Counseling And Wellness Resources | 1,009 |
| `student_life` | `frequently_asked_questions` | Student Frequently Asked Questions | 385 |
| `student_life` | `internship_offers` | Internship And Job Offers For Students | 349 |
| `student_life` | `student_clubs` | Student Clubs And Campus Life | 360 |

