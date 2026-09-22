// Evidence/Provenance Types
// Proof-carrying numbers for ocean measurements

export type ConfidenceLabel = 'high' | 'medium' | 'low';

export interface ConfidenceComponents {
  spatial_coverage: number;      // 0-1
  temporal_freshness: number;    // 0-1
  sample_density: number;        // 0-1
  measurement_quality: number;   // 0-1
  method_stability: number;      // 0-1
}

export interface ConfidenceScore {
  label: ConfidenceLabel;
  score: number;                 // 0-1
  components: ConfidenceComponents;
  explanation: string;           // Human-readable
  limitations: string[];
}

export interface DataFreshness {
  latest_profile: string;        // ISO 8601
  days_old: number;
  source: 'argo_realtime' | 'argo_delayed' | 'climatology' | 'reanalysis' | 'demo';
}

export interface RegionInfo {
  type: string;
  name?: string;
  min_lat?: number;
  max_lat?: number;
  min_lon?: number;
  max_lon?: number;
  lat?: number;
  lon?: number;
  radius_km?: number;
}

export interface DepthRangeInfo {
  min: number;
  max: number;
}

export interface TimeRangeInfo {
  start: string;
  end: string;
}

export interface QualityFiltersInfo {
  filters: string[];
  description: string;
}

export interface SourceIdentifiers {
  dataset: string;
  snapshot: string;              // ISO 8601
  doi?: string;
  source_urls: string[];
}

export interface QueryStep {
  step: number;
  tool: string;
  params: Record<string, unknown>;
  result_count: number;
  duration_ms?: number;
}

export interface EvidenceRecord {
  float_ids: number[];
  profile_count: number;
  observation_count: number;
  region: RegionInfo;
  depth_range_m?: DepthRangeInfo;
  time_range: TimeRangeInfo;
  quality_filters: QualityFiltersInfo;
  data_freshness: DataFreshness;
  confidence: ConfidenceScore;
  query_steps: QueryStep[];
  limitations: string[];
  source_identifiers: SourceIdentifiers;
  verified: boolean;
  verification_errors?: string[];
}

export interface NumericClaim {
  claim: string;                 // Human-readable claim
  value: number | string;
  unit: string;
  claim_id: string;              // Links to profile/observation/float
  source: 'measurement' | 'aggregation' | 'comparison' | 'projection' | 'climatology';
  verified: boolean;
}

export interface VerificationResult {
  all_verified: boolean;
  claims: NumericClaim[];
  failed_claims: NumericClaim[];
  summary: string;
}