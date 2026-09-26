'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import Icon from './Icon';
import Logo from './Logo';
import { navGroups } from '../data/mock';
import { useLanguage } from '../context/LanguageContext';

const GROUP_TRANSLATION_KEYS = {
  'CORE OPERATIONS': 'navGroup.operations',
  'TOOLS & INTELLIGENCE': 'navGroup.tools',
  'TECHNICAL': 'navGroup.technical',
};

const NAV_ITEM_TRANSLATION_KEYS = {
  '/dashboard': 'nav.dashboard',
  '/ai-copilot': 'nav.copilot',
  '/fishing': 'nav.fishing',
  '/safety': 'nav.safety',
  '/routes': 'nav.routes',
  '/alerts': 'nav.alerts',
  '/marine-map': 'nav.marineMap',
  '/marine-explorer': 'nav.marineExplorer',
  '/multilingual': 'nav.multilingual',
  '/knowledge': 'nav.knowledge',
  '/scenarios': 'nav.scenarios',
  '/analytics': 'nav.analytics',
  '/ml-governance': 'nav.mlGovernance',
  '/system-health': 'nav.systemHealth',
  '/workflow': 'nav.workflow',
  '/mobile': 'nav.mobile',
};

export default function Sidebar({
  isCollapsed = false,
  onToggleCollapse,
  mobileOpen = false,
  onMobileClose
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useLanguage();

  // Check if current route is inside the technical/collapsible group
  const isTechnicalRoute = navGroups
    .find(g => g.collapsible)
    ?.items.some(item => pathname === item.path);

  const [techExpanded, setTechExpanded] = useState(Boolean(isTechnicalRoute));
  const sidebarRef = useRef(null);

  useEffect(() => {
    if (!mobileOpen) return;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    sidebarRef.current?.querySelector('button[aria-label="Close menu"]')?.focus();
    const handleKey = (event) => {
      if (event.key === 'Escape') onMobileClose?.();
      if (event.key === 'Tab') {
        const items = [...sidebarRef.current.querySelectorAll('a, button, [tabindex="0"]')].filter(el => el.getClientRects().length);
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', handleKey); previousFocus?.focus(); };
  }, [mobileOpen]);

  useEffect(() => {
    if (isTechnicalRoute) {
      setTechExpanded(true);
    }
  }, [isTechnicalRoute]);

  const handleNavClick = () => {
    if (onMobileClose) {
      onMobileClose();
    }
  };

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className="sidebar-mobile-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onMobileClose}
          />
        )}
      </AnimatePresence>

      <aside
        ref={sidebarRef}
        aria-label="Workspace navigation"
        data-testid="workspace-sidebar"
        className={`sidebar ${isCollapsed ? 'sidebar--collapsed' : ''} ${
          mobileOpen ? 'sidebar--mobile-open' : ''
        }`}
      >
        {/* Top Header with Logo and Collapse/Close controls */}
        <div className="side-top">
          <Link href="/" className="side-top-brand" onClick={handleNavClick} data-testid="sidebar-home-link">
            <Logo compact={isCollapsed} />
          </Link>

          <div className="side-top-actions">
            {/* Desktop Rail Collapse Toggle - visible only when expanded */}
            {onToggleCollapse && !isCollapsed && (
              <button
                type="button"
                className="side-rail-toggle desktop-only"
                onClick={onToggleCollapse}
                title="Collapse Navigation (Rail Mode)"
                aria-label="Collapse sidebar"
                data-testid="sidebar-collapse-button"
              >
                <Icon name="PanelLeftClose" size={15} />
              </button>
            )}

            {/* Mobile Close Button */}
            {onMobileClose && (
              <button
                type="button"
                className="side-mobile-close mobile-only"
                onClick={onMobileClose}
                aria-label="Close menu"
                data-testid="sidebar-close-button"
              >
                <Icon name="X" size={18} />
              </button>
            )}
          </div>
        </div>

        {/* Navigation List */}
        <nav className="side-nav">
          {navGroups.map((group) => {
            const isCollapsible = group.collapsible;
            const isExpanded = !isCollapsible || techExpanded;

            return (
              <div key={group.label} className="nav-group">
                {/* Group Heading */}
                {!isCollapsed && (
                  <div
                    className={`nav-group-label ${isCollapsible ? 'nav-group-label--toggle' : ''}`}
                    onClick={isCollapsible ? () => setTechExpanded((v) => !v) : undefined}
                    role={isCollapsible ? 'button' : undefined}
                    data-testid={`sidebar-group-${group.label.toLowerCase().replaceAll(' ', '-')}`}
                    aria-expanded={isCollapsible ? techExpanded : undefined}
                    tabIndex={isCollapsible ? 0 : undefined}
                    onKeyDown={
                      isCollapsible
                        ? (e) => e.key === 'Enter' && setTechExpanded((v) => !v)
                        : undefined
                    }
                  >
                    <span>{t(GROUP_TRANSLATION_KEYS[group.label] || group.label, group.label)}</span>
                    {isCollapsible && (
                      <span className={`nav-group-chevron ${techExpanded ? 'open' : ''}`}>
                        <Icon name="ChevronDown" size={11} strokeWidth={2.5} />
                      </span>
                    )}
                  </div>
                )}

                {/* Collapsed mode group divider */}
                {isCollapsed && <div className="nav-group-divider" />}

                {/* Items */}
                <AnimatePresence initial={false}>
                  {isExpanded && (
                    <motion.div
                      className="nav-group-items"
                      initial={isCollapsible ? { height: 0, opacity: 0 } : false}
                      animate={isCollapsible ? { height: 'auto', opacity: 1 } : false}
                      exit={isCollapsible ? { height: 0, opacity: 0 } : false}
                      transition={{ duration: 0.18, ease: 'easeInOut' }}
                    >
                      {group.items.map((item) => {
                        const isActive = pathname === item.path;
                        const translatedLabel = t(NAV_ITEM_TRANSLATION_KEYS[item.path] || item.label, item.label);

                        return (
                          <div key={item.path} className="nav-item-wrapper">
                            <Link
                              href={item.path}
                              data-testid={`sidebar-${item.path.slice(1)}-link`}
                              aria-current={isActive ? 'page' : undefined}
                              onClick={handleNavClick}
                              className={`nav-item ${isActive ? 'active' : ''}`}
                              title={isCollapsed ? translatedLabel : undefined}
                            >
                              {/* Sliding Active Pill */}
                              {isActive && (
                                <motion.div
                                  layoutId="sidebarActivePill"
                                  className="nav-item-active-pill"
                                  transition={{
                                    type: 'spring',
                                    stiffness: 380,
                                    damping: 32
                                  }}
                                />
                              )}

                              <span className="nav-item-icon">
                                <Icon name={item.icon} size={16} strokeWidth={2} />
                              </span>

                              {!isCollapsed && (
                                <>
                                  <span className="nav-item-label">{translatedLabel}</span>
                                  {item.badge && (
                                    <span
                                      className={`nav-badge ${
                                        item.badge === 'LIVE' ? 'live' : ''
                                      } ${item.badge === 'AI' ? 'ai' : ''}`}
                                    >
                                      {item.badge === 'LIVE' && (
                                        <span className="nav-badge-pulse" />
                                      )}
                                      {item.badge}
                                    </span>
                                  )}
                                </>
                              )}

                              {isCollapsed && item.badge === 'LIVE' && (
                                <span className="nav-collapsed-dot" />
                              )}
                            </Link>

                            {/* Floating Tooltip in Rail Mode */}
                            {isCollapsed && (
                              <div className="nav-rail-tooltip">
                                <span className="tooltip-text">{translatedLabel}</span>
                                {item.badge && (
                                  <span className="tooltip-badge">{item.badge}</span>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </nav>

        {/* Intelligence Pro Promo Card (Compact Marine Copilot) */}
        {!isCollapsed && (
          <div className="sidebar-promo-card">
            <div className="promo-card-header">
              <span className="promo-card-icon">
                <Icon name="Sparkles" size={13} />
              </span>
              <b className="promo-card-title">{t('ocean.sidebarTitle', 'AI Oceanic Copilot')}</b>
            </div>
            <p className="promo-card-desc">{t('ocean.sidebarDescription', 'Ocean reasoning & navigational directives.')}</p>
            <button
              type="button"
              className="promo-card-btn"
              data-testid="sidebar-consult-copilot"
              onClick={() => router.push('/ai-copilot')}
            >
              <span>{t('nav.consultCopilot', 'Consult Copilot')} ↗</span>
            </button>
          </div>
        )}

        {/* User Mini Profile at bottom */}
        <div className="side-bottom">
          <div
            className={`user-mini ${isCollapsed ? 'user-mini--collapsed' : ''}`}
            onClick={() => router.push('/settings')}
            title="Dr. Ananya Kumar (Principal Oceanographer) — Click for Settings"
            role="button"
            data-testid="sidebar-profile-link"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                router.push('/settings');
              }
            }}
          >
            <div className="avatar">
              <span>AK</span>
              <span className="avatar-online" title="Telemetry Linked" />
            </div>

            {!isCollapsed && (
              <>
                <div className="user-mini-info">
                  <b>Dr. Ananya Kumar</b>
                  <span>{t('nav.userRole', 'Oceanographer • INCOIS')}</span>
                </div>
                <button
                  type="button"
                  className="user-mini-action"
                  data-testid="sidebar-settings-button"
                  title="Profile & Telemetry Settings"
                  onClick={(e) => {
                    e.stopPropagation();
                    router.push('/settings');
                  }}
                >
                  <Icon name="SlidersHorizontal" size={14} />
                </button>
              </>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
