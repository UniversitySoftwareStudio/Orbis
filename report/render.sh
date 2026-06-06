#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="$SCRIPT_DIR"
BUILD_DIR="$REPORT_DIR/build"
SOURCE="$REPORT_DIR/report.tex"
OUTPUT="$REPORT_DIR/report.pdf"
RENDER_LOG="$BUILD_DIR/render.log"

if ! command -v latexmk >/dev/null 2>&1; then
  echo "latexmk is required to render the report." >&2
  exit 127
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
rm -f \
  "$REPORT_DIR"/report.aux \
  "$REPORT_DIR"/report.bbl \
  "$REPORT_DIR"/report.blg \
  "$REPORT_DIR"/report.fdb_latexmk \
  "$REPORT_DIR"/report.fls \
  "$REPORT_DIR"/report.lof \
  "$REPORT_DIR"/report.log \
  "$REPORT_DIR"/report.lot \
  "$REPORT_DIR"/report.out \
  "$REPORT_DIR"/report.synctex.gz \
  "$REPORT_DIR"/report.toc \
  "$OUTPUT"

echo "Rendering report..."
if ! (
  cd "$REPORT_DIR"
  latexmk \
    -pdf \
    -interaction=nonstopmode \
    -halt-on-error \
    -file-line-error \
    -outdir="$BUILD_DIR" \
    report.tex
) >"$RENDER_LOG" 2>&1; then
  echo "Report render failed. Last log lines:" >&2
  tail -n 80 "$RENDER_LOG" >&2
  exit 1
fi

if [[ ! -s "$BUILD_DIR/report.pdf" ]]; then
  echo "Report render finished, but no PDF was produced at $BUILD_DIR/report.pdf." >&2
  exit 1
fi

cp "$BUILD_DIR/report.pdf" "$OUTPUT"

echo "PDF written to: $OUTPUT"
echo "Build log: $RENDER_LOG"
