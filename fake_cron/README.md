# fake_cron — Fake sensor readings for moist

Runs on a Raspberry Pi (or any machine) via cron. Every 30 minutes it discovers active sensors from Supabase and inserts one fake reading per sensor, simulating gradual soil drying, battery drain, and occasional watering events. Sensors added or removed via the web dashboard are automatically picked up on the next run.

## Setup on the Raspberry Pi

### 1. Clone the repo and install dependencies

```bash
cd ~
git clone <your-repo-url> moist
cd moist/fake_cron

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env
# Fill in your SUPABASE_URL and SUPABASE_SECRET_KEY
```

### 3. Test it manually

```bash
source .venv/bin/activate
python send_reading.py
```

You should see output like:

```
Inserted 4 readings:
  sensor 1: moisture=54.3%  battery=87.0%  raw=2223
  sensor 2: moisture=64.5%  battery=63.0%  raw=1972
  sensor 3: moisture=19.6%  battery=94.0%  raw=2897
  sensor 4: moisture=47.2%  battery=41.0%  raw=2314
```

### 4. Set up the cron job

```bash
crontab -e
```

Add this line (runs every 30 minutes):

```
*/30 * * * * cd /home/pi/moist/fake_cron && /home/pi/moist/fake_cron/.venv/bin/python /home/pi/moist/fake_cron/send_reading.py >> /home/pi/moist/fake_cron/cron.log 2>&1
```

> Adjust `/home/pi/moist` if you cloned the repo elsewhere.

### 5. Verify it's working

Wait 30 minutes, then check the log:

```bash
tail -20 ~/moist/fake_cron/cron.log
```

Or check Supabase Table Editor — you should see new rows in the `readings` table.

## How it works

- **Dynamic sensor discovery:** On each run, queries the `current_sensors` view from Supabase to get active sensors. New sensors are automatically initialized; removed sensors are pruned from state.
- **State file (`state.json`):** Persists current moisture and battery levels between cron runs so values drift realistically over time. Auto-created on first run. Delete it to reset to defaults.
- **Drying simulation:** Each tick, moisture drops 0.2–0.8 % with ±0.3 % noise.
- **Watering events:** ~3 % chance per tick (roughly once every 17 hours), moisture jumps up by 30–45 %.
- **Battery drain:** ~0.01 %/tick (≈ 0.5 %/day), bottoms out at 5 %.
- **Raw ADC:** Computed from moisture % using each sensor's calibration values fetched from Supabase.

## Files

```
fake_cron/
├── send_reading.py   # Main script — generate + insert fake readings
├── requirements.txt  # Python dependencies
├── .env.example      # Template for Supabase credentials
├── .env              # Your actual credentials (git-ignored)
├── state.json        # Auto-generated sensor state (git-ignored)
├── cron.log          # Cron output log (git-ignored)
└── README.md         # You are here
```
