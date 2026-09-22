'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { Globe2, Palette, Check, Menu, X, ArrowUpRight } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useLanguage } from '../context/LanguageContext';

export const LandingControls = () => {
  const [open, setOpen] = useState(null);
  const container = useRef(null);
  const { theme, setTheme, themes } = useTheme();
  const { language, setLanguage, languages } = useLanguage();
  useEffect(() => {
    const dismiss = (e) => {
      if (e.key === 'Escape' || (e.type === 'pointerdown' && !container.current?.contains(e.target))) setOpen(null);
    };
    document.addEventListener('keydown', dismiss);
    document.addEventListener('pointerdown', dismiss);
    return () => { document.removeEventListener('keydown', dismiss); document.removeEventListener('pointerdown', dismiss); };
  }, []);
  return (
    <div className="landing-utilities" ref={container}>
      <button className="landing-utility" aria-label="Choose language" aria-expanded={open === 'language'} data-testid="landing-language-toggle" onClick={() => setOpen(open === 'language' ? null : 'language')}><Globe2 size={16} /><span>{language.toUpperCase()}</span></button>
      <button className="landing-utility" aria-label="Choose theme" aria-expanded={open === 'theme'} data-testid="landing-theme-toggle" onClick={() => setOpen(open === 'theme' ? null : 'theme')}><Palette size={17} /></button>
      <Link href="/login" className="landing-signin" data-testid="landing-sign-in">Sign in <ArrowUpRight size={14} /></Link>
      <button className="landing-utility landing-menu-toggle" aria-label={open === 'menu' ? 'Close navigation' : 'Open navigation'} aria-expanded={open === 'menu'} data-testid="landing-menu-toggle" onClick={() => setOpen(open === 'menu' ? null : 'menu')}>{open === 'menu' ? <X size={20} /> : <Menu size={20} />}</button>
      {open && <div className="landing-popover" data-testid={`landing-${open}-menu`}>
        <span className="ocean-eyebrow">{open === 'theme' ? 'YOUR OCEAN, YOUR PALETTE' : open === 'language' ? 'SPEAK YOUR LANGUAGE' : 'EXPLORE ORCA'}</span>
        {open === 'theme' && themes.map(item => <button key={item.id} data-testid={`landing-theme-${item.id}`} onClick={() => { setTheme(item.id); setOpen(null); }}><i style={{ background: item.primary }} />{item.name}{theme === item.id && <Check size={15} />}</button>)}
        {open === 'language' && languages.map(item => <button key={item.code} data-testid={`landing-language-${item.code}`} onClick={() => { setLanguage(item.code); setOpen(null); }}><span>{item.native}</span><small>{item.name}</small>{language === item.code && <Check size={15} />}</button>)}
        {open === 'menu' && [['/dashboard', 'Open workspace'], ['/marine-map', 'Explore the ocean'], ['/ai-copilot', 'AI Copilot'], ['/fishing', 'Fishing intelligence'], ['/safety', 'Safety center'], ['/login', 'Sign in']].map(([href, label]) => <Link href={href} key={href} onClick={() => setOpen(null)} data-testid={`landing-mobile-${href.slice(1)}`}>{label}<ArrowUpRight size={15} /></Link>)}
      </div>}
    </div>
  );
};