"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { chat } from "@/lib/api";

interface Msg {
  role: "user" | "assistant";
  text: string;
}

export function Chat({
  carId,
  agent = "host",
  title = "Assistant",
  placeholder = "Message the assistant…",
  hint = "Ask a question to get started.",
}: {
  carId: string;
  agent?: "host" | "mater";
  title?: string;
  placeholder?: string;
  hint?: string;
}) {
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMsgs((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const { reply } = await chat(text, agent, carId);
      setMsgs((m) => [...m, { role: "assistant", text: reply }]);
    } catch {
      setMsgs((m) => [...m, { role: "assistant", text: "(agent unreachable)" }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col rounded-xl bg-panel p-4">
      <h2 className="mb-3 font-semibold">{title}</h2>

      <div className="flex-1 space-y-2 overflow-y-auto">
        {msgs.length === 0 && <p className="text-sm text-slate-500">{hint}</p>}
        {msgs.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
              m.role === "user"
                ? "ml-auto whitespace-pre-wrap bg-slate-700"
                : "bg-slate-800 text-slate-100"
            }`}
          >
            {m.role === "assistant" ? (
              <div className="markdown">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
              </div>
            ) : (
              m.text
            )}
          </div>
        ))}
        {busy && <div className="text-xs text-slate-500">thinking…</div>}
      </div>

      <div className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={placeholder}
          className="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-sm outline-none"
        />
        <button
          onClick={send}
          disabled={busy}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-ink disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
