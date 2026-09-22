# Contract versioning (Phase 10 - Part 48).
#
# These constants are the single source of truth for the public integration
# contract version.  Bump RESPONSE_SCHEMA_VERSION / EVENT_SCHEMA_VERSION when
# the corresponding schema changes in a non-backwards-compatible way and expose
# the new shape under a new version rather than silently mutating v1.
#
# API_VERSION is the URL path segment (/api/v1/).  A breaking change that
# cannot be additive must introduce /api/v2/ and leave /api/v1/ intact.

API_VERSION = "1"

# Version of the canonical OrchestrationResponse shape returned by the API.
RESPONSE_SCHEMA_VERSION = "1.0"

# Version of the streaming event envelope and enumerated event names.
EVENT_SCHEMA_VERSION = "1.0"

# Metadata returned alongside every orchestration response so the frontend can
# assert it is parsing the schema it was built against.
def contract_meta() -> dict:
    return {
        "api_version": API_VERSION,
        "response_schema_version": RESPONSE_SCHEMA_VERSION,
        "event_schema_version": EVENT_SCHEMA_VERSION,
    }
