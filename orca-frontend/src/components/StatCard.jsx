import React from 'react';
import Icon from './Icon';

export default function StatCard({
  icon,
  title,
  label,
  value,
  sub,
  tone = 'blue',
  trend,
  badge
}) {
  const displayTitle = title || label;
  const testId = `stat-${String(displayTitle).toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;

  return (
    <div className={`stat-card tone-${tone}`} data-testid={testId}>
      <div className="stat-card-header">
        <div className={`stat-icon-wrapper tone-${tone}`}>
          <Icon name={icon || 'Activity'} size={18} strokeWidth={2} />
        </div>
        {badge && <span className={`stat-mini-badge ${tone}`}>{badge}</span>}
      </div>

      <div className="stat-card-content">
        <span className="stat-label">{displayTitle}</span>
        <div className="stat-metric-value" data-testid={`${testId}-value`}>{value}</div>
        {sub && (
          <div className="stat-sub-row">
            {trend && <span className={`stat-trend ${trend.startsWith('↑') ? 'up' : 'down'}`}>{trend}</span>}
            <span className="stat-sub-text">{sub}</span>
          </div>
        )}
      </div>
      <div className={`stat-bottom-indicator tone-${tone}`} />
    </div>
  );
}
