# Step 02 - Group Classification

## Summary

- total_groups: `105`
- total_docs: `60649`
- known_groups / known_docs: `74` / `39325`
- unknown_groups / unknown_docs: `31` / `21324`

## Largest Unknown Groups

| # | Group | Parent | Docs | Reason |
|---:|---:|---|---:|---|
| 1 | 1 | `www.bilgi.edu.tr/media/uploads` | 20168 | Unknown: tail URLs are mostly dynamic/id-like and weak in semantic signal (dynamic_tail_ratio=0.75, semantic_tail_ratio=0.25). |
| 2 | 33 | `www.bilgi.edu.tr/media` | 369 | Unknown: tail signals are mixed or weak and do not meet known-group thresholds (semantic_tail_ratio=0.40, dynamic_tail_ratio=0.60, unique_tail_patterns=15). |
| 3 | 38 | `www.bilgi.edu.tr/tr/arastirma` | 176 | Unknown: tail signals are mixed or weak and do not meet known-group thresholds (semantic_tail_ratio=1.00, dynamic_tail_ratio=0.00, unique_tail_patterns=11). |
| 4 | 47 | `www.bilgi.edu.tr/tr/arastirma/dis-kaynakli-projeler` | 106 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.90, tail_entropy=0.60). |
| 5 | 52 | `www.bilgi.edu.tr/tr/arastirma/bilgi-arastirma-fonlari` | 76 | Unknown: tail signals are mixed or weak and do not meet known-group thresholds (semantic_tail_ratio=1.00, dynamic_tail_ratio=0.00, unique_tail_patterns=7). |
| 6 | 55 | `www.bilgi.edu.tr/tr/mezun` | 62 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.79, tail_entropy=1.11). |
| 7 | 56 | `www.bilgi.edu.tr/tr/arastirma/mukemmeliyet-alanlari` | 58 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.61, tail_entropy=0.97). |
| 8 | 59 | `www.bilgi.edu.tr/tr/arastirma/universite-sanayi-is-birligi` | 50 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.62, tail_entropy=1.50). |
| 9 | 70 | `www.bilgi.edu.tr/` | 26 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.62, tail_entropy=2.24). |
| 10 | 73 | `www.bilgi.edu.tr/en/uzem` | 26 | Unknown: tail signals are mixed or weak and do not meet known-group thresholds (semantic_tail_ratio=1.00, dynamic_tail_ratio=0.00, unique_tail_patterns=3). |
| 11 | 78 | `www.bilgi.edu.tr/tr/uzem` | 22 | Unknown: tail signals are mixed or weak and do not meet known-group thresholds (semantic_tail_ratio=1.00, dynamic_tail_ratio=0.00, unique_tail_patterns=3). |
| 12 | 80 | `www.bilgi.edu.tr/tr/arastirma/teknoloji-transfer-ofisi` | 20 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.86, tail_entropy=0.59). |
| 13 | 83 | `www.bilgi.edu.tr/en/quality/accreditations` | 14 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.86, tail_entropy=0.59). |
| 14 | 86 | `www.bilgi.edu.tr/tr/kalite/akreditasyonlar` | 12 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.83, tail_entropy=0.65). |
| 15 | 87 | `www.bilgi.edu.tr/en/university` | 11 | Unknown: tail signals are mixed or weak and do not meet known-group thresholds (semantic_tail_ratio=1.00, dynamic_tail_ratio=0.00, unique_tail_patterns=3). |
| 16 | 88 | `www.bilgi.edu.tr/en/alumni` | 10 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.67, tail_entropy=0.92). |
| 17 | 89 | `www.bilgi.edu.tr/en/quality` | 10 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.75, tail_entropy=0.81). |
| 18 | 90 | `www.bilgi.edu.tr/en/quality/commissions-and-boards` | 10 | Unknown: tail signals are mixed or weak and do not meet known-group thresholds (semantic_tail_ratio=1.00, dynamic_tail_ratio=0.00, unique_tail_patterns=3). |
| 19 | 92 | `www.bilgi.edu.tr/tr/kalite` | 10 | Unknown: tail URLs are repetitive with low information gain (dominant_pattern_share=0.75, tail_entropy=0.81). |
| 20 | 93 | `www.bilgi.edu.tr/tr/kalite/komisyonlar-ve-kurullar` | 10 | Unknown: tail signals are mixed or weak and do not meet known-group thresholds (semantic_tail_ratio=1.00, dynamic_tail_ratio=0.00, unique_tail_patterns=3). |
