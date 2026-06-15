"use client";

import { useState } from "react";
import { chat } from "@/lib/api";

interface Msg {
  role: "user" | "assistant";
  text: string;
}

export function Chat({ carId }: { carId: string }) {
  const [agent, setAgent] = useState<"host" | "mater">("host");
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
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Assistant</h2>
        <div className="flex gap-1 text-xs">
          {(["host", "mater"] as const).map((a) => (
            <button
              key={a}
              onClick={() => setAgent(a)}
              className={`rounded px-2 py-1 capitalize ${
                agent === a ? "bg-accent text-ink" : "bg-slate-700"
              }`}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto">
        {msgs.length === 0 && (
          <p className="text-sm text-slate-500">
            Ask “How was my last drive?” or “What does P0420 mean?”
          </p>
        )}
        {msgs.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
              m.role === "user"
                ? "ml-auto bg-slate-700"
                : "bg-slate-800 text-slate-100"
            }`}
          >
            {m.text}
          </div>
        ))}
        {busy && <div className="text-xs text-slate-500">thinking…</div>}
      </div>

      <div className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Message Mater…"
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
