# Baseline Paper Fetch Log

Official comparator candidates for subsystem-level baselines. Use these as
source records before adding citations or baseline tables to `report.tex`.

## Fetched Locally

- `assayed_2024_academic_advising_chatbots_review.pdf`
  - Official source: Springer LNCE chapter.
  - DOI: `10.1007/978-3-031-56121-4_33`
  - Use: academic-advising chatbot landscape, systematic review.
  - Key reported basis: PRISMA review screened 128 articles and included 11.

- `ismail_2025_academic_advising_llm_official_record.html`
  - Official source: Zayed University institutional repository / IEEE EDUCON record.
  - DOI: `10.1109/EDUCON62633.2025.11016582`
  - Use: academic-advising chatbot metric comparator.
  - Key reported metrics: BLEU 0.45 to 0.78, ROUGE-L 0.85, 50-student feedback
    with ratings 4.6/5 accuracy, 4.7/5 clarity, 4.8/5 time efficiency.

- `zhang_elgohary_2017_construction_regulation_ie_official_record.html`
  - Official source: University of Illinois Experts record for ASCE Journal of
    Computing in Civil Engineering.
  - DOI: `10.1061/(ASCE)CP.1943-5487.0000346`
  - Use: regulatory information extraction comparator.
  - Key reported metrics: precision 0.969 and recall 0.944 on quantitative
    requirements from the 2009 International Building Code.

- `wick_2016_dars_degree_audit_official_record.html`
  - Official source: The Keep / Journal of the North American Management Society.
  - Use: conventional degree-audit system comparator, mostly non-metric.
  - Note: official page exposes a PDF link, but direct command-line PDF fetch
    returned 403. Keep as official landing-page record unless manually accessed.

## Official Links Not Downloaded Locally

- Galli et al., "Approaching the AI Act... with AI: LLMs and knowledge graphs to
  extract and analyse obligations"
  - Official source: ScienceDirect, Computer Law & Security Review.
  - DOI: `10.1016/j.clsr.2025.106230`
  - URL: `https://www.sciencedirect.com/science/article/pii/S2212473X25001026`
  - Use: legal obligation extraction comparator.
  - Key reported metrics from official abstract: 93% precision in obligation
    filtering and over 99% accuracy in obligation type/addressee/predicate
    classification.
  - Note: open-access page is accessible, but direct PDF/HTML command-line fetch
    returned 403.

- Cisneros-Gonzalez et al., "JorGPT: Instructor-Aided Grading of Programming
  Assignments with Large Language Models (LLMs)"
  - Official source: MDPI Future Internet.
  - DOI: `10.3390/fi17060265`
  - URL: `https://www.mdpi.com/1999-5903/17/6/265`
  - Use: LLM-assisted submission grading/workload comparator.
  - Key reported metrics from official abstract: adjusted R^2 0.9156, mean
    absolute error 0.4579, 672 submissions, over 300 hours of manual work reduced
    to under 15 minutes of automated processing.
  - Note: official page is accessible in browser tooling, but direct command-line
    fetch returned 403.
