"""Route graph + A* optimizer over a risk-weighted grid. No neural route planner."""
from dataclasses import dataclass
from typing import Dict, List, Literal, Tuple
import heapq

Mode = Literal["SHORTEST", "SAFEST", "BALANCED"]


@dataclass
class RouteResult:
    mode: Mode
    distance_km: float
    risk_score: float
    waypoints: List[Tuple[float, float]]
    hazard_intersections: List[str]
    eta_minutes: float = 0.0


def astar(grid_cost: Dict[Tuple[int, int], float], start: Tuple[int, int],
          goal: Tuple[int, int]) -> List[Tuple[int, int]]:
    """Minimal A* on a 4-connected grid; blocked cells absent from grid_cost."""
    openh = [(0.0, start)]; came: Dict = {}; g = {start: 0.0}

    def h(a: Tuple[int, int]) -> float:
        return abs(a[0] - goal[0]) + abs(a[1] - goal[1])

    while openh:
        _, cur = heapq.heappop(openh)
        if cur == goal:
            path = [cur]
            while cur in came:
                cur = came[cur]; path.append(cur)
            return list(reversed(path))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt not in grid_cost:
                continue
            ng = g[cur] + grid_cost[nxt]
            if ng < g.get(nxt, 1e18):
                g[nxt] = ng; came[nxt] = cur
                heapq.heappush(openh, (ng + h(nxt), nxt))
    return []
