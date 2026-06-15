-- =============================================================================
-- Mater :: TimescaleDB Cold-Path Schema
-- Runs automatically on first container start (mounted into
-- /docker-entrypoint-initdb.d). Idempotent where practical.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- -----------------------------------------------------------------------------
-- Supplementary relational tables
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name    TEXT,
    email   TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS cars (
    car_id   TEXT PRIMARY KEY,
    owner_id UUID REFERENCES users(user_id),
    make     TEXT,
    model    TEXT,
    year     INT,
    vin      TEXT
);

CREATE TABLE IF NOT EXISTS trips (
    trip_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    car_id     TEXT REFERENCES cars(car_id),
    started_at TIMESTAMPTZ,
    ended_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS signal_registry (
    signal_name      VARCHAR(64) PRIMARY KEY,
    pid              VARCHAR(4),
    display_name     TEXT,
    unit             VARCHAR(16),
    min              DOUBLE PRECISION,
    max              DOUBLE PRECISION,
    vss_path         TEXT,
    supported_models TEXT[]
);

-- -----------------------------------------------------------------------------
-- Raw telemetry hypertable
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS car_telemetry (
    time        TIMESTAMPTZ      NOT NULL,
    car_id      TEXT             NOT NULL,
    signal_name VARCHAR(64)      NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    unit        VARCHAR(16),
    pid         VARCHAR(4),
    trip_id     UUID,
    quality     VARCHAR(16) DEFAULT 'normal'
);

SELECT create_hypertable(
    'car_telemetry',
    'time',
    chunk_time_interval => INTERVAL '1 day',
    partitioning_column => 'car_id',
    number_partitions   => 16,
    if_not_exists       => TRUE
);

CREATE INDEX IF NOT EXISTS idx_car_signal_time
    ON car_telemetry (car_id, signal_name, time DESC);

CREATE INDEX IF NOT EXISTS idx_trip
    ON car_telemetry (car_id, trip_id, time);

-- -----------------------------------------------------------------------------
-- Continuous aggregates
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    car_id,
    signal_name,
    avg(value)  AS avg_value,
    min(value)  AS min_value,
    max(value)  AS max_value,
    last(value, time) AS last_value,
    count(*)    AS sample_count
FROM car_telemetry
GROUP BY bucket, car_id, signal_name
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time) AS bucket,
    car_id,
    signal_name,
    avg(value)  AS avg_value,
    min(value)  AS min_value,
    max(value)  AS max_value,
    count(*)    AS sample_count
FROM car_telemetry
GROUP BY bucket, car_id, signal_name
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_1hour
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    car_id,
    signal_name,
    avg(value)  AS avg_value,
    min(value)  AS min_value,
    max(value)  AS max_value,
    count(*)    AS sample_count
FROM car_telemetry
GROUP BY bucket, car_id, signal_name
WITH NO DATA;

-- Refresh policies
SELECT add_continuous_aggregate_policy('telemetry_1min',
    start_offset => INTERVAL '10 minutes',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('telemetry_5min',
    start_offset => INTERVAL '1 hour',
    end_offset   => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('telemetry_1hour',
    start_offset => INTERVAL '3 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

-- -----------------------------------------------------------------------------
-- Lifecycle management: compression (7d) + retention (raw beyond 30d)
-- -----------------------------------------------------------------------------
ALTER TABLE car_telemetry SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'car_id, signal_name',
    timescaledb.compress_orderby   = 'time DESC'
);

SELECT add_compression_policy('car_telemetry', INTERVAL '7 days', if_not_exists => TRUE);

-- Drop raw rows after 30 days; aggregates persist for long-term trends.
SELECT add_retention_policy('car_telemetry', INTERVAL '30 days', if_not_exists => TRUE);

-- -----------------------------------------------------------------------------
-- Seed data (dev convenience)
-- -----------------------------------------------------------------------------
INSERT INTO users (user_id, name, email)
VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Owner', 'owner@example.com')
ON CONFLICT (email) DO NOTHING;

INSERT INTO cars (car_id, owner_id, make, model, year, vin)
VALUES ('acc001', '00000000-0000-0000-0000-000000000001', 'Honda', 'Accord', 2021, '1HGCV1F30MA000001')
ON CONFLICT (car_id) DO NOTHING;

INSERT INTO signal_registry (signal_name, pid, display_name, unit, min, max, vss_path, supported_models)
VALUES
    ('engine_speed',      '0C', 'Engine RPM',          'rpm',  0, 8000, 'Vehicle.Powertrain.CombustionEngine.Speed',            ARRAY['Accord']),
    ('vehicle_speed',     '0D', 'Vehicle Speed',       'km/h', 0, 240,  'Vehicle.Speed',                                        ARRAY['Accord']),
    ('coolant_temp',      '05', 'Coolant Temperature', 'degC', -40, 215,'Vehicle.Powertrain.CombustionEngine.ECT',              ARRAY['Accord']),
    ('throttle_position', '11', 'Throttle Position',   '%',    0, 100,  'Vehicle.Chassis.Accelerator.PedalPosition',            ARRAY['Accord']),
    ('intake_temp',       '0F', 'Intake Air Temp',     'degC', -40, 215,'Vehicle.Powertrain.CombustionEngine.IAT',              ARRAY['Accord']),
    ('maf',               '10', 'Mass Air Flow',       'g/s',  0, 655,  'Vehicle.Powertrain.CombustionEngine.MAF',              ARRAY['Accord']),
    ('fuel_level',        '2F', 'Fuel Level',          '%',    0, 100,  'Vehicle.Powertrain.FuelSystem.Level',                  ARRAY['Accord'])
ON CONFLICT (signal_name) DO NOTHING;
