#!/usr/bin/env python3
"""Lightweight DevOps Brain hygiene checks. Not a secret scanner."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ERRORS = []
WARNINGS = []

def check_file(path: Path):
    text = path.read_text(errors="replace")
    rel = path.relative_to(ROOT).as_posix()

    if not text.strip():
        ERRORS.append(f"{rel}: empty Markdown file")
    if "\t" in text:
        WARNINGS.append(f"{rel}: contains tabs; check formatting")

    # Heuristic only: catches obvious accidental credential assignments, not all secrets.
    patterns = [
        (r"(?i)\bAKIA[0-9A-Z]{16}\b", "possible AWS access key"),
        (r"(?i)(aws_secret_access_key|api_key|access_token|password)\s*[:=]\s*['\"]?[^<\s'\"]{8,}", "possible hard-coded secret"),
        (r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", "private-key header"),
    ]
    for pattern, message in patterns:
        if re.search(pattern, text):
            ERRORS.append(f"{rel}: {message}; inspect safely and remove any secret")

    if rel.startswith("projects/") and rel.count("/") >= 2:
        # Encourage metadata for substantive project docs, excluding readmes.
        if path.name.lower() not in {"readme.md"} and not any(
            marker in text for marker in ("**Status:**", "**Last verified:**")
        ):
            WARNINGS.append(f"{rel}: add Status and Last verified metadata")

def main():
    md_files = sorted(ROOT.rglob("*.md"))
    for path in md_files:
        if ".git" not in path.parts:
            check_file(path)

    if ERRORS:
        print("ERRORS:")
        for item in ERRORS:
            print(f"- {item}")
    if WARNINGS:
        print("WARNINGS:")
        for item in WARNINGS:
            print(f"- {item}")

    if ERRORS:
        print(f"\nFailed: {len(ERRORS)} error(s), {len(WARNINGS)} warning(s).")
        return 1
    print(f"Passed: {len(md_files)} Markdown file(s), {len(WARNINGS)} warning(s).")
    print("Note: this is a hygiene check, not a comprehensive secret scanner or factual validator.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
