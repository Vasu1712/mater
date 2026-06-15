"use client";

export function Gauge({
  label,
  value,
  unit,
  min = 0,
  max = 100,
}: {
  label: string;
  value: number | undefined;
  unit: string | null;
  min?: number;
  max?: number;
}) {
  const v = value ?? 0;
  const pct = Math.max(0, Math.min(1, (v - min) / (max - min)));
  const hue = 140 - pct * 140; // green -> red
  return (
    <div className="rounded-xl bg-panel p-4 shadow">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-3xl font-semibold tabular-nums">
        {value === undefined ? "—" : v.toFixed(0)}
        <span className="ml-1 text-sm text-slate-400">{unit}</span>
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-700">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct * 100}%`, background: `hsl(${hue} 70% 50%)` }}
        />
      </div>
    </div>
  );
}
