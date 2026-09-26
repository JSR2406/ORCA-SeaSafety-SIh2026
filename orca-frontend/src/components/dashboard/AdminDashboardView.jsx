'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import Card from '../../components/Card';
import Chart from '../../components/Chart';
import Badge from '../../components/Badge';
import SectionHeader from '../../components/SectionHeader';
import Icon from '../../components/Icon';
import { useBackend } from '../../context/BackendContext';
import { systemServices } from '../../data/mock';

const DATA_FEEDS = [
  { name: 'INCOIS SST Feed', status: 'Online', lastSync: '2 min ago', records: '1,621K' },
  { name: 'IMD Weather Radar', status: 'Online', lastSync: '5 min ago', records: '1,937K' },
  { name: 'Copernicus Sentinel-3', status: 'Online', lastSync: '18 min ago', records: '16,224' },
  { name: 'NOAA GFS Wind', status: 'Online', lastSync: '12 min ago', records: '1,337' },
  { name: 'AIS Vessel Stream', status: 'Online', lastSync: '1 min ago', records: '449' },
  { name: 'GEMTIDE Tidal Model', status: 'Degraded', lastSync: '48 min ago', records: '20' },
  { name: 'NAVAREA VIII Warnings', status: 'Online', lastSync: '8 min ago', records: '234' },
];

const WORKERS = [
  { name: 'SST Anomaly Compute Agent', status: 'Running', uptime: '14d 2h', icon: 'Thermometer' },
  { name: 'PFZ Zone Detection Worker', status: 'Running', uptime: '14d 2h', icon: 'Fish' },
  { name: 'AIS Ingestion Pipeline', status: 'Running', uptime: '7d 8h', icon: 'Radio' },
  { name: 'AI Copilot LLM Service', status: 'Running', uptime: '3d 12h', icon: 'Bot' },
];

export default function AdminDashboardView() {
  const router = useRouter();
  const { isBackendLive, latencyMs, recheckBackend, isChecking } = useBackend();

  const onlineFeeds = DATA_FEEDS.filter(f => f.status === 'Online').length;

  return (
    <>
      {/* KPI Row */}
      <div className="health-summary-grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        <Card className={`health-kpi-card ${isBackendLive ? 'border-green' : 'border-orange'}`}>
          <div className="health-kpi-header">
            <span className="health-kpi-label">API HEALTH / UPTIME</span>
            <span className={isBackendLive ? 'pulse-dot-green' : 'pulse-dot-amber'} />
          </div>
          <strong className={`health-kpi-val ${isBackendLive ? 'text-safe' : 'text-caution'}`}>
            {isBackendLive ? '99.8%' : 'Edge Mode'}
          </strong>
          <span className="health-kpi-sub">{isBackendLive ? `FastAPI latency: ${latencyMs}ms` : 'Operating in local fallback mode'}</span>
        </Card>
        <Card className="health-kpi-card border-blue">
          <div className="health-kpi-header">
            <span className="health-kpi-label">ACTIVE SESSIONS</span>
            <Icon name="Users" size={14} className="text-accent" />
          </div>
          <strong className="health-kpi-val">342</strong>
          <span className="health-kpi-sub">Web 248 · Mobile 94</span>
        </Card>
        <Card className="health-kpi-card border-blue">
          <div className="health-kpi-header">
            <span className="health-kpi-label">AI COPILOT AVG LATENCY</span>
            <Icon name="Bot" size={14} className="text-accent" />
          </div>
          <strong className="health-kpi-val">1.2s</strong>
          <span className="health-kpi-sub">Gemini Pro endpoint P95</span>
        </Card>
        <Card className="health-kpi-card border-green">
          <div className="health-kpi-header">
            <span className="health-kpi-label">DATA PIPELINES</span>
            <Icon name="Database" size={14} className="text-safe" />
          </div>
          <strong className="health-kpi-val text-safe">{onlineFeeds}/{DATA_FEEDS.length} Online</strong>
          <span className="health-kpi-sub">{onlineFeeds < DATA_FEEDS.length ? '1 feed degraded' : 'All feeds healthy'}</span>
        </Card>
      </div>

      {/* Data Feed Ingestion + System Performance */}
      <div className="simple-cols" style={{ marginTop: 18 }}>
        <div className="simple-card">
          <div className="simple-card-head">
            <div>
              <h3>Data Feed Ingestion Status</h3>
              <p>External data pipelines powering ORCA intelligence</p>
            </div>
            <button type="button" className="pill-badge-btn" onClick={recheckBackend} disabled={isChecking}>
              <Icon name="RefreshCw" size={13} />
              <span>{isChecking ? 'Checking…' : 'Refresh'}</span>
            </button>
          </div>
          <div className="stations-table-wrap">
            <table className="stations-table-pro">
              <thead>
                <tr>
                  <th>FEED</th>
                  <th>STATUS</th>
                  <th>LAST SYNC</th>
                  <th>RECORDS</th>
                </tr>
              </thead>
              <tbody>
                {DATA_FEEDS.map(f => (
                  <tr key={f.name}>
                    <td><b>{f.name}</b></td>
                    <td><Badge tone={f.status === 'Online' ? 'green' : 'orange'}>{f.status}</Badge></td>
                    <td>{f.lastSync}</td>
                    <td><code className="latency-code">{f.records}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="simple-stack">
          {/* Worker Agents */}
          <div className="simple-card">
            <div className="simple-card-head">
              <div>
                <h3>Worker Agents & Cron Jobs</h3>
                <p>Background processing pipeline status</p>
              </div>
            </div>
            <div className="alert-lines">
              {WORKERS.map(w => (
                <div className="alert-line" key={w.name}>
                  <Icon name={w.icon} size={16} style={{ color: w.status === 'Running' ? '#10b981' : '#f59e0b' }} />
                  <div style={{ flex: 1 }}>
                    <b>{w.name}</b>
                    <p>Uptime: {w.uptime}</p>
                  </div>
                  <Badge tone={w.status === 'Running' ? 'green' : 'orange'}>{w.status}</Badge>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Admin Actions */}
          <div className="simple-card">
            <div className="simple-card-head">
              <div>
                <h3>Quick Actions</h3>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button type="button" className="btn primary" style={{ width: '100%', justifyContent: 'center' }}>
                <Icon name="RefreshCw" size={14} /> <span>Trigger Full Data Sync</span>
              </button>
              <button type="button" className="btn secondary" style={{ width: '100%', justifyContent: 'center' }}>
                <Icon name="Zap" size={14} /> <span>Toggle Mock Fallback Engine</span>
              </button>
              <button type="button" className="btn secondary" style={{ width: '100%', justifyContent: 'center' }}>
                <Icon name="Database" size={14} /> <span>Clear Redis Cache</span>
              </button>
              <button type="button" className="btn secondary" style={{ width: '100%', justifyContent: 'center' }} onClick={() => router.push('/system-health')}>
                <Icon name="Server" size={14} /> <span>Full System Health →</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
