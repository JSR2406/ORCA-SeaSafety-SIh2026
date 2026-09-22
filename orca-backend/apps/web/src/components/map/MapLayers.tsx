"use client";

import { useEffect, useRef, useState } from "react";
import { Map, TileLayer, GeoJSON, CircleMarker, Polyline, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix Leaflet default icon issue
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

export interface MapLayerProps {
  center: [number, number];
  zoom: number;
  onClick?: (lat: number, lng: number) => void;
}

export interface LayerToggle {
  id: string;
  label: string;
  visible: boolean;
  onToggle: (id: string, visible: boolean) => void;
}

// Color scales
const waveColorScale = (height: number) => {
  if (height < 0.5) return "#00b4d8";
  if (height < 1.5) return "#90e0ef";
  if (height < 2.5) return "#ffd166";
  if (height < 4.0) return "#ef6f6c";
  return "#d62828";
};

const windColorScale = (speed: number) => {
  if (speed < 5) return "#00b4d8";
  if (speed < 10) return "#90e0ef";
  if (speed < 20) return "#ffd166";
  if (speed < 30) return "#ef6f6c";
  return "#d62828";
};

const currentColorScale = (speed: number) => {
  if (speed < 0.3) return "#00b4d8";
  if (speed < 0.8) return "#90e0ef";
  if (speed < 1.5) return "#ffd166";
  return "#ef6f6c";
};

const riskColorScale = (score: number) => {
  if (score < 0.3) return "#2a9d8f";
  if (score < 0.5) return "#e9c46a";
  if (score < 0.7) return "#f4a261";
  return "#e76f51";
};

// Wave Layer
export function WaveLayer({ data }: { data: any[] }) {
  if (!data?.length) return null;
  
  return (
    <>
      {data.map((point, i) => (
        <CircleMarker
          key={`wave-${i}`}
          center={[point.lat, point.lon]}
          radius={8}
          pathOptions={{
            fillColor: waveColorScale(point.wave_height || 0),
            fillOpacity: 0.7,
            color: "#fff",
            weight: 1,
          }}
        >
          <Popup>
            <div className="text-sm">
              <strong>Wave Height:</strong> {point.wave_height?.toFixed(1)} m<br />
              <strong>Period:</strong> {point.wave_period?.toFixed(1)} s<br />
              <strong>Direction:</strong> {point.wave_direction?.toFixed(0)}°
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}

// Wind Layer
export function WindLayer({ data }: { data: any[] }) {
  if (!data?.length) return null;
  
  return (
    <>
      {data.map((point, i) => (
        <CircleMarker
          key={`wind-${i}`}
          center={[point.lat, point.lon]}
          radius={8}
          pathOptions={{
            fillColor: windColorScale(point.wind_speed || 0),
            fillOpacity: 0.7,
            color: "#fff",
            weight: 1,
          }}
        >
          <Popup>
            <div className="text-sm">
              <strong>Wind Speed:</strong> {point.wind_speed?.toFixed(1)} m/s<br />
              <strong>Direction:</strong> {point.wind_direction?.toFixed(0)}°
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}

// Current Layer
export function CurrentLayer({ data }: { data: any[] }) {
  if (!data?.length) return null;
  
  return (
    <>
      {data.map((point, i) => (
        <CircleMarker
          key={`current-${i}`}
          center={[point.lat, point.lon]}
          radius={8}
          pathOptions={{
            fillColor: currentColorScale(point.current_speed || 0),
            fillOpacity: 0.7,
            color: "#fff",
            weight: 1,
          }}
        >
          <Popup>
            <div className="text-sm">
              <strong>Current Speed:</strong> {point.current_speed?.toFixed(2)} m/s<br />
              <strong>Direction:</strong> {point.current_direction?.toFixed(0)}°
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}

// Hazard Layer
export function HazardLayer({ data }: { data: any[] }) {
  if (!data?.length) return null;
  
  const severityColors = {
    low: "#2a9d8f",
    moderate: "#e9c46a",
    high: "#f4a261",
    critical: "#e76f51",
  };
  
  return (
    <>
      {data.map((hazard, i) => (
        <CircleMarker
          key={`hazard-${i}`}
          center={[hazard.location?.lat, hazard.location?.lon]}
          radius={12}
          pathOptions={{
            fillColor: severityColors[hazard.severity as keyof typeof severityColors] || "#e76f51",
            fillOpacity: 0.8,
            color: "#fff",
            weight: 2,
          }}
        >
          <Popup>
            <div className="text-sm">
              <strong>{hazard.hazard_type?.toUpperCase()}</strong><br />
              <strong>Severity:</strong> {hazard.severity}<br />
              <strong>Description:</strong> {hazard.description}
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}

// Route Layer
export function RouteLayer({ 
  route, 
  riskScore,
  onClick 
}: { 
  route: { lat: number; lon: number }[];
  riskScore?: number;
  onClick?: (lat: number, lng: number) => void;
}) {
  if (!route?.length) return null;
  
  const color = riskScore !== undefined ? riskColorScale(riskScore) : "#0077b6";
  
  return (
    <Polyline
      positions={route}
      pathOptions={{
        color,
        weight: 4,
        opacity: 0.8,
        dashArray: riskScore && riskScore > 0.5 ? "10, 5" : undefined,
      }}
      onClick={(e) => onClick?.(e.latlng.lat, e.latlng.lng)}
    >
      <Popup>
        <div className="text-sm">
          <strong>Route</strong><br />
          {riskScore !== undefined && (
            <>
              <strong>Risk Score:</strong> {(riskScore * 100).toFixed(0)}%<br />
              <strong>Risk Level:</strong> {riskScore > 0.7 ? "Elevated" : riskScore > 0.4 ? "Moderate" : "Low"}
            </>
          )}
        </div>
      </Popup>
    </Polyline>
  );
}

// Geofence Layer
export function GeofenceLayer({ data }: { data: any[] }) {
  if (!data?.length) return null;
  
  return (
    <>
      {data.map((geofence, i) => (
        <GeoJSON
          key={`geofence-${i}`}
          data={{
            type: "Feature",
            properties: { name: geofence.name, type: geofence.type },
            geometry: {
              type: "Polygon",
              coordinates: geofence.coordinates || [],
            },
          }}
          style={() => ({
            fillColor: "#e76f51",
            fillOpacity: 0.2,
            color: "#e76f51",
            weight: 2,
            dashArray: "5, 5",
          })}
        >
          <Popup>
            <div className="text-sm">
              <strong>{geofence.name}</strong><br />
              <strong>Type:</strong> {geofence.type}<br />
              <em>Restricted Area</em>
            </div>
          </Popup>
        </GeoJSON>
      ))}
    </>
  );
}

// Observation Layer (ARGO floats)
export function ObservationLayer({ 
  data, 
  onClick 
}: { 
  data: any[];
  onClick?: (lat: number, lng: number, profile: any) => void;
}) {
  if (!data?.length) return null;
  
  return (
    <>
      {data.map((obs, i) => (
        <CircleMarker
          key={`obs-${i}`}
          center={[obs.lat, obs.lon]}
          radius={6}
          pathOptions={{
            fillColor: "#0077b6",
            fillOpacity: 0.8,
            color: "#fff",
            weight: 2,
          }}
        >
          <Popup>
            <div className="text-sm">
              <strong>ARGO Float #{obs.float_id}</strong><br />
              <strong>Profile:</strong> {obs.profile_id}<br />
              <strong>Date:</strong> {obs.date}<br />
              <strong>Temp:</strong> {obs.temperature?.toFixed(1)}°C<br />
              <strong>Salinity:</strong> {obs.salinity?.toFixed(2)} PSU
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}

// Legend Component
export function MapLegend({ 
  layers 
}: { 
  layers: Array<{ id: string; label: string; color: string; type: "circle" | "line" | "polygon" }> 
}) {
  if (!layers?.length) return null;
  
  return (
    <div className="absolute bottom-4 right-4 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-3 border border-gray-200 max-w-xs">
      <div className="font-semibold text-sm mb-2">Legend</div>
      <div className="space-y-2">
        {layers.map((layer) => (
          <div key={layer.id} className="flex items-center gap-2 text-xs">
            {layer.type === "circle" && (
              <div 
                className="w-4 h-4 rounded-full border border-white/50"
                style={{ backgroundColor: layer.color }}
              />
            )}
            {layer.type === "line" && (
              <div 
                className="w-6 h-1 rounded"
                style={{ backgroundColor: layer.color }}
              />
            )}
            {layer.type === "polygon" && (
              <div 
                className="w-4 h-4 rounded border border-white/50"
                style={{ backgroundColor: layer.color + "33", borderColor: layer.color }}
              />
            )}
            <span className="text-gray-700">{layer.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Time Slider Component
export function TimeSlider({ 
  timeRange, 
  currentTime, 
  onTimeChange,
  playing,
  onPlayToggle,
}: { 
  timeRange: { start: string; end: string };
  currentTime: string;
  onTimeChange: (time: string) => void;
  playing: boolean;
  onPlayToggle: () => void;
}) {
  const [sliderValue, setSliderValue] = useState(0);
  
  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-3 border border-gray-200 w-full max-w-md">
      <div className="flex items-center gap-2 mb-2">
        <button
          onClick={onPlayToggle}
          className="p-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? "⏸" : "▶"}
        </button>
        <input
          type="range"
          min="0"
          max="100"
          value={sliderValue}
          onChange={(e) => {
            const val = parseInt(e.target.value);
            setSliderValue(val);
            // Convert to time - would need actual time interpolation
          }}
          className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
        />
        <span className="text-xs text-gray-600 w-24 text-right">{currentTime}</span>
      </div>
      <div className="flex justify-between text-xs text-gray-500">
        <span>{timeRange.start}</span>
        <span>{timeRange.end}</span>
      </div>
    </div>
  );
}

// Layer Toggle Panel
export function LayerControlPanel({ 
  layers, 
  onToggle 
}: { 
  layers: LayerToggle[];
  onToggle: (id: string, visible: boolean) => void;
}) {
  return (
    <div className="absolute top-4 right-4 bg-white/95 backdrop-blur-sm rounded-lg shadow-lg p-3 border border-gray-200 w-56">
      <div className="font-semibold text-sm mb-2 flex items-center justify-between">
        Map Layers
        <span className="text-xs text-gray-500">{layers.filter(l => l.visible).length} active</span>
      </div>
      <div className="space-y-2">
        {layers.map((layer) => (
          <label key={layer.id} className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={layer.visible}
              onChange={(e) => onToggle(layer.id, e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700">{layer.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}