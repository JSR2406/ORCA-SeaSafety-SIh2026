'use client';

import Link from 'next/link';
import { ArrowRight, ArrowUpRight, ArrowDown, Waves, ScanLine, Compass, Fish, ShieldCheck, Radio, GitBranch, MessageSquare, Satellite, MapPin } from 'lucide-react';
import Logo from '../components/Logo';
import MarineMap from '../components/DynamicMarineMap';
import { LandingControls } from '../components/LandingControls';
import { useLanguage } from '../context/LanguageContext';

const pathways = [
  { number: '01', icon: ScanLine, title: 'See the bigger picture', text: 'Ocean layers. One connected view.', href: '/marine-map', action: 'Explore the map' },
  { number: '02', icon: MessageSquare, title: 'Ask. Understand. Decide.', text: 'Complex marine data, in your words.', href: '/ai-copilot', action: 'Meet your copilot' },
  { number: '03', icon: Compass, title: 'Find a better way forward', text: 'More informed journeys at sea.', href: '/routes', action: 'Plan a route' },
];

export default function LandingPage() {
  const { t } = useLanguage();
  return (
    <div className="ocean-landing" data-testid="landing-page">
      <a className="ocean-skip-link" href="#ocean-story" data-testid="landing-skip-link">Skip to content</a>
      <header className="ocean-landing-nav" data-testid="landing-navigation">
        <Link href="/" aria-label="ORCA home" data-testid="landing-home-link"><Logo /></Link>
        <nav aria-label="Main navigation" className="ocean-landing-links">
          <a href="#capabilities" data-testid="landing-capabilities-link">The platform</a>
          <Link href="/marine-map" data-testid="landing-map-link">Ocean explorer</Link>
          <Link href="/ai-copilot" data-testid="landing-copilot-link">AI Copilot <span>ASK ORCA</span></Link>
          <Link href="/safety" data-testid="landing-safety-link">Safety & alerts</Link>
        </nav>
        <LandingControls />
      </header>

      <main id="ocean-story">
        <section className="ocean-hero" aria-labelledby="ocean-hero-title">
          <img className="ocean-hero-image" src="/images/ocean-aerial.jpg" alt="Aerial view of turquoise ocean currents and breaking waves" fetchPriority="high" />
          <div className="ocean-hero-shade" aria-hidden="true" />
          <div className="ocean-hero-grid" aria-hidden="true" />
          <div className="ocean-hero-content">
            <div className="ocean-hero-kicker" data-testid="landing-kicker"><span /> MARINE INTELLIGENCE. HUMAN IMPACT.</div>
            <h1 id="ocean-hero-title" data-testid="landing-hero-heading">{t('ocean.heroLineOne', 'An ocean of data.')}<br /><span>{t('ocean.heroLineTwo', 'A clearer direction.')}</span></h1>
            <p data-testid="landing-hero-description">Understand the waters. Discover possibilities. Navigate with insight.<br className="hero-desktop-break" /> Collaborative AI, bringing the ocean closer to everyone.</p>
            <div className="ocean-hero-actions">
              <Link href="/dashboard" className="ocean-button primary" data-testid="launch-workspace-button">{t('ocean.launch', 'Open your workspace')} <ArrowUpRight size={19} /></Link>
              <Link href="/ai-copilot" className="ocean-button outline" data-testid="ask-orca-button"><MessageSquare size={17} /> Ask ORCA</Link>
            </div>
            <div className="ocean-hero-footnote" data-testid="landing-purpose"><span className="hero-footnote-line" /> Built for the people who depend on the sea.</div>
          </div>
          <div className="ocean-hero-coordinate" data-testid="landing-coordinate"><MapPin size={14} /> 09°58′ N &nbsp; 076°16′ E <span>KOCHI, INDIA</span></div>
          <div className="ocean-field-note" data-testid="landing-field-note"><div><Satellite size={15} /><span>FROM SPACE TO SHORE</span></div><p>Many perspectives.<br />One connected ocean.</p><span className="field-note-rule" /><small>OBSERVE / REASON / RESPOND</small></div>
          <div className="ocean-hero-bottom"><span data-testid="landing-problem-id">SIH 2026 <i /> PROBLEM STATEMENT 26176</span><a href="#capabilities" data-testid="landing-discover-link">Discover what lies beneath <ArrowDown size={14} /></a><span className="ocean-edition" data-testid="landing-edition">THE OCEAN INTELLIGENCE EDITION — 01</span></div>
        </section>

        <section className="ocean-pathways" id="capabilities" aria-label="Explore the platform">
          {pathways.map(({ number, icon: Icon, title, text, href, action }) => <Link href={href} className="ocean-pathway" key={number} data-testid={`landing-pathway-${number}`}><span className="pathway-number">{number} /</span><div><Icon size={24} strokeWidth={1.4} /><h2 data-testid={`pathway-heading-${number}`}>{title}</h2><p>{text}</p><span className="pathway-action">{action} <ArrowRight size={15} /></span></div><ArrowUpRight className="pathway-corner" size={18} /></Link>)}
        </section>

        <section className="ocean-explorer-story" data-testid="landing-explorer-section">
          <div className="ocean-story-copy"><span className="ocean-eyebrow">01 / A SHARED PERSPECTIVE</span><h2 data-testid="landing-explorer-heading">A clearer picture<br />of your waters.</h2><p>From sea surface temperature to potential fishing zones, explore the layers that shape life at sea. Connect the dots without getting lost in the data.</p><div className="ocean-story-tags"><span><Waves size={15} /> Ocean conditions</span><span><Fish size={15} /> Fishing zones</span><span><ShieldCheck size={15} /> Marine advisories</span></div><Link className="ocean-text-link" href="/marine-map" data-testid="landing-full-map-link">Open ocean explorer <ArrowUpRight size={17} /></Link></div>
          <div className="ocean-map-frame"><div className="ocean-map-caption"><span><span className="ocean-beacon" /> KOCHI COASTAL REGION</span><span>INTERACTIVE MAP · SAMPLE OVERLAYS</span></div><div className="ocean-story-map"><MarineMap showControls={false} /></div><div className="ocean-map-foot"><span>Explore. Zoom. Find your perspective.</span><Compass size={16} /></div></div>
        </section>

        <section className="ocean-collaboration" data-testid="landing-collaboration-section"><div><span className="ocean-eyebrow">02 / BETTER TOGETHER</span><h2 data-testid="landing-collaboration-heading">Not just an answer.<br />A connected understanding.</h2><p>ORCA brings specialized perspectives together, helping turn complex questions into contextual, explainable marine insights.</p><Link href="/workflow" className="ocean-text-link" data-testid="landing-workflow-link">Explore the agent architecture <ArrowUpRight size={17} /></Link></div><div className="ocean-agent-stack">{[{ icon: MessageSquare, title: 'You ask', desc: 'A question, in your own language.', n: '01' }, { icon: GitBranch, title: 'Agents collaborate', desc: 'Weather, ocean, and spatial perspectives.', n: '02' }, { icon: Radio, title: 'Insight comes together', desc: 'Context, evidence, and a clearer next step.', n: '03' }].map(({ icon: Icon, title, desc, n }) => <div className="ocean-agent-step" key={n} data-testid={`landing-agent-step-${n}`}><span className="agent-step-icon"><Icon size={20} /></span><div><h3>{title}</h3><p>{desc}</p></div><span>{n}</span></div>)}</div></section>
        <section className="ocean-final-invite"><Waves size={30} strokeWidth={1.2} /><div><h2 data-testid="landing-invite-heading">The ocean has a story. Let’s understand it.</h2><p>Your next insight starts with a question.</p></div><Link href="/dashboard" className="ocean-button primary" data-testid="landing-bottom-workspace-link">Explore ORCA <ArrowUpRight size={18} /></Link></section>
      </main>

      <footer className="ocean-landing-footer"><div><Logo /><p data-testid="landing-footer-purpose">Marine ecosystem reasoning.<br />Collaborative intelligence. Shared possibilities.</p></div><div className="ocean-footer-links"><Link href="/fishing" data-testid="footer-fishing-link">Fishing intelligence</Link><Link href="/knowledge" data-testid="footer-knowledge-link">Knowledge center</Link><Link href="/multilingual" data-testid="footer-language-link">Your language</Link><Link href="/system-health" data-testid="footer-health-link">System status</Link></div><div className="ocean-footer-bottom" data-testid="landing-footer-legal"><span>© 2026 ORCA · Built for Smart India Hackathon</span><span>An independent SIH prototype · Not an official navigational service</span></div></footer>
    </div>
  );
}