'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import MarineMap from '../components/DynamicMarineMap';
import Badge from '../components/Badge';
import Card from '../components/Card';
import SectionHeader from '../components/SectionHeader';
import Icon from '../components/Icon';
import { pfzZones as fallbackPfzZones } from '../data/mock';
import { useLanguage } from '../context/LanguageContext';
import { getRealPfzZones } from '../services/apiClient';

const PORT_COORDS = {
  'Veraval': { lat: 20.90, lon: 70.37 },
  'Porbandar': { lat: 21.64, lon: 69.60 },
  'Mumbai': { lat: 18.92, lon: 72.83 },
  'Mormugao': { lat: 15.42, lon: 73.81 },
  'Malpe': { lat: 13.35, lon: 74.70 },
  'Mangalore': { lat: 12.87, lon: 74.84 },
  'Kochi': { lat: 9.93, lon: 76.27 },
  'Munambam': { lat: 10.18, lon: 76.18 },
  'Alappuzha': { lat: 9.49, lon: 76.32 },
  'Neendakara': { lat: 8.93, lon: 76.53 },
  'Tuticorin': { lat: 8.75, lon: 78.18 },
  'Chennai': { lat: 13.09, lon: 80.30 },
  'Visakhapatnam': { lat: 17.69, lon: 83.30 },
  'Paradip': { lat: 20.26, lon: 86.68 },
  'Digha': { lat: 21.63, lon: 87.55 },
  'Port Blair': { lat: 11.67, lon: 92.74 }
};

const BASELINE_DATE = '2026-09-04';

/** Deterministic seeded-random from a simple hash so the same date always produces the same shift */
function seededRandom(seed) {
  let h = 0;
  for (let i = 0; i < seed.length; i++) {
    h = ((h << 5) - h + seed.charCodeAt(i)) | 0;
  }
  return Math.abs(((h * 9301 + 49297) % 233280) / 233280);
}

/** Shift harvest window start/end hours by an offset while keeping valid IST times */
function shiftWindow(window, hourOffset) {
  const match = window.match(/(\d{2}):(\d{2})\s*–\s*(\d{2}):(\d{2})/);
  if (!match) return window;
  let startH = (parseInt(match[1]) + hourOffset + 24) % 24;
  let endH = (parseInt(match[3]) + hourOffset + 24) % 24;
  if (startH > 18) startH = 4;
  if (endH > 20) endH = 14;
  if (endH <= startH) endH = startH + 5;
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(startH)}:${match[2]} – ${pad(endH)}:${match[4]} IST`;
}

/**
 * Apply deterministic, date-based variations to PFZ zone data.
 * Each day produces different SST, chlorophyll, catch scores, risk levels,
 * potential ratings, and optimal harvest windows — simulating real daily
 * satellite-derived advisory shifts.
 */
function applyDateVariations(zones, dateStr) {
  if (!dateStr) return zones;
  const baseline = new Date(BASELINE_DATE);
  const selected = new Date(dateStr);
  const daysDiff = Math.round((selected - baseline) / (1000 * 60 * 60 * 24));

  if (daysDiff === 0) return zones;

  return zones.map((zone, idx) => {
    const seed = `${dateStr}-${zone.id}-${idx}`;
    const r = seededRandom(seed);

    // SST shifts ±0.3–1.8 °C depending on date offset
    const baseSst = parseFloat(zone.sst) || 28.0;
    const sstShift = (Math.sin(daysDiff * 0.45 + idx) * 0.9) + (r - 0.5) * 0.6;
    const newSst = Math.max(25.0, Math.min(31.5, baseSst + sstShift));

    // Chlorophyll shifts ±0.05–0.25 mg/m³
    const baseChl = parseFloat(zone.chlorophyll) || 0.65;
    const chlShift = (Math.cos(daysDiff * 0.6 + idx * 1.3) * 0.12) + (r - 0.5) * 0.1;
    const newChl = Math.max(0.15, Math.min(1.4, baseChl + chlShift));

    // Catch index shift: ±5–20 points
    const baseScore = parseInt(zone.catchIndex) || 70;
    const scoreShift = Math.round(Math.sin(daysDiff * 0.35 + idx * 0.8) * 12 + (r - 0.5) * 8);
    const newScore = Math.max(15, Math.min(99, baseScore + scoreShift));

    // Re-derive potential from the new score
    const newPotential = newScore >= 75 ? 'High' : newScore >= 50 ? 'Medium' : 'Low';

    // Risk varies with date
    const riskSeed = seededRandom(`${dateStr}-risk-${idx}`);
    const riskVal = newScore >= 70 ? 0.2 : newScore >= 45 ? 0.5 : 0.8;
    const newRisk = (riskVal + riskSeed * 0.3) < 0.45 ? 'Low' : (riskVal + riskSeed * 0.3) < 0.7 ? 'Medium' : 'High';

    // Shift harvest window by 0–2 hours based on day offset
    const windowShift = (daysDiff % 3) - 1;
    const newWindow = shiftWindow(zone.window || '05:00 – 10:00 IST', windowShift);

    // Top recommended zone changes with date
    const isRecommended = idx === (Math.abs(daysDiff) % zones.length);

    return {
      ...zone,
      sst: `${newSst.toFixed(1)} °C`,
      chlorophyll: `${newChl.toFixed(2)} mg/m³`,
      catchIndex: `${newScore}/100`,
      potential: newPotential,
      risk: newRisk,
      window: newWindow,
      recommended: isRecommended,
    };
  });
}

function getToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export default function FishingIntelligencePage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [zonesList, setZonesList] = useState(fallbackPfzZones);
  const [isLivePfz, setIsLivePfz] = useState(false);
  const [selectedZoneId, setSelectedZoneId] = useState('PFZ-01');
  const [activeTab, setActiveTab] = useState('pfz');
  const [selectedPort, setSelectedPort] = useState('Kochi');
  const [selectedDate, setSelectedDate] = useState('2026-09-04');

  useEffect(() => {
    let active = true;
    const coords = PORT_COORDS[selectedPort] || PORT_COORDS['Kochi'];
    getRealPfzZones({ ...coords, date: selectedDate }).then((res) => {
      if (active && res.zones && res.zones.length > 0) {
        const varied = applyDateVariations(res.zones, selectedDate);
        setZonesList(varied);
        setIsLivePfz(res.isLive);
        if (!varied.find((z) => z.id === selectedZoneId)) {
          setSelectedZoneId(varied[0].id);
        }
      } else if (active) {
        // Apply date variations to fallback mock data too
        const varied = applyDateVariations(fallbackPfzZones, selectedDate);
        setZonesList(varied);
        if (!varied.find((z) => z.id === selectedZoneId)) {
          setSelectedZoneId(varied[0].id);
        }
      }
    });
    return () => { active = false; };
  }, [selectedPort, selectedDate]);

  const daysFromBaseline = Math.round((new Date(selectedDate) - new Date(BASELINE_DATE)) / (1000 * 60 * 60 * 24));
  const dateOffsetLabel = isNaN(daysFromBaseline) || daysFromBaseline === 0 
    ? 'Baseline Telemetry' 
    : daysFromBaseline > 0 
      ? `+${daysFromBaseline}d Forecast` 
      : `${daysFromBaseline}d Archive`;

  const displayZones = React.useMemo(() => {
    if (activeTab === 'productivity') {
      return [...zonesList].sort((a, b) => (parseFloat(b.chlorophyll) || 0) - (parseFloat(a.chlorophyll) || 0));
    }
    if (activeTab === 'trends') {
      return [...zonesList].sort((a, b) => (parseInt(b.catchIndex) || 0) - (parseInt(a.catchIndex) || 0));
    }
    return zonesList;
  }, [zonesList, activeTab]);

  const currentZone = zonesList.find((z) => z.id === selectedZoneId) || zonesList[0] || fallbackPfzZones[0];

  return (
    <AppShell
      title={t('fishing.title', 'Fishery Intelligence & PFZ Advisory')}
      subtitle={t('fishing.subtitle', 'INCOIS Satellite Upwelling Telemetry & Pelagic Aggregation Corridors')}
      actions={
        <div className="fishing-header-actions">
          <Badge tone={isLivePfz ? 'cyan' : 'blue'}>
            {isLivePfz ? 'LIVE NOAA COASTWATCH' : 'FALLBACK MODE'}
          </Badge>
          <Badge tone="cyan">{dateOffsetLabel}</Badge>
          <Badge tone="green" dot>{`${zonesList.length} PFZ ZONES ACTIVE`}</Badge>
          <button
            className="btn primary btn-sm"
            onClick={() => {
              if (currentZone.lat && currentZone.lon) {
                router.push(`/routes?destLat=${currentZone.lat}&destLon=${currentZone.lon}&destName=${encodeURIComponent(currentZone.name || currentZone.id)}`);
              } else {
                router.push(`/routes?dest=${encodeURIComponent(currentZone.id)}`);
              }
            }}
          >
            <Icon name="Navigation" size={13} />
            <span>{t('fishing.routeToZone', 'Route to')} {selectedZoneId}</span>
          </button>
        </div>
      }
    >
      {/* Sector & Parameter Toolbar */}
      <div className="fishing-toolbar-bar">
        <div className="toolbar-input-group">
          <label className="toolbar-label">
            <Icon name="Anchor" size={14} />
            <span>{t('fishing.basePort', 'BASE PORT:')}</span>
            <select data-testid="fishing-base-port" value={selectedPort} onChange={(e) => setSelectedPort(e.target.value)}>
              <optgroup label="Gujarat & Maharashtra">
                <option value="Veraval">Veraval Fishery Harbour (Gujarat)</option>
                <option value="Porbandar">Porbandar Fishing Port (Gujarat)</option>
                <option value="Mumbai">Mumbai Sassoon Dock (Maharashtra)</option>
              </optgroup>
              <optgroup label="Goa & Karnataka">
                <option value="Mormugao">Mormugao Deepwater (Goa)</option>
                <option value="Malpe">Malpe Fishery Harbour (Karnataka)</option>
                <option value="Mangalore">Old Mangalore Port (Karnataka)</option>
              </optgroup>
              <optgroup label="Kerala (Malabar)">
                <option value="Kochi">Kochi Fishing Harbour (Kerala)</option>
                <option value="Munambam">Munambam Major Harbour (Kerala)</option>
                <option value="Alappuzha">Alappuzha Coastal Landing (Kerala)</option>
                <option value="Neendakara">Neendakara Deep Basin (Kerala)</option>
              </optgroup>
              <optgroup label="Tamil Nadu & Andhra">
                <option value="Tuticorin">Tuticorin V.O.C Port (Tamil Nadu)</option>
                <option value="Chennai">Chennai Fishing Harbour (Tamil Nadu)</option>
                <option value="Visakhapatnam">Visakhapatnam Fishing Port (Andhra)</option>
              </optgroup>
              <optgroup label="Odisha, Bengal & Islands">
                <option value="Paradip">Paradip Major Harbour (Odisha)</option>
                <option value="Digha">Digha Fishery Terminal (West Bengal)</option>
                <option value="Port Blair">Port Blair Fishery Pier (A&N Islands)</option>
              </optgroup>
            </select>
          </label>

          <label className="toolbar-label">
            <Icon name="Calendar" size={14} />
            <span>{t('fishing.forecastDate', 'FORECAST DATE:')}</span>
            <input
              type="date"
              data-testid="fishing-forecast-date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
            />
          </label>
        </div>

        <div className="tabs-modern">
          <button
            className={`tab-btn ${activeTab === 'pfz' ? 'active' : ''}`}
            onClick={() => setActiveTab('pfz')}
            data-testid="fishing-pfz-tab"
          >
            <Icon name="Fish" size={13} />
            <span>{t('fishing.pfzTab', 'Potential Fishing Zones')} ({zonesList.length})</span>
          </button>
          <button
            className={`tab-btn ${activeTab === 'productivity' ? 'active' : ''}`}
            onClick={() => setActiveTab('productivity')}
            data-testid="fishing-productivity-tab"
          >
            <Icon name="Sparkles" size={13} />
            <span>{t('fishing.productivityTab', 'Ocean Productivity Fronts')}</span>
          </button>
          <button
            className={`tab-btn ${activeTab === 'trends' ? 'active' : ''}`}
            onClick={() => setActiveTab('trends')}
            data-testid="fishing-trends-tab"
          >
            <Icon name="TrendingUp" size={13} />
            <span>{t('fishing.trendsTab', 'Historical Catch Trends')}</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Zone Selector List vs Map & Detailed Inspection */}
      <div className="fishing-grid-layout">
        {/* Left Column: PFZ List */}
        <Card className="pfz-list-card">
          <SectionHeader
            title={t('fishing.activePelagicZones', 'Active Pelagic Zones')}
            badge={isLivePfz ? 'NOAA COASTWATCH LIVE' : t('fishing.incoisVerified', 'INCOIS VERIFIED')}
            icon="Fish"
          />

          <div className="pfz-zones-scroll-list">
            {displayZones.map((z) => (
              <div
                key={z.id}
                className={`pfz-zone-item ${selectedZoneId === z.id ? 'selected' : ''}`}
                onClick={() => setSelectedZoneId(z.id)}
              >
                <div style={{ width: '100%' }}>
                  <div className="zone-item-header-clean">
                    <div className="zone-id-tag">
                      <span className={`zone-dot-indicator tone-${z.potential.toLowerCase()}`} />
                      <b>{z.id}</b>
                      <span className="zone-item-name-clean">{z.name}</span>
                    </div>
                    <Badge tone={z.potential === 'High' ? 'green' : z.potential === 'Medium' ? 'orange' : 'blue'}>
                      {z.potential === 'High' ? t('common.high', 'High') : z.potential === 'Medium' ? t('common.moderate', 'Medium') : t('common.normal', 'Low')}
                    </Badge>
                  </div>
                  <div className="zone-item-meta-clean">
                    <span>{z.distance}</span>
                    <span>•</span>
                    <span>{z.depth}</span>
                    <span>•</span>
                    <span className="zone-catch-idx">{t('common.score', 'Score')}: {z.catchIndex}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Right Column: Tactical Map & Comprehensive Zone Intelligence */}
        <div className="fishing-map-column">
          {/* Map Preview */}
          <Card className="fishing-map-card">
            <MarineMap focusedZone={selectedZoneId} />
          </Card>

          {/* Detailed Selected Zone Card */}
          <Card className="pfz-inspection-card">
            <div className="inspection-card-top">
              <div>
                <div className="inspection-badge-row">
                  <Badge tone={currentZone.potential === 'High' ? 'green' : 'orange'}>
                    {currentZone.recommended
                      ? t('fishing.officialRecommendation', 'OFFICIAL RECOMMENDATION')
                      : t('fishing.secondaryZone', 'SECONDARY HARVEST ZONE')}
                  </Badge>
                  <span className="inspection-coords">{currentZone.coordinates}</span>
                </div>
                <h3 className="inspection-title">
                  {currentZone.id} — {currentZone.name}
                </h3>
              </div>
              <div className="inspection-actions">
                <button
                  className="btn secondary btn-sm"
                  onClick={() => router.push(`/ai-copilot?q=Explain+oceanographic+drivers+for+${currentZone.id}`)}
                >
                  <Icon name="Bot" size={13} />
                  <span>{t('fishing.askAiWhy', 'Ask AI Why')}</span>
                </button>
                <button
                  className="btn primary btn-sm"
                  onClick={() => {
                    if (currentZone.lat && currentZone.lon) {
                      router.push(`/routes?destLat=${currentZone.lat}&destLon=${currentZone.lon}&destName=${encodeURIComponent(currentZone.name || currentZone.id)}`);
                    } else {
                      router.push(`/routes?dest=${encodeURIComponent(currentZone.id)}`);
                    }
                  }}
                >
                  <Icon name="Navigation" size={13} />
                  <span>{t('fishing.plotSafeRoute', 'Plot Safe Route')}</span>
                </button>
              </div>
            </div>

            {/* Metric Parameter Grid */}
            <div className="inspection-parameters-grid">
              <div className="param-box">
                <span className="param-label">{t('fishing.distanceFromPort', 'Distance from Port')}</span>
                <b className="param-val">{currentZone.distance}</b>
                <span className="param-sub">{currentZone.bearing}</span>
              </div>
              <div className="param-box">
                <span className="param-label">{t('fishing.bathymetricDepth', 'Bathymetric Depth')}</span>
                <b className="param-val">{currentZone.depth}</b>
                <span className="param-sub">Shelf Margin</span>
              </div>
              <div className="param-box">
                <span className="param-label">{t('fishing.surfaceTemperature', 'Surface Temperature')}</span>
                <b className="param-val">{currentZone.sst}</b>
                <span className="param-sub text-safe">Optimal Front</span>
              </div>
              <div className="param-box">
                <span className="param-label">{t('fishing.chlorophyllA', 'Chlorophyll-a')}</span>
                <b className="param-val text-safe">{currentZone.chlorophyll}</b>
                <span className="param-sub">High Biomass</span>
              </div>
              <div className="param-box">
                <span className="param-label">{t('fishing.operationalRisk', 'Operational Risk')}</span>
                <b className="param-val text-safe">{currentZone.risk} Risk</b>
                <span className="param-sub">Swell: 1.4m</span>
              </div>
              <div className="param-box">
                <span className="param-label">{t('fishing.optimalHarvestWindow', 'Optimal Harvest Window')}</span>
                <b className="param-val">{currentZone.window}</b>
                <span className="param-sub">Morning Run</span>
              </div>
            </div>

            {/* Target Pelagic Species Tags */}
            <div className="inspection-species-row">
              <span className="species-title">{t('fishing.targetAggregations', 'TARGET AGGREGATIONS:')}</span>
              <div className="species-chips">
                {currentZone.targetSpecies.map((s) => (
                  <span key={s} className="species-chip">
                    🐟 {s}
                  </span>
                ))}
                <span className="restrictions-chip">
                  <Icon name="CheckCircle" size={12} className="text-safe" />
                  <span>{t('fishing.regulatoryStatus', 'Regulatory Status:')} {currentZone.restrictions}</span>
                </span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
