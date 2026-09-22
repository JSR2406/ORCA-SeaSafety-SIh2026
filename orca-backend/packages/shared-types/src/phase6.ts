// Phase 6 - Operational Intelligence contract (orchestrate + execute stream)
// Mirrors the backend `apps/api/app/orchestration/synthesis.py` response frame.
export type SupportedLanguageV2 =
  | 'en-IN' | 'hi-IN' | 'ml-IN' | 'ta-IN' | 'te-IN' | 'kn-IN' | 'mr-IN';

export interface QuantityPoint {
  timestamp: string;
  value: number;
  unit: string;
  source: string;
  status: string;
}

export interface ChartPayload {
  type: 'chart';
  kind: 'observation' | 'model_prediction';
  title: string;
  unit: string;
  variable: string;
  source: string;
  status: string;
  series: QuantityPoint[];
  metadata: Record<string, unknown>;
}

export interface MapFeature {
  type: 'Feature';
  id: string;
  geometry: {
    type: 'Point' | 'LineString' | 'Polygon' | 'MultiPolygon';
    coordinates: unknown;
  };
  properties: Record<string, unknown>;
}

export interface MapPayload {
  type: 'FeatureCollection';
  features: MapFeature[];
  generated_at: string | null;
}

export interface RoutePayload {
  kind: 'route';
  waypoints: [number, number][];
  source: string;
  status: 'blocked' | 'caution' | 'clear';
  risk_score: number;
  recommended: boolean;
  length_km: number | null;
  intersections: unknown[];
  basis: string[];
}

export type AlertStatus = 'active' | 'upcoming' | 'expired';

export interface AlertPayload {
  alert_id: string;
  type: string;
  severity: string;
  title: string;
  message: string;
  location?: { lat: number; lon: number };
  geometry?: Record<string, unknown>;
  valid_from?: string | null;
  valid_until?: string | null;
  source?: string;
  status: AlertStatus;
  confidence?: number;
  evidence?: Array<{ claim: string; source: string }>;
}

export interface OutputsPayload {
  maps: MapPayload;
  charts: ChartPayload[];
  alerts: AlertPayload[];
  route: RoutePayload | null;
}

export interface PhaseTimings {
  intent_ms: number;
  plan_ms: number;
  execute_ms: number;
  synthesize_ms: number;
}

export interface ConfidencePayload {
  score: number;
  label: 'high' | 'medium' | 'low';
  basis: string[];
}

export interface RiskPayload {
  classification: 'SAFE' | 'LOW' | 'MODERATE' | 'HIGH' | 'UNKNOWN' | string;
  reason?: string;
  hard_constraint: boolean;
  assessed: boolean;
  /** @deprecated legacy field; read `classification`. */
  level?: string;
}

export interface EvidenceSummary {
  claim: string;
  source: string;
}

export interface OrchestrateResponse {
  request_id: string;
  run_id?: string;
  session_id?: string;
  conversation_id: string | null;
  intent: string;
  language: SupportedLanguageV2;
  status: 'completed' | 'needs_input' | 'failed' | 'invalid' | 'unavailable' | string;
  message: string;
  answer: string;
  sections: Array<{ title: string; lines: string[] }>;
  verification: { all_verified: boolean; checked: number } | null;
  tool_calls: number;
  duration_ms: number;
  phase_timings: PhaseTimings;
  confidence: ConfidencePayload;
  risk: RiskPayload;
  notes: Record<string, unknown>;
  outputs: OutputsPayload;
  evidence: EvidenceSummary[];
  provenance: Record<string, unknown>;
  limitations: string[];
  evidence_graph: { nodes: unknown[]; sources: unknown[] };
}

export interface UserLocation {
  latitude: number;
  longitude: number;
  accuracy_m?: number;
  timestamp?: string;
  source?: 'USER' | 'GPS' | 'MAP' | 'RESOLVED_PLACE' | 'SYSTEM' | string;
}

export interface OrchestrateRequest {
  /** Canonical field. Legacy alias `message` is also accepted. */
  query: string;
  /** @deprecated legacy alias for `query`. */
  message?: string;
  session_id?: string;
  /** @deprecated legacy alias for `session_id`. */
  conversation_id?: string;
  request_id?: string;
  language?: SupportedLanguageV2;
  user_location?: UserLocation;
  requested_outputs?: Array<'text' | 'map' | 'charts' | 'alerts' | 'route' | 'evidence' | 'history'>;
  route_request?: Record<string, unknown>;
  scenario_request?: Record<string, unknown>;
  context?: Record<string, unknown>;
}

export interface StreamEvent {
  event: string;
  request_id: string;
  conversation_id?: string;
  plan_id?: string;
  task_id?: string;
  timestamp: string;
  status: string;
  data: Record<string, unknown>;
}