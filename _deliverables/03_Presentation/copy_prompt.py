#!/usr/bin/env python3
"""Copy a slide's full image prompt (BASE + per-slide) to the clipboard.

Usage:
    ./copy_prompt.py 3        # copies BASE TEMPLATE + Slide 3 prompt
    ./copy_prompt.py          # lists available slides

Parses SLIDE_IMAGE_PROMPTS.md so prompts stay in sync with the source file.
Clipboard support: xclip/xsel/wl-copy (Linux), pbcopy (macOS), clip (Windows).
If no clipboard tool is found, prints the prompt to stdout instead.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).with_name("SLIDE_IMAGE_PROMPTS.md")


def load_sections():
    text = SRC.read_text(encoding="utf-8")
    # Split on H2 headers ("## ...").
    parts = re.split(r"^## ", text, flags=re.M)
    base = None
    slides = {}  # number -> (title, body)
    for part in parts:
        head, _, body = part.partition("\n")
        head = head.strip()
        if head.startswith("BASE TEMPLATE PROMPT"):
            base = body.strip()
        else:
            m = re.match(r"SLIDE (\d+)", head)
            if m:
                slides[int(m.group(1))] = (head, body.strip())
    return base, slides


def extract_prompt(body):
    """Pull the blockquote prompt (lines starting with '> ') out of a section,
    de-quoting and joining it into a clean paragraph."""
    lines = []
    for line in body.splitlines():
        if line.startswith(">"):
            lines.append(line[1:].lstrip())
    # Collapse the wrapped blockquote into flowing text.
    text = " ".join(l for l in lines if l != "").strip()
    return text


def to_clipboard(text):
    candidates = [
        (["wl-copy"], None),
        (["xclip", "-selection", "clipboard"], None),
        (["xsel", "--clipboard", "--input"], None),
        (["pbcopy"], None),
        (["clip"], None),
    ]
    for cmd, _ in candidates:
        if shutil.which(cmd[0]):
            subprocess.run(cmd, input=text.encode("utf-8"), check=True)
            return cmd[0]
    return None


def main():
    base, slides = load_sections()
    if base is None:
        sys.exit("Could not find BASE TEMPLATE PROMPT in SLIDE_IMAGE_PROMPTS.md")

    if len(sys.argv) < 2:
        print("Available slides:")
        for n in sorted(slides):
            title = slides[n][0]
            print(f"  {n:>2}  {title}")
        print("\nUsage: ./copy_prompt.py <slide-number>")
        return

    try:
        n = int(sys.argv[1])
    except ValueError:
        sys.exit(f"Slide number must be an integer, got {sys.argv[1]!r}")

    if n not in slides:
        sys.exit(f"No slide {n}. Available: {', '.join(map(str, sorted(slides)))}")

    title, body = slides[n]
    base_prompt = extract_prompt(base)
    slide_prompt = extract_prompt(body)
    combined = f"{base_prompt}\n\n{slide_prompt}".strip()

    tool = to_clipboard(combined)
    if tool:
        print(f"Copied Slide {n} prompt to clipboard via {tool} "
              f"({len(combined)} chars).")
        print(f"  {title}")
    else:
        print("No clipboard tool found; printing prompt below:\n")
        print(combined)


if __name__ == "__main__":
    main()
