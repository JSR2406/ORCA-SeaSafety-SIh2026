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
 * Curated Indian Coastal Ports and Landmarks for immediate offline / quick autocomplete
 */
export const COASTAL_QUICK_PORTS = [
  { name: 'Kochi Fishing Harbour (HQ)', lat: 9.9667, lng: 76.2667, state: 'Kerala', type: 'Major Port' },
  { name: 'Cochin Fairway Buoy', lat: 9.9750, lng: 76.1650, state: 'Kerala', type: 'Nav Buoy' },
  { name: 'Munambam Fishing Harbour', lat: 10.1800, lng: 76.1600, state: 'Kerala', type: 'Fishing Port' },
  { name: 'Vizhinjam International Seaport', lat: 8.3750, lng: 76.9950, state: 'Kerala', type: 'Deep Sea Port' },
  { name: 'Beypore Port & Estuary', lat: 11.1667, lng: 75.8050, state: 'Kerala', type: 'Commercial Port' },
  { name: 'Alappuzha Coastal Landing', lat: 9.4900, lng: 76.3300, state: 'Kerala', type: 'Coastal Landing' },
  { name: 'Mangalore New Port', lat: 12.9250, lng: 74.8150, state: 'Karnataka', type: 'Major Port' },
  { name: 'Mormugao Port (Goa)', lat: 15.4167, lng: 73.8000, state: 'Goa', type: 'Major Port' },
  { name: 'Mumbai JNPT Harbour', lat: 18.9500, lng: 72.9500, state: 'Maharashtra', type: 'Major Container Port' },
  { name: 'Veraval Fishing Harbour', lat: 20.9000, lng: 70.3667, state: 'Gujarat', type: 'Major Fishery Hub' },
  { name: 'Kavaratti Island (Lakshadweep)', lat: 10.5667, lng: 72.6333, state: 'Lakshadweep', type: 'Island Capital' },
  { name: 'Chennai Port', lat: 13.0850, lng: 80.2980, state: 'Tamil Nadu', type: 'East Coast Major Port' },
  { name: 'Tuticorin V.O.C Port', lat: 8.7500, lng: 78.1800, state: 'Tamil Nadu', type: 'Deep Water Port' }
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

  // 2. Check local curated maritime ports first for instant response
  const lower = trimmed.toLowerCase();
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

  // 3. If Google Maps SDK is loaded or key is available, use Google Geocoder
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
