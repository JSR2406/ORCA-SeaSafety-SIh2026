'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import Card from '../components/Card';
import SectionHeader from '../components/SectionHeader';
import Chart from '../components/Chart';
import Badge from '../components/Badge';
import Icon from '../components/Icon';

const DOMAIN_CONFIG = {
  marine: {
    metric: 'sst',
    badge: 'MOORED BUOY AD04',
    station: "Lat 09°58'N, Lon 076°14'E • Inshore Station",
    title: 'Sea Surface Temperature (SST) Trend Analysis',
    current: '28.7 °C',
    mean: '28.4 °C',
    variance: '+0.7 °C (Upwelling Front)',
    confidence: '98.4% R²'
  },
  fisheries: {
    metric: 'chlorophyll',
    badge: 'MODIS-AQUA SATELLITE',
    station: 'Sentinel-3 OLCI Spectrometer • 300m Resolution',
    title: 'Chlorophyll-a Biomass Concentration Fronts',
    current: '0.86 mg/m³',
    mean: '0.74 mg/m³',
    variance: '+0.28 mg/m³ (Pelagic Front)',
    confidence: '94.2% R²'
  },
  weather: {
    metric: 'wind',
    badge: 'COASTAL DOPPLER DWR-CHN',
    station: 'IMD Station Kochi • 10m Elevation Anemometer',
    title: 'Coastal Wind Velocity & Gust Dynamics',
    current: '14.8 kts',
    mean: '12.6 kts',
    variance: 'Gusts 21 kts ENE',
    confidence: '96.8% R²'
  },
  productivity: {
    metric: 'catch',
    badge: 'FLEET LOG TELEMETRY',
    station: 'INCOIS Marine Fisheries Census Log',
    title: 'Pelagic Harvest Yield & CPUE Index',
    current: '3.7 T / trip',
    mean: '3.1 T / trip',
    variance: '+18% vs Seasonal Median',
    confidence: '91.5% R²'
  },
  risk: {
    metric: 'risk',
    badge: 'COASTAL RISK ENGINE',
    station: 'S-52 Hydrodynamic Safety Matrix',
    title: 'Composite Hydrodynamic Risk Horizon',
    current: '0.41 (Moderate)',
    mean: '0.38 (Baseline)',
    variance: 'Elevated during 31 Aug squall',
    confidence: '99.1% R²'
  }
};

export default function AnalyticsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState('marine');
  const [activePeriod, setActivePeriod] = useState('30D');

  const activeDomain = DOMAIN_CONFIG[activeTab] || DOMAIN_CONFIG.marine;

  return (
    <AppShell
      title="Oceanographic Telemetry &amp; Predictive Analytics"
      subtitle="Moored Buoy Time Series, Satellite Chlorophyll Biomass &amp; Swell Dynamics"
      actions={
        <div className="analytics-header-actions">
          <Badge tone="green" dot>SENSOR FEEDS VERIFIED</Badge>
          <button className="btn primary btn-sm" onClick={() => router.push('/ml-governance')}>
            <Icon name="BrainCircuit" size={13} />
            <span>ML Model Governance</span>
          </button>
        </div>
      }
    >
      {/* Domain Sub-tabs */}
      <div className="tabs-modern" style={{ marginBottom: '14px' }}>
        {[
          { key: 'marine', label: 'Marine Oceanography', icon: 'Waves' },
          { key: 'fisheries', label: 'Fisheries & Chlorophyll', icon: 'Fish' },
          { key: 'weather', label: 'Meteorology & Wind', icon: 'Wind' },
          { key: 'productivity', label: 'Fleet Catch Yield', icon: 'BarChart' },
          { key: 'risk', label: 'Composite Risk Horizon', icon: 'ShieldAlert' }
        ].map((tab) => (
          <button
            key={tab.key}
            className={`tab-btn ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            <Icon name={tab.icon} size={13} />
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Analytics Grid */}
      <div className="analytics-grid-layout">
        {/* Main Chart Card */}
        <Card className="analytics-wide-chart-card">
          <div className="chart-card-top-bar">
            <div>
              <div className="chart-badge-group">
                <Badge tone="blue">{activeDomain.badge}</Badge>
                <span className="chart-subtitle">{activeDomain.station}</span>
              </div>
              <h3 className="chart-main-title">{activeDomain.title}</h3>
            </div>

            <div className="chart-period-pills">
              {['7D', '30D', '90D', '1Y'].map((period) => (
                <button
                  key={period}
                  className={`period-btn ${activePeriod === period ? 'active' : ''}`}
                  onClick={() => setActivePeriod(period)}
                >
                  {period}
                </button>
              ))}
            </div>
          </div>

          {/* Interactive Scientific SVG Chart */}
          <Chart type="line" metric={activeDomain.metric} />

          <div className="chart-footer-metrics">
            <div className="metric-chip">
              <span className="chip-lbl">Current Reading:</span>
              <b className="chip-val text-safe">{activeDomain.current}</b>
            </div>
            <div className="metric-chip">
              <span className="chip-lbl">Period Mean ({activePeriod}):</span>
              <b className="chip-val">{activeDomain.mean}</b>
            </div>
            <div className="metric-chip">
              <span className="chip-lbl">Peak Variance:</span>
              <b className="chip-val">{activeDomain.variance}</b>
            </div>
            <div className="metric-chip">
              <span className="chip-lbl">Model Confidence:</span>
              <b className="chip-val text-safe">{activeDomain.confidence}</b>
            </div>
          </div>
        </Card>

        {/* Right Side: Environmental Trends & Sensor Telemetry */}
        <div className="analytics-side-column">
          <Card className="trends-summary-card">
            <SectionHeader
              title="Environmental Variance"
              badge="7-DAY DELTA"
              icon="TrendingUp"
            />

            <div className="trends-table">
              <div className="trend-row-item">
                <div className="trend-name-group">
                  <Icon name="Sparkles" size={14} className="text-safe" />
                  <span>Chlorophyll-a Biomass</span>
                </div>
                <div className="trend-val-group">
                  <b>0.82 mg/m³</b>
                  <span className="delta-badge down">↓ 12% vs last week</span>
                </div>
              </div>

              <div className="trend-row-item">
                <div className="trend-name-group">
                  <Icon name="Waves" size={14} className="text-accent" />
                  <span>Significant Wave Height</span>
                </div>
                <div className="trend-val-group">
                  <b>1.4 m</b>
                  <span className="delta-badge down">↓ 8% calming</span>
                </div>
              </div>

              <div className="trend-row-item">
                <div className="trend-name-group">
                  <Icon name="Wind" size={14} className="text-caution" />
                  <span>Surface Wind Velocity</span>
                </div>
                <div className="trend-val-group">
                  <b>18 km/h</b>
                  <span className="delta-badge up">↑ 5% ENE gust</span>
                </div>
              </div>

              <div className="trend-row-item">
                <div className="trend-name-group">
                  <Icon name="Compass" size={14} />
                  <span>Coastal Current Drift</span>
                </div>
                <div className="trend-val-group">
                  <b>0.6 m/s</b>
                  <span className="delta-badge steady">Steady southerly</span>
                </div>
              </div>
            </div>
          </Card>

          {/* Sensor Drift & Telemetry Audit Card */}
          <Card className="telemetry-audit-card">
            <SectionHeader
              title="Telemetry Integrity"
              badge="HEALTHY"
              icon="CheckCircle"
            />

            <div className="audit-items-list">
              <div className="audit-item">
                <span>Input Data Drift</span>
                <Badge tone="green">LOW (0.02)</Badge>
              </div>
              <div className="audit-item">
                <span>Prediction Drift</span>
                <Badge tone="green">NONE (0.00)</Badge>
              </div>
              <div className="audit-item">
                <span>Acoustic Profiler (ADCP)</span>
                <Badge tone="green">99.8% CALIBRATED</Badge>
              </div>
              <div className="audit-item">
                <span>Telemetry Ingestion Packet Loss</span>
                <Badge tone="green">0.01% (OPTIMAL)</Badge>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Secondary Bottom Area Chart: Marine Risk Probability Horizon */}
      <Card className="risk-trend-card" style={{ marginTop: '14px' }}>
        <SectionHeader
          title="Composite Marine Operational Risk Probability Horizon (30 Days)"
          badge="PREDICTIVE ENSEMBLE"
          icon="ShieldAlert"
          action="Scenario Lab"
          onAction={() => router.push('/scenarios')}
        />
        <Chart type="area" metric="risk" />
      </Card>
    </AppShell>
  );
}
