# Terraform pattern checklist

- Pin provider and module versions where appropriate.
- Use remote state with access controls, encryption, versioning and locking supported by the chosen backend.
- Separate environments and state; avoid accidental cross-environment plans.
- Use least-privilege execution identities.
- Run formatting, validation, linting and security scans.
- Inspect `terraform plan` before apply.
- Treat replacements, deletions, IAM changes, public exposure and state migration as high risk.
- Never commit state files or secret values.
- Document import, recovery and rollback considerations.
