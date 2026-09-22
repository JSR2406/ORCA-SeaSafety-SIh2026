'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Mic, MicOff, Volume2, VolumeX, Loader2, MapPin, ChevronDown, ChevronUp, Download, FileText, Globe, Waves, Thermometer, AlertTriangle, CheckCircle, XCircle, HelpCircle } from 'lucide-react';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { EvidenceCard } from '@/components/evidence/EvidenceCard';
import { FloatMap } from '@/components/map/FloatMap';
import { DepthProfileChart, TimeSeriesChart } from '@/components/charts/Charts';
import { VoiceRecorder } from '@/components/voice/VoiceRecorder';
import { cn } from '@/lib/utils';
import type { ChatResponse, StructuredQuery, EvidenceRecord, ChartVisualizationData, MapVisualizationData } from '@floatchat/shared-types';

const EXAMPLE_QUERIES = [
  'Show temperature profiles in the Arabian Sea during July 2025',
  'What is the salinity trend near Kerala coast?',
  'Compare oxygen levels in Bay of Bengal vs Arabian Sea',
  'नालെ 40 കിലോമീറ്റർ കടലിലേക്ക് പോകുന്നത് സുരക്ഷിതമാണോ?',
  'Explain unusual warming at 100m depth in Arabian Sea',
  'What if current warming continues for 5 years?',
];

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [showExamples, setShowExamples] = useState(true);
  const [activeTab, setActiveTab] = useState<'chat' | 'evidence' | 'map' | 'charts'>('chat');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const handleSendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      content,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setInputValue('');
    setShowExamples(false);

    try {
      const response = await fetch(`${API_URL}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          mode: 'researcher',
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: ChatResponse = await response.json();
      setLastResponse(data);

      const aiMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        content: data.answer,
        isUser: false,
        timestamp: new Date(),
        structuredQuery: data.structured_query,
        visualizations: data.visualizations,
        evidence: data.evidence,
        audioUrl: data.audio_url,
        status: data.status,
        clarificationQuestion: data.clarification_question,
      };

      setMessages((prev) => [...prev, aiMessage]);
      setActiveTab('chat');
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        content: `Error: ${error instanceof Error ? error.message : 'Failed to get response'}`,
        isUser: false,
        timestamp: new Date(),
        isError: true,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExampleClick = (query: string) => {
    handleSendMessage(query);
  };

  const handleVoiceTranscript = (transcript: string) => {
    setInputValue(transcript);
  };

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-ocean-500 text-white">
                <Waves className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-foreground">FloatChat</h1>
                <p className="text-xs text-muted-foreground">Ask the Ocean, in Your Language</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted text-sm text-muted-foreground">
                <Globe className="h-3.5 w-3.5" />
                <span>ARGO Indian Ocean 2015-2025</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        <div className="container mx-auto h-full px-4">
          <div className="flex h-[calc(100vh-4rem)] gap-4">
            {/* Sidebar - Examples & History */}
            <aside className="w-72 flex-shrink-0 hidden lg:block">
              <div className="h-full flex flex-col gap-4">
                {/* Example Queries */}
                {showExamples && messages.length === 0 && (
                  <div className="rounded-xl border border-border bg-card p-4">
                    <h3 className="font-semibold text-foreground mb-3 flex items-center gap-2">
                      <HelpCircle className="h-4 w-4" />
                      Try asking
                    </h3>
                    <div className="space-y-2">
                      {EXAMPLE_QUERIES.map((query, i) => (
                        <button
                          key={i}
                          onClick={() => handleExampleClick(query)}
                          disabled={isLoading}
                          className="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-muted transition-colors border border-border bg-background text-foreground"
                        >
                          {query}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Voice Input */}
                <div className="rounded-xl border border-border bg-card p-4">
                  <h3 className="font-semibold text-foreground mb-3 flex items-center gap-2">
                    <Mic className="h-4 w-4" />
                    Voice Input
                  </h3>
                  <VoiceRecorder onTranscript={handleVoiceTranscript} disabled={isLoading} />
                </div>

                {/* Quick Stats */}
                {lastResponse?.evidence && (
                  <div className="rounded-xl border border-border bg-card p-4">
                    <h3 className="font-semibold text-foreground mb-3">Last Query Stats</h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Floats</span>
                        <span className="font-mono">{lastResponse.evidence.float_ids.length}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Profiles</span>
                        <span className="font-mono">{lastResponse.evidence.profile_count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Observations</span>
                        <span className="font-mono">{lastResponse.evidence.observation_count}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Confidence</span>
                        <span className={cn('font-mono font-medium', {
                          'text-emerald-600': lastResponse.evidence.confidence.label === 'high',
                          'text-amber-600': lastResponse.evidence.confidence.label === 'medium',
                          'text-rose-600': lastResponse.evidence.confidence.label === 'low',
                        })}>
                          {lastResponse.evidence.confidence.label}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </aside>

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col min-w-0">
              {/* Tab Navigation */}
              <div className="flex border-b border-border mb-4">
                {[
                  { id: 'chat', label: 'Chat', icon: <MessageSquare className="h-4 w-4" /> },
                  { id: 'evidence', label: 'Evidence', icon: <FileText className="h-4 w-4" /> },
                  { id: 'map', label: 'Map', icon: <MapPin className="h-4 w-4" /> },
                  { id: 'charts', label: 'Charts', icon: <BarChart3 className="h-4 w-4" /> },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors border-b-2',
                      activeTab === tab.id
                        ? 'border-primary text-primary'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    )}
                    disabled={!lastResponse && tab.id !== 'chat'}
                  >
                    {tab.icon} {tab.label}
                  </button>
                ))}
              </div>

              {/* Content Panels */}
              <div className="flex-1 overflow-auto">
                {activeTab === 'chat' && (
                  <ChatInterface
                    messages={messages}
                    isLoading={isLoading}
                    onSendMessage={handleSendMessage}
                    inputValue={inputValue}
                    setInputValue={setInputValue}
                    lastResponse={lastResponse}
                  />
                )}

                {activeTab === 'evidence' && lastResponse && (
                  <EvidenceCard
                    evidence={lastResponse.evidence}
                    structuredQuery={lastResponse.structured_query}
                  />
                )}

                {activeTab === 'map' && lastResponse?.visualizations?.map && (
                  <div className="h-[600px]">
                    <FloatMap
                      data={lastResponse.visualizations.map}
                      title="ARGO Float Locations"
                    />
                  </div>
                )}

                {activeTab === 'charts' && lastResponse?.visualizations?.charts && lastResponse.visualizations.charts.length > 0 && (
                  <div className="space-y-6 p-4">
                    {lastResponse.visualizations.charts.map((chart, i) => (
                      <div key={i} className="rounded-xl border border-border bg-card">
                        <div className="p-4 border-b border-border">
                          <h3 className="font-semibold">{chart.title}</h3>
                          <p className="text-sm text-muted-foreground">
                            {chart.metadata.variable} • {chart.metadata.region} • {chart.metadata.sample_count} samples
                          </p>
                        </div>
                        <div className="p-4 h-[400px]">
                          {chart.type === 'depth_profile' && (
                            <DepthProfileChart data={chart.data} config={chart.config} />
                          )}
                          {chart.type === 'time_series' && (
                            <TimeSeriesChart data={chart.data} config={chart.config} />
                          )}
                          {chart.type === 'anomaly' && (
                            <AnomalyChart data={chart.data} config={chart.config} />
                          )}
                          {chart.type === 'scenario' && (
                            <ScenarioChart data={chart.data} config={chart.config} />
                          )}
                          {chart.type === 'comparison' && (
                            <ComparisonChart data={chart.data} config={chart.config} />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {(!lastResponse || (activeTab !== 'chat' && !lastResponse)) && activeTab !== 'chat' && (
                  <div className="flex h-[400px] items-center justify-center text-muted-foreground">
                    <p>Send a query to see {activeTab}</p>
                  </div>
                )}
              </div>

              {/* Input Area - only show in chat tab */}
              {activeTab === 'chat' && (
                <div className="border-t border-border p-4 bg-card/50">
                  <div className="max-w-4xl mx-auto">
                    <div className="flex items-end gap-2">
                      <VoiceRecorder
                        onTranscript={handleVoiceTranscript}
                        disabled={isLoading}
                        inline
                      />
                      <div className="flex-1 flex items-center gap-2">
                        <textarea
                          value={inputValue}
                          onChange={(e) => setInputValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
                              e.preventDefault();
                              handleSendMessage(inputValue);
                            }
                          }}
                          placeholder="Ask about ARGO data... (Shift+Enter for new line)"
                          disabled={isLoading}
                          rows={1}
                          className="flex-1 min-h-[44px] max-h-[120px] px-4 py-3 rounded-xl border border-border bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                        />
                        <button
                          onClick={() => handleSendMessage(inputValue)}
                          disabled={isLoading || !inputValue.trim()}
                          className="p-3 rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          aria-label="Send message"
                        >
                          <Send className="h-5 w-5" />
                        </button>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground mt-2 text-center">
                      Press Enter to send • Shift+Enter for new line • Click microphone for voice input
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* Safety Disclaimer Footer */}
      <footer className="border-t border-border bg-card/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-3">
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 text-sm text-muted-foreground text-center">
            <div className="flex items-center gap-1.5 text-amber-600">
              <AlertTriangle className="h-4 w-4" />
              <span>Based on historical ARGO observations only. Not a safety forecast.</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Globe className="h-4 w-4" />
              <span>Check INCOIS/IMD official warnings before departure</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

// Types for local use
interface ChatMessage {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;
  structuredQuery?: StructuredQuery;
  visualizations?: ChatResponse['visualizations'];
  evidence?: EvidenceRecord;
  audioUrl?: string | null;
  status?: 'success' | 'needs_clarification' | 'error';
  clarificationQuestion?: string;
  isError?: boolean;
}

// Import icons
import { MessageSquare, BarChart3 } from 'lucide-react';
import { AnomalyChart, ScenarioChart, ComparisonChart } from '@/components/charts/Charts';