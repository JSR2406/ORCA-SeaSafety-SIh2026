# ORCA · Frontend design assessment

## Scope
An incremental, frontend-only redesign for SIH 2026 / PS 26176. The brief was to make ORCA distinctive while **not changing everything**. All 18 existing routes, redirects, backend endpoint paths, request/response shapes, map interactions, voice handlers, language choices, and six saved theme choices remain available. No files under `orca-backend` were modified.

## What the existing build showed
- **Architecture:** Next.js App Router, React client views, Framer Motion, Lucide, Leaflet with existing Google tile helpers. The frontend README was outdated (it described Vite).
- **Presentation:** a ~9,800-line global stylesheet with repeated overrides, small typography, hard-coded light surfaces in dark themes, fixed-width toolbars, and dense bulletin layouts.
- **Continuity:** most features already share AppShell, Topbar, Sidebar, Card, Badge, and StatCard. Enhancing those surfaces gives the existing suite a coherent identity without replacing its business logic.
- **Data clarity:** the supplied API client uses sample fallbacks when services are unreachable. Some old labels implied live data or certified safety regardless of connection. The new shell, dashboard, and copilot distinguish preview data from API responses. This does not validate the legacy sample dataset or convert it into operational advice.
- **Environment:** the imported project contained no configured API credentials or working backend process. Next.js dev-origin configuration required adjustment for the preview proxy. Client interactions were verified after the fix.

## Design approach: Ocean System
- **Identity:** deep navy surfaces, luminous seafoam, restrained glass, fine chart-like rules, understated status colors.
- **Typography:** Outfit for expressive headings, DM Sans for readable controls, JetBrains Mono for coordinates and telemetry.
- **Entry experience:** an editorial, ocean-photography hero; three direct task entry points; the existing interactive map; a concise collaborative-agent story.
- **Workspace:** familiar grouped sidebar, consistent heading hierarchy, quieter cards, legible forms and dark-mode tables, clear connection notice, keyboard focus and reduced-motion support.
- **Dashboard:** preserved telemetry, chart/outlook switch, forecasts, PFZ route links, hazards and inline chat. Customization now shows/hides actual panels and persists locally.
- **Copilot:** retained conversation, source citations, voice and map/route actions. Added a clear question-led introduction, domain chips, source-mode labels and a more readable message hierarchy.
- **Responsive:** mobile navigation retains full text even when desktop rail mode was saved. Drawer keyboard trap/Escape handling, responsive tables and wrapping toolbars improve handheld use.

## Frontend architecture decisions
`src/ocean-system.css` is an isolated presentation layer loaded after the existing stylesheet. `src/landing.css` scopes the new public page. These avoid a risky rewrite of the legacy CSS during a broad UI upgrade. New `LandingControls` and `ConnectionNotice` are small reusable components. Existing React contexts and the central API service remain authoritative.

## Remaining work (separate from this UI scope)
1. Connect and verify the actual marine, weather, AI, voice, database, and authoritative geofence services. Never use preview data for navigation.
2. Replace legacy synthetic advisories and inferred safety verdicts with source-provenanced backend responses. A successful health check alone does not validate every dataset.
3. Complete translation coverage for the existing English-only text and new editorial copy.
4. Gradually consolidate legacy CSS and split large views along data/presentation boundaries, rather than replacing working features wholesale.
5. Implement real authenticated profiles and server-side preference persistence; the supplied role-selection sign-in remains a demo flow.

## Asset
Ocean aerial photograph: Unsplash, photo `1619128198504-9ec7a232a38e`; downloaded to `public/images/ocean-aerial.jpg` for reliable rendering.