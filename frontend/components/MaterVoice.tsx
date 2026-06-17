"use client";

import { useEffect, useRef, useState } from "react";
import { chat } from "@/lib/api";

// --- Minimal Web Speech API typings (not in the standard DOM lib) -----------
interface SpeechRecognitionResultLike {
  0: { transcript: string };
  isFinal: boolean;
}
interface SpeechRecognitionEventLike {
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}
type RecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

// --- Voice character -------------------------------------------------------
// Ordered, case-insensitive name matches; first available wins. Edit these to
// change how Mater sounds. Falls back to any English voice, then the browser
// default. (Available voices are OS/browser-specific.)
const PREFERRED_VOICES = [
  "Microsoft Guy",             // Edge/Windows
  "Daniel",                    // macOS (en-GB male)
  "Google UK English Male",    // Chrome
  "Samantha",                  // macOS (en-US)
  "Google US English",         // Chrome
];
const SPEECH_RATE = 1.0;
const SPEECH_PITCH = 1.0;

function selectVoice(): SpeechSynthesisVoice | null {
  if (typeof window === "undefined" || !window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  if (voices.length === 0) return null;
  for (const pref of PREFERRED_VOICES) {
    const hit = voices.find((v) => v.name.toLowerCase().includes(pref.toLowerCase()));
    if (hit) return hit;
  }
  return voices.find((v) => v.lang.toLowerCase().startsWith("en")) ?? null;
}

type Status = "idle" | "listening" | "thinking" | "speaking";

export function MaterVoice({ carId }: { carId: string }) {
  const [supported, setSupported] = useState(true);
  const [status, setStatus] = useState<Status>("idle");
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => {
    // Capability check after mount keeps SSR and first client render in sync.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!getRecognitionCtor()) setSupported(false);
    // Prime the voice list (loads async on first access in some browsers) so the
    // first spoken reply already uses the preferred voice.
    window.speechSynthesis?.getVoices();
    return () => {
      recognitionRef.current?.stop();
      if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    };
  }, []);

  function speak(text: string) {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    const voice = selectVoice();
    if (voice) u.voice = voice;
    u.rate = SPEECH_RATE;
    u.pitch = SPEECH_PITCH;
    u.onend = () => setStatus("idle");
    setStatus("speaking");
    window.speechSynthesis.speak(u);
  }

  async function ask(text: string) {
    const q = text.trim();
    if (!q) return;
    setStatus("thinking");
    try {
      const { reply } = await chat(q, "mater", carId);
      setReply(reply);
      speak(reply);
    } catch {
      const msg = "Sorry, I couldn't reach the car right now.";
      setReply(msg);
      speak(msg);
    }
  }

  // Created lazily on first use so we never touch the Web Speech API on the server.
  function ensureRecognition(): SpeechRecognitionLike | null {
    if (recognitionRef.current) return recognitionRef.current;
    const Ctor = getRecognitionCtor();
    if (!Ctor) return null;
    const rec = new Ctor();
    rec.lang = "en-US";
    rec.continuous = false;
    rec.interimResults = true;
    rec.onresult = (e) => {
      const text = Array.from(e.results)
        .map((r) => r[0].transcript)
        .join("");
      setTranscript(text);
      const last = e.results[e.results.length - 1];
      if (last?.isFinal) void ask(text);
    };
    rec.onerror = () => setStatus("idle");
    rec.onend = () => setStatus((s) => (s === "listening" ? "idle" : s));
    recognitionRef.current = rec;
    return rec;
  }

  function toggleListen() {
    if (status === "listening") {
      recognitionRef.current?.stop();
      setStatus("idle");
      return;
    }
    const rec = ensureRecognition();
    if (!rec) {
      setSupported(false);
      return;
    }
    window.speechSynthesis?.cancel();
    setTranscript("");
    setReply("");
    setStatus("listening");
    rec.start();
  }

  const label = {
    idle: "Tap to talk to Mater",
    listening: "Listening…",
    thinking: "Thinking…",
    speaking: "Speaking…",
  }[status];

  return (
    <div className="flex h-full flex-col items-center justify-center gap-5 rounded-xl bg-panel p-6">
      <button
        onClick={toggleListen}
        disabled={!supported || status === "thinking"}
        aria-label="Talk to Mater"
        className={`flex h-28 w-28 items-center justify-center rounded-full text-4xl transition disabled:opacity-50 ${
          status === "listening"
            ? "animate-pulse bg-accent text-ink"
            : "bg-slate-700 hover:bg-slate-600"
        }`}
      >
        🎙️
      </button>

      <p className="text-sm font-medium text-slate-300">
        {supported ? label : "Voice not supported in this browser"}
      </p>

      {transcript && (
        <p className="max-w-md text-center text-sm text-slate-400">
          “{transcript}”
        </p>
      )}
      {reply && (
        <p className="max-w-md text-center text-sm text-slate-100">{reply}</p>
      )}
    </div>
  );
}
