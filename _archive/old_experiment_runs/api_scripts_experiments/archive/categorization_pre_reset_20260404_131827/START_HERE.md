# Start Here (Clean Flow)

Use this single entrypoint:

```bash
python3 -u api/scripts/experiments/categorization/00_run_flow.py list
```

Most common commands:

```bash
# 1) URL umbrella groups
python3 -u api/scripts/experiments/categorization/00_run_flow.py 01 -- --sample-size 0 --dynamic-depth --min-depth 2 --max-depth 3 --min-parent-docs 6 --similarity-threshold 0.85

# 2) Tail-depth decisions
python3 -u api/scripts/experiments/categorization/00_run_flow.py 02 -- --input-json <umbrella_json>

# 3) AI input gate
python3 -u api/scripts/experiments/categorization/00_run_flow.py 04 -- --depth-json <depth_json> --umbrella-json <umbrella_json> --include-decisions url_only_parent,url_only_categorize

# 4) Pass-1 tree + pass-2 merge
python3 -u api/scripts/experiments/categorization/00_run_flow.py 06 -- --input-json <ai_taxonomy_json>
python3 -u api/scripts/experiments/categorization/00_run_flow.py 07 -- --depth-json <depth_json> --umbrella-json <umbrella_json> --pass1-ai-json <ai_taxonomy_json> --pass1-tree-json <tree_json> --model-id 6

# 5) Clean output folder
python3 -u api/scripts/experiments/categorization/00_run_flow.py 90 -- --run-name taxonomy_clean --update-latest-link --archive-source-files
```

Directory clarity rule:
- Open `api/scripts/experiments/results/categorization/latest_clean_run/` first.
