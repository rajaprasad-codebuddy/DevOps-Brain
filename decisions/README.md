# Architecture decisions

Create one file per decision using `templates/adr.md`. Record the context, decision, alternatives, consequences, status, owner, and date. Do not rewrite old decisions to make history appear different; supersede them with a new ADR.

Note: an ADR's own `Status` field (Proposed / Accepted / Rejected / Superseded) is a different
vocabulary from the Brain's fact-status labels (`CONFIRMED`/`ASSUMPTION`/`PENDING`/`DEPRECATED` — see
root `README.md`) — don't conflate the two when writing or reviewing one.

Search existing decisions before proposing a new one: `python3 scripts/search_brain.py "<keyword>" --category decision`.
