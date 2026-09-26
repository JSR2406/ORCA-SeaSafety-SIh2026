'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import Card from '../components/Card';
import MarineMap from '../components/DynamicMarineMap';
import Badge from '../components/Badge';
import SectionHeader from '../components/SectionHeader';
import Icon from '../components/Icon';
import { useLanguage } from '../context/LanguageContext';
import { useBackend } from '../context/BackendContext';
import { getMarineBriefing, analyzeRoute } from '../services/apiClient';

const VESSEL_SPECS = {
  'trawler': { name: 'Inshore Motorized Trawler (< 15m)', speedKts: 10.4, fuelPerHour: 28.5, maxDraft: '2.8m' },
  'gillnetter': { name: 'Deep Sea Gillnetter (15-24m)', speedKts: 12.2, fuelPerHour: 36.0, maxDraft: '3.4m' },
  'catamaran': { name: 'Traditional Motorized Catamaran (< 10m)', speedKts: 8.5, fuelPerHour: 14.0, maxDraft: '1.2m' },
  'research': { name: 'Scientific Research Vessel (NIOS)', speedKts: 14.0, fuelPerHour: 55.0, maxDraft: '4.8m' }
};

export const HARBOURS = {
  'Kochi Fishing Harbour (HQ)': {
    id: 'kochi',
    name: 'Kochi Fishing Harbour (HQ)',
    fullName: "Kochi Fishing Harbour Base (HQ) • 09°58'N, 076°16'E (Kerala)",
    lat: 9.9667,
    lon: 76.2400,
    depth: '12m'
  },
  'Veraval Fishery Harbour': {
    id: 'veraval',
    name: 'Veraval Fishery Harbour',
    fullName: "Veraval Fishery Harbour • 20°54'N, 070°22'E (Gujarat)",
    lat: 20.9000,
    lon: 70.3667,
    depth: '8m'
  },
  'Porbandar All-Weather Port': {
    id: 'porbandar',
    name: 'Porbandar All-Weather Port',
    fullName: "Porbandar Port • 21°38'N, 069°36'E (Gujarat)",
    lat: 21.6333,
    lon: 69.6000,
    depth: '11m'
  },
  'Mumbai Sassoon Dock': {
    id: 'mumbai',
    name: 'Mumbai Sassoon Dock',
    fullName: "Mumbai Sassoon Dock • 18°55'N, 072°50'E (Maharashtra)",
    lat: 18.9167,
    lon: 72.8250,
    depth: '9m'
  },
  'Mormugao Deepwater Port': {
    id: 'mormugao',
    name: 'Mormugao Deepwater Port',
    fullName: "Mormugao Deepwater Port • 15°25'N, 073°48'E (Goa)",
    lat: 15.4167,
    lon: 73.8050,
    depth: '14m'
  },
  'Malpe Fishery Harbour': {
    id: 'malpe',
    name: 'Malpe Fishery Harbour',
    fullName: "Malpe Fishery Harbour • 13°21'N, 074°42'E (Karnataka)",
    lat: 13.3520,
    lon: 74.7010,
    depth: '7m'
  },
  'Munambam Fishing Port': {
    id: 'munambam',
    name: 'Munambam Fishing Port',
    fullName: "Munambam Fishing Port • 10°11'N, 076°10'E (Kerala)",
    lat: 10.1833,
    lon: 76.1667,
    depth: '10m'
  },
  'Alappuzha Coastal Landing': {
    id: 'alappuzha',
    name: 'Alappuzha Coastal Landing',
    fullName: "Alappuzha Coastal Landing • 09°29'N, 076°20'E (Kerala)",
    lat: 9.4833,
    lon: 76.3333,
    depth: '8m'
  },
  'Chellanam Fishing Harbour': {
    id: 'chellanam',
    name: 'Chellanam Fishing Harbour',
    fullName: "Chellanam Fishing Harbour • 09°48'N, 076°16'E (Kerala)",
    lat: 9.8000,
    lon: 76.2700,
    depth: '9m'
  },
  'Kollam / Neendakara Port': {
    id: 'kollam',
    name: 'Kollam / Neendakara Port',
    fullName: "Kollam / Neendakara Port • 08°56'N, 076°32'E (Kerala)",
    lat: 8.9333,
    lon: 76.5333,
    depth: '14m'
  },
  'Tuticorin V.O.C Port': {
    id: 'tuticorin',
    name: 'Tuticorin V.O.C Port',
    fullName: "Tuticorin V.O.C Port • 08°45'N, 078°11'E (Tamil Nadu)",
    lat: 8.7500,
    lon: 78.1800,
    depth: '13m'
  },
  'Chennai Fishing Harbour': {
    id: 'chennai',
    name: 'Chennai Fishing Harbour',
    fullName: "Chennai Fishery Harbour • 13°05'N, 080°18'E (Tamil Nadu)",
    lat: 13.0900,
    lon: 80.3000,
    depth: '10m'
  },
  'Visakhapatnam Fishing Port': {
    id: 'visakhapatnam',
    name: 'Visakhapatnam Fishing Port',
    fullName: "Visakhapatnam Fishing Port • 17°41'N, 083°18'E (Andhra Pradesh)",
    lat: 17.6900,
    lon: 83.3000,
    depth: '12m'
  },
  'Paradip Port Trust': {
    id: 'paradip',
    name: 'Paradip Port Trust',
    fullName: "Paradip Port Trust • 20°15'N, 086°41'E (Odisha)",
    lat: 20.2600,
    lon: 86.6800,
    depth: '14m'
  },
  'Digha Fishery Terminal': {
    id: 'digha',
    name: 'Digha Fishery Terminal',
    fullName: "Digha Fishery Terminal • 21°38'N, 087°33'E (West Bengal)",
    lat: 21.6300,
    lon: 87.5500,
    depth: '6m'
  },
  'Port Blair Harbour': {
    id: 'portblair',
    name: 'Port Blair Harbour',
    fullName: "Port Blair Harbour • 11°40'N, 092°44'E (Andaman & Nicobar)",
    lat: 11.6700,
    lon: 92.7400,
    depth: '15m'
  }
};

export const DESTINATIONS = {
  'PFZ-01': {
    id: 'PFZ-01',
    name: 'PFZ-01: Kochi Offshore Front (14.2 km SW • Catch Score 92)',
    shortName: 'PFZ-01: Kochi Offshore Front',
    lat: 9.8700,
    lon: 76.1400,
    depth: '42m'
  },
  'PFZ-02': {
    id: 'PFZ-02',
    name: 'PFZ-02: Vypin Deep Upwelling (21.5 km W • Catch Score 88)',
    shortName: 'PFZ-02: Vypin Deep Upwelling',
    lat: 10.0750,
    lon: 75.9700,
    depth: '65m'
  },
  'PFZ-03': {
    id: 'PFZ-03',
    name: 'PFZ-03: Alappuzha Shelf Margin (31.8 km SSW • Catch Score 74)',
    shortName: 'PFZ-03: Alappuzha Shelf Margin',
    lat: 9.4000,
    lon: 76.2000,
    depth: '52m'
  },
  'PFZ-04': {
    id: 'PFZ-04',
    name: 'PFZ-04: Chellanam Inshore Bank (12.8 km W • Catch Score 81)',
    shortName: 'PFZ-04: Chellanam Inshore Bank',
    lat: 9.8000,
    lon: 76.1200,
    depth: '35m'
  },
  'PFZ-05': {
    id: 'PFZ-05',
    name: 'PFZ-05: Chavakkad Pelagic Front (Catch Score 86)',
    shortName: 'PFZ-05: Chavakkad Pelagic Front',
    lat: 10.5500,
    lon: 75.8500,
    depth: '70m'
  },
  'PFZ-GJ-01': {
    id: 'PFZ-GJ-01',
    name: 'PFZ-GJ-01: Veraval Offshore Shelf (Catch Score 94)',
    shortName: 'PFZ-GJ-01: Veraval Offshore',
    lat: 20.7200,
    lon: 69.9500,
    depth: '45m'
  },
  'PFZ-MH-01': {
    id: 'PFZ-MH-01',
    name: 'PFZ-MH-01: Ratnagiri Upwelling Front (Catch Score 91)',
    shortName: 'PFZ-MH-01: Ratnagiri Front',
    lat: 17.0200,
    lon: 72.8500,
    depth: '52m'
  },
  'PFZ-KA-01': {
    id: 'PFZ-KA-01',
    name: 'PFZ-KA-01: Malpe Continental Shelf Edge (Catch Score 89)',
    shortName: 'PFZ-KA-01: Malpe Shelf',
    lat: 13.3000,
    lon: 74.2000,
    depth: '60m'
  },
  'PFZ-TN-01': {
    id: 'PFZ-TN-01',
    name: 'PFZ-TN-01: Wadge Bank Pelagic Front (Catch Score 95)',
    shortName: 'PFZ-TN-01: Wadge Bank',
    lat: 7.8500,
    lon: 77.5500,
    depth: '48m'
  },
  'PFZ-AP-01': {
    id: 'PFZ-AP-01',
    name: 'PFZ-AP-01: Godavari Estuary Plume (Catch Score 90)',
    shortName: 'PFZ-AP-01: Godavari Plume',
    lat: 16.7800,
    lon: 82.5200,
    depth: '55m'
  },
  'PFZ-OD-01': {
    id: 'PFZ-OD-01',
    name: 'PFZ-OD-01: Paradip Shelf Break Front (Catch Score 92)',
    shortName: 'PFZ-OD-01: Paradip Shelf',
    lat: 20.1200,
    lon: 86.9500,
    depth: '62m'
  },
  'PFZ-WB-01': {
    id: 'PFZ-WB-01',
    name: 'PFZ-WB-01: Sandheads Oceanic Convergence (Catch Score 88)',
    shortName: 'PFZ-WB-01: Sandheads Plume',
    lat: 21.2500,
    lon: 88.2500,
    depth: '35m'
  },
  'Munambam': {
    id: 'Munambam',
    name: 'Munambam Harbour Alternate Refuge',
    shortName: 'Munambam Refuge Harbour',
    lat: 10.1833,
    lon: 76.1667,
    depth: '10m'
  },
  'Kochi': {
    id: 'Kochi',
    name: 'Kochi Fishing Harbour (Return Port)',
    shortName: 'Kochi Fishing Harbour',
    lat: 9.9667,
    lon: 76.2400,
    depth: '12m'
  }
};

function calculateHaversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371.0;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function formatNauticalCoord(lat, lon) {
  const latDeg = Math.floor(Math.abs(lat));
  const latMin = ((Math.abs(lat) - latDeg) * 60).toFixed(1);
  const latStr = `${String(latDeg).padStart(2, '0')}°${latMin.padStart(4, '0')}'${lat >= 0 ? 'N' : 'S'}`;

  const lonDeg = Math.floor(Math.abs(lon));
  const lonMin = ((Math.abs(lon) - lonDeg) * 60).toFixed(1);
  const lonStr = `${String(lonDeg).padStart(3, '0')}°${lonMin.padStart(4, '0')}'${lon >= 0 ? 'E' : 'W'}`;

  return { latStr, lonStr };
}

function generateDynamicRoutes(originInfo, destInfo, currentVessel) {
  const oLat = originInfo.lat;
  const oLon = originInfo.lon;
  const dLat = destInfo.lat;
  const dLon = destInfo.lon;

  const directKm = calculateHaversineKm(oLat, oLon, dLat, dLon);
  const directNm = directKm / 1.852;

  // Check if direct path passes through or near NAVAREA VIII Sector Bravo (approx 9.88-9.98 N, 76.17-76.28 E)
  const midLat = (oLat + dLat) / 2;
  const midLon = (oLon + dLon) / 2;
  const nearNaval =
    (midLat >= 9.85 && midLat <= 10.02 && midLon >= 76.14 && midLon <= 76.30) ||
    (oLat >= 9.88 && oLat <= 9.98 && oLon >= 76.17 && oLon <= 76.28);

  const oCoordFmt = formatNauticalCoord(oLat, oLon);
  const dCoordFmt = formatNauticalCoord(dLat, dLon);

  // --- Route B: Northwest / Fairway Certified Channel (Recommended) ---
  const bEgressLat = oLat + (dLat > oLat ? 0.02 : -0.015);
  const bEgressLon = oLon - 0.08;
  const bEgressFmt = formatNauticalCoord(bEgressLat, bEgressLon);

  // Push safe transit lane west of the naval box (lon <= 76.08)
  const bMidLat = (oLat + dLat) / 2 + 0.01;
  const bMidLon = Math.min(oLon, dLon, 76.08) - 0.03;
  const bMidFmt = formatNauticalCoord(bMidLat, bMidLon);

  const bAppLat = dLat + (oLat > dLat ? 0.015 : -0.015);
  const bAppLon = dLon - 0.02;
  const bAppFmt = formatNauticalCoord(bAppLat, bAppLon);

  const bWaypoints = [
    {
      name: `WP-01: ${originInfo.name}`,
      latNum: oLat,
      lonNum: oLon,
      lat: oCoordFmt.latStr,
      lon: oCoordFmt.lonStr,
      depth: originInfo.depth || '12m',
      status: 'Departure Harbour'
    },
    {
      name: 'WP-02: Outer Fairway Channel Buoy',
      latNum: bEgressLat,
      lonNum: bEgressLon,
      lat: bEgressFmt.latStr,
      lon: bEgressFmt.lonStr,
      depth: '24m',
      status: 'Nav Buoy'
    },
    {
      name: 'WP-03: Coastal Transit Deep Channel',
      latNum: bMidLat,
      lonNum: bMidLon,
      lat: bMidFmt.latStr,
      lon: bMidFmt.lonStr,
      depth: '42m',
      status: 'Safe Channel'
    },
    {
      name: `WP-04: ${destInfo.shortName || destInfo.name} Approach`,
      latNum: bAppLat,
      lonNum: bAppLon,
      lat: bAppFmt.latStr,
      lon: bAppFmt.lonStr,
      depth: '48m',
      status: 'Corridor Clear'
    },
    {
      name: `WP-05: ${destInfo.shortName || destInfo.name} Entry`,
      latNum: dLat,
      lonNum: dLon,
      lat: dCoordFmt.latStr,
      lon: dCoordFmt.lonStr,
      depth: destInfo.depth || '45m',
      status: 'Destination'
    }
  ];

  let bDistKm = 0;
  for (let i = 0; i < bWaypoints.length - 1; i++) {
    bDistKm += calculateHaversineKm(
      bWaypoints[i].latNum,
      bWaypoints[i].lonNum,
      bWaypoints[i + 1].latNum,
      bWaypoints[i + 1].lonNum
    );
  }
  const bDistNm = bDistKm / 1.852;
  const bDurH = bDistNm / currentVessel.speedKts;
  const bDurStr = `${Math.floor(bDurH)}h ${Math.round((bDurH - Math.floor(bDurH)) * 60)}m`;
  const bFuel = Math.round(bDurH * currentVessel.fuelPerHour);

  // --- Route A: Direct Rhumb Line (Shortest - High Hazard) ---
  const aMidFmt = formatNauticalCoord(midLat, midLon);
  const aWaypoints = [
    {
      name: `WP-01: ${originInfo.name}`,
      latNum: oLat,
      lonNum: oLon,
      lat: oCoordFmt.latStr,
      lon: oCoordFmt.lonStr,
      depth: originInfo.depth || '12m',
      status: 'Departure Harbour'
    },
    {
      name: nearNaval ? 'WP-02: Naval Sector Edge Cross' : 'WP-02: Direct Mid-Track',
      latNum: midLat,
      lonNum: midLon,
      lat: aMidFmt.latStr,
      lon: aMidFmt.lonStr,
      depth: '30m',
      status: nearNaval ? 'RESTRICTED HAZARD' : 'Swell Convergence'
    },
    {
      name: `WP-03: ${destInfo.shortName || destInfo.name} Entry`,
      latNum: dLat,
      lonNum: dLon,
      lat: dCoordFmt.latStr,
      lon: dCoordFmt.lonStr,
      depth: destInfo.depth || '45m',
      status: 'Destination'
    }
  ];

  const aDistKm = directKm;
  const aDistNm = directNm;
  const aDurH = aDistNm / currentVessel.speedKts;
  const aDurStr = `${Math.floor(aDurH)}h ${Math.round((aDurH - Math.floor(aDurH)) * 60)}m`;
  const aFuel = Math.round(aDurH * currentVessel.fuelPerHour);

  // --- Route C: Southern / Offshore Deep Detour (Alternative) ---
  const cEgressLat = oLat - 0.03;
  const cEgressLon = oLon - 0.14;
  const cEgressFmt = formatNauticalCoord(cEgressLat, cEgressLon);

  const cMidLat = dLat - 0.02;
  const cMidLon = Math.min(oLon, dLon) - 0.12;
  const cMidFmt = formatNauticalCoord(cMidLat, cMidLon);

  const cWaypoints = [
    {
      name: `WP-01: ${originInfo.name}`,
      latNum: oLat,
      lonNum: oLon,
      lat: oCoordFmt.latStr,
      lon: oCoordFmt.lonStr,
      depth: originInfo.depth || '12m',
      status: 'Departure Harbour'
    },
    {
      name: 'WP-02: Seaward Deep-Shelf Egress',
      latNum: cEgressLat,
      lonNum: cEgressLon,
      lat: cEgressFmt.latStr,
      lon: cEgressFmt.lonStr,
      depth: '52m',
      status: 'Clear Deep Water'
    },
    {
      name: 'WP-03: Offshore Bathymetric Corridor',
      latNum: cMidLat,
      lonNum: cMidLon,
      lat: cMidFmt.latStr,
      lon: cMidFmt.lonStr,
      depth: '64m',
      status: 'Clear'
    },
    {
      name: `WP-04: ${destInfo.shortName || destInfo.name} Entry`,
      latNum: dLat,
      lonNum: dLon,
      lat: dCoordFmt.latStr,
      lon: dCoordFmt.lonStr,
      depth: destInfo.depth || '45m',
      status: 'Destination'
    }
  ];

  let cDistKm = 0;
  for (let i = 0; i < cWaypoints.length - 1; i++) {
    cDistKm += calculateHaversineKm(
      cWaypoints[i].latNum,
      cWaypoints[i].lonNum,
      cWaypoints[i + 1].latNum,
      cWaypoints[i + 1].lonNum
    );
  }
  const cDistNm = cDistKm / 1.852;
  const cDurH = cDistNm / currentVessel.speedKts;
  const cDurStr = `${Math.floor(cDurH)}h ${Math.round((cDurH - Math.floor(cDurH)) * 60)}m`;
  const cFuel = Math.round(cDurH * currentVessel.fuelPerHour);

  return [
    {
      id: 'route-b',
      name: 'Route B — Northwest Fairway (Recommended)',
      distance: `${bDistKm.toFixed(1)} km (${bDistNm.toFixed(1)} NM)`,
      distanceKm: Number(bDistKm.toFixed(1)),
      distanceNm: Number(bDistNm.toFixed(1)),
      duration: `${bDurStr} @ ${currentVessel.speedKts} kts`,
      durationStr: bDurStr,
      fuelEstimate: `${bFuel} Litres HSD`,
      fuelLitres: bFuel,
      risk: 'LOW',
      riskScore: 0.22,
      color: '#10B981',
      highWaveAreas: 0,
      restrictedZones: 0,
      waypoints: bWaypoints,
      summary: `Certified navigational channel routing from ${originInfo.name} to ${destInfo.shortName || destInfo.name}, bypassing shallow breakers and maintaining full safety clearance from naval sectors.`
    },
    {
      id: 'route-a',
      name: 'Route A — Direct Line (Shortest)',
      distance: `${aDistKm.toFixed(1)} km (${aDistNm.toFixed(1)} NM)`,
      distanceKm: Number(aDistKm.toFixed(1)),
      distanceNm: Number(aDistNm.toFixed(1)),
      duration: `${aDurStr} @ ${currentVessel.speedKts} kts`,
      durationStr: aDurStr,
      fuelEstimate: `${aFuel} Litres HSD`,
      fuelLitres: aFuel,
      risk: nearNaval ? 'HIGH' : 'MODERATE',
      riskScore: nearNaval ? 0.78 : 0.46,
      color: '#EF4444',
      highWaveAreas: 1,
      restrictedZones: nearNaval ? 1 : 0,
      waypoints: aWaypoints,
      summary: `Rhumb-line direct track saving ${Math.max(1, (bDistKm - aDistKm)).toFixed(1)} km, but ${nearNaval ? 'clips the NAVAREA VIII Sector Bravo naval firing perimeter and ' : ''}intersects coastal swell convergence breakers. NOT RECOMMENDED.`
    },
    {
      id: 'route-c',
      name: 'Route C — Southern Offshore Detour (Alternative)',
      distance: `${cDistKm.toFixed(1)} km (${cDistNm.toFixed(1)} NM)`,
      distanceKm: Number(cDistKm.toFixed(1)),
      distanceNm: Number(cDistNm.toFixed(1)),
      duration: `${cDurStr} @ ${currentVessel.speedKts} kts`,
      durationStr: cDurStr,
      fuelEstimate: `${cFuel} Litres HSD`,
      fuelLitres: cFuel,
      risk: 'LOW',
      riskScore: 0.16,
      color: '#0099DD',
      highWaveAreas: 0,
      restrictedZones: 0,
      waypoints: cWaypoints,
      summary: `Deep-water offshore shelf transit corridor giving widest safety buffer (> 10 km) clear of all naval exercises, sandbars, and nearshore traffic. Consumes approx ${Math.max(1, (cFuel - bFuel))}L more diesel.`
    }
  ];
}

export default function RoutePlannerPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const { isBackendLive, latencyMs } = useBackend();
  const [selectedRouteId, setSelectedRouteId] = useState('route-b');
  const [origin, setOrigin] = useState('Kochi Fishing Harbour (HQ)');
  const [destination, setDestination] = useState('PFZ-01');
  const [customDestCoord, setCustomDestCoord] = useState(null);
  const [vesselKey, setVesselKey] = useState('trawler');
  const [exportNotice, setExportNotice] = useState(null);
  const [isCalculating, setIsCalculating] = useState(false);
  const [liveBriefing, setLiveBriefing] = useState(null);

  const currentVessel = VESSEL_SPECS[vesselKey] || VESSEL_SPECS.trawler;

  // Read destination coordinates from query parameters if linked from Dashboard / Fishing
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const lat = params.get('destLat');
      const lon = params.get('destLon');
      const destName = params.get('destName');
      const dest = params.get('dest');
      if (lat && lon) {
        const parsedLat = parseFloat(lat);
        const parsedLon = parseFloat(lon);
        const nameStr = destName || `PFZ Target (${parsedLat.toFixed(2)}°N, ${parsedLon.toFixed(2)}°E)`;
        setCustomDestCoord({
          id: 'custom-target',
          name: nameStr,
          shortName: nameStr,
          lat: parsedLat,
          lon: parsedLon,
          depth: '45m'
        });
        setDestination('custom-target');
      } else if (destName) {
        setDestination(destName);
      } else if (dest) {
        setDestination(dest);
      }
    }
  }, []);

  // Determine Origin Info
  const originInfo = useMemo(() => {
    return HARBOURS[origin] || HARBOURS['Kochi Fishing Harbour (HQ)'];
  }, [origin]);

  // Determine Destination Info
  const destInfo = useMemo(() => {
    if (destination === 'custom-target' && customDestCoord) {
      return customDestCoord;
    }
    return DESTINATIONS[destination] || customDestCoord || DESTINATIONS['PFZ-01'];
  }, [destination, customDestCoord]);

  // Dynamically calculate routes whenever origin, destination, or vessel changes
  const calculatedRoutes = useMemo(() => {
    return generateDynamicRoutes(originInfo, destInfo, currentVessel);
  }, [originInfo, destInfo, currentVessel]);

  const currentRoute = useMemo(() => {
    return calculatedRoutes.find((r) => r.id === selectedRouteId) || calculatedRoutes[0];
  }, [calculatedRoutes, selectedRouteId]);

  const handleRecalculate = async () => {
    setIsCalculating(true);
    try {
      const briefing = await getMarineBriefing({ lat: originInfo.lat, lon: originInfo.lon, distanceKm: 50 });
      const analysis = await analyzeRoute({
        originLat: originInfo.lat,
        originLon: originInfo.lon,
        destinationLat: destInfo.lat,
        destinationLon: destInfo.lon,
        waypoints: currentRoute.waypoints,
        vesselType: vesselKey
      });

      setLiveBriefing({
        isLive: briefing.isLive || analysis.isLive,
        compositeScore: analysis.analysis?.risk_assessment?.overall_score || briefing.composite_score || 0.24,
        verdict:
          analysis.analysis?.risk_assessment?.reasoning ||
          briefing.verdict ||
          `Optimal track evaluated from ${originInfo.name} to ${destInfo.shortName || destInfo.name}. Conditions within certified operational limits.`,
        timestamp: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) + ' IST'
      });
      setSelectedRouteId('route-b');
    } catch (err) {
      console.error('Recalculation error:', err);
    } finally {
      setIsCalculating(false);
    }
  };

  const handleExportGps = () => {
    // Generate valid GPX XML for marine GPS chartplotters
    const gpxContent = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="ORCA Intelligent Marine Navigational Engine" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${currentRoute.name}</name>
    <desc>ORCA Navigational Track from ${originInfo.name} to ${destInfo.name}</desc>
    <time>${new Date().toISOString()}</time>
  </metadata>
  <rte>
    <name>${currentRoute.name}</name>
    <cmt>Distance: ${currentRoute.distance} | Duration: ${currentRoute.duration} | Fuel: ${currentRoute.fuelEstimate}</cmt>
    ${currentRoute.waypoints
      .map(
        (wp) => `
    <rtept lat="${wp.latNum.toFixed(4)}" lon="${wp.lonNum.toFixed(4)}">
      <name>${wp.name}</name>
      <desc>${wp.status} • Sounding Depth: ${wp.depth}</desc>
    </rtept>`
      )
      .join('')}
  </rte>
</gpx>`;

    const blob = new Blob([gpxContent], { type: 'application/gpx+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const cleanOrigin = originInfo.id || 'origin';
    const cleanDest = destInfo.id || 'dest';
    link.download = `ORCA_NAV_${selectedRouteId.toUpperCase()}_${cleanOrigin}_to_${cleanDest}.gpx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    setExportNotice(
      `Route ${selectedRouteId.toUpperCase()} GPX waypoint package successfully downloaded for Vessel Chartplotter (MMSI: 419001248).`
    );
    setTimeout(() => setExportNotice(null), 4000);
  };

  return (
    <AppShell
      title={t('routes.title', 'Intelligent Voyage Route Planner')}
      subtitle={t('routes.subtitle', 'Multi-Criteria Route Optimization Avoiding High Swell & Naval Restriction Zones')}
      actions={
        <div className="route-header-actions">
          <span className="terminal-status-tag" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <span className={isBackendLive ? 'enc-pulse-dot' : 'enc-pulse-dot-amber'} />
            {isBackendLive ? `FASTAPI RISK ENGINE (${latencyMs}ms)` : 'EDGE ROUTE ENGINE'}
          </span>
          <button className="btn secondary btn-sm" onClick={() => router.push('/marine-map')}>
            <Icon name="Map" size={13} />
            <span>{t('routes.fullChartView', 'Full Chart View')}</span>
          </button>
          <button
            className="btn primary btn-sm"
            onClick={() =>
              router.push(
                `/ai-copilot?q=Brief+me+on+navigational+hazards+and+advisories+for+${encodeURIComponent(
                  originInfo.name
                )}+to+${encodeURIComponent(destInfo.shortName || destInfo.name)}`
              )
            }
          >
            <Icon name="Bot" size={13} />
            <span>{t('routes.copilotRouteAudit', 'Copilot Route Audit')}</span>
          </button>
        </div>
      }
    >
      {/* Route Parameters Form Bar */}
      <Card className="route-form-card">
        <div className="route-form-grid">
          <label className="route-form-field">
            <span className="field-label">{t('routes.originHarbour', 'ORIGIN DEPARTURE HARBOUR')}</span>
            <div className="field-input-wrap">
              <Icon name="Anchor" size={14} className="text-safe" />
              <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
                {Object.entries(HARBOURS).map(([key, h]) => (
                  <option key={key} value={key}>
                    {h.fullName}
                  </option>
                ))}
              </select>
            </div>
          </label>

          <label className="route-form-field">
            <span className="field-label">{t('routes.targetDestination', 'TARGET DESTINATION')}</span>
            <div className="field-input-wrap">
              <Icon name="Target" size={14} className="text-accent" />
              <select value={destination} onChange={(e) => setDestination(e.target.value)}>
                {customDestCoord && !DESTINATIONS[destination] && (
                  <option value="custom-target">{customDestCoord.name}</option>
                )}
                {Object.entries(DESTINATIONS).map(([key, d]) => (
                  <option key={key} value={key}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          </label>

          <label className="route-form-field">
            <span className="field-label">{t('routes.vesselClass', 'VESSEL CLASSIFICATION & DRAFT')}</span>
            <div className="field-input-wrap">
              <Icon name="Ship" size={14} />
              <select value={vesselKey} onChange={(e) => setVesselKey(e.target.value)}>
                <option value="trawler">Inshore Motorized Trawler (&lt; 15m) • 10.4 kts • Draft: 2.8m</option>
                <option value="gillnetter">Deep Sea Gillnetter (15-24m) • 12.2 kts • Draft: 3.4m</option>
                <option value="catamaran">Traditional Motorized Catamaran (&lt; 10m) • 8.5 kts • Draft: 1.2m</option>
                <option value="research">Scientific Research Vessel (NIOS) • 14.0 kts • Draft: 4.8m</option>
              </select>
            </div>
          </label>

          <div className="route-form-button-wrap">
            <button className="btn primary wide" disabled={isCalculating} onClick={handleRecalculate}>
              <Icon name="Compass" size={14} />
              <span>
                {isCalculating ? 'Computing Hydrodynamics...' : t('routes.recalculateTrack', 'Recalculate Optimal Track')}
              </span>
            </button>
          </div>
        </div>
      </Card>

      {liveBriefing && (
        <div
          className="status-banner-notice"
          style={{
            margin: '10px 0',
            padding: '10px 14px',
            background: 'var(--c-surface)',
            border: '1px solid var(--c-border)',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Icon name="ShieldCheck" size={15} className="text-safe" />
            <span>
              <b>{liveBriefing.isLive ? 'FastAPI Marine Engine Verified:' : 'Edge Simulation:'}</b> {liveBriefing.verdict}
            </span>
          </div>
          <Badge tone={liveBriefing.compositeScore < 0.4 ? 'green' : 'orange'}>
            Risk Index: {typeof liveBriefing.compositeScore === 'number' ? liveBriefing.compositeScore.toFixed(2) : liveBriefing.compositeScore}
          </Badge>
        </div>
      )}

      {exportNotice && (
        <div
          className="status-banner-notice safe"
          style={{
            margin: '10px 0',
            padding: '10px 14px',
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '12px',
            color: '#065f46',
            fontFamily: 'monospace'
          }}
        >
          <Icon name="CheckCircle" size={15} />
          <span>{exportNotice}</span>
        </div>
      )}

      {/* Main Grid: Interactive Map & Route Comparison */}
      <div className="route-planner-grid">
        {/* Left: Real Leaflet Map with Active Route Highlighting */}
        <Card className="route-map-card">
          <SectionHeader
            title={t('routes.navTrajectory', 'Navigational Route Trajectory (ECDIS)')}
            badge={`ACTIVE: ${currentRoute.name.split('—')[0].trim().toUpperCase()} • FROM ${originInfo.id.toUpperCase()} TO ${(destInfo.id || 'TARGET').toUpperCase()}`}
            icon="Navigation"
          />
          <MarineMap
            large
            activeRouteId={selectedRouteId}
            routes={calculatedRoutes}
            originCoord={originInfo}
            destinationCoord={destInfo}
          />
        </Card>

        {/* Right: Route Options & Dynamic Waypoint Analysis */}
        <div className="route-side-column">
          <Card className="route-options-card">
            <SectionHeader
              title={t('routes.routeAlternatives', 'Calculated Route Alternatives (3)')}
              badge={`ORIGIN: ${originInfo.id.toUpperCase()}`}
              icon="GitCompare"
            />

            <div className="route-options-list">
              {calculatedRoutes.map((r) => {
                const isSelected = selectedRouteId === r.id;

                return (
                  <div
                    key={r.id}
                    className={`route-option-item ${isSelected ? 'active' : ''} border-${r.risk.toLowerCase()}`}
                    onClick={() => setSelectedRouteId(r.id)}
                  >
                    <div className="route-option-top">
                      <div>
                        <b className="route-name">{r.name}</b>
                        <span className="route-dist-dur">
                          {r.distance} • {r.duration} • {r.fuelEstimate}
                        </span>
                      </div>
                      <Badge tone={r.risk === 'LOW' ? 'green' : r.risk === 'MODERATE' ? 'orange' : 'red'}>
                        {r.risk} {t('fishing.operationalRisk', 'RISK')} ({r.riskScore})
                      </Badge>
                    </div>
                    <p className="route-summary-snippet">{r.summary}</p>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Selected Route Detailed Analysis */}
          <Card className="route-analysis-card">
            <SectionHeader
              title={`${t('routes.hydrodynamicAnalysis', 'Hydrodynamic Analysis')} — ${currentRoute.name.split('—')[0].trim()}`}
              badge={`EST. DIESEL: ${currentRoute.fuelEstimate}`}
              icon="CheckCircle"
            />

            <div className="route-metrics-grid">
              <div className="route-metric-box">
                <span>{t('routes.totalDistance', 'Total Distance')}</span>
                <b>{currentRoute.distance}</b>
              </div>
              <div className="route-metric-box">
                <span>{t('routes.voyageDuration', 'Voyage Duration')}</span>
                <b>{currentRoute.durationStr}</b>
              </div>
              <div className="route-metric-box">
                <span>{t('routes.highSwellBreakers', 'High Swell Breakers')}</span>
                <b className={currentRoute.highWaveAreas > 0 ? 'text-hazard' : 'text-safe'}>
                  {currentRoute.highWaveAreas} Zones
                </b>
              </div>
              <div className="route-metric-box">
                <span>{t('routes.navalGeofences', 'Naval Geofence Breaches')}</span>
                <b className={currentRoute.restrictedZones > 0 ? 'text-hazard' : 'text-safe'}>
                  {currentRoute.restrictedZones} Breaches
                </b>
              </div>
              <div className="route-metric-box">
                <span>{t('routes.compositeRisk', 'Composite Risk')}</span>
                <b className={currentRoute.risk === 'LOW' ? 'text-safe' : 'text-hazard'}>
                  {currentRoute.risk} ({currentRoute.riskScore})
                </b>
              </div>
              <div className="route-metric-box">
                <span>{t('routes.fuelConsumption', 'Fuel Consumption')}</span>
                <b>{currentRoute.fuelEstimate}</b>
              </div>
            </div>

            {/* Waypoint Sequence Table */}
            <div className="waypoints-table-wrap">
              <table className="waypoints-table">
                <thead>
                  <tr>
                    <th>{t('routes.waypointSequence', 'Waypoint Identification')}</th>
                    <th>Latitude</th>
                    <th>Longitude</th>
                    <th>{t('common.depth', 'Chart Depth')}</th>
                    <th>{t('dashboard.rating', 'ECDIS Clearance')}</th>
                  </tr>
                </thead>
                <tbody>
                  {currentRoute.waypoints.map((wp, idx) => (
                    <tr key={idx}>
                      <td>
                        <b>{wp.name}</b>
                      </td>
                      <td>
                        <code>{wp.lat}</code>
                      </td>
                      <td>
                        <code>{wp.lon}</code>
                      </td>
                      <td>{wp.depth}</td>
                      <td>
                        <span
                          className={`status-pill ${
                            wp.status.includes('HAZARD') || wp.status.includes('Waves') || wp.status.includes('RESTRICTED')
                              ? 'hazard'
                              : 'safe'
                          }`}
                        >
                          {wp.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="route-action-footer">
              <button className="btn secondary btn-sm" onClick={handleExportGps}>
                <Icon name="Upload" size={13} />
                <span>{t('routes.exportGps', 'Export to Vessel GPS (GPX)')}</span>
              </button>
              <button
                className="btn primary btn-sm"
                onClick={() =>
                  router.push(
                    `/ai-copilot?q=Provide+nautical+route+briefing+for+${encodeURIComponent(currentRoute.name)}+from+${encodeURIComponent(
                      originInfo.name
                    )}+to+${encodeURIComponent(destInfo.name)}`
                  )
                }
              >
                <Icon name="Bot" size={13} />
                <span>{t('routes.audioBriefing', 'Audio Nav Briefing')}</span>
              </button>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
