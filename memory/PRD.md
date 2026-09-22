# ORCA · Frontend Ocean System Upgrade

## Original problem statement
SIH 2026, problem statement 26176: **ORCA Marine EcOsystem Reasoning with Collaborative Agents**, ISRO / Department of Space. The platform should support multilingual conversational marine intelligence, collaborative agents, satellite and oceanographic reasoning, PFZ discovery, maps, safety alerts, geofencing, routes, evidence, and explainable recommendations.

User's exact frontend request: “I want to upgrade it ui/ux to the out of the box so that the website should feels like something different every element , the style , the design theme , the frontend architecture compsataible with backend and also analyze the current build frontend , cause the changed must be made there only use all the skills you currently have”.

User choices: “Let me create a distinctive, ocean-inspired direction based on the current app”; “Redesign all existing screens and reusable components, preserving functionality”; “It's upto you make note that dont change everything”.

## Architecture and scope
- Existing repository: `/app/orca-frontend` (Next.js16 App Router / React / Framer Motion / Leaflet / Lucide), `/app/orca-backend` (untouched).
- Retain all18 routes, redirects, view state, API methods/payloads, maps, voice handlers, six themes, and language contexts.
- Add isolated Ocean System and landing CSS after the existing stylesheet, rather than rewriting every view.
- Small shared components: LandingControls, ConnectionNotice. Existing Sidebar, Topbar, PageWrapper, StatCard, AppShell enhanced.
- Font stack: Outfit / DM Sans / JetBrains Mono. Default Ocean Depths, saved prior themes honored.
- Supervisor program `orca-frontend`, configuration persisted at `/app/orca-frontend/supervisor.conf`; Next dev on port3000. Env configuration at `.env.local`. No backend configuration or credentials added.

## Implemented
- Editorial ocean-photo landing with clear workspace/copilot/map entry points and preserved map preview.
- Unified shared typography, colors, cards, buttons, forms, tables, status colors, focus states, reduced-motion support.
- Improved grouped navigation, desktop rail, mobile full-text drawer, keyboard trap, Escape close, skip link.
- Dashboard clearer hierarchy, map/outlook tabs, accessible forecast selection, existing PFZ/route/chat flows.
- Real dashboard panel customization with local persistence, functional hide/show toggles and empty state.
- Copilot question-led introduction, agent-domain chips, source-mode labels, conversation autoscroll, retained voice/evidence/map actions.
- Clear shell connection state and explicit sample-data notice in dashboard/copilot. Removed unsupported public institutional-partnership/certified-safety claims from redesigned landing.
- Dark form/table readability and handheld toolbars/tables addressed throughout the existing suite.
- Current-build analysis and rationale in `UI_UX_AUDIT.md`, corrected outdated frontend README.
- Fixed preview development-origin startup configuration. Fixed original mobile sidebar `display:none` conflict and dashboard submetric three-column mobile overflow.

## Verification
- Testing-agent report iteration1: hydration/root-cause diagnostics, working theme interaction after dev-origin correction.
- Testing-agent report iteration2: all18 routes exercised on desktop/mobile; navigation, search, themes/language/sidebar/widget persistence, route forwarding, map controls, alerts UI verified. One dashboard mobile overflow reported and then fixed by main agent.
- Production `yarn build`: successful, all21 static outputs (18 pages plus internal routes), log `/app/orca-build.log`.
- Main-agent final screenshots and checks stored under `/app/`; mobile submetrics measured390px document width at390px viewport after fix. Mobile drawer visibility/Escape and dark form text contrast verified. Fixed clipped map preview controls by making the existing map fill its actual container and wrapping its coordinate readout.
- No actual auth accounts created; see `test_credentials.md` for existing demo identities.

## Known limitations / prioritized backlog
### P0 — required before operational use (outside frontend redesign)
- Backend unavailable in imported environment. Existing offline API fallbacks remain; no live marine/AI/voice/SMS service has been verified. Do not treat UI data as navigational advice.
- Replace legacy synthetic verdicts, safety thresholds, coordinates and source claims with authoritative, source-provenanced backend outputs. Health success does not imply every source is live.
### P1
- Verify real backend integration end-to-end with existing credentials/configuration supplied by project owner.
- Complete translations for legacy and new editorial strings; existing selected-language behavior is retained.
- Real authentication and server-side profile/preferences persistence (existing sign-in is a demo).
- Fisherman-focused compact home view prioritizing weather, departure risk, and local-language questions.
### P2
- Gradual CSS consolidation and splitting of large legacy views into data hooks and presentation components.
- Low-bandwidth mode, source freshness at individual measurement level, shareable marine briefings.

## Next tasks
Confirm the visual direction with the project owner, then prioritize verified source freshness and a compact fisherman-first view without changing backend contracts.
