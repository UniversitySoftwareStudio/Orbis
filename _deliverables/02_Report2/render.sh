#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="$SCRIPT_DIR/report"
BUILD_DIR="$SCRIPT_DIR/build"
SOURCE="report2.tex"
OUTPUT="$SCRIPT_DIR/Report2.pdf"
RENDER_LOG="$BUILD_DIR/render.log"

if ! command -v latexmk >/dev/null 2>&1; then
  echo "latexmk is required to render Report2." >&2
  exit 127
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
rm -f "$OUTPUT" \
  "$SCRIPT_DIR/121200152_Atakan_Gul_Report2.pdf" \
  "$SCRIPT_DIR/122200045_Arda_Kaan_Yildiz_Report2.pdf"

echo "Rendering Report2..."
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
  echo "Report2 render failed. Last log lines:" >&2
  tail -n 80 "$RENDER_LOG" >&2
  exit 1
fi

if [[ ! -s "$BUILD_DIR/report2.pdf" ]]; then
  echo "Report2 render finished, but no PDF was produced at $BUILD_DIR/report2.pdf." >&2
  exit 1
fi

cp "$BUILD_DIR/report2.pdf" "$OUTPUT"
cp "$OUTPUT" "$SCRIPT_DIR/121200152_Atakan_Gul_Report2.pdf"
cp "$OUTPUT" "$SCRIPT_DIR/122200045_Arda_Kaan_Yildiz_Report2.pdf"

echo "PDF written to: $OUTPUT"
echo "Moodle copies:"
echo "  $SCRIPT_DIR/121200152_Atakan_Gul_Report2.pdf"
echo "  $SCRIPT_DIR/122200045_Arda_Kaan_Yildiz_Report2.pdf"
echo "Build log: $RENDER_LOG"
