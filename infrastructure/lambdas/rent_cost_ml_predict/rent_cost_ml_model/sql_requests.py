SELECT_ALL_FEATURES_PREDICTION = rf"""
WITH base AS (
    SELECT
        v.id                                                AS vehicle_id,
        'ELECTRIC'                                          AS energy,
        DATE_PART('year', AGE(v.entry_into_fleet_date))     AS age,
        EXTRACT(YEAR FROM v.entry_into_fleet_date)          AS entry_year,
        v.trim_id                                           AS segment,
        v.brand_id                                          AS brand,
        vc.lease_months,
        vc.lease_mileage,
        vc.contract_type,
        v.co2_per_km::FLOAT                                 AS co2_per_km,
        v.fiscal_power::FLOAT                               AS fiscal_power,
        v.seat_count::FLOAT                                 AS seat_count,
        v.transmission,
        v.motor_power::FLOAT                                AS motor_power
    FROM publ.vehicles v
    JOIN publ.vehicle_contracts vc ON vc.vehicle_id = v.id
    WHERE
        v.energy != 'ELECTRIC'
        AND vc.contract_type != 'ACQ'
        AND v.entry_into_fleet_date IS NOT NULL
        AND v.energy IS NOT NULL
),

stats AS (
    SELECT
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY age)            AS median_age,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY entry_year)     AS median_entry_year,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lease_mileage)  AS median_lease_mileage,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY co2_per_km)     AS median_co2,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fiscal_power)   AS median_fiscal_power,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY seat_count)     AS median_seat_count,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY motor_power)    AS median_motor_power,
        MODE() WITHIN GROUP (ORDER BY lease_months)                  AS mode_lease_months,
        MODE() WITHIN GROUP (ORDER BY segment::TEXT)                 AS mode_segment,
        MODE() WITHIN GROUP (ORDER BY brand::TEXT)                   AS mode_brand,
        MODE() WITHIN GROUP (ORDER BY contract_type)                 AS mode_contract_type,
        MODE() WITHIN GROUP (ORDER BY transmission)                  AS mode_transmission
    FROM base
)

SELECT
    b.vehicle_id,
    b.energy,
    COALESCE(b.age,           s.median_age)           AS age,
    COALESCE(b.entry_year,    s.median_entry_year)    AS entry_year,
    COALESCE(b.segment::TEXT, s.mode_segment)         AS segment,
    COALESCE(b.brand::TEXT,   s.mode_brand)           AS brand,
    COALESCE(b.lease_months,  s.mode_lease_months)    AS lease_months,
    COALESCE(b.lease_mileage, s.median_lease_mileage) AS lease_mileage,
    COALESCE(b.contract_type, s.mode_contract_type)   AS contract_type,
    COALESCE(b.co2_per_km,    s.median_co2)           AS co2_per_km,
    COALESCE(b.fiscal_power,  s.median_fiscal_power)  AS fiscal_power,
    COALESCE(b.seat_count,    s.median_seat_count)    AS seat_count,
    COALESCE(b.transmission,  s.mode_transmission)    AS transmission,
    COALESCE(b.motor_power,   s.median_motor_power)   AS motor_power
FROM base b
CROSS JOIN stats s
;
"""