'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Logo from '../components/Logo';
import Icon from '../components/Icon';
import Badge from '../components/Badge';
import Card from '../components/Card';

export default function WorkflowPage() {
  const router = useRouter();
  const [selectedStage, setSelectedStage] = useState(0);

  const stages = [
    {
      step: '01',
      title: 'User Query',
      subtitle: 'Natural Language & Voice Input',
      role: 'Multimodal Input Layer',
      icon: 'MessageSquare',
      latency: '~15 ms',
      tech: 'Whisper Indic ASR • WebSockets',
      desc: 'Accepts unstructured questions in 14 Indian regional languages or English via text or coastal voice radio recordings.',
      sampleInput: 'Is it safe to fish near Kochi tomorrow morning?',
      sampleOutput: '{ intent: "coastal_safety_check", location: "Kochi", temporal: "+1d_morning", vessel: "small_craft" }'
    },
    {
      step: '02',
      title: 'Orchestrator',
      subtitle: 'Intent Routing & DAG Planning',
      role: 'Autonomous Cognitive Planner',
      icon: 'Workflow',
      latency: '~120 ms',
      tech: 'LangGraph • FastAPI State Machine',
      desc: 'Decomposes high-level intent into parallelized sub-tasks. Enforces deterministic safety policies before agent delegation.',
      sampleInput: '{ intent: "coastal_safety_check", sector: "Kochi_4" }',
      sampleOutput: 'DAG: [Task_Marine_SST, Task_IMD_Radar, Task_Naval_Restrictions, Task_PFZ_Upwelling]'
    },
    {
      step: '03',
      title: 'Specialized Agents',
      subtitle: 'Domain Expert Reasoning',
      role: 'Federated Agentic Cluster',
      icon: 'Bot',
      latency: '~340 ms',
      tech: 'Oceanographer • Weather • Safety Agents',
      desc: 'Domain-specific reasoning agents evaluate ocean currents, barometric squall patterns, and marine spatial safety.',
      sampleInput: 'Execute parallelized domain assessments for Kochi offshore shelf.',
      sampleOutput: 'MarineAgent: Wave 1.6m; WeatherAgent: Wind 18km/h; SafetyAgent: Navarea Notice #0482 active'
    },
    {
      step: '04',
      title: 'MCP Tools',
      subtitle: 'Standardized Tool Interface',
      role: 'Model Context Protocol (MCP)',
      icon: 'Wrench',
      latency: '~65 ms',
      tech: 'MCP Server Clusters • JSON-RPC',
      desc: 'Standardized interfaces isolate backend tools from LLM prompts. Strictly prevents direct database or model coupling.',
      sampleInput: 'Call tool: get_wave_forecast(lat=9.93, lon=76.27, hours=24)',
      sampleOutput: '{ significant_wave_height: 1.6, swell_period: 11.4, wave_dir: "WSW" }'
    },
    {
      step: '05',
      title: 'Data Sources',
      subtitle: 'Authoritative Government Feeds',
      role: 'Multi-Sensor Fusion Layer',
      icon: 'Radio',
      latency: '~85 ms',
      tech: 'INCOIS • IMD • NAVTEX • Sentinel-3',
      desc: 'Fuses live ocean buoy telemetry, Doppler weather radar, ISRO satellite ocean colour, and official hydrographic notices.',
      sampleInput: 'Pull moored buoy AD04 telemetry & Sentinel-3 OLCI chlorophyll swath.',
      sampleOutput: 'Verified telemetry frame: SST 28.4°C, Chlorophyll-a 0.88 mg/m³, Baro 1009.4 hPa'
    },
    {
      step: '06',
      title: 'Risk Engine',
      subtitle: 'Deterministic + ML Scoring',
      role: 'Hydrodynamic Risk Evaluation',
      icon: 'ShieldAlert',
      latency: '~45 ms',
      tech: 'SWAN Coupled Models • XGBoost Classifier',
      desc: 'Computes multi-criteria operational safety score. Deterministic rules immediately veto ML predictions if hard safety boundaries breached.',
      sampleInput: '{ wave: 1.6m, wind: 18km/h, restriction: true, vessel_freeboard: 1.1m }',
      sampleOutput: '{ risk_level: "MODERATE", risk_score: 0.61, restriction_flag: true }'
    },
    {
      step: '07',
      title: 'Safety Verifier',
      subtitle: 'Zero-Hallucination Guardrails',
      role: 'Evidence Validation & Audit',
      icon: 'ShieldCheck',
      latency: '~30 ms',
      tech: 'Pydantic Validators • Spatial Boundary Check',
      desc: 'Performs spatial geofence polygon intersection checks and validates that all generated claims are grounded in raw telemetry.',
      sampleInput: 'Validate response claims against NAVAREA message geometry & buoy bounds.',
      sampleOutput: '{ verified: true, claims_grounded: 100%, geofence_clearance: "CORRIDOR_B" }'
    },
    {
      step: '08',
      title: 'Evidence Provenance',
      subtitle: 'Cryptographic Citation Tracking',
      role: 'Explainability & Source Lineage',
      icon: 'FileCheck',
      latency: '~15 ms',
      tech: 'Citation Chain • ISO Provenance',
      desc: 'Attaches verifiable data timestamps, sensor IDs, and official bulletin references so every claim can be audited by coast guard officials.',
      sampleInput: 'Assemble provenance packet for advisory #142.',
      sampleOutput: '{ citations: ["INCOIS_WAM_4.2", "DWR_COCHIN_284", "NAVAREA_0482_2026"] }'
    },
    {
      step: '09',
      title: 'Response Gen',
      subtitle: 'Grounded Actionable Synthesis',
      role: 'Multilingual Natural Language Synthesis',
      icon: 'Sparkles',
      latency: '~210 ms',
      tech: 'Template-Grounded LLM • Confidence Scoring',
      desc: 'Synthesizes clear, concise operational instructions with structured condition cards and confidence ratings in the user native language.',
      sampleInput: 'Synthesize verified advisory for small craft master.',
      sampleOutput: 'Generated operational brief + 5 condition cards + audio translation payload'
    },
    {
      step: '10',
      title: 'Frontend Client',
      subtitle: 'Tactical GIS & Audio Interface',
      role: 'Presentation & Interaction Layer',
      icon: 'Monitor',
      latency: '~10 ms',
      tech: 'React • Leaflet/MapLibre • PWA',
      desc: 'Renders bathymetric GIS charts, route waypoints, and vernacular voice bulletins. Acts purely as a presentation layer.',
      sampleInput: 'Render structured response JSON on map and chat interface.',
      sampleOutput: 'User views live tactical chart, Route B path, and hears audio bulletin.'
    }
  ];

  const active = stages[selectedStage] || stages[0];


  return (
    <div className="workflow-page-layout">
      {/* Header Bar */}
      <header className="workflow-page-header">
        <div className="wf-header-left">
          <Logo />
          <span className="wf-header-sep">/</span>
          <span className="wf-header-title">End-to-End Agentic Architecture (FloatChat Spec)</span>
        </div>

        <div className="wf-header-right">
          <Badge tone="green" dot>BLACK-BOX ARCHITECTURE VERIFIED</Badge>
          <button className="btn ghost btn-sm" onClick={() => router.push('/dashboard')}>
            <Icon name="ArrowLeft" size={13} />
            <span>Dashboard</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="workflow-main-container">
        {/* Title Group */}
        <div className="workflow-title-block">
          <span className="wf-eyebrow">COGNITIVE MARITIME DECISION PIPELINE</span>
          <h1 className="wf-heading">From Coastal Question to Verified Maritime Action.</h1>
          <p className="wf-subline">
            Strict separation of concerns: The frontend owns presentation, interaction, and geospatial charting; the backend owns intent planning, multi-sensor fusion, deterministic risk safety, and evidence provenance.
          </p>
        </div>

        {/* 10-Stage Pipeline Visual Grid */}
        <div className="flow-pipeline-scroll-row">
          {stages.map((st, i) => (
            <React.Fragment key={st.step}>
              <div
                className={`flow-stage-node ${selectedStage === i ? 'selected' : ''}`}
                onClick={() => setSelectedStage(i)}
              >
                <div className="stage-top-meta">
                  <span className="stage-step-num">{st.step}</span>
                  <span className="stage-latency">{st.latency}</span>
                </div>
                <div className="stage-icon-circle">
                  <Icon name={st.icon} size={18} />
                </div>
                <b className="stage-title-text">{st.title}</b>
                <span className="stage-sub-text">{st.subtitle}</span>
              </div>
              {i < stages.length - 1 && (
                <div className="stage-flow-connector">
                  <span className="connector-arrow">→</span>
                  <span className="connector-pulse-dot" />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Interactive Selected Stage Inspection Inspector Card */}
        <Card className="stage-inspector-card">
          <div className="inspector-card-header">
            <div className="inspector-title-group">
              <div className="inspector-icon-box">
                <Icon name={active.icon} size={22} className="text-accent" />
              </div>
              <div>
                <div className="inspector-step-tag">STAGE {active.step} OF 10 • {active.role}</div>
                <h2>{active.title} — {active.subtitle}</h2>
              </div>
            </div>

            <div className="inspector-meta-badges">
              <span className="latency-badge">Latency Budget: <b>{active.latency}</b></span>
              <span className="tech-badge">Framework: <b>{active.tech}</b></span>
            </div>
          </div>

          <p className="inspector-desc-p">{active.desc}</p>

          {/* I/O Contracts Simulation */}
          <div className="inspector-contracts-grid">
            <div className="contract-box">
              <div className="contract-box-header">
                <Icon name="ArrowRightCircle" size={13} className="text-safe" />
                <b>STAGE INPUT CONTRACT:</b>
              </div>
              <pre className="contract-code-block">{active.sampleInput}</pre>
            </div>

            <div className="contract-box">
              <div className="contract-box-header">
                <Icon name="CheckCircle2" size={13} className="text-accent" />
                <b>STAGE OUTPUT CONTRACT:</b>
              </div>
              <pre className="contract-code-block">{active.sampleOutput}</pre>
            </div>
          </div>
        </Card>

        {/* Executive Footer Banner */}
        <div className="workflow-executive-footer">
          <div className="footer-brand-side">
            <Logo />
            <div className="footer-motto">
              <b>ORCA Maritime Safety System</b>
              <span>Ocean Reasoning with Collaborative Agent • Smart India Hackathon Grand Finalist</span>
            </div>
          </div>

          <div className="footer-mission-side">
            <span className="mission-quote">"For People. For Oceans. For a Safer Tomorrow."</span>
            <span className="gov-partners">In Cooperation with INCOIS • IMD • Ministry of Earth Sciences</span>
          </div>
        </div>
      </main>
    </div>
  );
}
