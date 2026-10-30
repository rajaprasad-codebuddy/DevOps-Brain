---
title: "Change safety standard"
category: standard
technology: general
status: CONFIRMED
created: 2026-10-30
last_verified: 2026-10-30
source: "Repository policy (adopted in initial setup)"
---

# Change safety standard

1. Inspect before changing.
2. Explain the proposed change and impact.
3. Use a branch and reviewable diff.
4. Validate syntax, tests, policy and plan output.
5. Obtain required approval before sensitive or production actions.
6. Prefer reversible changes and document rollback.
7. Verify actual outcome after execution.
8. Never put secrets in code, logs, prompts, or Brain documents.

AI agents may draft and test changes in a safe environment. They do not have authority to approve production changes.
