"use client";

import { useEffect, useRef, useState } from "react";

// A4 (vernacular + voice-first advisory) — full AI4Bharat speech-to-text
// (Hindi + other Indian languages) isn't wired in yet (deferred, same as the
// gold vendor and IDBI rate card elsewhere in this app). As a real, working
// stopgap rather than a dead placeholder, this uses the browser's built-in
// Web Speech API (SpeechRecognition) for English-only voice input. Chrome
// desktop supports it out of the box; if the browser doesn't, the button
// shows a clear "not supported here" state instead of silently failing.
export function MicButton({ onResult }) {
  const [supported, setSupported] = useState(true);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef(null);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSupported(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = (event) => {
      onResult(event.results[0][0].transcript);
      setListening(false);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!supported) {
    return (
      <button
        disabled
        title="Voice input — coming with Hindi support. Not available in this browser yet."
        className="rounded-full border border-zinc-300 px-3 py-2 text-sm text-zinc-400 dark:border-zinc-700"
      >
        🎤
      </button>
    );
  }

  const toggle = () => {
    if (listening) {
      recognitionRef.current.stop();
      setListening(false);
    } else {
      recognitionRef.current.start();
      setListening(true);
    }
  };

  return (
    <button
      onClick={toggle}
      title="Voice input (English only for now — Hindi support coming)"
      className={`rounded-full border px-3 py-2 text-sm ${
        listening
          ? "border-rose-400 bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-300"
          : "border-zinc-300 text-black hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-50 dark:hover:bg-zinc-800"
      }`}
    >
      {listening ? "🎤 listening..." : "🎤"}
    </button>
  );
}
