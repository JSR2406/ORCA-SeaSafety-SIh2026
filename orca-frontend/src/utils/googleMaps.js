// ============================================================================
// ORCA — Google Maps API Integration Utilities
// High-Resolution Maritime Cartography, Geocoding & Places Service
// ============================================================================

const STORAGE_KEY = 'orca_google_maps_api_key';

/**
 * Retrieve active Google Maps API Key from environment or localStorage
 */
export function getGoogleMapsApiKey() {
  // Check Next.js and fallback environment variables
  let envKey = '';
  try {
    envKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || process.env.VITE_GOOGLE_MAPS_API_KEY || '';
  } catch (e) {}

  if (typeof envKey === 'string' && envKey.trim().length > 0) {
    return envKey.trim();
  }

  // Fallback to browser localStorage
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      const localKey = localStorage.getItem(STORAGE_KEY);
      if (typeof localKey === 'string' && localKey.trim().length > 0) {
        return localKey.trim();
      }
    }
  } catch (e) {
    console.warn('Unable to access localStorage for Google Maps API key:', e);
  }

  return '';
}

/**
 * Check if a Google Maps API Key is currently configured
 */
export function hasGoogleMapsApiKey() {
  return getGoogleMapsApiKey().length > 0;
}

/**
 * Mask an API key for safe UI presentation (e.g. AIza••••••••••••2eU)
 */
export function maskApiKey(key) {
  if (!key || typeof key !== 'string') return '';
  const trimmed = key.trim();
  if (trimmed.length <= 8) return '••••••••';
  return trimmed.slice(0, 4) + '••••••••••••••••' + trimmed.slice(-4);
}

/**
 * Determine if the active API key is sourced from environment configuration
 */
export function isEnvApiKey() {
  try {
    const envKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || process.env.VITE_GOOGLE_MAPS_API_KEY || '';
    return Boolean(envKey && envKey.trim().length > 0);
  } catch (e) {
    return false;
  }
}

/**
 * Persist or clear Google Maps API Key in localStorage and broadcast change event
 */
export function setGoogleMapsApiKey(key) {
  try {
    const cleanKey = typeof key === 'string' ? key.trim() : '';
    if (cleanKey) {
      localStorage.setItem(STORAGE_KEY, cleanKey);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }

    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('orca:google-maps-key-changed', {
          detail: { apiKey: cleanKey, hasKey: Boolean(cleanKey) }
        })
      );
    }
    return true;
  } catch (e) {
    console.error('Failed to set Google Maps API key:', e);
    return false;
  }
}

/**
 * Generate Google Maps Tile Layer endpoints
 * lyrs=y -> Hybrid (Satellite + Roads/Labels)
 * lyrs=s -> Pure Satellite Imagery
 * lyrs=m -> Standard Nautical / Vector Roadmap
 * lyrs=p -> Terrain with Contours & Relief
 */
export function getGoogleTileConfig(apiKey) {
  const keyParam = apiKey ? `&key=${encodeURIComponent(apiKey)}` : '';
  return {
    hybrid: {
      url: `https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}${keyParam}`,
      options: {
        maxZoom: 21,
        subdomains: ['0', '1', '2', '3'],
        attribution: '&copy; Google Maps'
      }
    },
    satellite: {
      url: `https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}${keyParam}`,
      options: {
        maxZoom: 21,
        subdomains: ['0', '1', '2', '3'],
        attribution: '&copy; Google Maps'
      }
    },
    roadmap: {
      url: `https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}${keyParam}`,
      options: {
        maxZoom: 21,
        subdomains: ['0', '1', '2', '3'],
        attribution: '&copy; Google Maps'
      }
    },
    terrain: {
      url: `https://mt{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}${keyParam}`,
      options: {
        maxZoom: 21,
        subdomains: ['0', '1', '2', '3'],
        attribution: '&copy; Google Maps'
      }
    }
  };
}

let googleMapsScriptLoadingPromise = null;

/**
 * Dynamically load Google Maps JavaScript API SDK if not already loaded
 */
export function loadGoogleMapsJsSdk(apiKey) {
  if (typeof window === 'undefined') return Promise.reject(new Error('Window unavailable'));

  if (window.google && window.google.maps) {
    return Promise.resolve(window.google.maps);
  }

  if (googleMapsScriptLoadingPromise) {
    return googleMapsScriptLoadingPromise;
  }

  const keyToUse = apiKey || getGoogleMapsApiKey();
  if (!keyToUse) {
    return Promise.reject(new Error('No Google Maps API Key provided'));
  }

  googleMapsScriptLoadingPromise = new Promise((resolve, reject) => {
    const existingScript = document.getElementById('orca-google-maps-sdk');
    if (existingScript) {
      existingScript.remove();
    }

    const script = document.createElement('script');
    script.id = 'orca-google-maps-sdk';
    script.type = 'text/javascript';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(
      keyToUse
    )}&libraries=places,geometry`;
    script.async = true;
    script.defer = true;

    script.onload = () => {
      if (window.google && window.google.maps) {
        resolve(window.google.maps);
      } else {
        reject(new Error('Google Maps SDK loaded but window.google.maps is undefined'));
      }
    };

    script.onerror = (err) => {
      googleMapsScriptLoadingPromise = null;
      reject(err || new Error('Failed to load Google Maps SDK'));
    };

    document.head.appendChild(script);
  });

  return googleMapsScriptLoadingPromise;
}

/**
 * Major Indian Coastal Sectors covering the complete 7,516 km coastline
 */
export const INDIA_COASTAL_SECTORS = [
  {
    id: 'all-india',
    name: 'All India Coastal Waters',
    shortName: '🇮🇳 All India',
    state: 'National',
    lat: 15.2,
    lng: 78.5,
    zoom: 5,
    description: 'Complete Indian Peninsula: 7,516 km coastline across Arabian Sea, Indian Ocean & Bay of Bengal',
    coastlineKm: 7516,
    majorPorts: ['Mumbai', 'Kochi', 'Chennai', 'Visakhapatnam', 'Kandla', 'Paradip', 'Kolkata']
  },
  {
    id: 'gujarat',
    name: 'Gujarat Coast (Kutch & Saurashtra)',
    shortName: '🦀 Gujarat Coast',
    state: 'Gujarat',
    lat: 21.65,
    lng: 69.95,
    zoom: 8,
    description: "India's longest coastline (1,600 km) & top marine fish producer (Veraval, Porbandar, Kandla)",
    coastlineKm: 1600,
    majorPorts: ['Veraval', 'Kandla (Deendayal)', 'Porbandar', 'Okha', 'Mundra']
  },
  {
    id: 'maharashtra',
    name: 'Maharashtra & Konkan Coast',
    shortName: '🚢 Maharashtra (Konkan)',
    state: 'Maharashtra',
    lat: 18.92,
    lng: 72.85,
    zoom: 8,
    description: 'Vital maritime shipping gateway (Mumbai JNPT, Sassoon Docks, Ratnagiri & Malvan)',
    coastlineKm: 720,
    majorPorts: ['Mumbai Port', 'JNPT Nhava Sheva', 'Sassoon Dock', 'Ratnagiri Mirkarwada', 'Malvan']
  },
  {
    id: 'goa-karnataka',
    name: 'Goa & Karnataka Coast (Karavali)',
    shortName: '⚓ Goa & Karavali',
    state: 'Karnataka / Goa',
    lat: 14.15,
    lng: 74.35,
    zoom: 8,
    description: 'Deep-sea purse seine hub & iron ore gateway (Malpe, New Mangalore, Mormugao, Karwar)',
    coastlineKm: 420,
    majorPorts: ['New Mangalore Port', 'Malpe Fishery Harbour', 'Mormugao', 'Karwar']
  },
  {
    id: 'kerala',
    name: 'Kerala & Malabar Coast',
    shortName: '🐟 Kerala (Malabar)',
    state: 'Kerala',
    lat: 9.95,
    lng: 76.15,
    zoom: 9,
    description: 'Premier pelagic fishing & transshipment hub (Kochi, Munambam, Vizhinjam Seaport, Neendakara)',
    coastlineKm: 590,
    majorPorts: ['Kochi (Cochin Major Port)', 'Munambam', 'Vizhinjam Seaport', 'Neendakara', 'Beypore']
  },
  {
    id: 'gulf-of-mannar',
    name: 'Kanyakumari & Gulf of Mannar',
    shortName: '🌊 Gulf of Mannar',
    state: 'Tamil Nadu',
    lat: 8.75,
    lng: 78.40,
    zoom: 8,
    description: 'Tri-sea confluence & Marine Biosphere Reserve (Tuticorin VOC, Rameswaram, Cape Comorin)',
    coastlineKm: 350,
    majorPorts: ['Tuticorin (V.O.C Port)', 'Rameswaram Pamban', 'Kanyakumari', 'Mandapam']
  },
  {
    id: 'tamil-nadu',
    name: 'Tamil Nadu & Coromandel Coast',
    shortName: '🏖️ Coromandel (TN)',
    state: 'Tamil Nadu',
    lat: 12.80,
    lng: 80.25,
    zoom: 8,
    description: 'Eastern deepwater shipping lanes & major port terminals (Chennai Port, Ennore, Cuddalore)',
    coastlineKm: 1076,
    majorPorts: ['Chennai Port', 'Kamarajar (Ennore)', 'Cuddalore', 'Nagapattinam']
  },
  {
    id: 'andhra-pradesh',
    name: 'Andhra Pradesh Coast (Northern Circars)',
    shortName: '🎯 Andhra Coast',
    state: 'Andhra Pradesh',
    lat: 16.90,
    lng: 82.50,
    zoom: 8,
    description: "Second longest mainland coastline (974 km) with major naval & commercial hub (Visakhapatnam, Kakinada)",
    coastlineKm: 974,
    majorPorts: ['Visakhapatnam Port (Vizag)', 'Kakinada Deepwater', 'Gangavaram', 'Krishnapatnam']
  },
  {
    id: 'odisha',
    name: 'Odisha & Utkal Coast',
    shortName: '🐢 Odisha Coast',
    state: 'Odisha',
    lat: 20.10,
    lng: 86.60,
    zoom: 8,
    description: 'Heavy mineral export & Olive Ridley sanctuary (Paradip Port, Dhamra, Gahirmatha Marine Sanctuary)',
    coastlineKm: 480,
    majorPorts: ['Paradip Port', 'Dhamra Port', 'Gopalpur', 'Gahirmatha']
  },
  {
    id: 'west-bengal',
    name: 'West Bengal & Sundarbans Delta',
    shortName: '🐅 Bengal & Sundarbans',
    state: 'West Bengal',
    lat: 21.80,
    lng: 88.15,
    zoom: 8,
    description: "World's largest mangrove delta & major estuarine fishery (Kolkata SPM, Haldia, Digha Harbour)",
    coastlineKm: 158,
    majorPorts: ['Kolkata SPM Port', 'Haldia Dock Complex', 'Digha Fishery Harbour', 'Sagar Island']
  },
  {
    id: 'islands',
    name: 'Lakshadweep & Andaman Nicobar',
    shortName: '🏝️ Island Territories',
    state: 'Islands (UT)',
    lat: 11.65,
    lng: 92.70,
    zoom: 7,
    description: 'Strategic Indian Ocean island archipelagos & oceanic tuna grounds (Port Blair, Kavaratti, Minicoy)',
    coastlineKm: 2094,
    majorPorts: ['Port Blair (Haddo)', 'Kavaratti Lagoon', 'Agatti', 'Campbell Bay']
  }
];

/**
 * Curated Indian Coastal Ports and Landmarks for immediate offline / quick autocomplete
 * Covering all 9 coastal states and 2 island territories of India
 */
export const COASTAL_QUICK_PORTS = [
  // ── Gujarat ──
  { name: 'Veraval Fishing Harbour', lat: 20.9000, lng: 70.3667, state: 'Gujarat', type: 'Major Fishery Hub' },
  { name: 'Kandla / Deendayal Port', lat: 23.0033, lng: 70.2189, state: 'Gujarat', type: 'Major Port' },
  { name: 'Porbandar Deep Sea Port', lat: 21.6417, lng: 69.6050, state: 'Gujarat', type: 'Fishing & Commercial Port' },
  { name: 'Okha Fishery Port & Gateway', lat: 22.4667, lng: 69.0833, state: 'Gujarat', type: 'Gulf of Kutch Gateway' },
  { name: 'Mundra Port', lat: 22.7444, lng: 69.7042, state: 'Gujarat', type: 'Major Commercial Port' },
  { name: 'Pipavav Port', lat: 20.9167, lng: 71.5000, state: 'Gujarat', type: 'Deepwater Container Port' },

  // ── Maharashtra ──
  { name: 'Mumbai Port Trust & Sassoon Docks', lat: 18.9167, lng: 72.8250, state: 'Maharashtra', type: 'Major Fishery & Port' },
  { name: 'Mumbai JNPT Harbour (Nhava Sheva)', lat: 18.9500, lng: 72.9500, state: 'Maharashtra', type: 'Major Container Gateway' },
  { name: 'Bhaucha Dhakka Ferry Wharf', lat: 18.9500, lng: 72.8500, state: 'Maharashtra', type: 'Central Fish Auction Market' },
  { name: 'Ratnagiri Mirkarwada Harbour', lat: 16.9833, lng: 73.2833, state: 'Maharashtra', type: 'Major Konkan Fishery Port' },
  { name: 'Malvan Coastal Jetty & Sanctuary', lat: 16.0500, lng: 73.4667, state: 'Maharashtra', type: 'Marine Sanctuary Hub' },

  // ── Goa ──
  { name: 'Mormugao Port (Goa)', lat: 15.4167, lng: 73.8000, state: 'Goa', type: 'Major Deepwater Port' },
  { name: 'Panaji Mandovi Fishery Jetty', lat: 15.5000, lng: 73.8333, state: 'Goa', type: 'Estuarine Fishery Harbour' },

  // ── Karnataka ──
  { name: 'Malpe Fishery Harbour', lat: 13.3500, lng: 74.7000, state: 'Karnataka', type: 'Leading Purse Seine Hub' },
  { name: 'Mangalore New Port', lat: 12.9250, lng: 74.8150, state: 'Karnataka', type: 'Major Port' },
  { name: 'Karwar Baitkhol Fishing Port', lat: 14.8167, lng: 74.1333, state: 'Karnataka', type: 'Naval & Fishery Base' },

  // ── Kerala ──
  { name: 'Kochi Fishing Harbour (HQ)', lat: 9.9667, lng: 76.2667, state: 'Kerala', type: 'Major Port & HQ' },
  { name: 'Cochin Fairway Buoy', lat: 9.9750, lng: 76.1650, state: 'Kerala', type: 'Nav Buoy' },
  { name: 'Munambam Fishing Port', lat: 10.1800, lng: 76.1600, state: 'Kerala', type: 'Fishing Port' },
  { name: 'Vizhinjam International Seaport', lat: 8.3750, lng: 76.9950, state: 'Kerala', type: 'Deep Sea Transshipment' },
  { name: 'Neendakara Fishery Harbour (Kollam)', lat: 8.9350, lng: 76.5400, state: 'Kerala', type: 'Mechanized Trawler Port' },
  { name: 'Beypore Port & Estuary', lat: 11.1667, lng: 75.8050, state: 'Kerala', type: 'Commercial Port' },
  { name: 'Alappuzha Coastal Landing', lat: 9.4900, lng: 76.3300, state: 'Kerala', type: 'Coastal Landing' },

  // ── Tamil Nadu ──
  { name: 'Chennai Port', lat: 13.0850, lng: 80.2980, state: 'Tamil Nadu', type: 'East Coast Major Port' },
  { name: 'Kasimedu Fishing Harbour (Chennai)', lat: 13.1200, lng: 80.3000, state: 'Tamil Nadu', type: 'Major Eastern Fishery Base' },
  { name: 'Tuticorin V.O.C Port', lat: 8.7500, lng: 78.1800, state: 'Tamil Nadu', type: 'Deep Water Port' },
  { name: 'Rameswaram Pamban Pier', lat: 9.2833, lng: 79.3167, state: 'Tamil Nadu', type: 'Palk Strait Fishery Gateway' },
  { name: 'Kanyakumari Chinnamuttam Port', lat: 8.0833, lng: 77.5667, state: 'Tamil Nadu', type: 'Cape Comorin Fishery Base' },
  { name: 'Nagapattinam Port', lat: 10.7667, lng: 79.8500, state: 'Tamil Nadu', type: 'Coromandel Coastal Port' },

  // ── Andhra Pradesh ──
  { name: 'Visakhapatnam (Vizag) Major Port', lat: 17.6833, lng: 83.2833, state: 'Andhra Pradesh', type: 'Major Naval & Commercial Port' },
  { name: 'Vizag Fishing Harbour', lat: 17.7000, lng: 83.3000, state: 'Andhra Pradesh', type: 'Major Trawler Base' },
  { name: 'Kakinada Deepwater Port', lat: 16.9833, lng: 82.2667, state: 'Andhra Pradesh', type: 'Deepwater Commercial Port' },
  { name: 'Gangavaram Port', lat: 17.6167, lng: 83.2333, state: 'Andhra Pradesh', type: 'All-Weather Deep Port' },
  { name: 'Krishnapatnam Port', lat: 14.2500, lng: 80.1333, state: 'Andhra Pradesh', type: 'Deepwater Port' },

  // ── Odisha ──
  { name: 'Paradip Major Port', lat: 20.2667, lng: 86.6667, state: 'Odisha', type: 'Major Port' },
  { name: 'Paradip Fishing Harbour', lat: 20.2833, lng: 86.6833, state: 'Odisha', type: 'Mechanized Fishery Base' },
  { name: 'Dhamra Port', lat: 20.8167, lng: 86.9667, state: 'Odisha', type: 'Deep Draft Bulk Port' },
  { name: 'Gopalpur Port', lat: 19.3000, lng: 84.9667, state: 'Odisha', type: 'Commercial Deepwater Port' },

  // ── West Bengal ──
  { name: 'Haldia Dock Complex', lat: 22.0167, lng: 88.0667, state: 'West Bengal', type: 'Major Riverine Port' },
  { name: 'Kolkata Syama Prasad Mookerjee Port', lat: 22.5500, lng: 88.3167, state: 'West Bengal', type: 'Historic Major Port' },
  { name: 'Digha Fishery Harbour (Sankarpur)', lat: 21.6333, lng: 87.5667, state: 'West Bengal', type: 'Premier Marine Fish Hub' },
  { name: 'Fraserganj Fishing Harbour', lat: 21.5833, lng: 88.2500, state: 'West Bengal', type: 'Sundarbans Marine Fishery' },
  { name: 'Sagar Island (Ganga Sagar)', lat: 21.6500, lng: 88.0500, state: 'West Bengal', type: 'Estuarine Island Hub' },

  // ── Island Territories ──
  { name: 'Kavaratti Island (Lakshadweep)', lat: 10.5667, lng: 72.6333, state: 'Lakshadweep', type: 'Island Capital' },
  { name: 'Agatti Island Jetty', lat: 10.8500, lng: 72.1833, state: 'Lakshadweep', type: 'Island Fishery & Airport' },
  { name: 'Minicoy Island Harbour', lat: 8.2833, lng: 73.0500, state: 'Lakshadweep', type: 'Eight Degree Channel Port' },
  { name: 'Port Blair Haddo Harbour', lat: 11.6667, lng: 92.7333, state: 'Andaman & Nicobar', type: 'Island Strategic Hub' },
  { name: 'Campbell Bay (Great Nicobar)', lat: 7.0000, lng: 93.9167, state: 'Andaman & Nicobar', type: 'Ten Degree Channel Gateway' }
];

/**
 * Geocode a place name or coordinate query using Google Geocoder or fallback
 */
export async function geocodeLocation(query, apiKey) {
  if (!query || typeof query !== 'string') return null;
  const trimmed = query.trim();

  // 1. Check if user typed direct decimal lat/lng like "9.9667, 76.2667"
  const coordRegex = /^([-+]?\d{1,2}(?:\.\d+)?)\s*,\s*([-+]?\d{1,3}(?:\.\d+)?)$/;
  const coordMatch = trimmed.match(coordRegex);
  if (coordMatch) {
    const lat = parseFloat(coordMatch[1]);
    const lng = parseFloat(coordMatch[2]);
    if (lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
      return {
        lat,
        lng,
        name: `GPS Fix: ${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E`,
        source: 'coordinates'
      };
    }
  }

  // 2. Check Indian Coastal Sectors first
  const lower = trimmed.toLowerCase();
  const matchedSector = INDIA_COASTAL_SECTORS.find(
    (s) =>
      s.name.toLowerCase().includes(lower) ||
      s.shortName.toLowerCase().includes(lower) ||
      s.id.toLowerCase() === lower
  );
  if (matchedSector) {
    return {
      lat: matchedSector.lat,
      lng: matchedSector.lng,
      zoom: matchedSector.zoom,
      name: `${matchedSector.name} (${matchedSector.state})`,
      source: 'coastal-sector'
    };
  }

  // 3. Check curated Indian maritime ports for instant offline response
  const matchedPort = COASTAL_QUICK_PORTS.find(
    (p) => p.name.toLowerCase().includes(lower) || lower.includes(p.name.toLowerCase().split(' ')[0])
  );
  if (matchedPort) {
    return {
      lat: matchedPort.lat,
      lng: matchedPort.lng,
      name: `${matchedPort.name} (${matchedPort.state})`,
      source: 'maritime-directory'
    };
  }

  // 4. If Google Maps SDK is loaded or key is available, use Google Geocoder
  const keyToUse = apiKey || getGoogleMapsApiKey();
  if (keyToUse) {
    try {
      const googleMaps = await loadGoogleMapsJsSdk(keyToUse);
      if (googleMaps && googleMaps.Geocoder) {
        const geocoder = new googleMaps.Geocoder();
        const response = await new Promise((resolve, reject) => {
          geocoder.geocode({ address: trimmed, region: 'IN' }, (results, status) => {
            if (status === 'OK' && results && results.length > 0) {
              resolve(results[0]);
            } else {
              reject(new Error(`Google Geocoder status: ${status}`));
            }
          });
        });

        if (response && response.geometry && response.geometry.location) {
          return {
            lat: response.geometry.location.lat(),
            lng: response.geometry.location.lng(),
            name: response.formatted_address || trimmed,
            source: 'google-geocoder'
          };
        }
      }
    } catch (err) {
      console.warn('Google Maps Geocoding SDK failed, attempting fetch fallback:', err);
    }

    // 4. HTTP Fetch fallback to Google Geocoding REST API
    try {
      const url = `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(
        trimmed
      )}&key=${encodeURIComponent(keyToUse)}&region=in`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'OK' && data.results && data.results.length > 0) {
          const loc = data.results[0].geometry.location;
          return {
            lat: loc.lat,
            lng: loc.lng,
            name: data.results[0].formatted_address,
            source: 'google-rest-api'
          };
        }
      }
    } catch (e) {
      console.warn('Google REST Geocode failed:', e);
    }
  }

  return null;
}
