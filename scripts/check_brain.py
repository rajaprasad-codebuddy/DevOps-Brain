#!/usr/bin/env python3
"""DevOps Brain hygiene and structural checks. Not a secret scanner or a factual validator.

Fast and dependency-free (standard library only) by design, so it stays usable as the Brain scales to
hundreds of documents without adding install friction to CI or local use.
"""
from pathlib import Path
import re
import sys
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
ERRORS = []
WARNINGS = []

STATUS_VALUES = {"CONFIRMED", "ASSUMPTION", "PENDING", "DEPRECATED"}

# Files that are purely navigational/meta — not knowledge claims — so status/date/duplicate-title
# checks that make sense for a fact don't make sense for these.
STATUS_EXEMPT_NAMES = {"readme.md", "agents.md", "security.md", "changelog.md"}

# Top-level directories/files treated as repo-root-relative when seen inside backticks, e.g.
# `core/standards/aws-security.md` or `AGENTS.md` — everything else resolves relative to the
# referencing file's own directory.
ROOT_RELATIVE_PREFIXES = (
    "core/", "projects/", "runbooks/", "decisions/", "incidents/", "templates/",
    "scripts/", "tasks/", "proposals/", "learning/",
)
ROOT_RELATIVE_FILENAMES = {"README.md", "AGENTS.md", "SECURITY.md", "CHANGELOG.md"}

# Documents that intentionally use a different status vocabulary (ADR/proposal lifecycle states like
# Proposed/Accepted/Rejected/Superseded), not the Brain's CONFIRMED/ASSUMPTION/PENDING/DEPRECATED facts.
STATUS_ENUM_EXEMPT_PATHS = ("decisions/", "proposals/", "templates/adr.md", "templates/knowledge-update.md")

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
MD_LINK_RE = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")
BACKTICK_MD_PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.md)(#[^`]*)?`")
BOLD_STATUS_RE = re.compile(r"\*\*Status:\*\*\s*([A-Za-z]+)")
BOLD_LAST_VERIFIED_RE = re.compile(r"\*\*Last verified:\*\*\s*([^\n]+)")
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

# Runbooks with the extended 16-section format used under core/runbooks/.
EXTENDED_RUNBOOK_SECTIONS = [
    "symptom", "root cause", "prerequisites", "cli command",
    "resolution option", "risk", "post-resolution verification", "verification status",
]
# Runbooks following the simpler templates/runbook.md shape (top-level runbooks/, project runbooks).
SIMPLE_RUNBOOK_SECTIONS = ["purpose", "precondition", "procedure", "verification", "rollback"]


def strip_code_fences(text: str) -> str:
    """Blank fenced code block contents so link/reference scanning ignores CLI/JSON examples."""
    out_lines = []
    in_fence = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out_lines.append("")
            continue
        out_lines.append("" if in_fence else line)
    return "\n".join(out_lines)


def parse_frontmatter(text: str):
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    meta = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    return meta


def get_status_and_last_verified(text: str, meta: dict):
    status = meta.get("status")
    last_verified = meta.get("last_verified")
    if status is None:
        bold_status = BOLD_STATUS_RE.search(text)
        if bold_status:
            status = bold_status.group(1).upper()
    if last_verified is None:
        bold_lv = BOLD_LAST_VERIFIED_RE.search(text)
        if bold_lv:
            last_verified = bold_lv.group(1).strip()
    return status, last_verified


def runbook_profile(rel: str, name: str):
    if name.lower() == "readme.md":
        return None
    if rel.startswith("core/runbooks/"):
        return "extended"
    if "/runbooks/" in rel:
        return "simple"
    return None


def resolve_candidates(target: str, current_file: Path):
    """Return every plausible resolution of a reference; a reference is broken only if none exist.

    A bare prefix like `runbooks/` is genuinely ambiguous — it could mean the top-level `runbooks/`
    directory, or a `runbooks/` subdirectory next to the referencing file (e.g. a project's own
    `runbooks/`). Trying both and accepting either avoids flagging the latter as broken.
    """
    target = target.split("#", 1)[0].strip()
    if not target:
        return []
    if target.startswith("/"):
        return [ROOT / target.lstrip("/")]
    candidates = [current_file.parent / target]
    if target.startswith(ROOT_RELATIVE_PREFIXES) or target in ROOT_RELATIVE_FILENAMES:
        candidates.append(ROOT / target)
    return candidates


def reference_exists(target: str, current_file: Path) -> bool:
    for candidate in resolve_candidates(target, current_file):
        try:
            if candidate.resolve().exists():
                return True
        except OSError:
            continue
    return False


def check_links(path: Path, rel: str, scanned_text: str):
    for match in MD_LINK_RE.finditer(scanned_text):
        target = match.group(1).strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if not reference_exists(target, path):
            ERRORS.append(f"{rel}: broken link target '{target}'")

    for match in BACKTICK_MD_PATH_RE.finditer(scanned_text):
        target = match.group(1).strip()
        if not reference_exists(target, path):
            WARNINGS.append(f"{rel}: backtick reference to missing file '{target}'")


def check_runbook_sections(path: Path, rel: str, scanned_text: str):
    profile = runbook_profile(rel, path.name)
    if profile is None:
        return
    headings = "\n".join(
        line for line in scanned_text.split("\n") if line.strip().startswith("#")
    ).lower()
    required = EXTENDED_RUNBOOK_SECTIONS if profile == "extended" else SIMPLE_RUNBOOK_SECTIONS
    missing = [section for section in required if section not in headings]
    if missing:
        ERRORS.append(f"{rel}: runbook missing required section(s): {', '.join(missing)}")


def check_status_metadata(path: Path, rel: str, text: str, meta: dict):
    if path.name.lower() in STATUS_EXEMPT_NAMES:
        return
    status, last_verified = get_status_and_last_verified(text, meta)
    if status is None:
        WARNINGS.append(f"{rel}: no knowledge status found (frontmatter `status:` or **Status:**)")
        return
    if status not in STATUS_VALUES and not rel.startswith(STATUS_ENUM_EXEMPT_PATHS):
        WARNINGS.append(f"{rel}: status '{status}' is not one of {sorted(STATUS_VALUES)}")
    if status == "CONFIRMED" and (not last_verified or last_verified.strip().lower() == "unknown"):
        WARNINGS.append(f"{rel}: status is CONFIRMED but last_verified is missing or 'Unknown'")


def check_secrets(path: Path, rel: str, text: str):
    # Heuristic only: catches obvious accidental credential assignments, not all secrets.
    patterns = [
        (r"(?i)\bAKIA[0-9A-Z]{16}\b", "possible AWS long-term access key"),
        (r"(?i)\bASIA[0-9A-Z]{16}\b", "possible AWS temporary (STS) access key"),
        (r"(?i)(aws_secret_access_key|api_key|access_token|password)\s*[:=]\s*['\"]?[^<\s'\"]{8,}",
         "possible hard-coded secret"),
        (r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----", "private-key header"),
    ]
    for pattern, message in patterns:
        if re.search(pattern, text):
            ERRORS.append(f"{rel}: {message}; inspect safely and remove any secret")


def check_file(path: Path, title_registry: dict):
    text = path.read_text(errors="replace")
    rel = path.relative_to(ROOT).as_posix()

    if not text.strip():
        ERRORS.append(f"{rel}: empty Markdown file")
        return  # nothing else is meaningful to check on an empty file
    if "\t" in text:
        WARNINGS.append(f"{rel}: contains tabs; check formatting")

    check_secrets(path, rel, text)

    meta = parse_frontmatter(text)
    scanned_text = strip_code_fences(text)

    check_links(path, rel, scanned_text)
    check_runbook_sections(path, rel, scanned_text)
    check_status_metadata(path, rel, text, meta)

    title = meta.get("title") or next(iter(H1_RE.findall(text)), None)
    if title:
        title_registry[title.strip().lower()].append(rel)

    # Preserve the original, narrower project-metadata nudge for backward compatibility.
    if rel.startswith("projects/") and rel.count("/") >= 2:
        if path.name.lower() not in {"readme.md"} and not any(
            marker in text for marker in ("**Status:**", "**Last verified:**")
        ) and "status" not in meta:
            WARNINGS.append(f"{rel}: add Status and Last verified metadata")


def check_duplicate_titles(title_registry: dict):
    for title, files in sorted(title_registry.items()):
        if len(files) > 1:
            WARNINGS.append(f"Duplicate title '{title}' used in: {', '.join(sorted(files))}")


def main():
    md_files = sorted(ROOT.rglob("*.md"))
    title_registry = defaultdict(list)
    for path in md_files:
        if ".git" not in path.parts:
            check_file(path, title_registry)
    check_duplicate_titles(title_registry)

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
    print("Note: this is a hygiene/structure check, not a comprehensive secret scanner or factual validator.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
