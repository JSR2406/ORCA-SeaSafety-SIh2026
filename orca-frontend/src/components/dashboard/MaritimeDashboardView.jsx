'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import Card from '../../components/Card';
import MarineMap from '../../components/DynamicMarineMap';
import Badge from '../../components/Badge';
import Icon from '../../components/Icon';

const ROUTE_COMPARISON = [
  { label: 'Coastal Route', dist: '142 NM', time: '08:31', fuel: '420 L', safety: 92, color: '#0ea5e9' },
  { label: 'Offshore Route', dist: '168 NM', time: '10:15', fuel: '540 L', safety: 78, color: '#f59e0b' },
];

const PORT_QUEUE = [
  { port: 'Mumbai JNPT', queue: '2.5 hrs', berths: 3, draft: '14.5m' },
  { port: 'Kochi Willingdon', queue: '1.2 hrs', berths: 5, draft: '12.8m' },
  { port: 'Chennai Kamarajar', queue: '3.8 hrs', berths: 2, draft: '16.2m' },
  { port: 'Visakhapatnam', queue: '0.8 hrs', berths: 4, draft: '15.0m' },
  { port: 'Paradip', queue: '1.5 hrs', berths: 3, draft: '13.5m' },
];

const NAVAREA_NOTICES = [
  { id: 'VIII-0041', title: 'Submarine exercise zone active — Kochi approaches', severity: 'orange' },
  { id: 'VIII-0039', title: 'Oil platform MOPU relocation — Mumbai High', severity: 'orange' },
  { id: 'VIII-0037', title: 'Hydrographic survey vessel — Tuticorin fairway', severity: 'green' },
];

export default function MaritimeDashboardView() {
  const router = useRouter();

  return (
    <>
      {/* KPI Row */}
      <div className="health-summary-grid">
        <Card className="health-kpi-card border-green">
          <div className="health-kpi-header">
            <span className="health-kpi-label">KEEL CLEARANCE</span>
            <Icon name="Anchor" size={14} className="text-safe" />
          </div>
          <strong className="health-kpi-val text-safe">4.2m</strong>
          <span className="health-kpi-sub">Adequate under-keel depth for transit</span>
        </Card>
        <Card className="health-kpi-card border-blue">
          <div className="health-kpi-header">
            <span className="health-kpi-label">TSS COMPLIANCE</span>
            <Icon name="Navigation" size={14} className="text-accent" />
          </div>
          <strong className="health-kpi-val">Active</strong>
          <span className="health-kpi-sub">Traffic Separation Scheme adherent</span>
        </Card>
        <Card className="health-kpi-card border-orange">
          <div className="health-kpi-header">
            <span className="health-kpi-label">NAVAREA VIII NOTICES</span>
            <Icon name="AlertTriangle" size={14} className="text-caution" />
          </div>
          <strong className="health-kpi-val text-caution">{NAVAREA_NOTICES.length}</strong>
          <span className="health-kpi-sub">Active navigational warnings</span>
        </Card>
      </div>

      {/* Map + Route Analysis */}
      <div className="simple-cols" style={{ marginTop: 18 }}>
        <div className="simple-stack">
          <div className="simple-card">
            <div className="simple-card-head">
              <div>
                <h3>Marine Navigation Chart</h3>
                <p>Shipping lanes, TSS corridors & vessel positions</p>
              </div>
              <button type="button" className="pill-badge-btn" onClick={() => router.push('/marine-map')}>
                <Icon name="Maximize2" size={13} />
                <span>Full map</span>
              </button>
            </div>
            <div className="simple-map">
              <MarineMap showControls={false} />
            </div>
          </div>
        </div>

        <div className="simple-stack">
          <div className="simple-card">
            <div className="simple-card-head">
              <div>
                <h3>Route Analysis Comparison</h3>
                <p>Planned vs alternate route cost/safety evaluation</p>
              </div>
              <button type="button" className="pill-badge-btn" onClick={() => router.push('/routes')}>
                <Icon name="ExternalLink" size={13} />
                <span>Plan route</span>
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {ROUTE_COMPARISON.map(r => (
                <div key={r.label} className="alert-line" style={{ borderLeft: `3px solid ${r.color}` }}>
                  <div style={{ flex: 1 }}>
                    <b>{r.label}</b>
                    <div className="verdict-facts" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginTop: 8 }}>
                      <div className="fact"><span>Distance</span><b>{r.dist}</b></div>
                      <div className="fact"><span>Est. Time</span><b>{r.time}</b></div>
                      <div className="fact"><span>Fuel</span><b>{r.fuel}</b></div>
                      <div className="fact"><span>Safety</span><b style={{ color: r.safety > 85 ? '#10b981' : '#f59e0b' }}>{r.safety}%</b></div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* NAVAREA Notices */}
          <div className="simple-card">
            <div className="simple-card-head">
              <div>
                <h3>NAVAREA VIII Active Notices</h3>
                <p>Indian Ocean navigational warnings</p>
              </div>
            </div>
            <div className="alert-lines">
              {NAVAREA_NOTICES.map(n => (
                <div className="alert-line" key={n.id}>
                  <Icon name="AlertTriangle" size={16} style={{ color: n.severity === 'orange' ? '#f59e0b' : '#10b981' }} />
                  <div>
                    <b>{n.id} — {n.title}</b>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Port Berthing Queue */}
      <div className="simple-card" style={{ marginTop: 18 }}>
        <div className="simple-card-head">
          <div>
            <h3>Port Berthing Queue & Draft Limits</h3>
            <p>Estimated wait times & available berths at Indian major ports</p>
          </div>
        </div>
        <div className="stations-table-wrap">
          <table className="stations-table-pro">
            <thead>
              <tr>
                <th>PORT</th>
                <th>QUEUE TIME</th>
                <th>BERTHS AVAILABLE</th>
                <th>MAX DRAFT</th>
              </tr>
            </thead>
            <tbody>
              {PORT_QUEUE.map(p => (
                <tr key={p.port}>
                  <td><b>{p.port}</b></td>
                  <td>{p.queue}</td>
                  <td>{p.berths}</td>
                  <td>{p.draft}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Action Bar */}
      <div className="verdict-actions" style={{ marginTop: 18 }}>
        <button type="button" className="btn primary" onClick={() => router.push('/routes')}>
          <Icon name="Navigation" size={14} /> <span>Optimize Route</span>
        </button>
        <button type="button" className="btn secondary">
          <Icon name="Anchor" size={14} /> <span>Channel Clearance Query</span>
        </button>
        <button type="button" className="btn secondary">
          <Icon name="Zap" size={14} /> <span>Fuel Calculator</span>
        </button>
        <button type="button" className="btn secondary" onClick={() => router.push('/safety')}>
          <Icon name="CloudLightning" size={14} /> <span>Weather Brief</span>
        </button>
      </div>
    </>
  );
}
