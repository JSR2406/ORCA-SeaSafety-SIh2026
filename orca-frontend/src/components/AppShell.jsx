'use client';

import React, { useState, useEffect } from 'react';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import PageWrapper from './PageWrapper';
import { ConnectionNotice } from './ConnectionNotice';

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
    <div className={`app-shell ${isCollapsed ? 'app-shell--rail' : ''}`} data-testid="app-shell">
      <a className="ocean-skip-link" href="#main-content" data-testid="skip-to-content">Skip to content</a>
      <Sidebar
        isCollapsed={isCollapsed && !mobileOpen}
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

        <ConnectionNotice />

        {title && (
          <div className="page-title-bar">
            <div className="title-text-group">
              <span className="ocean-eyebrow" data-testid="workspace-eyebrow">ORCA / INTELLIGENCE WORKSPACE</span>
              <h1 className="page-heading" data-testid="page-heading">{title}</h1>
              <span className="page-subheading">
                {subtitle || 'Explore your waters. Understand the evidence. Make informed decisions.'}
              </span>
            </div>
            {actions && <div className="page-title-actions">{actions}</div>}
          </div>
        )}

        <main id="main-content" tabIndex={-1} className="ocean-main-content">
        <PageWrapper className="page-content">
          {children}
        </PageWrapper>
        </main>
      </div>
    </div>
  );
}
