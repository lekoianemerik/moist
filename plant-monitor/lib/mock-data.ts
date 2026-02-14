// Mock data for development -- matches the Supabase schema from project-overview.md
// This will be replaced with real Supabase queries once the database is wired up.

export interface Plant {
  id: string;
  name: string;
  location: string;
  plant_type: string;
  ideal_min: number;
  ideal_max: number;
  water_below: number;
  avg_daily_drop: number;
}

export interface Reading {
  moisture: number;
  battery: number;
  raw_value: number;
  recorded_at: string;
}

export interface PlantWithReadings extends Plant {
  latest: Reading;
  history: Reading[];
}

// Generate fake 7-day history for a plant.
// Starts at `startMoisture` and trends downward with noise, occasional watering spikes.
function generateHistory(
  startMoisture: number,
  days: number = 7,
  readingsPerDay: number = 48 // one every 30 min
): Reading[] {
  const history: Reading[] = [];
  const totalReadings = days * readingsPerDay;
  const now = Date.now();
  let moisture = startMoisture;
  let battery = 95;

  for (let i = totalReadings; i >= 0; i--) {
    const timestamp = now - i * 30 * 60 * 1000; // 30 min intervals

    // Gradual drying with noise
    moisture -= Math.random() * 0.6 + 0.05;
    moisture += (Math.random() - 0.5) * 0.3;

    // Simulate watering events roughly every 2-3 days
    if (i > 0 && i % (readingsPerDay * 2.5) < 1 && moisture < 50) {
      moisture += 30 + Math.random() * 15;
    }

    moisture = Math.max(5, Math.min(100, moisture));
    battery = Math.max(0, battery - Math.random() * 0.02);

    history.push({
      moisture: Math.round(moisture * 10) / 10,
      battery: Math.round(battery),
      raw_value: Math.round(3200 - (moisture / 100) * 1800),
      recorded_at: new Date(timestamp).toISOString(),
    });
  }

  return history;
}

const basilHistory = generateHistory(72);
const fernHistory = generateHistory(80);
const succulentHistory = generateHistory(35);
const tomatoHistory = generateHistory(65);

export const mockPlants: PlantWithReadings[] = [
  {
    id: "sensor-01",
    name: "Kitchen Basil",
    location: "Kitchen windowsill",
    plant_type: "basil",
    ideal_min: 40,
    ideal_max: 60,
    water_below: 30,
    avg_daily_drop: 8.0,
    latest: basilHistory[basilHistory.length - 1],
    history: basilHistory,
  },
  {
    id: "sensor-02",
    name: "Bathroom Fern",
    location: "Bathroom shelf",
    plant_type: "fern",
    ideal_min: 60,
    ideal_max: 80,
    water_below: 50,
    avg_daily_drop: 6.0,
    latest: fernHistory[fernHistory.length - 1],
    history: fernHistory,
  },
  {
    id: "sensor-03",
    name: "Desk Succulent",
    location: "Office desk",
    plant_type: "succulent",
    ideal_min: 10,
    ideal_max: 25,
    water_below: 10,
    avg_daily_drop: 3.0,
    latest: succulentHistory[succulentHistory.length - 1],
    history: succulentHistory,
  },
  {
    id: "sensor-04",
    name: "Balcony Tomato",
    location: "Balcony planter",
    plant_type: "tomato",
    ideal_min: 50,
    ideal_max: 70,
    water_below: 35,
    avg_daily_drop: 10.0,
    latest: tomatoHistory[tomatoHistory.length - 1],
    history: tomatoHistory,
  },
];
