# Security and data handling

## Do not store
- AWS access keys, secret keys, session tokens, passwords, API keys, OAuth tokens, private keys, certificates containing private key material, or recovery codes.
- Raw `.env` files, credential-bearing connection strings, database dumps, unredacted logs, customer personal data, or confidential data without explicit authorization.
- Secrets Manager/Parameter Store secret values. It is acceptable to document a secret's logical name/ARN only if policy permits and it is necessary.

## Safe documentation
- Prefer placeholders such as `<AWS_ACCOUNT_ID>`, `<REGION>`, `<SERVICE_NAME>`, and `<REDACTED>`.
- Record only the minimum resource metadata required to explain architecture.
- Sanitize logs before sharing them with an AI tool.
- Confirm company policy before putting employer or customer infrastructure details in any external AI service.

## Access and review
- Keep the repository private.
- Use MFA and least-privilege access.
- Require review for changes to architecture, security controls, production runbooks, and environment-specific facts.
- Use branch protection and secret scanning where available.
- If a secret is accidentally committed, treat it as exposed: follow the organization's incident process and rotate/revoke it. Deleting the line alone is not sufficient.

## AI boundaries
- AI output is untrusted until reviewed.
- Knowledge updates must not trigger cloud changes.
- Use a separate, least-privilege identity for any later read-only integrations.
