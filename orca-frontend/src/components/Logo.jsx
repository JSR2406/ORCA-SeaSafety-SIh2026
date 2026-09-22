import React from 'react';

export default function Logo({ dark = false, compact = false }) {
  return (
    <div className={`logo ${dark ? 'logo-dark' : ''} ${compact ? 'logo-compact' : ''}`}>
      <div className="logo-mark">
        <img
          src="/logo.png"
          alt="ORCA Ocean Waves Logo"
          className="logo-img"
        />
      </div>
      {!compact && (
        <div className="logo-text-group">
          <div className="logo-word">ORCA</div>
          <div className="logo-sub">Ocean Reasoning with Collaborative Agent</div>
        </div>
      )}
    </div>
  );
}
