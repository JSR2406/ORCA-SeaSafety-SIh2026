import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import Icon from './Icon';
import GoogleMapsConfigModal from './GoogleMapsConfigModal';
import {
  getGoogleMapsApiKey,
  getGoogleTileConfig,
  geocodeLocation
} from '../utils/googleMaps';

// Official Kochi & Kerala Coastline Maritime Coordinates
export const MARITIME_LOCATIONS = {
  kochiHarbour: { name: 'Kochi Fishing Harbour (HQ)', lat: 9.9667, lng: 76.2667, type: 'port', depth: '14.5m', berths: '450 Vessels' },
  fairwayBuoy: { name: 'Cochin Fairway Light Buoy (RW Iso.4s)', lat: 9.9750, lng: 76.1650, type: 'buoy', depth: '24m', light: 'RW Iso.W.4s' },
  vypinLight: { name: 'Vypin Lighthouse (Fl(3) 20s 42m 24M)', lat: 10.0150, lng: 76.2167, type: 'light', depth: 'Land', range: '24 NM' },
  munambamHarbour: { name: 'Munambam Fishing Port', lat: 10.1800, lng: 76.1600, type: 'port', depth: '6.2m', berths: '320 Vessels' },
  alappuzhaCoast: { name: 'Alappuzha Coastal Landing', lat: 9.4900, lng: 76.3300, type: 'port', depth: '8.5m', berths: 'Artisanal Landing' },
  chellanamHarbour: { name: 'Chellanam Fishery Harbour', lat: 9.7900, lng: 76.2800, type: 'port', depth: '5.2m', berths: '180 Vessels' },
  thoppumpadyMarket: { name: 'Thoppumpady Fish Market Terminal', lat: 9.9350, lng: 76.2600, type: 'port', depth: '11.0m', berths: 'Auction Center' },
  vesselMatsya: { name: 'F/V Matsya-04 (MMSI: 419001248)', lat: 9.9400, lng: 76.1800, type: 'vessel', speed: '9.8 kts', cog: '255°' }
};

// All 7 Official INCOIS PFZ coordinates
export const PFZ_COORDINATES = {
  'PFZ-01': { name: 'PFZ-01: Kochi Offshore Front', lat: 9.8700, lng: 76.1400, dist: '14.2 km SW', sst: '28.4 °C', chl: '0.88 mg/m³', depth: '42m', potential: 'High', target: 'Indian Mackerel, Sardine, Ribbonfish' },
  'PFZ-02': { name: 'PFZ-02: Vypin Deep Upwelling', lat: 9.9600, lng: 76.0700, dist: '21.5 km W', sst: '28.1 °C', chl: '0.79 mg/m³', depth: '58m', potential: 'High', target: 'Squid, Cuttlefish, Trevally' },
  'PFZ-03': { name: 'PFZ-03: Alappuzha Shelf Margin', lat: 9.5700, lng: 76.1900, dist: '31.8 km SSW', sst: '27.8 °C', chl: '0.64 mg/m³', depth: '75m', potential: 'Medium', target: 'Tuna, Seer Fish, Barracuda' },
  'PFZ-04': { name: 'PFZ-04: Chellanam Canyon', lat: 9.4700, lng: 75.9700, dist: '42.0 km SW', sst: '27.5 °C', chl: '0.52 mg/m³', depth: '110m', potential: 'Medium', target: 'Pelagic Shark, Skipjack Tuna' },
  'PFZ-05': { name: 'PFZ-05: Munambam Outer Trench', lat: 10.3000, lng: 75.7500, dist: '56.4 km NW', sst: '27.2 °C', chl: '0.41 mg/m³', depth: '160m', potential: 'Low', target: 'Yellowfin Tuna, Billfish' },
  'PFZ-06': { name: 'PFZ-06: Malabar Deep Margin', lat: 10.4000, lng: 75.5300, dist: '68.0 km WNW', sst: '27.0 °C', chl: '0.38 mg/m³', depth: '320m', potential: 'Low', target: 'Oceanic Whitetip, Swordfish' },
  'PFZ-07': { name: 'PFZ-07: Lakshadweep Basin Edge', lat: 9.7800, lng: 75.4100, dist: '74.5 km WSW', sst: '26.8 °C', chl: '0.32 mg/m³', depth: '550m', potential: 'Low', target: 'Bigeye Tuna, Deepwater Snapper' }
};

// Route Tracks
export const ROUTE_B_COORDS = [
  [9.9667, 76.2667],
  [9.9800, 76.1700],
  [9.9350, 76.0900],
  [9.8700, 76.1400]
];

export const ROUTE_A_COORDS = [
  [9.9667, 76.2667],
  [9.9080, 76.1830],
  [9.8850, 76.1630],
  [9.8700, 76.1400]
];

export const ROUTE_C_COORDS = [
  [9.9667, 76.2667],
  [9.8000, 76.2510],
  [9.7750, 76.1200],
  [9.8700, 76.1400]
];

// NAVAREA VIII Sector Bravo Naval Firing Polygon
export const NAVAL_DANGER_BOX = [
  [9.92, 76.17],
  [9.98, 76.24],
  [9.93, 76.28],
  [9.88, 76.22]
];

// Cochin Port Traffic Separation Scheme (TSS) Corridors
export const TSS_INBOUND_LANE = [
  [9.9950, 76.0500],
  [9.9850, 76.1600]
];

export const TSS_OUTBOUND_LANE = [
  [9.9650, 76.1600],
  [9.9550, 76.0500]
];

export function calculateHaversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return (R * c).toFixed(1);
}

export function calculateBearing(lat1, lon1, lat2, lon2) {
  const y = Math.sin((lon2 - lon1) * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180);
  const x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) -
            Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos((lon2 - lon1) * Math.PI / 180);
  let brng = Math.atan2(y, x) * 180 / Math.PI;
  brng = (brng + 360) % 360;
  return Math.round(brng);
}

export default function MarineMap({
  large = false,
  focusedZone = null,
  showControls = true,
  showKeyConfig = false,
  activeRouteId = 'route-b',
  routes = null,
  originCoord = null,
  destinationCoord = null,
  onFixCoordinates = null,
  layersState = null,
  forecastHorizon = 'NOW',
  externalFlyTo = null,
  isMeasuring = false,
  onMeasurementDone = null,
  onClearMeasurement = null
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const layersRef = useRef({});
  const measuringRef = useRef({
    pointA: null,
    pointB: null,
    startMarker: null,
    endMarker: null,
    fixedLine: null,
    previewLine: null,
    badgeMarker: null
  });

  const [googleKey, setGoogleKey] = useState(() => getGoogleMapsApiKey());
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchFeedback, setSearchFeedback] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);

  const [mouseCoords, setMouseCoords] = useState({ lat: 9.9667, lng: 76.1650 });
  const [activeTileLayer, setActiveTileLayer] = useState('googleHybrid');
  const [internalToggles, setInternalToggles] = useState({
    pfz: true,
    routes: true,
    restrictions: true,
    buoys: true,
    seamarks: true,
    ais: true,
    territorial: true,
    shelf: true
  });
  const [clickPin, setClickPin] = useState(null);

  const isMeasuringRef = useRef(isMeasuring);
  useEffect(() => {
    isMeasuringRef.current = isMeasuring;
    if (mapContainerRef.current) {
      mapContainerRef.current.style.cursor = isMeasuring ? 'crosshair' : '';
    }
    if (!isMeasuring) {
      clearMeasurePreview();
    }
  }, [isMeasuring]);

  const clearMeasurePreview = () => {
    const map = mapInstanceRef.current;
    if (map && measuringRef.current.previewLine) {
      map.removeLayer(measuringRef.current.previewLine);
      measuringRef.current.previewLine = null;
    }
  };

  const clearAllMeasurement = () => {
    const map = mapInstanceRef.current;
    if (!map) return;
    const m = measuringRef.current;
    if (m.startMarker) map.removeLayer(m.startMarker);
    if (m.endMarker) map.removeLayer(m.endMarker);
    if (m.fixedLine) map.removeLayer(m.fixedLine);
    if (m.previewLine) map.removeLayer(m.previewLine);
    if (m.badgeMarker) map.removeLayer(m.badgeMarker);
    measuringRef.current = {
      pointA: null,
      pointB: null,
      startMarker: null,
      endMarker: null,
      fixedLine: null,
      previewLine: null,
      badgeMarker: null
    };
  };

  useEffect(() => {
    if (onClearMeasurement) {
      clearAllMeasurement();
    }
  }, [onClearMeasurement]);

  // Master Leaflet Map Initialization
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [9.93, 76.16],
      zoom: large ? 11 : 10,
      zoomControl: false,
      attributionControl: false
    });

    mapInstanceRef.current = map;

    L.control.scale({ imperial: true, metric: true, position: 'bottomleft' }).addTo(map);

    const googleConfig = getGoogleTileConfig(googleKey);

    const tileLayers = {
      googleHybrid: L.tileLayer(googleConfig.hybrid.url, googleConfig.hybrid.options),
      googleRoadmap: L.tileLayer(googleConfig.roadmap.url, googleConfig.roadmap.options),
      googleTerrain: L.tileLayer(googleConfig.terrain.url, googleConfig.terrain.options),
      googleSatellite: L.tileLayer(googleConfig.satellite.url, googleConfig.satellite.options),
    };

    const openSeaMapOverlay = L.tileLayer('https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png', {
      maxZoom: 18,
      opacity: 0.95
    });
    openSeaMapOverlay.addTo(map);
    layersRef.current.openSeaMapOverlay = openSeaMapOverlay;

    const initialLayer = 'googleHybrid';
    tileLayers[initialLayer].addTo(map);
    layersRef.current.tileLayers = tileLayers;
    layersRef.current.currentTile = initialLayer;

    const createNauticalIcon = (color, text, shape = 'rect') => {
      return L.divIcon({
        className: 'custom-nautical-icon',
        html: `<div style="background: ${color}; color: #ffffff; font-size: 10px; font-family: monospace; font-weight: bold; padding: 2px 7px; border-radius: ${shape === 'circle' ? '12px' : '4px'}; border: 1.5px solid #ffffff; box-shadow: 0 2px 6px rgba(0,0,0,0.4); white-space: nowrap; display: inline-flex; align-items: center; gap: 4px;">${text}</div>`,
        iconSize: [110, 24],
        iconAnchor: [55, 12]
      });
    };

    // Mousemove handler
    map.on('mousemove', (e) => {
      const lat = Number(e.latlng.lat.toFixed(4));
      const lng = Number(e.latlng.lng.toFixed(4));
      setMouseCoords({ lat, lng });

      if (isMeasuringRef.current && measuringRef.current.pointA && !measuringRef.current.pointB) {
        const ptA = measuringRef.current.pointA;
        const currentCoord = [lat, lng];

        if (!measuringRef.current.previewLine) {
          measuringRef.current.previewLine = L.polyline([ptA, currentCoord], {
            color: '#38bdf8',
            weight: 2.5,
            dashArray: '5, 5',
            opacity: 0.85
          }).addTo(map);
        } else {
          measuringRef.current.previewLine.setLatLngs([ptA, currentCoord]);
        }
      }
    });

    // Click handler: Measuring Mode or Tactical GPS Fix
    map.on('click', (e) => {
      const lat = Number(e.latlng.lat.toFixed(4));
      const lng = Number(e.latlng.lng.toFixed(4));

      if (isMeasuringRef.current) {
        const m = measuringRef.current;
        if (!m.pointA) {
          clearAllMeasurement();
          m.pointA = [lat, lng];
          const iconA = L.divIcon({
            className: 'ruler-point-icon',
            html: '<div style="background:#0ea5e9;color:#fff;font-family:monospace;font-size:10px;font-weight:bold;padding:2px 7px;border-radius:4px;border:2px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.5);white-space:nowrap;">📍 [A] START</div>',
            iconSize: [80, 24],
            iconAnchor: [40, 12]
          });
          m.startMarker = L.marker([lat, lng], { icon: iconA }).addTo(map);
          return;
        } else if (m.pointA && !m.pointB) {
          m.pointB = [lat, lng];
          if (m.previewLine) {
            map.removeLayer(m.previewLine);
            m.previewLine = null;
          }

          const iconB = L.divIcon({
            className: 'ruler-point-icon',
            html: '<div style="background:#10b981;color:#fff;font-family:monospace;font-size:10px;font-weight:bold;padding:2px 7px;border-radius:4px;border:2px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.5);white-space:nowrap;">🎯 [B] END</div>',
            iconSize: [80, 24],
            iconAnchor: [40, 12]
          });
          m.endMarker = L.marker([lat, lng], { icon: iconB }).addTo(map);

          const distKm = calculateHaversineKm(m.pointA[0], m.pointA[1], lat, lng);
          const distNm = (distKm * 0.539957).toFixed(1);
          const bearing = calculateBearing(m.pointA[0], m.pointA[1], lat, lng);
          const totalHours = (distNm / 10);
          const hours = Math.floor(totalHours);
          const mins = Math.round((totalHours - hours) * 60);
          const timeStr = `${hours}h ${mins}m`;

          m.fixedLine = L.polyline([m.pointA, m.pointB], {
            color: '#00e5ff',
            weight: 3.5,
            dashArray: '6, 6',
            opacity: 0.95
          }).addTo(map);

          const midLat = (m.pointA[0] + lat) / 2;
          const midLng = (m.pointA[1] + lng) / 2;
          const midBadgeIcon = L.divIcon({
            className: 'ruler-midpoint-badge',
            html: `<div style="background:rgba(10,25,45,0.95);color:#38bdf8;border:1.5px solid #38bdf8;border-radius:5px;padding:4px 9px;font-family:monospace;font-size:10.5px;font-weight:bold;box-shadow:0 4px 14px rgba(0,0,0,0.6);white-space:nowrap;display:flex;align-items:center;gap:6px;">
              <span>📏 <b>${distNm} NM</b> (${distKm} km)</span>
              <span style="opacity:0.4;">|</span>
              <span style="color:#f59e0b;">🧭 ${bearing}° True</span>
              <span style="opacity:0.4;">|</span>
              <span style="color:#10b981;">⏱️ ~${timeStr} @ 10 kts</span>
            </div>`,
            iconSize: [260, 28],
            iconAnchor: [130, 14]
          });

          m.badgeMarker = L.marker([midLat, midLng], { icon: midBadgeIcon }).addTo(map);

          if (onMeasurementDone) {
            onMeasurementDone({
              distanceKm: distKm,
              distanceNm: distNm,
              bearingDeg: bearing,
              estTime: timeStr,
              pointA: m.pointA,
              pointB: m.pointB
            });
          }
          return;
        } else {
          clearAllMeasurement();
          m.pointA = [lat, lng];
          const iconA = L.divIcon({
            className: 'ruler-point-icon',
            html: '<div style="background:#0ea5e9;color:#fff;font-family:monospace;font-size:10px;font-weight:bold;padding:2px 7px;border-radius:4px;border:2px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.5);white-space:nowrap;">📍 [A] START</div>',
            iconSize: [80, 24],
            iconAnchor: [40, 12]
          });
          m.startMarker = L.marker([lat, lng], { icon: iconA }).addTo(map);
          return;
        }
      }

      const distKm = calculateHaversineKm(9.9667, 76.2667, lat, lng);
      const distNm = (distKm * 0.539957).toFixed(1);
      const bearing = calculateBearing(9.9667, 76.2667, lat, lng);
      const estDepth = Math.max(6, Math.min(650, Math.round(12 + Math.pow(distKm, 1.35) * 1.6)));

      if (layersRef.current.userClickMarker) {
        map.removeLayer(layersRef.current.userClickMarker);
      }

      const clickIcon = L.divIcon({
        className: 'user-click-fix-icon',
        html: `<div style="background: #0ea5e9; color: #ffffff; font-size: 10px; font-family: monospace; font-weight: bold; padding: 3px 7px; border-radius: 4px; border: 2px solid #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.5); white-space: nowrap; display: inline-flex; align-items: center; gap: 4px;">🎯 FIX: ${lat}°N, ${lng}°E</div>`,
        iconSize: [140, 26],
        iconAnchor: [70, 13]
      });

      const userMarker = L.marker([lat, lng], { icon: clickIcon });
      userMarker.bindPopup(`
        <div style="font-family: monospace; font-size: 11px; padding: 2px; color: #0a1c2e;">
          <strong style="color: #0284c7; display: block; margin-bottom: 4px;">📍 TACTICAL GPS FIX</strong>
          <div>Coordinates: <b>${lat}° N, ${lng}° E</b></div>
          <div>From Kochi HQ: <b>${distKm} km (${distNm} NM)</b></div>
          <div>True Bearing: <b>${bearing}°</b></div>
          <div>Sounded Depth: <b>~${estDepth} m</b></div>
          <div style="margin-top: 5px; padding-top: 4px; border-top: 1px solid #e2e8f0; font-size: 10px; color: #059669; font-weight: bold;">
            ECDIS STATUS: HYDROGRAPHIC DATA VERIFIED
          </div>
        </div>
      `).openPopup();

      userMarker.addTo(map);
      layersRef.current.userClickMarker = userMarker;
      setClickPin({ lat, lng, distKm, distNm, bearing, estDepth });

      if (onFixCoordinates) {
        onFixCoordinates({ lat, lng, distKm, estDepth });
      }
    });

    // ──────────────────────────────────────────────────────────────────────────
    // 1. PFZ LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const pfzGroup = L.layerGroup();
    Object.entries(PFZ_COORDINATES).forEach(([id, z]) => {
      const isHigh = z.potential === 'High';
      const isMed = z.potential === 'Medium';
      const color = isHigh ? '#0284c7' : isMed ? '#f59e0b' : '#64748b';
      const fillColor = isHigh ? '#38bdf8' : isMed ? '#fbbf24' : '#94a3b8';

      const circle = L.circle([z.lat, z.lng], {
        radius: isHigh ? 4200 : 3500,
        color: color,
        fillColor: fillColor,
        fillOpacity: 0.24,
        weight: 2,
        dashArray: '5, 5'
      }).bindPopup(`
        <div style="font-family: sans-serif; font-size: 11.5px; line-height: 1.4;">
          <strong style="color: #0284c7; font-size: 12px;">🐟 ${z.name}</strong><br/>
          <span>SST: <b>${z.sst}</b> • Chlorophyll-a: <b>${z.chl}</b></span><br/>
          <span>Depth: <b>${z.depth}</b> • Range: <b>${z.dist}</b></span><br/>
          <span style="color: #0369a1; font-size: 10.5px;">Target: <b>${z.target}</b></span><br/>
          <small style="color: ${isHigh ? '#059669' : '#d97706'}; font-weight: bold;">
            HARVEST POTENTIAL: ${z.potential.toUpperCase()}
          </small>
        </div>
      `);
      pfzGroup.addLayer(circle);
    });
    pfzGroup.addTo(map);
    layersRef.current.pfzGroup = pfzGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 2. SST LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const sstGroup = L.layerGroup();
    const sstWarmBand = L.polygon([
      [10.35, 76.12], [10.35, 76.28], [9.35, 76.45], [9.35, 76.25]
    ], {
      color: '#f97316', weight: 1.5, fillColor: '#f97316', fillOpacity: 0.16, dashArray: '4, 4'
    }).bindPopup('<b>SST Inshore Thermal Band: 29.1°C</b><br/>Warm coastal shelf layer, moderate plankton density.');
    sstGroup.addLayer(sstWarmBand);

    const sstFront = L.polygon([
      [10.45, 75.75], [10.45, 76.08], [9.25, 76.20], [9.25, 75.90]
    ], {
      color: '#06b6d4', weight: 2, fillColor: '#06b6d4', fillOpacity: 0.18
    }).bindPopup('<b>SST Thermal Break Upwelling Front: 28.2°C</b><br/>Primary thermal divergence boundary where pelagic fish congregate.');
    sstGroup.addLayer(sstFront);

    [
      { name: 'Kochi Inshore SST Buoy', lat: 9.98, lng: 76.20, temp: '28.9°C' },
      { name: 'Shelf Margin SST Buoy', lat: 9.80, lng: 75.95, temp: '28.1°C' },
      { name: 'Deep Pelagic SST Buoy', lat: 9.50, lng: 75.60, temp: '27.4°C' }
    ].forEach((b) => {
      const icon = L.divIcon({
        className: 'sst-pill-icon',
        html: `<div style="background:#ea580c;color:#fff;font-family:monospace;font-size:9.5px;font-weight:bold;padding:1px 5px;border-radius:3px;border:1px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.4);white-space:nowrap;">🌡️ ${b.temp}</div>`,
        iconSize: [60, 20],
        iconAnchor: [30, 10]
      });
      const marker = L.marker([b.lat, b.lng], { icon }).bindPopup(`<b>${b.name}</b><br/>Surface Temperature: <b>${b.temp}</b>`);
      sstGroup.addLayer(marker);
    });
    sstGroup.addTo(map);
    layersRef.current.sstGroup = sstGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 3. CHLOROPHYLL LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const chlorophyllGroup = L.layerGroup();
    const chlPlume1 = L.polygon([
      [10.05, 76.02], [10.15, 76.08], [9.90, 76.15], [9.80, 76.08]
    ], {
      color: '#10b981', weight: 1.5, fillColor: '#10b981', fillOpacity: 0.26, dashArray: '3, 4'
    }).bindPopup('<b>Chlorophyll-a High Biomass Plume</b><br/>Concentration: <b>1.42 mg/m³</b><br/>High phytoplankton biomass supporting large baitfish schools.');
    chlorophyllGroup.addLayer(chlPlume1);

    const chlPlume2 = L.polygon([
      [9.68, 76.10], [9.80, 76.16], [9.72, 76.26], [9.55, 76.18]
    ], {
      color: '#059669', weight: 1.5, fillColor: '#059669', fillOpacity: 0.22
    }).bindPopup('<b>Alappuzha Upwelling Chlorophyll Plume</b><br/>Concentration: <b>1.18 mg/m³</b><br/>Rich nutrient upwelling core.');
    chlorophyllGroup.addLayer(chlPlume2);

    [
      { lat: 9.94, lng: 76.11, val: '1.42 mg/m³' },
      { lat: 9.66, lng: 76.18, val: '1.18 mg/m³' }
    ].forEach((c) => {
      const icon = L.divIcon({
        className: 'chl-pill-icon',
        html: `<div style="background:#059669;color:#fff;font-family:monospace;font-size:9.5px;font-weight:bold;padding:1px 5px;border-radius:3px;border:1px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.4);white-space:nowrap;">🌿 ${c.val}</div>`,
        iconSize: [80, 20],
        iconAnchor: [40, 10]
      });
      chlorophyllGroup.addLayer(L.marker([c.lat, c.lng], { icon }));
    });
    chlorophyllGroup.addTo(map);
    layersRef.current.chlorophyllGroup = chlorophyllGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 4. CURRENTS LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const currentsGroup = L.layerGroup();
    const currentVectors = [
      { coords: [[10.20, 76.05], [9.95, 76.12]], speed: '1.2 kts', dir: '155° SSE' },
      { coords: [[9.95, 76.12], [9.65, 76.22]], speed: '1.4 kts', dir: '160° SSE' },
      { coords: [[10.30, 75.70], [10.00, 75.80]], speed: '1.6 kts', dir: '165° SSE' },
      { coords: [[10.00, 75.80], [9.60, 75.92]], speed: '1.5 kts', dir: '162° SSE' }
    ];
    currentVectors.forEach((cv) => {
      const line = L.polyline(cv.coords, {
        color: '#38bdf8',
        weight: 3,
        opacity: 0.85,
        dashArray: '8, 8'
      }).bindPopup(`<b>West India Coastal Current</b><br/>Speed: <b>${cv.speed}</b> • Set: <b>${cv.dir}</b>`);
      currentsGroup.addLayer(line);

      const midPt = [(cv.coords[0][0] + cv.coords[1][0]) / 2, (cv.coords[0][1] + cv.coords[1][1]) / 2];
      const icon = L.divIcon({
        className: 'current-arrow-icon',
        html: `<div style="background:#0284c7;color:#fff;font-family:monospace;font-size:9px;font-weight:bold;padding:1px 5px;border-radius:3px;border:1px solid #fff;white-space:nowrap;">➔ ${cv.speed}</div>`,
        iconSize: [60, 18],
        iconAnchor: [30, 9]
      });
      currentsGroup.addLayer(L.marker(midPt, { icon }));
    });
    currentsGroup.addTo(map);
    layersRef.current.currentsGroup = currentsGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 5. WAVE HEIGHT LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const waveHeightGroup = L.layerGroup();
    const waveInshore = L.polygon([
      [10.25, 76.10], [10.25, 76.24], [9.45, 76.38], [9.45, 76.22]
    ], {
      color: '#10b981', weight: 1.5, fillColor: '#10b981', fillOpacity: 0.14
    }).bindPopup('<b>Inshore Swell Zone: 0.9m - 1.2m</b><br/>State: Slight. Safe for small traditional craft.');
    waveHeightGroup.addLayer(waveInshore);

    const waveOffshore = L.polygon([
      [10.35, 75.80], [10.35, 76.08], [9.30, 76.20], [9.30, 75.92]
    ], {
      color: '#f59e0b', weight: 1.5, fillColor: '#f59e0b', fillOpacity: 0.18, dashArray: '5, 5'
    }).bindPopup('<b>Offshore Swell Zone: 1.6m - 2.1m</b><br/>State: Moderate. Mechanized trawlers operational.');
    waveHeightGroup.addLayer(waveOffshore);

    const waveDeep = L.polygon([
      [10.45, 75.40], [10.45, 75.75], [9.15, 75.88], [9.15, 75.50]
    ], {
      color: '#ef4444', weight: 1.5, fillColor: '#ef4444', fillOpacity: 0.18, dashArray: '6, 6'
    }).bindPopup('<b>Deep Oceanic Swell: 2.4m - 2.8m</b><br/>State: Rough. Caution advised for craft under 15m.');
    waveHeightGroup.addLayer(waveDeep);

    waveHeightGroup.addTo(map);
    layersRef.current.waveHeightGroup = waveHeightGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 6. WAVE DIRECTION LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const waveDirectionGroup = L.layerGroup();
    [
      { lat: 9.98, lng: 76.10, deg: '245° WSW', period: '8.4s' },
      { lat: 9.75, lng: 76.15, deg: '240° WSW', period: '8.6s' },
      { lat: 10.15, lng: 76.02, deg: '248° WSW', period: '8.2s' },
      { lat: 9.55, lng: 76.22, deg: '242° WSW', period: '8.8s' }
    ].forEach((w) => {
      const icon = L.divIcon({
        className: 'wave-dir-icon',
        html: `<div style="background:#0891b2;color:#fff;font-family:monospace;font-size:9.5px;font-weight:bold;padding:2px 6px;border-radius:3px;border:1px solid #fff;white-space:nowrap;">↗ Swell ${w.deg} (${w.period})</div>`,
        iconSize: [125, 20],
        iconAnchor: [62, 10]
      });
      const marker = L.marker([w.lat, w.lng], { icon }).bindPopup(`<b>Dominant Swell Vector</b><br/>Direction: <b>${w.deg}</b> • Peak Period: <b>${w.period}</b>`);
      waveDirectionGroup.addLayer(marker);
    });
    layersRef.current.waveDirectionGroup = waveDirectionGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 7. WIND LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const windGroup = L.layerGroup();
    [
      { name: 'Kochi Fairway Buoy Wind Station', lat: 9.975, lng: 76.165, speed: '14 kts', dir: 'WNW 290°', gust: '18 kts' },
      { name: 'Munambam Outer Station', lat: 10.18, lng: 76.12, speed: '16 kts', dir: 'WNW 285°', gust: '21 kts' },
      { name: 'Chellanam Offshore Station', lat: 9.78, lng: 76.22, speed: '18 kts', dir: 'W 275°', gust: '23 kts' }
    ].forEach((w) => {
      const icon = L.divIcon({
        className: 'wind-pill-icon',
        html: `<div style="background:#0284c7;color:#fff;font-family:monospace;font-size:9.5px;font-weight:bold;padding:2px 6px;border-radius:3px;border:1.5px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);white-space:nowrap;">💨 ${w.speed} ${w.dir.split(' ')[0]}</div>`,
        iconSize: [95, 22],
        iconAnchor: [47, 11]
      });
      const marker = L.marker([w.lat, w.lng], { icon }).bindPopup(`
        <b>${w.name}</b><br/>
        Sustained Wind: <b>${w.speed}</b> • Gusts: <b>${w.gust}</b><br/>
        Direction: <b>${w.dir}</b> • Beaufort Force 4 (Moderate Breeze)
      `);
      windGroup.addLayer(marker);
    });
    windGroup.addTo(map);
    layersRef.current.windGroup = windGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 8. TIDE LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const tideGroup = L.layerGroup();
    [
      { name: 'Cochin Port (Willingdon Island)', lat: 9.960, lng: 76.270, level: '+1.18m', state: 'FLOOD (Rising)', hw: '14:35 IST (+1.24m)' },
      { name: 'Munambam Bar Mouth', lat: 10.178, lng: 76.168, level: '+1.02m', state: 'FLOOD (Bar Safe)', hw: '14:20 IST (+1.10m)' },
      { name: 'Alappuzha Pier Station', lat: 9.492, lng: 76.325, level: '+0.84m', state: 'SLACK (High)', hw: '14:05 IST (+0.92m)' },
      { name: 'Neendakara Fishery Port', lat: 8.935, lng: 76.540, level: '+0.92m', state: 'FLOOD', hw: '13:50 IST (+0.98m)' }
    ].forEach((t) => {
      const icon = L.divIcon({
        className: 'tide-pill-icon',
        html: `<div style="background:#0d9488;color:#fff;font-family:monospace;font-size:9.5px;font-weight:bold;padding:2px 6px;border-radius:3px;border:1.5px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);white-space:nowrap;">🌊 ${t.level} ${t.state.split(' ')[0]}</div>`,
        iconSize: [110, 22],
        iconAnchor: [55, 11]
      });
      const marker = L.marker([t.lat, t.lng], { icon }).bindPopup(`
        <b>${t.name} Tide Gauge</b><br/>
        Current Gauge: <b>${t.level}</b> (${t.state})<br/>
        Next High Water: <b>${t.hw}</b>
      `);
      tideGroup.addLayer(marker);
    });
    tideGroup.addTo(map);
    layersRef.current.tideGroup = tideGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 9. CYCLONE LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const cycloneGroup = L.layerGroup();
    const cycloneTrackCoords = [
      [9.10, 73.80],
      [9.50, 74.20],
      [10.10, 74.50],
      [10.70, 74.70],
      [11.40, 74.80]
    ];
    const cycloneTrackLine = L.polyline(cycloneTrackCoords, {
      color: '#dc2626',
      weight: 3.5,
      dashArray: '6, 6'
    }).bindPopup('<b>IMD Cyclone Advisory Track</b><br/>Deep Depression BOB/ARB-02 moving NNW at 12 km/h.');
    cycloneGroup.addLayer(cycloneTrackLine);

    const cycloneCone = L.polygon([
      [9.10, 73.80],
      [11.80, 74.10],
      [11.80, 75.40],
      [10.10, 74.50]
    ], {
      color: '#ef4444',
      weight: 1.5,
      fillColor: '#ef4444',
      fillOpacity: 0.18,
      dashArray: '4, 4'
    }).bindPopup('<b>IMD 72h Cone of Uncertainty</b><br/>Probability of squally winds exceeding 45 kts.');
    cycloneGroup.addLayer(cycloneCone);

    const cycloneIcon = L.divIcon({
      className: 'cyclone-eye-icon',
      html: '<div style="background:#dc2626;color:#fff;font-family:monospace;font-size:10px;font-weight:bold;padding:2px 7px;border-radius:12px;border:2px solid #fff;box-shadow:0 0 10px rgba(220,38,38,0.8);white-space:nowrap;">🌀 DEPRESSION (45 kts)</div>',
      iconSize: [140, 24],
      iconAnchor: [70, 12]
    });
    const cycloneMarker = L.marker([10.10, 74.50], { icon: cycloneIcon }).bindPopup(`
      <b>IMD Tropical Cyclone Alert: ARB-02</b><br/>
      Location: 10.1°N, 74.5°E (~175 km W of Kochi)<br/>
      Central Pressure: 996 hPa • Max Wind: 45 kts (gusting 55 kts)<br/>
      <small style="color:#dc2626;font-weight:bold;">Fishermen strictly advised not to venture into deep sea.</small>
    `);
    cycloneGroup.addLayer(cycloneMarker);
    cycloneGroup.addTo(map);
    layersRef.current.cycloneGroup = cycloneGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 10. LIGHTNING LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const lightningGroup = L.layerGroup();
    const lightningZone = L.polygon([
      [10.35, 75.80], [10.50, 75.95], [10.40, 76.10], [10.25, 75.90]
    ], {
      color: '#eab308',
      weight: 2,
      fillColor: '#facc15',
      fillOpacity: 0.28,
      dashArray: '4, 4'
    }).bindPopup('<b>⚡ Lightning Strike Activity Zone</b><br/>Active convective thunderstorm cluster. Strike frequency: 148 / hour.');
    lightningGroup.addLayer(lightningZone);

    const lightningIcon = L.divIcon({
      className: 'lightning-icon',
      html: '<div style="background:#ca8a04;color:#fff;font-family:monospace;font-size:10px;font-weight:bold;padding:2px 7px;border-radius:4px;border:1.5px solid #fff;box-shadow:0 0 10px rgba(234,179,8,0.8);white-space:nowrap;">⚡ LIGHTNING ALERT (148/hr)</div>',
      iconSize: [160, 24],
      iconAnchor: [80, 12]
    });
    lightningGroup.addLayer(L.marker([10.38, 75.94], { icon: lightningIcon }));
    layersRef.current.lightningGroup = lightningGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 11. WEATHER WARNINGS LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const weatherWarningsGroup = L.layerGroup();
    const warningZone = L.polygon([
      [10.50, 76.00], [10.50, 76.25], [9.30, 76.40], [9.30, 76.05]
    ], {
      color: '#f59e0b',
      weight: 2.5,
      fillColor: '#f59e0b',
      fillOpacity: 0.20,
      dashArray: '6, 6'
    }).bindPopup(`
      <div style="font-family: sans-serif; font-size: 11.5px;">
        <strong style="color: #d97706; display: block; margin-bottom: 3px;">⚠️ INCOIS HIGH SWELL ALERT</strong>
        <span>Yellow Warning: High Swell Waves (2.2m - 2.6m)</span><br/>
        <small style="color: #b45309; font-weight: bold;">Artisanal non-motorized craft advised not to cross surf zone.</small>
      </div>
    `);
    weatherWarningsGroup.addLayer(warningZone);
    weatherWarningsGroup.addTo(map);
    layersRef.current.weatherWarningsGroup = weatherWarningsGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 12. RESTRICTED AREAS LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const restrictedAreasGroup = L.layerGroup();
    const dangerZone = L.polygon(NAVAL_DANGER_BOX, {
      color: '#dc2626',
      weight: 2,
      fillColor: '#ef4444',
      fillOpacity: 0.28,
      dashArray: '6, 6'
    }).bindPopup(`
      <div style="font-family: sans-serif; font-size: 11.5px;">
        <strong style="color: #dc2626; display: block; margin-bottom: 2px;">⚠️ NAVAREA VIII RESTRICTED ZONE</strong>
        <span>Sector Bravo: Joint Naval Firing Exercises</span><br/>
        <span style="color: #64748b;">Notice #0482 • Coordinates: 09°58'N, 076°22'E</span><br/>
        <small style="color: #dc2626; font-weight: bold;">PROHIBITION: All commercial and fishing vessels strictly excluded.</small>
      </div>
    `);
    restrictedAreasGroup.addLayer(dangerZone);

    const tssIn = L.polyline(TSS_INBOUND_LANE, {
      color: '#0284c7', weight: 3, dashArray: '4, 4'
    }).bindPopup('<b>Cochin Port TSS Inbound Lane (070°)</b><br/>Deep draft commercial vessels approaching fairway.');
    restrictedAreasGroup.addLayer(tssIn);

    const tssOut = L.polyline(TSS_OUTBOUND_LANE, {
      color: '#0284c7', weight: 3, dashArray: '4, 4'
    }).bindPopup('<b>Cochin Port TSS Outbound Lane (250°)</b><br/>Departing vessel traffic corridor.');
    restrictedAreasGroup.addLayer(tssOut);

    restrictedAreasGroup.addTo(map);
    layersRef.current.restrictedAreasGroup = restrictedAreasGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 13. EEZ & TERRITORIAL SEA LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const eezGroup = L.layerGroup();
    const line12nm = L.polyline([
      [10.4500, 75.7200],
      [10.1800, 75.8800],
      [9.9667, 75.9800],
      [9.5000, 76.0800],
      [8.8500, 76.3200]
    ], {
      color: '#f59e0b',
      weight: 2,
      dashArray: '8, 6',
      opacity: 0.85
    }).bindPopup(`
      <div style="font-family: sans-serif; font-size: 11px;">
        <strong style="color: #d97706;">🇮🇳 INDIAN TERRITORIAL SEA LIMIT (12 NM)</strong><br/>
        <span>Sovereign Maritime Zone Baseline Boundary</span><br/>
        <small style="color: #64748b;">UNCLOS 1982 • Inshore artisanal craft priority zone</small>
      </div>
    `);
    eezGroup.addLayer(line12nm);

    const line200nm = L.polyline([
      [11.0000, 73.2000],
      [10.5000, 73.4000],
      [9.8000, 73.6500],
      [9.0000, 73.9000]
    ], {
      color: '#0284c7',
      weight: 2,
      dashArray: '10, 8',
      opacity: 0.75
    }).bindPopup('<b>🇮🇳 Indian Exclusive Economic Zone (200 NM Outer Line)</b><br/>Sovereign rights for exploring and managing marine resources.');
    eezGroup.addLayer(line200nm);

    eezGroup.addTo(map);
    layersRef.current.eezGroup = eezGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 14. MPA LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const mpaGroup = L.layerGroup();
    const mpaZone1 = L.polygon([
      [9.85, 76.30], [9.95, 76.35], [9.80, 76.42], [9.70, 76.38]
    ], {
      color: '#10b981',
      weight: 2,
      fillColor: '#10b981',
      fillOpacity: 0.22,
      dashArray: '5, 5'
    }).bindPopup(`
      <b>🌿 Vembanad Ramsar Marine Protected Area</b><br/>
      Critical estuarine nursery & fish breeding zone.<br/>
      <small style="color:#059669;font-weight:bold;">Mechanized trawling strictly prohibited.</small>
    `);
    mpaGroup.addLayer(mpaZone1);
    layersRef.current.mpaGroup = mpaGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 15. FISHING HARBOURS & LANDINGS LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const fishingHarboursGroup = L.layerGroup();
    const harbours = [
      { name: '⚓ KOCHI FISHING HARBOUR (HQ)', lat: 9.9667, lng: 76.2667, depth: '14.5m', info: '450 Mechanized Trawlers • 3 Ice Plants • Bunkering' },
      { name: '⚓ MUNAMBAM FISHING PORT', lat: 10.1800, lng: 76.1600, depth: '6.2m', info: '320 Purse-seiners & Gillnetters • Auction Hall' },
      { name: '⚓ THOPPUMPADY FISH TERMINAL', lat: 9.9350, lng: 76.2600, depth: '11.0m', info: 'Central Commercial Export & Ice Supply Base' },
      { name: '⚓ CHELLANAM HARBOUR', lat: 9.7900, lng: 76.2800, depth: '5.2m', info: '180 Artisanal Motorized Craft Landing' },
      { name: '🏖️ ALAPPUZHA LANDING', lat: 9.4900, lng: 76.3300, depth: '8.5m', info: 'Traditional Beach Landing & Thanguvallam Fleet' }
    ];
    harbours.forEach((h) => {
      const icon = createNauticalIcon('#0284c7', h.name, 'rect');
      const marker = L.marker([h.lat, h.lng], { icon }).bindPopup(`
        <b>${h.name}</b><br/>
        Draft: <b>${h.depth}</b><br/>
        <span>${h.info}</span>
      `);
      fishingHarboursGroup.addLayer(marker);
    });
    fishingHarboursGroup.addTo(map);
    layersRef.current.fishingHarboursGroup = fishingHarboursGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 16. VESSELS AIS TRAFFIC LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const vesselsAisGroup = L.layerGroup();
    const aisVessels = [
      { name: 'ICGS VARUNA (CG-34)', type: 'coast_guard', lat: 9.9150, lng: 76.1200, speed: '21.5 kts', cog: '045° NE', mmsi: '419000112' },
      { name: 'M/V SAGAR RATNA (Tanker)', type: 'tanker', lat: 9.9950, lng: 76.0200, speed: '12.4 kts', cog: '315° NW', mmsi: '419004521' },
      { name: 'F/V SAGARIKA (Trawler)', type: 'fishing', lat: 9.8550, lng: 76.1600, speed: '6.8 kts', cog: '190° S', mmsi: '419008762' },
      { name: 'F/V MATSYA-04 (MMSI: 419001248)', type: 'fishing', lat: 9.9400, lng: 76.1800, speed: '9.8 kts', cog: '255° WSW', mmsi: '419001248' },
      { name: 'PILOT BOAT COCHIN-1', type: 'pilot', lat: 9.9720, lng: 76.2100, speed: '14.0 kts', cog: '260° W', mmsi: '419009981' },
      { name: 'CONTAINER SHIP MSC ALAPPUZHA', type: 'cargo', lat: 10.0800, lng: 75.9200, speed: '16.2 kts', cog: '140° SE', mmsi: '419003890' }
    ];
    aisVessels.forEach((v) => {
      const iconColor = v.type === 'coast_guard' ? '#3b82f6' : v.type === 'tanker' ? '#f59e0b' : v.type === 'pilot' ? '#06b6d4' : v.type === 'cargo' ? '#8b5cf6' : '#10b981';
      const vIcon = L.divIcon({
        className: 'ais-vessel-icon',
        html: `<div style="background: ${iconColor}; color: #ffffff; font-size: 9px; font-family: monospace; font-weight: bold; padding: 2px 5px; border-radius: 3px; border: 1.5px solid #ffffff; box-shadow: 0 2px 6px rgba(0,0,0,0.4); white-space: nowrap; display: inline-flex; align-items: center; gap: 3px;">🚢 ${v.name.slice(0, 16)}</div>`,
        iconSize: [120, 22],
        iconAnchor: [60, 11]
      });
      const marker = L.marker([v.lat, v.lng], { icon: vIcon }).bindPopup(`
        <div style="font-family: sans-serif; font-size: 11px;">
          <strong style="color: ${iconColor};">📡 AIS LIVE TELEMETRY</strong><br/>
          <b>${v.name}</b><br/>
          <span>MMSI: ${v.mmsi} • Type: ${v.type.toUpperCase()}</span><br/>
          <span>Speed: <b>${v.speed}</b> • Course: <b>${v.cog}</b></span>
        </div>
      `);
      vesselsAisGroup.addLayer(marker);
    });
    vesselsAisGroup.addTo(map);
    layersRef.current.vesselsAisGroup = vesselsAisGroup;

    // Navigation Aids
    const markersGroup = L.layerGroup();
    const buoyMarker = L.marker([9.9750, 76.1650], {
      icon: createNauticalIcon('#dc2626', 'RW FAIRWAY (Iso.4s)', 'rect')
    }).bindPopup('<b>Cochin Fairway Light Buoy (RW Iso.W.4s)</b><br/>Approach Channel Waypoint WP-02 • Depth: 24m');
    markersGroup.addLayer(buoyMarker);

    const vypinMarker = L.marker([10.0150, 76.2167], {
      icon: createNauticalIcon('#eab308', '⚡ VYPIN LIGHTHOUSE', 'rect')
    }).bindPopup('<b>Vypin Lighthouse</b><br/>Light Character: Fl(3) 20s 42m 24M Range');
    markersGroup.addLayer(vypinMarker);

    markersGroup.addTo(map);
    layersRef.current.markersGroup = markersGroup;

    // 200m Shelf Break
    const shelfBreakGroup = L.layerGroup();
    const shelfLine = L.polyline([
      [10.5500, 75.4000],
      [10.2500, 75.5200],
      [9.8500, 75.6800],
      [9.4000, 75.8200],
      [8.7000, 76.1200]
    ], {
      color: '#0284c7',
      weight: 2,
      dashArray: '4, 8',
      opacity: 0.8
    }).bindPopup(`
      <div style="font-family: sans-serif; font-size: 11px;">
        <strong style="color: #0284c7;">🌊 200m CONTINENTAL SHELF BREAK</strong><br/>
        <span>Deep ocean transition & primary pelagic upwelling front</span><br/>
        <small style="color: #0369a1;">High concentration of Tuna, Mackerel & Plankton</small>
      </div>
    `);
    shelfBreakGroup.addLayer(shelfLine);
    shelfBreakGroup.addTo(map);
    layersRef.current.shelfBreakGroup = shelfBreakGroup;

    // Route Lines
    const routeLinesGroup = L.layerGroup();
    const routeB = L.polyline(ROUTE_B_COORDS, {
      color: '#10b981', weight: 4.5, opacity: 0.95, lineCap: 'round', lineJoin: 'round'
    }).bindPopup('<b>Route B (Fairway Channel - Recommended)</b><br/>Safe certified channel • Zero naval breaches');
    routeLinesGroup.addLayer(routeB);
    layersRef.current.routeB = routeB;

    const routeA = L.polyline(ROUTE_A_COORDS, {
      color: '#ef4444', weight: 3, opacity: 0.8, dashArray: '6, 8'
    }).bindPopup('<b>Route A (Direct Line - High Risk)</b><br/>WARNING: Clips active naval firing zone.');
    routeLinesGroup.addLayer(routeA);
    layersRef.current.routeA = routeA;

    const routeC = L.polyline(ROUTE_C_COORDS, {
      color: '#0284c7', weight: 3.5, opacity: 0.85, dashArray: '4, 4'
    }).bindPopup('<b>Route C (Southern Offshore Detour)</b><br/>Wide safety buffer • Completely clear of naval limits');
    routeLinesGroup.addLayer(routeC);
    layersRef.current.routeC = routeC;

    routeLinesGroup.addTo(map);
    layersRef.current.routeLinesGroup = routeLinesGroup;

    return () => {
      clearAllMeasurement();
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [large]);

  // Reactive Layer Visibility Sync when layersState changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !layersState) return;

    const mapping = {
      pfz: layersRef.current.pfzGroup,
      sst: layersRef.current.sstGroup,
      chlorophyll: layersRef.current.chlorophyllGroup,
      currents: layersRef.current.currentsGroup,
      waveHeight: layersRef.current.waveHeightGroup,
      waveDirection: layersRef.current.waveDirectionGroup,
      wind: layersRef.current.windGroup,
      tide: layersRef.current.tideGroup,
      cyclone: layersRef.current.cycloneGroup,
      lightning: layersRef.current.lightningGroup,
      weatherWarnings: layersRef.current.weatherWarningsGroup,
      restrictedAreas: layersRef.current.restrictedAreasGroup,
      eez: layersRef.current.eezGroup,
      mpa: layersRef.current.mpaGroup,
      fishingHarbours: layersRef.current.fishingHarboursGroup,
      vesselsAis: layersRef.current.vesselsAisGroup
    };

    Object.entries(mapping).forEach(([key, group]) => {
      if (!group) return;
      const shouldShow = layersState[key] ?? true;
      if (shouldShow) {
        if (!map.hasLayer(group)) map.addLayer(group);
      } else {
        if (map.hasLayer(group)) map.removeLayer(group);
      }
    });
  }, [layersState]);

  // Smooth External Fly To Effect
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !externalFlyTo || typeof externalFlyTo.lat !== 'number' || typeof externalFlyTo.lng !== 'number') return;
    map.flyTo([externalFlyTo.lat, externalFlyTo.lng], externalFlyTo.zoom || 12, { duration: 1.2 });
  }, [externalFlyTo]);

  // Focused Zone Effect
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !focusedZone) return;

    const targetPfz = PFZ_COORDINATES[focusedZone];
    if (targetPfz) {
      map.flyTo([targetPfz.lat, targetPfz.lng], 12, { duration: 1.2 });
    }
  }, [focusedZone]);

  // Dynamic Route Rendering Effect
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !layersRef.current.routeLinesGroup) return;

    const group = layersRef.current.routeLinesGroup;
    group.clearLayers();

    if (routes && Array.isArray(routes) && routes.length > 0) {
      const activeCoords = [];
      const allWaypoints = [];

      routes.forEach((r) => {
        const isSelected = r.id === activeRouteId;
        const rawWps = r.waypoints || [];
        const coords = rawWps
          .map((wp) => {
            if (Array.isArray(wp)) return [Number(wp[0]), Number(wp[1])];
            const lat =
              typeof wp.latNum === 'number'
                ? wp.latNum
                : typeof wp.lat === 'number'
                ? wp.lat
                : parseFloat(wp.lat);
            const lon =
              typeof wp.lonNum === 'number'
                ? wp.lonNum
                : typeof wp.lon === 'number'
                ? wp.lon
                : parseFloat(wp.lon || wp.lng);
            return [lat, lon];
          })
          .filter((c) => !isNaN(c[0]) && !isNaN(c[1]));

        if (coords.length < 2) return;

        allWaypoints.push(...coords);
        if (isSelected) {
          activeCoords.push(...coords);
        }

        const color =
          r.color ||
          (r.id === 'route-b' ? '#10b981' : r.id === 'route-a' ? '#ef4444' : '#0284c7');
        const weight = isSelected ? 5.5 : 2.5;
        const opacity = isSelected ? 0.95 : 0.4;
        const dashArray =
          r.id === 'route-a' ? '6, 8' : r.id === 'route-c' ? '4, 4' : undefined;

        const line = L.polyline(coords, {
          color,
          weight,
          opacity,
          dashArray,
          lineCap: 'round',
          lineJoin: 'round'
        }).bindPopup(`
          <div style="font-family: sans-serif; font-size: 11px;">
            <strong style="color: ${color};">${r.name || r.id}</strong><br/>
            <span>Distance: ${r.distance || ''} • Duration: ${r.duration || ''}</span><br/>
            <small style="color: #64748b;">${r.summary || ''}</small>
          </div>
        `);
        group.addLayer(line);
      });

      if (originCoord && originCoord.lat && originCoord.lon) {
        const oIcon = L.divIcon({
          className: 'harbour-origin-pin',
          html: `<div style="background:#10b981;color:#fff;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:13px;border:2px solid #fff;box-shadow:0 0 10px rgba(16,185,129,0.8);cursor:pointer;" title="Departure: ${originCoord.name || 'Harbour'}">⚓</div>`,
          iconSize: [26, 26],
          iconAnchor: [13, 13]
        });
        const oMarker = L.marker([originCoord.lat, originCoord.lon], { icon: oIcon })
          .bindPopup(`<div style="font-family: sans-serif; font-size: 11px;"><strong style="color:#10b981;">⚓ DEPARTURE HARBOUR</strong><br/><b>${originCoord.name || 'Origin Port'}</b></div>`);
        group.addLayer(oMarker);
        allWaypoints.push([originCoord.lat, originCoord.lon]);
      }

      if (destinationCoord && destinationCoord.lat && destinationCoord.lon) {
        const dIcon = L.divIcon({
          className: 'target-destination-pin',
          html: `<div style="background:#0ea5e9;color:#fff;border-radius:50%;width:26px;height:26px;display:flex;align-items:center;justify-content:center;font-size:13px;border:2px solid #fff;box-shadow:0 0 10px rgba(14,165,233,0.8);cursor:pointer;" title="Destination: ${destinationCoord.name || 'Target Zone'}">🎯</div>`,
          iconSize: [26, 26],
          iconAnchor: [13, 13]
        });
        const dMarker = L.marker([destinationCoord.lat, destinationCoord.lon], { icon: dIcon })
          .bindPopup(`<div style="font-family: sans-serif; font-size: 11px;"><strong style="color:#0ea5e9;">🎯 TARGET DESTINATION</strong><br/><b>${destinationCoord.name || 'Destination'}</b></div>`);
        group.addLayer(dMarker);
        allWaypoints.push([destinationCoord.lat, destinationCoord.lon]);
      }

      const boundsToFit = activeCoords.length > 0 ? activeCoords : allWaypoints;
      if (boundsToFit.length >= 2) {
        try {
          map.fitBounds(L.latLngBounds(boundsToFit), { padding: [45, 45], maxZoom: 13 });
        } catch {
          // ignore
        }
      }
    } else {
      const rB = L.polyline(ROUTE_B_COORDS, {
        color: '#10b981',
        weight: activeRouteId === 'route-b' ? 5.5 : 2.5,
        opacity: activeRouteId === 'route-b' ? 0.95 : 0.4,
        lineCap: 'round',
        lineJoin: 'round'
      });
      group.addLayer(rB);

      const rA = L.polyline(ROUTE_A_COORDS, {
        color: '#ef4444',
        weight: activeRouteId === 'route-a' ? 5.5 : 2.5,
        opacity: activeRouteId === 'route-a' ? 0.95 : 0.4,
        dashArray: '6, 8'
      });
      group.addLayer(rA);

      const rC = L.polyline(ROUTE_C_COORDS, {
        color: '#0284c7',
        weight: activeRouteId === 'route-c' ? 5.5 : 2.5,
        opacity: activeRouteId === 'route-c' ? 0.95 : 0.4,
        dashArray: '4, 4'
      });
      group.addLayer(rC);
    }
  }, [routes, activeRouteId, originCoord, destinationCoord]);

  const handleTileSwitch = (tileKey) => {
    const map = mapInstanceRef.current;
    if (!map || !layersRef.current.tileLayers) return;

    const currentTile = layersRef.current.currentTile;
    if (currentTile && layersRef.current.tileLayers[currentTile]) {
      map.removeLayer(layersRef.current.tileLayers[currentTile]);
    }

    layersRef.current.tileLayers[tileKey].addTo(map);
    layersRef.current.currentTile = tileKey;
    setActiveTileLayer(tileKey);
  };

  const handleInternalToggle = (layerKey) => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const newState = !internalToggles[layerKey];
    setInternalToggles((prev) => ({ ...prev, [layerKey]: newState }));

    const layerMap = {
      pfz: layersRef.current.pfzGroup,
      routes: layersRef.current.routeLinesGroup,
      restrictions: layersRef.current.restrictedAreasGroup,
      buoys: layersRef.current.markersGroup,
      seamarks: layersRef.current.openSeaMapOverlay,
      ais: layersRef.current.vesselsAisGroup,
      territorial: layersRef.current.eezGroup,
      shelf: layersRef.current.shelfBreakGroup
    };

    const target = layerMap[layerKey];
    if (target) {
      if (newState) map.addLayer(target);
      else map.removeLayer(target);
    }
  };

  const handleSearchLocation = async (e) => {
    e.preventDefault();
    const query = searchQuery.trim();
    if (!query) return;

    setIsSearching(true);
    setSearchFeedback('');

    try {
      const result = await geocodeLocation(query, googleKey);
      if (result && result.lat && result.lng) {
        const map = mapInstanceRef.current;
        if (map) {
          map.flyTo([result.lat, result.lng], 13, { duration: 1.4 });

          const distKm = calculateHaversineKm(9.9667, 76.2667, result.lat, result.lng);
          const distNm = (distKm * 0.539957).toFixed(1);
          const bearing = calculateBearing(9.9667, 76.2667, result.lat, result.lng);
          const estDepth = Math.max(6, Math.min(650, Math.round(12 + Math.pow(distKm, 1.35) * 1.6)));

          if (layersRef.current.userClickMarker) {
            map.removeLayer(layersRef.current.userClickMarker);
          }

          const clickIcon = L.divIcon({
            className: 'user-click-fix-icon',
            html: `<div style="background: #0284c7; color: #ffffff; font-size: 10px; font-family: monospace; font-weight: bold; padding: 3px 8px; border-radius: 4px; border: 2px solid #ffffff; box-shadow: 0 4px 14px rgba(0,0,0,0.4); white-space: nowrap; display: inline-flex; align-items: center; gap: 4px;">🎯 FIX: ${result.name.slice(0, 24)}</div>`,
            iconSize: [160, 26],
            iconAnchor: [80, 13]
          });

          const userMarker = L.marker([result.lat, result.lng], { icon: clickIcon });
          userMarker.bindPopup(`
            <div style="font-family: monospace; font-size: 11px; padding: 2px; color: #0a1c2e;">
              <strong style="color: #0284c7; display: block; margin-bottom: 4px;">📍 GEOCODED MARITIME FIX</strong>
              <div>Target: <b>${result.name}</b></div>
              <div>Coordinates: <b>${result.lat.toFixed(4)}° N, ${result.lng.toFixed(4)}° E</b></div>
              <div>From Kochi HQ: <b>${distKm} km (${distNm} NM)</b></div>
              <div>True Bearing: <b>${bearing}°</b></div>
              <div>Sounded Depth: <b>~${estDepth} m</b></div>
            </div>
          `).openPopup();

          userMarker.addTo(map);
          layersRef.current.userClickMarker = userMarker;
          setClickPin({ lat: result.lat, lng: result.lng, distKm, distNm, bearing, estDepth });

          if (onFixCoordinates) {
            onFixCoordinates({ lat: result.lat, lng: result.lng, distKm, estDepth, name: result.name });
          }

          setSearchFeedback(`Fixed: ${result.name}`);
        }
      } else {
        setSearchFeedback('Location not found');
      }
    } catch {
      setSearchFeedback('Search failed');
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className={'real-gis-container ' + (large ? 'large' : '') + (isFullscreen ? ' fullscreen' : '')}>
      <div ref={mapContainerRef} className="leaflet-map-canvas" />

      {showControls && (
        <div className="real-map-top-bar">
          <div className="map-base-selector">
            <button
              type="button"
              className={'base-tab gmaps-tab ' + (activeTileLayer === 'googleHybrid' ? 'active' : '')}
              onClick={() => handleTileSwitch('googleHybrid')}
              title="Google Maps Satellite Hybrid"
            >
              <span className="gmaps-tag">GOOGLE</span>
              Satellite Hybrid
            </button>
            <button
              type="button"
              className={'base-tab gmaps-tab ' + (activeTileLayer === 'googleRoadmap' ? 'active' : '')}
              onClick={() => handleTileSwitch('googleRoadmap')}
              title="Google Maps Coastal Roadmap"
            >
              <span className="gmaps-tag">GOOGLE</span>
              Roadmap
            </button>
            <button
              type="button"
              className={'base-tab gmaps-tab ' + (activeTileLayer === 'googleTerrain' ? 'active' : '')}
              onClick={() => handleTileSwitch('googleTerrain')}
              title="Google Maps Coastal Terrain"
            >
              <span className="gmaps-tag">GOOGLE</span>
              Terrain
            </button>
            <button
              type="button"
              className={'base-tab gmaps-tab ' + (activeTileLayer === 'googleSatellite' ? 'active' : '')}
              onClick={() => handleTileSwitch('googleSatellite')}
              title="Google Maps Pure Satellite"
            >
              <span className="gmaps-tag">GOOGLE</span>
              Pure Satellite
            </button>
          </div>

          <form onSubmit={handleSearchLocation} className="map-coastal-search-bar" title="Search harbour, port, buoy or coordinates">
            <Icon name="Search" size={13} className="search-bar-icon" />
            <input
              type="text"
              className="search-bar-input"
              placeholder="Search port, buoy, coords (e.g. Munambam, 9.98, 76.16)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {isSearching ? (
              <Icon name="RefreshCw" size={12} className="spin-icon search-bar-status" />
            ) : searchFeedback ? (
              <span className="search-bar-feedback" title={searchFeedback}>
                {searchFeedback.slice(0, 16)}
              </span>
            ) : (
              <button type="submit" className="search-bar-submit" title="Geocode location">
                ↵
              </button>
            )}
          </form>

          {showKeyConfig && (
            <button
              type="button"
              className={`map-gmaps-pill-btn ${googleKey ? 'connected' : 'unconfigured'}`}
              onClick={() => setIsConfigModalOpen(true)}
              title={googleKey ? 'Google Maps API Connected • Click to manage' : 'Configure Google Maps API Key'}
            >
              <span className={`gmaps-status-bullet ${googleKey ? 'connected' : 'unconfigured'}`} />
              <span className="gmaps-pill-label">{googleKey ? 'Google Maps Active' : 'Configure Google Maps'}</span>
              <Icon name="Settings" size={12} />
            </button>
          )}

          {!layersState && (
            <div className="map-vector-toggles">
              <button
                className={'vec-toggle ' + (internalToggles.pfz ? 'active' : '')}
                onClick={() => handleInternalToggle('pfz')}
              >
                <span>PFZ Zones</span>
              </button>
              <button
                className={'vec-toggle ' + (internalToggles.routes ? 'active' : '')}
                onClick={() => handleInternalToggle('routes')}
              >
                <span>Routes</span>
              </button>
              <button
                className={'vec-toggle ' + (internalToggles.seamarks ? 'active' : '')}
                onClick={() => handleInternalToggle('seamarks')}
              >
                <span>Seamarks</span>
              </button>
              <button
                className={'vec-toggle ' + (internalToggles.ais ? 'active' : '')}
                onClick={() => handleInternalToggle('ais')}
              >
                <span>AIS Fleet</span>
              </button>
              <button
                className={'vec-toggle ' + (internalToggles.territorial ? 'active' : '')}
                onClick={() => handleInternalToggle('territorial')}
              >
                <span>12 NM Limit</span>
              </button>
              <button
                className={'vec-toggle ' + (internalToggles.shelf ? 'active' : '')}
                onClick={() => handleInternalToggle('shelf')}
              >
                <span>200m Shelf</span>
              </button>
              <button
                className={'vec-toggle ' + (internalToggles.restrictions ? 'active' : '')}
                onClick={() => handleInternalToggle('restrictions')}
              >
                <span>Navarea VIII</span>
              </button>
              <button
                className={'vec-toggle ' + (internalToggles.buoys ? 'active' : '')}
                onClick={() => handleInternalToggle('buoys')}
              >
                <span>Aids to Nav</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* Bottom Telemetry HUD */}
      <div className="real-map-bottom-hud">
        <div className="hud-coord-readout">
          <span className="coord-lbl">CURSOR FIX:</span>
          <code className="coord-val">
            {mouseCoords.lat}° N, {mouseCoords.lng}° E
          </code>
          <span className="coord-sep">|</span>
          <span className="coord-lbl">DATUM:</span>
          <span className="coord-val">WGS 84 • INCOIS HYDRO</span>
          {clickPin && (
            <>
              <span className="coord-sep">|</span>
              <span className="coord-lbl">SOUNDING:</span>
              <span className="coord-val" style={{ color: '#38bdf8' }}>
                {clickPin.distKm} km • ~{clickPin.estDepth}m depth
              </span>
            </>
          )}
        </div>

        <div className="map-quick-zoom">
          <button
            onClick={() => mapInstanceRef.current?.zoomIn()}
            title="Zoom In"
          >
            +
          </button>
          <button
            onClick={() => mapInstanceRef.current?.zoomOut()}
            title="Zoom Out"
          >
            −
          </button>
          <button
            onClick={() => mapInstanceRef.current?.setView([9.93, 76.16], 11)}
            title="Recenter on Kochi Approach"
          >
            ⌖
          </button>
          <button
            onClick={() => {
              const next = !isFullscreen;
              setIsFullscreen(next);
              setTimeout(() => {
                mapInstanceRef.current?.invalidateSize();
              }, 250);
            }}
            title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Command Center View'}
            style={{ fontWeight: 'bold' }}
          >
            {isFullscreen ? '✕' : '⛶'}
          </button>
        </div>
      </div>

      {showKeyConfig && (
        <GoogleMapsConfigModal
          isOpen={isConfigModalOpen}
          onClose={() => setIsConfigModalOpen(false)}
          onKeyUpdated={(newKey) => setGoogleKey(newKey)}
        />
      )}
    </div>
  );
}
