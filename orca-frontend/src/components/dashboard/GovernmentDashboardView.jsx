'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import Card from '../../components/Card';
import MarineMap from '../../components/DynamicMarineMap';
import Badge from '../../components/Badge';
import SectionHeader from '../../components/SectionHeader';
import Icon from '../../components/Icon';

const SECTOR_STATUS = [
  { state: 'Gujarat', craft: 1420, status: 'Normal', tone: 'green' },
  { state: 'Maharashtra', craft: 723, status: 'Caution', tone: 'orange' },
  { state: 'Kerala', craft: 540, status: 'High Swell Alert', tone: 'red' },
  { state: 'Tamil Nadu', craft: 318, status: 'Normal', tone: 'green' },
  { state: 'Andhra Pradesh', craft: 245, status: 'Normal', tone: 'green' },
  { state: 'Odisha', craft: 180, status: 'Normal', tone: 'green' },
  { state: 'West Bengal', craft: 96, status: 'Caution', tone: 'orange' },
];

const INCIDENT_FEED = [
  { time: '10:14', event: 'Craft near 12 NM territorial boundary', sector: 'Gujarat', severity: 'orange' },
  { time: '09:40', event: 'INCOIS High Swell Yellow Alert issued', sector: 'Kerala', severity: 'red' },
  { time: '08:22', event: 'NAVAREA VIII Firing Range Zone activated', sector: 'Kochi', severity: 'orange' },
  { time: '07:55', event: 'ICGS Samarth patrol sortie completed', sector: 'Veraval', severity: 'green' },
  { time: '06:30', event: 'Mumbai High ODAG security perimeter check', sector: 'Mumbai', severity: 'green' },
  { time: '05:10', event: 'Cyclone low-pressure watch issued', sector: 'Bay of Bengal', severity: 'red' },
];

export default function GovernmentDashboardView() {
  const router = useRouter();
  const totalCraft = SECTOR_STATUS.reduce((s, r) => s + r.craft, 0);
  const alertCount = INCIDENT_FEED.filter(i => i.severity !== 'green').length;

  return (
    <>
      {/* KPI Row */}
      <div className="health-summary-grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        <Card className="health-kpi-card border-blue">
          <div className="health-kpi-header">
            <span className="health-kpi-label">ACTIVE CRAFT AT SEA</span>
            <Icon name="Anchor" size={14} className="text-accent" />
          </div>
          <strong className="health-kpi-val">{totalCraft.toLocaleString()}</strong>
          <span className="health-kpi-sub">Across 9 maritime states & island UTs</span>
        </Card>
        <Card className="health-kpi-card border-orange">
          <div className="health-kpi-header">
            <span className="health-kpi-label">ALERTS ACTIVE</span>
            <Icon name="AlertTriangle" size={14} className="text-caution" />
          </div>
          <strong className="health-kpi-val text-caution">{alertCount}</strong>
          <span className="health-kpi-sub">Boundary crossings & weather warnings</span>
        </Card>
        <Card className="health-kpi-card border-green">
          <div className="health-kpi-header">
            <span className="health-kpi-label">SOS DISTRESS SIGNALS</span>
            <Icon name="Radio" size={14} className="text-safe" />
          </div>
          <strong className="health-kpi-val text-safe">0</strong>
          <span className="health-kpi-sub">No active SAR operations</span>
        </Card>
        <Card className="health-kpi-card border-blue">
          <div className="health-kpi-header">
            <span className="health-kpi-label">ICGS PATROL FLEET</span>
            <Icon name="Shield" size={14} className="text-accent" />
          </div>
          <strong className="health-kpi-val">8</strong>
          <span className="health-kpi-sub">Coast Guard cutters on patrol</span>
        </Card>
      </div>

      {/* Map + Incident Feed */}
      <div className="simple-cols" style={{ marginTop: 18 }}>
        <div className="simple-stack">
          <div className="simple-card">
            <div className="simple-card-head">
              <div>
                <h3>Pan-India Fleet & Surveillance Map</h3>
                <p>Live vessel density & Coast Guard patrol tracks</p>
              </div>
              <button type="button" className="pill-badge-btn" onClick={() => router.push('/marine-map')}>
                <Icon name="Maximize2" size={13} />
                <span>Full map</span>
              </button>
            </div>
            <div className="simple-map">
              <MarineMap showControls={false} initialSectorId="all-india" />
            </div>
          </div>
        </div>

        <div className="simple-stack">
          <div className="simple-card">
            <div className="simple-card-head">
              <div>
                <h3>Live Incident & Violation Feed</h3>
                <p>Real-time boundary crossings, alerts & patrols</p>
              </div>
              <button type="button" className="pill-badge-btn" onClick={() => router.push('/alerts')}>
                <Icon name="ExternalLink" size={13} />
                <span>All alerts</span>
              </button>
            </div>
            <div className="alert-lines">
              {INCIDENT_FEED.map((inc, idx) => (
                <div className="alert-line" key={idx}>
                  <Icon
                    name={inc.severity === 'green' ? 'CheckCircle2' : 'AlertTriangle'}
                    size={16}
                    style={{ color: inc.severity === 'red' ? '#ef4444' : inc.severity === 'orange' ? '#f59e0b' : '#10b981' }}
                  />
                  <div>
                    <b>{inc.time} — {inc.event}</b>
                    <p>Sector: {inc.sector}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Regional Sector Status + Emergency Actions */}
      <div className="simple-cols" style={{ marginTop: 18 }}>
        <div className="simple-card">
          <div className="simple-card-head">
            <div>
              <h3>Regional Coastal Sector Status</h3>
              <p>Craft counts and operational status per maritime state</p>
            </div>
          </div>
          <div className="stations-table-wrap">
            <table className="stations-table-pro">
              <thead>
                <tr>
                  <th>STATE</th>
                  <th>CRAFT COUNT</th>
                  <th>STATUS</th>
                </tr>
              </thead>
              <tbody>
                {SECTOR_STATUS.map(s => (
                  <tr key={s.state}>
                    <td><b>{s.state}</b></td>
                    <td>{s.craft.toLocaleString()}</td>
                    <td><Badge tone={s.tone}>{s.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="simple-card">
          <div className="simple-card-head">
            <div>
              <h3>Emergency Broadcast Console</h3>
              <p>Issue maritime warnings & dispatch response teams</p>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <button
              type="button"
              className="btn primary"
              style={{ width: '100%', justifyContent: 'center', background: '#dc2626', borderColor: '#dc2626' }}
              onClick={() => {
                if (typeof window !== 'undefined') {
                  window.dispatchEvent(new CustomEvent('orca:open-sos'));
                }
              }}
            >
              <Icon name="Radio" size={14} /> <span>Issue Pan-India Maritime Warning</span>
            </button>
            <button
              type="button"
              className="btn primary"
              style={{ width: '100%', justifyContent: 'center', background: '#ea580c', borderColor: '#ea580c' }}
              onClick={() => {
                if (typeof window !== 'undefined') {
                  window.dispatchEvent(new CustomEvent('orca:open-sos'));
                }
              }}
            >
              <Icon name="Navigation" size={14} /> <span>Dispatch Search & Rescue Team</span>
            </button>
            <button type="button" className="btn secondary" style={{ width: '100%', justifyContent: 'center' }}>
              <Icon name="Shield" size={14} /> <span>Harbour Bar-Closure Order</span>
            </button>
            <button type="button" className="btn secondary" style={{ width: '100%', justifyContent: 'center' }} onClick={() => router.push('/alerts')}>
              <Icon name="Bell" size={14} /> <span>View Full Alerts Center</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
