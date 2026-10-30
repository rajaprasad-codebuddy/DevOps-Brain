#!/usr/bin/env python3
"""Local search over the DevOps Brain's Markdown documents.

No database, no external service, no third-party dependency — just a filesystem walk and some regex,
so it stays usable without any setup as the Brain grows. Read-only: it never modifies a document.

Examples
--------
  python3 scripts/search_brain.py "capacity provider"
  python3 scripts/search_brain.py "CannotPullContainerError" --error
  python3 scripts/search_brain.py --technology ecs --category runbook
  python3 scripts/search_brain.py "fundamentals" --title
  python3 scripts/search_brain.py "PENDING" --runbooks
  python3 scripts/search_brain.py --technology ecs --list
"""
from pathlib import Path
import argparse
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
EXCERPT_MAX_LEN = 160
MAX_EXCERPTS_PER_FILE = 2

CATEGORY_PATH_HINTS = (
    ("core/patterns/", "pattern"),
    ("core/runbooks/", "runbook"),
    ("core/standards/", "standard"),
    ("projects/", "project"),
    ("decisions/", "decision"),
    ("incidents/", "incident"),
    ("learning/", "learning"),
    ("templates/", "template"),
    ("tasks/", "task"),
    ("proposals/", "proposal"),
    ("runbooks/", "runbook"),
)


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


def get_title(text: str, meta: dict):
    if meta.get("title"):
        return meta["title"]
    match = H1_RE.search(text)
    return match.group(1).strip() if match else "(untitled)"


def infer_category(rel: str, meta: dict):
    if meta.get("category"):
        return meta["category"]
    for prefix, category in CATEGORY_PATH_HINTS:
        if rel.startswith(prefix):
            return category
    if Path(rel).name.lower() == "readme.md":
        return "index"
    return "index"


def infer_technology(rel: str, meta: dict):
    if meta.get("technology"):
        return meta["technology"]
    if "/ecs/" in rel:
        return "ecs"
    if "terraform" in rel:
        return "terraform"
    if "github-actions" in rel:
        return "github-actions"
    return "general"


class Document:
    def __init__(self, path: Path):
        self.path = path
        self.rel = path.relative_to(ROOT).as_posix()
        self.text = path.read_text(errors="replace")
        self.meta = parse_frontmatter(self.text)
        self.title = get_title(self.text, self.meta)
        self.category = infer_category(self.rel, self.meta)
        self.technology = infer_technology(self.rel, self.meta)
        self.status = self.meta.get("status")


def load_documents():
    docs = []
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts:
            continue
        docs.append(Document(path))
    return docs


def make_excerpt(line: str, query: str, case_sensitive: bool) -> str:
    line = line.strip().lstrip("#").strip()
    if not case_sensitive:
        idx = line.lower().find(query.lower())
    else:
        idx = line.find(query)
    if idx == -1 or len(line) <= EXCERPT_MAX_LEN:
        return line[:EXCERPT_MAX_LEN] + ("..." if len(line) > EXCERPT_MAX_LEN else "")
    start = max(0, idx - EXCERPT_MAX_LEN // 2)
    end = min(len(line), start + EXCERPT_MAX_LEN)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(line) else ""
    return prefix + line[start:end] + suffix


def search_body(doc: Document, query: str, case_sensitive: bool):
    excerpts = []
    haystack_line_fn = (lambda l: l) if case_sensitive else (lambda l: l.lower())
    needle = query if case_sensitive else query.lower()
    for lineno, line in enumerate(doc.text.split("\n"), start=1):
        if needle in haystack_line_fn(line):
            excerpts.append((lineno, make_excerpt(line, query, case_sensitive)))
            if len(excerpts) >= MAX_EXCERPTS_PER_FILE:
                break
    return excerpts


def matches_filters(doc: Document, args) -> bool:
    if args.technology and doc.technology.lower() != args.technology.lower():
        return False
    if args.category and doc.category.lower() != args.category.lower():
        return False
    if args.runbooks and doc.category != "runbook":
        return False
    return True


def run_search(docs, args):
    results = []
    for doc in docs:
        if not matches_filters(doc, args):
            continue

        if args.query is None:
            results.append((doc, [(0, doc.title)]))
            continue

        if args.title:
            if args.query.lower() in doc.title.lower():
                results.append((doc, [(0, doc.title)]))
            continue

        excerpts = search_body(doc, args.query, case_sensitive=args.error)
        if excerpts:
            results.append((doc, excerpts))
    return results


def print_results(results, args):
    if not results:
        print("No matches.")
        return
    for doc, excerpts in results:
        meta_bits = f"[{doc.category}/{doc.technology}" + (f", {doc.status}" if doc.status else "") + "]"
        print(f"\n{doc.rel} {meta_bits}")
        print(f"  title: {doc.title}")
        for lineno, excerpt in excerpts:
            location = f"L{lineno}: " if lineno else ""
            print(f"  {location}{excerpt}")
    print(f"\n{len(results)} document(s) matched.")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Search the DevOps Brain's Markdown documents (keyword, title, technology, "
                    "category, error message, or runbooks-only).",
    )
    parser.add_argument("query", nargs="?", default=None,
                         help="Keyword or phrase to search for. Omit to just list documents matching "
                              "--technology/--category/--runbooks.")
    parser.add_argument("--technology", help="Filter by technology tag, e.g. ecs, terraform, general.")
    parser.add_argument("--category", help="Filter by category, e.g. pattern, runbook, standard, project.")
    parser.add_argument("--runbooks", action="store_true", help="Shortcut for --category runbook.")
    parser.add_argument("--title", action="store_true",
                         help="Match the query against document titles only, not body text.")
    parser.add_argument("--error", action="store_true",
                         help="Case-sensitive exact-substring search — use for a specific AWS error "
                              "message/string rather than a loose keyword.")
    parser.add_argument("--list", action="store_true",
                         help="List matching documents without requiring a query (same as omitting it).")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.list:
        args.query = None
    if args.query is None and not (args.technology or args.category or args.runbooks or args.list):
        parser.print_help()
        return 1

    docs = load_documents()
    results = run_search(docs, args)
    print_results(results, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
