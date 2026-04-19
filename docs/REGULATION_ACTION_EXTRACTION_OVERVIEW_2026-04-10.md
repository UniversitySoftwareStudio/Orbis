REGULATION ACTION EXTRACTION
============================

SYSTEM FLOW
-----------

Categorization pipeline
  -> regulation document set
  -> 80 regulation documents
  -> 935 KB chunks
  -> LLM pass 1: extract action objects
  -> LLM pass 2: review / fix / remove
  -> quality gates: timing + specificity + dedup
  -> stored action objects
  -> student / staff matching


FINAL RESULT
------------

Documents total      -> 80
Done                 -> 59
Skipped              -> 21
Failed               -> 0

Accepted actions     -> 178
Blocking actions     -> 108
Non-blocking         -> 70

Contextual actions   -> 167
SQL actions          -> 11

Student              -> 153
Staff                -> 11
Admin                -> 9
All                  -> 5


OUTPUT OBJECT
-------------

Action object
  -> rule_text
  -> applies_to
  -> trigger
  -> deadline
  -> valid_from
  -> valid_until
  -> blocking
  -> consequence
  -> authority
  -> exceptions
  -> target_role
  -> match_type
  -> sql_condition
  -> confidence
  -> evidence_quote


TOP DOCUMENTS
-------------

regulation-on-double-major-minor-and-honors-programs.pdf
  -> 9 actions

education-training-and-examination-precautions-for-the-disabled-students.pdf
  -> 9 actions

bursvedestekprogramlariyonergesi.pdf
  -> 8 actions

credit-system-bachelors-degree-and-associate-degree-education-and-examination-regulation
  -> 8 actions

undergraduate-student-handbook
  -> 7 actions


SAMPLE ACTIONS
--------------

Internship timing
  -> Do not begin a compulsory internship before the summer following the end of your 4th semester.
  -> Trigger: when the student is deciding when to schedule an internship
  -> Blocking: true
  -> Consequence: internship will not be accepted

Internship documents
  -> Submit internship contract forms at least 10 working days before the internship start date.
  -> Trigger: before the internship starts
  -> Blocking: true
  -> Consequence: internship cannot proceed

Graduation project
  -> Find a project advisor within the first two weeks of the first semester.

Student exams
  -> Bring your university identification card to every examination.


FILTERED OUT
------------

Expired announcements
  -> removed

Blank forms
  -> removed

Committee workflow
  -> removed

Purpose / definition text
  -> removed

Generic awareness items
  -> removed


MAIN FILES
----------

/home/zperson/Orbis/api/events/orchestrator.py
/home/zperson/Orbis/api/events/student_agent.py
/home/zperson/Orbis/api/database/models/events.py

