"use client";

import { useEffect, useState } from "react";
import { Gauge } from "@/components/Gauge";
import { Chat } from "@/components/Chat";
import { getSnapshot, getAlerts, type Snapshot, type Alert } from "@/lib/api";

const CAR_ID = "acc001";

// label, signal_name, max
const GAUGES: [string, string, number][] = [
  ["Engine RPM", "engine_speed", 8000],
  ["Speed", "vehicle_speed", 240],
  ["Coolant", "coolant_temp", 130],
  ["Throttle", "throttle_position", 100],
  ["Fuel", "fuel_level", 100],
  ["MAF", "maf", 60],
];

export default function Page() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const [s, a] = await Promise.all([getSnapshot(CAR_ID), getAlerts(CAR_ID)]);
        if (active) {
          setSnap(s);
          setAlerts(a);
        }
      } catch {
        /* ingestion/agent not up yet */
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const sig = (name: string) => snap?.signals?.[name]?.v;
  const unit = (name: string) => snap?.signals?.[name]?.u ?? "";

  return (
    <main className="mx-auto max-w-6xl p-6">
      <header className="mb-6 flex items-baseline justify-between">
        <h1 className="text-2xl font-bold">
          Mater <span className="text-slate-500">· {CAR_ID}</span>
        </h1>
        <span className="text-sm text-slate-400">
          {snap?.timestamp
            ? `updated ${new Date(snap.timestamp).toLocaleTimeString()}`
            : "waiting for telemetry…"}
        </span>
      </header>

      {alerts.length > 0 && (
        <div className="mb-4 space-y-2">
          {alerts.map((a) => (
            <div
              key={a.code}
              className={`rounded-lg px-4 py-2 text-sm ${
                a.severity === "critical" ? "bg-crit/20 text-crit" : "bg-warn/20 text-warn"
              }`}
            >
              <strong className="uppercase">{a.severity}</strong> — {a.message}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section className="grid grid-cols-2 gap-4 lg:col-span-2 sm:grid-cols-3">
          {GAUGES.map(([label, name, max]) => (
            <Gauge key={name} label={label} value={sig(name)} unit={unit(name)} max={max} />
          ))}
        </section>

        <section className="h-[28rem] lg:col-span-1">
          <Chat carId={CAR_ID} />
        </section>
      </div>
    </main>
  );
}
