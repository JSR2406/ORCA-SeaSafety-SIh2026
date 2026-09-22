'use client';

import React from 'react';
import Icon from './Icon';

export default function MinimalistTelemetryBar({ onSelectMetric, activeMetric = 'swell' }) {
  const metrics = [
    {
      id: 'risk',
      label: 'VOYAGE RISK',
      value: '0.61',
      unit: '/ 1.0',
      status: 'Moderate Caution',
      tone: 'orange',
      icon: 'ShieldAlert',
    },
    {
      id: 'swell',
      label: 'SEA STATE',
      value: '1.4',
      unit: 'm Hs',
      status: 'Douglas 3 (11.8s)',
      tone: 'green',
      icon: 'Waves',
    },
    {
      id: 'wind',
      label: 'SURFACE WIND',
      value: '9.7',
      unit: 'kts',
      status: '065° ENE (Beaufort 3)',
      tone: 'green',
      icon: 'Wind',
    },
    {
      id: 'sst',
      label: 'SURFACE TEMP',
      value: '28.7',
      unit: '°C',
      status: 'Thermal Front 14km SW',
      tone: 'blue',
      icon: 'Thermometer',
    },
    {
      id: 'tide',
      label: 'TIDAL STAGE',
      value: '+1.2',
      unit: 'm',
      status: 'Ebb (High 22:15 IST)',
      tone: 'blue',
      icon: 'Compass',
    },
  ];

  return (
    <div className="telemetry-bar-clean">
      {metrics.map((m, idx) => {
        const isSelected = activeMetric === m.id;
        return (
          <div
            key={m.id}
            className={`telemetry-cell ${idx > 0 ? 'with-divider' : ''} ${isSelected ? 'selected' : ''}`}
            onClick={() => onSelectMetric?.(m.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectMetric?.(m.id)}
          >
            <div className="cell-top">
              <span className="cell-label">{m.label}</span>
              <span className={`cell-dot dot-${m.tone}`} />
            </div>

            <div className="cell-value-group">
              <span className="cell-num">{m.value}</span>
              <span className="cell-unit">{m.unit}</span>
            </div>

            <div className="cell-status-line">
              <span className="status-text">{m.status}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
