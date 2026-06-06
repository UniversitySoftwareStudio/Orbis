# Data Folder

This folder contains JSONL files with scraped university data. The actual data files are gitignored.

It also contains report-facing ground-truth artifacts under
`api/data/ground_truth/`; those are intentionally committed because they support
the report's quantitative evaluation.

## Data Structure

- `*_courses_data.jsonl` - Course information
- `*_university_data.jsonl` - General university information  
- `*_pdfs_*.jsonl` - PDF document contents

See `*_example.jsonl` files for data structure examples.

## Ground Truth

- `ground_truth/events/`: silver labels for event extraction and assignment
  matching, plus inter-judge validation summary.
- `ground_truth/submissions/`: deterministic 32-case submission-review suite
  and latest result JSONL.
