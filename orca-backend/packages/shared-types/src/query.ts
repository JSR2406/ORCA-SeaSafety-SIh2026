// Query Contract Types
// Strict schema for structured ocean-data queries

export type SupportedLanguage = 'en-IN' | 'ml-IN' | 'hi-IN' | 'mr-IN';

export type Intent =
  | 'profile_search'
  | 'timeseries_summary'
  | 'depth_profile_summary'
  | 'anomaly_detection'
  | 'scenario_projection'
  | 'marine_condition_briefing'
  | 'dataset_explanation'
  | 'export_results';

export type RegionType = 'bbox' | 'radius' | 'polygon' | 'named_region' | 'route';

export interface BBoxRegion {
  type: 'bbox';
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
}

export interface RadiusRegion {
  type: 'radius';
  lat: number;
  lon: number;
  radius_km: number;
}

export interface PolygonRegion {
  type: 'polygon';
  coordinates: number[][][]; // GeoJSON polygon
}

export interface NamedRegion {
  type: 'named_region';
  name: 'arabian_sea' | 'bay_of_bengal' | 'kerala_coast' | 'indian_ocean' | 'equatorial_indian_ocean';
}

export interface RouteRegion {
  type: 'route';
  origin: { lat: number; lon: number };
  destination: { lat: number; lon: number };
  corridor_km?: number;
}

export type Region = BBoxRegion | RadiusRegion | PolygonRegion | NamedRegion | RouteRegion;

export interface TimeRange {
  start: string; // ISO 8601 date
  end: string;   // ISO 8601 date
}

export interface DepthRange {
  min: number; // meters
  max: number; // meters
}

export type Variable = 'temperature' | 'salinity' | 'oxygen' | 'chlorophyll' | 'nitrate' | 'ph';

export type QualityFilter = 'all' | 'recommended' | 'good_only';

export type Aggregation = 'profile' | 'daily' | 'weekly' | 'monthly' | 'depth_bin';

export interface StructuredQuery {
  intent: Intent;
  language: SupportedLanguage;
  region?: Region;
  time_range?: TimeRange;
  depth_range_m?: DepthRange;
  variables?: Variable[];
  quality_filter?: QualityFilter;
  aggregation?: Aggregation;
  limit?: number;
  
  // For marine_condition_briefing
  distance_km?: number;
  origin?: { lat: number; lon: number };
  destination?: { lat: number; lon: number };
  departure_time?: string; // ISO 8601
  vessel_type?: string;
  include_forecast?: boolean;
  
  // For anomaly_detection
  reference_period?: TimeRange;
  analysis_period?: TimeRange;
  depth_m?: number;
  threshold_std?: number;
  
  // For scenario_projection
  trend_window?: TimeRange;
  projection_years?: number;
  model?: 'linear_trend' | 'polynomial' | 'theil_sen';
  assumptions?: string[];
  
  // For export_results
  export_format?: 'profiles' | 'observations' | 'summary';
}

export interface QueryPlanResult {
  status: 'ready' | 'needs_clarification' | 'unsupported';
  intent: Intent;
  language: SupportedLanguage;
  query: StructuredQuery;
  clarification_question?: string;
  warnings: string[];
}

// Supported named regions with bounding boxes
export const NAMED_REGIONS: Record<NamedRegion['name'], BBoxRegion> = {
  arabian_sea: { type: 'bbox', min_lat: 8.0, max_lat: 25.0, min_lon: 60.0, max_lon: 78.0 },
  bay_of_bengal: { type: 'bbox', min_lat: 5.0, max_lat: 22.0, min_lon: 80.0, max_lon: 100.0 },
  kerala_coast: { type: 'bbox', min_lat: 8.0, max_lat: 13.0, min_lon: 74.0, max_lon: 77.0 },
  indian_ocean: { type: 'bbox', min_lat: -30.0, max_lat: 30.0, min_lon: 30.0, max_lon: 120.0 },
  equatorial_indian_ocean: { type: 'bbox', min_lat: -10.0, max_lat: 10.0, min_lon: 40.0, max_lon: 110.0 },
};