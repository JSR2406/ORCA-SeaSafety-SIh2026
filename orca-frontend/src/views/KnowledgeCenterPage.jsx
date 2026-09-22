'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import Card from '../components/Card';
import Badge from '../components/Badge';
import SectionHeader from '../components/SectionHeader';
import Icon from '../components/Icon';
import { knowledgeDocs } from '../data/mock';

export default function KnowledgeCenterPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const [selectedGazetteDoc, setSelectedGazetteDoc] = useState(null);

  const filteredDocs = knowledgeDocs.filter((doc) => {
    const matchesCat = activeCategory === 'All' || doc.category === activeCategory;
    const matchesSearch = doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          doc.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          doc.source.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  return (
    <AppShell
      title="Oceanic Knowledge &amp; Regulatory Library"
      subtitle="Maritime Regulations, Sustainable Fisheries Protocols &amp; Disaster Guidelines (RAG Indexed)"
      actions={
        <div className="knowledge-header-actions">
          <Badge tone="blue" dot>5 DOCUMENTS INDEXED</Badge>
          <button
            className="btn primary btn-sm"
            onClick={() => router.push('/ai-copilot?q=Summarize+all+Kerala+marine+fishing+regulations+for+2026')}
          >
            <Icon name="Bot" size={13} />
            <span>Ask Copilot to Summarize</span>
          </button>
        </div>
      }
    >
      {/* Semantic Search Bar */}
      <input
        type="text"
        className="knowledge-search-modern"
        placeholder="Search marine regulations, coastal CRZ notifications, bycatch laws, cyclone manuals..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
      />

      {/* Suggested Search Chips */}
      <div className="knowledge-quick-tags">
        <span className="tags-label">FREQUENT INQUIRIES:</span>
        {['MFRA 2024 Amendments', 'Trawling Ban Dates', 'PFZ Methodology', 'IMBL Coordinates', 'NDMA Cyclone Safety'].map((tag) => (
          <button
            key={tag}
            className="knowledge-tag-chip"
            onClick={() => setSearchQuery(tag)}
          >
            {tag}
          </button>
        ))}
      </div>

      {/* Category Tabs Bar */}
      <div className="tabs-modern" style={{ margin: '14px 0' }}>
        {['All', 'Regulations', 'Advisories', 'Research', 'Reports'].map((cat) => (
          <button
            key={cat}
            className={`tab-btn ${activeCategory === cat ? 'active' : ''}`}
            onClick={() => setActiveCategory(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Publications List Card */}
      <Card className="knowledge-main-card">
        <SectionHeader
          title={`Indexed Publications (${filteredDocs.length})`}
          badge="SEMANTIC PGVECTOR SEARCH"
          icon="BookOpen"
        />

        <div className="knowledge-docs-list">
          {filteredDocs.map((doc) => (
            <div key={doc.id} className="knowledge-doc-item">
              <div className="doc-icon-box">
                <Icon name="FileText" size={20} />
              </div>

              <div className="doc-content-col">
                <div className="doc-headline-row">
                  <h3 className="doc-title">{doc.title}</h3>
                  <div className="doc-badges">
                    <Badge tone="blue">{doc.category}</Badge>
                    <span className="relevance-score">{doc.relevance} Match</span>
                  </div>
                </div>

                <div className="doc-source-row">
                  <Icon name="Building" size={12} />
                  <span>{doc.source}</span>
                  <span>•</span>
                  <span>Updated: {doc.updated}</span>
                  <span>•</span>
                  <span>{doc.readTime}</span>
                </div>

                <p className="doc-abstract">{doc.summary}</p>

                <div className="doc-actions-row">
                  <button
                    className="btn secondary btn-sm"
                    onClick={() => setSelectedGazetteDoc(doc)}
                  >
                    <Icon name="FileText" size={12} />
                    <span>View Gazette Provisions</span>
                  </button>
                  <button
                    className="btn primary btn-sm"
                    onClick={() => router.push(`/ai-copilot?q=What+does+the+document+"${encodeURIComponent(doc.title)}"+mandate+for+fishermen?`)}
                  >
                    <Icon name="Bot" size={12} />
                    <span>Ask AI About this Policy</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Official Gazette Document Viewer Modal */}
      {selectedGazetteDoc && (
        <div className="maritime-modal-overlay" onClick={() => setSelectedGazetteDoc(null)}>
          <div className="maritime-modal-window wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-bar">
              <div className="modal-header-title">
                <Icon name="FileText" size={18} className="text-accent" />
                <span>OFFICIAL STATUTORY GAZETTE VIEWER • EXTRAORDINARY ISSUE</span>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedGazetteDoc(null)}>
                <Icon name="X" size={16} />
              </button>
            </div>

            <div className="modal-body-content">
              {/* Official Gazette Letterhead */}
              <div className="gazette-doc-paper">
                <div className="gazette-paper-emblem">🇮🇳</div>
                <div className="gazette-paper-header">
                  <h4>THE GAZETTE OF INDIA : EXTRAORDINARY</h4>
                  <p>PART II — SECTION 3 — SUB-SECTION (ii)</p>
                  <span>PUBLISHED BY AUTHORITY • MINISTRY OF FISHERIES &amp; EARTH SCIENCES</span>
                </div>

                <div className="gazette-meta-divider">
                  <span>Notification Ref: <b>GOI-MFRA-{selectedGazetteDoc.id}-2026</b></span>
                  <span>Promulgated: <b>{selectedGazetteDoc.updated}</b></span>
                </div>

                <div className="gazette-title-block">
                  <h3>{selectedGazetteDoc.title}</h3>
                  <span className="gazette-issuing-auth">Issuing Department: {selectedGazetteDoc.source}</span>
                </div>

                <div className="gazette-clause-section">
                  <div className="clause-item">
                    <b>SECTION 1 — SHORT TITLE, JURISDICTION &amp; COMMENCEMENT</b>
                    <p>
                      (1) These regulations may be cited as the <em>{selectedGazetteDoc.title}</em>.<br/>
                      (2) They shall extend to the entire Exclusive Economic Zone (EEZ) of the Union of India, specifically coastal sectors adjoining the State of Kerala (Lat 08°15'N to 12°48'N).<br/>
                      (3) They shall come into force immediately upon publication in the Official Gazette.
                    </p>
                  </div>

                  <div className="clause-item">
                    <b>SECTION 2 — STATUTORY PROHIBITIONS &amp; COMPLIANCE DIRECTIVES</b>
                    <p>
                      {selectedGazetteDoc.summary}
                    </p>
                    <ul>
                      <li><b>Trawling Gear Restrictions:</b> Minimum square mesh cod-end size set to 35mm for fish trawls and 25mm for shrimp trawls.</li>
                      <li><b>Zone Buffer Clearances:</b> Mechanized vessels exceeding 15m overall length strictly prohibited from harvesting within 12 nautical miles from low-water coastline mark.</li>
                      <li><b>Geofence Integrity:</b> Any vessel encroaching upon NAVAREA VIII Sector Bravo during notified firing schedules shall face immediate suspension of registration under Section 14.</li>
                    </ul>
                  </div>

                  <div className="clause-item">
                    <b>SECTION 3 — PENALTIES AND ENFORCEMENT PROTOCOLS</b>
                    <p>
                      Authorized officers of the Indian Coast Guard and State Fisheries Directorate are empowered to seize unauthorized catches, impound vessels, and impose statutory fines up to ₹2,50,000 for first offenses.
                    </p>
                  </div>
                </div>

                <div className="gazette-signature-block">
                  <div className="sig-line">
                    <b>(Dr. S. K. Nambiar)</b><br/>
                    <span>Joint Secretary to the Government of India</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="modal-footer-bar">
              <button className="btn secondary" onClick={() => setSelectedGazetteDoc(null)}>
                Close Viewer
              </button>
              <button
                className="btn primary"
                onClick={() => {
                  const blob = new Blob([
                    `THE GAZETTE OF INDIA : EXTRAORDINARY\n${selectedGazetteDoc.title}\n${selectedGazetteDoc.source}\nUpdated: ${selectedGazetteDoc.updated}\n\nPROVISIONS:\n${selectedGazetteDoc.summary}\n\nEnforced by Coast Guard & Fisheries Dept.`
                  ], { type: 'text/plain' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `${selectedGazetteDoc.id}_Gazette_Provisions.txt`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                <Icon name="Download" size={14} />
                <span>Export Official Provisions (.TXT)</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
