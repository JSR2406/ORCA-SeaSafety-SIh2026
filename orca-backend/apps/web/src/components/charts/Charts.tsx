'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area, ScatterChart, Scatter, Cell, BarChart, Bar, ComposedChart } from 'recharts';
import { cn, formatNumber } from '@/lib/utils';
import type { ChartDataPoint, ChartConfig } from '@floatchat/shared-types';

// Color palette
const CHART_COLORS = ['#0ea5e9', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

interface BaseChartProps {
  data: ChartDataPoint[];
  config: ChartConfig;
  className?: string;
  height?: number;
}

export function DepthProfileChart({ data, config, className, height = 400 }: BaseChartProps) {
  // For depth profile, we typically have depth on Y (inverted) and temperature on X
  // Data format: { x: temp, y: depth, group?: string }
  
  const series = config.series || [{ key: 'temperature_c', label: 'Temperature (°C)', color: CHART_COLORS[0] }];
  
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            type="number"
            dataKey="x"
            label={{ value: config.xAxis?.label || 'Temperature (°C)', position: 'bottom', offset: 20 }}
            tickFormatter={(v) => v.toFixed(1)}
          />
          <YAxis
            type="number"
            dataKey="y"
            label={{ value: config.yAxis?.label || 'Depth (m)', position: 'left', offset: -10, angle: -90 }}
            reversed={true}
            tickFormatter={(v) => `${v}m`}
          />
          <Tooltip
            formatter={(value: number, name: string) => [value.toFixed(2), name]}
            labelFormatter={(label) => `Depth: ${label}m`}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
          />
          <Legend />
          {series.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key === 'temperature_c' ? 'x' : s.key}
              name={s.label}
              stroke={s.color || CHART_COLORS[i % CHART_COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6 }}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TimeSeriesChart({ data, config, className, height = 400 }: BaseChartProps) {
  // Data format: { x: date, y: value, group?: string }
  
  const series = config.series || [{ key: 'mean', label: 'Mean', color: CHART_COLORS[0] }];
  
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 20, right: 30, left: 60, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="x"
            type="category"
            label={{ value: config.xAxis?.label || 'Date', position: 'bottom', offset: 20 }}
            tick={{ rotation: 45, dy: 10 }}
            tickFormatter={(v) => {
              try { return new Date(v).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }); } catch { return v; }
            }}
            interval={Math.max(1, Math.floor(data.length / 10))}
          />
          <YAxis
            type="number"
            label={{ value: config.yAxis?.label || 'Value', position: 'left', offset: -10, angle: -90 }}
            tickFormatter={(v) => v.toFixed(2)}
          />
          <Tooltip
            labelFormatter={(label) => {
              try { return new Date(label).toLocaleDateString('en-IN', { year: 'numeric', month: 'long', day: 'numeric' }); } catch { return label; }
            }}
            formatter={(value: number, name: string) => [value.toFixed(2), name]}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
          />
          <Legend />
          {series.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color || CHART_COLORS[i % CHART_COLORS.length]}
              strokeWidth={2}
              dot={{ r: 4, strokeWidth: 2 }}
              activeDot={{ r: 6 }}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AnomalyChart({ data, config, className, height = 400 }: BaseChartProps) {
  // Data: { x: location/depth, y: anomaly_value, baseline: value, current: value, group?: string }
  
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 20, right: 30, left: 60, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="x"
            type={config.xAxis?.type || 'category'}
            label={{ value: config.xAxis?.label || 'Location', position: 'bottom', offset: 20 }}
          />
          <YAxis
            label={{ value: config.yAxis?.label || 'Anomaly', position: 'left', offset: -10, angle: -90 }}
            tickFormatter={(v) => v.toFixed(2)}
          />
          <Tooltip
            formatter={(value: number, name: string) => [value.toFixed(2), name]}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
          />
          <Legend />
          <Bar
            dataKey="anomaly"
            name="Anomaly"
            fill="#ef4444"
            radius={[4, 4, 0, 0]}
          />
          <Line
            type="monotone"
            dataKey="threshold"
            name="Threshold (2σ)"
            stroke="#f59e0b"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ScenarioChart({ data, config, className, height = 400 }: BaseChartProps) {
  // Data: { x: year, y: projected, historical: value, lower: value, upper: value }
  
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 20, right: 30, left: 60, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="x"
            type="number"
            label={{ value: config.xAxis?.label || 'Year', position: 'bottom', offset: 20 }}
            tickFormatter={(v) => v.toString()}
          />
          <YAxis
            label={{ value: config.yAxis?.label || 'Value', position: 'left', offset: -10, angle: -90 }}
            tickFormatter={(v) => v.toFixed(2)}
          />
          <Tooltip
            labelFormatter={(label) => `Year: ${label}`}
            formatter={(value: number, name: string) => [value.toFixed(2), name]}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
          />
          <Legend />
          {/* Uncertainty area */}
          <Area
            type="monotone"
            dataKey="upper"
            name="Uncertainty"
            fill="#0ea5e9"
            fillOpacity={0.15}
            stroke="none"
          />
          <Area
            type="monotone"
            dataKey="lower"
            fill="#888"
            fillOpacity={0}
            stroke="none"
          />
          {/* Historical */}
          <Line
            type="monotone"
            dataKey="historical"
            name="Historical"
            stroke="#22c55e"
            strokeWidth={2}
            dot={{ r: 4 }}
          />
          {/* Projection */}
          <Line
            type="monotone"
            dataKey="y"
            name="Projection"
            stroke="#0ea5e9"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={{ r: 4, fill: '#0ea5e9' }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ComparisonChart({ data, config, className, height = 400 }: BaseChartProps) {
  // Data: { x: category, y: value, group: 'A' | 'B' }
  
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 30, left: 60, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="x"
            type="category"
            label={{ value: config.xAxis?.label || 'Category', position: 'bottom', offset: 20 }}
          />
          <YAxis
            label={{ value: config.yAxis?.label || 'Value', position: 'left', offset: -10, angle: -90 }}
          />
          <Tooltip
            formatter={(value: number, name: string) => [value.toFixed(2), name]}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
          />
          <Legend />
          <Bar dataKey="y" name="Value" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Simple profile chart for individual float profiles
export function ProfileChart({ data, config, className, height = 400 }: BaseChartProps) {
  // Data: individual profile points { depth, temperature, salinity }
  
  return (
    <div className={cn('w-full', className)} style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 20, right: 30, left: 60, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            type="number"
            dataKey="temperature"
            label={{ value: 'Temperature (°C)', position: 'bottom', offset: 20 }}
            tickFormatter={(v) => v.toFixed(1)}
          />
          <YAxis
            type="number"
            dataKey="depth"
            label={{ value: 'Depth (m)', position: 'left', offset: -10, angle: -90 }}
            reversed={true}
            tickFormatter={(v) => `${v}m`}
          />
          <Tooltip
            formatter={(value: number, name: string) => [value.toFixed(2), name]}
            labelFormatter={(label) => `Temp: ${label}°C`}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '8px' }}
          />
          <Legend />
          <Scatter
            name="Temperature"
            data={data}
            fill="#0ea5e9"
            stroke="#0ea5e9"
            shape="circle"
            size={4}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}