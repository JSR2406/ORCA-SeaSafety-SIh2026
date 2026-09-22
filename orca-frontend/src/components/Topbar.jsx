'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import Icon from './Icon';
import { useTheme } from '../context/ThemeContext';
import { useLanguage } from '../context/LanguageContext';
import { getHazards } from '../services/apiClient';

export default function Topbar({
  isCollapsed = false,
  onToggleCollapse,
  onMobileMenuClick
}) {
  const router = useRouter();
  const { theme: currentTheme, setTheme, themes, activeThemeMeta } = useTheme();
  const { language, setLanguage, t, languages } = useLanguage();

  const [query, setQuery] = useState('');
  const [langOpen, setLangOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [activeAlertsCount, setActiveAlertsCount] = useState(5);

  useEffect(() => {
    let isSubscribed = true;
    getHazards().then((res) => {
      if (isSubscribed && res && res.hazards) {
        setActiveAlertsCount(res.hazards.length);
      }
    }).catch(() => {});
    return () => { isSubscribed = false; };
  }, []);

  const searchInputRef = useRef(null);
  const searchContainerRef = useRef(null);
  const themeMenuRef = useRef(null);
  const langMenuRef = useRef(null);

  // Global Keyboard Shortcut (⌘K / Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
        setIsSearchFocused(true);
      }
      if (e.key === 'Escape') {
        setIsSearchFocused(false);
        setThemeOpen(false);
        setLangOpen(false);
        searchInputRef.current?.blur();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Click Outside to Dismiss Search Flyout & Dropdowns
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target)) {
        setIsSearchFocused(false);
      }
      if (themeMenuRef.current && !themeMenuRef.current.contains(e.target)) {
        setThemeOpen(false);
      }
      if (langMenuRef.current && !langMenuRef.current.contains(e.target)) {
        setLangOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearch = (e) => {
    if (e.key === 'Enter' && query.trim()) {
      setIsSearchFocused(false);
      router.push(`/ai-copilot?q=${encodeURIComponent(query.trim())}`);
    }
  };

  const executeQuickNav = (path) => {
    setIsSearchFocused(false);
    router.push(path);
  };

  // Quick Command Suggestions
  const searchSuggestions = [
    {
      id: 'copilot-query',
      icon: 'Bot',
      title: 'Ask AI Copilot',
      desc: query.trim() ? `Analyze: "${query.trim()}"` : 'Is Route B fairway safe for departure today?',
      action: () => executeQuickNav(`/ai-copilot?q=${encodeURIComponent(query.trim() || 'Is Route B fairway safe for departure today?')}`),
      badge: 'AI Reasoning',
      badgeTone: 'blue'
    },
    {
      id: 'pfz-zone',
      icon: 'Fish',
      title: 'Kochi Offshore Upwelling (PFZ-01)',
      desc: 'Satellite chlorophyll 0.88 mg/m³ • SST 28.7°C • 14.2 km SW',
      action: () => executeQuickNav('/fishing'),
      badge: 'High Potential',
      badgeTone: 'green'
    },
    {
      id: 'fairway-buoy',
      icon: 'Compass',
      title: 'Cochin Fairway Light Buoy (RW Iso.4s)',
      desc: 'Nautical Waypoint WP-02 • 24m Sounded Depth',
      action: () => executeQuickNav('/marine-map'),
      badge: 'AtoN Channel',
      badgeTone: 'cyan'
    },
    {
      id: 'naval-danger',
      icon: 'ShieldAlert',
      title: 'NAVAREA VIII Active Exclusion Warnings',
      desc: 'Sector Bravo naval firing exercises • Notice #0482',
      action: () => executeQuickNav('/alerts'),
      badge: 'Hazard Notice',
      badgeTone: 'red'
    }
  ];

  return (
    <header className="topbar">
      <div className="topbar-left">
        {/* Mobile Hamburger Menu Toggle */}
        {onMobileMenuClick && (
          <button
            type="button"
            className="topbar-mobile-btn mobile-only"
            onClick={onMobileMenuClick}
            aria-label="Open Navigation Drawer"
            title="Open Menu"
          >
            <Icon name="Menu" size={19} />
          </button>
        )}

        {/* Desktop Sidebar Expand Toggle - visible only when sidebar is collapsed */}
        {onToggleCollapse && isCollapsed && (
          <button
            type="button"
            className="topbar-collapse-btn desktop-only"
            onClick={onToggleCollapse}
            title="Expand Sidebar (240px)"
            aria-label="Expand sidebar"
          >
            <Icon name="PanelLeftOpen" size={16} />
          </button>
        )}

        {/* Modern Command Search Bar */}
        <div
          ref={searchContainerRef}
          className={`topbar-search-wrap ${isSearchFocused ? 'focused' : ''}`}
        >
          <Icon name="Search" size={16} className="search-icon" />
          <input
            ref={searchInputRef}
            type="text"
            className="global-search-input"
            placeholder={t('topbar.searchPlaceholder', 'Search ocean telemetry, routes, alerts, or ask AI Copilot... (⌘K)')}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setIsSearchFocused(true)}
            onKeyDown={handleSearch}
          />

          {/* Clear Query Button */}
          {query && (
            <button
              type="button"
              className="search-clear-btn"
              onClick={(e) => {
                e.stopPropagation();
                setQuery('');
                searchInputRef.current?.focus();
              }}
              title="Clear query"
            >
              <Icon name="X" size={13} />
            </button>
          )}

          {/* Command Shortcut Badge */}
          <div className="search-shortcut-group">
            <kbd className="search-kbd">⌘K</kbd>
            <span className="search-shortcut-enter">↵</span>
          </div>

          {/* Quick Suggestions / Command Flyout Dropdown */}
          <AnimatePresence>
            {isSearchFocused && (
              <motion.div
                className="topbar-search-flyout"
                initial={{ opacity: 0, y: 8, scale: 0.99 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 6, scale: 0.99 }}
                transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }}
              >
                <div className="search-flyout-header">
                  <span>{t('topbar.quickNav', 'QUICK NAVIGATION & TELEMETRY FIXES')}</span>
                  <span className="flyout-shortcut-hint">{t('topbar.escToClose', 'Esc to close')}</span>
                </div>

                <div className="search-flyout-list">
                  {searchSuggestions.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="search-flyout-item"
                      onClick={item.action}
                    >
                      <div className={`flyout-icon-box ${item.badgeTone}`}>
                        <Icon name={item.icon} size={15} />
                      </div>
                      <div className="flyout-item-content">
                        <div className="flyout-title-row">
                          <b className="flyout-item-title">{item.title}</b>
                          <span className={`flyout-badge ${item.badgeTone}`}>{item.badge}</span>
                        </div>
                        <p className="flyout-item-desc">{item.desc}</p>
                      </div>
                      <Icon name="ArrowRight" size={13} className="flyout-arrow" />
                    </button>
                  ))}
                </div>

                <div className="search-flyout-footer">
                  <span>{t('topbar.enterToQuery', 'Press Enter to query AI Copilot with current text')}</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <div className="top-actions">
        {/* Theme Factory Switcher Dropdown */}
        <div className="topbar-theme-wrap" ref={themeMenuRef}>
          <button
            type="button"
            className="topbar-theme-btn"
            onClick={() => {
              setThemeOpen(!themeOpen);
              setLangOpen(false);
            }}
            title={`Active Theme: ${activeThemeMeta.name}`}
            aria-label="Select visual theme"
          >
            <span
              className="topbar-theme-dot"
              style={{ background: activeThemeMeta.primary }}
            />
            <span className="topbar-theme-name desktop-only">{activeThemeMeta.name}</span>
            <Icon name="ChevronDown" size={11} className="theme-chevron" />
          </button>

          <AnimatePresence>
            {themeOpen && (
              <motion.div
                className="topbar-theme-dropdown"
                initial={{ opacity: 0, y: 6, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 4, scale: 0.96 }}
                transition={{ duration: 0.15 }}
              >
                <div className="dropdown-label">{t('topbar.themeFactory', 'THEME FACTORY PALETTES')}</div>
                {themes.map((th) => {
                  const isSelected = currentTheme === th.id;
                  return (
                    <button
                      key={th.id}
                      type="button"
                      className={`topbar-theme-opt ${isSelected ? 'active' : ''}`}
                      onClick={() => {
                        setTheme(th.id);
                        setThemeOpen(false);
                      }}
                    >
                      <div className="theme-opt-color" style={{ background: th.primary }} />
                      <div className="theme-opt-info">
                        <span className="theme-opt-name">{th.name}</span>
                        <span className="theme-opt-desc">{th.desc}</span>
                      </div>
                      {isSelected && <Icon name="Check" size={13} className="theme-opt-check" />}
                    </button>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Alerts Center Bell */}
        <button
          type="button"
          className="topbar-icon-btn"
          title={`${activeAlertsCount} Active Maritime Warnings`}
          onClick={() => router.push('/alerts')}
        >
          <Icon name="Bell" size={16} />
          {activeAlertsCount > 0 && <span className="topbar-badge">{activeAlertsCount}</span>}
        </button>

        {/* Regional Language Switcher */}
        <div className="lang-dropdown-wrapper" ref={langMenuRef}>
          <button
            type="button"
            className="lang-pill-btn"
            onClick={() => {
              setLangOpen(!langOpen);
              setThemeOpen(false);
            }}
            title="Switch Regional Indian Language"
          >
            <Icon name="Globe" size={13} />
            <span style={{ fontWeight: 600 }}>{language.toUpperCase()}</span>
            <Icon name="ChevronDown" size={11} />
          </button>

          <AnimatePresence>
            {langOpen && (
              <motion.div
                className="lang-menu-dropdown"
                initial={{ opacity: 0, y: 6, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 4, scale: 0.96 }}
                transition={{ duration: 0.15 }}
              >
                <div className="dropdown-label">{t('topbar.languageTitle', 'SELECT REGIONAL LANGUAGE / भाषा')}</div>
                {languages.map((item) => {
                  const isSelected = language === item.code;
                  return (
                    <button
                      key={item.code}
                      type="button"
                      className={`topbar-lang-opt ${isSelected ? 'active' : ''}`}
                      onClick={() => {
                        setLanguage(item.code);
                        setLangOpen(false);
                      }}
                    >
                      <span className="lang-opt-flag">{item.flag}</span>
                      <div className="lang-opt-info">
                        <span className="lang-opt-native">{item.native}</span>
                        <span className="lang-opt-label">{item.name} ({item.code.toUpperCase()})</span>
                      </div>
                      {isSelected && <Icon name="Check" size={13} className="lang-opt-check" />}
                    </button>
                  );
                })}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Separator before user profile */}
        <div className="topbar-divider" />

        {/* User Profile Avatar with Online Ring */}
        <div
          className="topbar-profile"
          title="Dr. Ananya Kumar (Principal Oceanographer) — Click for Settings"
          onClick={() => router.push('/settings')}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              router.push('/settings');
            }
          }}
          aria-label="User profile settings"
        >
          <div className="avatar-wrap">
            <div className="avatar-sm">AK</div>
            <span className="avatar-online-dot" />
          </div>
          <div className="profile-text-group desktop-only">
            <span className="profile-name">Dr. Ananya</span>
            <span className="profile-role">Oceanographer</span>
          </div>
        </div>
      </div>
    </header>
  );
}
