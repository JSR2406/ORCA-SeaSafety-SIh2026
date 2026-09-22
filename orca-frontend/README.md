# ORCA Marine Intelligence Frontend

A Next.js App Router frontend for ORCA marine intelligence. The Ocean System refresh preserves the original feature suite and backend request contracts while improving typography, navigation, responsive layouts, and data-source clarity.

## Pages / routes

- `/` — Landing Page
- `/login` — Login
- `/dashboard` — Dashboard
- `/marine-map` — Marine Explorer / Map
- `/ai-copilot` — AI Copilot Chat
- `/fishing` — Fishing Intelligence
- `/safety` — Safety Center
- `/routes` — Route Planner
- `/scenarios` — Scenario Lab
- `/alerts` — Alerts Center
- `/knowledge` — Knowledge Center
- `/analytics` — Analytics
- `/ml-governance` — ML Governance
- `/system-health` — System Health
- `/settings` — User Profile & Settings
- `/mobile` — Mobile View mockups
- `/multilingual` — Multilingual Support
- `/workflow` — AI Workflow Architecture

## Run locally

```bash
yarn install
yarn dev
```

Set `NEXT_PUBLIC_API_URL` to your existing ORCA API origin in `.env.local`, then open the Next.js URL shown in the terminal. `ORCA_API_UPSTREAM` optionally controls the server-side API rewrite. For proxied development, configure `ORCA_DEV_ORIGINS` with the allowed hostnames. Do not include secret server keys in `NEXT_PUBLIC_` variables.

## Design architecture

- `src/styles.css`: existing feature styles and map layouts.
- `src/ocean-system.css`: shared theme, shell, dashboard, copilot, and responsive refinements.
- `src/landing.css`: scoped public landing experience.
- `src/components/LandingControls.jsx`: theme/language/menu controls using the existing contexts.
- `src/components/ConnectionNotice.jsx`: visible API connection and preview-data status.
- `UI_UX_AUDIT.md`: existing-build assessment, design rationale, preserved contracts, and follow-up recommendations.

Production verification: `yarn build`. All 18 existing pages remain available.

## Notes

The existing API client attempts live backend requests and falls back to sample data when unavailable. This redesign does not configure backend services or add authentication. The supplied sign-in is a role-selection demo. Preview marine data and illustrative advisories must not be used for navigation or safety decisions.
