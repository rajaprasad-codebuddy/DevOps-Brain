# Incident knowledge

Only store sanitized incident summaries. Exclude raw secrets, personal data, customer payloads, and sensitive log lines. Separate timeline facts from hypotheses and confirmed root cause.

A confirmed root cause earns `CONFIRMED` status; an untested hypothesis stays `ASSUMPTION` even after
the incident is closed — closing an incident doesn't retroactively confirm a guess (see root `README.md`
§Fact status).

Search existing incidents before writing a new one up: `python3 scripts/search_brain.py "<keyword>" --category incident`.
