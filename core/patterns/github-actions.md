# GitHub Actions security checklist

- Prefer OIDC to long-lived cloud credentials.
- Set minimum required `permissions` at workflow/job level.
- Pin third-party actions to verified immutable SHAs where organizational policy requires it.
- Use protected environments and required reviewers for production.
- Do not expose secrets to untrusted pull-request code.
- Validate artifacts and restrict who can publish/deploy them.
- Run tests and security scans before deployment.
- Use explicit timeouts and concurrency controls where appropriate.
- Keep deployment credentials separate from build/test permissions.
