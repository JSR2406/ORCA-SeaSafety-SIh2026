'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import MarineMap from '../components/DynamicMarineMap';
import Icon from '../components/Icon';
import Badge from '../components/Badge';
import { geocodeLocation, getGoogleMapsApiKey } from '../utils/googleMaps';

// Sector Quick Jump Presets
const QUICK_SECTORS = [
  { label: '⚓ Kochi Fairway', lat: 9.9750, lng: 76.1650, zoom: 12, depth: 24, name: 'Cochin Fairway Buoy Approach' },
  { label: '🐟 PFZ-01 Shelf', lat: 9.8700, lng: 76.1400, zoom: 12, depth: 42, name: 'PFZ-01 Kochi Offshore Upwelling' },
  { label: '⚓ Munambam Port', lat: 10.1800, lng: 76.1600, zoom: 13, depth: 6, name: 'Munambam Fishing Port Bar Mouth' },
  { label: '⚠️ Naval Firing Box', lat: 9.9300, lng: 76.2200, zoom: 12, depth: 28, name: 'NAVAREA VIII Sector Bravo Firing Polygon' },
  { label: '🌊 200m Shelf Edge', lat: 9.8500, lng: 75.6800, zoom: 11, depth: 210, name: 'Continental Shelf Break Front' },
  { label: '🏖️ Alappuzha Coast', lat: 9.4900, lng: 76.3300, zoom: 12, depth: 9, name: 'Alappuzha Coastal Landing Center' }
];

// Sea State Forecast Telemetry by Horizon
const FORECAST_TELEMETRY = {
  'NOW': { swell: '1.4m', sst: '28.7°C', wind: '14 kts WNW', current: '0.9 kts SSE', condition: 'MODERATE', tone: 'orange' },
  '+6h': { swell: '1.7m', sst: '28.5°C', wind: '17 kts WNW', current: '1.2 kts SSE', condition: 'CAUTION', tone: 'orange' },
  '+12h': { swell: '2.3m', sst: '28.2°C', wind: '22 kts W', current: '1.5 kts SSE', condition: 'WARNING', tone: 'red' },
  '+24h': { swell: '2.6m', sst: '27.9°C', wind: '25 kts WSW', current: '1.7 kts SSE', condition: 'HIGH SWELL', tone: 'red' },
  '+48h': { swell: '1.8m', sst: '28.4°C', wind: '16 kts NW', current: '1.1 kts S', condition: 'MODERATE', tone: 'orange' }
};

export default function MarineExplorerPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('Kochi Coastal Sector • 09°58\'N, 076°16\'E');
  const [selectedDate, setSelectedDate] = useState('04 Sep 2026');
  const [forecastHorizon, setForecastHorizon] = useState('NOW');
  const [externalFlyTo, setExternalFlyTo] = useState(null);

  // Tactical GPS Fix State
  const [activeFix, setActiveFix] = useState({
    lat: 9.9667,
    lng: 76.1650,
    distKm: '0.0',
    estDepth: 24,
    name: 'Kochi Fairway Approach'
  });

  // Handle Incoming URL Parameters from Alerts Center or External Links
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const latParam = params.get('lat');
      const lngParam = params.get('lng') || params.get('lon');
      const nameParam = params.get('name') || params.get('title');
      const zoomParam = params.get('zoom');
      if (latParam && lngParam) {
        const lat = parseFloat(latParam);
        const lng = parseFloat(lngParam);
        if (!isNaN(lat) && !isNaN(lng)) {
          const locName = nameParam || `Sector Fix (${lat.toFixed(2)}°N, ${lng.toFixed(2)}°E)`;
          setExternalFlyTo({
            lat,
            lng,
            zoom: zoomParam ? parseInt(zoomParam, 10) : 12,
            name: locName
          });
          setActiveFix({
            lat,
            lng,
            distKm: '0.0',
            estDepth: 28,
            name: locName
          });
          setSearchQuery(`${locName} • ${lat.toFixed(2)}°N, ${lng.toFixed(2)}°E`);
        }
      }
    }
  }, []);

  // 16 Real Oceanographic & Navigational Layers
  const [layersState, setLayersState] = useState({
    pfz: true,
    sst: true,
    chlorophyll: true,
    currents: true,
    waveHeight: true,
    waveDirection: false,
    wind: true,
    tide: true,
    cyclone: true,
    lightning: false,
    weatherWarnings: true,
    restrictedAreas: true,
    eez: true,
    mpa: false,
    fishingHarbours: true,
    vesselsAis: true
  });

  // Ruler Distance & Bearing Measurement State
  const [isMeasuring, setIsMeasuring] = useState(false);
  const [measurementResult, setMeasurementResult] = useState(null);
  const [clearMeasureToken, setClearMeasureToken] = useState(0);

  const toggle = (key) => setLayersState((prev) => ({ ...prev, [key]: !prev[key] }));

  const toggleAllLayers = (enable) => {
    setLayersState((prev) => {
      const next = {};
      Object.keys(prev).forEach((k) => {
        next[k] = enable;
      });
      return next;
    });
  };

  // Modern Search Submission
  const handleSearchSubmit = async (e) => {
    e.preventDefault();
    const query = searchQuery.trim();
    if (!query) return;

    // Check coordinate pattern like "9.95, 76.15"
    const coordMatch = query.match(/([0-9]+\.?[0-9]*)\s*[,°\sNn]+\s*([0-9]+\.?[0-9]*)/);
    if (coordMatch) {
      const lat = parseFloat(coordMatch[1]);
      const lng = parseFloat(coordMatch[2]);
      if (!isNaN(lat) && !isNaN(lng)) {
        setExternalFlyTo({ lat, lng, zoom: 12, name: `Coordinates Fix: ${lat}°N, ${lng}°E` });
        setActiveFix({ lat, lng, distKm: '12.4', estDepth: 35, name: `Fix: ${lat}°N, ${lng}°E` });
        return;
      }
    }

    // Check predefined quick sector match
    const foundSector = QUICK_SECTORS.find((s) => s.label.toLowerCase().includes(query.toLowerCase()) || s.name.toLowerCase().includes(query.toLowerCase()));
    if (foundSector) {
      handleJumpSector(foundSector);
      return;
    }

    // Fallback to Google / OpenStreetMap Geocoder
    try {
      const apiKey = getGoogleMapsApiKey();
      const res = await geocodeLocation(query, apiKey);
      if (res && res.lat && res.lng) {
        setExternalFlyTo({ lat: res.lat, lng: res.lng, zoom: 12, name: res.name });
        setActiveFix({ lat: res.lat, lng: res.lng, distKm: '18.0', estDepth: 28, name: res.name });
      }
    } catch (err) {
      console.error('Search geocode error:', err);
    }
  };

  const handleJumpSector = (sector) => {
    setExternalFlyTo({ lat: sector.lat, lng: sector.lng, zoom: sector.zoom, name: sector.name });
    setActiveFix({
      lat: sector.lat,
      lng: sector.lng,
      distKm: '0.0',
      estDepth: sector.depth,
      name: sector.name
    });
    setSearchQuery(`${sector.name} • ${sector.lat}°N, ${sector.lng}°E`);
  };

  // Comprehensive GeoJSON Export aggregating active layers
  const handleExportGeoJSON = () => {
    const features = [];

    features.push({
      type: 'Feature',
      properties: { name: activeFix.name || 'Tactical GPS Fix', type: 'gps_fix', estDepth: `${activeFix.estDepth}m` },
      geometry: { type: 'Point', coordinates: [activeFix.lng, activeFix.lat] }
    });

    if (layersState.fishingHarbours) {
      features.push(
        {
          type: 'Feature',
          properties: { name: 'Kochi Fishing Harbour (Base HQ)', type: 'port', depth: '14.5m', berths: '450 vessels' },
          geometry: { type: 'Point', coordinates: [76.2667, 9.9667] }
        },
        {
          type: 'Feature',
          properties: { name: 'Munambam Fishing Port', type: 'port', depth: '6.2m', berths: '320 vessels' },
          geometry: { type: 'Point', coordinates: [76.1600, 10.1800] }
        },
        {
          type: 'Feature',
          properties: { name: 'Alappuzha Coastal Landing', type: 'port', depth: '8.5m' },
          geometry: { type: 'Point', coordinates: [76.3300, 9.4900] }
        }
      );
    }

    if (layersState.pfz) {
      features.push(
        {
          type: 'Feature',
          properties: { name: 'PFZ-01: Kochi Offshore Front', sst: '28.4 °C', chlorophyll: '0.88 mg/m³', depth: '42m', potential: 'High' },
          geometry: { type: 'Point', coordinates: [76.1400, 9.8700] }
        },
        {
          type: 'Feature',
          properties: { name: 'PFZ-02: Vypin Deep Upwelling', sst: '28.1 °C', chlorophyll: '0.79 mg/m³', depth: '58m', potential: 'High' },
          geometry: { type: 'Point', coordinates: [76.0700, 9.9600] }
        },
        {
          type: 'Feature',
          properties: { name: 'PFZ-03: Alappuzha Shelf Margin', sst: '27.8 °C', chlorophyll: '0.64 mg/m³', depth: '75m', potential: 'Medium' },
          geometry: { type: 'Point', coordinates: [76.1900, 9.5700] }
        }
      );
    }

    if (layersState.restrictedAreas) {
      features.push({
        type: 'Feature',
        properties: { name: 'NAVAREA VIII Sector Bravo Firing Exercise', warning: 'Strict Exclusion' },
        geometry: {
          type: 'Polygon',
          coordinates: [[[76.17, 9.92], [76.24, 9.98], [76.28, 9.93], [76.22, 9.88], [76.17, 9.92]]]
        }
      });
    }

    if (layersState.eez) {
      features.push({
        type: 'Feature',
        properties: { name: 'Indian Territorial Sea (12 NM)', jurisdiction: 'UNCLOS Sovereign Baseline' },
        geometry: {
          type: 'LineString',
          coordinates: [[75.72, 10.45], [75.88, 10.18], [75.98, 9.9667], [76.08, 9.50], [76.32, 8.85]]
        }
      });
    }

    if (layersState.vesselsAis) {
      features.push(
        {
          type: 'Feature',
          properties: { name: 'ICGS VARUNA', mmsi: '419000112', type: 'coast_guard', speed: '21.5 kts', cog: '045°' },
          geometry: { type: 'Point', coordinates: [76.1200, 9.9150] }
        },
        {
          type: 'Feature',
          properties: { name: 'F/V MATSYA-04', mmsi: '419001248', type: 'fishing', speed: '9.8 kts', cog: '255°' },
          geometry: { type: 'Point', coordinates: [76.1800, 9.9400] }
        }
      );
    }

    if (layersState.weatherWarnings) {
      features.push({
        type: 'Feature',
        properties: { name: 'INCOIS High Swell Yellow Alert Zone', wave_height: '2.2m - 2.6m' },
        geometry: {
          type: 'Polygon',
          coordinates: [[[76.00, 10.50], [76.25, 10.50], [76.40, 9.30], [76.05, 9.30], [76.00, 10.50]]]
        }
      });
    }

    const geojsonData = {
      type: 'FeatureCollection',
      metadata: {
        system: 'ORCA Marine Intelligence GIS',
        agency: 'INCOIS / IMD / MoES',
        sector: 'Kochi & Malabar Maritime Grid',
        datum: 'WGS 84',
        forecastHorizon: forecastHorizon,
        activeLayerCount: Object.values(layersState).filter(Boolean).length,
        exportedAt: new Date().toISOString()
      },
      features
    };

    const blob = new Blob([JSON.stringify(geojsonData, null, 2)], { type: 'application/geo+json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ORCA_Marine_GIS_${forecastHorizon}_${Date.now()}.geojson`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const currentTelemetry = FORECAST_TELEMETRY[forecastHorizon] || FORECAST_TELEMETRY['NOW'];
  const activeLayersCount = Object.values(layersState).filter(Boolean).length;

  return (
    <AppShell
      title="Marine Explorer GIS"
      subtitle="Multi-Layer Oceanographic Telemetry, Dynamic Forecasting & Navigational Bathymetry"
      actions={
        <div className="explorer-header-actions">
          <button
            className={`btn btn-sm ${isMeasuring ? 'primary' : 'secondary'}`}
            onClick={() => {
              const next = !isMeasuring;
              setIsMeasuring(next);
              if (!next) {
                setMeasurementResult(null);
                setClearMeasureToken((t) => t + 1);
              }
            }}
            title="Measure nautical distance and bearing between two points on the map"
          >
            <Icon name="Navigation" size={13} />
            <span>{isMeasuring ? 'Exit Ruler Mode' : 'Measure Distance (NM)'}</span>
          </button>
          <button className="btn secondary btn-sm" onClick={handleExportGeoJSON} title="Download GeoJSON feature collection of active layers">
            <Icon name="Download" size={13} />
            <span>Export GeoJSON</span>
          </button>
          <button
            className="btn primary btn-sm"
            onClick={() => router.push(`/ai-copilot?q=Give+comprehensive+oceanographic+assessment+for+coordinates+${activeFix.lat}N+${activeFix.lng}E+at+depth+${activeFix.estDepth}m+forecast+${forecastHorizon}`)}
          >
            <Icon name="Bot" size={13} />
            <span>Query Coordinates</span>
          </button>
        </div>
      }
    >
      {/* Top Search & Presets Toolbar */}
      <div className="map-toolbar-modern">
        <form onSubmit={handleSearchSubmit} className="map-search-form-wrapper">
          <Icon name="Search" size={14} className="search-form-icon" />
          <input
            type="text"
            className="map-search-modern"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search port, coordinates (e.g. 09°58'N, 076°16'E), or landmark..."
          />
          <button type="submit" className="search-submit-btn" title="Search or Fix">
            Search
          </button>
        </form>

        <div className="map-timeline-selector">
          <div className="timeline-date-btn">
            <Icon name="Calendar" size={14} />
            <span>{selectedDate}</span>
          </div>
          <div className="timeline-horizons">
            {['NOW', '+6h', '+12h', '+24h', '+48h'].map((hz) => (
              <button
                key={hz}
                className={`horizon-chip ${forecastHorizon === hz ? 'active' : ''}`}
                onClick={() => setForecastHorizon(hz)}
                title={`Set sea-state forecast horizon to ${hz}`}
              >
                {hz}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Sector Presets Bar */}
      <div className="explorer-quick-sectors">
        <span className="quick-sectors-lbl">QUICK SECTOR:</span>
        <div className="quick-sectors-chips">
          {QUICK_SECTORS.map((s) => (
            <button
              key={s.label}
              type="button"
              className="quick-sector-chip"
              onClick={() => handleJumpSector(s)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Active Distance Ruler Banner */}
      {isMeasuring && (
        <div className="ruler-overlay-banner">
          <div className="ruler-banner-content">
            <Icon name="Navigation" size={14} className="spin-icon" style={{ color: '#00e5ff' }} />
            {!measurementResult ? (
              <span><b>RULER ACTIVE:</b> Click Point A on the map, then click Point B to calculate nautical distance, bearing & steaming duration.</span>
            ) : (
              <span>
                <b>RULER FIX:</b> Distance: <b>{measurementResult.distanceNm} NM</b> ({measurementResult.distanceKm} km) • Bearing: <b>{measurementResult.bearingDeg}° True</b> • Est. Steaming: <b>{measurementResult.estTime} @ 10 kts</b>
              </span>
            )}
          </div>
          <div className="ruler-banner-actions">
            {measurementResult && (
              <button
                type="button"
                className="ruler-banner-btn-secondary"
                onClick={() => {
                  setMeasurementResult(null);
                  setClearMeasureToken((t) => t + 1);
                }}
              >
                Reset Line
              </button>
            )}
            <button
              type="button"
              className="ruler-banner-btn-close"
              onClick={() => {
                setIsMeasuring(false);
                setMeasurementResult(null);
                setClearMeasureToken((t) => t + 1);
              }}
            >
              ✕ Done
            </button>
          </div>
        </div>
      )}

      {/* Explorer Stage: Map + Telemetry HUD + 16-Layer Manager */}
      <div className="explorer-body">
        <div className="explorer-map-stage">
          <MarineMap
            large
            layersState={layersState}
            forecastHorizon={forecastHorizon}
            externalFlyTo={externalFlyTo}
            isMeasuring={isMeasuring}
            onMeasurementDone={(res) => setMeasurementResult(res)}
            onClearMeasurement={clearMeasureToken}
            onFixCoordinates={(fix) => {
              setActiveFix(fix);
              setSearchQuery(`${fix.name || 'Tactical Fix'} • ${fix.lat}° N, ${fix.lng}° E • Sounding: ~${fix.estDepth}m`);
            }}
          />

          {/* Floating Telemetry HUD Pill (Elevated above bottom HUD) */}
          <div className="floating-hud-pill">
            <div className="hud-pill-telemetry">
              <span><b>{activeFix.lat}° N, {activeFix.lng}° E</b></span>
              <span className="hud-pill-sep">•</span>
              <span>Sounding: <b>~{activeFix.estDepth}m</b></span>
              <span className="hud-pill-sep">•</span>
              <span>Swell: <b>{currentTelemetry.swell}</b></span>
              <span className="hud-pill-sep">•</span>
              <span>Wind: <b>{currentTelemetry.wind}</b></span>
              <span className="hud-pill-sep">•</span>
              <span>SST: <b>{currentTelemetry.sst}</b></span>
              <span className="hud-pill-sep">•</span>
              <Badge tone={currentTelemetry.tone}>{currentTelemetry.condition} ({forecastHorizon})</Badge>
            </div>
            <button
              type="button"
              className="hud-pill-btn"
              onClick={() => router.push(`/ai-copilot?q=Analyze+harvest+viability+and+safety+at+${activeFix.lat}N+${activeFix.lng}E+depth+${activeFix.estDepth}m+forecast+${forecastHorizon}`)}
              title="Query AI Copilot for this location"
            >
              <Icon name="Bot" size={13} />
              <span>Query Copilot</span>
            </button>
          </div>
        </div>

        {/* Right Sidebar: Comprehensive 16-Layer GIS Manager */}
        <aside className="layers-panel-modern">
          <div className="layers-panel-top">
            <div className="layers-panel-title">
              <Icon name="Layers" size={16} />
              <h2>Chart Layers (16)</h2>
            </div>
            <div className="layers-header-actions">
              <span className="layers-count">{activeLayersCount} Active</span>
              <div className="layers-quick-toggles">
                <button
                  type="button"
                  className="layer-sub-btn"
                  onClick={() => toggleAllLayers(true)}
                  title="Enable all layers"
                >
                  All On
                </button>
                <span className="layer-sub-sep">|</span>
                <button
                  type="button"
                  className="layer-sub-btn"
                  onClick={() => toggleAllLayers(false)}
                  title="Disable all layers"
                >
                  All Off
                </button>
              </div>
            </div>
          </div>

          <div className="layers-scroll-list">
            {/* Category: Oceanography */}
            <div className="layer-category-group">
              <span className="layer-cat-title">OCEANOGRAPHY</span>
              {[
                ['pfz', 'PFZ (Potential Fishing Zones)', 'Fish'],
                ['sst', 'Sea Surface Temperature Fronts', 'Thermometer'],
                ['chlorophyll', 'Chlorophyll-a Biomass Plumes', 'Sparkles'],
                ['currents', 'Surface Ocean Currents', 'Compass']
              ].map(([key, label, icon]) => (
                <label key={key} className="layer-toggle-row">
                  <div className="layer-info">
                    <Icon name={icon} size={14} className="layer-icon" />
                    <span>{label}</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={layersState[key] ?? true}
                    onChange={() => toggle(key)}
                  />
                  <span className="toggle-switch-visual" />
                </label>
              ))}
            </div>

            {/* Category: Meteorology & Swell */}
            <div className="layer-category-group">
              <span className="layer-cat-title">METEOROLOGY & SWELL</span>
              {[
                ['waveHeight', 'Significant Wave Height Zones', 'Waves'],
                ['waveDirection', 'Swell Direction Vectors', 'Navigation'],
                ['wind', 'Surface Wind Speed Stations', 'Wind'],
                ['tide', 'Coastal Tide Gauge Stations', 'Activity'],
                ['cyclone', 'IMD Cyclone Advisory Track', 'AlertTriangle'],
                ['lightning', 'Lightning Strike Cluster Activity', 'Zap']
              ].map(([key, label, icon]) => (
                <label key={key} className="layer-toggle-row">
                  <div className="layer-info">
                    <Icon name={icon} size={14} className="layer-icon" />
                    <span>{label}</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={layersState[key] ?? false}
                    onChange={() => toggle(key)}
                  />
                  <span className="toggle-switch-visual" />
                </label>
              ))}
            </div>

            {/* Category: Maritime Boundaries & Safety */}
            <div className="layer-category-group">
              <span className="layer-cat-title">MARITIME BOUNDARIES & SAFETY</span>
              {[
                ['weatherWarnings', 'INCOIS Marine Warnings', 'AlertCircle'],
                ['restrictedAreas', 'NAVAREA VIII Restrictions & TSS', 'ShieldAlert'],
                ['eez', 'Indian EEZ & 12 NM Limits', 'Globe'],
                ['mpa', 'Marine Protected Areas (MPA)', 'Anchor'],
                ['fishingHarbours', 'Fishing Harbours & Landings', 'MapPin'],
                ['vesselsAis', 'AIS Live Fleet Traffic', 'Ship']
              ].map(([key, label, icon]) => (
                <label key={key} className="layer-toggle-row">
                  <div className="layer-info">
                    <Icon name={icon} size={14} className="layer-icon" />
                    <span>{label}</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={layersState[key] ?? true}
                    onChange={() => toggle(key)}
                  />
                  <span className="toggle-switch-visual" />
                </label>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
