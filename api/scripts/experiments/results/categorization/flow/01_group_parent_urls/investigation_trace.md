# Step 01 - Investigation Trace

## Config

- sample_size: `0`
- max_depth: `3`
- min_docs: `5`
- min_distinct_children: `2`
- strong_min_docs: `25`
- strong_min_distinct_children: `3`
- strong_min_semantic_ratio: `0.4`
- strong_max_dynamic_ratio: `0.55`
- weak_max_semantic_ratio: `0.15`
- weak_min_dynamic_ratio: `0.8`
- large_group_doc_threshold: `1000`
- large_group_min_semantic_segments: `1`
- ai_mode: `off`
- max_ai_candidates: `200`
- llm_provider: `outlier`
- ollama_url: `http://localhost:11434`
- ollama_model: `qwen:4b`
- outlier_url: `http://127.0.0.1:8080`
- outlier_model: `claude-opus-4-6`
- llm_timeout_seconds: `30.0`

## Summary

- created_at_utc: `2026-04-04T14:49:16.770305+00:00`
- total_docs: `60649`
- candidate_count: `1993`
- accepted_parent_candidates: `105`
- final_parent_groups: `105`
- fallback_root_docs: `26`
- ai_calls: `0`
- ai_errors: `0`
- large_group_doc_threshold: `1000`
- large_group_accept_count: `8`
- accepted_by_depth: `{'1': 5, '2': 24, '3': 76}`
- decisions_by_depth: `{'depth_1': {'accept': 5, 'reject': 1}, 'depth_2': {'accept': 24, 'reject': 125}, 'depth_3': {'accept': 76, 'reject': 1762}}`

## Candidate Decisions (Top 120 by docs)

| Depth | Parent | Docs | Children | Semantic | Dynamic | Decision | Source | Reason |
|---:|---|---:|---:|---:|---:|---|---|---|
| 1 | `www.bilgi.edu.tr/media` | 20537 | 2 | 1.000 | 0.000 | `accept` | `rule_large_group` | large_group_keep_together |
| 2 | `www.bilgi.edu.tr/media/uploads` | 20168 | 10 | 0.000 | 1.000 | `accept` | `rule_large_group` | large_group_keep_together |
| 1 | `www.bilgi.edu.tr/tr` | 17000 | 20 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 1 | `www.bilgi.edu.tr/en` | 14391 | 15 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/akademik` | 10380 | 20 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/en/academic` | 8910 | 23 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 1 | `ects.bilgi.edu.tr/course` | 6482 | 1 | 1.000 | 0.000 | `accept` | `rule_large_group` | large_group_keep_together |
| 2 | `ects.bilgi.edu.tr/course/detail` | 6482 | 0 | 0.000 | 0.000 | `accept` | `rule_large_group` | large_group_keep_together |
| 3 | `www.bilgi.edu.tr/media/uploads/2023` | 3803 | 12 | 0.000 | 1.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/tr/akademik/kadro` | 3438 | 511 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/media/uploads/2020` | 2976 | 12 | 0.000 | 1.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/media/uploads/2021` | 2773 | 11 | 0.000 | 1.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/en/academic/staff` | 2631 | 512 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/media/uploads/2022` | 2287 | 12 | 0.000 | 1.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 1 | `www.bilgi.edu.tr/upload` | 2213 | 110 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/media/uploads/2025` | 2123 | 12 | 0.000 | 1.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/media/uploads/2024` | 2053 | 12 | 0.000 | 1.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/media/uploads/2018` | 1822 | 11 | 0.000 | 1.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 2 | `www.bilgi.edu.tr/tr/haber` | 1754 | 477 | 0.000 | 1.000 | `accept` | `rule_large_group` | large_group_keep_together |
| 3 | `www.bilgi.edu.tr/media/uploads/2019` | 1688 | 11 | 0.000 | 1.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/tr/akademik/lisansustu` | 1657 | 59 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/etkinlik` | 1614 | 561 | 0.000 | 1.000 | `accept` | `rule_large_group` | large_group_keep_together |
| 3 | `www.bilgi.edu.tr/en/academic/graduate` | 1551 | 54 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/en/news` | 1389 | 298 | 0.000 | 1.000 | `accept` | `rule_large_group` | large_group_keep_together |
| 2 | `www.bilgi.edu.tr/en/event` | 1106 | 285 | 0.000 | 1.000 | `accept` | `rule_large_group` | large_group_keep_together |
| 2 | `www.bilgi.edu.tr/en/international` | 1092 | 11 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/en/university` | 987 | 4 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/university/about` | 976 | 7 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/sosyal-ve-beseri-bilimler-fakultesi` | 972 | 16 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/international` | 970 | 11 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/international/international-office` | 818 | 10 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/international/uluslararasi-ofis` | 768 | 10 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/universite` | 739 | 5 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/universite/hakkinda` | 726 | 7 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/academic/faculty-of-social-sciences-and-humanities` | 708 | 16 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/muhendislik-ve-doga-bilimleri-fakultesi` | 665 | 22 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/media/uploads/2026` | 642 | 2 | 0.000 | 1.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 2 | `www.bilgi.edu.tr/en/life-at-bilgi` | 632 | 7 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/academic/faculty-of-engineering-and-natural-sciences` | 576 | 22 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/yasam` | 564 | 8 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/iletisim-fakultesi` | 540 | 16 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/academic/school-of-advanced-vocational-studies` | 532 | 22 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/academic/vocational-school-of-health-services` | 524 | 14 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/arastirma` | 522 | 15 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/saglik-hizmetleri-meslek-yuksekokulu` | 510 | 14 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/meslek-yuksekokulu` | 488 | 22 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/life-at-bilgi/student` | 468 | 9 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/academic/faculty-of-business` | 454 | 11 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/saglik-bilimleri-fakultesi` | 454 | 14 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/isletme-fakultesi` | 448 | 11 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/yasam/ogrenci` | 420 | 9 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/academic/faculty-of-applied-sciences` | 412 | 16 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/uygulamali-bilimler-fakultesi` | 408 | 16 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/academic/faculty-of-communication` | 382 | 13 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/media/attachments` | 369 | 4 | 0.000 | 1.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/en/academic/english-language-programs` | 294 | 27 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/ingilizce-hazirlik-programi` | 258 | 27 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/mimarlik-fakultesi` | 198 | 12 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/academic/faculty-of-architecture` | 192 | 12 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/upload/kurum-ic-degerlendirme-raporu-2017` | 190 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/media/attachments/2026` | 168 | 1 | 0.000 | 1.000 | `reject` | `parent_not_accepted` | parent_not_accepted:www.bilgi.edu.tr/media/attachments |
| 2 | `www.bilgi.edu.tr/upload/kurum-ic-degerlendirme-raporu-2016` | 162 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/media/attachments/2024` | 160 | 3 | 0.000 | 1.000 | `reject` | `parent_not_accepted` | parent_not_accepted:www.bilgi.edu.tr/media/attachments |
| 2 | `www.bilgi.edu.tr/upload/undergraduate-student-handbook` | 157 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/en/academic/faculty-of-health-sciences` | 146 | 14 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/hukuk-fakultesi` | 136 | 4 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/upload/kurum-ic-degerlendirme-raporu-2015` | 133 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/en/international/international-admissions` | 132 | 10 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/life-at-bilgi/units-and-services` | 130 | 7 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/academic/faculty-of-law` | 126 | 4 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/en/talent` | 122 | 8 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/upload/ogrenci-el-kitabi-lisans-onlisans` | 122 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/en/academic/emacfall2025` | 120 | 18 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/upload/graduate-student-handbook` | 118 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/tr/yasam/birim-ve-hizmetler` | 114 | 7 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/upload/bilgide-sosyal-sorumluluk` | 106 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/tr/arastirma/dis-kaynakli-projeler` | 106 | 4 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/international/uluslararasi-aday-ogrenci` | 106 | 9 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/arastirma/arastirmacilar` | 102 | 1 | 1.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 2 | `www.bilgi.edu.tr/upload/kurum-ic-degerlendirme-raporu-2018` | 101 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/en/academic/foreign-language-programs` | 100 | 5 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/international/international-student-advising-office` | 96 | 7 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/upload/credit-system-bachelors-degree-and-associate-degree-education-and-examination-regulation` | 95 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 2 | `www.bilgi.edu.tr/upload/ogrenci-el-kitabi-lisansustu` | 95 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 2 | `www.bilgi.edu.tr/tr/talent` | 94 | 8 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/yabanci-dil-programlari` | 88 | 5 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/mezun` | 86 | 6 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/arastirma/bilgi-arastirma-fonlari` | 76 | 7 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/ihaleler` | 74 | 30 | 0.000 | 1.000 | `reject` | `rule_weak` | weak_signal |
| 2 | `www.bilgi.edu.tr/upload/bilgi-lisansustu-brosur` | 67 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/tr/international/uluslararasi-ogrenci-danismanlik-ofisi` | 66 | 7 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/en/quality` | 64 | 8 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/kalite` | 60 | 8 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/event/13036` | 60 | 2 | 1.000 | 0.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/tr/arastirma/mukemmeliyet-alanlari` | 58 | 2 | 1.000 | 0.000 | `accept` | `middle_rule` | ai_skipped |
| 3 | `www.bilgi.edu.tr/en/event/12253` | 54 | 1 | 1.000 | 0.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/tr/etkinlik/12252` | 54 | 1 | 1.000 | 0.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/en/academic/virginia-woolf-conference-2026` | 50 | 9 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/arastirma/universite-sanayi-is-birligi` | 50 | 5 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/talent/talent-development-office` | 48 | 5 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/mezun/mezunlarimizin-deneyimleri` | 46 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/adalet-meslek-yuksekokulu` | 44 | 5 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/ik` | 42 | 14 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/news/11179` | 42 | 1 | 1.000 | 0.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/media/attachments/2023` | 40 | 1 | 0.000 | 1.000 | `reject` | `parent_not_accepted` | parent_not_accepted:www.bilgi.edu.tr/media/attachments |
| 3 | `www.bilgi.edu.tr/en/talent/internship-office` | 38 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 2 | `www.bilgi.edu.tr/upload/bilgi-onlisans-programlari` | 37 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 2 | `www.bilgi.edu.tr/en/alumni` | 36 | 3 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/en/news/12444` | 36 | 2 | 1.000 | 0.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/tr/arastirma/dis-fonlu-ogrenci-projeleri` | 36 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/tr/talent/yetenek-gelisim-ofisi` | 36 | 5 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/tr/etkinlikler-arsivi` | 32 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 2 | `www.bilgi.edu.tr/tr/haberler-duyurular-arsivi` | 32 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/en/academic/vocational-school-of-justice` | 32 | 4 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 2 | `www.bilgi.edu.tr/upload/fba-352-erkek-giyim-ogrenci-calismalari-sergisi` | 30 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
| 3 | `www.bilgi.edu.tr/en/academic/general-education-department` | 30 | 7 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/akademik/genel-egitim-bolumu` | 30 | 7 | 1.000 | 0.000 | `accept` | `rule_strong` | strong_signal |
| 3 | `www.bilgi.edu.tr/tr/etkinlik/13035` | 30 | 1 | 1.000 | 0.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 3 | `www.bilgi.edu.tr/tr/haber/12442` | 28 | 2 | 1.000 | 0.000 | `reject` | `rule_invalid_parent_tail` | parent_ends_with_dynamic_segment |
| 2 | `www.bilgi.edu.tr/upload/call-for-2023-project-erasmus-europe-study-mobility` | 27 | 0 | 0.000 | 0.000 | `reject` | `rule_weak` | weak_signal |
