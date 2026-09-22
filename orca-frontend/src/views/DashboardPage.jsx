'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import MarineMap from '../components/DynamicMarineMap';
import Icon from '../components/Icon';
import Badge from '../components/Badge';
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
  const [activeView, setActiveView] = useState('chart'); // 'chart' | 'trend'
  const [hoveredTrendIndex, setHoveredTrendIndex] = useState(0);
  const [widgetModalOpen, setWidgetModalOpen] = useState(false);
  const [hiddenWidgets, setHiddenWidgets] = useState([]);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('orca-dashboard-hidden-widgets') || '[]');
      if (Array.isArray(saved)) setHiddenWidgets(saved.filter(id => ['chart', 'forecast', 'pfz', 'hazards'].includes(id)));
    } catch {}
  }, []);
  const toggleWidget = (id) => {
    setHiddenWidgets(previous => {
      const next = previous.includes(id) ? previous.filter(item => item !== id) : [...previous, id];
      try { localStorage.setItem('orca-dashboard-hidden-widgets', JSON.stringify(next)); } catch {}
      return next;
    });
  };
  useEffect(() => {
    if (!widgetModalOpen) return;
    const previous = document.activeElement;
    const dialog = document.querySelector('[data-testid="dashboard-widget-dialog"]');
    dialog?.querySelector('button')?.focus();
    const onKey = event => {
      if (event.key === 'Escape') setWidgetModalOpen(false);
      if (event.key === 'Tab') {
        const items = dialog?.querySelectorAll('button');
        const first = items?.[0], last = items?.[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); previous?.focus(); };
  }, [widgetModalOpen]);

  // Real backend telemetry state
  const [oceanTelemetry, setOceanTelemetry] = useState(null);
  const [marineBriefing, setMarineBriefing] = useState(null);
  const [pfzData, setPfzData] = useState(null);
  const [warningsData, setWarningsData] = useState(null);
  const [isLiveTelemetry, setIsLiveTelemetry] = useState(false);

  // Inline AI Assistant State
  const [copilotInput, setCopilotInput] = useState('');
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotReply, setCopilotReply] = useState(null);

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
      if (briefingRes.status === 'fulfilled' && briefingRes.value) {
        setMarineBriefing(briefingRes.value);
      }
      if (pfzRes.status === 'fulfilled' && pfzRes.value) {
        setPfzData(pfzRes.value);
      }
      if (warnRes.status === 'fulfilled' && warnRes.value) {
        setWarningsData(warnRes.value);
      }
    });
    return () => { active = false; };
  }, []);

  // 4 Real Top KPI Metric Cards
  const kpiMetrics = [
    {
      id: 'risk',
      label: t('dashboard.riskIndex', 'Voyage Risk Index'),
      value: marineBriefing?.composite_score ? marineBriefing.composite_score.toFixed(2) : '0.61',
      trend: marineBriefing?.composite_score && marineBriefing.composite_score > 0.65 ? '▲ ELEVATED' : '▼ MODERATE',
      trendTone: marineBriefing?.composite_score && marineBriefing.composite_score > 0.65 ? 'down' : 'up',
      icon: 'ShieldAlert',
      iconTone: 'blue',
      subtext: marineBriefing?.verdict ? (marineBriefing.verdict.slice(0, 32) + '...') : 'Douglas 3 • 11.8s Swell Period',
    },
    {
      id: 'swell',
      label: t('dashboard.seaState', 'Sea State & Weather'),
      value: oceanTelemetry ? `${oceanTelemetry.temperatureC}°C Air` : '26.0°C Air',
      trend: isLiveTelemetry ? '● CONNECTED' : '● SAMPLE',
      trendTone: 'neutral',
      icon: 'Waves',
      iconTone: 'cyan',
      subtext: oceanTelemetry ? `${oceanTelemetry.condition} • ${oceanTelemetry.tideType}` : 'Overcast clouds • HIGH TIDE',
    },
    {
      id: 'wind',
      label: t('dashboard.windVector', 'Surface Wind Vector'),
      value: oceanTelemetry ? `${oceanTelemetry.windSpeedKts} kts` : '3.6 kts',
      trend: oceanTelemetry ? `${oceanTelemetry.windSpeedMs} m/s` : '1.8 m/s',
      trendTone: 'up',
      icon: 'Wind',
      iconTone: 'purple',
      subtext: oceanTelemetry ? `${oceanTelemetry.windDirection} • ${oceanTelemetry.pressureHpa} hPa` : '343° NNW • 1014 hPa',
    },
    {
      id: 'pfz',
      label: t('dashboard.pfzCorridors', 'Active PFZ Corridors'),
      value: pfzData ? `${pfzData.total} Zones` : '20 Zones',
      trend: pfzData?.isLive ? '● CONNECTED' : '● SAMPLE',
      trendTone: 'up',
      icon: 'Fish',
      iconTone: 'green',
      subtext: oceanTelemetry ? `SST ${oceanTelemetry.sstC}°C • CoastWatch Front` : 'SST 28.3°C • Thermal Front',
    },
  ];

  // Dynamic 5-Day Forecast Grouping from Backend Telemetry with Current Day Highlighting
  const trendPoints = useMemo(() => {
    const now = new Date();
    const todayDateStr = now.toISOString().split('T')[0];
    const todayLocalStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

    const entries = oceanTelemetry?.forecastEntries;
    if (Array.isArray(entries) && entries.length >= 5) {
      const daysMap = new Map();
      entries.forEach((e) => {
        const datePart = e.time.split(' ')[0];
        if (!daysMap.has(datePart)) daysMap.set(datePart, []);
        daysMap.get(datePart).push(e);
      });

      const dayEntries = Array.from(daysMap.entries()).slice(0, 5);
      let foundToday = false;
      const points = dayEntries.map(([dateStr, items], idx) => {
        const d = new Date(dateStr + 'T12:00:00Z');
        const dayName = d.toLocaleDateString('en-US', { weekday: 'short' });
        const formattedDate = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
        const avgTemp = (items.reduce((sum, item) => sum + (item.temperature_c || 26), 0) / items.length).toFixed(1);
        const maxWindMs = Math.max(...items.map((i) => i.wind_speed_ms || 1.8));
        const windKts = (maxWindMs * 1.94384).toFixed(1);
        const condition = items[0]?.condition || 'Clear Coastal';
        const pressure = items[0]?.pressure_hpa || 1013;

        const isTodayCandidate =
          dateStr === todayDateStr ||
          dateStr === todayLocalStr ||
          d.toDateString() === now.toDateString() ||
          idx === 0;

        const isToday = !foundToday && isTodayCandidate;
        if (isToday) foundToday = true;

        return {
          day: dayName,
          date: formattedDate,
          temp: parseFloat(avgTemp),
          windKts,
          condition: condition.charAt(0).toUpperCase() + condition.slice(1),
          pressure,
          barHeight: Math.min(100, Math.max(35, Math.round((parseFloat(avgTemp) / 35) * 100))),
          isToday
        };
      });

      if (!foundToday && points.length > 0) {
        points[0].isToday = true;
      }
      return points;
    }

    // Dynamic fallback matching actual current day and subsequent 4 days
    const fallbackDays = [];
    const temps = [28.1, 27.5, 28.4, 29.0, 27.8];
    const winds = ['4.5', '5.2', '4.1', '6.0', '4.8'];
    const conditions = ['Scattered clouds', 'Moderate breeze', 'Clear sky', 'Light swell', 'Overcast clouds'];

    for (let i = 0; i < 5; i++) {
      const d = new Date();
      d.setDate(d.getDate() + i);
      const dayName = d.toLocaleDateString('en-US', { weekday: 'short' });
      const formattedDate = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
      const t = temps[i % temps.length];

      fallbackDays.push({
        day: dayName,
        date: formattedDate,
        temp: t,
        windKts: winds[i % winds.length],
        condition: conditions[i % conditions.length],
        pressure: 1013,
        barHeight: Math.min(100, Math.max(35, Math.round((t / 35) * 100))),
        isToday: i === 0
      });
    }

    return fallbackDays;
  }, [oceanTelemetry]);

  // Sync hoveredTrendIndex to today's index initially and on telemetry updates
  useEffect(() => {
    const todayIdx = trendPoints.findIndex((p) => p.isToday);
    if (todayIdx >= 0) {
      setHoveredTrendIndex(todayIdx);
    }
  }, [trendPoints]);

  // SVG Curve Coordinate Generation from Real Points
  const curvePoints = useMemo(() => {
    const minT = Math.min(...trendPoints.map((p) => p.temp)) - 1;
    const maxT = Math.max(...trendPoints.map((p) => p.temp)) + 1;
    const range = maxT - minT || 1;

    return trendPoints.map((pt, i) => {
      const cx = 40 + i * 125;
      const cy = Math.round(135 - ((pt.temp - minT) / range) * 85);
      return { ...pt, cx, cy, index: i };
    });
  }, [trendPoints]);

  const curveSvgPath = useMemo(() => {
    if (curvePoints.length < 2) return '';
    return curvePoints.reduce((acc, pt, i, arr) => {
      if (i === 0) return `M ${pt.cx} ${pt.cy}`;
      const prev = arr[i - 1];
      const cp1x = prev.cx + (pt.cx - prev.cx) / 2;
      const cp1y = prev.cy;
      const cp2x = prev.cx + (pt.cx - prev.cx) / 2;
      const cp2y = pt.cy;
      return `${acc} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${pt.cx} ${pt.cy}`;
    }, '');
  }, [curvePoints]);

  const curveAreaPath = useMemo(() => {
    if (curvePoints.length < 2) return '';
    const first = curvePoints[0];
    const last = curvePoints[curvePoints.length - 1];
    return `${curveSvgPath} L ${last.cx} 150 L ${first.cx} 150 Z`;
  }, [curveSvgPath, curvePoints]);

  // Top Real PFZ Zones for Table
  const topPfzZones = useMemo(() => {
    if (pfzData?.zones && pfzData.zones.length > 0) {
      return pfzData.zones.slice(0, 5);
    }
    return [
      {
        id: 'PFZ-01',
        name: 'CoastWatch Front Sector A (10.65°N, 75.75°E)',
        distance: '98.2 km',
        bearing: '325° NW',
        depth: '45 m',
        potential: 'High',
        catchIndex: '92/100',
        sst: '28.3 °C',
        chlorophyll: '0.84 mg/m³'
      },
      {
        id: 'PFZ-02',
        name: 'CoastWatch Front Sector B (10.65°N, 75.50°E)',
        distance: '116.2 km',
        bearing: '314° NW',
        depth: '60 m',
        potential: 'High',
        catchIndex: '88/100',
        sst: '28.9 °C',
        chlorophyll: '0.78 mg/m³'
      },
      {
        id: 'PFZ-03',
        name: 'CoastWatch Front Sector C (10.65°N, 75.25°E)',
        distance: '137.8 km',
        bearing: '306° NW',
        depth: '85 m',
        potential: 'Medium',
        catchIndex: '74/100',
        sst: '27.9 °C',
        chlorophyll: '0.68 mg/m³'
      },
      {
        id: 'PFZ-04',
        name: 'CoastWatch Front Sector D (10.40°N, 75.75°E)',
        distance: '76.4 km',
        bearing: '320° NW',
        depth: '40 m',
        potential: 'Medium',
        catchIndex: '71/100',
        sst: '28.1 °C',
        chlorophyll: '0.72 mg/m³'
      },
      {
        id: 'PFZ-05',
        name: 'CoastWatch Front Sector E (10.40°N, 75.50°E)',
        distance: '97.6 km',
        bearing: '307° NW',
        depth: '55 m',
        potential: 'Medium',
        catchIndex: '69/100',
        sst: '27.7 °C',
        chlorophyll: '0.64 mg/m³'
      }
    ];
  }, [pfzData]);

  // Real GDACS Disaster / Cyclone Advisory
  const activeCyclone = useMemo(() => {
    const hazards = warningsData?.hazards || [];
    return hazards.find((h) => h.category?.toLowerCase().includes('cyclone')) || hazards[0] || null;
  }, [warningsData]);

  // Inline FloatChat AI Assistant Handler
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
    } catch (err) {
      setCopilotReply({
        answer: 'Analyzed regional marine conditions: Weather and sea state off Kochi remain moderate. Swell height 1.4m, surface wind 3.6 kts @ 343° NNW.',
        status: 'fallback'
      });
    } finally {
      setCopilotLoading(false);
    }
  };

  const currentHovered = curvePoints[hoveredTrendIndex] || curvePoints[0];

  // Available Widgets for Drawer
  const widgetCatalog = [
    {
      id: 'chart',
      name: 'Coastal overview',
      desc: 'Your navigational map and five-day trend view.',
      tag: '#Navigation',
      icon: 'Navigation',
    },
    {
      id: 'forecast',
      name: 'The days ahead',
      desc: 'At-a-glance temperature and wind outlook.',
      tag: '#Hydrodynamics',
      icon: 'Waves',
    },
    {
      id: 'pfz',
      name: 'Fishing corridors',
      desc: 'Potential fishing zones with route-planning shortcuts.',
      tag: '#Fishery',
      icon: 'Thermometer',
    },
    {
      id: 'hazards',
      name: 'On your radar',
      desc: 'Marine advisories and your safety-center shortcut.',
      tag: '#Safety',
      icon: 'ShieldAlert',
    },
  ];

  return (
    <AppShell>
      <div className="orca-pro-dashboard">
        {/* Page Top Header with Live Controls */}
        <div className="pro-page-header">
          <div className="pro-header-title-group">
            <span className="ocean-eyebrow" data-testid="dashboard-eyebrow">YOUR OCEAN, IN FOCUS</span>
            <h1 data-testid="dashboard-heading">{t('ocean.dashboardTitle', 'Marine overview')}</h1>
            <p>{t('ocean.dashboardSubtitle', 'A connected perspective on the conditions that matter.')}</p>
          </div>

          <div className="pro-header-actions">
            <div className="pill-badge-btn" title="Live telemetry connection status">
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  background: isLiveTelemetry ? '#10b981' : '#f59e0b',
                  display: 'inline-block',
                  boxShadow: isLiveTelemetry ? '0 0 8px #10b981' : 'none'
                }}
              />
              <span>{isLiveTelemetry ? 'DATA CONNECTED' : 'SAMPLE DATA'}</span>
            </div>

            <button
              type="button"
              className="pill-badge-btn"
              onClick={() => setWidgetModalOpen(true)}
              data-testid="dashboard-customize-button"
              title="Customize dashboard widgets"
            >
              <Icon name="Sliders" size={13} />
              <span>{t('ocean.customize', 'Customize')}</span>
            </button>

            <button
              type="button"
              className="pill-badge-btn primary-blue"
              onClick={() => router.push('/marine-map')}
              title="Open Full Screen Navigational Chart"
            >
              <Icon name="Compass" size={13} />
              <span>{t('ocean.openExplorer', 'Open explorer')}</span>
            </button>
          </div>
        </div>

        {/* 4-Card Top KPI Metric Strip */}
        <div className="kpi-grid-pro">
          {kpiMetrics.map((kpi) => (
            <div key={kpi.id} className="kpi-card-pro" data-testid={`dashboard-metric-${kpi.id}`}>
              <div className="kpi-top-row">
                <span className="kpi-label">{kpi.label}</span>
                <div className={`kpi-icon-box ${kpi.iconTone}`}>
                  <Icon name={kpi.icon} size={15} />
                </div>
              </div>

              <div className="kpi-main-row">
                <span className="kpi-value">{kpi.value}</span>
                <span className={`kpi-trend-pill ${kpi.trendTone}`}>
                  {kpi.trend}
                </span>
              </div>

              <span className="kpi-subtext">{kpi.subtext}</span>
            </div>
          ))}
        </div>

        {/* Main Bento Layout */}
        <div className="bento-main-grid-pro">
          {/* Left Column (~65%) */}
          <div className="bento-left-column">
            {/* Primary Operations Hub Card */}
            <div className="card-pro" data-hidden={hiddenWidgets.includes('chart')} data-testid="dashboard-chart-panel">
              <div className="trend-header-row">
                <div className="trend-stat-box">
                  <span className="trend-label">{t('ocean.coastalPerspective', 'YOUR COASTAL PERSPECTIVE')}</span>
                  <div className="trend-value-group">
                    <span className="trend-value-big">
                      {!marineBriefing?.isLive ? 'Kochi coastal waters' : marineBriefing.composite_score > 0.65 ? 'Caution advised' : 'Review voyage conditions'}
                    </span>
                    <span className={`kpi-trend-pill ${marineBriefing?.composite_score && marineBriefing.composite_score > 0.65 ? 'down' : 'up'}`}>
                      {marineBriefing?.composite_score ? `Index: ${marineBriefing.composite_score.toFixed(2)}` : 'Index: 0.61'}
                    </span>
                  </div>
                </div>

                <div className="view-toggle-pills">
                  <button
                    type="button"
                    className={`toggle-pill-btn ${activeView === 'chart' ? 'active' : ''}`}
                    onClick={() => setActiveView('chart')}
                    data-testid="dashboard-chart-tab"
                    aria-pressed={activeView === 'chart'}
                  >
                    <Icon name="Map" size={12} />
                    <span>{t('dashboard.navChart', 'Nautical Chart')}</span>
                  </button>
                  <button
                    type="button"
                    className={`toggle-pill-btn ${activeView === 'trend' ? 'active' : ''}`}
                    onClick={() => setActiveView('trend')}
                    data-testid="dashboard-outlook-tab"
                    aria-pressed={activeView === 'trend'}
                  >
                    <Icon name="Activity" size={12} />
                    <span>{t('ocean.forecastTab', '5-day outlook')}</span>
                  </button>
                </div>
              </div>

              {/* View Content */}
              {activeView === 'chart' ? (
                <div className="dashboard-map-preview" style={{ height: '320px', borderRadius: '8px', overflow: 'hidden', position: 'relative' }}>
                  <MarineMap showControls={false} />
                </div>
              ) : (
                <div style={{ padding: '10px 0 0', position: 'relative' }}>
                  {/* Smooth Interactive SVG Curve driven by 5-Day Telemetry */}
                  <svg viewBox="0 0 580 160" style={{ width: '100%', height: '180px', overflow: 'visible' }}>
                    <defs>
                      <linearGradient id="marineCurveGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--th-accent-cyan, #38bdf8)" stopOpacity="0.25" />
                        <stop offset="100%" stopColor="var(--th-accent-cyan, #38bdf8)" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* Horizontal Grid lines */}
                    <line x1="20" y1="30" x2="560" y2="30" stroke="var(--c-border-subtle)" strokeDasharray="4 4" />
                    <line x1="20" y1="80" x2="560" y2="80" stroke="var(--c-border-subtle)" strokeDasharray="4 4" />
                    <line x1="20" y1="130" x2="560" y2="130" stroke="var(--c-border-subtle)" strokeDasharray="4 4" />

                    {/* Gradient Area Fill */}
                    {curveAreaPath && (
                      <path d={curveAreaPath} fill="url(#marineCurveGrad)" />
                    )}

                    {/* Smooth Primary Stroke */}
                    {curveSvgPath && (
                      <path
                        d={curveSvgPath}
                        fill="none"
                        stroke="var(--th-accent-cyan, #38bdf8)"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                      />
                    )}

                    {/* Interactive Points with Today Pointer */}
                    {curvePoints.map((pt, idx) => {
                      const isHovered = hoveredTrendIndex === idx;
                      const isToday = pt.isToday;
                      return (
                        <g
                          key={idx}
                          onMouseEnter={() => setHoveredTrendIndex(idx)}
                          style={{ cursor: 'pointer' }}
                        >
                          {/* Indicator Pin Pointing to Current Day on Curve */}
                          {isToday && (
                            <g>
                              <circle
                                cx={pt.cx}
                                cy={pt.cy}
                                r="10"
                                fill="none"
                                stroke="var(--th-accent-cyan, #38bdf8)"
                                strokeWidth="1.5"
                                strokeDasharray="2 2"
                                opacity="0.85"
                              />
                              <text
                                x={pt.cx}
                                y={pt.cy - 14}
                                textAnchor="middle"
                                fontSize="9"
                                fontWeight="800"
                                fill="var(--th-accent-cyan, #38bdf8)"
                                letterSpacing="0.4"
                              >
                                TODAY ▼
                              </text>
                            </g>
                          )}

                          {isHovered && (
                            <line
                              x1={pt.cx}
                              y1="15"
                              x2={pt.cx}
                              y2="145"
                              stroke="var(--th-accent-cyan, #38bdf8)"
                              strokeDasharray="3 3"
                              opacity="0.7"
                            />
                          )}
                          <circle
                            cx={pt.cx}
                            cy={pt.cy}
                            r={isHovered ? 6 : isToday ? 5 : 4}
                            fill={isToday ? 'var(--th-accent-cyan, #38bdf8)' : 'var(--c-surface)'}
                            stroke="var(--th-accent-cyan, #38bdf8)"
                            strokeWidth={isHovered ? 3 : 2}
                          />
                          <text
                            x={pt.cx}
                            y="158"
                            textAnchor="middle"
                            fontSize="11"
                            fill={isToday ? 'var(--th-accent-cyan, #38bdf8)' : isHovered ? 'var(--c-text-primary)' : 'var(--c-text-muted)'}
                            fontWeight={isHovered || isToday ? '700' : '400'}
                          >
                            {pt.day}{isToday ? ' (Today)' : ''}
                          </text>
                        </g>
                      );
                    })}
                  </svg>

                  {/* Interactive Tooltip Card matching real values */}
                  {currentHovered && (
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: '6px', marginBottom: '8px' }}>
                      <div style={{
                        background: 'var(--c-surface)',
                        border: '1px solid var(--c-border)',
                        borderRadius: '8px',
                        padding: '6px 14px',
                        backdropFilter: 'blur(12px)',
                        boxShadow: '0 4px 14px rgba(0,0,0,0.12)',
                        fontSize: '11.5px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px'
                      }}>
                        <b>{currentHovered.day} ({currentHovered.date}):</b>
                        <span style={{ color: 'var(--th-accent-cyan, #38bdf8)', fontWeight: 600 }}>{currentHovered.temp}°C Air</span>
                        <span style={{ opacity: 0.3 }}>•</span>
                        <span style={{ color: 'var(--c-text-primary)', fontWeight: 500 }}>{currentHovered.windKts} kts Wind</span>
                        <span style={{ opacity: 0.3 }}>•</span>
                        <span style={{ color: 'var(--c-text-muted)' }}>{currentHovered.condition}</span>
                        <span style={{ opacity: 0.3 }}>•</span>
                        <span style={{ color: 'var(--c-text-muted)' }}>{currentHovered.pressure} hPa</span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Segmented Sub-metrics in Container */}
              <div className="segmented-status-row">
                <div className="submetric-item">
                  <span className="submetric-bar blue" />
                  <div className="submetric-text">
                    <span className="submetric-val">Kochi Port Fairway</span>
                    <span className="submetric-lbl">Sample fairway reference</span>
                  </div>
                </div>

                <div className="submetric-item">
                  <span className="submetric-bar green" />
                  <div className="submetric-text">
                    <span className="submetric-val">
                      {topPfzZones[0] ? `${topPfzZones[0].distance} (${topPfzZones[0].bearing})` : '98.2 km (325° NW)'}
                    </span>
                    <span className="submetric-lbl">
                      {topPfzZones[0]?.name?.split('(')[0] || 'CoastWatch PFZ-01 Front'}
                    </span>
                  </div>
                </div>

                <div className="submetric-item">
                  <span className="submetric-bar orange" />
                  <div className="submetric-text">
                    <span className="submetric-val">
                      {oceanTelemetry ? `SST ${oceanTelemetry.sstC}°C • ${oceanTelemetry.condition}` : 'SST 28.3°C • Overcast'}
                    </span>
                    <span className="submetric-lbl">
                      {oceanTelemetry ? `Wind ${oceanTelemetry.windSpeedKts} kts @ ${oceanTelemetry.windDirection}` : '3.6 kts @ 343° NNW'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Real Potential Fishing Corridors (NOAA CoastWatch Fronts) */}
            {hiddenWidgets.includes('chart') && hiddenWidgets.includes('pfz') && <div className="card-pro ocean-empty-panels" data-testid="dashboard-hidden-panels"><Icon name="LayoutDashboard" size={28} /><h2>Your overview, your way.</h2><p>Restore the panels you want to keep in focus.</p><button className="btn secondary" data-testid="restore-panels-button" onClick={() => setWidgetModalOpen(true)}>Choose your panels</button></div>}
            <div className="card-pro" data-hidden={hiddenWidgets.includes('pfz')} data-testid="dashboard-fishing-panel">
              <div className="card-pro-header">
                <div>
                  <h2 className="card-pro-title">
                    <span>{t('ocean.fishingCorridors', 'Potential fishing corridors')}</span>
                  </h2>
                  <p style={{ margin: '2px 0 0', fontSize: '11px', color: 'var(--c-text-muted)' }}>
                    High-resolution satellite ocean color & sea surface temperature gradients
                  </p>
                </div>
                <button
                  type="button"
                  className="pill-badge-btn"
                  onClick={() => router.push('/fishing')}
                  title="View all 20 fishing zones"
                >
                  <Icon name="ExternalLink" size={13} />
                  <span>View all {pfzData?.total || ''}</span>
                </button>
              </div>

              <div className="stations-table-wrap">
                <table className="stations-table-pro">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>ZONE / LOCATION</th>
                      <th>DISTANCE & BEARING</th>
                      <th>TELEMETRY (SST / CHL)</th>
                      <th>CATCH POTENTIAL</th>
                      <th>ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topPfzZones.map((zone) => (
                      <tr key={zone.id}>
                        <td className="station-id-code">{zone.id}</td>
                        <td>
                          <div className="station-name-cell">
                            <div className="station-icon-box" style={{ color: 'var(--c-safe, #10b981)', background: 'var(--c-safe-bg, rgba(16, 185, 129, 0.12))' }}>
                              <Icon name="Fish" size={14} />
                            </div>
                            <div>
                              <span style={{ fontWeight: 600, display: 'block' }}>{zone.name.split('(')[0].trim()}</span>
                              <span style={{ fontSize: '10.5px', color: 'var(--c-text-muted)' }}>
                                {zone.name.includes('(') ? zone.name.slice(zone.name.indexOf('(')) : zone.depth}
                              </span>
                            </div>
                          </div>
                        </td>
                        <td>
                          <div style={{ fontWeight: 600, color: 'var(--c-text-primary)' }}>{zone.distance}</div>
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
                            title={`Plot navigational route to ${zone.id}`}
                          >
                            <Icon name="Navigation" size={12} />
                            <span>Plot Route</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Right Column (~35%) */}
          <div className="bento-right-column">
            {/* Real 5-Day Meteorological Outlook Bar Chart Card */}
            <div className="card-pro" data-hidden={hiddenWidgets.includes('forecast')} data-testid="dashboard-forecast-panel">
              <div className="card-pro-header">
                <div>
                  <h3 className="card-pro-title">{t('ocean.forecastTitle', 'The days ahead')}</h3>
                  <span style={{ fontSize: '11px', color: 'var(--c-text-muted)' }}>{isLiveTelemetry ? '5-day marine forecast' : '5-day sample outlook · not a forecast'}</span>
                </div>
                <button
                  type="button"
                  className="card-pro-action-btn"
                  onClick={() => router.push('/marine-map')}
                  title="Open live meteorological maps"
                >
                  <Icon name="MoreHorizontal" size={16} />
                </button>
              </div>

              <div className="weekly-bars-container">
                {trendPoints.map((bar, idx) => {
                  const isSelected = hoveredTrendIndex === idx;
                  const isToday = bar.isToday;
                  return (
                    <div
                      key={bar.day + idx}
                      className={`weekly-bar-col ${isSelected ? 'active' : ''} ${isToday ? 'is-today' : ''}`}
                      onClick={() => setHoveredTrendIndex(idx)}
                      role="button"
                      tabIndex={0}
                      aria-pressed={isSelected}
                      data-testid={`forecast-day-${idx}`}
                      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setHoveredTrendIndex(idx); } }}
                      style={{ cursor: 'pointer' }}
                      title={`${bar.day} (${bar.date})${isToday ? ' [CURRENT DAY]' : ''}: ${bar.temp}°C, ${bar.windKts} kts wind, ${bar.condition}`}
                    >
                      {/* Animated Pointer Pin Pointing to Current Day */}
                      {isToday && (
                        <div className="today-pointer-pin" title="Current Day Forecast">
                          <span className="today-pin-badge">
                            <span className="today-pulse-dot" />
                            TODAY
                          </span>
                          <span className="today-pointer-arrow">▼</span>
                        </div>
                      )}

                      <div className="weekly-bar-track">
                        <div className={`bar-floating-badge ${isSelected ? 'active' : ''} ${isToday ? 'today-badge' : ''}`}>
                          {bar.temp}°C
                        </div>
                        <div
                          className={`weekly-bar-fill ${isToday ? 'today-fill' : ''}`}
                          style={{ height: `${bar.barHeight}%` }}
                        />
                      </div>
                      <span className={`bar-day-label ${isToday ? 'today-label' : ''}`}>
                        {bar.day}
                        {isToday && <span className="today-dot" title="Current Day" />}
                      </span>
                      <span className={`forecast-bar-temp-val ${isToday ? 'today-val' : ''}`}>{bar.windKts}kt</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Active GDACS Tropical Cyclone & Marine Hazards Radar Card */}
            <div className="card-pro" data-hidden={hiddenWidgets.includes('hazards')} data-testid="dashboard-hazards-panel">
              <div className="card-pro-header">
                <div>
                  <h3 className="card-pro-title">On your radar</h3>
                  <span style={{ fontSize: '11px', color: 'var(--c-text-muted)' }}>GDACS & INCOIS Bulletin Feed</span>
                </div>
                <button
                  type="button"
                  className="card-pro-action-btn"
                  onClick={() => router.push('/alerts')}
                  title="View all marine bulletins"
                >
                  <Icon name="ExternalLink" size={14} />
                </button>
              </div>

              <div className="hazard-radar-container">
                {activeCyclone ? (
                  <div className="radar-storm-banner">
                    <div className="radar-pulse-dot" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                        <span style={{ fontWeight: 700, fontSize: '12.5px', color: 'var(--c-hazard, #ef4444)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                          {activeCyclone.title || 'TROPICAL CYCLONE FOURTEEN-E'}
                        </span>
                        <span className="radar-wind-tag">
                          {activeCyclone.actionRequired?.match(/(\d+\s*km\/h)/)?.[0] || '157 km/h'}
                        </span>
                      </div>
                      <p style={{ margin: '4px 0 0', fontSize: '11px', color: 'var(--c-text-muted)', lineHeight: '1.4' }}>
                        {activeCyclone.desc ? (activeCyclone.desc.slice(0, 110) + '...') : 'Tropical disturbance active in maritime sector. Sustained gale winds.'}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 12px', background: 'var(--c-safe-bg, rgba(16, 185, 129, 0.12))', border: '1px solid var(--c-safe-border, rgba(16, 185, 129, 0.25))', borderRadius: '8px' }}>
                    <Icon name="CheckCircle" size={18} style={{ color: 'var(--c-safe, #10b981)' }} />
                    <span style={{ fontSize: '12px', color: 'var(--c-safe, #10b981)', fontWeight: 600 }}>
                      Loading marine advisories. Conditions are not yet verified.
                    </span>
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px', paddingTop: '10px', borderTop: '1px solid var(--c-border-subtle)' }}>
                  <div>
                    <div style={{ fontSize: '10.5px', color: 'var(--c-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Composite Risk Status
                    </div>
                    <div style={{ fontSize: '13.5px', fontWeight: 700, color: marineBriefing?.composite_score > 0.65 ? 'var(--c-hazard, #ef4444)' : 'var(--c-safe, #10b981)' }}>
                      {marineBriefing?.composite_score ? (marineBriefing.composite_score > 0.65 ? 'ELEVATED RISK' : 'MODERATE / SAFE') : 'MODERATE (0.61)'}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="radar-inspect-btn"
                    onClick={() => router.push('/safety')}
                    title="Open Safety Center"
                  >
                    <span>Safety Center</span>
                    <Icon name="ArrowRight" size={12} />
                  </button>
                </div>
              </div>
            </div>

            {/* AI Assistant Card with Real FloatChat Integration */}
            <div className="card-pro ai-orb-card">
              <div className="card-pro-header" style={{ width: '100%' }}>
                <div>
                  <h3 className="card-pro-title">{t('ocean.copilotTitle', 'A question worth asking?')}</h3>
                  <span style={{ fontSize: '11px', color: 'var(--c-text-muted)' }}>Your marine copilot is a conversation away.</span>
                </div>
                <button
                  type="button"
                  className="card-pro-action-btn"
                  onClick={() => router.push('/ai-copilot')}
                  title="Open full Copilot"
                >
                  <Icon name="Maximize2" size={13} />
                </button>
              </div>

              {/* 3D Glowing Blue Sphere Visual */}
              <div className="ai-orb-visual">
                <div className="ai-orb-ambient-glow" />
                <div className="ai-3d-sphere" />
              </div>

              {/* Real Copilot Response Box */}
              {copilotLoading && (
                <div style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--c-text-muted)', display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
                  <span style={{ width: '12px', height: '12px', border: '2px solid var(--th-accent-cyan, #38bdf8)', borderRightColor: 'transparent', borderRadius: '50%', display: 'inline-block', animation: 'spin 1s linear infinite' }} />
                  <span>Querying FloatChat Marine Model...</span>
                </div>
              )}

              {copilotReply && !copilotLoading && (
                <div className="ai-inline-response-box">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', fontWeight: 600, color: 'var(--th-accent-cyan, #38bdf8)', fontSize: '11.5px' }}>
                    <Icon name="Compass" size={12} />
                    <span>{copilotReply.isLive ? 'ORCA response' : 'Sample response · not navigational advice'}</span>
                  </div>
                  <p style={{ margin: 0, fontSize: '11.5px', lineHeight: '1.45', color: 'var(--c-text-primary)' }}>
                    {copilotReply.answer || copilotReply.message || 'Regional sea state off Kochi indicates 1.4m swell with calm surface winds.'}
                  </p>
                </div>
              )}

              {/* Bottom Capsule Input Bar */}
              <form onSubmit={handleInlineCopilot} className="ai-capsule-input-bar">
                <input
                  type="text"
                  className="ai-capsule-input"
                  data-testid="dashboard-copilot-input"
                  aria-label="Ask your marine copilot"
                  placeholder={t('dashboard.copilotPlaceholder', 'Ask FloatChat about swell, PFZ, or weather...')}
                  value={copilotInput}
                  onChange={(e) => setCopilotInput(e.target.value)}
                  disabled={copilotLoading}
                />
                <button
                  type="button"
                  className="ai-capsule-icon-btn"
                  title="Voice input"
                  onClick={() => router.push('/ai-copilot')}
                >
                  <Icon name="Mic" size={13} />
                </button>
                <button
                  type="submit"
                  className="ai-capsule-send-btn"
                  data-testid="dashboard-copilot-send"
                  title="Submit prompt to FloatChat"
                  disabled={copilotLoading}
                >
                  <Icon name="ArrowUp" size={13} />
                </button>
              </form>
            </div>
          </div>
        </div>

        {/* Add Widget Drawer Modal (Matching Reference Top Overlay) */}
        {widgetModalOpen && (
          <div
            className="widget-modal-backdrop"
            onClick={() => setWidgetModalOpen(false)}
          >
            <div
              className="widget-modal-dialog"
              data-testid="dashboard-widget-dialog"
              role="dialog"
              aria-modal="true"
              aria-labelledby="widget-dialog-title"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="widget-modal-header">
                <h3 id="widget-dialog-title">{t('ocean.customizeOverview', 'Make it your overview')}</h3>
                <button
                  type="button"
                  className="widget-modal-close"
                  data-testid="dashboard-widget-close"
                  aria-label="Close customization"
                  onClick={() => setWidgetModalOpen(false)}
                >
                  <Icon name="X" size={16} />
                </button>
              </div>

              <div className="widget-modal-list">
                {widgetCatalog.map((w) => (
                  <div key={w.id} className="widget-preview-item">
                    <div className="station-icon-box" style={{ width: '38px', height: '38px' }}>
                      <Icon name={w.icon} size={18} />
                    </div>
                    <div className="widget-item-info">
                      <b>{w.name}</b>
                      <p>{w.desc}</p>
                      <span className="widget-tag-pill">{w.tag}</span>
                    </div>
                    <button
                      type="button"
                      className="widget-select-btn"
                      onClick={() => toggleWidget(w.id)}
                      role="switch"
                      aria-checked={!hiddenWidgets.includes(w.id)}
                      aria-label={`Show ${w.name}`}
                      data-testid={`widget-toggle-${w.id}`}
                    >
                      {hiddenWidgets.includes(w.id) ? 'Hidden' : 'Visible'}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
