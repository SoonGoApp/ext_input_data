SELECT_ALL_FEATURES_TRAINING = """
WITH base AS (
    SELECT
        vc.vehicle_id,
        vc.total_rent_tax_exc::FLOAT                        AS target,
        v.energy,
        DATE_PART('year', AGE(v.entry_into_fleet_date))     AS age,
        EXTRACT(YEAR FROM v.entry_into_fleet_date)          AS entry_year,
        vm.model_category                                   AS segment,
        vb.name                                             AS brand,
        vc.lease_months,
        vc.lease_mileage,
        vc.contract_type,
        v.co2_per_km::FLOAT                                 AS co2_per_km,
        v.fiscal_power::FLOAT                               AS fiscal_power,
        v.seat_count::FLOAT                                 AS seat_count,
        v.transmission,
        v.motor_power::FLOAT                                AS motor_power
    FROM publ.vehicle_contracts vc
    JOIN publ.vehicles v ON vc.vehicle_id = v.id
    JOIN common.vehicle_models vm ON v.model_id = vm.id
    JOIN common.vehicle_brands vb ON v.brand_id = vb.id
    WHERE
        vc.total_rent_tax_exc IS NOT NULL
        AND vc.total_rent_tax_exc != '0'
        AND v.entry_into_fleet_date IS NOT NULL
        AND v.fiscal_power IS NOT NULL
        AND v.seat_count IS NOT NULL
        AND v.motor_power IS NOT NULL
        AND vc.lease_months IS NOT NULL
        AND vc.lease_mileage IS NOT NULL
        AND vc.contract_type != 'ACQ'
),

stats AS (
    SELECT
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY target)        AS q1_target,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY target)        AS q3_target,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY age)           AS q1_age,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY age)           AS q3_age,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY lease_mileage) AS q1_mileage,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY lease_mileage) AS q3_mileage,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY co2_per_km)     AS median_co2
    FROM base
),

imputed AS (
    SELECT
        b.vehicle_id,
        b.target,
        COALESCE(b.energy,        'unknown')        AS energy,
        b.age,
        b.entry_year,
        COALESCE(b.segment,       'unknown')        AS segment,
        COALESCE(b.brand,         'unknown')        AS brand,
        b.lease_months,
        b.lease_mileage,
        COALESCE(b.contract_type, 'unknown')        AS contract_type,
        COALESCE(b.co2_per_km,    s.median_co2)     AS co2_per_km,
        b.fiscal_power,
        b.seat_count,
        COALESCE(b.transmission,  'unknown')        AS transmission,
        b.motor_power
    FROM base b
    CROSS JOIN stats s
),

outliers_bounds AS (
    SELECT
        q1_target  - 1.5 * (q3_target  - q1_target)    AS lower_target,
        q3_target  + 1.5 * (q3_target  - q1_target)    AS upper_target,
        q1_age     - 1.5 * (q3_age     - q1_age)       AS lower_age,
        q3_age     + 1.5 * (q3_age     - q1_age)       AS upper_age,
        q1_mileage - 1.5 * (q3_mileage - q1_mileage)   AS lower_mileage,
        q3_mileage + 1.5 * (q3_mileage - q1_mileage)   AS upper_mileage
    FROM stats
)

SELECT
    i.vehicle_id,
    i.target,
    i.energy,
    GREATEST(ob.lower_age, LEAST(ob.upper_age, i.age))                   AS age,
    i.entry_year,
    i.segment,
    i.brand,
    i.lease_months,
    GREATEST(ob.lower_mileage, LEAST(ob.upper_mileage, i.lease_mileage)) AS lease_mileage,
    i.contract_type,
    i.co2_per_km,
    i.fiscal_power,
    i.seat_count,
    i.transmission,
    i.motor_power
FROM imputed i
CROSS JOIN outliers_bounds ob
WHERE i.target BETWEEN ob.lower_target AND ob.upper_target
;
"""