-- Solar Monitor — esquema de base de datos PostgreSQL
-- Ejecutar con: psql -U solar -d solar_monitor -f schema.sql

CREATE DATABASE solar_monitor;
-- o si ya existe:
-- CREATE DATABASE solar_monitor;  -- saltará error si ya existe, ignóralo

\c solar_monitor;

-- Tabla principal de lecturas del inversor
CREATE TABLE IF NOT EXISTS solar_readings (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    device          TEXT NOT NULL,          -- 'sungrow_sh6', 'wibeee_mono', etc.

    -- Potencia
    total_dc_power_w    NUMERIC(10, 2),   -- Potencia DC total (W)
    total_ac_power_w    NUMERIC(10, 2),   -- Potencia AC total (W)

    -- Tensión
    voltage_l1_v        NUMERIC(8, 3),    -- Fase L1 (V)
    voltage_l2_v        NUMERIC(8, 3),    -- Fase L2 (V)
    voltage_l3_v        NUMERIC(8, 3),    -- Fase L3 (V)

    -- Corriente
    current_l1_a        NUMERIC(8, 3),    -- Fase L1 (A)
    current_l2_a        NUMERIC(8, 3),    -- Fase L2 (A)
    current_l3_a        NUMERIC(8, 3),    -- Fase L3 (A)

    -- Energía
    total_energy_kwh    NUMERIC(12, 3),   -- Energía total generada (kWh)

    -- Estado
    device_status       INTEGER,          -- 0=off, 1=on, 2=standby, etc.

    -- Consumos Wibeee (NULL si no disponible aún)
    consumption_w       NUMERIC(10, 2),   -- Consumo activo (W)
    consumption_var     NUMERIC(10, 2),   -- Consumo reactivo (VAR)

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para consultas eficientes
CREATE INDEX IF NOT EXISTS idx_solar_readings_timestamp ON solar_readings (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_solar_readings_device    ON solar_readings (device);

-- Tabla de valores diários agregados (para gráficas largas)
CREATE TABLE IF NOT EXISTS daily_summary (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE NOT NULL UNIQUE,
    device          TEXT NOT NULL,

    -- Energía generada ese día (kWh)
    energy_kwh      NUMERIC(12, 3),

    -- Potencia pico (W)
    peak_power_w    NUMERIC(10, 2),

    -- Media de producción (W)
    avg_power_w     NUMERIC(10, 2),

    -- Consumo total Wibeee (kWh)
    consumption_kwh NUMERIC(12, 3),

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_summary_date   ON daily_summary (date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_summary_device ON daily_summary (device);

-- Función para actualizar resúmenes diários automáticamente
CREATE OR REPLACE FUNCTION update_daily_summary()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO daily_summary (date, device, energy_kwh, peak_power_w, avg_power_w)
    VALUES (
        CURRENT_DATE,
        NEW.device,
        NEW.total_energy_kwh,
        NEW.total_ac_power_w,
        NEW.total_ac_power_w  -- provisional, se calculará con ventana
    )
    ON CONFLICT (date, device) DO UPDATE SET
        energy_kwh    = GREATEST(daily_summary.energy_kwh, NEW.total_energy_kwh),
        peak_power_w  = GREATEST(daily_summary.peak_power_w, COALESCE(NEW.total_ac_power_w, 0));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para actualizar resúmenes en cada insert
-- DESCOMENTA cuando quieras activar la función:
-- CREATE TRIGGER trigger_update_daily_summary
--    AFTER INSERT ON solar_readings
--    FOR EACH ROW EXECUTE FUNCTION update_daily_summary();