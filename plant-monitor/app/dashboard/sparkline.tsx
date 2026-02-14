"use client";

import { Reading } from "@/lib/mock-data";

interface SparklineProps {
  readings: Reading[];
  width?: number;
  height?: number;
  color?: string;
}

export default function Sparkline({
  readings,
  width = 140,
  height = 36,
  color = "#22c55e",
}: SparklineProps) {
  if (readings.length < 2) return null;

  // Sample down to ~50 points for a clean sparkline
  const step = Math.max(1, Math.floor(readings.length / 50));
  const sampled = readings.filter((_, i) => i % step === 0);

  const moistures = sampled.map((r) => r.moisture);
  const min = Math.min(...moistures);
  const max = Math.max(...moistures);
  const range = max - min || 1;

  const padding = 2;
  const innerW = width - padding * 2;
  const innerH = height - padding * 2;

  const points = sampled
    .map((r, i) => {
      const x = padding + (i / (sampled.length - 1)) * innerW;
      const y = padding + innerH - ((r.moisture - min) / range) * innerH;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="block"
    >
      <polyline
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}
