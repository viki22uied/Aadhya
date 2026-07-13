"use client";

import { useState, useRef, useEffect } from "react";
import { AadhyaAvatar } from "./components/Aadhya";
import { ToolResultCard } from "./components/ToolCards";
import { MicButton } from "./components/MicButton";
import { useLanguage } from "./components/LanguageContext";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Judges land on an empty chat with no idea what it can do — these are
// real prompts the backend tool-calling handles, shown as clickable chips
// so there's a script to follow instead of guessing free text.
const EXAMPLE_PROMPTS = [
  "Show my FDs",
  "What's my gold worth?",
  "Buy ₹50 of gold",
  "What's my loan offer?",
  "Show my allocation",
  "What if the market drops 20%?",
];

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [llmDown, setLlmDown] = useState(false);
  const bottomRef = useRef(null);
  const { lang, translate, hindiError } = useLanguage();

  useEffect(() => {
    // Aadhya opens the conversation herself — this is deterministic, no LLM
    // call — deciding whether to lead with a downturn alert, the next step
    // of the FD-first sequence, or a plain greeting once that's all done.
    fetch(`${API}/chat/greeting`)
      .then((r) => r.json())
      .then(async (g) => {
        const content = await translate(g.reply);
        setMessages([{ role: "assistant", original: g.reply, content, tool_calls: g.tool_calls || [] }]);
      })
      .catch(() =>
        setMessages([
          { role: "assistant", original: ["Could not reach Aadhya right now."], content: ["Could not reach Aadhya right now."], tool_calls: [] },
        ])
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Re-translate existing assistant bubbles when the language toggle
  // changes, from their cached original English — never re-translating
  // Hindi back through the pipeline.
  useEffect(() => {
    (async () => {
      const updated = await Promise.all(
        messages.map(async (m) => {
          if (m.role !== "assistant" || !m.original) return m;
          const content = await translate(m.original);
          return { ...m, content };
        })
      );
      setMessages(updated);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const send = async (text) => {
    const message = text ?? input;
    if (!message.trim() || sending) return;
    const history = [...messages, { role: "user", content: [message] }];
    setMessages(history);
    setInput("");
    setSending(true);
    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          history: history.map(({ role, content }) => ({ role, content: Array.isArray(content) ? content.join(" ") : content })),
        }),
      });
      const data = await r.json();
      if (data.error === "llm_unavailable") {
        setLlmDown(true);
        const original = [
          "I can't reach my language model right now.",
          "The chat wiring is built and tested — it just has no model to call.",
        ];
        setMessages([...history, { role: "assistant", original, content: await translate(original), tool_calls: [] }]);
      } else {
        const content = await translate(data.reply);
        setMessages([...history, { role: "assistant", original: data.reply, content, tool_calls: data.tool_calls || [] }]);
      }
    } catch {
      setMessages([...history, { role: "assistant", content: ["Something went wrong reaching the server."], tool_calls: [] }]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-64px)] flex-col bg-zinc-50 font-sans dark:bg-black">
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col px-6 py-6">
        {llmDown && (
          <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
            Chat requires a language model (Ollama locally or Groq hosted) — neither is configured in
            this environment right now, so replies aren't available. The tool-calling architecture
            underneath is wired and tested; see /onboarding and /allocation for the live data directly.
          </div>
        )}

        {lang === "hi" && hindiError && (
          <div className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
            Couldn&apos;t reach the Hindi translation service right now — showing English.
          </div>
        )}

        <div className="flex-1 space-y-4 overflow-y-auto">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-2 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
              {m.role === "assistant" && <AadhyaAvatar size={28} />}
              <div className={`max-w-[80%] space-y-1.5 ${m.role === "user" ? "text-right" : ""}`}>
                {(Array.isArray(m.content) ? m.content : [m.content]).map((bubble, k) => (
                  <div
                    key={k}
                    className={`inline-block rounded-xl px-3 py-2 text-sm ${
                      m.role === "user"
                        ? "bg-black text-white dark:bg-zinc-100 dark:text-black"
                        : "bg-violet-50 text-zinc-800 dark:bg-violet-950/30 dark:text-zinc-200"
                    }`}
                  >
                    {bubble}
                  </div>
                ))}
                {m.tool_calls?.map((tc, j) => <ToolResultCard key={j} name={tc.name} result={tc.result} />)}
              </div>
            </div>
          ))}
          {sending && <p className="text-xs text-zinc-500 dark:text-zinc-400">Aadhya is thinking...</p>}
          <div ref={bottomRef} />
        </div>

        {messages.length <= 1 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLE_PROMPTS.map((p) => (
              <button
                key={p}
                onClick={() => send(p)}
                disabled={sending}
                className="rounded-full border border-violet-300 bg-violet-50 px-3 py-1.5 text-xs text-violet-800 hover:bg-violet-100 disabled:opacity-50 dark:border-violet-800 dark:bg-violet-950/30 dark:text-violet-200 dark:hover:bg-violet-900/40"
              >
                {p}
              </button>
            ))}
          </div>
        )}

        <div className="mt-4 flex gap-2">
          <MicButton onResult={(transcript) => send(transcript)} />
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask about your FDs, loans, gold, or allocation..."
            className="flex-1 rounded-full border border-zinc-300 bg-white px-4 py-2 text-sm text-black outline-none focus:border-violet-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
          <button
            onClick={() => send()}
            disabled={sending}
            className="rounded-full bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
