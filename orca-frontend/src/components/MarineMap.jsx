import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import Icon from './Icon';
import GoogleMapsConfigModal from './GoogleMapsConfigModal';
import {
  getGoogleMapsApiKey,
  getGoogleTileConfig,
  geocodeLocation,
  INDIA_COASTAL_SECTORS,
  COASTAL_QUICK_PORTS
} from '../utils/googleMaps';

// Curated Maritime Bases & Landmarks across India's Major Coastal Areas
export const MARITIME_LOCATIONS = {
  // Western Seaboard
  veravalHarbour: { name: 'Veraval Fishing Harbour (HQ)', state: 'Gujarat', lat: 20.9000, lng: 70.3667, type: 'port', depth: '7.8m', berths: '4,200 Vessels' },
  kandlaPort: { name: 'Kandla / Deendayal Port', state: 'Gujarat', lat: 23.0033, lng: 70.2189, type: 'port', depth: '14.0m', berths: 'Cargo Gateway' },
  porbandarPort: { name: 'Porbandar Deep Sea Port', state: 'Gujarat', lat: 21.6417, lng: 69.6050, type: 'port', depth: '9.5m', berths: '1,200 Vessels' },
  mumbaiSassoon: { name: 'Sassoon Dock & Mumbai Harbour', state: 'Maharashtra', lat: 18.9167, lng: 72.8250, type: 'port', depth: '12.5m', berths: '1,500 Vessels' },
  mumbaiJnpt: { name: 'JNPT Nhava Sheva Gateway', state: 'Maharashtra', lat: 18.9500, lng: 72.9500, type: 'port', depth: '15.0m', berths: 'Container Terminal' },
  ratnagiriPort: { name: 'Ratnagiri Mirkarwada Port', state: 'Maharashtra', lat: 16.9833, lng: 73.2833, type: 'port', depth: '6.5m', berths: '800 Trawlers' },
  mormugaoPort: { name: 'Mormugao Port (Goa)', state: 'Goa', lat: 15.4167, lng: 73.8000, type: 'port', depth: '14.4m', berths: 'Deep Natural Port' },
  malpeHarbour: { name: 'Malpe Fishery Harbour (HQ)', state: 'Karnataka', lat: 13.3500, lng: 74.7000, type: 'port', depth: '6.8m', berths: '2,400 Vessels' },
  mangalorePort: { name: 'New Mangalore Port', state: 'Karnataka', lat: 12.9250, lng: 74.8150, type: 'port', depth: '15.1m', berths: 'Major Deep Port' },
  kochiHarbour: { name: 'Kochi Fishing Harbour (HQ)', state: 'Kerala', lat: 9.9667, lng: 76.2667, type: 'port', depth: '14.5m', berths: '450 Vessels' },
  fairwayBuoy: { name: 'Cochin Fairway Light Buoy (RW Iso.4s)', state: 'Kerala', lat: 9.9750, lng: 76.1650, type: 'buoy', depth: '24m', light: 'RW Iso.W.4s' },
  vypinLight: { name: 'Vypin Lighthouse (Fl(3) 20s 42m 24M)', state: 'Kerala', lat: 10.0150, lng: 76.2167, type: 'light', depth: 'Land', range: '24 NM' },
  munambamHarbour: { name: 'Munambam Fishing Port', state: 'Kerala', lat: 10.1800, lng: 76.1600, type: 'port', depth: '6.2m', berths: '320 Vessels' },
  vizhinjamPort: { name: 'Vizhinjam International Seaport', state: 'Kerala', lat: 8.3750, lng: 76.9950, type: 'port', depth: '20.0m', berths: 'Transshipment Hub' },
  alappuzhaCoast: { name: 'Alappuzha Coastal Landing', state: 'Kerala', lat: 9.4900, lng: 76.3300, type: 'port', depth: '8.5m', berths: 'Artisanal Landing' },

  // Eastern Seaboard & Islands
  chennaiKasimedu: { name: 'Kasimedu Fishing Harbour (Chennai)', state: 'Tamil Nadu', lat: 13.1200, lng: 80.3000, type: 'port', depth: '7.5m', berths: '1,800 Trawlers' },
  chennaiPort: { name: 'Chennai Major Port', state: 'Tamil Nadu', lat: 13.0850, lng: 80.2980, type: 'port', depth: '17.0m', berths: 'Major Port' },
  tuticorinPort: { name: 'Tuticorin V.O.C Port', state: 'Tamil Nadu', lat: 8.7500, lng: 78.1800, type: 'port', depth: '14.2m', berths: 'Deep Sea Port' },
  rameswaramPier: { name: 'Rameswaram Pamban Pier', state: 'Tamil Nadu', lat: 9.2833, lng: 79.3167, type: 'port', depth: '5.5m', berths: 'Palk Strait Hub' },
  kanyakumariPort: { name: 'Kanyakumari Chinnamuttam Port', state: 'Tamil Nadu', lat: 8.0833, lng: 77.5667, type: 'port', depth: '6.2m', berths: 'Wadge Bank Fleet' },
  vizagPort: { name: 'Visakhapatnam (Vizag) Port', state: 'Andhra Pradesh', lat: 17.6833, lng: 83.2833, type: 'port', depth: '18.1m', berths: 'Major Naval Port' },
  vizagFishing: { name: 'Vizag Fishing Harbour', state: 'Andhra Pradesh', lat: 17.7000, lng: 83.3000, type: 'port', depth: '6.5m', berths: '700 Trawlers' },
  kakinadaPort: { name: 'Kakinada Deepwater Port', state: 'Andhra Pradesh', lat: 16.9833, lng: 82.2667, type: 'port', depth: '14.5m', berths: 'Deepwater Port' },
  paradipPort: { name: 'Paradip Major Port', state: 'Odisha', lat: 20.2667, lng: 86.6667, type: 'port', depth: '17.5m', berths: 'Major Eastern Port' },
  paradipFishing: { name: 'Paradip Fishing Harbour', state: 'Odisha', lat: 20.2833, lng: 86.6833, type: 'port', depth: '6.2m', berths: '850 Trawlers' },
  dighaHarbour: { name: 'Digha (Sankarpur) Fishery Harbour', state: 'West Bengal', lat: 21.6333, lng: 87.5667, type: 'port', depth: '5.8m', berths: '1,100 Trawlers' },
  haldiaPort: { name: 'Haldia Dock Complex', state: 'West Bengal', lat: 22.0167, lng: 88.0667, type: 'port', depth: '12.5m', berths: 'Riverine Port' },
  portBlairHarbour: { name: 'Port Blair Haddo Harbour', state: 'Andaman & Nicobar', lat: 11.6667, lng: 92.7333, type: 'port', depth: '12.0m', berths: 'Strategic Naval Hub' },
  kavarattiHarbour: { name: 'Kavaratti Island Harbour', state: 'Lakshadweep', lat: 10.5667, lng: 72.6333, type: 'port', depth: '4.5m', berths: 'Island Fishery Base' }
};

// Official INCOIS Potential Fishing Zones (PFZs) across India's Major Coastal Areas
export const PFZ_COORDINATES = {
  // ── Kerala & Malabar ──
  'PFZ-01': { name: 'PFZ-01: Kochi Offshore Front', region: 'Kerala', lat: 9.8700, lng: 76.1400, dist: '14.2 km SW', sst: '28.4 °C', chl: '0.88 mg/m³', depth: '42m', potential: 'High', target: 'Indian Mackerel, Sardine, Ribbonfish' },
  'PFZ-02': { name: 'PFZ-02: Vypin Deep Upwelling', region: 'Kerala', lat: 9.9600, lng: 76.0700, dist: '21.5 km W', sst: '28.1 °C', chl: '0.79 mg/m³', depth: '58m', potential: 'High', target: 'Squid, Cuttlefish, Trevally' },
  'PFZ-03': { name: 'PFZ-03: Alappuzha Shelf Margin', region: 'Kerala', lat: 9.5700, lng: 76.1900, dist: '31.8 km SSW', sst: '27.8 °C', chl: '0.64 mg/m³', depth: '75m', potential: 'Medium', target: 'Tuna, Seer Fish, Barracuda' },
  'PFZ-04': { name: 'PFZ-04: Chellanam Canyon', region: 'Kerala', lat: 9.4700, lng: 75.9700, dist: '42.0 km SW', sst: '27.5 °C', chl: '0.52 mg/m³', depth: '110m', potential: 'Medium', target: 'Pelagic Shark, Skipjack Tuna' },
  'PFZ-05': { name: 'PFZ-05: Munambam Outer Trench', region: 'Kerala', lat: 10.3000, lng: 75.7500, dist: '56.4 km NW', sst: '27.2 °C', chl: '0.41 mg/m³', depth: '160m', potential: 'Low', target: 'Yellowfin Tuna, Billfish' },
  'PFZ-06': { name: 'PFZ-06: Malabar Deep Margin', region: 'Kerala', lat: 10.4000, lng: 75.5300, dist: '68.0 km WNW', sst: '27.0 °C', chl: '0.38 mg/m³', depth: '320m', potential: 'Low', target: 'Oceanic Whitetip, Swordfish' },
  'PFZ-07': { name: 'PFZ-07: Lakshadweep Basin Edge', region: 'Lakshadweep', lat: 9.7800, lng: 75.4100, dist: '74.5 km WSW', sst: '26.8 °C', chl: '0.32 mg/m³', depth: '550m', potential: 'Low', target: 'Bigeye Tuna, Deepwater Snapper' },

  // ── Gujarat Coast (Kutch & Saurashtra) ──
  'PFZ-GJ01': { name: 'PFZ-GJ01: Veraval Offshore Front', region: 'Gujarat', lat: 20.6500, lng: 69.8000, dist: '48 km SW of Veraval', sst: '27.9 °C', chl: '1.25 mg/m³', depth: '55m', potential: 'High', target: 'Silver Pomfret, Ribbonfish, Croakers' },
  'PFZ-GJ02': { name: 'PFZ-GJ02: Okha / Kutch Thermal Plume', region: 'Gujarat', lat: 22.3500, lng: 68.6500, dist: '35 km W of Okha', sst: '27.4 °C', chl: '1.10 mg/m³', depth: '45m', potential: 'High', target: 'Hilsa, Indian Salmon, Bombay Duck' },

  // ── Maharashtra & Konkan ──
  'PFZ-MH01': { name: 'PFZ-MH01: Mumbai High Pelagic Edge', region: 'Maharashtra', lat: 19.1000, lng: 71.8000, dist: '95 km W of Mumbai', sst: '28.2 °C', chl: '0.95 mg/m³', depth: '85m', potential: 'High', target: 'Seer Fish, King Mackerel, Black Pomfret' },
  'PFZ-MH02': { name: 'PFZ-MH02: Ratnagiri Mirkarwada Shelf', region: 'Maharashtra', lat: 16.9000, lng: 72.5000, dist: '42 km W of Ratnagiri', sst: '28.0 °C', chl: '0.82 mg/m³', depth: '65m', potential: 'Medium', target: 'Squid, Sardine, Mackerel' },

  // ── Goa & Karavali (Karnataka) ──
  'PFZ-KA01': { name: 'PFZ-KA01: Malpe Continental Slope', region: 'Karnataka', lat: 13.3000, lng: 74.1000, dist: '55 km W of Malpe', sst: '28.3 °C', chl: '0.92 mg/m³', depth: '70m', potential: 'High', target: 'Indian Oil Sardine, Horse Mackerel, Tuna' },
  'PFZ-GA01': { name: 'PFZ-GA01: Mormugao Shelf Break', region: 'Goa', lat: 15.3500, lng: 73.2000, dist: '45 km W of Vasco', sst: '28.1 °C', chl: '0.78 mg/m³', depth: '60m', potential: 'Medium', target: 'Carangids, Cuttlefish, Anchovy' },

  // ── Kanyakumari & Gulf of Mannar ──
  'PFZ-WB01': { name: 'PFZ-WB01: Wadge Bank Core Upwelling', region: 'Kanyakumari', lat: 7.8000, lng: 77.4000, dist: '40 km S of Cape Comorin', sst: '26.9 °C', chl: '1.45 mg/m³', depth: '65m', potential: 'High', target: 'Yellowfin Tuna, Skipjack, Snappers, Grouper' },
  'PFZ-TN01': { name: 'PFZ-TN01: Gulf of Mannar Shelf Trench', region: 'Tamil Nadu', lat: 8.7000, lng: 78.4500, dist: '32 km E of Tuticorin', sst: '27.7 °C', chl: '0.85 mg/m³', depth: '52m', potential: 'High', target: 'Seer Fish, Trevally, Barramundi' },

  // ── Tamil Nadu (Coromandel) ──
  'PFZ-TN02': { name: 'PFZ-TN02: Chennai Deep Pelagic Front', region: 'Tamil Nadu', lat: 13.1500, lng: 80.6000, dist: '38 km E of Kasimedu', sst: '28.6 °C', chl: '0.74 mg/m³', depth: '95m', potential: 'Medium', target: 'Sailfish, Yellowfin Tuna, Tiger Prawn' },

  // ── Andhra Pradesh ──
  'PFZ-AP01': { name: 'PFZ-AP01: Visakhapatnam Trench Front', region: 'Andhra Pradesh', lat: 17.5000, lng: 83.6000, dist: '36 km SE of Vizag Port', sst: '28.5 °C', chl: '0.90 mg/m³', depth: '85m', potential: 'High', target: 'Ribbonfish, Croakers, Skipjack Tuna' },
  'PFZ-AP02': { name: 'PFZ-AP02: Kakinada Godavari Plume Front', region: 'Andhra Pradesh', lat: 16.7000, lng: 82.6000, dist: '28 km SE of Kakinada', sst: '28.8 °C', chl: '1.30 mg/m³', depth: '48m', potential: 'High', target: 'Tiger Prawn, White Pomfret, Catfish' },

  // ── Odisha ──
  'PFZ-OD01': { name: 'PFZ-OD01: Paradip Shelf Upwelling', region: 'Odisha', lat: 20.0500, lng: 86.9500, dist: '42 km SE of Paradip', sst: '28.2 °C', chl: '1.15 mg/m³', depth: '50m', potential: 'High', target: 'Hilsa, Pomfret, Ribbonfish, Seabass' },

  // ── West Bengal ──
  'PFZ-WB02': { name: 'PFZ-WB02: Swatch of No Ground Trench', region: 'West Bengal', lat: 21.2000, lng: 88.5000, dist: '65 km S of Digha', sst: '28.1 °C', chl: '1.40 mg/m³', depth: '180m', potential: 'High', target: 'Tenualosa ilisha (Hilsa), Bombay Duck, Croaker' }
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
  initialSectorId = 'all-india',
  showControls = true,
  showKeyConfig = true,
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
  const [selectedRegionId, setSelectedRegionId] = useState(initialSectorId || 'all-india');
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchFeedback, setSearchFeedback] = useState('');
  const [isFullscreen, setIsFullscreen] = useState(false);

  const [mouseCoords, setMouseCoords] = useState({ lat: 15.2000, lng: 78.5000 });
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

    const sectorInit = INDIA_COASTAL_SECTORS.find((s) => s.id === (initialSectorId || 'all-india')) || INDIA_COASTAL_SECTORS[0];
    const initialCenter = focusedZone && PFZ_COORDINATES[focusedZone]
      ? [PFZ_COORDINATES[focusedZone].lat, PFZ_COORDINATES[focusedZone].lng]
      : [sectorInit.lat, sectorInit.lng];
    const initialZoom = focusedZone ? 12 : (large ? (sectorInit.id === 'all-india' ? 5 : sectorInit.zoom) : (sectorInit.id === 'all-india' ? 5 : sectorInit.zoom - 1));

    const map = L.map(mapContainerRef.current, {
      center: initialCenter,
      zoom: initialZoom,
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
    // 1. PFZ LAYER GROUP (Pan-India INCOIS Coverage)
    // ──────────────────────────────────────────────────────────────────────────
    const pfzGroup = L.layerGroup();
    Object.entries(PFZ_COORDINATES).forEach(([id, z]) => {
      const isHigh = z.potential === 'High';
      const isMed = z.potential === 'Medium';
      const color = isHigh ? '#0284c7' : isMed ? '#f59e0b' : '#64748b';
      const fillColor = isHigh ? '#38bdf8' : isMed ? '#fbbf24' : '#94a3b8';

      const circle = L.circle([z.lat, z.lng], {
        radius: isHigh ? 4800 : 3800,
        color: color,
        fillColor: fillColor,
        fillOpacity: 0.25,
        weight: 2,
        dashArray: '5, 5'
      }).bindPopup(`
        <div style="font-family: sans-serif; font-size: 11.5px; line-height: 1.4;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 2px;">
            <strong style="color: #0284c7; font-size: 12px;">🐟 ${z.name}</strong>
            <span style="font-size: 9.5px; background: rgba(2,132,199,0.15); color: #0284c7; padding: 1px 4px; border-radius: 3px; font-weight: bold;">${z.region || 'India'}</span>
          </div>
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
    // 2. SST LAYER GROUP (Pan-India Thermal Fronts & Buoy Telemetry)
    // ──────────────────────────────────────────────────────────────────────────
    const sstGroup = L.layerGroup();
    // West Coast Thermal Fronts
    const sstGujarat = L.polygon([
      [21.80, 69.20], [21.90, 70.10], [20.50, 70.30], [20.40, 69.40]
    ], { color: '#06b6d4', weight: 2, fillColor: '#06b6d4', fillOpacity: 0.18 })
      .bindPopup('<b>SST Saurashtra Thermal Front: 27.9°C</b><br/>Primary winter/spring pelagic divergence in Arabian Sea.');
    sstGroup.addLayer(sstGujarat);

    const sstMumbai = L.polygon([
      [19.60, 71.40], [19.60, 72.30], [18.20, 72.50], [18.20, 71.60]
    ], { color: '#0ea5e9', weight: 1.8, fillColor: '#0ea5e9', fillOpacity: 0.16, dashArray: '4, 4' })
      .bindPopup('<b>SST Mumbai High Offshore Front: 28.2°C</b><br/>Thermal boundary supporting pelagic fish schools.');
    sstGroup.addLayer(sstMumbai);

    const sstMalabar = L.polygon([
      [10.45, 75.75], [10.45, 76.08], [9.25, 76.20], [9.25, 75.90]
    ], { color: '#06b6d4', weight: 2, fillColor: '#06b6d4', fillOpacity: 0.18 })
      .bindPopup('<b>SST Malabar Thermal Break Upwelling Front: 28.2°C</b><br/>Primary thermal divergence boundary near Kochi.');
    sstGroup.addLayer(sstMalabar);

    const sstWadge = L.polygon([
      [8.20, 77.00], [8.30, 77.80], [7.40, 77.90], [7.40, 77.10]
    ], { color: '#0284c7', weight: 2, fillColor: '#0284c7', fillOpacity: 0.20 })
      .bindPopup('<b>SST Wadge Bank Upwelling Core: 26.9°C</b><br/>Intense deep-water nutrient upwelling south of Cape Comorin.');
    sstGroup.addLayer(sstWadge);

    // East Coast Thermal Fronts
    const sstCoromandel = L.polygon([
      [13.60, 80.40], [13.60, 80.80], [12.40, 80.60], [12.40, 80.20]
    ], { color: '#f97316', weight: 1.8, fillColor: '#f97316', fillOpacity: 0.16, dashArray: '4, 4' })
      .bindPopup('<b>SST Coromandel Coastal Thermal Boundary: 28.6°C</b><br/>East Coast Current interaction zone.');
    sstGroup.addLayer(sstCoromandel);

    const sstAndhra = L.polygon([
      [17.80, 83.40], [17.80, 84.10], [16.50, 83.10], [16.50, 82.40]
    ], { color: '#06b6d4', weight: 2, fillColor: '#06b6d4', fillOpacity: 0.18 })
      .bindPopup('<b>SST Godavari-Krishna Delta Front: 28.5°C</b><br/>River plume divergence zone high in nutrients.');
    sstGroup.addLayer(sstAndhra);

    const sstOdisha = L.polygon([
      [20.80, 86.80], [20.80, 87.50], [19.50, 87.10], [19.50, 86.40]
    ], { color: '#0284c7', weight: 2, fillColor: '#0284c7', fillOpacity: 0.18 })
      .bindPopup('<b>SST Paradip & Bengal Shelf Divergence: 28.2°C</b><br/>Deep slope upwelling front in North Bay of Bengal.');
    sstGroup.addLayer(sstOdisha);

    // Pan-India Moored SST Buoys
    [
      { name: 'Veraval Coast SST Buoy', lat: 20.85, lng: 70.25, temp: '27.9°C' },
      { name: 'Mumbai Offshore SST Buoy', lat: 18.90, lng: 72.40, temp: '28.2°C' },
      { name: 'Malpe Karavali SST Buoy', lat: 13.30, lng: 74.45, temp: '28.3°C' },
      { name: 'Kochi Inshore SST Buoy', lat: 9.98, lng: 76.20, temp: '28.9°C' },
      { name: 'Cape Comorin Wadge Bank Buoy', lat: 7.85, lng: 77.45, temp: '26.9°C' },
      { name: 'Tuticorin Gulf of Mannar Buoy', lat: 8.70, lng: 78.35, temp: '27.7°C' },
      { name: 'Chennai Deep SST Buoy', lat: 13.15, lng: 80.50, temp: '28.6°C' },
      { name: 'Vizag Eastern Shelf SST Buoy', lat: 17.65, lng: 83.55, temp: '28.5°C' },
      { name: 'Paradip Coastal SST Buoy', lat: 20.20, lng: 86.85, temp: '28.2°C' },
      { name: 'Sandheads Bengal Met Buoy', lat: 21.05, lng: 88.25, temp: '28.1°C' },
      { name: 'Port Blair Andaman SST Buoy', lat: 11.60, lng: 92.85, temp: '28.8°C' }
    ].forEach((b) => {
      const icon = L.divIcon({
        className: 'sst-pill-icon',
        html: `<div style="background:#ea580c;color:#fff;font-family:monospace;font-size:9px;font-weight:bold;padding:1px 5px;border-radius:3px;border:1px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.4);white-space:nowrap;">🌡️ ${b.temp}</div>`,
        iconSize: [60, 20],
        iconAnchor: [30, 10]
      });
      const marker = L.marker([b.lat, b.lng], { icon }).bindPopup(`<b>${b.name}</b><br/>Surface Temperature: <b>${b.temp}</b><br/><small style="color:#64748b;">INCOIS Moored Ocean Buoy Network</small>`);
      sstGroup.addLayer(marker);
    });
    sstGroup.addTo(map);
    layersRef.current.sstGroup = sstGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 3. CHLOROPHYLL LAYER GROUP (Pan-India Biomass Plumes)
    // ──────────────────────────────────────────────────────────────────────────
    const chlorophyllGroup = L.layerGroup();
    // Gujarat Plume
    const chlGujarat = L.polygon([
      [21.50, 69.50], [21.80, 70.30], [20.80, 70.50], [20.50, 69.70]
    ], { color: '#10b981', weight: 1.8, fillColor: '#10b981', fillOpacity: 0.24, dashArray: '3, 4' })
      .bindPopup('<b>Saurashtra High Biomass Plume</b><br/>Concentration: <b>1.85 mg/m³</b><br/>High phytoplankton supporting ribbonfish & pomfret.');
    chlorophyllGroup.addLayer(chlGujarat);

    // Malabar Plume
    const chlMalabar = L.polygon([
      [10.05, 76.02], [10.15, 76.08], [9.90, 76.15], [9.80, 76.08]
    ], { color: '#10b981', weight: 1.5, fillColor: '#10b981', fillOpacity: 0.26, dashArray: '3, 4' })
      .bindPopup('<b>Kochi-Alappuzha Chlorophyll-a Plume</b><br/>Concentration: <b>1.42 mg/m³</b><br/>High baitfish & pelagic aggregation.');
    chlorophyllGroup.addLayer(chlMalabar);

    // Wadge Bank Plume
    const chlWadge = L.polygon([
      [8.10, 77.20], [8.15, 77.70], [7.60, 77.75], [7.55, 77.25]
    ], { color: '#059669', weight: 1.8, fillColor: '#059669', fillOpacity: 0.24 })
      .bindPopup('<b>Wadge Bank Nutrient Plume</b><br/>Concentration: <b>1.65 mg/m³</b><br/>Prime oceanic tuna & cephalopod concentration.');
    chlorophyllGroup.addLayer(chlWadge);

    // Godavari Plume
    const chlGodavari = L.polygon([
      [17.10, 82.30], [17.10, 82.90], [16.40, 82.70], [16.40, 82.10]
    ], { color: '#10b981', weight: 1.8, fillColor: '#10b981', fillOpacity: 0.22, dashArray: '3, 4' })
      .bindPopup('<b>Godavari Delta Plume</b><br/>Concentration: <b>1.75 mg/m³</b><br/>High estuarine nutrient enrichment.');
    chlorophyllGroup.addLayer(chlGodavari);

    // Bengal / Sundarbans Plume
    const chlSundarbans = L.polygon([
      [21.80, 87.70], [21.80, 88.70], [21.10, 88.50], [21.10, 87.50]
    ], { color: '#059669', weight: 2, fillColor: '#059669', fillOpacity: 0.28 })
      .bindPopup('<b>Sundarbans Delta Biomass Plume</b><br/>Concentration: <b>2.10 mg/m³</b><br/>Hilsa migration route & rich estuarine biomass.');
    chlorophyllGroup.addLayer(chlSundarbans);

    [
      { lat: 21.10, lng: 69.90, val: '1.85 mg/m³' },
      { lat: 9.94, lng: 76.11, val: '1.42 mg/m³' },
      { lat: 7.85, lng: 77.45, val: '1.65 mg/m³' },
      { lat: 16.75, lng: 82.50, val: '1.75 mg/m³' },
      { lat: 21.45, lng: 88.10, val: '2.10 mg/m³' }
    ].forEach((c) => {
      const icon = L.divIcon({
        className: 'chl-pill-icon',
        html: `<div style="background:#059669;color:#fff;font-family:monospace;font-size:9px;font-weight:bold;padding:1px 5px;border-radius:3px;border:1px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.4);white-space:nowrap;">🌿 ${c.val}</div>`,
        iconSize: [80, 20],
        iconAnchor: [40, 10]
      });
      chlorophyllGroup.addLayer(L.marker([c.lat, c.lng], { icon }));
    });
    chlorophyllGroup.addTo(map);
    layersRef.current.chlorophyllGroup = chlorophyllGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 4. CURRENTS LAYER GROUP (Pan-India Coastal Current System)
    // ──────────────────────────────────────────────────────────────────────────
    const currentsGroup = L.layerGroup();
    const currentVectors = [
      // West India Coastal Current (WICC) - Southerly flow
      { coords: [[21.50, 69.60], [20.40, 70.00]], speed: '1.3 kts', dir: '150° SSE (WICC)' },
      { coords: [[19.20, 72.00], [17.50, 72.60]], speed: '1.4 kts', dir: '160° SSE (WICC)' },
      { coords: [[14.50, 73.80], [12.80, 74.30]], speed: '1.2 kts', dir: '155° SSE (WICC)' },
      { coords: [[10.20, 76.05], [9.65, 76.22]], speed: '1.4 kts', dir: '160° SSE (WICC)' },
      { coords: [[8.20, 77.20], [7.50, 77.80]], speed: '1.8 kts', dir: '135° SE (Wadge Bank Current)' },

      // East India Coastal Current (EICC)
      { coords: [[10.50, 80.40], [12.80, 80.60]], speed: '1.5 kts', dir: '015° NNE (EICC)' },
      { coords: [[13.20, 80.70], [16.20, 82.50]], speed: '1.6 kts', dir: '035° NE (EICC)' },
      { coords: [[16.80, 82.80], [19.50, 86.20]], speed: '1.7 kts', dir: '045° NE (EICC)' },
      { coords: [[19.80, 86.80], [21.20, 88.40]], speed: '1.4 kts', dir: '050° NE (Bay Current)' }
    ];
    currentVectors.forEach((cv) => {
      const line = L.polyline(cv.coords, {
        color: '#38bdf8', weight: 2.8, opacity: 0.85, dashArray: '8, 8'
      }).bindPopup(`<b>Indian Coastal Current</b><br/>Speed: <b>${cv.speed}</b> • Set: <b>${cv.dir}</b><br/><small style="color:#64748b;">INCOIS Ocean Circulation Model</small>`);
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
    // 5. WAVE HEIGHT LAYER GROUP (Pan-India Swell Forecast)
    // ──────────────────────────────────────────────────────────────────────────
    const waveHeightGroup = L.layerGroup();
    // Arabian Sea Swell Contours
    const waveArabian = L.polygon([
      [22.50, 68.00], [22.50, 70.50], [15.00, 73.00], [15.00, 70.00]
    ], { color: '#f59e0b', weight: 1.5, fillColor: '#f59e0b', fillOpacity: 0.16, dashArray: '5, 5' })
      .bindPopup('<b>North Arabian Sea Swell: 1.5m - 1.9m</b><br/>State: Moderate. Mechanized trawlers operational.');
    waveHeightGroup.addLayer(waveArabian);

    const waveSouthwest = L.polygon([
      [12.00, 74.00], [12.00, 75.50], [8.00, 77.50], [8.00, 75.00]
    ], { color: '#ef4444', weight: 1.5, fillColor: '#ef4444', fillOpacity: 0.18, dashArray: '6, 6' })
      .bindPopup('<b>Southwest Coast High Swell Zone: 2.2m - 2.8m</b><br/>State: Rough. Caution for craft under 15m.');
    waveHeightGroup.addLayer(waveSouthwest);

    // Bay of Bengal Swell Contours
    const waveBay = L.polygon([
      [11.00, 80.00], [11.00, 83.00], [19.00, 87.00], [19.00, 84.00]
    ], { color: '#10b981', weight: 1.5, fillColor: '#10b981', fillOpacity: 0.14 })
      .bindPopup('<b>Central Bay of Bengal Swell: 1.1m - 1.5m</b><br/>State: Slight to Moderate. Safe for all certified craft.');
    waveHeightGroup.addLayer(waveBay);

    waveHeightGroup.addTo(map);
    layersRef.current.waveHeightGroup = waveHeightGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 6. WAVE DIRECTION LAYER GROUP
    // ──────────────────────────────────────────────────────────────────────────
    const waveDirectionGroup = L.layerGroup();
    [
      { lat: 21.00, lng: 69.50, deg: '255° WSW', period: '7.8s' },
      { lat: 18.50, lng: 72.00, deg: '260° W', period: '8.2s' },
      { lat: 13.50, lng: 74.00, deg: '250° WSW', period: '8.4s' },
      { lat: 9.98, lng: 76.10, deg: '245° WSW', period: '8.4s' },
      { lat: 7.90, lng: 77.50, deg: '210° SSW', period: '9.2s' },
      { lat: 13.20, lng: 80.80, deg: '160° SSE', period: '7.6s' },
      { lat: 17.50, lng: 83.60, deg: '175° S', period: '8.0s' },
      { lat: 20.40, lng: 87.10, deg: '185° S', period: '8.5s' }
    ].forEach((w) => {
      const icon = L.divIcon({
        className: 'wave-dir-icon',
        html: `<div style="background:#0891b2;color:#fff;font-family:monospace;font-size:9px;font-weight:bold;padding:2px 6px;border-radius:3px;border:1px solid #fff;white-space:nowrap;">↗ Swell ${w.deg} (${w.period})</div>`,
        iconSize: [125, 20],
        iconAnchor: [62, 10]
      });
      const marker = L.marker([w.lat, w.lng], { icon }).bindPopup(`<b>Dominant Swell Vector</b><br/>Direction: <b>${w.deg}</b> • Peak Period: <b>${w.period}</b>`);
      waveDirectionGroup.addLayer(marker);
    });
    layersRef.current.waveDirectionGroup = waveDirectionGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 7. WIND LAYER GROUP (Pan-India Coastal Stations)
    // ──────────────────────────────────────────────────────────────────────────
    const windGroup = L.layerGroup();
    [
      { name: 'Veraval Coast Wind Station', lat: 20.90, lng: 70.37, speed: '16 kts', dir: 'NW 315°', gust: '21 kts' },
      { name: 'Mumbai Offshore Met Buoy', lat: 18.92, lng: 72.82, speed: '15 kts', dir: 'WNW 295°', gust: '19 kts' },
      { name: 'Malpe Karavali Wind Station', lat: 13.35, lng: 74.70, speed: '12 kts', dir: 'W 270°', gust: '16 kts' },
      { name: 'Kochi Fairway Buoy Wind Station', lat: 9.975, lng: 76.165, speed: '14 kts', dir: 'WNW 290°', gust: '18 kts' },
      { name: 'Kanyakumari Cape Wind Station', lat: 8.08, lng: 77.57, speed: '22 kts', dir: 'WSW 245°', gust: '28 kts' },
      { name: 'Chennai Port Met Station', lat: 13.08, lng: 80.30, speed: '13 kts', dir: 'SE 135°', gust: '17 kts' },
      { name: 'Visakhapatnam Coastal Station', lat: 17.68, lng: 83.28, speed: '15 kts', dir: 'SSW 205°', gust: '20 kts' },
      { name: 'Paradip Outer Met Buoy', lat: 20.26, lng: 86.67, speed: '17 kts', dir: 'S 180°', gust: '23 kts' },
      { name: 'Sandheads Bengal Met Light Station', lat: 20.95, lng: 88.20, speed: '18 kts', dir: 'SSE 160°', gust: '24 kts' }
    ].forEach((w) => {
      const icon = L.divIcon({
        className: 'wind-pill-icon',
        html: `<div style="background:#0284c7;color:#fff;font-family:monospace;font-size:9px;font-weight:bold;padding:2px 6px;border-radius:3px;border:1.5px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);white-space:nowrap;">💨 ${w.speed} ${w.dir.split(' ')[0]}</div>`,
        iconSize: [95, 22],
        iconAnchor: [47, 11]
      });
      const marker = L.marker([w.lat, w.lng], { icon }).bindPopup(`
        <b>${w.name}</b><br/>
        Sustained Wind: <b>${w.speed}</b> • Gusts: <b>${w.gust}</b><br/>
        Direction: <b>${w.dir}</b> • IMD Marine Grid
      `);
      windGroup.addLayer(marker);
    });
    windGroup.addTo(map);
    layersRef.current.windGroup = windGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 8. TIDE LAYER GROUP (Major Indian Ports Tide Gauges)
    // ──────────────────────────────────────────────────────────────────────────
    const tideGroup = L.layerGroup();
    [
      { name: 'Kandla Port Tide Station (Kutch)', lat: 23.00, lng: 70.22, level: '+3.42m', state: 'FLOOD (Rising)', hw: '15:10 IST (+3.85m)' },
      { name: 'Mumbai Apollo Bunder Tide Gauge', lat: 18.92, lng: 72.83, level: '+2.65m', state: 'FLOOD (Rising)', hw: '14:50 IST (+3.10m)' },
      { name: 'Mormugao Port Gauge (Goa)', lat: 15.42, lng: 73.80, level: '+1.82m', state: 'SLACK (High)', hw: '14:15 IST (+1.95m)' },
      { name: 'New Mangalore Port Gauge', lat: 12.92, lng: 74.82, level: '+1.45m', state: 'EBB (Falling)', hw: '13:40 IST (+1.55m)' },
      { name: 'Cochin Port (Willingdon Island)', lat: 9.960, lng: 76.270, level: '+1.18m', state: 'FLOOD (Rising)', hw: '14:35 IST (+1.24m)' },
      { name: 'Tuticorin VOC Port Gauge', lat: 8.75, lng: 78.18, level: '+0.95m', state: 'SLACK', hw: '14:00 IST (+1.05m)' },
      { name: 'Chennai Port Marine Gauge', lat: 13.08, lng: 80.30, level: '+1.12m', state: 'FLOOD', hw: '14:45 IST (+1.28m)' },
      { name: 'Visakhapatnam Naval Tide Gauge', lat: 17.68, lng: 83.28, level: '+1.38m', state: 'FLOOD', hw: '15:00 IST (+1.52m)' },
      { name: 'Paradip Port Coastal Gauge', lat: 20.26, lng: 86.67, level: '+2.14m', state: 'FLOOD', hw: '15:30 IST (+2.40m)' },
      { name: 'Sagar Island / Haldia Gauge (Hooghly)', lat: 21.65, lng: 88.05, level: '+3.78m', state: 'BORE ACTIVE', hw: '15:45 IST (+4.20m)' }
    ].forEach((t) => {
      const icon = L.divIcon({
        className: 'tide-pill-icon',
        html: `<div style="background:#0d9488;color:#fff;font-family:monospace;font-size:9px;font-weight:bold;padding:2px 6px;border-radius:3px;border:1.5px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);white-space:nowrap;">🌊 ${t.level} ${t.state.split(' ')[0]}</div>`,
        iconSize: [110, 22],
        iconAnchor: [55, 11]
      });
      const marker = L.marker([t.lat, t.lng], { icon }).bindPopup(`
        <b>${t.name}</b><br/>
        Current Height: <b>${t.level}</b> (${t.state})<br/>
        Next High Water: <b>${t.hw}</b><br/>
        <small style="color:#64748b;">Survey of India Marine Hydrographic Data</small>
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
      [9.10, 73.80], [9.50, 74.20], [10.10, 74.50], [10.70, 74.70], [11.40, 74.80]
    ];
    const cycloneTrackLine = L.polyline(cycloneTrackCoords, {
      color: '#dc2626', weight: 3.5, dashArray: '6, 6'
    }).bindPopup('<b>IMD Cyclone Advisory Track</b><br/>Deep Depression BOB/ARB-02 moving NNW at 12 km/h.');
    cycloneGroup.addLayer(cycloneTrackLine);

    const cycloneCone = L.polygon([
      [9.10, 73.80], [11.80, 74.10], [11.80, 75.40], [10.10, 74.50]
    ], {
      color: '#ef4444', weight: 1.5, fillColor: '#ef4444', fillOpacity: 0.18, dashArray: '4, 4'
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
      color: '#eab308', weight: 2, fillColor: '#facc15', fillOpacity: 0.28, dashArray: '4, 4'
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
    // 11. WEATHER WARNINGS LAYER GROUP (Pan-India Marine Alerts)
    // ──────────────────────────────────────────────────────────────────────────
    const weatherWarningsGroup = L.layerGroup();
    // Southwest Coast Warning
    const warningZoneSW = L.polygon([
      [10.50, 76.00], [10.50, 76.25], [9.30, 76.40], [9.30, 76.05]
    ], { color: '#f59e0b', weight: 2.5, fillColor: '#f59e0b', fillOpacity: 0.20, dashArray: '6, 6' })
      .bindPopup(`
        <div style="font-family: sans-serif; font-size: 11.5px;">
          <strong style="color: #d97706; display: block; margin-bottom: 3px;">⚠️ INCOIS HIGH SWELL ALERT (Kerala Coast)</strong>
          <span>Yellow Warning: High Swell Waves (2.2m - 2.6m)</span><br/>
          <small style="color: #b45309; font-weight: bold;">Artisanal non-motorized craft advised not to cross surf zone.</small>
        </div>
      `);
    weatherWarningsGroup.addLayer(warningZoneSW);

    // North Bay of Bengal Warning
    const warningZoneBay = L.polygon([
      [20.50, 86.50], [21.80, 87.80], [21.20, 88.80], [19.80, 87.20]
    ], { color: '#f59e0b', weight: 2.5, fillColor: '#f59e0b', fillOpacity: 0.20, dashArray: '6, 6' })
      .bindPopup(`
        <div style="font-family: sans-serif; font-size: 11.5px;">
          <strong style="color: #d97706; display: block; margin-bottom: 3px;">⚠️ INCOIS SQUALLY WEATHER ALERT (Odisha-Bengal Coast)</strong>
          <span>Wind speeds reaching 40-50 km/h gusting to 60 km/h. Sea conditions rough.</span>
        </div>
      `);
    weatherWarningsGroup.addLayer(warningZoneBay);

    weatherWarningsGroup.addTo(map);
    layersRef.current.weatherWarningsGroup = weatherWarningsGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 12. RESTRICTED AREAS & TSS TRAFFIC CORRIDORS
    // ──────────────────────────────────────────────────────────────────────────
    const restrictedAreasGroup = L.layerGroup();
    // NAVAREA VIII Sector Bravo (Kochi)
    const dangerZone = L.polygon(NAVAL_DANGER_BOX, {
      color: '#dc2626', weight: 2, fillColor: '#ef4444', fillOpacity: 0.28, dashArray: '6, 6'
    }).bindPopup(`
      <div style="font-family: sans-serif; font-size: 11.5px;">
        <strong style="color: #dc2626; display: block; margin-bottom: 2px;">⚠️ NAVAREA VIII RESTRICTED ZONE</strong>
        <span>Sector Bravo: Joint Naval Firing Exercises</span><br/>
        <small style="color: #dc2626; font-weight: bold;">PROHIBITION: All commercial and fishing vessels strictly excluded.</small>
      </div>
    `);
    restrictedAreasGroup.addLayer(dangerZone);

    // Mumbai High Offshore Defense Exclusion Area (ODAG)
    const mumbaiHighExclusion = L.polygon([
      [19.10, 71.00], [19.60, 71.00], [19.60, 71.60], [19.10, 71.60]
    ], { color: '#ef4444', weight: 2, fillColor: '#ef4444', fillOpacity: 0.24, dashArray: '6, 6' })
      .bindPopup('<b>⚠️ Mumbai High Offshore Security Zone (ODAG)</b><br/>500m Safety Exclusion Zone around all oil & gas platforms. Fishing prohibited.');
    restrictedAreasGroup.addLayer(mumbaiHighExclusion);

    // Chandipur ITR Safety Zone (Odisha)
    const chandipurZone = L.polygon([
      [21.10, 87.00], [21.50, 87.30], [21.30, 87.60], [20.90, 87.20]
    ], { color: '#dc2626', weight: 2, fillColor: '#ef4444', fillOpacity: 0.24, dashArray: '6, 6' })
      .bindPopup('<b>⚠️ Chandipur ITR Maritime Exclusion Zone (DRDO)</b><br/>Notice to Mariners: Rocket test firing hazard area.');
    restrictedAreasGroup.addLayer(chandipurZone);

    // Cochin TSS
    const tssIn = L.polyline(TSS_INBOUND_LANE, { color: '#0284c7', weight: 3, dashArray: '4, 4' })
      .bindPopup('<b>Cochin Port TSS Inbound Lane (070°)</b><br/>Deep draft commercial vessels approaching fairway.');
    restrictedAreasGroup.addLayer(tssIn);

    const tssOut = L.polyline(TSS_OUTBOUND_LANE, { color: '#0284c7', weight: 3, dashArray: '4, 4' })
      .bindPopup('<b>Cochin Port TSS Outbound Lane (250°)</b><br/>Departing vessel traffic corridor.');
    restrictedAreasGroup.addLayer(tssOut);

    // Mumbai Approach TSS
    const tssMumbai = L.polyline([
      [18.70, 72.50], [18.90, 72.75]
    ], { color: '#0284c7', weight: 3, dashArray: '4, 4' })
      .bindPopup('<b>Mumbai Harbour Pilot TSS Channel (045°)</b><br/>Approaching container and crude carrier corridor.');
    restrictedAreasGroup.addLayer(tssMumbai);

    // Gulf of Kutch TSS
    const tssKutch = L.polyline([
      [22.45, 68.80], [22.65, 69.50]
    ], { color: '#0284c7', weight: 3, dashArray: '4, 4' })
      .bindPopup('<b>Gulf of Kutch Deepwater Channel TSS</b><br/>Traffic separation for Kandla & Mundra supertankers.');
    restrictedAreasGroup.addLayer(tssKutch);

    restrictedAreasGroup.addTo(map);
    layersRef.current.restrictedAreasGroup = restrictedAreasGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 13. EEZ & TERRITORIAL SEA LAYER GROUP (Pan-India)
    // ──────────────────────────────────────────────────────────────────────────
    const eezGroup = L.layerGroup();
    // Continuous 12 NM Indian Territorial Sea Boundary Line
    const india12NM = L.polyline([
      [23.20, 68.20], [21.80, 68.80], [20.60, 69.80], [19.20, 72.40],
      [15.80, 73.30], [13.20, 74.40], [10.45, 75.72], [8.00, 77.30],
      [8.60, 78.40], [10.80, 80.10], [13.20, 80.50], [16.80, 82.60],
      [19.80, 86.40], [21.40, 87.80], [21.60, 88.80]
    ], {
      color: '#f59e0b', weight: 2, dashArray: '8, 6', opacity: 0.85
    }).bindPopup(`
      <div style="font-family: sans-serif; font-size: 11px;">
        <strong style="color: #d97706;">🇮🇳 INDIAN TERRITORIAL SEA LIMIT (12 NM)</strong><br/>
        <span>Sovereign Maritime Zone Baseline Boundary (UNCLOS 1982)</span><br/>
        <small style="color: #64748b;">Inshore artisanal craft priority zone</small>
      </div>
    `);
    eezGroup.addLayer(india12NM);

    // Indian EEZ (200 NM Outer Limit Line)
    const india200NM = L.polyline([
      [22.50, 66.50], [19.50, 68.50], [16.50, 70.00], [13.00, 71.50],
      [8.00, 74.00], [6.00, 77.50], [7.50, 81.50], [11.00, 83.50],
      [15.00, 85.50], [18.50, 88.00], [20.50, 89.50]
    ], {
      color: '#0284c7', weight: 2, dashArray: '10, 8', opacity: 0.75
    }).bindPopup('<b>🇮🇳 Indian Exclusive Economic Zone (200 NM Outer Limit)</b><br/>Sovereign rights for exploring and managing marine resources.');
    eezGroup.addLayer(india200NM);

    eezGroup.addTo(map);
    layersRef.current.eezGroup = eezGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 14. MARINE PROTECTED AREAS (MPA) GROUP across India
    // ──────────────────────────────────────────────────────────────────────────
    const mpaGroup = L.layerGroup();
    const mpas = [
      { name: '🌿 Gulf of Kutch Marine National Park', state: 'Gujarat', bounds: [[22.40, 69.20], [22.70, 69.80], [22.45, 70.10], [22.25, 69.40]], note: "India's 1st Marine National Park • Coral Reefs & Mangroves" },
      { name: '🌿 Malvan Marine Sanctuary', state: 'Maharashtra', bounds: [[15.98, 73.40], [16.12, 73.52], [16.05, 73.55], [15.95, 73.45]], note: 'Sindhudurg Coral Beds • Sea Anemone & Turtle Habitats' },
      { name: '🌿 Vembanad Ramsar Marine Protected Area', state: 'Kerala', bounds: [[9.85, 76.30], [9.95, 76.35], [9.80, 76.42], [9.70, 76.38]], note: 'Critical estuarine nursery & fish breeding zone. Mechanized trawling prohibited.' },
      { name: '🌿 Gulf of Mannar Marine Biosphere Reserve', state: 'Tamil Nadu', bounds: [[8.60, 78.10], [9.30, 79.25], [9.05, 79.45], [8.40, 78.35]], note: '21 Coral Islands • Dugong (Sea Cow) & Pearl Oyster Sanctuary' },
      { name: '🌿 Gahirmatha Marine Wildlife Sanctuary', state: 'Odisha', bounds: [[20.50, 86.80], [20.85, 87.15], [20.75, 87.35], [20.40, 87.00]], note: "World's Largest Olive Ridley Sea Turtle Mass Nesting Beach" },
      { name: '🌿 Sundarbans UNESCO Marine Biosphere Reserve', state: 'West Bengal', bounds: [[21.50, 88.00], [22.10, 88.90], [21.65, 89.10], [21.30, 88.20]], note: 'Mangrove Delta & Estuarine Royal Bengal Tiger Reserve' },
      { name: '🌿 Mahatma Gandhi Marine National Park (Wandoor)', state: 'Andaman & Nicobar', bounds: [[11.45, 92.50], [11.65, 92.65], [11.55, 92.70], [11.35, 92.55]], note: '15 Pristine Coral Islands • Hawksbill & Green Sea Turtles' }
    ];
    mpas.forEach((m) => {
      const poly = L.polygon(m.bounds, {
        color: '#10b981', weight: 2, fillColor: '#10b981', fillOpacity: 0.22, dashArray: '5, 5'
      }).bindPopup(`<b>${m.name}</b><br/><span>State: ${m.state}</span><br/><small style="color:#059669;font-weight:bold;">${m.note}</small>`);
      mpaGroup.addLayer(poly);
    });
    layersRef.current.mpaGroup = mpaGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 15. FISHING HARBOURS & MAJOR PORTS across India
    // ──────────────────────────────────────────────────────────────────────────
    const fishingHarboursGroup = L.layerGroup();
    const harbours = [
      // Gujarat
      { name: '⚓ VERAVAL FISHING HARBOUR', state: 'Gujarat', lat: 20.9000, lng: 70.3667, depth: '7.8m', info: 'Premier Indian Seafood Hub • 4,200 Mechanized Boats • Cold Storage Grid' },
      { name: '⚓ KANDLA / DEENDAYAL PORT', state: 'Gujarat', lat: 23.0033, lng: 70.2189, depth: '14.0m', info: 'Major Cargo Hub • Gulf of Kutch Maritime Gateway' },
      { name: '⚓ PORBANDAR DEEP SEA PORT', state: 'Gujarat', lat: 21.6417, lng: 69.6050, depth: '9.5m', info: 'All-Weather Deep Sea Fishing & Commercial Port' },
      { name: '⚓ OKHA FISHERY PORT', state: 'Gujarat', lat: 22.4667, lng: 69.0833, depth: '8.2m', info: 'Gulf of Kutch Western Gateway • Marine Pilot Station' },

      // Maharashtra
      { name: '⚓ SASSOON DOCK & MUMBAI PORT', state: 'Maharashtra', lat: 18.9167, lng: 72.8250, depth: '12.5m', info: 'Historic Fishery Harbour • 1,500 Trawlers • Daily Fish Auction' },
      { name: '⚓ JNPT NHAVA SHEVA HARBOUR', state: 'Maharashtra', lat: 18.9500, lng: 72.9500, depth: '15.0m', info: "India's Busiest Container Gateway • Modern Vessel Traffic Service (VTS)" },
      { name: '⚓ RATNAGIRI MIRKARWADA PORT', state: 'Maharashtra', lat: 16.9833, lng: 73.2833, depth: '6.5m', info: 'Major Konkan Deep-Sea Trawler Base • Processing Hub' },
      { name: '⚓ MALVAN COASTAL HARBOUR', state: 'Maharashtra', lat: 16.0500, lng: 73.4667, depth: '4.8m', info: 'Artisanal Fishery Base & Marine Wildlife Sanctuary Gateway' },

      // Goa
      { name: '⚓ MORMUGAO PORT (GOA)', state: 'Goa', lat: 15.4167, lng: 73.8000, depth: '14.4m', info: 'Major Port • Deep Natural Harbour • Zuari River Estuary' },
      { name: '⚓ PANAJI MANDOVI JETTY', state: 'Goa', lat: 15.5000, lng: 73.8333, depth: '5.2m', info: 'Central Goa Fishing Fleet & Navigation Base' },

      // Karnataka
      { name: '⚓ MALPE FISHERY HARBOUR', state: 'Karnataka', lat: 13.3500, lng: 74.7000, depth: '6.8m', info: "India's Premier Purse Seine & Multi-Day Trawler Base • 2,400 Vessels" },
      { name: '⚓ NEW MANGALORE MAJOR PORT', state: 'Karnataka', lat: 12.9250, lng: 74.8150, depth: '15.1m', info: 'All-Weather Deep Sea Major Port • Panambur Coast' },
      { name: '⚓ KARWAR BAITKHOL PORT', state: 'Karnataka', lat: 14.8167, lng: 74.1333, depth: '9.0m', info: 'Naval Base INS Kadamba & Mechanized Fishery Port' },

      // Kerala
      { name: '⚓ KOCHI FISHING HARBOUR (HQ)', state: 'Kerala', lat: 9.9667, lng: 76.2667, depth: '14.5m', info: '450 Mechanized Trawlers • 3 Ice Plants • Bunkering' },
      { name: '⚓ MUNAMBAM FISHING PORT', state: 'Kerala', lat: 10.1800, lng: 76.1600, depth: '6.2m', info: '320 Purse-seiners & Gillnetters • Auction Hall' },
      { name: '⚓ VIZHINJAM INTERNATIONAL SEAPORT', state: 'Kerala', lat: 8.3750, lng: 76.9950, depth: '20.0m', info: 'Deepwater Transshipment Mega Hub • Natural 20m Depth Contour' },
      { name: '⚓ NEENDAKARA PORT (KOLLAM)', state: 'Kerala', lat: 8.9350, lng: 76.5400, depth: '6.0m', info: 'Major Mechanized Trawler Hub • Ashtamudi Estuary Mouth' },
      { name: '⚓ BEYPORE FISHERY HARBOUR', state: 'Kerala', lat: 11.1667, lng: 75.8050, depth: '5.8m', info: 'Chaliyar River Estuary • Historic Marine Trading & Fishery Port' },
      { name: '🏖️ ALAPPUZHA COASTAL LANDING', state: 'Kerala', lat: 9.4900, lng: 76.3300, depth: '8.5m', info: 'Traditional Beach Landing & Thanguvallam Fleet' },

      // Tamil Nadu
      { name: '⚓ KASIMEDU FISHING HARBOUR (CHENNAI)', state: 'Tamil Nadu', lat: 13.1200, lng: 80.3000, depth: '7.5m', info: 'East Coast Premier Marine Landing Hub • 1,800 Trawlers' },
      { name: '⚓ CHENNAI MAJOR PORT', state: 'Tamil Nadu', lat: 13.0850, lng: 80.2980, depth: '17.0m', info: 'Oldest East Coast Major Port • 24 Automated Berths' },
      { name: '⚓ TUTICORIN V.O.C PORT', state: 'Tamil Nadu', lat: 8.7500, lng: 78.1800, depth: '14.2m', info: 'All-Weather Deep Sea Container Port • Pearl City Marine Base' },
      { name: '⚓ RAMESWARAM PAMBAN HARBOUR', state: 'Tamil Nadu', lat: 9.2833, lng: 79.3167, depth: '5.5m', info: 'Palk Bay Artisanal Fishing Fleet • Historic Marine Corridor' },
      { name: '⚓ KANYAKUMARI CHINNAMUTTAM HARBOUR', state: 'Tamil Nadu', lat: 8.0833, lng: 77.5667, depth: '6.2m', info: 'Cape Comorin Tri-Sea Fishing Base • Wadge Bank Fleet HQ' },

      // Andhra Pradesh
      { name: '⚓ VISAKHAPATNAM (VIZAG) MAJOR PORT', state: 'Andhra Pradesh', lat: 17.6833, lng: 83.2833, depth: '18.1m', info: 'Eastern Naval Command Base & Deepwater Major Cargo Port' },
      { name: '⚓ VIZAG FISHING HARBOUR', state: 'Andhra Pradesh', lat: 17.7000, lng: 83.3000, depth: '6.5m', info: '700 Mechanized Trawlers • Sona Boats Fleet • Cold Chain' },
      { name: '⚓ KAKINADA DEEPWATER PORT', state: 'Andhra Pradesh', lat: 16.9833, lng: 82.2667, depth: '14.5m', info: 'Deepwater & Anchorage Hub • Godavari Estuarine Fishery' },
      { name: '⚓ KRISHNAPATNAM PORT', state: 'Andhra Pradesh', lat: 14.2500, lng: 80.1333, depth: '18.5m', info: 'Modern Deepwater Port • South Andhra Marine Corridor' },

      // Odisha
      { name: '⚓ PARADIP MAJOR PORT', state: 'Odisha', lat: 20.2667, lng: 86.6667, depth: '17.5m', info: 'Major Bulk & Container Gateway • Mahanadi Estuary' },
      { name: '⚓ PARADIP FISHING HARBOUR', state: 'Odisha', lat: 20.2833, lng: 86.6833, depth: '6.2m', info: '850 Mechanized Trawlers • Major Eastern Marine Catch Hub' },
      { name: '⚓ DHAMRA DEEP PORT', state: 'Odisha', lat: 20.8167, lng: 86.9667, depth: '18.0m', info: 'All-Weather Deep Draft Port • Gahirmatha Border' },

      // West Bengal
      { name: '⚓ DIGHA (SANKARPUR) FISHERY HARBOUR', state: 'West Bengal', lat: 21.6333, lng: 87.5667, depth: '5.8m', info: 'Premier Marine Fish Landing Base • Hilsa & Pomfret Trade' },
      { name: '⚓ HALDIA DOCK COMPLEX', state: 'West Bengal', lat: 22.0167, lng: 88.0667, depth: '12.5m', info: 'Major Riverine Cargo Gateway • Hooghly River Channel' },
      { name: '⚓ FRASERGANJ FISHING HARBOUR', state: 'West Bengal', lat: 21.5833, lng: 88.2500, depth: '4.8m', info: 'Sundarbans Estuarine Marine Fishery Center' },

      // Island Territories
      { name: '⚓ PORT BLAIR HADDO HARBOUR', state: 'Andaman & Nicobar', lat: 11.6667, lng: 92.7333, depth: '12.0m', info: 'Strategic Andaman Marine Hub • Deep Oceanic Fishery Base' },
      { name: '⚓ KAVARATTI LAGOON HARBOUR', state: 'Lakshadweep', lat: 10.5667, lng: 72.6333, depth: '4.5m', info: 'Coral Atoll Fishery Hub • Pole-and-Line Skipjack Fleet' }
    ];
    harbours.forEach((h) => {
      const icon = createNauticalIcon('#0284c7', h.name, 'rect');
      const marker = L.marker([h.lat, h.lng], { icon }).bindPopup(`
        <b>${h.name}</b><br/>
        <span>State: <b>${h.state}</b> • Depth: <b>${h.depth}</b></span><br/>
        <span>${h.info}</span>
      `);
      fishingHarboursGroup.addLayer(marker);
    });
    fishingHarboursGroup.addTo(map);
    layersRef.current.fishingHarboursGroup = fishingHarboursGroup;

    // ──────────────────────────────────────────────────────────────────────────
    // 16. VESSELS AIS TRAFFIC LAYER GROUP across Indian Waters
    // ──────────────────────────────────────────────────────────────────────────
    const vesselsAisGroup = L.layerGroup();
    const aisVessels = [
      // Indian Coast Guard Cutters
      { name: 'ICGS SAMARTH (CG-11)', region: 'West Coast / Mumbai', type: 'coast_guard', lat: 18.8500, lng: 72.6000, speed: '22.0 kts', cog: '310° NW', mmsi: '419000101' },
      { name: 'ICGS VIJIT (CG-31)', region: 'North-West / Gujarat', type: 'coast_guard', lat: 20.8000, lng: 70.1500, speed: '19.5 kts', cog: '280° W', mmsi: '419000102' },
      { name: 'ICGS VARUNA (CG-34)', region: 'South-West / Kochi', type: 'coast_guard', lat: 9.9150, lng: 76.1200, speed: '21.5 kts', cog: '045° NE', mmsi: '419000112' },
      { name: 'ICGS RAJDOOT (CG-45)', region: 'Coromandel / Chennai', type: 'coast_guard', lat: 13.1000, lng: 80.4000, speed: '20.0 kts', cog: '160° SSE', mmsi: '419000118' },
      { name: 'ICGS SHAUNAK (CG-15)', region: 'East Coast / Vizag', type: 'coast_guard', lat: 17.6500, lng: 83.4500, speed: '18.4 kts', cog: '030° NNE', mmsi: '419000124' },
      { name: 'ICGS SUJAY (CG-18)', region: 'North-East / Paradip', type: 'coast_guard', lat: 20.1500, lng: 86.8500, speed: '21.0 kts', cog: '070° ENE', mmsi: '419000130' },

      // Commercial Cargo & Tankers
      { name: 'M/T DESH SHANTI (Crude Tanker)', region: 'Gulf of Kutch', type: 'tanker', lat: 21.9000, lng: 69.2000, speed: '13.8 kts', cog: '340° NNW', mmsi: '419004550' },
      { name: 'M/V SAGAR RATNA (Tanker)', region: 'Kochi Approach', type: 'tanker', lat: 9.9950, lng: 76.0200, speed: '12.4 kts', cog: '315° NW', mmsi: '419004521' },
      { name: 'CONTAINER SHIP CHENNAI EXPRESS', region: 'Chennai Corridor', type: 'cargo', lat: 13.0500, lng: 80.3500, speed: '16.5 kts', cog: '275° W', mmsi: '419003888' },
      { name: 'BULK CARRIER ODISHA PRIDE', region: 'Paradip Roadstead', type: 'cargo', lat: 20.2000, lng: 86.7500, speed: '11.2 kts', cog: '190° S', mmsi: '419003895' },

      // Mechanized Fishing Vessels
      { name: 'F/V SAGAR KRIPA (Veraval Trawler)', region: 'Gujarat Coast', type: 'fishing', lat: 20.8200, lng: 70.2800, speed: '7.2 kts', cog: '210° SSW', mmsi: '419008701' },
      { name: 'F/V MAHALAKSHMI (Mumbai Trawler)', region: 'Maharashtra Coast', type: 'fishing', lat: 18.8800, lng: 72.7400, speed: '8.0 kts', cog: '260° W', mmsi: '419008715' },
      { name: 'F/V SEA QUEEN (Malpe Purse-Seiner)', region: 'Karnataka Coast', type: 'fishing', lat: 13.3100, lng: 74.6200, speed: '9.4 kts', cog: '275° W', mmsi: '419008722' },
      { name: 'F/V MATSYA-04 (MMSI: 419001248)', region: 'Kerala Coast', type: 'fishing', lat: 9.9400, lng: 76.1800, speed: '9.8 kts', cog: '255° WSW', mmsi: '419001248' },
      { name: 'F/V VELANKANNI (Tuticorin Liner)', region: 'Gulf of Mannar', type: 'fishing', lat: 8.6800, lng: 78.2500, speed: '8.5 kts', cog: '140° SE', mmsi: '419008735' },
      { name: 'F/V GANAPATHI (Vizag Deep Trawler)', region: 'Andhra Coast', type: 'fishing', lat: 17.6200, lng: 83.3500, speed: '7.8 kts', cog: '115° ESE', mmsi: '419008748' },
      { name: 'F/V BANGA SOUNDARI (Digha Trawler)', region: 'West Bengal Coast', type: 'fishing', lat: 21.5500, lng: 87.6500, speed: '8.2 kts', cog: '165° SSE', mmsi: '419008760' }
    ];
    aisVessels.forEach((v) => {
      const iconColor = v.type === 'coast_guard' ? '#3b82f6' : v.type === 'tanker' ? '#f59e0b' : v.type === 'cargo' ? '#8b5cf6' : '#10b981';
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
          <span>MMSI: ${v.mmsi} • Sector: <b>${v.region}</b></span><br/>
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

    // 200m Continental Shelf Break (West & East Indian Coastlines)
    const shelfBreakGroup = L.layerGroup();
    const westShelf = L.polyline([
      [22.20, 68.20], [20.50, 69.30], [19.20, 71.20], [17.00, 72.20],
      [14.50, 73.50], [12.50, 74.20], [10.55, 75.40], [9.85, 75.68],
      [8.00, 76.80], [7.50, 77.50]
    ], {
      color: '#0284c7', weight: 2, dashArray: '5, 8', opacity: 0.85
    }).bindPopup('<b>🌊 West Indian 200m Continental Shelf Margin</b><br/>High upwelling & primary pelagic upwelling front.');
    shelfBreakGroup.addLayer(westShelf);

    const eastShelf = L.polyline([
      [7.50, 77.50], [8.50, 78.60], [10.50, 80.20], [13.20, 80.70],
      [16.50, 82.80], [17.80, 84.00], [19.80, 86.80], [21.00, 88.50]
    ], {
      color: '#0284c7', weight: 2, dashArray: '5, 8', opacity: 0.85
    }).bindPopup('<b>🌊 East Indian 200m Continental Shelf Margin</b><br/>Bay of Bengal deep slope divergence zone.');
    shelfBreakGroup.addLayer(eastShelf);

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

  const handleRegionChange = (sectorId) => {
    setSelectedRegionId(sectorId);
    const found = INDIA_COASTAL_SECTORS.find((s) => s.id === sectorId);
    if (found && mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([found.lat, found.lng], found.zoom, { duration: 1.4 });
      setMouseCoords({ lat: found.lat, lng: found.lng });
      if (onFixCoordinates) {
        onFixCoordinates({
          lat: found.lat,
          lng: found.lng,
          distKm: '0.0',
          estDepth: 35,
          name: found.name
        });
      }
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
          const targetZoom = result.zoom || 13;
          map.flyTo([result.lat, result.lng], targetZoom, { duration: 1.4 });

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
              <div>Datum: <b>WGS 84 • INCOIS Hydro</b></div>
              <div>Sounded Depth: <b>~${estDepth} m</b></div>
            </div>
          `).openPopup();

          userMarker.addTo(map);
          layersRef.current.userClickMarker = userMarker;
          setClickPin({ lat: result.lat, lng: result.lng, distKm, distNm, bearing, estDepth });

          if (onFixCoordinates) {
            onFixCoordinates({ lat: result.lat, lng: result.lng, distKm, estDepth, name: result.name });
          }

          setSearchFeedback(`Fixed: ${result.name.slice(0, 18)}`);
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

          {/* Indian Coastal Region Selector */}
          <div className="map-region-selector" title="Switch Indian Coastal Region">
            <span className="region-selector-icon">🇮🇳</span>
            <select
              value={selectedRegionId}
              onChange={(e) => handleRegionChange(e.target.value)}
              className="region-select-input"
            >
              {INDIA_COASTAL_SECTORS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.shortName} — {s.name}
                </option>
              ))}
            </select>
          </div>

          <form onSubmit={handleSearchLocation} className="map-coastal-search-bar" title="Search harbour, port, buoy or coordinates">
            <Icon name="Search" size={13} className="search-bar-icon" />
            <input
              type="text"
              className="search-bar-input"
              placeholder="Search Indian port, buoy, coords (e.g. Veraval, Mumbai, 18.9, 72.8)..."
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
            data-testid="map-zoom-in"
          >
            +
          </button>
          <button
            onClick={() => mapInstanceRef.current?.zoomOut()}
            title="Zoom Out"
            data-testid="map-zoom-out"
          >
            −
          </button>
          <button
            onClick={() => {
              const curSector = INDIA_COASTAL_SECTORS.find((s) => s.id === selectedRegionId) || INDIA_COASTAL_SECTORS[0];
              mapInstanceRef.current?.setView([curSector.lat, curSector.lng], curSector.zoom);
            }}
            title="Recenter on Coastal Area"
            data-testid="map-recenter"
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
            data-testid="map-fullscreen-toggle"
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
