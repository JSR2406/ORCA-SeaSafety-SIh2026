"""Dynamic cell cost: distance + wave/wind/current + hazard + geofence penalties."""


def cell_cost(distance_km: float = 1.0, wave_risk: float = 0.0, wind_risk: float = 0.0,
              current_risk: float = 0.0, hazard_penalty: float = 0.0,
              geofence_penalty: float = 0.0, mode: str = "BALANCED") -> float:
    w = {"SHORTEST": (1.0, 0.2), "SAFEST": (0.2, 1.0), "BALANCED": (0.6, 0.6)}[mode]
    return w[0] * distance_km + w[1] * (wave_risk + wind_risk + current_risk) \
        + hazard_penalty + geofence_penalty
