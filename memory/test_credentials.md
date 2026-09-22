# ORCA test credentials

## Harbour authority operator (backend alert publishing)
Used by: `POST /api/v1/auth/login` on the FastAPI backend (`/app/orca-backend`), and the
"Harbour tools" sign-in on the frontend `/alerts` page.

- Email: `harbour.authority@orca.gov.in`
- Password: `OrcaHarbour#2026`
- Role: `authority`

Source of truth: `/app/orca-backend/.env` (`AUTH_OPERATOR_EMAIL`, `AUTH_OPERATOR_PASSWORD`,
`AUTH_JWT_SECRET`). Publishing and acknowledging safety alerts requires this token
(`Authorization: Bearer <access_token>`, 8 hour expiry).

Note: the FastAPI backend is NOT running in this preview environment, so a live sign-in from
the UI will fail with "service unavailable". The gate itself is verified by
`/app/tests/verify_alert_auth.py`.

## Frontend demo identities
The `/login` page is still a demo (no real authentication). Any email/password combination
enters the app, and "Continue as Public Observer" skips the form entirely. Displayed user
"Dr. Ananya Kumar / Oceanographer · INCOIS" is sample data, not an account.
