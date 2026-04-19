# Taxonomy Validation Report

- leaves validated: **21**
- good: **13** | mixed: **1** | bad: **5**
- avg fit score: **0.770**
- provider: `outlier` / sample_size: `15`

## Leaves Needing Attention

| Verdict | Leaf | Top | Docs | Fit | Suggestion |
|---|---|---|---:|---:|---|
| `bad` | Research Projects And Grants | research | 1,744 | 0.10 | split into three leaves: 'Research Awards And Prizes' (for / |
| `bad` | Events, Seminars and Conferences | events | 7,291 | 0.40 | split: Separate into two leaves — 'Events, Seminars and Conf |
| `bad` | University Policies, Regulations and Official | regulations | 5,302 | 0.40 | split: Separate into narrower leaves such as 'University Han |
| `bad` | Student Wellbeing, Counseling and Campus Serv | student_life | 2,346 | 0.40 | split into: 'Student Clubs and Organizations', 'Student Admi |
| `bad` | Faculty Of Applied Sciences | academics | 1,420 | 0.47 | split into two separate leaves: 'Faculty Of Applied Sciences |
| `mixed` | Accreditation and Quality Assurance | quality | 6,801 | 0.55 | Rename leaf to 'University Quality Processes and Documentati |

## Issue Details

### `research/funded_research_projects/Research Projects And Grants`
- doc_count: 1,744 | fit: 0.10 | verdict: bad
- suggestion: split into three leaves: 'Research Awards And Prizes' (for /arastirma/oduller/ pages), 'Intellectual Property' (for /arastirma/fikri-mulkiyet/ pages), and keep 'Research Projects And Grants' only for actual funded project listings
- issues:
  - {'title': 'Diğer Ödüller', 'url': 'http://www.bilgi.edu.tr/tr/arastirma/oduller/diger-oduller/', 'reason': 'Page about research awards/prizes, not research projects or grants'}
  - {'title': 'Tescil Edilmiş Patent ve Faydalı Modeller', 'url': 'http://www.bilgi.edu.tr/tr/arastirma/fikri-mulkiyet/tescil-edilmis-patent-ve-faydali-modeller/', 'reason': 'About registered patents and utility models (intellectual property), not research projects or grants'}
  - {'title': 'Türkiye Bilimler Akademisi (TÜBA) Ödülleri', 'url': 'https://www.bilgi.edu.tr/tr/arastirma/oduller/tuba/', 'reason': 'About TÜBA awards, not funded research projects'}
  - {'title': 'Faydalı Bağlantılar', 'url': 'http://www.bilgi.edu.tr/tr/arastirma/fikri-mulkiyet/faydali-baglantilar/', 'reason': 'Useful links page under intellectual property, not research projects'}
  - {'title': 'Süreç Tablosu', 'url': 'https://www.bilgi.edu.tr/tr/arastirma/fikri-mulkiyet/surec-tablosu/', 'reason': 'Process table for intellectual property, not research projects'}
  - {'title': 'Fikri Mülkiyet', 'url': 'https://www.bilgi.edu.tr/tr/arastirma/fikri-mulkiyet/', 'reason': 'Intellectual property main page, not research projects or grants'}
  - {'title': 'TÜBİTAK Ödülleri', 'url': 'http://www.bilgi.edu.tr/tr/arastirma/oduller/tubitak/', 'reason': 'TÜBİTAK awards page, not funded research projects'}
  - {'title': 'Formlar', 'url': 'http://www.bilgi.edu.tr/tr/arastirma/fikri-mulkiyet/formlar/', 'reason': 'Forms for intellectual property, not research projects or grants'}
  - {'title': 'Yönerge', 'url': 'https://www.bilgi.edu.tr/tr/arastirma/fikri-mulkiyet/yonerge/', 'reason': 'Directive/guideline for intellectual property, not research projects'}

### `events/events/Events, Seminars and Conferences`
- doc_count: 7,291 | fit: 0.40 | verdict: bad
- suggestion: split: Separate into two leaves — 'Events, Seminars and Conferences' for actual event/etkinlik pages (URLs containing /event/ or /etkinlik/) and 'University News and Announcements' for news/haber pages (URLs containing /news/ or /haber/) covering admissions, exam results, project updates, awards, partnerships, etc.
- issues:
  - {'title': 'Application Process for University of London Honours Programmes (2021-2022)', 'url': 'https://www.bilgi.edu.tr/en/news/10481/...', 'reason': 'This is a university admissions/application announcement (news), not an event, seminar, or conference.'}
  - {'title': "BİLGİ Enerji Sistemleri Mühendisliği Bölümü'nden güneş santrallerinin verimliliğini artıracak proje", 'url': 'http://www.bilgi.edu.tr/tr/haber/12756/...', 'reason': 'News article about a research project, not an event/seminar/conference.'}
  - {'title': '2022-2023 Erasmus İngilizce Dil Sınavı Duyurusu', 'url': 'http://www.bilgi.edu.tr/tr/haber/10771/...', 'reason': 'Exam announcement (haber/news), not an event/seminar/conference.'}
  - {'title': "BİLGİ Mimarlık Bölümü öğrencisi Zeynep İğmen'in 'Zaman Barınağı' tasarımı KulturRegion Festivali'nde sergilendi", 'url': 'https://www.bilgi.edu.tr/tr/haber/11287/...', 'reason': 'News article about a student exhibition, not an event listing.'}
  - {'title': 'Spor Yöneticiliği Özel Yetenek Sınavı Sonuçları (2023)', 'url': 'http://www.bilgi.edu.tr/tr/haber/11727/...', 'reason': 'Exam results announcement, not an event/seminar/conference.'}
  - {'title': "BİLGİ ve Tekfen Holding'den üniversite-sanayi işbirliğinde stratejik adım", 'url': 'https://www.bilgi.edu.tr/tr/haber/12755/...', 'reason': 'News about a university-industry partnership, not an event/seminar/conference.'}
  - {'title': 'Prof. Turgut Tarhanlı from BİLGİ Faculty of Law receives the Academic Honor Award...', 'url': 'https://www.bilgi.edu.tr/en/news/12828/...', 'reason': 'News about an award, not an event/seminar/conference listing.'}
  - {'title': 'BİLGİ Tekstil ve Moda Tasarımı Bölümü öğrencileri 33. Koza Genç Moda Tasarımcıları Yarışması finalinde', 'url': 'http://www.bilgi.edu.tr/tr/haber/12715/...', 'reason': 'News about a student competition result, not an event/seminar/conference.'}

### `regulations/institutional_documents/University Policies, Regulations and Official Documents`
- doc_count: 5,302 | fit: 0.40 | verdict: bad
- suggestion: split: Separate into narrower leaves such as 'University Handbooks & Student Guides', 'Institutional Evaluation Reports', 'University Procurement & Tenders', 'University Governance & Administration', and 'Community Service Projects & Initiatives'. Reserve the current leaf label only for actual policy/regulation documents.
- issues:
  - {'title': 'İstanbul Bilgi Üniversitesi - Bilgisayar Alım İhalesi', 'reason': 'Procurement/tender announcement, not a policy or regulation document.'}
  - {'title': 'İstanbul Bilgi Üniversitesi - Kampüsler Çatı ve İzolasyon Yapımı İşleri İhalesi', 'reason': 'Procurement/tender announcement for construction, not a policy or regulation.'}
  - {'title': 'Social Responsibility Courses', 'reason': 'Course listing under community services, not a policy or regulation.'}
  - {'title': 'Projects 2015', 'reason': 'Community service projects listing, not a policy or regulation.'}
  - {'title': 'Projects Before 2013', 'reason': 'Community service projects listing, not a policy or regulation.'}
  - {'title': 'Projects 2022', 'reason': 'Community service projects listing, not a policy or regulation.'}
  - {'title': 'Campus Initiatives', 'reason': 'Sustainability initiatives page, not a policy or regulation document.'}
  - {'title': 'Rektörlük', 'reason': 'General administrative/governance page about the rectorate, not a specific policy or regulation.'}
  - {'title': 'Former Rectors', 'reason': 'Historical listing of university leadership, not a policy or regulation.'}
  - {'title': 'Yalnizlik', 'reason': "Unclear upload with no evident connection to policies or regulations; title means 'Loneliness'."}

### `student_life/campus_units_and_counseling/Student Wellbeing, Counseling and Campus Services`
- doc_count: 2,346 | fit: 0.40 | verdict: bad
- suggestion: split into: 'Student Clubs and Organizations', 'Student Administrative Affairs' (registration, transfers, student affairs), and narrow 'Student Wellbeing and Counseling' (disability support, international student advising, psychological counseling). Alternatively relabel this leaf as 'Student Life and Support Services' to honestly cover the breadth.
- issues:
  - {'title': 'Toplumsal Katkı ve Sürdürülebilirlik Kulüpleri', 'reason': 'Student clubs about social contribution, not wellbeing or counseling'}
  - {'title': 'Social Contribution and Sustainability Clubs', 'reason': 'Student clubs, not wellbeing or counseling'}
  - {'title': 'Hobby Clubs', 'reason': 'Student clubs, not wellbeing or counseling'}
  - {'title': 'Spor ve Sanat İçerikli Kulüpler', 'reason': 'Sports and arts clubs, not wellbeing or counseling'}
  - {'title': 'Course Registration', 'reason': 'Academic registration process, not wellbeing or counseling'}
  - {'title': 'Scholarships', 'reason': 'Financial aid, not wellbeing or counseling'}
  - {'title': 'Transfers', 'reason': 'Student transfer/admissions process, not wellbeing or counseling'}
  - {'title': 'Lisans-Önlisans Öğrenci İşleri', 'reason': 'General undergraduate student affairs, broader than wellbeing/counseling'}
  - {'title': 'Frequently Asked Questions', 'reason': 'Generic FAQ, no clear link to wellbeing or counseling'}
  - {'title': 'Sıkça Sorulan Sorular', 'reason': 'Generic FAQ, no clear link to wellbeing or counseling'}
  - {'title': 'Educational Environment', 'reason': 'Campus facilities/environment, not specifically wellbeing or counseling'}

### `academics/faculties/Faculty Of Applied Sciences`
- doc_count: 1,420 | fit: 0.47 | verdict: bad
- suggestion: split into two separate leaves: 'Faculty Of Applied Sciences' (uygulamali-bilimler-fakultesi / faculty-of-applied-sciences URLs) and 'Faculty Of Health Sciences' (saglik-bilimleri-fakultesi / faculty-of-health-sciences URLs)
- issues:
  - {'title': 'Erken Müdahalede Gelişimsel Yaklaşımlar ve Motor Beceri Odaklı Müdahale Sempozyumu', 'url': 'https://www.bilgi.edu.tr/tr/akademik/saglik-bilimleri-fakultesi/cocuk-gelisimi/erken-mudahalede-geli', 'reason': 'URL indicates Faculty of Health Sciences (saglik-bilimleri-fakultesi), not Faculty of Applied Sciences'}
  - {'title': 'Anatomi Laboratuvarı', 'url': 'https://www.bilgi.edu.tr/tr/akademik/saglik-bilimleri-fakultesi/beslenme-ve-diyetetik/laboratuvarlar', 'reason': 'URL indicates Faculty of Health Sciences (Nutrition and Dietetics department)'}
  - {'title': 'Anatomi Laboratuvarı', 'url': 'https://www.bilgi.edu.tr/tr/akademik/saglik-bilimleri-fakultesi/hemsirelik/laboratuvarlar/anatomi-la', 'reason': 'URL indicates Faculty of Health Sciences (Nursing department)'}
  - {'title': 'Vizyon ve Misyon', 'url': 'http://www.bilgi.edu.tr/tr/akademik/saglik-bilimleri-fakultesi/beslenme-ve-diyetetik/vizyon-misyon/', 'reason': 'URL indicates Faculty of Health Sciences (Nutrition and Dietetics department)'}
  - {'title': 'Temel Beceri Laboratuvarı II', 'url': 'https://www.bilgi.edu.tr/tr/akademik/saglik-bilimleri-fakultesi/hemsirelik/laboratuvarlar/temel-bece', 'reason': 'URL indicates Faculty of Health Sciences (Nursing department)'}
  - {'title': 'Developmental Approaches in Early Intervention & Motor Skill-Focused Intervention Symposium', 'url': 'http://www.bilgi.edu.tr/en/academic/faculty-of-health-sciences/child-development/developmental-appro', 'reason': 'URL explicitly shows faculty-of-health-sciences, not faculty-of-applied-sciences'}
  - {'title': 'Sağlık Yönetimi Bölümü *', 'url': 'https://www.bilgi.edu.tr/tr/akademik/saglik-bilimleri-fakultesi/saglik-yonetimi/', 'reason': 'URL indicates Faculty of Health Sciences (Health Management department)'}

### `quality/accreditation_reports/Accreditation and Quality Assurance`
- doc_count: 6,801 | fit: 0.55 | verdict: mixed
- suggestion: Rename leaf to 'University Quality Processes and Documentation' or split into 'accreditation_reports' for actual accreditation evaluation reports and 'quality_processes' for operational quality management pages like guides, ECTS packages, and diploma supplements
- issues:
  - {'title': 'Guides', 'url': 'https://www.bilgi.edu.tr/en/quality/processes/guides/', 'reason': 'Generic quality process guides, not accreditation reports'}
  - {'title': 'Externally Sourced Documents', 'url': 'https://www.bilgi.edu.tr/en/quality/processes/externally-sourced-documents/', 'reason': 'Generic document management page, not an accreditation report'}
  - {'title': 'ECTS Information Package', 'url': 'http://www.bilgi.edu.tr/en/quality/processes/ects-information-package/', 'reason': 'ECTS credit system documentation, relates to quality processes but not accreditation reporting'}
  - {'title': 'Diploma Supplement (DS)', 'url': 'https://www.bilgi.edu.tr/en/quality/processes/diploma-supplement-ds/', 'reason': 'Diploma supplement is a credential transparency tool, not an accreditation report'}
  - {'title': 'Diploma Eki (DS)', 'url': 'http://www.bilgi.edu.tr/tr/kalite/surecler/diploma-eki-ds/', 'reason': 'Turkish version of Diploma Supplement, same issue as above'}
  - {'title': 'Processes', 'url': 'https://www.bilgi.edu.tr/en/quality/processes/', 'reason': 'Top-level quality processes landing page, not a specific accreditation report'}
  - {'title': 'Kılavuzlar', 'url': 'http://www.bilgi.edu.tr/tr/kalite/surecler/kilavuzlar/', 'reason': 'Turkish version of Guides page, generic quality process content'}
  - {'title': 'Dış Kaynaklı Dokümanlar', 'url': 'https://www.bilgi.edu.tr/tr/kalite/surecler/dis-kaynakli-dokumanlar/', 'reason': 'Turkish version of Externally Sourced Documents, generic quality process content'}
  - {'title': 'AKTS Bilgi Paketi', 'url': 'https://www.bilgi.edu.tr/tr/kalite/surecler/akts-bilgi-paketi/', 'reason': 'Turkish version of ECTS Information Package, not accreditation reporting'}

## All Leaves

| Verdict | Top | Sub | Leaf | Docs | Fit |
|---|---|---|---|---:|---:|
| ✓ `good` | academics | course_catalog | Course Catalog and Curricula | 6,802 | 0.95 |
| ✗ `bad` | academics | faculties | Faculty Of Applied Sciences | 1,420 | 0.47 |
| ✓ `good` | academics | faculties | Faculty Of Architecture | 390 | 0.95 |
| ✓ `good` | academics | faculties | Faculty Of Business | 902 | 0.95 |
| ✓ `good` | academics | faculties | Faculty Of Communication | 922 | 0.98 |
| ✓ `good` | academics | faculties | Faculty Of Engineering And Natural Sciences | 1,285 | 1.00 |
| ✓ `good` | academics | faculties | Faculty Of Law | 370 | 1.00 |
| ✓ `good` | academics | faculties | Faculty of Arts, Social Sciences and Humaniti | 1,680 | 0.95 |
| ✓ `good` | academics | graduate_programs | Graduate Programs | 3,533 | 0.93 |
| ✓ `good` | academics | preparatory_programs | Language Preparatory Programs | 945 | 0.93 |
| ? `no_samples` | academics | teaching_learning_resources | Teaching and Learning Support | 823 | — |
| ✓ `good` | academics | vocational_school | Vocational School and Associate Degree Progra | 2,130 | 0.92 |
| ✗ `bad` | events | events | Events, Seminars and Conferences | 7,291 | 0.40 |
| ✓ `good` | international | erasmus_mobility_applications | International Exchange and Mobility Programs | 6,077 | 0.87 |
| ✓ `good` | people | academic_staff | Faculty and Staff Directory | 6,069 | 0.95 |
| ~ `mixed` | quality | accreditation_reports | Accreditation and Quality Assurance | 6,801 | 0.55 |
| ✗ `bad` | regulations | institutional_documents | University Policies, Regulations and Official | 5,302 | 0.40 |
| ✗ `bad` | research | funded_research_projects | Research Projects And Grants | 1,744 | 0.10 |
| ? `no_samples` | research | research_centers | Research Centers And Institutes | 3,337 | — |
| ✗ `bad` | student_life | campus_units_and_counseling | Student Wellbeing, Counseling and Campus Serv | 2,346 | 0.40 |
| ✓ `good` | student_life | career_alumni | Career Services And Alumni Network | 480 | 0.93 |
