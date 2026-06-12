#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="$SCRIPT_DIR/report"
BUILD_DIR="$SCRIPT_DIR/build"
SOURCE="report1.tex"
OUTPUT="$SCRIPT_DIR/Report1.pdf"
RENDER_LOG="$BUILD_DIR/render.log"

# Ensure BibTeX resolves the report-local bibliography instead of any MiKTeX system copy.
export BIBINPUTS="$REPORT_DIR${BIBINPUTS:+;$BIBINPUTS}"

if ! command -v latexmk >/dev/null 2>&1; then
  echo "latexmk is required to render Report1." >&2
  exit 127
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
rm -f "$OUTPUT" \
  "$SCRIPT_DIR/121200152_Atakan_Gul_Report1.pdf" \
  "$SCRIPT_DIR/122200045_Arda_Kaan_Yildiz_Report1.pdf"

echo "Rendering Report1..."
if ! (
  cd "$REPORT_DIR"
  latexmk \
    -pdf \
    -interaction=nonstopmode \
    -halt-on-error \
    -file-line-error \
    -outdir="$BUILD_DIR" \
    "$SOURCE"
) >"$RENDER_LOG" 2>&1; then
  echo "Report1 render failed. Last log lines:" >&2
  tail -n 80 "$RENDER_LOG" >&2
  exit 1
fi

if [[ ! -s "$BUILD_DIR/report1.pdf" ]]; then
  echo "Report1 render finished, but no PDF was produced at $BUILD_DIR/report1.pdf." >&2
  exit 1
fi

cp "$BUILD_DIR/report1.pdf" "$OUTPUT"
cp "$OUTPUT" "$SCRIPT_DIR/121200152_Atakan_Gul_Report1.pdf"
cp "$OUTPUT" "$SCRIPT_DIR/122200045_Arda_Kaan_Yildiz_Report1.pdf"

echo "PDF written to: $OUTPUT"
echo "Moodle copies:"
echo "  $SCRIPT_DIR/121200152_Atakan_Gul_Report1.pdf"
echo "  $SCRIPT_DIR/122200045_Arda_Kaan_Yildiz_Report1.pdf"
echo "Build log: $RENDER_LOG"
