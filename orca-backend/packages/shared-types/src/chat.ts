// Chat/Response Types

import type { StructuredQuery, Intent, EvidenceRecord, ConfidenceScore } from './query';
import type { NumericClaim } from './evidence';

export interface ChatRequest {
  message: string;
  session_id?: string;
  language?: string;
  mode?: 'fisherfolk' | 'researcher';
  context?: Record<string, unknown>;
}

export interface ChatResponse {
  query_run_id: string;
  answer: string;
  language: string;
  structured_query: StructuredQuery;
  visualizations?: {
    map?: MapVisualizationData;
    charts: ChartVisualizationData[];
  };
  evidence: EvidenceRecord;
  audio_url?: string;
  status?: 'success' | 'needs_clarification' | 'error';
  clarification_question?: string;
  partial_query?: StructuredQuery;
}

export interface MapVisualizationData {
  type: 'geojson';
  features: GeoJSONFeature[];
  center: [number, number];
  zoom: number;
}

export interface GeoJSONFeature {
  type: 'Feature';
  geometry: {
    type: 'Point';
    coordinates: [number, number]; // [lon, lat]
  };
  properties: {
    float_id: number;
    platform_number: number;
    cycle_number: number;
    profile_time: string;
    latitude: number;
    longitude: number;
    temperature_c?: number;
    salinity_psu?: number;
    depth_m?: number;
  };
}

export type ChartType = 'depth_profile' | 'time_series' | 'anomaly' | 'scenario' | 'comparison' | 'histogram';

export interface ChartVisualizationData {
  type: ChartType;
  title: string;
  data: ChartDataPoint[];
  config: ChartConfig;
  metadata: ChartMetadata;
}

export interface ChartDataPoint {
  x: number | string;
  y: number;
  label?: string;
  group?: string;
  sample_count?: number;
  claim_id?: string;
}

export interface ChartConfig {
  xAxis: { label: string; unit?: string; type?: 'linear' | 'time' | 'category' };
  yAxis: { label: string; unit?: string; type?: 'linear' | 'log' };
  series?: ChartSeries[];
}

export interface ChartSeries {
  key: string;
  label: string;
  color?: string;
}

export interface ChartMetadata {
  variable: string;
  region: string;
  time_range: string;
  depth_range?: string;
  sample_count: number;
  float_count: number;
  data_source: string;
}

export interface QueryRunRecord {
  id: string;
  session_id: string;
  user_input: string;
  detected_language: string;
  normalized_intent: Intent;
  structured_query: StructuredQuery;
  tool_calls: QueryStep[];
  execution_status: 'pending' | 'running' | 'success' | 'failed' | 'needs_clarification';
  created_at: string;
  evidence?: EvidenceRecord;
  narratives?: NarrativeRecord[];
  scenarios?: ScenarioRecord[];
}

export interface QueryStep {
  step: number;
  tool: string;
  params: Record<string, unknown>;
  result_count: number;
  duration_ms?: number;
  status: 'success' | 'failed';
  error?: string;
}

export interface NarrativeRecord {
  id: string;
  title: string;
  narrative_text: string;
  numeric_claims: NumericClaim[];
  verified: boolean;
  created_at: string;
}

export interface ScenarioRecord {
  id: string;
  variable: string;
  region: string;
  baseline: Record<string, unknown>;
  trend_window: { start: string; end: string };
  projection_horizon: string;
  model_name: string;
  assumptions: string[];
  uncertainty_method: string;
  created_at: string;
}

export interface DatasetStatus {
  name: string;
  region: string;
  start_time: string;
  end_time: string;
  source: string;
  source_version: string;
  record_count: number;
  profile_count: number;
  float_count: number;
  ingested_at: string;
  status: 'active' | 'archived' | 'updating';
  checksum?: string;
  demo_mode: boolean;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  demo_mode: boolean;
  database: 'connected' | 'disconnected' | 'demo';
  timestamp: string;
}