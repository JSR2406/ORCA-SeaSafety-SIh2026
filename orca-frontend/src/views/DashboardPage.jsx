'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import MarineMap from '../components/DynamicMarineMap';
import Icon from '../components/Icon';
import { useLanguage } from '../context/LanguageContext';
import {
  getOceanConditions,
  getMarineBriefing,
  getRealPfzZones,
  getRealMarineWarnings,
  sendChatMessage
} from '../services/apiClient';

export default function DashboardPage() {
  const router = useRouter();
  const { t } = useLanguage();

  const [showDetails, setShowDetails] = useState(false);
  const [selectedDay, setSelectedDay] = useState(0);

  const [oceanTelemetry, setOceanTelemetry] = useState(null);
  const [marineBriefing, setMarineBriefing] = useState(null);
  const [pfzData, setPfzData] = useState(null);
  const [warningsData, setWarningsData] = useState(null);
  const [isLiveTelemetry, setIsLiveTelemetry] = useState(false);

  const [copilotInput, setCopilotInput] = useState('');
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotReply, setCopilotReply] = useState(null);

  useEffect(() => {
    try {
      setShowDetails(localStorage.getItem('orca-dashboard-details') === '1');
    } catch {}
  }, []);

  const toggleDetails = () => {
    setShowDetails(previous => {
      const next = !previous;
      try { localStorage.setItem('orca-dashboard-details', next ? '1' : '0'); } catch {}
      return next;
    });
  };

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      getOceanConditions({ lat: 9.93, lon: 76.27 }),
      getMarineBriefing({ lat: 9.93, lon: 76.27 }),
      getRealPfzZones({ lat: 9.93, lon: 76.27 }),
      getRealMarineWarnings()
    ]).then(([oceanRes, briefingRes, pfzRes, warnRes]) => {
      if (!active) return;
      if (oceanRes.status === 'fulfilled' && oceanRes.value) {
        setOceanTelemetry(oceanRes.value);
        if (oceanRes.value.isLive) setIsLiveTelemetry(true);
      }
      if (briefingRes.status === 'fulfilled' && briefingRes.value) setMarineBriefing(briefingRes.value);
      if (pfzRes.status === 'fulfilled' && pfzRes.value) setPfzData(pfzRes.value);
      if (warnRes.status === 'fulfilled' && warnRes.value) setWarningsData(warnRes.value);
    });
    return () => { active = false; };
  }, []);

  const riskScore = marineBriefing?.composite_score ?? 0.61;

  const verdict = useMemo(() => {
    if (riskScore > 0.65) {
      return {
        tone: 'avoid',
        icon: 'CloudLightning',
        headline: t('simple.verdictAvoid', 'Better to stay ashore today'),
        line: 'Conditions near Kochi look rough. Waves and wind are strong enough to make a trip risky.'
      };
    }
    if (riskScore > 0.4) {
      return {
        tone: 'caution',
        icon: 'AlertTriangle',
        headline: t('simple.verdictCaution', 'You can go, but stay careful'),
        line: 'Conditions near Kochi are moderate. Keep close to the coast, watch the wind and head back early.'
      };
    }
    return {
      tone: 'good',
      icon: 'CheckCircle2',
      headline: t('simple.verdictGood', 'Good conditions to head out'),
      line: 'The sea near Kochi is calm right now. Normal precautions are enough.'
    };
  }, [riskScore, t]);

  const facts = [
    {
      id: 'wind',
      label: t('simple.wind', 'Wind'),
      value: oceanTelemetry ? `${oceanTelemetry.windSpeedKts} kts` : '3.6 kts'
    },
    {
      id: 'swell',
      label: t('simple.sea', 'Sea & sky'),
      value: oceanTelemetry ? oceanTelemetry.condition : 'Overcast'
    },
    {
      id: 'risk',
      label: t('simple.water', 'Water temp'),
      value: oceanTelemetry ? `${oceanTelemetry.sstC}°C` : '28.3°C'
    },
    {
      id: 'pfz',
      label: t('simple.fishing', 'Fishing zones'),
      value: pfzData ? `${pfzData.total}` : '20'
    }
  ];

  const trendPoints = useMemo(() => {
    const entries = oceanTelemetry?.forecastEntries;
    if (Array.isArray(entries) && entries.length >= 5) {
      const daysMap = new Map();
      entries.forEach((e) => {
        const datePart = e.time.split(' ')[0];
        if (!daysMap.has(datePart)) daysMap.set(datePart, []);
        daysMap.get(datePart).push(e);
      });
      return Array.from(daysMap.entries()).slice(0, 5).map(([dateStr, items], idx) => {
        const d = new Date(dateStr + 'T12:00:00Z');
        const avgTemp = (items.reduce((sum, item) => sum + (item.temperature_c || 26), 0) / items.length).toFixed(1);
        const maxWindMs = Math.max(...items.map((i) => i.wind_speed_ms || 1.8));
        return {
          day: d.toLocaleDateString('en-US', { weekday: 'short' }),
          date: d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
          temp: parseFloat(avgTemp),
          windKts: (maxWindMs * 1.94384).toFixed(1),
          condition: (items[0]?.condition || 'Clear coastal'),
          barHeight: Math.min(100, Math.max(35, Math.round((parseFloat(avgTemp) / 35) * 100))),
          isToday: idx === 0
        };
      });
    }

    const temps = [28.1, 27.5, 28.4, 29.0, 27.8];
    const winds = ['4.5', '5.2', '4.1', '6.0', '4.8'];
    const conditions = ['Scattered clouds', 'Moderate breeze', 'Clear sky', 'Light swell', 'Overcast clouds'];
    return temps.map((temp, i) => {
      const d = new Date();
      d.setDate(d.getDate() + i);
      return {
        day: d.toLocaleDateString('en-US', { weekday: 'short' }),
        date: d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
        temp,
        windKts: winds[i],
        condition: conditions[i],
        barHeight: Math.min(100, Math.max(35, Math.round((temp / 35) * 100))),
        isToday: i === 0
      };
    });
  }, [oceanTelemetry]);

  const topPfzZones = useMemo(() => {
    if (pfzData?.zones?.length) return pfzData.zones.slice(0, 5);
    return [
      { id: 'PFZ-01', name: 'CoastWatch Front Sector A (10.65°N, 75.75°E)', distance: '98.2 km', bearing: '325° NW', depth: '45 m', potential: 'High', catchIndex: '92/100', sst: '28.3 °C', chlorophyll: '0.84 mg/m³' },
      { id: 'PFZ-02', name: 'CoastWatch Front Sector B (10.65°N, 75.50°E)', distance: '116.2 km', bearing: '314° NW', depth: '60 m', potential: 'High', catchIndex: '88/100', sst: '28.9 °C', chlorophyll: '0.78 mg/m³' },
      { id: 'PFZ-03', name: 'CoastWatch Front Sector C (10.65°N, 75.25°E)', distance: '137.8 km', bearing: '306° NW', depth: '85 m', potential: 'Medium', catchIndex: '74/100', sst: '27.9 °C', chlorophyll: '0.68 mg/m³' },
      { id: 'PFZ-04', name: 'CoastWatch Front Sector D (10.40°N, 75.75°E)', distance: '76.4 km', bearing: '320° NW', depth: '40 m', potential: 'Medium', catchIndex: '71/100', sst: '28.1 °C', chlorophyll: '0.72 mg/m³' },
      { id: 'PFZ-05', name: 'CoastWatch Front Sector E (10.40°N, 75.50°E)', distance: '97.6 km', bearing: '307° NW', depth: '55 m', potential: 'Medium', catchIndex: '69/100', sst: '27.7 °C', chlorophyll: '0.64 mg/m³' }
    ];
  }, [pfzData]);

  const topAlerts = useMemo(() => (warningsData?.hazards || []).slice(0, 3), [warningsData]);

  const handleInlineCopilot = async (e) => {
    e.preventDefault();
    if (!copilotInput.trim()) return;
    setCopilotLoading(true);
    try {
      const res = await sendChatMessage({
        message: copilotInput.trim(),
        language: 'en',
        sessionId: 'orca-dashboard-session'
      });
      setCopilotReply(res);
    } catch {
      setCopilotReply({
        answer: 'Sea and weather off Kochi remain moderate. Swell height 1.4m, surface wind 3.6 kts from 343° NNW.',
        status: 'fallback'
      });
    } finally {
      setCopilotLoading(false);
    }
  };

  const activeDay = trendPoints[selectedDay] || trendPoints[0];

  return (
    <AppShell>
      <div className="simple-dash" data-testid="dashboard-simple">
        <div className="simple-head">
          <div>
            <span className="ocean-eyebrow" data-testid="dashboard-eyebrow">KOCHI COASTAL WATERS</span>
            <h1 data-testid="dashboard-heading">{t('ocean.dashboardTitle', 'Today at sea')}</h1>
            <p>{isLiveTelemetry ? 'Live conditions, updated automatically.' : 'Sample conditions · not for navigation.'}</p>
          </div>
          <div className="simple-head-actions">
            <button
              type="button"
              className="pill-badge-btn"
              onClick={toggleDetails}
              data-testid="dashboard-details-toggle"
              aria-expanded={showDetails}
            >
              <Icon name={showDetails ? 'ChevronUp' : 'Sliders'} size={13} />
              <span>{showDetails ? 'Hide details' : 'More details'}</span>
            </button>
            <button
              type="button"
              className="pill-badge-btn primary-blue"
              onClick={() => router.push('/marine-map')}
              data-testid="dashboard-open-map"
            >
              <Icon name="Compass" size={13} />
              <span>{t('ocean.openExplorer', 'Open map')}</span>
            </button>
          </div>
        </div>

        <section className="simple-verdict" data-tone={verdict.tone} data-testid="dashboard-verdict">
          <div className="verdict-mark"><Icon name={verdict.icon} size={26} strokeWidth={1.8} /></div>
          <div className="verdict-body">
            <span className="verdict-kicker">Can I go out today?</span>
            <h2 data-testid="dashboard-verdict-headline">{verdict.headline}</h2>
            <p data-testid="dashboard-verdict-line">{marineBriefing?.verdict || verdict.line}</p>

            <div className="verdict-facts">
              {facts.map(fact => (
                <div className="fact" key={fact.id} data-testid={`dashboard-metric-${fact.id}`}>
                  <span>{fact.label}</span>
                  <b>{fact.value}</b>
                </div>
              ))}
            </div>

            <div className="verdict-actions">
              <button type="button" className="btn secondary" onClick={() => router.push('/safety')} data-testid="dashboard-safety-link">
                <Icon name="ShieldAlert" size={14} /> <span>Safety advice</span>
              </button>
              <button type="button" className="btn secondary" onClick={() => router.push('/fishing')} data-testid="dashboard-fishing-link">
                <Icon name="Fish" size={14} /> <span>Where to fish</span>
              </button>
            </div>
          </div>
        </section>

        <div className="simple-cols">
          <div className="simple-stack">
            <div className="simple-card" data-testid="dashboard-chart-panel">
              <div className="simple-card-head">
                <div>
                  <h3>Your waters right now</h3>
                  <p>Tap the map to explore zones, vessels and routes.</p>
                </div>
                <button type="button" className="pill-badge-btn" onClick={() => router.push('/marine-map')} data-testid="dashboard-map-expand">
                  <Icon name="Maximize2" size={13} />
                  <span>Full map</span>
                </button>
              </div>
              <div className="simple-map">
                <MarineMap showControls={false} />
              </div>
            </div>

            <form className="simple-card" onSubmit={handleInlineCopilot} data-testid="dashboard-ask-panel">
              <div className="simple-card-head">
                <div>
                  <h3>Ask in your own words</h3>
                  <p>For example: “Is it safe to go out tomorrow morning?”</p>
                </div>
              </div>
              <div className="simple-ask">
                <input
                  type="text"
                  data-testid="dashboard-copilot-input"
                  aria-label="Ask your marine copilot"
                  placeholder={t('dashboard.copilotPlaceholder', 'Ask about weather, safety or fishing…')}
                  value={copilotInput}
                  onChange={(e) => setCopilotInput(e.target.value)}
                  disabled={copilotLoading}
                />
                <button type="button" className="pill-badge-btn" onClick={() => router.push('/ai-copilot')} data-testid="dashboard-voice-button">
                  <Icon name="Mic" size={13} />
                </button>
                <button type="submit" className="pill-badge-btn primary-blue" data-testid="dashboard-copilot-send" disabled={copilotLoading}>
                  <Icon name={copilotLoading ? 'Loader' : 'ArrowUp'} size={13} />
                </button>
              </div>
              {copilotLoading && <div className="simple-answer" data-testid="dashboard-copilot-loading">Thinking…</div>}
              {copilotReply && !copilotLoading && (
                <div className="simple-answer" data-testid="dashboard-copilot-answer">
                  <span>{copilotReply.isLive ? 'ORCA answer' : 'Sample answer · not navigational advice'}</span>
                  {copilotReply.answer || copilotReply.message || 'Sea state off Kochi indicates 1.4m swell with calm surface winds.'}
                </div>
              )}
            </form>
          </div>

          <div className="simple-stack">
            <div className="simple-card" data-testid="dashboard-forecast-panel">
              <div className="simple-card-head">
                <div>
                  <h3>Next 5 days</h3>
                  <p>{isLiveTelemetry ? 'Marine forecast outlook' : 'Sample outlook · not a forecast'}</p>
                </div>
              </div>
              <div className="days-strip">
                {trendPoints.map((day, idx) => (
                  <button
                    type="button"
                    key={day.day + idx}
                    className="day-chip"
                    data-today={day.isToday ? 'true' : 'false'}
                    data-testid={`forecast-day-${idx}`}
                    aria-pressed={selectedDay === idx}
                    onClick={() => setSelectedDay(idx)}
                  >
                    <em>{day.isToday ? 'Today' : day.day}</em>
                    <b>{day.temp}°</b>
                    <small>{day.windKts} kts</small>
                  </button>
                ))}
              </div>
              {activeDay && (
                <p className="simple-note" style={{ marginTop: '12px' }} data-testid="dashboard-day-summary">
                  {activeDay.isToday ? 'Today' : activeDay.day} ({activeDay.date}) · {activeDay.condition} · wind {activeDay.windKts} kts
                </p>
              )}
            </div>

            <div className="simple-card" data-testid="dashboard-hazards-panel">
              <div className="simple-card-head">
                <div>
                  <h3>Warnings</h3>
                  <p>Official marine bulletins for your area.</p>
                </div>
                <button type="button" className="pill-badge-btn" onClick={() => router.push('/alerts')} data-testid="dashboard-alerts-link">
                  <Icon name="ExternalLink" size={13} />
                  <span>All</span>
                </button>
              </div>
              <div className="alert-lines">
                {topAlerts.length === 0 && (
                  <div className="alert-line">
                    <Icon name="CheckCircle2" size={16} style={{ color: 'var(--c-safe, #10b981)' }} />
                    <div>
                      <b>No active warnings loaded</b>
                      <p>Conditions are not yet verified against live bulletins.</p>
                    </div>
                  </div>
                )}
                {topAlerts.map((hazard, idx) => (
                  <div className="alert-line" key={hazard.id || idx} data-testid={`dashboard-alert-${idx}`}>
                    <Icon name="AlertTriangle" size={16} style={{ color: 'var(--c-hazard, #ef4444)' }} />
                    <div>
                      <b>{hazard.title || 'Marine advisory'}</b>
                      <p>{hazard.desc ? `${hazard.desc.slice(0, 120)}…` : 'Advisory active in this maritime sector.'}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {showDetails && (
          <div className="simple-details" data-testid="dashboard-details-section">
            <div className="simple-card" data-testid="dashboard-fishing-panel">
              <div className="simple-card-head">
                <div>
                  <h3>{t('ocean.fishingCorridors', 'Potential fishing corridors')}</h3>
                  <p>Satellite ocean colour and sea surface temperature gradients.</p>
                </div>
                <button type="button" className="pill-badge-btn" onClick={() => router.push('/fishing')}>
                  <Icon name="ExternalLink" size={13} />
                  <span>View all {pfzData?.total || ''}</span>
                </button>
              </div>
              <div className="stations-table-wrap">
                <table className="stations-table-pro">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>ZONE</th>
                      <th>DISTANCE</th>
                      <th>SST / CHL</th>
                      <th>POTENTIAL</th>
                      <th>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topPfzZones.map((zone) => (
                      <tr key={zone.id}>
                        <td className="station-id-code">{zone.id}</td>
                        <td>
                          <span style={{ fontWeight: 600, display: 'block' }}>{zone.name.split('(')[0].trim()}</span>
                          <span style={{ fontSize: '10.5px', color: 'var(--c-text-muted)' }}>
                            {zone.name.includes('(') ? zone.name.slice(zone.name.indexOf('(')) : zone.depth}
                          </span>
                        </td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{zone.distance}</div>
                          <div style={{ fontSize: '11px', color: 'var(--c-text-muted)' }}>{zone.bearing}</div>
                        </td>
                        <td>
                          <div style={{ fontWeight: 600, color: 'var(--th-accent-cyan, #38bdf8)' }}>{zone.sst}</div>
                          <div style={{ fontSize: '11px', color: 'var(--c-text-muted)' }}>{zone.chlorophyll}</div>
                        </td>
                        <td>
                          <div className="rating-stars-badge" style={{ color: zone.potential === 'High' ? '#10b981' : '#f59e0b', borderColor: zone.potential === 'High' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)' }}>
                            <span>●</span>
                            <span>{zone.catchIndex} ({zone.potential})</span>
                          </div>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn-route-action"
                            onClick={() => router.push(`/routes?destLat=${zone.lat || 10.65}&destLon=${zone.lon || 75.75}&destName=${encodeURIComponent(zone.name || zone.id)}`)}
                          >
                            <Icon name="Navigation" size={12} />
                            <span>Plot route</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="simple-card" data-testid="dashboard-technical-panel">
              <div className="simple-card-head">
                <div>
                  <h3>Technical readout</h3>
                  <p>Composite risk and surface telemetry for this location.</p>
                </div>
              </div>
              <div className="verdict-facts">
                <div className="fact"><span>Risk index</span><b>{riskScore.toFixed(2)}</b></div>
                <div className="fact"><span>Air temp</span><b>{oceanTelemetry ? `${oceanTelemetry.temperatureC}°C` : '26.0°C'}</b></div>
                <div className="fact"><span>Wind dir</span><b>{oceanTelemetry ? oceanTelemetry.windDirection : '343° NNW'}</b></div>
                <div className="fact"><span>Pressure</span><b>{oceanTelemetry ? `${oceanTelemetry.pressureHpa} hPa` : '1014 hPa'}</b></div>
                <div className="fact"><span>Tide</span><b>{oceanTelemetry ? oceanTelemetry.tideType : 'High tide'}</b></div>
                <div className="fact"><span>Data source</span><b>{isLiveTelemetry ? 'Live services' : 'Sample data'}</b></div>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
