'use client';

import React, { useState } from 'react';

const METRIC_DATA = {
  sst: {
    unit: '°C',
    gridLines: ['29.5°C', '29.0°C', '28.5°C', '28.0°C'],
    dataPoints: [
      { label: '29 Aug', time: '06:00', val: 28.1, display: '28.1 °C', normY: 65 },
      { label: '29 Aug', time: '18:00', val: 28.3, display: '28.3 °C', normY: 58 },
      { label: '30 Aug', time: '06:00', val: 28.2, display: '28.2 °C', normY: 62 },
      { label: '30 Aug', time: '18:00', val: 28.5, display: '28.5 °C', normY: 50 },
      { label: '31 Aug', time: '06:00', val: 28.4, display: '28.4 °C', normY: 54 },
      { label: '31 Aug', time: '18:00', val: 28.7, display: '28.7 °C', normY: 42 },
      { label: '01 Sep', time: '06:00', val: 28.6, display: '28.6 °C', normY: 46 },
      { label: '01 Sep', time: '18:00', val: 28.9, display: '28.9 °C', normY: 34 },
      { label: '02 Sep', time: '06:00', val: 28.7, display: '28.7 °C', normY: 42 },
      { label: '02 Sep', time: '18:00', val: 29.1, display: '29.1 °C', normY: 26 },
      { label: '03 Sep', time: '06:00', val: 28.8, display: '28.8 °C', normY: 38 },
      { label: '03 Sep', time: '18:00', val: 28.7, display: '28.7 °C', normY: 42 }
    ]
  },
  chlorophyll: {
    unit: 'mg/m³',
    gridLines: ['1.20', '0.90', '0.60', '0.30'],
    dataPoints: [
      { label: '29 Aug', time: '06:00', val: 0.65, display: '0.65 mg/m³', normY: 60 },
      { label: '29 Aug', time: '18:00', val: 0.72, display: '0.72 mg/m³', normY: 50 },
      { label: '30 Aug', time: '06:00', val: 0.78, display: '0.78 mg/m³', normY: 45 },
      { label: '30 Aug', time: '18:00', val: 0.85, display: '0.85 mg/m³', normY: 38 },
      { label: '31 Aug', time: '06:00', val: 0.82, display: '0.82 mg/m³', normY: 40 },
      { label: '31 Aug', time: '18:00', val: 0.89, display: '0.89 mg/m³', normY: 30 },
      { label: '01 Sep', time: '06:00', val: 0.94, display: '0.94 mg/m³', normY: 25 },
      { label: '01 Sep', time: '18:00', val: 0.88, display: '0.88 mg/m³', normY: 32 },
      { label: '02 Sep', time: '06:00', val: 0.84, display: '0.84 mg/m³', normY: 38 },
      { label: '02 Sep', time: '18:00', val: 0.80, display: '0.80 mg/m³', normY: 44 },
      { label: '03 Sep', time: '06:00', val: 0.82, display: '0.82 mg/m³', normY: 40 },
      { label: '03 Sep', time: '18:00', val: 0.86, display: '0.86 mg/m³', normY: 35 }
    ]
  },
  wind: {
    unit: 'kts',
    gridLines: ['25 kts', '18 kts', '12 kts', '6 kts'],
    dataPoints: [
      { label: '29 Aug', time: '06:00', val: 8.5, display: '8.5 kts', normY: 70 },
      { label: '29 Aug', time: '18:00', val: 11.2, display: '11.2 kts', normY: 58 },
      { label: '30 Aug', time: '06:00', val: 14.0, display: '14.0 kts', normY: 48 },
      { label: '30 Aug', time: '18:00', val: 16.5, display: '16.5 kts', normY: 40 },
      { label: '31 Aug', time: '06:00', val: 18.2, display: '18.2 kts', normY: 32 },
      { label: '31 Aug', time: '18:00', val: 15.0, display: '15.0 kts', normY: 44 },
      { label: '01 Sep', time: '06:00', val: 12.8, display: '12.8 kts', normY: 52 },
      { label: '01 Sep', time: '18:00', val: 10.4, display: '10.4 kts', normY: 62 },
      { label: '02 Sep', time: '06:00', val: 9.6, display: '9.6 kts', normY: 66 },
      { label: '02 Sep', time: '18:00', val: 11.0, display: '11.0 kts', normY: 59 },
      { label: '03 Sep', time: '06:00', val: 13.5, display: '13.5 kts', normY: 50 },
      { label: '03 Sep', time: '18:00', val: 14.8, display: '14.8 kts', normY: 45 }
    ]
  },
  catch: {
    unit: 'tons',
    gridLines: ['4.5 T', '3.5 T', '2.5 T', '1.5 T'],
    dataPoints: [
      { label: '29 Aug', time: '06:00', val: 2.1, display: '2.1 T', normY: 72 },
      { label: '29 Aug', time: '18:00', val: 2.6, display: '2.6 T', normY: 62 },
      { label: '30 Aug', time: '06:00', val: 3.2, display: '3.2 T', normY: 48 },
      { label: '30 Aug', time: '18:00', val: 3.8, display: '3.8 T', normY: 36 },
      { label: '31 Aug', time: '06:00', val: 4.1, display: '4.1 T', normY: 28 },
      { label: '31 Aug', time: '18:00', val: 3.9, display: '3.9 T', normY: 32 },
      { label: '01 Sep', time: '06:00', val: 3.4, display: '3.4 T', normY: 44 },
      { label: '01 Sep', time: '18:00', val: 3.1, display: '3.1 T', normY: 50 },
      { label: '02 Sep', time: '06:00', val: 2.8, display: '2.8 T', normY: 58 },
      { label: '02 Sep', time: '18:00', val: 3.0, display: '3.0 T', normY: 54 },
      { label: '03 Sep', time: '06:00', val: 3.5, display: '3.5 T', normY: 42 },
      { label: '03 Sep', time: '18:00', val: 3.7, display: '3.7 T', normY: 38 }
    ]
  },
  risk: {
    unit: 'Index',
    gridLines: ['0.80', '0.60', '0.40', '0.20'],
    dataPoints: [
      { label: '29 Aug', time: '06:00', val: 0.32, display: '0.32 (Low)', normY: 75 },
      { label: '29 Aug', time: '18:00', val: 0.38, display: '0.38 (Low)', normY: 68 },
      { label: '30 Aug', time: '06:00', val: 0.45, display: '0.45 (Mod)', normY: 58 },
      { label: '30 Aug', time: '18:00', val: 0.58, display: '0.58 (Mod)', normY: 46 },
      { label: '31 Aug', time: '06:00', val: 0.68, display: '0.68 (Elevated)', normY: 34 },
      { label: '31 Aug', time: '18:00', val: 0.61, display: '0.61 (Mod)', normY: 42 },
      { label: '01 Sep', time: '06:00', val: 0.48, display: '0.48 (Mod)', normY: 55 },
      { label: '01 Sep', time: '18:00', val: 0.42, display: '0.42 (Mod)', normY: 62 },
      { label: '02 Sep', time: '06:00', val: 0.35, display: '0.35 (Low)', normY: 70 },
      { label: '02 Sep', time: '18:00', val: 0.39, display: '0.39 (Low)', normY: 65 },
      { label: '03 Sep', time: '06:00', val: 0.44, display: '0.44 (Mod)', normY: 60 },
      { label: '03 Sep', time: '18:00', val: 0.41, display: '0.41 (Mod)', normY: 63 }
    ]
  }
};

export default function Chart({ type = 'line', metric = 'sst' }) {
  const [hoverIndex, setHoverIndex] = useState(null);

  const activeConfig = METRIC_DATA[metric] || METRIC_DATA.sst;
  const dataPoints = activeConfig.dataPoints;

  const width = 600;
  const height = 180;
  const padLeft = 45;
  const padRight = 20;
  const padTop = 25;
  const padBottom = 35;
  const chartW = width - padLeft - padRight;
  const chartH = height - padTop - padBottom;

  const points = dataPoints.map((pt, i) => {
    const x = padLeft + (i / (dataPoints.length - 1)) * chartW;
    const y = padTop + (pt.normY / 100) * chartH;
    return { x, y, ...pt };
  });

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
  const areaD = `${pathD} L ${points[points.length - 1].x} ${height - padBottom} L ${padLeft} ${height - padBottom} Z`;

  return (
    <div className="telemetry-chart-container">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="telemetry-chart-svg"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="chartAreaGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--th-accent-cyan, #0ea5e9)" stopOpacity="0.35" />
            <stop offset="60%" stopColor="var(--th-accent, #0284c7)" stopOpacity="0.08" />
            <stop offset="100%" stopColor="var(--th-accent, #0284c7)" stopOpacity="0.00" />
          </linearGradient>

          <linearGradient id="chartLineGradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--th-accent, #0284c7)" />
            <stop offset="50%" stopColor="var(--th-accent-cyan, #0ea5e9)" />
            <stop offset="100%" stopColor="var(--th-accent-secondary, #38bdf8)" />
          </linearGradient>

          <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="4" floodColor="var(--th-accent-cyan, #0ea5e9)" floodOpacity="0.35" />
          </filter>
        </defs>

        {/* Horizontal Gridlines & Y-Axis Labels */}
        {(activeConfig.gridLines || ['29.5°C', '29.0°C', '28.5°C', '28.0°C']).map((label, idx) => {
          const yPcts = [0.1, 0.35, 0.6, 0.85];
          const yPos = padTop + (yPcts[idx] || 0.5) * chartH;
          return (
            <g key={idx} className="chart-grid-row">
              <text
                x={padLeft - 8}
                y={yPos + 3.5}
                textAnchor="end"
                fill="var(--c-text-muted, #64748b)"
                fontSize="8.5"
                fontFamily="monospace"
              >
                {label}
              </text>
              <line
                x1={padLeft}
                y1={yPos}
                x2={width - padRight}
                y2={yPos}
                stroke="var(--c-border, #e2e8f0)"
                strokeOpacity="0.6"
                strokeWidth="0.85"
                strokeDasharray="4 4"
              />
            </g>
          );
        })}

        {/* X-Axis Baseline */}
        <line
          x1={padLeft}
          y1={height - padBottom}
          x2={width - padRight}
          y2={height - padBottom}
          stroke="var(--c-border, #cbd5e1)"
          strokeWidth="1.2"
        />

        {/* X-Axis Date Labels */}
        {[
          { text: '29 Aug', xIdx: 0 },
          { text: '30 Aug', xIdx: 2 },
          { text: '31 Aug', xIdx: 4 },
          { text: '01 Sep', xIdx: 6 },
          { text: '02 Sep', xIdx: 8 },
          { text: '03 Sep', xIdx: 10 }
        ].map((lbl, idx) => (
          <text
            key={idx}
            x={points[lbl.xIdx]?.x || padLeft}
            y={height - padBottom + 16}
            textAnchor="middle"
            fill="var(--c-text-muted, #64748b)"
            fontSize="8.5"
            fontFamily="monospace"
          >
            {lbl.text}
          </text>
        ))}

        {/* Filled Area (under curve) */}
        <path d={areaD} fill="url(#chartAreaGradient)" />

        {/* Main Telemetry Curve with Glow */}
        <path
          d={pathD}
          fill="none"
          stroke="url(#chartLineGradient)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter="url(#neonGlow)"
        />

        {/* Data Points */}
        {points.map((p, i) => (
          <g
            key={i}
            className="chart-data-node"
            onMouseEnter={() => setHoverIndex(i)}
            onMouseLeave={() => setHoverIndex(null)}
          >
            {/* Hit target */}
            <circle cx={p.x} cy={p.y} r="10" fill="transparent" cursor="pointer" />
            {/* Visual Dot */}
            <circle
              cx={p.x}
              cy={p.y}
              r={hoverIndex === i ? 5 : 3}
              fill={hoverIndex === i ? 'var(--th-text-primary, #ffffff)' : 'var(--th-accent-cyan, #0ea5e9)'}
              stroke="var(--th-accent, #0284c7)"
              strokeWidth={hoverIndex === i ? 2.5 : 1.5}
            />
            {/* Tooltip on hover */}
            {hoverIndex === i && (
              <g transform={`translate(${p.x}, ${p.y - 14})`}>
                <rect
                  x="-32"
                  y="-22"
                  width="64"
                  height="22"
                  rx="4"
                  fill="var(--th-bg-chrome, #0f172a)"
                  stroke="var(--th-accent-cyan, #38bdf8)"
                  strokeWidth="1"
                />
                <text
                  x="0"
                  y="-8"
                  textAnchor="middle"
                  fill="var(--th-text-primary, #ffffff)"
                  fontSize="9"
                  fontWeight="700"
                  fontFamily="monospace"
                >
                  {p.display}
                </text>
              </g>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
