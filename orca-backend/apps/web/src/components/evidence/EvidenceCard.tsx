'use client';

import { ChevronDown, ChevronUp, CheckCircle, XCircle, AlertCircle, Info, ExternalLink, Copy, Globe, Clock, Database, Filter, Target, Layers, Award } from 'lucide-react';
import { cn, formatNumber, getConfidenceColor } from '@/lib/utils';
import type { EvidenceRecord, StructuredQuery } from '@floatchat/shared-types';

interface EvidenceCardProps {
  evidence: EvidenceRecord;
  structuredQuery: StructuredQuery;
}

export function EvidenceCard({ evidence, structuredQuery }: EvidenceCardProps) {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    overview: true,
    query: true,
    data: true,
    quality: true,
    confidence: true,
    limitations: true,
    sources: true,
    steps: true,
  });

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const renderSection = (title: string, icon: React.ReactNode, sectionKey: string, children: React.ReactNode) => (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      <button
        onClick={() => toggleSection(sectionKey)}
        className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
        aria-expanded={expandedSections[sectionKey]}
      >
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center">{icon}</div>
          <h3 className="font-semibold text-foreground">{title}</h3>
        </div>
        {expandedSections[sectionKey] ? <ChevronUp className="h-5 w-5 text-muted-foreground" /> : <ChevronDown className="h-5 w-5 text-muted-foreground" />}
      </button>
      {expandedSections[sectionKey] && (
        <div className="px-4 pb-4 border-t border-border animate-in fade-in-0 duration-200">
          {children}
        </div>
      )}
    </div>
  );

  const renderKeyValue = (label: string, value: string | number | null | undefined, icon?: React.ReactNode, tooltip?: string) => (
    <div className="flex items-start gap-3 py-2">
      {icon && <span className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5">{icon}</span>}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="font-mono text-foreground truncate">{value ?? '—'}</p>
      </div>
      {tooltip && <Info className="h-4 w-4 text-muted-foreground hover:text-foreground cursor-help" title={tooltip} />}
    </div>
  );

  const renderBadge = (label: string, colorClass: string) => (
    <span className={cn('px-2 py-0.5 rounded text-xs font-medium', colorClass)}>{label}</span>
  );

  return (
    <div className="space-y-6 p-4 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-ocean-100 flex items-center justify-center">
            <Award className="h-5 w-5 text-ocean-600" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-foreground">Evidence & Provenance</h2>
            <p className="text-sm text-muted-foreground">Every number traced to source data</p>
          </div>
        </div>
        <div className={cn('px-3 py-1 rounded-full text-sm font-medium border', getConfidenceColor(evidence.confidence.label))}>
          {evidence.confidence.label.toUpperCase()} CONFIDENCE
        </div>
      </div>

      {/* Verification Status */}
      <div className={cn('p-3 rounded-lg flex items-center gap-3', evidence.verified ? 'bg-emerald-50 border border-emerald-200' : 'bg-amber-50 border border-amber-200')}>
        {evidence.verified ? (
          <>
            <CheckCircle className="h-5 w-5 text-emerald-600" />
            <span className="text-emerald-800 font-medium">All numeric claims verified</span>
          </>
        ) : (
          <>
            <AlertCircle className="h-5 w-5 text-amber-600" />
            <span className="text-amber-800 font-medium">Verification pending or failed</span>
          </>
        )}
        {evidence.verification_errors && evidence.verification_errors.length > 0 && (
          <button className="ml-auto text-xs text-amber-600 hover:underline">View {evidence.verification_errors.length} error(s)</button>
        )}
      </div>

      <div className="space-y-4">
        {/* Overview */}
        {renderSection('Overview', <Globe className="h-4 w-4" />, 'overview', (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {renderKeyValue('Float IDs', evidence.float_ids.join(', ') || '—', <Target className="h-4 w-4" />)}
            {renderKeyValue('Profiles', formatNumber(evidence.profile_count), <Database className="h-4 w-4" />)}
            {renderKeyValue('Observations', formatNumber(evidence.observation_count), <Layers className="h-4 w-4" />)}
            {renderKeyValue('Data Freshness', `${evidence.data_freshness.days_old} days (${evidence.data_freshness.source})`, <Clock className="h-4 w-4" />)}
          </div>
        ))}

        {/* Structured Query */}
        {renderSection('Structured Query', <FileText className="h-4 w-4" />, 'query', (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {renderBadge(`Intent: ${structuredQuery.intent}`, 'bg-blue-100 text-blue-700')}
              {renderBadge(`Language: ${structuredQuery.language}`, 'bg-green-100 text-green-700')}
              {renderBadge(`Quality: ${structuredQuery.quality_filter}`, 'bg-purple-100 text-purple-700')}
              {renderBadge(`Limit: ${structuredQuery.limit}`, 'bg-gray-100 text-gray-700')}
            </div>
            <pre className="p-3 bg-muted rounded text-xs font-mono overflow-x-auto max-h-64">{JSON.stringify(structuredQuery, null, 2)}</pre>
          </div>
        ))}

        {/* Data Coverage */}
        {renderSection('Data Coverage', <Database className="h-4 w-4" />, 'data', (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-3 rounded-lg bg-muted/50">
                <p className="text-sm text-muted-foreground">Region</p>
                <pre className="text-xs font-mono mt-1">{JSON.stringify(evidence.region, null, 2)}</pre>
              </div>
              {evidence.depth_range_m && (
                <div className="p-3 rounded-lg bg-muted/50">
                  <p className="text-sm text-muted-foreground">Depth Range (m)</p>
                  <p className="font-mono mt-1">{evidence.depth_range_m.min} – {evidence.depth_range_m.max}</p>
                </div>
              )}
              <div className="p-3 rounded-lg bg-muted/50">
                <p className="text-sm text-muted-foreground">Time Range</p>
                <p className="font-mono mt-1">{evidence.time_range.start} to {evidence.time_range.end}</p>
              </div>
            </div>
          </div>
        ))}

        {/* Quality Filters */}
        {renderSection('Quality Control', <Filter className="h-4 w-4" />, 'quality', (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">{evidence.quality_filters.description}</p>
            <div className="flex flex-wrap gap-2">
              {evidence.quality_filters.filters.map((f, i) => (
                <span key={i} className="px-2 py-1 rounded bg-muted border border-border text-sm font-mono">{f}</span>
              ))}
            </div>
          </div>
        ))}

        {/* Confidence Breakdown */}
        {renderSection('Confidence Breakdown', <Award className="h-4 w-4" />, 'confidence', (
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-muted/50">
              <p className="text-sm text-muted-foreground">Overall Score</p>
              <p className="text-3xl font-bold font-mono mt-1">{Math.round(evidence.confidence.score * 100)}%</p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(evidence.confidence.components).map(([key, value]) => (
                <div key={key} className="p-3 rounded-lg bg-muted/50">
                  <p className="text-xs text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${value * 100}%` }} />
                    </div>
                    <span className="font-mono text-sm w-12 text-right">{Math.round(value * 100)}%</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-sm text-muted-foreground">{evidence.confidence.explanation}</p>
          </div>
        ))}

        {/* Limitations */}
        {renderSection('Limitations', <AlertCircle className="h-4 w-4" />, 'limitations', (
          <ul className="space-y-2">
            {evidence.limitations.length === 0 ? (
              <li className="text-sm text-muted-foreground">No specific limitations identified</li>
            ) : (
              evidence.limitations.map((lim, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <AlertCircle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
                  <span>{lim}</span>
                </li>
              ))
            )}
          </ul>
        ))}

        {/* Sources */}
        {renderSection('Data Sources', <ExternalLink className="h-4 w-4" />, 'sources', (
          <div className="space-y-3">
            <div className="p-3 rounded-lg bg-muted/50">
              <p className="text-sm text-muted-foreground">Dataset</p>
              <p className="font-mono mt-1">{evidence.source_identifiers.dataset}</p>
            </div>
            <div className="p-3 rounded-lg bg-muted/50">
              <p className="text-sm text-muted-foreground">Snapshot</p>
              <p className="font-mono mt-1">{evidence.source_identifiers.snapshot}</p>
            </div>
            {evidence.source_identifiers.doi && (
              <div className="p-3 rounded-lg bg-muted/50">
                <p className="text-sm text-muted-foreground">DOI</p>
                <p className="font-mono mt-1">{evidence.source_identifiers.doi}</p>
              </div>
            )}
            {evidence.source_identifiers.source_urls.length > 0 && (
              <div className="p-3 rounded-lg bg-muted/50">
                <p className="text-sm text-muted-foreground">Source URLs</p>
                <ul className="mt-1 space-y-1">
                  {evidence.source_identifiers.source_urls.map((url, i) => (
                    <li key={i} className="flex items-center gap-2 text-xs">
                      <ExternalLink className="h-3 w-3 text-muted-foreground" />
                      <a href={url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate font-mono">{url}</a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}

        {/* Query Steps */}
        {renderSection('Query Execution Steps', <List className="h-4 w-4" />, 'steps', (
          <div className="space-y-2">
            {evidence.query_steps.length === 0 ? (
              <p className="text-sm text-muted-foreground">No step details available</p>
            ) : (
              evidence.query_steps.map((step, i) => (
                <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
                  <span className="h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">{step.step}</span>
                  <div className="flex-1">
                    <p className="font-medium text-sm">{step.tool}</p>
                    <p className="text-xs text-muted-foreground">{step.result_count} results {step.duration_ms ? `• ${step.duration_ms}ms` : ''}</p>
                  </div>
                  <pre className="text-xs font-mono text-muted-foreground max-w-xs overflow-hidden">{JSON.stringify(step.params)}</pre>
                </div>
              ))
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

import { useState } from 'react';
import { List } from 'lucide-react';