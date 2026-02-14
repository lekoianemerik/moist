"use client";

import { PlantWithReadings } from "@/lib/mock-data";
import Sparkline from "./sparkline";

// Plant type to emoji mapping
const plantEmoji: Record<string, string> = {
  basil: "\u{1F33F}",
  fern: "\u{1F331}",
  succulent: "\u{1FAB4}",
  tomato: "\u{1F345}",
};

function getStatus(
  moisture: number,
  waterBelow: number,
  idealMin: number,
  idealMax: number
): { label: string; color: string; bgColor: string } {
  if (moisture <= waterBelow) {
    return {
      label: "Dry!",
      color: "text-red-600 dark:text-red-400",
      bgColor: "bg-red-100 dark:bg-red-950",
    };
  }
  if (moisture < idealMin) {
    return {
      label: "Needs Water",
      color: "text-amber-600 dark:text-amber-400",
      bgColor: "bg-amber-100 dark:bg-amber-950",
    };
  }
  if (moisture > idealMax) {
    return {
      label: "Overwatered",
      color: "text-blue-600 dark:text-blue-400",
      bgColor: "bg-blue-100 dark:bg-blue-950",
    };
  }
  return {
    label: "Healthy",
    color: "text-emerald-600 dark:text-emerald-400",
    bgColor: "bg-emerald-100 dark:bg-emerald-950",
  };
}

function getMoistureBarColor(moisture: number, waterBelow: number, idealMin: number): string {
  if (moisture <= waterBelow) return "bg-red-500";
  if (moisture < idealMin) return "bg-amber-500";
  return "bg-emerald-500";
}

function getBatteryIcon(battery: number): string {
  if (battery > 60) return "\u{1F50B}";
  if (battery > 20) return "\u{1FAAB}";
  return "\u26A0\uFE0F";
}

function getSparklineColor(moisture: number, waterBelow: number, idealMin: number): string {
  if (moisture <= waterBelow) return "#ef4444";
  if (moisture < idealMin) return "#f59e0b";
  return "#22c55e";
}

export default function PlantCard({ plant }: { plant: PlantWithReadings }) {
  const { latest } = plant;
  const status = getStatus(latest.moisture, plant.water_below, plant.ideal_min, plant.ideal_max);
  const barColor = getMoistureBarColor(latest.moisture, plant.water_below, plant.ideal_min);
  const sparkColor = getSparklineColor(latest.moisture, plant.water_below, plant.ideal_min);
  const emoji = plantEmoji[plant.plant_type] || "\u{1F33F}";

  // Calculate time since last reading
  const lastReadingTime = new Date(latest.recorded_at);
  const minutesAgo = Math.round((Date.now() - lastReadingTime.getTime()) / 60000);
  const timeAgo =
    minutesAgo < 1
      ? "just now"
      : minutesAgo < 60
        ? `${minutesAgo}m ago`
        : `${Math.round(minutesAgo / 60)}h ago`;

  return (
    <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card-bg)] p-5 shadow-sm transition-shadow hover:shadow-md">
      {/* Header */}
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{emoji}</span>
          <div>
            <h3 className="font-semibold leading-tight">{plant.name}</h3>
            <p className="text-xs text-[var(--muted)]">{plant.location}</p>
          </div>
        </div>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${status.color} ${status.bgColor}`}
        >
          {status.label}
        </span>
      </div>

      {/* Moisture */}
      <div className="mb-3">
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-sm text-[var(--muted)]">Moisture</span>
          <span className="text-xl font-bold tabular-nums">
            {latest.moisture.toFixed(1)}%
          </span>
        </div>
        {/* Bar */}
        <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-800">
          <div
            className={`h-full rounded-full transition-all ${barColor}`}
            style={{ width: `${Math.min(100, latest.moisture)}%` }}
          />
        </div>
        {/* Ideal range markers */}
        <div className="mt-0.5 flex justify-between text-[10px] text-[var(--muted)]">
          <span>0%</span>
          <span>
            Ideal: {plant.ideal_min}–{plant.ideal_max}%
          </span>
          <span>100%</span>
        </div>
      </div>

      {/* Sparkline */}
      <div className="mb-3">
        <p className="mb-1 text-xs text-[var(--muted)]">7-day trend</p>
        <Sparkline readings={plant.history} color={sparkColor} />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-[var(--muted)]">
        <span>
          {getBatteryIcon(latest.battery)} {latest.battery}%
        </span>
        <span>Updated {timeAgo}</span>
      </div>
    </div>
  );
}
