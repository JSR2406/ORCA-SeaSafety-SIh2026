"""Hard constraints: restricted/geofence cells must be impassable, never just costly."""


def apply_constraints(blocked_cells: list, candidate_cells: list) -> list:
    blocked = set(blocked_cells)
    return [c for c in candidate_cells if c not in blocked]
