# Runbook: deploy service

- **Status:** PENDING
- **Owner:** Unknown
- **Last verified:** Unknown
- **Environment:** `<environment>`
- **Risk:** Medium until reviewed
- **Approval required:** Confirm project policy before use

## Purpose
Describe what this runbook deploys and what it does not change.

## Preconditions
- [ ] Correct repository and branch confirmed.
- [ ] Target environment explicitly confirmed.
- [ ] Required approvals obtained.
- [ ] CI checks passed.
- [ ] Rollback path is available.
- [ ] No unresolved high-severity security findings.

## Procedure
1. Inspect the deployment diff and artifact version.
2. Review the deployment plan and impact.
3. Obtain required approval.
4. Execute the approved deployment using the team's established process.
5. Verify service health, logs, metrics and smoke tests.

## Verification
- Expected health:
- Logs/metrics to inspect:
- Smoke test:
- Success criteria:

## Rollback / stop conditions
- Stop if the target environment is ambiguous or the plan contains unexpected destructive changes.
- Roll back using the approved project-specific procedure if verification fails.
- Record the actual outcome; do not assume success.

## Evidence and update history
- Source:
- Last execution:
- Outcome:
