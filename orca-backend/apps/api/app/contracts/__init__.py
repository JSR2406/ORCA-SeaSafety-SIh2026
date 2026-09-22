# FloatChat public integration contracts.
#
# These models are the STABLE, VERSIONED boundary between the backend and an
# independently developed frontend.  They are intentionally domain-neutral and
# free of internal implementation detail (no agents, MCP, planner, executor,
# database, or Python modules are exposed).
#
# The frontend treats the backend as a black box and only consumes these
# contracts (plus OpenAPI and the example fixtures).
