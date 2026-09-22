'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import Card from '../components/Card';
import MarineMap from '../components/DynamicMarineMap';
import Badge from '../components/Badge';
import SectionHeader from '../components/SectionHeader';
import Icon from '../components/Icon';
import { alerts as fallbackAlerts } from '../data/mock';
import { useLanguage } from '../context/LanguageContext';
import { getMarineBriefing, getRealMarineWarnings, getOceanConditions } from '../services/apiClient';

export default function SafetyCenterPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState('map');
  const [briefing, setBriefing] = useState(null);
  const [warningsList, setWarningsList] = useState(fallbackAlerts);
  const [oceanData, setOceanData] = useState(null);
  const [isLiveSafety, setIsLiveSafety] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      getMarineBriefing({ lat: 9.93, lon: 76.27 }),
      getRealMarineWarnings(),
      getOceanConditions({ lat: 9.93, lon: 76.27 })
    ]).then(([briefingRes, warningsRes, oceanRes]) => {
      if (!active) return;
      if (briefingRes.status === 'fulfilled' && briefingRes.value) {
        setBriefing(briefingRes.value);
        if (briefingRes.value.isLive) setIsLiveSafety(true);
      }
      if (warningsRes.status === 'fulfilled' && warningsRes.value?.hazards) {
        setWarningsList(warningsRes.value.hazards);
        if (warningsRes.value.isLive) setIsLiveSafety(true);
      }
      if (oceanRes.status === 'fulfilled' && oceanRes.value) {
        setOceanData(oceanRes.value);
      }
    });
    return () => { active = false; };
  }, []);

  const riskScore = briefing?.composite_score ?? 0.61;
  const riskPct = Math.round(riskScore * 100);

  return (
    <AppShell
      title={t('safety.title', 'Maritime Safety & Hazard Command')}
      subtitle={t('safety.subtitle', 'Navigational Warnings, Restricted Military Zones & Real-time Swell Hazards')}
      actions={
        <div className="safety-header-actions">
          <Badge tone={isLiveSafety ? 'green' : 'orange'} dot>
            {isLiveSafety ? 'FASTAPI & GDACS LIVE' : 'OFFLINE SAFETY BUFFER'}
          </Badge>
          <button className="btn secondary btn-sm" onClick={() => router.push('/alerts')}>
            <Icon name="Bell" size={13} />
            <span>{t('safety.alertsCenter', 'Alerts Center')}</span>
          </button>
          <button className="btn primary btn-sm" onClick={() => router.push('/routes')}>
            <Icon name="Navigation" size={13} />
            <span>{t('safety.planRouteHazards', 'Plan Route Around Hazards')}</span>
          </button>
        </div>
      }
    >
      {/* 4-Tile Safety Assessment Matrix */}
      <div className="safety-stats-matrix">
        <Card className="safety-stat-card border-orange">
          <div className="stat-card-header">
            <div className="safety-icon-box tone-orange">
              <Icon name="ShieldAlert" size={18} />
            </div>
            <Badge tone={riskScore > 0.65 ? 'red' : 'orange'}>
              {riskScore > 0.65 ? t('common.high', 'HIGH RISK') : t('common.caution', 'CAUTION')}
            </Badge>
          </div>
          <span className="stat-label">{t('safety.overallSafetyStatus', 'Overall Safety Status')}</span>
          <strong className="stat-metric-value text-caution">
            {briefing?.verdict ? (briefing.verdict.toLowerCase().includes('high') ? 'ELEVATED' : 'MODERATE') : t('common.moderate', 'MODERATE')}
          </strong>
          <span className="stat-sub-text">{t('safety.compositeRiskScore', 'Composite Risk Score')}: {riskScore.toFixed(2)} / 1.00</span>
          <div className="safety-progress-bar">
            <div className="progress-fill" style={{ width: `${riskPct}%`, background: riskScore > 0.65 ? '#EF4444' : '#F59E0B' }} />
          </div>
        </Card>

        <Card className="safety-stat-card border-green">
          <div className="stat-card-header">
            <div className="safety-icon-box tone-green">
              <Icon name="CloudSun" size={18} />
            </div>
            <Badge tone="green">{t('common.low', 'LOW RISK')}</Badge>
          </div>
          <span className="stat-label">{t('safety.meteorologicalRisk', 'Meteorological Risk')}</span>
          <strong className="stat-metric-value text-safe">{t('common.safe', 'SAFE')} (0.18)</strong>
          <span className="stat-sub-text">
            {oceanData ? `Wind: ${oceanData.windSpeedKts} kts • Vis: ${oceanData.visibilityKm} km` : 'Wind: 18 km/h • Visibility: 8.5 km'}
          </span>
          <div className="safety-progress-bar">
            <div className="progress-fill" style={{ width: '18%', background: '#10B981' }} />
          </div>
        </Card>

        <Card className="safety-stat-card border-orange">
          <div className="stat-card-header">
            <div className="safety-icon-box tone-orange">
              <Icon name="Ban" size={18} />
            </div>
            <Badge tone="orange">{t('common.moderate', 'MEDIUM')}</Badge>
          </div>
          <span className="stat-label">{t('safety.navRestrictions', 'Navigational Restrictions')}</span>
          <strong className="stat-metric-value text-caution">2 {t('common.active', 'ACTIVE')}</strong>
          <span className="stat-sub-text">Sector Bravo Naval Exercise 12 km E</span>
          <div className="safety-progress-bar">
            <div className="progress-fill" style={{ width: '50%', background: '#F59E0B' }} />
          </div>
        </Card>

        <Card className="safety-stat-card border-green">
          <div className="stat-card-header">
            <div className="safety-icon-box tone-green">
              <Icon name="Tornado" size={18} />
            </div>
            <Badge tone="green">{t('common.clear', 'CLEAR')}</Badge>
          </div>
          <span className="stat-label">{t('safety.cycloneIndex', 'Cyclone & Storm Index')}</span>
          <strong className="stat-metric-value text-safe">{t('common.normal', 'NORMAL')} (0.04)</strong>
          <span className="stat-sub-text">No active depressions in Arabian Sea</span>
          <div className="safety-progress-bar">
            <div className="progress-fill" style={{ width: '4%', background: '#10B981' }} />
          </div>
        </Card>
      </div>

      {/* Interactive Tabs */}
      <div className="tabs-modern" style={{ marginBottom: '14px' }}>
        <button
          className={`tab-btn ${activeTab === 'map' ? 'active' : ''}`}
          onClick={() => setActiveTab('map')}
        >
          <Icon name="Map" size={13} />
          <span>{t('safety.hazardMapTab', 'Interactive Hazard Map')}</span>
        </button>
        <button
          className={`tab-btn ${activeTab === 'warnings' ? 'active' : ''}`}
          onClick={() => setActiveTab('warnings')}
        >
          <Icon name="Bell" size={13} />
          <span>{t('safety.warningBulletinsTab', 'Official Warning Bulletins')} ({warningsList.length})</span>
        </button>
        <button
          className={`tab-btn ${activeTab === 'geofences' ? 'active' : ''}`}
          onClick={() => setActiveTab('geofences')}
        >
          <Icon name="ShieldAlert" size={13} />
          <span>{t('safety.geofenceTab', 'Geofence & Coastal Borders')}</span>
        </button>
      </div>

      {/* Tab 1: Interactive Hazard Map */}
      {activeTab === 'map' && (
        <div className="safety-grid-layout">
          <Card className="safety-map-card">
            <SectionHeader
              title={t('safety.hazardOverlay', 'Navigational Hazard Overlay & Geofence Perimeter')}
              badge="ARABIAN SEA SECTOR"
              icon="Compass"
            />
            <MarineMap large />
          </Card>

          {/* Right Column: Warnings Stream & Emergency Contacts */}
          <div className="safety-side-column">
            <Card className="active-warnings-card">
              <SectionHeader
                title={t('safety.officialWarnings', 'Official Maritime Warnings')}
                badge={isLiveSafety ? 'GDACS / INCOIS LIVE' : 'INCOIS / IMD'}
                icon="AlertTriangle"
              />

              <div className="safety-warnings-list">
                {warningsList.slice(0, 3).map((w) => (
                  <div key={w.id} className={`safety-warning-box border-${w.level.toLowerCase()}`}>
                    <div className="warning-box-top">
                      <div className="warning-title-group">
                        <span className={`warning-dot tone-${w.level.toLowerCase()}`} />
                        <b>{w.title}</b>
                      </div>
                      <Badge tone={w.level === 'HIGH' ? 'red' : w.level === 'MEDIUM' ? 'orange' : 'blue'}>
                        {w.level === 'HIGH' ? t('common.high', 'HIGH') : w.level === 'MEDIUM' ? t('common.moderate', 'MEDIUM') : t('common.normal', 'LOW')}
                      </Badge>
                    </div>
                    <p className="warning-desc">{w.desc}</p>
                    <div className="warning-meta-grid">
                      <div><span>{t('common.location', 'Location')}:</span> <b>{w.place}</b></div>
                      <div><span>{t('alerts.validUntil', 'Valid Until')}:</span> <b>{w.validTill}</b></div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            {/* Coastal Emergency Refuge Card */}
            <Card className="emergency-refuge-card">
              <div className="emergency-header">
                <Icon name="LifeBuoy" size={16} className="text-safe" />
                <b>{t('safety.coastalDistress', 'Coastal Distress & Emergency Refuge Channels')}</b>
              </div>
              <div className="emergency-contacts">
                <div className="contact-row">
                  <span>{t('safety.coastGuardMrcc', 'Coast Guard MRCC Kochi:')}</span>
                  <b>VHF Ch 16 / +91 484 2215115</b>
                </div>
                <div className="contact-row">
                  <span>{t('safety.tsunamiCell', 'INCOIS Emergency Tsunami Cell:')}</span>
                  <b>Toll-free 1800-425-1025</b>
                </div>
                <div className="contact-row">
                  <span>{t('safety.fisheriesControl', 'Fisheries Control Room:')}</span>
                  <b>VHF Ch 72 / 0484-2503244</b>
                </div>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Tab 2: Full Official Warning Bulletins */}
      {activeTab === 'warnings' && (
        <Card className="active-warnings-card" style={{ width: '100%' }}>
          <SectionHeader
            title={t('safety.officialWarnings', 'Official Maritime Warning Bulletins')}
            badge={`${warningsList.length} ACTIVE ADVISORIES`}
            icon="AlertTriangle"
          />

          <div className="safety-warnings-list" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '12px' }}>
            {warningsList.map((w) => (
              <div key={w.id} className={`safety-warning-box border-${w.level.toLowerCase()}`} style={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div className="warning-box-top">
                    <div className="warning-title-group">
                      <span className={`warning-dot tone-${w.level.toLowerCase()}`} />
                      <b>{w.title}</b>
                    </div>
                    <Badge tone={w.level === 'HIGH' ? 'red' : w.level === 'MEDIUM' ? 'orange' : 'blue'}>
                      {w.level}
                    </Badge>
                  </div>
                  <p className="warning-desc">{w.desc}</p>
                  <div className="warning-meta-grid">
                    <div><span>{t('common.location', 'Location')}:</span> <b>{w.place}</b></div>
                    <div><span>{t('alerts.validUntil', 'Valid Until')}:</span> <b>{w.validTill}</b></div>
                    <div><span>Source:</span> <b>{w.source}</b></div>
                    <div><span>{t('alerts.directive', 'Action')}:</span> <b className="text-hazard">{w.actionRequired}</b></div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px', marginTop: '12px', borderTop: '1px solid var(--c-border)', paddingTop: '10px' }}>
                  <button
                    className="btn secondary btn-sm"
                    onClick={() => router.push(`/ai-copilot?q=Brief+me+on+${encodeURIComponent(w.title)}+and+advisories`)}
                  >
                    <Icon name="Bot" size={12} />
                    <span>Audit in Copilot</span>
                  </button>
                  <button
                    className="btn primary btn-sm"
                    onClick={() => router.push('/routes')}
                  >
                    <Icon name="Route" size={12} />
                    <span>Plan Safe Route</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Tab 3: Geofences & Maritime Borders */}
      {activeTab === 'geofences' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <Card>
            <SectionHeader
              title="Active Navigational Geofences & Maritime Security Borders"
              badge="NHO DEHRADUN / NAVAREA VIII"
              icon="ShieldAlert"
            />
            <p style={{ fontSize: '13px', color: 'var(--c-text-muted)', marginBottom: '16px' }}>
              Real-time geofences tracked by the ORCA Deterministic Safety Engine. Any route intersecting red perimeters is automatically vetoed with an alternative fairway recommended.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '14px' }}>
              {[
                {
                  id: 'GF-01',
                  name: 'Sector Bravo Naval Firing Exercise Box',
                  status: 'STRICT PROHIBITION',
                  tone: 'red',
                  authority: 'Southern Naval Command / NAVAREA VIII',
                  coords: '09°50\'N–09°56\'N, 076°22\'E–076°28\'E',
                  vesselLimit: 'All civilian craft excluded. Active live-fire exercises.',
                  bufferRequired: '3.0 Nautical Miles',
                  vhf: '156.500 MHz (Ch 70 DSC)'
                },
                {
                  id: 'GF-02',
                  name: 'Indian Territorial Waters Baseline (12 NM)',
                  status: 'SOVEREIGN JURISDICTION',
                  tone: 'blue',
                  authority: 'Ministry of External Affairs / Coast Guard',
                  coords: '12 NM seaward from coastal baseline',
                  vesselLimit: 'Registered Indian fishing craft only. Foreign vessel entry requires naval clearance.',
                  bufferRequired: 'Continuous AIS Class B broadcast',
                  vhf: 'VHF Ch 16'
                },
                {
                  id: 'GF-03',
                  name: 'Cochin Port Commercial Traffic Separation Scheme',
                  status: 'HIGH TRAFFIC FAIRWAY',
                  tone: 'orange',
                  authority: 'Cochin Port Trust Authority',
                  coords: 'Fairway Buoy Approach (09°58\'N, 076°14\'E)',
                  vesselLimit: 'Deep-draft tankers & container ships. Small craft must yield right of way.',
                  bufferRequired: 'Cross at 90° right angle only',
                  vhf: 'VHF Ch 12 / 16'
                },
                {
                  id: 'GF-04',
                  name: 'Monsoon Marine Protected Corridor (Periyar Shelf)',
                  status: 'ENVIRONMENTAL RESERVE',
                  tone: 'green',
                  authority: 'CMFRI / Kerala State Fisheries Dept',
                  coords: '09°40\'N–10°05\'N, Inshore 5 NM',
                  vesselLimit: 'Mechanized bottom trawling banned. Traditional gillnet permitted.',
                  bufferRequired: 'Non-destructive gear only',
                  vhf: 'VHF Ch 72'
                }
              ].map((gf) => (
                <div
                  key={gf.id}
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    border: '1px solid var(--c-border)',
                    background: 'var(--c-surface)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '10px'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <div>
                        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--th-accent-cyan, #38bdf8)' }}>{gf.id}</span>
                        <h4 style={{ margin: '2px 0 0 0', fontSize: '14px', fontWeight: 600, color: 'var(--c-text-primary)' }}>{gf.name}</h4>
                      </div>
                      <Badge tone={gf.tone}>{gf.status}</Badge>
                    </div>

                    <div style={{ fontSize: '12px', color: 'var(--c-text-muted)', display: 'flex', flexDirection: 'column', gap: '4px', margin: '8px 0' }}>
                      <div><span>Authority:</span> <b style={{ color: 'var(--c-text-primary)' }}>{gf.authority}</b></div>
                      <div><span>Coordinates:</span> <code style={{ fontSize: '11px' }}>{gf.coords}</code></div>
                      <div><span>Policy:</span> <span>{gf.vesselLimit}</span></div>
                      <div><span>Buffer:</span> <b style={{ color: gf.tone === 'red' ? '#ef4444' : 'inherit' }}>{gf.bufferRequired}</b></div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', borderTop: '1px solid var(--c-border)', paddingTop: '10px' }}>
                    <button
                      className="btn secondary btn-sm"
                      style={{ flex: 1 }}
                      onClick={() => router.push(`/ai-copilot?q=Verify+restrictions+and+clearance+for+${encodeURIComponent(gf.name)}`)}
                    >
                      <Icon name="Bot" size={12} />
                      <span>Audit Geofence</span>
                    </button>
                    <button
                      className="btn primary btn-sm"
                      onClick={() => router.push('/marine-map')}
                    >
                      <Icon name="Map" size={12} />
                      <span>Chart</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </AppShell>
  );
}
