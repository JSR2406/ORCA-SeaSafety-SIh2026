"use client";

import { useState, useRef, useEffect } from "react";
import { Mic, Send, MicOff, Volume2, VolumeX, Globe, FileText, AlertTriangle } from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  language?: string;
  evidence?: any[];
  visualizations?: any;
  riskAssessment?: any;
  status?: string;
  limitations?: string[];
  sources?: string[];
}

/** Cached geolocation (browser permission granted once, reused across turns).
 *  Falls back to null when the browser has no geolocation / denies access -
 *  the backend then resolves location from message/context or requests input. */
let cachedPosition: { latitude: number; longitude: number } | null | undefined;
function getCachedPosition(): Promise<{ latitude: number; longitude: number; source: string } | null> {
  if (cachedPosition !== undefined) return Promise.resolve(cachedPosition);
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    cachedPosition = null;
    return Promise.resolve(null);
  }
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        cachedPosition = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
        resolve({ ...cachedPosition, source: "GPS" });
      },
      () => {
        cachedPosition = null;
        resolve(null);
      },
      { timeout: 3000, maximumAge: 600000 },
    );
  });
}

interface ChatMessage {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;
  structuredQuery?: any;
  visualizations?: any;
  evidence?: any;
  audioUrl?: string | null;
  status?: string;
  clarificationQuestion?: string;
  isError?: boolean;
}

interface ChatInterfaceProps {
  messages?: ChatMessage[];
  isLoading?: boolean;
  onSendMessage?: (content: string) => Promise<void> | void;
  inputValue?: string;
  setInputValue?: (value: string) => void;
  lastResponse?: any;
  onVoiceStart?: () => void;
  onVoiceStop?: () => void;
}

export function ChatInterface({
  onVoiceStart,
  onVoiceStop,
  messages: externalMessages,
  isLoading: externalIsLoading,
  onSendMessage,
  inputValue: externalInput,
  setInputValue: externalSetInput,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Welcome to ORCA! I'm your marine intelligence assistant. Ask me about ocean conditions, route safety, hazards, or scenario projections. I support 10 Indian coastal languages.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState("en-IN");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const conversationIdRef = useRef<string | null>(null);

  const controlled = typeof externalMessages !== "undefined";
  const displayMessages: Message[] = controlled
    ? (externalMessages ?? []).map((m) => ({
        id: m.id,
        role: m.isUser ? "user" : "assistant",
        content: m.content,
        timestamp: m.timestamp,
        status: m.status,
        evidence: m.evidence ? [m.evidence] : [],
      }))
    : messages;
  const displayInput = controlled ? externalInput ?? "" : input;
  const displayLoading = controlled ? externalIsLoading ?? false : isLoading;

  const setDisplayInput = (value: string) => {
    if (controlled) {
      externalSetInput?.(value);
    } else {
      setInput(value);
    }
  };
  
  const languages = [
    { code: "en-IN", name: "English", flag: "🇮🇳" },
    { code: "hi-IN", name: "हिंदी", flag: "🇮🇳" },
    { code: "ml-IN", name: "മലയാളം", flag: "🇮🇳" },
    { code: "ta-IN", name: "தமிழ்", flag: "🇮🇳" },
    { code: "te-IN", name: "తెలుగు", flag: "🇮🇳" },
    { code: "bn-IN", name: "বাংলা", flag: "🇮🇳" },
    { code: "gu-IN", name: "ગુજરાતી", flag: "🇮🇳" },
    { code: "mr-IN", name: "मराठी", flag: "🇮🇳" },
    { code: "or-IN", name: "ଓଡ଼ିଆ", flag: "🇮🇳" },
    { code: "kn-IN", name: "ಕನ್ನಡ", flag: "🇮🇳" },
  ];
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages, externalMessages]);

  const handleSubmitInner = async (raw: string) => {
    const userInput = raw.trim();
    if (!userInput || displayLoading) return;

    if (controlled) {
      await onSendMessage?.(userInput);
      return;
    }

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: userInput,
      timestamp: new Date(),
      language: selectedLanguage,
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    const conversationId = conversationIdRef.current ?? undefined;
    const response = await requestOrchestrate(userInput, selectedLanguage, conversationId);
    if (response?.conversation_id) {
      conversationIdRef.current = response.conversation_id;
    }

    const assistantMessage: Message = {
      id: `msg-${Date.now() + 1}`,
      role: "assistant",
      content: response?.answer ?? "I could not reach the marine intelligence service. No safety conclusion is offered.",
      timestamp: new Date(),
      language: response?.language ?? selectedLanguage,
      riskAssessment: response?.risk
        ? {
            classification: response.risk.classification || response.risk.level,
            score: response.confidence?.score ?? 0,
            reasoning: (response.limitations ?? []).join(". "),
          }
        : undefined,
      status: response?.status,
      limitations: response?.limitations,
      sources: (response as any)?.provenance?.sources
        ? Array.isArray((response as any).provenance.sources)
          ? (response as any).provenance.sources.map((s: unknown) => String(s))
          : undefined
        : undefined,
    };
    setMessages(prev => [...prev, assistantMessage]);
    setIsLoading(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSubmitInner(displayInput);
  };

  async function requestOrchestrate(message: string, language: string, conversationId?: string) {
    try {
      const { api } = await import("../../lib/api-client");
      const userLocation = await getCachedPosition();
      return await api.orchestrate({
        query: message,
        session_id: conversationId,
        language: language as any,
        requested_outputs: ["text", "map", "charts", "alerts", "route", "evidence"],
        ...(userLocation ? { user_location: userLocation } : {}),
      });
    } catch {
      return null;
    }
  }
  
  const handleVoiceToggle = () => {
    if (isRecording) {
      setIsRecording(false);
      onVoiceStop?.();
    } else {
      setIsRecording(true);
      onVoiceStart?.();
    }
  };
  
  const handleLanguageChange = (lang: string) => {
    setSelectedLanguage(lang);
  };
  
  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg flex items-center justify-center text-white font-bold">
              ORCA
            </div>
            <div>
              <h1 className="text-lg font-semibold text-gray-900">Marine Intelligence Chat</h1>
              <p className="text-xs text-gray-500">Powered by ARGO • 10 Indian Languages • Voice Enabled</p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <select
              value={selectedLanguage}
              onChange={(e) => handleLanguageChange(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              {languages.map(lang => (
                <option key={lang.code} value={lang.code}>
                  {lang.flag} {lang.name}
                </option>
              ))}
            </select>
            
            <button
              onClick={() => setIsMuted(!isMuted)}
              className={`p-2 rounded-lg transition-colors ${isMuted ? "bg-red-100 text-red-600" : "hover:bg-gray-100"}`}
              title={isMuted ? "Unmute TTS" : "Mute TTS"}
            >
              {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
            </button>
            
            <button
              onClick={handleVoiceToggle}
              disabled={displayLoading}
              className={`p-2 rounded-lg transition-colors ${isRecording ? "bg-red-600 text-white animate-pulse" : "bg-blue-600 text-white hover:bg-blue-700"}`}
              title={isRecording ? "Stop Recording" : "Start Voice Input"}
            >
              {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </header>
      
      {/* Messages */}
      <main className="flex-1 overflow-y-auto p-4 max-w-4xl mx-auto w-full">
        <div className="space-y-4" ref={messagesEndRef}>
          {displayMessages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {displayLoading && (
            <div className="flex justify-start">
              <div className="max-w-[80%] bg-gray-100 rounded-2xl p-4 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div className="h-4 bg-gray-200 rounded w-1/2"></div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </main>
      
      {/* Input */}
      <footer className="bg-white border-t border-gray-200 p-4">
        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={displayInput}
              onChange={(e) => setDisplayInput(e.target.value)}
              placeholder="Ask about ocean conditions, route safety, hazards, scenarios..."
              rows={1}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none text-sm"
              disabled={displayLoading}
            />
            <button
              type="submit"
              disabled={!displayInput.trim() || displayLoading}
              className={`px-6 py-3 rounded-xl font-medium transition-colors ${!displayInput.trim() || displayLoading ? "bg-gray-300 text-gray-500 cursor-not-allowed" : "bg-blue-600 text-white hover:bg-blue-700"}`}
            >
              Send
            </button>
          </div>
          <p className="text-xs text-gray-500 text-center mt-2">
            Supports: English, Hindi, Malayalam, Tamil, Telugu, Bengali, Gujarati, Marathi, Odia, Kannada
          </p>
        </form>
      </footer>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const langLabel = message.language ? message.language.replace("-IN", "").toUpperCase() : "";
  
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] ${isUser ? "bg-blue-600 text-white" : "bg-white text-gray-900 border border-gray-200"}`}>
        {!isUser && (
          <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100 bg-gray-50">
            <span className="w-6 h-6 bg-gradient-to-br from-blue-600 to-blue-800 rounded-full flex items-center justify-center text-white text-xs font-bold">
              ORCA
            </span>
            {message.language && (
              <span className="ml-2 text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">
                {message.language.replace("-IN", "").toUpperCase()}
              </span>
            )}
          </div>
        )}
        <div className={`p-4 ${isUser ? "" : "text-gray-900"}`}>
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
        {!isUser && message.evidence && message.evidence.length > 0 && (
          <div className="px-4 pb-4 pt-2 border-t border-gray-100">
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span className="px-2 py-0.5 bg-gray-100 rounded">📊 Evidence</span>
              {message.evidence.map((e: any, i: number) => (
                <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded">
                  {e.source}: {e.profiles} profiles
                </span>
              ))}
            </div>
          </div>
        )}
        {!isUser && message.riskAssessment && (
          <div className="px-4 pb-4 pt-2 border-t border-gray-100">
            <div className="flex items-center gap-2 text-xs">
              <span className={`px-2 py-0.5 rounded ${
                message.riskAssessment.classification?.toLowerCase() === "safe" ? "bg-green-100 text-green-700" :
                message.riskAssessment.classification?.toLowerCase() === "low" ? "bg-green-100 text-green-700" :
                message.riskAssessment.classification?.toLowerCase() === "moderate" ? "bg-yellow-100 text-yellow-700" :
                message.riskAssessment.classification?.toLowerCase() === "high" ? "bg-red-100 text-red-700" :
                "bg-gray-100 text-gray-700"
              }`}>
                ⚠️ Risk: {(message.riskAssessment.classification ?? "UNKNOWN").toUpperCase()}
              </span>
              <span className="text-gray-500">Score: {(message.riskAssessment.score * 100).toFixed(0)}%</span>
            </div>
          </div>
        )}
        {!isUser && message.limitations && message.limitations.length > 0 && (
          <div className="px-4 pb-4 pt-2 border-t border-gray-100">
            <div className="flex items-start gap-2 text-xs text-gray-500">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <div>
                {message.limitations.slice(0, 3).map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </div>
            </div>
          </div>
        )}
        <div className="px-4 pb-3 text-right">
          <span className={`text-xs ${isUser ? "text-blue-200" : "text-gray-400"}`}>
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
      </div>
    </div>
  );
}

export default ChatInterface;