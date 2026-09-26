'use client';

import React, { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Card from '../../components/Card';
import Chart from '../../components/Chart';
import Badge from '../../components/Badge';
import SectionHeader from '../../components/SectionHeader';
import Icon from '../../components/Icon';
import { useBackend } from '../../context/BackendContext';

const BUOY_DATA = [
  { id: 'BD08', location: 'Arabian Sea (Off Goa)', temp: '28.2°C', salinity: '35.1 PSU', depth: '50m', status: 'Online' },
  { id: 'CB02', location: 'Bay of Bengal (Off Vizag)', temp: '29.1°C', salinity: '33.8 PSU', depth: '300m', status: 'Online' },
  { id: 'AD09', location: 'Lakshadweep Basin', temp: '28.9°C', salinity: '34.6 PSU', depth: '200m', status: 'Online' },
  { id: 'SW06', location: 'SW Indian Ocean Mooring', temp: '27.4°C', salinity: '35.3 PSU', depth: '500m', status: 'Degraded' },
];

export default function ResearcherDashboardView() {
  const router = useRouter();
  const [activeMetric, setActiveMetric] = useState('sst');

  const metrics = [
    { key: 'sst', label: 'SST Fronts', icon: 'Thermometer' },
    { key: 'chlorophyll', label: 'Chlorophyll-a', icon: 'Sparkles' },
    { key: 'wind', label: 'Wind Dynamics', icon: 'Wind' },
    { key: 'risk', label: 'Risk Index', icon: 'Activity' },
  ];

  return (
    <>
      {/* KPI Row */}
      <div className="health-summary-grid">
        <Card className="health-kpi-card border-orange">
          <div className="health-kpi-header">
            <span className="health-kpi-label">SEA SURFACE TEMPERATURE</span>
            <Icon name="Thermometer" size={14} className="text-caution" />
          </div>
          <strong className="health-kpi-val">28.4°C</strong>
          <span className="health-kpi-sub">+0.8°C anomaly vs 30-yr climatology</span>
        </Card>
        <Card className="health-kpi-card border-green">
          <div className="health-kpi-header">
            <span className="health-kpi-label">CHLOROPHYLL-a BIOMASS</span>
            <Icon name="Sparkles" size={14} className="text-safe" />
          </div>
          <strong className="health-kpi-val text-safe">1.34 mg/m³</strong>
          <span className="health-kpi-sub">Upwelling-driven pelagic front active</span>
        </Card>
        <Card className="health-kpi-card border-blue">
          <div className="health-kpi-header">
            <span className="health-kpi-label">MOORED BUOYS ONLINE</span>
            <Icon name="Radio" size={14} className="text-accent" />
          </div>
          <strong className="health-kpi-val">12 / 12</strong>
          <span className="health-kpi-sub">INCOIS / NIOT deep-sea buoy array</span>
        </Card>
      </div>

      {/* Chart + Metric Tabs */}
      <div className="simple-card" style={{ marginTop: 18 }}>
        <div className="simple-card-head">
          <div>
            <h3>Telemetry Time-Series Analysis</h3>
            <p>Multi-sensor fusion: MODIS-Aqua, Sentinel-3 OLCI, INSAT-3DR</p>
          </div>
          <button type="button" className="pill-badge-btn" onClick={() => router.push('/analytics')}>
            <Icon name="ExternalLink" size={13} />
            <span>Full Analytics</span>
          </button>
        </div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
          {metrics.map(m => (
            <button
              key={m.key}
              type="button"
              className={`simple-chip ${activeMetric === m.key ? 'active' : ''}`}
              onClick={() => setActiveMetric(m.key)}
            >
              <Icon name={m.icon} size={12} /> {m.label}
            </button>
          ))}
        </div>
        <Chart metric={activeMetric} />
      </div>

      {/* Buoy Array Table */}
      <div className="simple-card" style={{ marginTop: 18 }}>
        <div className="simple-card-head">
          <div>
            <h3>Real-Time Moored Buoy Array (INCOIS / NIOT)</h3>
            <p>CTD salinity, temperature & depth profiles across Indian Ocean basin</p>
          </div>
        </div>
        <div className="stations-table-wrap">
          <table className="stations-table-pro">
            <thead>
              <tr>
                <th>BUOY ID</th>
                <th>LOCATION</th>
                <th>SST</th>
                <th>SALINITY</th>
                <th>DEPTH</th>
                <th>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {BUOY_DATA.map(b => (
                <tr key={b.id}>
                  <td className="station-id-code">{b.id}</td>
                  <td>{b.location}</td>
                  <td><b style={{ color: 'var(--th-accent-cyan, #38bdf8)' }}>{b.temp}</b></td>
                  <td>{b.salinity}</td>
                  <td>{b.depth}</td>
                  <td><Badge tone={b.status === 'Online' ? 'green' : 'orange'}>{b.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Export Actions */}
      <div className="simple-card" style={{ marginTop: 18 }}>
        <div className="simple-card-head">
          <div>
            <h3>Datasets & Export</h3>
            <p>Download telemetry data in research-compatible formats</p>
          </div>
        </div>
        <div className="verdict-actions">
          <button type="button" className="btn secondary"><Icon name="Download" size={14} /> <span>NetCDF4</span></button>
          <button type="button" className="btn secondary"><Icon name="Download" size={14} /> <span>GeoJSON</span></button>
          <button type="button" className="btn secondary"><Icon name="Download" size={14} /> <span>CSV</span></button>
          <button type="button" className="btn primary" onClick={() => router.push('/marine-map')}>
            <Icon name="Globe" size={14} /> <span>Biomass Plume Map</span>
          </button>
        </div>
      </div>
    </>
  );
}
