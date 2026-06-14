# Security

## Secrets

Never commit `.env`, API keys, access tokens, passwords, generated resumes, or
the local SQLite database. The repository includes `.env.example` with safe
placeholders and `.gitignore` rules for local secrets and generated files.
The same rule applies to `.streamlit/secrets.toml`; configure deployment
secrets through Streamlit Community Cloud instead.

If a key is accidentally exposed:

1. Revoke it immediately with the API provider.
2. Create a new key.
3. Replace the key only in your local `.env`.
4. Remove the secret from Git history before publishing.

## Candidate Data

Generated resumes, cover letters, tracker records, and contact information can
contain personal data. Keep `outputs/` local and review documents before sharing
or submitting them.

## Private Alpha

The shared-password gate is a basic control for a small invited testing group;
it is not full user authentication. Use a unique testing password, share it
privately, and rotate it if it is exposed.

The per-session AI allowance reduces accidental API usage but is not a
provider-level spending cap. Configure billing alerts or limits with the model
provider as an additional safeguard.

## Reporting

For a public deployment, add a private security-reporting email or GitHub
Security Advisory process before accepting external users.
