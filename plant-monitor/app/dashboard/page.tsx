import { mockPlants } from "@/lib/mock-data";
import PlantCard from "./plant-card";

export default function DashboardPage() {
  const healthyCount = mockPlants.filter(
    (p) => p.latest.moisture >= p.ideal_min && p.latest.moisture <= p.ideal_max
  ).length;
  const needsAttention = mockPlants.length - healthyCount;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">
          <span className="mr-2">{"\u{1F331}"}</span>
          moist
        </h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Soil humidity monitor &mdash; {mockPlants.length} plants tracked
        </p>
      </div>

      {/* Summary bar */}
      <div className="mb-6 flex gap-4">
        <div className="flex items-center gap-2 rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
          {healthyCount} healthy
        </div>
        {needsAttention > 0 && (
          <div className="flex items-center gap-2 rounded-lg bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
            <span className="inline-block h-2 w-2 rounded-full bg-amber-500" />
            {needsAttention} needs attention
          </div>
        )}
      </div>

      {/* Plant cards grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        {mockPlants.map((plant) => (
          <PlantCard key={plant.id} plant={plant} />
        ))}
      </div>

      {/* Footer note */}
      <p className="mt-8 text-center text-xs text-[var(--muted)]">
        Showing mock data &mdash; connect Supabase to see real sensor readings
      </p>
    </div>
  );
}
