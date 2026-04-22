// VoiceTestTab — real-time WebSocket voice/text session tester
import { useEffect, useRef, useState, useCallback } from 'react';
import { Mic, MicOff, Send, RotateCcw, Phone, PhoneOff, Globe } from 'lucide-react';
import type { TranscriptEntry, WsMessage } from '../types';
import { format } from 'date-fns';

interface Props {
  onToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

const WS_BASE = 'ws://localhost:8000';

const LANG_FLAGS: Record<string, string> = { en: '🇬🇧', hi: '🇮🇳', ta: '🇮🇳' };
const LANG_NAMES: Record<string, string> = { en: 'English', hi: 'Hindi', ta: 'Tamil' };

export default function VoiceTestTab({ onToast }: Props) {
  const [phone, setPhone] = useState('+919876543210');
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [language, setLanguage] = useState('en');
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [textInput, setTextInput] = useState('');
  const [sending, setSending] = useState(false);
  const [processing, setProcessing] = useState(false);

  // Audio recording
  const [recording, setRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingStartedAtRef = useRef<number>(0);
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const addMsg = useCallback((role: TranscriptEntry['role'], content: string, lang?: string) => {
    setTranscript(prev => [...prev, {
      role,
      content,
      language: lang,
      timestamp: new Date().toISOString(),
    }]);
  }, []);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript]);

    // Audio playback via Web Audio API
  const audioCtxRef = useRef<AudioContext | null>(null);

  function getAudioCtx(): AudioContext {
    if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
      audioCtxRef.current = new AudioContext();
    }
    // Resume if suspended (browser autoplay policy)
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }
    return audioCtxRef.current;
  }

  async function playAudioBlob(blob: Blob) {
    try {
      const ctx = getAudioCtx();
      const arrayBuffer = await blob.arrayBuffer();
      const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);
      source.start(0);
    } catch (err) {
      console.warn('Audio playback error:', err);
    }
  }

  function connect() {
    const cleanPhone = phone.trim().replace(/\s+/g, '');
    if (!cleanPhone) { onToast('Enter a patient phone number', 'error'); return; }
    setPhone(cleanPhone);
    setConnecting(true);
    const ws = new WebSocket(`${WS_BASE}/ws/voice/${encodeURIComponent(cleanPhone)}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnecting(false);
      setConnected(true);
      onToast('WebSocket connected', 'success');
    };

    ws.onmessage = async (ev) => {
      // ── Binary message = TTS audio bytes → play immediately ──────────
      if (ev.data instanceof Blob) {
        await playAudioBlob(ev.data);
        return;
      }

      // ── JSON messages ─────────────────────────────────────────────────
      try {
        const msg: WsMessage = JSON.parse(ev.data as string);

        if (msg.type === 'session_start') {
          setSessionId(msg.session_id ?? '');
          if (msg.language) setLanguage(msg.language);
          addMsg('system', `Session started: ${msg.session_id}`);
          if (msg.message) addMsg('system', msg.message);

        } else if (msg.type === 'turn_complete') {
          setProcessing(false);
          // Voice turn completed: show STT transcript + agent reply
          if (msg.language) setLanguage(msg.language);
          if (msg.user_text) addMsg('user', `🎤 ${msg.user_text}`, msg.language);
          if (msg.text) {
            addMsg('assistant', msg.text, msg.language);
          } else {
            addMsg('system', 'No speech detected in that audio. Please try again.');
            onToast('No speech detected. Speak closer to the mic and retry.', 'info');
          }

        } else if (msg.type === 'response') {
          setProcessing(false);
          // Text turn response
          if (msg.language) setLanguage(msg.language);
          addMsg('assistant', msg.text ?? '', msg.language);

        } else if (msg.type === 'error') {
          setProcessing(false);
          addMsg('system', `⚠️ Error: ${msg.message}`);
          onToast(msg.message ?? 'Unknown error', 'error');

        } else if (msg.type === 'pong') {
          // ping-pong alive — no-op
        }
      } catch {
        // Ignore unparseable non-binary messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      setConnecting(false);
      setSessionId('');
      setProcessing(false);
      addMsg('system', 'Session disconnected');
      onToast('WebSocket disconnected', 'info');
    };

    ws.onerror = () => {
      setConnected(false);
      setConnecting(false);
      setProcessing(false);
      onToast('WebSocket connection failed. Is the backend running?', 'error');
    };
  }

  function disconnect() {
    wsRef.current?.close();
    stopRecording();
  }

  async function sendText() {
    if (!textInput.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setSending(true);
    setProcessing(true);
    addMsg('user', textInput.trim());
    wsRef.current.send(textInput.trim());
    setTextInput('');
    setSending(false);
  }

  async function toggleRecord() {
    if (recording) {
      stopRecording();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });

      let mimeType = '';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/webm')) {
        mimeType = 'audio/webm';
      } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
        mimeType = 'audio/ogg;codecs=opus';
      }

      const mr = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      recordingStartedAtRef.current = Date.now();

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'audio_start' }));
      }

      mr.ondataavailable = e => {
        if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          e.data.arrayBuffer().then(buf => wsRef.current?.send(buf));
        }
      };
      mr.onstop = () => {
        const elapsedMs = Date.now() - recordingStartedAtRef.current;
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'audio_end' }));
          if (elapsedMs < 700) {
            onToast('Recording too short. Hold mic for at least 1 second and speak clearly.', 'info');
            setProcessing(false);
          } else {
            setProcessing(true);
          }
        }
        stream.getTracks().forEach(t => t.stop());
      };

      mr.start(250);
      setRecording(true);
    } catch {
      onToast('Microphone access denied', 'error');
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  function clearTranscript() {
    setTranscript([]);
  }

  useEffect(() => {
    return () => { wsRef.current?.close(); };
  }, []);

  const roleLabel: Record<TranscriptEntry['role'], string> = {
    user: 'You',
    assistant: 'Agent',
    system: 'System',
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Voice Test Console</div>
          <div className="page-subtitle">Test real-time voice &amp; text sessions via WebSocket</div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {connected && sessionId && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              <code className="mono">{sessionId.slice(0, 12)}…</code>
            </div>
          )}
          {connected && (
            <span className="badge badge-accent">
              {LANG_FLAGS[language]} {LANG_NAMES[language] ?? language}
            </span>
          )}
        </div>
      </div>

      <div className="voice-panel">
        {/* Connection controls */}
        <div className="card">
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: 1, minWidth: '220px' }}>
              <Globe size={15} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                id="ws-phone"
                className="input"
                placeholder="Patient phone (e.g. +919876543210)"
                value={phone}
                onChange={e => setPhone(e.target.value)}
                disabled={connected}
                style={{ paddingLeft: '2.25rem' }}
              />
            </div>
            {!connected ? (
              <button
                id="ws-connect"
                className="btn btn-primary"
                onClick={connect}
                disabled={connecting}
              >
                {connecting
                  ? <><div className="spinner" style={{ width: 16, height: 16 }} /> Connecting…</>
                  : <><Phone size={15} /> Connect</>}
              </button>
            ) : (
              <button
                id="ws-disconnect"
                className="btn btn-danger"
                onClick={disconnect}
              >
                <PhoneOff size={15} /> Disconnect
              </button>
            )}
            <button className="btn btn-ghost btn-sm" onClick={clearTranscript} title="Clear transcript">
              <RotateCcw size={14} />
            </button>
          </div>

          {!connected && (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
              Connect to start a real-time session. You can send text messages or record audio directly from the browser.
            </p>
          )}
        </div>

        {/* Transcript */}
        <div className="transcript-box" ref={scrollRef}>
          {transcript.length === 0 ? (
            <div className="empty-state" style={{ flex: 1, padding: '2rem' }}>
              <Mic size={36} />
              <p>Connect to start a session</p>
              <p style={{ fontSize: '0.8rem' }}>Messages will appear here in real time</p>
            </div>
          ) : (
            transcript.map((msg, i) => (
              <div key={i} className={`transcript-msg ${msg.role}`}>
                <div className="msg-meta">
                  <strong>{roleLabel[msg.role]}</strong>
                  {' · '}
                  {format(new Date(msg.timestamp), 'HH:mm:ss')}
                  {msg.language && ` · ${LANG_FLAGS[msg.language] ?? ''} ${msg.language}`}
                </div>
                <div className="msg-bubble">{msg.content}</div>
              </div>
            ))
          )}
          {processing && (
            <div className="transcript-msg system">
              <div className="msg-meta">
                <strong>System</strong>
                {' · '}
                {format(new Date(), 'HH:mm:ss')}
              </div>
              <div className="msg-bubble" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--text-muted)', animation: 'pulse-dot 1s infinite' }} />
                Processing your request...
              </div>
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="card">
          <div className="voice-controls">
            <button
              id="mic-btn"
              className={`mic-btn ${recording ? 'recording' : ''}`}
              onClick={toggleRecord}
              disabled={!connected}
              title={recording ? 'Stop recording' : 'Start recording'}
            >
              {recording ? <MicOff size={20} /> : <Mic size={20} />}
            </button>
            <div className="text-input-row">
              <input
                id="text-message-input"
                className="input"
                placeholder={connected ? 'Type a message and press Enter…' : 'Connect first to send messages'}
                value={textInput}
                disabled={!connected}
                onChange={e => setTextInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(); } }}
              />
              <button
                id="send-text-btn"
                className="btn btn-primary"
                onClick={sendText}
                disabled={!connected || !textInput.trim() || sending}
              >
                <Send size={15} />
              </button>
            </div>
          </div>
          {recording && (
            <div style={{ marginTop: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--rose)', fontSize: '0.8rem' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--rose)', animation: 'pulse-dot 1s infinite' }} />
              Recording… click the microphone button to stop and send
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
