# Event System DB Results - 2026-04-24

Source database: `orbisdb`

Status: historical report-evidence snapshot. These numbers are the basis for
the report's regulation extraction and assignment-matching tables. They refer
to the action-object pipeline stored in `regulation_rules`,
`user_rule_assignments`, and `event_candidate_logs`; the currently wired
`/api/events/trigger` route writes extraction output to `regulatory_events`.

## Executive Summary

The event system has one completed DB run from 2026-04-10. It processed 80 regulation sources and 935 knowledge-base chunks, evaluated 323 candidate rules, accepted 178 active regulation rules, and produced 176 active user-rule assignments for 4 test students.

## Extraction Run

| Metric | Value |
|---|---:|
| Run ID | `fadc244f-d26d-46e0-be9d-b934ce3378b4` |
| Status | `COMPLETED` |
| Started | `2026-04-10 08:16:47` |
| Completed | `2026-04-10 09:16:01` |
| Source documents processed | 80 |
| KB chunks consumed | 935 |
| Candidate rules evaluated | 323 |
| Accepted active rules | 178 |
| Rejected quality candidates | 145 |
| Existing `regulatory_events` rows | 0 |
| Active `regulation_rules` rows | 178 |
| Active `user_rule_assignments` rows | 176 |

## Rule Quality Funnel

| Candidate decision | Count |
|---|---:|
| `ACCEPT_PENDING` | 178 |
| `REJECT_QUALITY` | 145 |

| Top rejection reason | Count |
|---|---:|
| `not_imperative_enough` | 128 |
| `audience_too_broad` | 4 |
| `awareness_only_wording` | 2 |

## Extracted Rule Breakdown

| Dimension | Value | Count |
|---|---|---:|
| Status | `ACTIVE` | 178 |
| Match type | `CONTEXTUAL` | 167 |
| Match type | `SQL` | 11 |
| Target role | `STUDENT` | 153 |
| Target role | `STAFF` | 11 |
| Target role | `ADMIN` | 9 |
| Target role | `ALL` | 5 |
| Blocking | `true` | 108 |
| Blocking | `false` | 70 |

## Assignment Results

| Student | GPA | Profile context | Assignments | HIGH | MEDIUM | LOW | SQL | Contextual |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| Mehmet Demir | 2.40 | Graduation project in progress, Year 4, Computer Engineering | 60 | 38 | 17 | 5 | 2 | 58 |
| Ali Yilmaz | 1.60 | Academic probation, Year 2, Computer Engineering | 42 | 30 | 8 | 4 | 8 | 34 |
| Zeynep Arslan | 2.85 | Mandatory internship this semester, Year 3, Computer Engineering | 38 | 29 | 5 | 4 | 2 | 36 |
| Ayse Kaya | 3.50 | Double major, Year 3, Business Administration | 36 | 25 | 6 | 5 | 3 | 33 |

Totals:

| Assignment dimension | Count |
|---|---:|
| Total assignments | 176 |
| HIGH urgency | 122 |
| MEDIUM urgency | 36 |
| LOW urgency | 18 |
| SQL matched | 15 |
| Contextual LLM matched | 161 |

## User Context Inputs

| Student | Extra context |
|---|---|
| Ali Yilmaz | `{"scholarship": "none", "internship_status": "not_started"}` |
| Ayse Kaya | `{"scholarship": "merit-based"}` |
| Mehmet Demir | `{"advisor": "assigned", "graduation_project_status": "in_progress"}` |
| Zeynep Arslan | `{"has_insurance": false, "internship_status": "mandatory internship required this semester", "internship_company": "not yet found", "internship_credits_needed": 30, "internship_form_submitted": false}` |

## Zeynep Internship Examples

Zeynep has 13 internship-related/context-sensitive assignments in the DB query, including 10 direct internship/process obligations plus related eligibility and invention rules.

| Urgency | Rule | Why it matched |
|---|---|---|
| HIGH | Complete a total of 40 working days (20 + 20) of mandatory internship to qualify for your undergraduate degree. | Her profile says mandatory internship is required this semester. |
| HIGH | Submit the mandatory/voluntary internship agreement cover form and vocational education contract at least 10 business days before the internship start date. | She has not found a company and has not submitted forms yet, so the rule is actionable once she secures placement. |
| HIGH | Do not schedule classes or exams on internship days if completing the internship during the semester. | Her internship is required during the semester, so schedule conflict rules apply. |
| HIGH | Print the Internship Logbook before starting and ensure pages are signed/stamped weekly. | She is preparing for a mandatory internship. |
| HIGH | Do not begin a compulsory internship before the summer following the end of the 4th semester. | She has completed 6 semesters, so the constraint applies and is satisfied. |

## SQL Matching Examples

| Student | GPA | SQL condition | Example matched rule |
|---|---:|---|---|
| Ali Yilmaz | 1.60 | `gpa < 1.75` | Academic probation and restricted credit load rule. |
| Ali Yilmaz | 1.60 | `gpa < 2.00` | Graduation GPA threshold and scholarship/discount retention rules. |
| Ayse Kaya | 3.50 | `gpa >= 3.00` | Double major application eligibility rule. |
| Ayse Kaya | 3.50 | `gpa >= 2.80` | Secondary major graduation eligibility rule. |
| Mehmet Demir | 2.40 | `gpa < 2.80` | Part-time student worker GPA threshold rule. |
| Zeynep Arslan | 2.85 | `gpa >= 2.80` | Secondary major graduation eligibility rule. |

## Strongest Rule Sources

| Source | Active rules | Blocking | SQL | Contextual |
|---|---:|---:|---:|---:|
| `bilgi-procedures-and-principles-on-the-education...` | 9 | 2 | 0 | 9 |
| `regulation-on-double-major-minor-and-honors...` | 9 | 7 | 4 | 5 |
| `bursvedestekprogramlariyonergesi.pdf` | 8 | 3 | 2 | 6 |
| `credit-system-bachelors-degree-and-associate-degree...` | 8 | 8 | 2 | 6 |
| `internship_directive.pdf` | 7 | 7 | 0 | 7 |
| `internship-guide.pdf` | 7 | 7 | 0 | 7 |
| `staj-kilavuzu.pdf` | 7 | 7 | 0 | 7 |
| `undergraduate-student-handbook` | 7 | 4 | 2 | 5 |

## Presentation Takeaway

The DB demonstrates the full intended story: regulations were converted into structured action rules, weak/non-actionable candidates were filtered out, deterministic SQL rules caught objective GPA cases, and contextual matching used each student's profile and `extra_context` to produce personalized assignments with reasons.
