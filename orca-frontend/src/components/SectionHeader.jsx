import React from 'react';
import Icon from './Icon';

export default function SectionHeader({ title, action, link, icon, badge, onAction }) {
  const displayAction = action || link;
  return (
    <div className="section-header">
      <div className="section-title-group">
        {icon && <Icon name={icon} size={16} className="section-icon" />}
        <h2 className="section-heading">{title}</h2>
        {badge && <span className="section-badge">{badge}</span>}
      </div>
      {displayAction && (
        <button className="text-link" onClick={onAction}>
          <span>{displayAction}</span>
          <Icon name="ArrowRight" size={12} />
        </button>
      )}
    </div>
  );
}
