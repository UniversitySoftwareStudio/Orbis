#!/usr/bin/env bash
#
# build_sent.sh — assemble the final Moodle submission set under ../_sent/
#
# Dumps every artifact FLAT under each student's folder (no per-artifact
# subfolders), named exactly as the CMPE 492 announcement requires:
#
#   _sent/<studentid_name_surname>/
#       <stem>_Report1.pdf
#       <stem>_Report2.pdf
#       <stem>_presentation.pptx
#       <stem>_code.zip
#       <stem>_video.mpg
#       <stem>_poster.pdf
#       <stem>_latex_project.zip      (CMPR492-Latex Project slot)
#
# Idempotent: rebuilds _sent/ from scratch each run. Self-contained: builds the
# code zip and transcodes the video if those intermediates are missing.
#
# Run from anywhere:  bash _deliverables/build_sent.sh
set -euo pipefail

# --- locate repo root (this script lives in <root>/_deliverables) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEL="$ROOT/_deliverables"
SENT="$ROOT/_sent"

# --- team members (Moodle filename stems) ---
STEMS=(
  "121200152_Atakan_Gul"
  "122200045_Arda_Kaan_Yildiz"
)

say() { printf '  %s\n' "$*"; }

# --- 1. shared sources (one copy each, reused for every student) ---
REPORT1_DIR="$DEL/01_Report1"
REPORT2_DIR="$DEL/02_Report2"
PRESENTATION_PPTX="$DEL/03_Presentation/CMPE 492 - Orbis - Final Presentation.pptx"
POSTER_DIR="$DEL/06_Poster"
LATEX_ZIP="$DEL/07_Latex_Project/Orbis_LaTeX_Project.zip"
VIDEO_SRC_MP4="$DEL/05_Video/demo_video/orbis-demo.mp4"
VIDEO_MPG="$DEL/05_Video/orbis-demo.mpg"

# --- 2. build the code zip if missing (tracked source only, lean) ---
build_code_zip() {
  local out="$1"
  echo "Building code zip (lean: tracked source, no generated/media)..."
  local stage; stage="$(mktemp -d)"
  git -C "$ROOT" archive --format=tar HEAD | tar -x -C "$stage"
  # drop non-code: media/deliverable folders + generated artifacts + large seed data
  rm -rf "$stage/_deliverables" "$stage/_archive" "$stage/_sent" \
         "$stage/.github/instructions" \
         "$stage/api/scripts/categorization/url_embeddings.json" \
         "$stage/api/scripts/categorization/url_clusters.json" \
         "$stage/api/scripts/categorization/cluster_samples.json" \
         "$stage/api/scripts/categorization/subcluster_samples.json" \
         "$stage/api/scripts/experiments/results" \
         "$stage/api/data/rag_evaluation_logs.jsonl" 2>/dev/null || true
  find "$stage/api/scripts/ingest" -maxdepth 1 -name '*.jsonl' -size +1M -delete 2>/dev/null || true
  ( cd "$stage" && mkdir Orbis && find . -maxdepth 1 ! -name . ! -name Orbis -exec mv {} Orbis/ \; \
      && zip -rq "$out" Orbis -x '*.DS_Store' )
  rm -rf "$stage"
}

# --- 3. transcode the video to .mpg if missing ---
build_video_mpg() {
  local src="$1" out="$2"
  echo "Transcoding demo video to .mpg..."
  ffmpeg -y -loglevel error -i "$src" \
    -c:v mpeg2video -b:v 4000k -c:a mp2 -b:a 192k -f mpeg "$out"
}

# === preflight: ensure all required sources exist / can be built ===
[ -f "$PRESENTATION_PPTX" ] || { echo "ERROR: missing presentation PPTX: $PRESENTATION_PPTX"; exit 1; }
[ -f "$LATEX_ZIP" ]        || { echo "ERROR: missing LaTeX zip: $LATEX_ZIP"; exit 1; }
[ -f "$VIDEO_MPG" ] || { [ -f "$VIDEO_SRC_MP4" ] || { echo "ERROR: no video source ($VIDEO_SRC_MP4) and no $VIDEO_MPG"; exit 1; }; build_video_mpg "$VIDEO_SRC_MP4" "$VIDEO_MPG"; }

CODE_ZIP="$(mktemp -d)/Orbis_code.zip"
build_code_zip "$CODE_ZIP"

# === assemble: wipe and rebuild _sent/, flat per student ===
echo "Assembling _sent/ ..."
rm -rf "$SENT"
mkdir -p "$SENT"

for stem in "${STEMS[@]}"; do
  dst="$SENT/$stem"
  mkdir -p "$dst"
  cp "$REPORT1_DIR/${stem}_Report1.pdf" "$dst/${stem}_Report1.pdf"
  cp "$REPORT2_DIR/${stem}_Report2.pdf" "$dst/${stem}_Report2.pdf"
  cp "$PRESENTATION_PPTX"               "$dst/${stem}_presentation.pptx"
  cp "$CODE_ZIP"                        "$dst/${stem}_code.zip"
  cp "$VIDEO_MPG"                       "$dst/${stem}_video.mpg"
  cp "$POSTER_DIR/${stem}_Poster.pdf"   "$dst/${stem}_poster.pdf"
  cp "$LATEX_ZIP"                       "$dst/${stem}_latex_project.zip"
  say "built $stem ($(ls -1 "$dst" | wc -l | tr -d ' ') files)"
done
rm -rf "$(dirname "$CODE_ZIP")"

# === verify: exactly the 7 expected names per student, nothing else ===
echo "Verifying names..."
status=0
for stem in "${STEMS[@]}"; do
  expected=(
    "${stem}_Report1.pdf" "${stem}_Report2.pdf" "${stem}_presentation.pptx"
    "${stem}_code.zip" "${stem}_video.mpg" "${stem}_poster.pdf"
    "${stem}_latex_project.zip"
  )
  for name in "${expected[@]}"; do
    [ -s "$SENT/$stem/$name" ] || { echo "  MISSING/EMPTY: $stem/$name"; status=1; }
  done
  # flag anything unexpected
  while IFS= read -r f; do
    keep=0; for name in "${expected[@]}"; do [ "$f" = "$name" ] && keep=1; done
    [ "$keep" = 1 ] || { echo "  UNEXPECTED: $stem/$f"; status=1; }
  done < <(ls -1 "$SENT/$stem")
done

echo
echo "=== _sent/ ==="
( cd "$SENT" && find . -type f | sed 's|^\./|  |' | sort )
echo
if [ "$status" = 0 ]; then
  echo "OK — 7 correctly-named artifacts per student. Ready to upload."
else
  echo "DONE WITH WARNINGS (see above)."
fi
exit "$status"
