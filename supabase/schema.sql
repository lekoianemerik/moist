-- ============================================================
-- Moist: Supabase Schema
-- Run this entire file in the Supabase SQL Editor (one shot).
-- ============================================================

-- 1. Tables --------------------------------------------------

-- plants (append-only: latest row per plant_id = current config)
CREATE TABLE plants (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plant_id      INTEGER NOT NULL,
    plant_name    TEXT NOT NULL,
    plant_position TEXT,
    ideal_min     INTEGER NOT NULL DEFAULT 40,
    ideal_max     INTEGER NOT NULL DEFAULT 60,
    water_below   INTEGER NOT NULL DEFAULT 30,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- sensors (append-only: latest row per sensor_id = current config)
CREATE TABLE sensors (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sensor_id       INTEGER NOT NULL,
    plant_id        INTEGER NOT NULL,
    calibration_dry INTEGER NOT NULL,   -- raw ADC reading at 0% moisture (dry / air)
    calibration_wet INTEGER NOT NULL,   -- raw ADC reading at 100% moisture (water)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- readings (time-series, append-only)
CREATE TABLE readings (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sensor_id     INTEGER NOT NULL,
    moisture_raw  INTEGER NOT NULL,
    moisture_pct  REAL NOT NULL,        -- calibrated 0-100
    battery       REAL,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Indexes -------------------------------------------------

CREATE INDEX idx_plants_latest  ON plants  (plant_id, created_at DESC);
CREATE INDEX idx_sensors_latest ON sensors (sensor_id, created_at DESC);
CREATE INDEX idx_readings_sensor_time ON readings (sensor_id, recorded_at DESC);

-- 3. Views (current state) -----------------------------------

CREATE VIEW current_plants AS
SELECT DISTINCT ON (plant_id) *
FROM plants
ORDER BY plant_id, created_at DESC;

CREATE VIEW current_sensors AS
SELECT DISTINCT ON (sensor_id) *
FROM sensors
ORDER BY sensor_id, created_at DESC;

-- 4. Seed data -----------------------------------------------

INSERT INTO plants (plant_id, plant_name, plant_position, ideal_min, ideal_max, water_below) VALUES
    (1, 'Kitchen Basil',    'Kitchen windowsill', 40, 60, 30),
    (2, 'Bathroom Fern',    'Bathroom shelf',     60, 80, 50),
    (3, 'Desk Succulent',   'Office desk',        10, 25, 10),
    (4, 'Balcony Tomato',   'Balcony planter',    50, 70, 35);

INSERT INTO sensors (sensor_id, plant_id, calibration_dry, calibration_wet) VALUES
    (1, 1, 3200, 1400),
    (2, 2, 3100, 1350),
    (3, 3, 3250, 1450),
    (4, 4, 3150, 1380);

-- 5. Dummy readings (7 days, every 30 min, 4 sensors) --------
--
-- Each sensor starts at a different moisture level and dries out
-- gradually.  One simulated watering event mid-week bumps it back up.

INSERT INTO readings (sensor_id, moisture_raw, moisture_pct, battery, recorded_at)
SELECT
    s.sensor_id,

    -- raw ADC: interpolate between calibration endpoints
    (s.cal_dry - (pct / 100.0) * (s.cal_dry - s.cal_wet))::INTEGER,

    -- calibrated moisture %
    ROUND(pct::NUMERIC, 1)::REAL,

    -- battery: starts ~95 %, drains slowly
    ROUND(GREATEST(20, 95 - age_days * 0.7 + (random() - 0.5))::NUMERIC, 0)::REAL,

    t
FROM
    generate_series(
        now() - INTERVAL '7 days',
        now(),
        INTERVAL '30 minutes'
    ) AS t
CROSS JOIN (
    VALUES
        (1, 3200, 1400, 72.0, 8.0),
        (2, 3100, 1350, 80.0, 6.0),
        (3, 3250, 1450, 35.0, 3.0),
        (4, 3150, 1380, 65.0, 10.0)
) AS s(sensor_id, cal_dry, cal_wet, start_moisture, daily_drop)
CROSS JOIN LATERAL (
    SELECT EXTRACT(EPOCH FROM (now() - t)) / 86400.0 AS age_days
) AS a
CROSS JOIN LATERAL (
    SELECT GREATEST(5, LEAST(100,
        CASE
            -- After the watering event (day 3-4 mark), moisture jumps then resumes drying
            WHEN age_days < 3.5 THEN
                s.start_moisture - age_days * s.daily_drop + (random() - 0.5) * 3
            ELSE
                -- Watering event bumps moisture up by 30-40 %, then resumes drying
                LEAST(95, s.start_moisture + 35)
                - (age_days - 3.5) * s.daily_drop
                + (random() - 0.5) * 3
        END
    )) AS pct
) AS m;

-- 6. Row-level security --------------------------------------

ALTER TABLE plants   ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensors  ENABLE ROW LEVEL SECURITY;
ALTER TABLE readings ENABLE ROW LEVEL SECURITY;

-- Authenticated users (web dashboard) can read everything
CREATE POLICY "authenticated_read_plants"
    ON plants FOR SELECT TO authenticated USING (true);

CREATE POLICY "authenticated_read_sensors"
    ON sensors FOR SELECT TO authenticated USING (true);

CREATE POLICY "authenticated_read_readings"
    ON readings FOR SELECT TO authenticated USING (true);

-- Service role (Pi ingest) can insert into all tables
CREATE POLICY "service_insert_plants"
    ON plants FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "service_insert_sensors"
    ON sensors FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "service_insert_readings"
    ON readings FOR INSERT TO service_role WITH CHECK (true);
