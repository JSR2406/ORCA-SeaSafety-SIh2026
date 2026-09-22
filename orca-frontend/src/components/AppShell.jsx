'use client';

import React, { useState, useEffect } from 'react';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import PageWrapper from './PageWrapper';

export default function AppShell({ children, title, subtitle, actions }) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem('orca-sidebar-collapsed');
      if (saved === 'true') {
        setIsCollapsed(true);
      }
    } catch (e) {
      console.warn('Unable to read sidebar state:', e);
    }
  }, []);

  const handleToggleCollapse = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('orca-sidebar-collapsed', String(next));
      } catch (e) {}
      return next;
    });
  };

  return (
    <div className={`app-shell ${isCollapsed ? 'app-shell--rail' : ''}`}>
      <Sidebar
        isCollapsed={isCollapsed}
        onToggleCollapse={handleToggleCollapse}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />

      <div className={`main ${isCollapsed ? 'main--rail' : ''}`}>
        <Topbar
          isCollapsed={isCollapsed}
          onToggleCollapse={handleToggleCollapse}
          onMobileMenuClick={() => setMobileOpen(true)}
        />

        {title && (
          <div className="page-title-bar">
            <div className="title-text-group">
              <h1 className="page-heading">{title}</h1>
              <span className="page-subheading">
                {subtitle || 'INCOIS • IMD • NAVAREA VIII Live Operational Telemetry'}
              </span>
            </div>
            {actions && <div className="page-title-actions">{actions}</div>}
          </div>
        )}

        <PageWrapper className="page-content">
          {children}
        </PageWrapper>
      </div>
    </div>
  );
}
