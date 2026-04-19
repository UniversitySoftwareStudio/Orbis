# Step 04 — Algorithm Merge

## Summary

- embedding model_id: `6`
- fetched embeddings: `60401` / `60534`
- reference leaf centroids: `52`
- unknown groups processed: `31`
- algorithm subclusters: `61` | mapped: `61` | unresolved: `0`
- mapped docs: `21324` | unresolved docs: `0`
- step-03 tree docs: `39,325` → merged total: `60,649`
- merged leaf entries: `52`

## Algorithm Docs Added per Top Level

| Top Level | Added Docs |
|---|---:|
| `services` | 6,053 |
| `administration` | 4,907 |
| `international` | 4,844 |
| `events` | 1,620 |
| `research` | 1,499 |
| `student_life` | 1,423 |
| `academics` | 966 |
| `quality` | 12 |

## Top Assignments (by subcluster doc count)

| Source Group | Parent Key | Docs | k | Subcluster | Status | Matched Leaf | Sim |
|---:|---|---:|---:|---:|---|---|---:|
| 1 | `www.bilgi.edu.tr/media/uploads` | 3,017 | 12 | 4 | `mapped` | `services/document_uploads/Document Uploads` | 0.975 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 2,522 | 12 | 2 | `mapped` | `international/international_office/International Office` | 0.979 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 2,260 | 12 | 5 | `mapped` | `international/international_office/International Office` | 0.957 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 2,184 | 12 | 11 | `mapped` | `services/document_uploads/Document Uploads` | 0.939 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 2,130 | 12 | 3 | `mapped` | `administration/university_information/University Information` | 0.934 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 1,667 | 12 | 6 | `mapped` | `administration/about_university/About University` | 0.969 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 1,463 | 12 | 7 | `mapped` | `events/university_events/University Events` | 0.948 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 1,423 | 12 | 9 | `mapped` | `research/intellectual_property/Intellectual Property` | 0.819 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 1,342 | 12 | 12 | `mapped` | `student_life/student_experience/Student Experience` | 0.970 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 950 | 12 | 1 | `mapped` | `administration/about_university/About University` | 0.905 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 626 | 12 | 8 | `mapped` | `services/document_uploads/Document Uploads` | 0.826 |
| 1 | `www.bilgi.edu.tr/media/uploads` | 584 | 12 | 10 | `mapped` | `academics/faculty_of_law/Faculty Of Law` | 0.821 |
| 33 | `www.bilgi.edu.tr/media` | 118 | 6 | 6 | `mapped` | `services/document_uploads/Document Uploads` | 0.792 |
| 33 | `www.bilgi.edu.tr/media` | 109 | 6 | 2 | `mapped` | `events/university_events/University Events` | 0.913 |
| 38 | `www.bilgi.edu.tr/tr/arastirma` | 100 | 4 | 4 | `mapped` | `academics/faculty_of_social_sciences/Faculty Of Social Scien` | 0.914 |
| 47 | `www.bilgi.edu.tr/tr/arastirma/dis-kaynakli-projeler` | 62 | 3 | 1 | `mapped` | `administration/about_university/About University` | 0.934 |
| 55 | `www.bilgi.edu.tr/tr/mezun` | 50 | 2 | 1 | `mapped` | `academics/faculty_of_business_management/Faculty Of Business` | 0.919 |
| 33 | `www.bilgi.edu.tr/media` | 48 | 6 | 3 | `mapped` | `events/university_events/University Events` | 0.885 |
| 33 | `www.bilgi.edu.tr/media` | 44 | 6 | 5 | `mapped` | `international/international_office/International Office` | 0.942 |
| 52 | `www.bilgi.edu.tr/tr/arastirma/bilgi-arastirma-fonlari` | 44 | 3 | 1 | `mapped` | `academics/faculty_of_engineering/Faculty Of Engineering And ` | 0.918 |
| 56 | `www.bilgi.edu.tr/tr/arastirma/mukemmeliyet-alanlari` | 38 | 2 | 1 | `mapped` | `administration/about_university/About University` | 0.930 |
| 38 | `www.bilgi.edu.tr/tr/arastirma` | 36 | 4 | 3 | `mapped` | `academics/faculty_of_engineering/Faculty Of Engineering And ` | 0.921 |
| 47 | `www.bilgi.edu.tr/tr/arastirma/dis-kaynakli-projeler` | 32 | 3 | 3 | `mapped` | `academics/faculty_of_engineering/Faculty Of Engineering And ` | 0.903 |
| 59 | `www.bilgi.edu.tr/tr/arastirma/universite-sanayi-is-birl` | 30 | 2 | 2 | `mapped` | `academics/faculty_of_health_sciences/Faculty Of Health Scien` | 0.938 |
| 33 | `www.bilgi.edu.tr/media` | 26 | 6 | 4 | `mapped` | `services/document_uploads/Document Uploads` | 0.683 |
| 38 | `www.bilgi.edu.tr/tr/arastirma` | 26 | 4 | 2 | `mapped` | `academics/faculty_of_computer_science/Faculty Of Computer Sc` | 0.902 |
| 33 | `www.bilgi.edu.tr/media` | 24 | 6 | 1 | `mapped` | `services/document_uploads/Document Uploads` | 0.780 |
| 56 | `www.bilgi.edu.tr/tr/arastirma/mukemmeliyet-alanlari` | 20 | 2 | 2 | `mapped` | `administration/university_information/University Information` | 0.894 |
| 59 | `www.bilgi.edu.tr/tr/arastirma/universite-sanayi-is-birl` | 20 | 2 | 1 | `mapped` | `research/intellectual_property/Intellectual Property` | 0.924 |
| 52 | `www.bilgi.edu.tr/tr/arastirma/bilgi-arastirma-fonlari` | 18 | 3 | 3 | `mapped` | `research/intellectual_property/Intellectual Property` | 0.893 |

## Merged Tree (top-level summary)

| Top Level | Docs | Leaves |
|---|---:|---:|
| `academics` | 20,653 | 26 |
| `administration` | 6,836 | 4 |
| `events` | 4,340 | 1 |
| `international` | 6,906 | 6 |
| `news` | 3,143 | 1 |
| `people` | 6,069 | 1 |
| `quality` | 30 | 1 |
| `research` | 1,535 | 2 |
| `services` | 8,726 | 5 |
| `student_life` | 2,411 | 5 |

