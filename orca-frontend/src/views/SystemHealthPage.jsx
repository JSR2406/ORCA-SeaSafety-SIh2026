'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import Card from '../components/Card';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import Icon from '../components/Icon';
import { systemServices } from '../data/mock';
import { useBackend } from '../context/BackendContext';
import { getDatasetsStatus } from '../services/apiClient';

export default function SystemHealthPage() {
  const router = useRouter();
  const { isBackendLive, latencyMs, backendInfo, isChecking, recheckBackend } = useBackend();
  const [datasetsData, setDatasetsData] = useState(null);

  useEffect(() => {
    let active = true;
    getDatasetsStatus().then((res) => {
      if (active && res.data) {
        setDatasetsData(res.data);
      }
    });
    return () => { active = false; };
  }, [isBackendLive]);

  // Merge live FastAPI core telemetry into system services list
  const servicesList = systemServices.map((svc) => {
    if (svc.name.toLowerCase().includes('gateway') || svc.name.toLowerCase().includes('core api')) {
      return {
        ...svc,
        status: isBackendLive ? 'ACTIVE' : 'OFFLINE_FALLBACK',
        latency: isBackendLive ? `${latencyMs} ms` : 'Offline Buffer',
        version: isBackendLive ? `v${backendInfo?.version || '0.1.0'}` : 'Edge 1.0',
        uptime: isBackendLive ? '100.0%' : 'Degraded'
      };
    }
    return svc;
  });

  return (
    <AppShell
      title="Infrastructure &amp; Microservices Health"
      subtitle="Operational Telemetry, Latency Budgets &amp; Agentic Runtime Monitoring"
      actions={
        <div className="health-header-actions">
          <Badge tone={isBackendLive ? "green" : "orange"} dot>
            {isBackendLive ? `FASTAPI CORE ONLINE (${latencyMs}ms)` : 'FASTAPI OFFLINE (RESILIENT EDGE)'}
          </Badge>
          <button className="btn secondary btn-sm" onClick={recheckBackend} disabled={isChecking}>
            <Icon name="RefreshCw" size={13} />
            <span>{isChecking ? 'Pinging...' : 'Ping Gateway'}</span>
          </button>
          <button className="btn primary btn-sm" onClick={() => router.push('/ml-governance')}>
            <Icon name="BrainCircuit" size={13} />
            <span>ML Governance</span>
          </button>
        </div>
      }
    >
      {/* High-Level Infrastructure Health Summary */}
      <div className="health-summary-grid">
        <Card className={`health-kpi-card ${isBackendLive ? 'border-green' : 'border-orange'}`}>
          <div className="health-kpi-header">
            <span className="health-kpi-label">SYSTEM UPTIME (30 DAYS)</span>
            <span className={isBackendLive ? "pulse-dot-green" : "pulse-dot-amber"} />
          </div>
          <strong className={`health-kpi-val ${isBackendLive ? 'text-safe' : 'text-caution'}`}>
            {isBackendLive ? '99.98%' : 'Edge Mode'}
          </strong>
          <span className="health-kpi-sub">
            {isBackendLive ? '0 unplanned outages in past 720 hours' : 'Operating in resilient local edge buffer'}
          </span>
        </Card>

        <Card className="health-kpi-card border-blue">
          <div className="health-kpi-header">
            <span className="health-kpi-label">API GATEWAY P95 LATENCY</span>
            <Icon name="Zap" size={14} className="text-accent" />
          </div>
          <strong className="health-kpi-val">
            {isBackendLive ? `${latencyMs} ms` : '142 ms (Cached)'}
          </strong>
          <span className="health-kpi-sub">
            {isBackendLive ? 'Live FastAPI async endpoint benchmark' : 'Local fallback cache benchmark'}
          </span>
        </Card>

        <Card className="health-kpi-card border-green">
          <div className="health-kpi-header">
            <span className="health-kpi-label">TELEMETRY INGESTION RATE</span>
            <Icon name="Radio" size={14} className="text-safe" />
          </div>
          <strong className="health-kpi-val">4,280 /min</strong>
          <span className="health-kpi-sub">INCOIS buoys, IMD radar, AIS feeds</span>
        </Card>
      </div>

      {/* Microservices Cluster Health Table */}
      <Card className="services-health-card" style={{ marginTop: '14px' }}>
        <SectionHeader
          title="Operational Services &amp; Agentic Backends (10 Services)"
          badge="HEALTHCHECKS EVERY 30s"
          icon="Server"
        />

        <div className="services-table-wrap">
          <table className="services-health-table">
            <thead>
              <tr>
                <th>Service Name &amp; Role</th>
                <th>Status</th>
                <th>Response Latency</th>
                <th>Service Uptime</th>
                <th>Release Version</th>
                <th>Heartbeat Ping</th>
              </tr>
            </thead>
            <tbody>
              {servicesList.map((s) => (
                <tr key={s.name}>
                  <td>
                    <div className="service-name-cell">
                      <div className="service-icon-box">
                        <Icon name={s.status === 'ACTIVE' ? "CheckCircle" : "AlertTriangle"} size={14} className={s.status === 'ACTIVE' ? "text-safe" : "text-caution"} />
                      </div>
                      <div>
                        <b>{s.name}</b>
                      </div>
                    </div>
                  </td>
                  <td>
                    <Badge tone={s.status === 'ACTIVE' ? "green" : "orange"}>{s.status}</Badge>
                  </td>
                  <td>
                    <code className="latency-code">{s.latency}</code>
                  </td>
                  <td>
                    <b className="uptime-val text-safe">{s.uptime}</b>
                  </td>
                  <td>
                    <span className="version-pill">{s.version}</span>
                  </td>
                  <td>
                    <div className="heartbeat-cell">
                      <span className="heartbeat-ping-dot" />
                      <span>3s ago</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </AppShell>
  );
}
