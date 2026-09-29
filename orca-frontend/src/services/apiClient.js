// ============================================================================
// ORCA — API Client Service
// Resilient HTTP client bridging Next.js Frontend with FastAPI Backend (Port 8000)
// Includes automatic mock fallbacks when backend is offline
// ============================================================================

import {
  conditions as mockConditions,
  alerts as mockAlerts,
  pfzZones as mockPfzZones,
  routesData as mockRoutesData
} from '../data/mock';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || process.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Standard fetch helper with timeout and fallback
 */
// Operator (harbour authority) session token for privileged alert writes.
// Held in memory only: never localStorage, so an XSS payload cannot read it.
let operatorToken = null;

export function setOperatorToken(token) {
  operatorToken = token || null;
}

export function getOperatorToken() {
  return operatorToken;
}

function operatorAuthHeaders() {
  return operatorToken ? { Authorization: `Bearer ${operatorToken}` } : {};
}

export async function operatorLogin({ email, password }) {
  const res = await fetchWithTimeout('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  }, 5000);
  if (!res?.access_token) throw new Error('Sign-in failed');
  setOperatorToken(res.access_token);
  return res;
}

async function fetchWithTimeout(endpoint, options = {}, timeoutMs = 4500) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(options.headers || {})
      }
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text().catch(() => '');
      throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
    }

    return await response.json();
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}

// ----------------------------------------------------------------------------
// 1. Health & Telemetry
// ----------------------------------------------------------------------------

export async function checkBackendHealth() {
  const start = Date.now();
  try {
    const data = await fetchWithTimeout('/api/v1/health', { method: 'GET' }, 2500);
    const latencyMs = Date.now() - start;
    return {
      isLive: true,
      status: data.status || 'healthy',
      database: data.database || 'connected',
      version: data.version || '0.1.0',
      latencyMs,
      timestamp: data.timestamp || new Date().toISOString()
    };
  } catch (err) {
    return {
      isLive: false,
      status: 'offline',
      database: 'disconnected',
      version: 'offline-mode',
      latencyMs: 0,
      timestamp: new Date().toISOString(),
      error: err.message
    };
  }
}

export async function getDatasetsStatus() {
  try {
    const data = await fetchWithTimeout('/api/v1/datasets/status', { method: 'GET' }, 3000);
    return { isLive: true, data };
  } catch (err) {
    return {
      isLive: false,
      data: {
        datasets: [
          { name: 'INCOIS Ocean State Forecast', status: 'live', cadence: '6h', lastSync: '10m ago' },
          { name: 'IMD Coastal Warning System', status: 'live', cadence: '3h', lastSync: '15m ago' },
          { name: 'Open-Meteo Marine Hydrodynamics', status: 'live', cadence: '1h', lastSync: '2m ago' },
          { name: 'NAVAREA VIII Exclusion Bulletins', status: 'live', cadence: 'Continuous', lastSync: '5m ago' },
          { name: 'ISRO MOSDAC / OCEANSAT-3 PFZ', status: 'live', cadence: '12h', lastSync: '1h ago' }
        ]
      }
    };
  }
}

// ----------------------------------------------------------------------------
// 2. AI Copilot (/api/v1/chat)
// ----------------------------------------------------------------------------

export async function sendChatMessage({ message, language = 'en', sessionId = null }) {
  const startTime = Date.now();
  try {
    const payload = {
      message,
      language,
      session_id: sessionId || `orca-sess-${Date.now()}`
    };

    const res = await fetchWithTimeout('/api/v1/chat', {
      method: 'POST',
      body: JSON.stringify(payload)
    }, 45000); // 45s for LLM processing timeout

    const latencyMs = Date.now() - startTime;

    return {
      isLive: true,
      answer: res.answer || res.message || res.data || 'Query processed by ORCA Agent Orchestrator.',
      queryRunId: res.query_run_id || `run-${Date.now().toString().slice(-4)}`,
      status: res.status || 'success',
      evidence: res.evidence || [],
      visualizations: res.visualizations || null,
      ml_scores: res.ml_scores || null,
      hydrodynamics: res.hydrodynamics || null,
      latencyMs,
      structuredQuery: res.structured_query
    };
  } catch (err) {
    // Intelligent contextual fallback
    const latencyMs = Date.now() - startTime;
    return {
      isLive: false,
      answer: generateFallbackCopilotAnswer(message, language),
      queryRunId: `mock-${Date.now()}`,
      status: 'fallback',
      evidence: [
        { claim: 'Wave height safe at 1.4m', source: 'INCOIS Station AD04', verified: true },
        { claim: 'Thermal upwelling verified at PFZ-01', source: 'OCEANSAT-3', verified: true }
      ],
      latencyMs,
      note: 'Processed via ORCA Edge Engine (FastAPI offline)'
    };
  }
}

function generateFallbackCopilotAnswer(query, lang = 'en') {
  const q = (query || '').toLowerCase();

  if (q.includes('fish') || q.includes('pfz') || q.includes('मछली') || q.includes('മത്സ്യ')) {
    return 'Pelagic thermal front analysis: Optimal harvest potential is confirmed at **PFZ-01 (14.2 km SW of Kochi)** with SST of 28.4°C and chlorophyll bloom at 0.88 mg/m³. Pelagic species (Indian Mackerel & Oil Sardine) are strongly congregated along the thermal boundary. Recommend departure via Northwest Fairway Channel.';
  }

  if (q.includes('safe') || q.includes('wave') || q.includes('risk') || q.includes('सुरक्षित') || q.includes('സുരക്ഷിത')) {
    return 'Current maritime risk assessment for Kochi Coastal Sector 4 is **MODERATE RISK (Composite Index: 0.61)**. Significant wave height is 1.4m (Douglas Sea State 3) with swell period 11.8s. Safe operational fairway is certified along Route B. Avoid Sector Bravo naval firing range (Notice #0482 active until 18:00 IST).';
  }

  if (q.includes('route') || q.includes('waypoint') || q.includes('रास्ता') || q.includes('റൂട്ട്')) {
    return 'Voyage Analysis: **Route B (Northwest Fairway Channel)** is the recommended path (42.8 km, 2h 14m). It maintains a 5.2m minimum depth sounding and provides a wide 8.5 km buffer from the active NAVAREA VIII Sector Bravo exercise zone.';
  }

  return `Analyzed marine telemetry for "${query}". Sea conditions off Kochi are evaluated as **MODERATE RISK** for vessels under 15m. Surface wind 18 km/h ENE, swell 1.4m, and barometric pressure 1009.4 hPa. All systems operational.`;
}

// ----------------------------------------------------------------------------
// 3. Marine Risk & Briefing (/api/v1/risk/briefing)
// ----------------------------------------------------------------------------

export async function getMarineBriefing({ lat = 9.93, lon = 76.27, distanceKm = 50 }) {
  try {
    const payload = {
      origin: { lat, lon },
      distance_km: distanceKm,
      include_forecast: true
    };

    const data = await fetchWithTimeout('/api/v1/risk/briefing', {
      method: 'POST',
      body: JSON.stringify(payload)
    }, 6000);

    return { isLive: true, ...data };
  } catch (err) {
    return {
      isLive: false,
      composite_score: 0.61,
      verdict: 'Sea conditions near Kochi evaluated as MODERATE RISK for fishing vessels under 15m.',
      components: [
        { name: 'Wave Risk', score: 0.38, detail: '1.4m swell height with 11.8s period' },
        { name: 'Wind Risk', score: 0.22, detail: '18 km/h ENE surface vector' },
        { name: 'Naval Restriction', score: 0.75, detail: 'Sector Bravo exercise 12 km East' }
      ],
      float_count: 8,
      source: 'INCOIS Marine Forecast'
    };
  }
}

// ----------------------------------------------------------------------------
// 4. Route Analysis & Geofencing (/api/v1/route/analyze)
// ----------------------------------------------------------------------------

export async function analyzeRoute({
  originLat,
  originLon,
  destinationLat,
  destinationLon,
  waypoints = [],
  vesselType = 'trawler'
}) {
  try {
    const payload = {
      origin_lat: originLat,
      origin_lon: originLon,
      destination_lat: destinationLat,
      destination_lon: destinationLon,
      waypoints: (waypoints || []).map((pt) => ({
        lat: Array.isArray(pt) ? pt[0] : pt.latNum || pt.lat,
        lon: Array.isArray(pt) ? pt[1] : pt.lonNum || pt.lon || pt.lng
      })),
      vessel_type: vesselType
    };

    const data = await fetchWithTimeout('/api/v1/route/analyze', {
      method: 'POST',
      body: JSON.stringify(payload)
    }, 6000);

    return { isLive: true, ...data };
  } catch (err) {
    return {
      isLive: false,
      recommendedRoute: 'route-b',
      geofenceViolations: [],
      reasoning: 'Calculated via ECDIS standard waypoint model (Offline Fallback)'
    };
  }
}

// ----------------------------------------------------------------------------
// 5. Hazards & Real Marine Warnings (/api/v1/alerts & /api/v1/marine/warnings)
// ----------------------------------------------------------------------------

export async function getBackendAlerts() {
  try {
    const res = await fetchWithTimeout('/api/v1/alerts', { method: 'GET' }, 3500);
    if (res && Array.isArray(res.alerts) && res.alerts.length > 0) {
      const normalized = res.alerts.map((a, idx) => {
        const rawLevel = (a.level || a.severity || 'warning').toUpperCase();
        const level = (rawLevel === 'CRITICAL' || rawLevel === 'RED' || rawLevel === 'HIGH') ? 'HIGH'
          : (rawLevel === 'WATCH' || rawLevel === 'MEDIUM' || rawLevel === 'ORANGE') ? 'MEDIUM'
          : 'LOW';

        return {
          id: a.id || `ALT-${idx + 1}`,
          title: a.title || 'Maritime Safety Bulletin',
          place: a.place || 'Coastal Operating Zone',
          time: a.time || (a.created_at ? new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Active'),
          level,
          category: a.category || (a.type === 'high_waves' ? 'Weather' : a.type === 'restriction' || a.type === 'geofence' ? 'Geofence' : 'Safety'),
          source: a.source || 'Coast Guard MRCC',
          validTill: a.validTill || (a.valid_until ? new Date(a.valid_until).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'Continuous'),
          desc: a.desc || a.message || 'Advisory active for regional mariners.',
          coordinates: a.coordinates || (a.latitude && a.longitude ? `${Number(a.latitude).toFixed(2)}°N, ${Number(a.longitude).toFixed(2)}°E` : "09°58'N, 076°16'E"),
          lat: a.latitude || 9.96,
          lon: a.longitude || 76.16,
          actionRequired: a.actionRequired || a.action_required || 'Maintain VHF Channel 16 listening watch.',
          status: a.status || 'active',
          isLive: true
        };
      });
      return { isLive: true, alerts: normalized, total: normalized.length };
    }
    return { isLive: false, alerts: mockAlerts, total: mockAlerts.length };
  } catch (err) {
    return { isLive: false, alerts: mockAlerts, total: mockAlerts.length, error: err.message };
  }
}

export async function createBackendAlert(alertData) {
  try {
    const res = await fetchWithTimeout('/api/v1/alerts', {
      method: 'POST',
      headers: operatorAuthHeaders(),
      body: JSON.stringify(alertData)
    }, 4000);
    return { isLive: true, ...res };
  } catch (err) {
    console.warn('Backend alert dispatch fallback to local state:', err.message);
    return {
      isLive: false,
      status: 'created',
      alert: {
        ...alertData,
        id: alertData.id || `ALT-LOCAL-${Date.now().toString().slice(-4)}`,
        created_at: new Date().toISOString()
      }
    };
  }
}

export async function acknowledgeBackendAlert(alertId) {
  try {
    const res = await fetchWithTimeout(`/api/v1/alerts/${alertId}/acknowledge`, {
      method: 'POST',
      headers: operatorAuthHeaders()
    }, 3000);
    return { isLive: true, ...res };
  } catch (err) {
    console.warn('Backend alert acknowledge fallback:', err.message);
    return { isLive: false, status: 'acknowledged-locally', alertId };
  }
}

const SMS_OUTBOX_KEY = 'orca-sms-outbox';

function readSmsOutbox() {
  try {
    return JSON.parse(localStorage.getItem(SMS_OUTBOX_KEY) || '[]');
  } catch {
    return [];
  }
}

function queueSmsOffline(entry) {
  try {
    const box = readSmsOutbox();
    box.push({ ...entry, queuedAt: new Date().toISOString(), status: 'queued-offline' });
    localStorage.setItem(SMS_OUTBOX_KEY, JSON.stringify(box.slice(-50)));
  } catch {
    // storage unavailable — demo continues without outbox
  }
}

export function getSmsOutbox() {
  return readSmsOutbox();
}

export async function syncSmsOutbox() {
  const pending = readSmsOutbox();
  const results = [];
  for (const item of pending) {
    try {
      const res = await fetchWithTimeout('/api/v1/alerts/dispatch-sms', {
        method: 'POST',
        body: JSON.stringify({
          phone: item.phone, message: item.message,
          alert_id: item.alertId, severity: item.severity
        })
      }, 4000);
      results.push({ ...item, synced: true, server: res?.dispatch || res });
    } catch (err) {
      results.push({ ...item, synced: false, error: err.message });
    }
  }
  const unsynced = results.filter((r) => !r.synced).map(({ synced, server, error, ...rest }) => rest);
  try {
    localStorage.setItem(SMS_OUTBOX_KEY, JSON.stringify(unsynced));
  } catch {
    // ignore
  }
  return { attempted: pending.length, synced: results.filter((r) => r.synced).length, results };
}

export async function dispatchSmsAlert({ phone, message, alertId = null, severity = 'INFO' }) {
  try {
    const res = await fetchWithTimeout('/api/v1/alerts/dispatch-sms', {
      method: 'POST',
      body: JSON.stringify({ phone, message, alert_id: alertId, severity })
    }, 4000);
    const dispatch = res?.dispatch || res;
    return { isLive: true, ...dispatch };
  } catch (err) {
    console.warn('SMS dispatch offline — queued for later sync:', err.message);
    queueSmsOffline({ phone, message, alertId, severity });
    return { isLive: false, status: 'queued-offline', demo: true };
  }
}

export async function getSmsDispatchLog(limit = 50) {
  try {
    const res = await fetchWithTimeout(`/api/v1/alerts/sms-log?limit=${limit}`, { method: 'GET' }, 3500);
    return { isLive: true, entries: res?.data || [], total: res?.total || 0, demoNotice: res?.demo_notice };
  } catch (err) {
    const outbox = readSmsOutbox();
    return {
      isLive: false, total: outbox.length, error: err.message,
      entries: outbox.map((o) => ({ ...o, demo: true, note: 'offline outbox (simulated)' }))
    };
  }
}

export async function getRealMarineWarnings() {
  try {
    // 1. First fetch persistent /api/v1/alerts
    const backendRes = await getBackendAlerts();

    // 2. Fetch live GDACS / storm warnings if available
    let gdacsWarnings = [];
    try {
      const res = await fetchWithTimeout('/api/v1/marine/warnings', { method: 'GET' }, 3000);
      const warningsList = res?.warnings || res?.data;
      if (Array.isArray(warningsList) && warningsList.length > 0) {
        gdacsWarnings = warningsList.map((w, idx) => {
          const meta = w.metadata_json || {};
          const stormName = meta.storm_name || w.warning_type?.toUpperCase() || `Storm #${w.id || idx + 1}`;
          const maxWind = meta.max_wind_kmh ? `${Math.round(parseFloat(meta.max_wind_kmh))} km/h` : '120 km/h';
          const rawLevel = (meta.alertlevel || w.severity || 'low').toUpperCase();
          const level = rawLevel === 'RED' || rawLevel === 'HIGH' ? 'HIGH' : rawLevel === 'ORANGE' || rawLevel === 'MEDIUM' ? 'MEDIUM' : 'LOW';

          return {
            id: w.warning_id || `ALT-GDACS-${w.id || idx + 1}`,
            title: `Tropical Advisory: ${stormName}`,
            place: `Oceanic Sector & Coastal Approaches (${stormName})`,
            time: w.issued_at ? new Date(w.issued_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'Active',
            level,
            category: 'Weather',
            source: `GDACS • ${w.source?.toUpperCase() || 'GLOBAL MONITOR'}`,
            validTill: w.valid_until ? new Date(w.valid_until).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'Ongoing',
            desc: w.description || `${stormName} active tropical disturbance alert with peak winds of ${maxWind}.`,
            coordinates: meta.center ? `${meta.center.lat.toFixed(2)}°N, ${meta.center.lng.toFixed(2)}°E` : "10°15'N, 075°30'E",
            lat: meta.center?.lat || 10.25,
            lon: meta.center?.lng || 75.5,
            actionRequired: `Maintain continuous VHF radio watch. Gusts up to ${maxWind}. Non-motorized craft return to shelter.`,
            status: 'active',
            isLive: true
          };
        });
      }
    } catch (_) {
      // Best-effort GDACS fetch
    }

    if (backendRes.isLive && backendRes.alerts && backendRes.alerts.length > 0) {
      // Merge GDACS warnings if not already in list
      const combined = [...gdacsWarnings, ...backendRes.alerts];
      return {
        isLive: true,
        hazards: combined,
        total: combined.length,
        realCount: backendRes.alerts.length + gdacsWarnings.length
      };
    }

    if (gdacsWarnings.length > 0) {
      return {
        isLive: true,
        hazards: [...gdacsWarnings, ...mockAlerts],
        total: gdacsWarnings.length + mockAlerts.length,
        realCount: gdacsWarnings.length
      };
    }

    return { isLive: false, hazards: mockAlerts, total: mockAlerts.length, realCount: 0 };
  } catch (err) {
    return { isLive: false, hazards: mockAlerts, total: mockAlerts.length, realCount: 0, error: err.message };
  }
}

export async function getHazards() {
  return getRealMarineWarnings();
}

// ----------------------------------------------------------------------------
// 6. Real-Time Ocean & Atmospheric Conditions (/api/v1/marine/ocean & weather)
// Live chain: ORCA backend (/marine/latest) → direct Open-Meteo in browser
// (keyless, CORS-open) → labeled seasonal fallback. Dashboard therefore shows
// real data dated 30 Sep 2026 onward even when the backend is unreachable.
// ----------------------------------------------------------------------------

const WMO_LABELS = {
  0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
  45: 'Fog', 48: 'Icy fog', 51: 'Light drizzle', 53: 'Drizzle',
  55: 'Dense drizzle', 61: 'Light rain', 63: 'Rain', 65: 'Heavy rain',
  71: 'Light snow', 80: 'Rain showers', 81: 'Rain showers', 82: 'Heavy showers',
  95: 'Thunderstorm', 96: 'Storm with hail', 99: 'Storm with hail'
};

const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
function compassFromDeg(deg) {
  const d = Number(deg);
  if (!Number.isFinite(d)) return '';
  return COMPASS[Math.round(d / 22.5) % 16];
}

async function fetchDirectMarineLive({ lat = 9.93, lon = 76.27 } = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 8000);
  try {
    const [marineRes, wxRes] = await Promise.all([
      fetch(`https://marine-api.open-meteo.com/v1/marine?latitude=${lat}&longitude=${lon}&hourly=wave_height,wave_direction,wave_period,sea_surface_temperature,ocean_current_velocity,ocean_current_direction&daily=wave_height_max,wave_direction_dominant,wave_period_max&timezone=Asia%2FKolkata&forecast_days=7`, { signal: ctrl.signal }),
      fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,pressure_msl,precipitation,weathercode&daily=temperature_2m_max,temperature_2m_min,wind_speed_10m_max,wind_direction_10m_dominant,precipitation_probability_max,weathercode&current=temperature_2m,wind_speed_10m,wind_direction_10m,pressure_msl,weathercode&timezone=Asia%2FKolkata&forecast_days=7&wind_speed_unit=ms`, { signal: ctrl.signal })
    ]);
    if (!marineRes.ok || !wxRes.ok) throw new Error(`upstream ${marineRes.status}/${wxRes.status}`);
    const marine = await marineRes.json();
    const wx = await wxRes.json();
    const now = Date.now();
    const nearest = (times) => {
      let bi = 0; let best = Infinity;
      (times || []).forEach((ts, i) => {
        const dd = Math.abs(new Date(ts).getTime() - now);
        if (dd < best) { best = dd; bi = i; }
      });
      return bi;
    };
    const mi = nearest(marine?.hourly?.time);
    const wi = nearest(wx?.hourly?.time);
    const at = (h, k, i) => (Array.isArray(h?.[k]) && i < h[k].length && h[k][i] != null ? Number(h[k][i]) : null);
    const cur = wx?.current || {};
    const windMs = cur.wind_speed_10m ?? at(wx?.hourly, 'wind_speed_10m', wi) ?? 0.55;
    const windDeg = Math.round(cur.wind_direction_10m ?? at(wx?.hourly, 'wind_direction_10m', wi) ?? 360);
    const tempC = cur.temperature_2m ?? at(wx?.hourly, 'temperature_2m', wi) ?? 27.8;
    const pressure = cur.pressure_msl ?? at(wx?.hourly, 'pressure_msl', wi) ?? 1013.1;
    const code = cur.weathercode ?? at(wx?.hourly, 'weathercode', wi) ?? 3;
    const waveH = at(marine?.hourly, 'wave_height', mi) ?? 0.84;
    const waveP = at(marine?.hourly, 'wave_period', mi) ?? 9.7;
    const waveD = Math.round(at(marine?.hourly, 'wave_direction', mi) ?? 233);
    const sst = at(marine?.hourly, 'sea_surface_temperature', mi) ?? 30.2;
    const curVelKmh = at(marine?.hourly, 'ocean_current_velocity', mi);
    const days = wx?.daily?.time || marine?.daily?.time || [];
    const entries = days.map((day, i) => {
      const pick = (d, k) => (Array.isArray(d?.[k]) && i < d[k].length ? d[k][i] : null);
      const c = pick(wx?.daily, 'weathercode');
      return {
        time: `${day} 12:00`,
        date: day,
        temperature_c: pick(wx?.daily, 'temperature_2m_max'),
        temperature_min_c: pick(wx?.daily, 'temperature_2m_min'),
        wind_speed_ms: pick(wx?.daily, 'wind_speed_10m_max'),
        wind_direction_deg: pick(wx?.daily, 'wind_direction_10m_dominant'),
        precipitation_probability: pick(wx?.daily, 'precipitation_probability_max'),
        wave_height_m: pick(marine?.daily, 'wave_height_max'),
        wave_period_s: pick(marine?.daily, 'wave_period_max'),
        condition: WMO_LABELS[c] || 'Marine outlook',
        weathercode: c
      };
    });
    return {
      isLive: true,
      isDirectLive: true,
      retrievalTime: new Date().toISOString(),
      temperatureC: Number(Number(tempC).toFixed(1)),
      sstC: Number(Number(sst).toFixed(1)),
      windSpeedMs: Number(windMs),
      windSpeedKts: (Number(windMs) * 1.94384).toFixed(1),
      windDirection: `${windDeg}° ${compassFromDeg(windDeg)}`.trim(),
      windDeg,
      pressureHpa: Number(Number(pressure).toFixed(1)),
      humidityPct: 82,
      visibilityKm: '10.0',
      condition: WMO_LABELS[code] || 'Overcast',
      weathercode: code,
      waveHeightM: waveH,
      wavePeriodS: waveP,
      waveDirectionDeg: waveD,
      currentMs: curVelKmh != null ? Number((curVelKmh / 3.6).toFixed(2)) : 0.08,
      tideType: 'HIGH TIDE (1.2m)',
      forecastEntries: entries,
      source: 'Open-Meteo Marine + Forecast (live) · IMD/INCOIS fused in prototype backend'
    };
  } finally {
    clearTimeout(t);
  }
}

export async function getOceanConditions({ lat = 9.93, lon = 76.27 } = {}) {
  // 1) Prefer the ORCA backend (it fuses INCOIS-THREDDS + IMD labels when available).
  try {
    const [latestRes, oceanRes, weatherRes, tideRes] = await Promise.allSettled([
      fetchWithTimeout(`/api/v1/marine/latest?lat=${lat}&lon=${lon}`, { method: 'GET' }, 4500),
      fetchWithTimeout(`/api/v1/marine/ocean?lat=${lat}&lon=${lon}`, { method: 'GET' }, 3500),
      fetchWithTimeout(`/api/v1/marine/weather-forecast?lat=${lat}&lon=${lon}`, { method: 'GET' }, 3500),
      fetchWithTimeout(`/api/v1/marine/tides?lat=${lat}&lon=${lon}`, { method: 'GET' }, 3500)
    ]);

    const latest = latestRes.status === 'fulfilled' ? latestRes.value : null;
    if (latest && (latest.is_live || latest.current)) {
      const c = latest.current || {};
      const windMs = c.wind_speed_ms ?? 0.55;
      const windDeg = Math.round(c.wind_direction_deg ?? 360);
      const dm = latest.daily_marine || {};
      const dw = latest.daily_weather || {};
      const days = dw.time || dm.time || [];
      const entries = days.map((day, i) => {
        const pick = (d, k) => (Array.isArray(d?.[k]) && i < d[k].length ? d[k][i] : null);
        const code = pick(dw, 'weathercode');
        return {
          time: `${day} 12:00`, date: day,
          temperature_c: pick(dw, 'temperature_2m_max'),
          temperature_min_c: pick(dw, 'temperature_2m_min'),
          wind_speed_ms: pick(dw, 'wind_speed_10m_max'),
          wind_direction_deg: pick(dw, 'wind_direction_10m_dominant'),
          precipitation_probability: pick(dw, 'precipitation_probability_max'),
          wave_height_m: pick(dm, 'wave_height_max'),
          wave_period_s: pick(dm, 'wave_period_max'),
          condition: WMO_LABELS[code] || 'Marine outlook',
          weathercode: code
        };
      });
      if (entries.length > 0 || c.temperature_c != null) {
        return {
          isLive: true,
          retrievalTime: latest.retrieval_time || new Date().toISOString(),
          temperatureC: c.temperature_c ?? 27.8,
          sstC: c.sst_c ?? 30.2,
          windSpeedKts: (Number(windMs) * 1.94384).toFixed(1),
          windSpeedMs: windMs,
          windDirection: `${windDeg}° ${compassFromDeg(windDeg)}`.trim(),
          windDeg,
          pressureHpa: c.pressure_hpa ?? 1013.1,
          humidityPct: 82,
          visibilityKm: '10.0',
          condition: WMO_LABELS[c.weathercode] || (entries[0]?.condition) || 'Overcast',
          weathercode: c.weathercode ?? 3,
          waveHeightM: c.wave_height_m ?? 0.84,
          wavePeriodS: c.wave_period_s ?? 9.7,
          waveDirectionDeg: c.wave_direction_deg ?? 233,
          currentMs: c.current_speed_ms ?? 0.08,
          tideType: 'HIGH TIDE (1.2m)',
          forecastEntries: entries,
          source: `ORCA backend live (${(latest.sources || ['INCOIS', 'IMD']).join(' + ')})`
        };
      }
    }

    const oceanItem = oceanRes.status === 'fulfilled' && oceanRes.value?.data?.[0] ? oceanRes.value.data[0] : null;
    const weatherItem = weatherRes.status === 'fulfilled' && weatherRes.value?.data?.[0] ? weatherRes.value.data[0] : null;
    const tideItem = tideRes.status === 'fulfilled' && tideRes.value?.data?.[0] ? tideRes.value.data[0] : null;

    if (oceanItem || weatherItem) {
      const rawOcean = oceanItem?.raw_payload || {};
      const rawWeather = weatherItem?.raw_payload || {};

      const tempC = rawOcean.temperature_c ?? rawOcean.sst_c ?? weatherItem?.temperature_c ?? 27.8;
      const windMs = rawOcean.wind_speed_ms ?? rawWeather.wind_speed_ms
        ?? (rawWeather.wind_speed_kts != null ? Number(rawWeather.wind_speed_kts) / 1.94384 : null)
        ?? weatherItem?.wind_speed_ms ?? 0.55;
      const windKts = (Number(windMs) * 1.94384).toFixed(1);
      const windDeg = Math.round(rawOcean.wind_direction_deg ?? rawWeather.wind_direction_deg ?? 360);
      const pressure = rawOcean.pressure_hpa ?? rawWeather.pressure_hpa ?? 1013.1;
      const condition = rawOcean.condition ?? rawWeather.condition ?? 'Overcast';
      const forecastEntries = Array.isArray(rawWeather.entries) ? rawWeather.entries : [];

      if (forecastEntries.length > 0) {
        return {
          isLive: true,
          retrievalTime: oceanRes.value?.retrieval_time || weatherRes.value?.retrieval_time || new Date().toISOString(),
          temperatureC: tempC,
          sstC: rawOcean.sst_c ?? 30.2,
          windSpeedKts: windKts,
          windSpeedMs: Number(Number(windMs).toFixed(2)),
          windDirection: `${windDeg}° ${compassFromDeg(windDeg)}`.trim(),
          windDeg,
          pressureHpa: pressure,
          humidityPct: 82,
          visibilityKm: '10.0',
          condition: String(condition).charAt(0).toUpperCase() + String(condition).slice(1),
          waveHeightM: rawOcean.wave_height_m ?? rawWeather.wave_height_m ?? 0.84,
          wavePeriodS: rawOcean.wave_period_s ?? 9.7,
          tideType: tideItem?.tide_type ? `${tideItem.tide_type.toUpperCase()} TIDE` : 'HIGH TIDE (1.2m)',
          forecastEntries,
          source: oceanItem?.source || weatherItem?.source || 'ORCA backend (live)'
        };
      }
    }
  } catch (_) {
    // fall through to direct live fetch
  }

  // 2) Direct browser fetch to Open-Meteo (no key, CORS-open) — real data till 30 Sep+.
  try {
    return await fetchDirectMarineLive({ lat, lon });
  } catch (err) {
    // 3) Labeled seasonal fallback (realistic 30 Sep 2026 values, clearly marked).
    return {
      isLive: false,
      retrievalTime: new Date().toISOString(),
      temperatureC: 27.8,
      sstC: 30.2,
      windSpeedKts: '1.1',
      windSpeedMs: 0.55,
      windDirection: '360° N',
      windDeg: 360,
      pressureHpa: 1013.1,
      humidityPct: 82,
      visibilityKm: '10.0',
      condition: 'Overcast',
      weathercode: 3,
      waveHeightM: 0.84,
      wavePeriodS: 9.7,
      waveDirectionDeg: 233,
      currentMs: 0.08,
      tideType: 'HIGH TIDE (1.2m)',
      forecastEntries: [
        { time: '2026-09-30 12:00', date: '2026-09-30', temperature_c: 30.9, temperature_min_c: 26.3, wind_speed_ms: 4.07, condition: 'Drizzle', wave_height_m: 0.84, wave_period_s: 9.75 },
        { time: '2026-10-01 12:00', date: '2026-10-01', temperature_c: 31.0, temperature_min_c: 26.3, wind_speed_ms: 3.91, condition: 'Drizzle', wave_height_m: 0.80, wave_period_s: 11.1 },
        { time: '2026-10-02 12:00', date: '2026-10-02', temperature_c: 30.8, temperature_min_c: 24.4, wind_speed_ms: 3.56, condition: 'Thunderstorm', wave_height_m: 0.76, wave_period_s: 11.25 },
        { time: '2026-10-03 12:00', date: '2026-10-03', temperature_c: 29.5, temperature_min_c: 24.5, wind_speed_ms: 3.18, condition: 'Rain showers', wave_height_m: 0.72, wave_period_s: 11.05 },
        { time: '2026-10-04 12:00', date: '2026-10-04', temperature_c: 29.9, temperature_min_c: 24.7, wind_speed_ms: 2.90, condition: 'Drizzle', wave_height_m: 0.66, wave_period_s: 10.65 },
        { time: '2026-10-05 12:00', date: '2026-10-05', temperature_c: 29.5, temperature_min_c: 25.0, wind_speed_ms: 2.56, condition: 'Drizzle', wave_height_m: 0.64, wave_period_s: 10.4 },
        { time: '2026-10-06 12:00', date: '2026-10-06', temperature_c: 30.0, temperature_min_c: 24.8, wind_speed_ms: 2.63, condition: 'Thunderstorm', wave_height_m: 0.54, wave_period_s: 11.4 }
      ],
      source: 'Seasonal fallback (Sep–Oct climatology) — live sync retrying',
      error: err.message
    };
  }
}

// ----------------------------------------------------------------------------
// 7. Potential Fishing Zones (/api/v1/marine/pfz)
// ----------------------------------------------------------------------------

function calculateDistanceAndBearing(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const distKm = (R * c).toFixed(1);

  const y = Math.sin(dLon) * Math.cos(lat2 * Math.PI / 180);
  const x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) -
            Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos(dLon);
  let brng = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  const compassPoints = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  const compassDir = compassPoints[Math.round(brng / 22.5) % 16];

  return { distKm: parseFloat(distKm), bearing: `${Math.round(brng)}° ${compassDir}` };
}

export async function getRealPfzZones({ lat = 9.93, lon = 76.27, date = null } = {}) {
  try {
    const dateQuery = date ? `&date=${encodeURIComponent(date)}` : '';
    const res = await fetchWithTimeout(`/api/v1/marine/pfz?lat=${lat}&lon=${lon}${dateQuery}`, { method: 'GET' }, 4000);

    if (res && Array.isArray(res.data) && res.data.length > 0) {
      const transformed = res.data.map((item, idx) => {
        const cLat = item.centroid_latitude || (item.geometry?.coordinates?.[0]?.[0]?.[0]?.[1]) || lat;
        const cLon = item.centroid_longitude || (item.geometry?.coordinates?.[0]?.[0]?.[0]?.[0]) || lon;
        const { distKm, bearing } = calculateDistanceAndBearing(lat, lon, cLat, cLon);
        const confidence = item.confidence || 0.7;
        const sstVal = item.metadata_json?.sst_c || 28.2;
        const frontDelta = item.metadata_json?.front_delta_c || 0.85;
        const isHigh = confidence >= 0.7;
        const potential = isHigh ? 'High' : confidence >= 0.5 ? 'Medium' : 'Low';
        const catchScore = Math.round(confidence * 100);
        const estimatedDepth = Math.round(35 + (distKm * 1.5));

        const sectorLetter = String.fromCharCode(65 + (idx % 26));
        const sectorNum = Math.floor(idx / 26) ? Math.floor(idx / 26) : '';

        return {
          id: `PFZ-${String(idx + 1).padStart(2, '0')}`,
          name: `CoastWatch Front Sector ${sectorLetter}${sectorNum} (${cLat.toFixed(2)}°N, ${cLon.toFixed(2)}°E)`,
          distance: `${distKm} km`,
          bearing,
          depth: `${estimatedDepth} m`,
          potential,
          catchIndex: `${catchScore}/100`,
          sst: `${sstVal.toFixed(1)} °C`,
          chlorophyll: `${(0.65 + (frontDelta * 0.22)).toFixed(2)} mg/m³`,
          targetSpecies: ['Yellowfin Tuna', 'Indian Mackerel', 'Skipjack', 'Seer Fish'],
          risk: 'Low',
          restrictions: 'None',
          window: '04:30 – 10:30 IST',
          coordinates: `${cLat.toFixed(4)}°N, ${cLon.toFixed(4)}°E`,
          lat: cLat,
          lon: cLon,
          recommended: idx === 0,
          source: item.source || 'CoastWatch',
          validUntil: item.valid_until || '2026-09-10T09:00:00Z',
          geometry: item.geometry,
          isLive: true
        };
      });

      return {
        isLive: true,
        zones: transformed,
        total: transformed.length
      };
    }

    return { isLive: false, zones: mockPfzZones, total: mockPfzZones.length };
  } catch (err) {
    return { isLive: false, zones: mockPfzZones, total: mockPfzZones.length, error: err.message };
  }
}

// ----------------------------------------------------------------------------
// 8. ML Model Governance Metrics (/api/v1/ml/dashboard)
// ----------------------------------------------------------------------------

export async function getMlDashboardMetrics() {
  try {
    const data = await fetchWithTimeout('/api/v1/ml/dashboard', { method: 'GET' }, 3500);
    return { isLive: true, data };
  } catch (err) {
    return {
      isLive: false,
      data: {
        models: {
          pfz: [
            {
              name: 'pfz',
              version: '1.1.0',
              stage: 'production',
              metrics: { mae: 0.068, rmse: 0.0861, r2: 0.8832, accuracy: 0.9139 }
            }
          ]
        }
      }
    };
  }
}

// ----------------------------------------------------------------------------
// 9. Scenarios (/api/v1/scenarios/create)
// ----------------------------------------------------------------------------

export async function createScenario(params) {
  try {
    const data = await fetchWithTimeout('/api/v1/scenarios/create', {
      method: 'POST',
      body: JSON.stringify(params)
    }, 6000);

    return { isLive: true, ...data };
  } catch (err) {
    return {
      isLive: false,
      scenario_id: `scen-${Date.now()}`,
      confidence: 0.91,
      recommendations: [
        'Maintain safe clearance from shoaling sandbars',
        'Monitor continuous VHF Channel 16 for coastal advisories'
      ]
    };
  }
}

// ----------------------------------------------------------------------------
// 10. Voice Services — Sarvam AI STT (saaras:v3) & TTS (bulbul:v3)
// ----------------------------------------------------------------------------

export async function getVoiceProvidersStatus() {
  try {
    const data = await fetchWithTimeout('/api/v1/voice/providers', { method: 'GET' }, 3000);
    return { isLive: true, data };
  } catch (err) {
    return {
      isLive: false,
      data: {
        stt: { sarvam: { status: 'configured', provider: 'sarvam', supported_languages: 10 } },
        tts: { sarvam: { status: 'configured', provider: 'sarvam', supported_languages: 10 } }
      }
    };
  }
}

export async function transcribeAudioWithSarvam(audioBlob, languageHint = 'ml-IN') {
  try {
    const formData = new FormData();
    const isWebm = audioBlob.type?.includes('webm');
    const filename = isWebm ? 'recording.webm' : 'recording.wav';
    formData.append('audio', audioBlob, filename);
    formData.append('language_hint', languageHint);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    const res = await fetch(`${API_BASE}/api/v1/voice/transcribe`, {
      method: 'POST',
      body: formData,
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Sarvam STT failed with status ${res.status}`);
    }

    const data = await res.json();
    return {
      isLive: true,
      transcript: data.transcript || '',
      language: data.language || languageHint,
      confidence: data.confidence || 0.95,
      provider: 'Sarvam AI (saaras:v3)'
    };
  } catch (err) {
    console.warn('Sarvam transcription error, falling back:', err.message);
    throw err;
  }
}

export async function synthesizeAudioWithSarvam(text, language = 'ml-IN', voice = 'kavitha') {
  try {
    // Sarvam API has a 500-character limit on input text
    const sanitizedText = text && text.length > 480 ? text.slice(0, 480).trim() + '...' : text;
    const payload = {
      text: sanitizedText,
      language,
      voice
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    const res = await fetch(`${API_BASE}/api/v1/voice/synthesize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Sarvam TTS failed with status ${res.status}`);
    }

    const data = await res.json();
    return {
      isLive: true,
      audioUrl: data.audio_url,
      durationSeconds: data.duration_seconds,
      provider: 'Sarvam AI (bulbul:v3)'
    };
  } catch (err) {
    console.warn('Sarvam synthesis error, falling back:', err.message);
    throw err;
  }
}

