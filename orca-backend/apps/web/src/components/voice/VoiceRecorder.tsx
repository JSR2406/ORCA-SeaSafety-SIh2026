'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Mic, MicOff, Loader2, X, Volume2, CheckCircle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface VoiceRecorderProps {
  onTranscript: (transcript: string) => void;
  disabled?: boolean;
  inline?: boolean;
  language?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function VoiceRecorder({ onTranscript, disabled = false, inline = false, language = 'ml-IN' }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  // Check MediaRecorder support
  useEffect(() => {
    const supported = !!navigator.mediaDevices?.getUserMedia && !!window.MediaRecorder;
    if (!supported) {
      console.warn('MediaRecorder not supported in this browser');
    }
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  const startRecording = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError('Audio recording not supported in this browser. Use Chrome/Edge/Firefox.');
      return;
    }

    try {
      setError(null);
      setTranscript('');
      setIsProcessing(false);

      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: { 
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      
      streamRef.current = stream;
      mediaRecorderRef.current = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      audioChunksRef.current = [];
      
      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorderRef.current.onstop = async () => {
        setIsProcessing(true);
        try {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          
          // Upload to backend for transcription
          const formData = new FormData();
          formData.append('audio', audioBlob, 'recording.webm');
          formData.append('language', language);
          
          const response = await fetch(`${API_URL}/api/v1/voice/transcribe`, {
            method: 'POST',
            body: formData,
          });
          
          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Transcription failed: ${response.status}`);
          }
          
          const data = await response.json();
          const result = data.transcript || data.text || '';
          
          if (result) {
            setTranscript(result);
            onTranscript(result);
          } else {
            setError('No speech detected. Please try again.');
          }
        } catch (err) {
          console.error('Transcription error:', err);
          setError(err instanceof Error ? err.message : 'Transcription failed');
        } finally {
          setIsProcessing(false);
        }
        
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorderRef.current.start(100); // Collect data every 100ms
      setIsRecording(true);
    } catch (err) {
      console.error('Recording error:', err);
      setError(err instanceof Error ? err.message : 'Failed to start recording');
    }
  }, [language, onTranscript]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
    }
    setIsRecording(false);
  }, []);

  const clearTranscript = useCallback(() => {
    setTranscript('');
    setError(null);
  }, []);

  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    return (
      <div className={cn('p-3 rounded-lg bg-rose-50 border border-rose-200', inline && 'w-full')}>
        <div className="flex items-center gap-2 text-rose-700 text-sm">
          <AlertCircle className="h-4 w-4" />
          <span>Voice input not supported in this browser. Use Chrome/Edge/Firefox for best experience.</span>
        </div>
      </div>
    );
  }

  if (inline) {
    return (
      <div className="flex items-center gap-2">
        <button
          onClick={isRecording || isProcessing ? stopRecording : startRecording}
          disabled={disabled || isProcessing}
          className={cn(
            'p-2 rounded-xl transition-colors',
            isRecording
              ? 'bg-rose-100 text-rose-600 animate-pulse'
              : isProcessing
              ? 'bg-amber-100 text-amber-600'
              : 'bg-muted text-muted-foreground hover:bg-muted/80',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
          aria-label={isRecording ? 'Stop recording' : isProcessing ? 'Processing...' : 'Start recording'}
          title={isRecording ? 'Stop recording' : isProcessing ? 'Processing audio...' : 'Start voice input'}
        >
          {isRecording ? (
            <MicOff className="h-5 w-5" />
          ) : isProcessing ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Mic className="h-5 w-5" />
          )}
        </button>
        {transcript && (
          <div className="flex-1 min-w-0">
            <p className="text-xs text-muted-foreground truncate">{transcript}</p>
            <button
              onClick={clearTranscript}
              className="text-xs text-primary hover:underline mt-1"
            >
              Clear
            </button>
          </div>
        )}
        {error && (
          <span className="text-xs text-rose-600">{error}</span>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-medium text-foreground">Voice Input</h4>
        <span className={cn('px-2 py-0.5 rounded text-xs font-medium', language === 'ml-IN' ? 'bg-purple-100 text-purple-700' : language === 'hi-IN' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700')}>
          {language === 'ml-IN' ? 'മലയാളം' : language === 'hi-IN' ? 'हिन्दी' : 'English'}
        </span>
      </div>

      <button
        onClick={isRecording || isProcessing ? stopRecording : startRecording}
        disabled={disabled || isProcessing}
        className={cn(
          'w-full flex items-center justify-center gap-3 px-4 py-4 rounded-xl border-2 transition-all',
          isRecording
            ? 'border-rose-300 bg-rose-50 text-rose-600 animate-pulse'
            : isProcessing
            ? 'border-amber-300 bg-amber-50 text-amber-600'
            : 'border-border bg-background text-foreground hover:border-primary/50',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
        aria-label={isRecording ? 'Stop recording' : isProcessing ? 'Processing...' : 'Start voice input'}
      >
        {isRecording ? (
          <>
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="font-medium">Recording... Click to stop</span>
            <span className="text-sm text-muted-foreground">Speak now</span>
          </>
        ) : isProcessing ? (
          <>
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="font-medium">Processing audio...</span>
            <span className="text-sm text-muted-foreground">Transcribing with Sarvam AI</span>
          </>
        ) : (
          <>
            <Mic className="h-6 w-6" />
            <span className="font-medium">Start Voice Input</span>
            <span className="text-sm text-muted-foreground">Click and speak</span>
          </>
        )}
      </button>

      {transcript && (
        <div className="mt-3 p-3 rounded-lg bg-muted/50 border border-border">
          <div className="flex items-start justify-between gap-2 mb-2">
            <p className="text-sm font-medium text-foreground">Transcript:</p>
            <button
              onClick={clearTranscript}
              className="p-1 rounded hover:bg-muted transition-colors"
              aria-label="Clear transcript"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <p className="text-sm text-foreground whitespace-pre-wrap">{transcript}</p>
          <button
            onClick={() => onTranscript(transcript)}
            className="mt-2 text-sm text-primary hover:underline flex items-center gap-1"
          >
            <CheckCircle className="h-4 w-4" />
            Use this transcript
          </button>
        </div>
      )}

      {error && (
        <div className="mt-3 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm">
          {error}
        </div>
      )}

      <p className="mt-3 text-xs text-muted-foreground text-center">
        Powered by Sarvam AI • Supports: Malayalam, Hindi, English, Tamil, Telugu, Kannada, Bengali, Marathi, Gujarati, Odia • Click microphone to start
      </p>
    </div>
  );
}