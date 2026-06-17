"use client";

import { Chat } from "@/components/Chat";

const CAR_ID = "acc001";

export default function HostPage() {
  return (
    <main className="mx-auto flex h-[calc(100vh-3.5rem)] max-w-3xl flex-col p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">
          Host <span className="text-slate-500">· owner assistant</span>
        </h1>
        <p className="text-sm text-slate-400">
          Trips, vehicle health, maintenance and fleet questions.
        </p>
      </header>

      <div className="min-h-0 flex-1">
        <Chat
          carId={CAR_ID}
          agent="host"
          title="Host"
          placeholder="Ask about your vehicle…"
          hint="Ask “How was my last drive?” or “When is my next service due?”"
        />
      </div>
    </main>
  );
}
