SELECT_ALL_FEATURES_TRAINING = """
WITH base AS (
    SELECT
        vc.vehicle_id,
        v.rebate_price::FLOAT                                   AS target,
        v.energy,
        EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT         AS entry_year,
        vm.model_category                                       AS segment,
        vb.name                                                 AS brand,
        v.fiscal_power::FLOAT                                   AS fiscal_power,
        v.seat_count::FLOAT                                     AS seat_count,
        v.transmission,
        v.motor_power::FLOAT                                    AS motor_power
    FROM publ.vehicle_contracts vc
    JOIN publ.vehicles v             ON vc.vehicle_id = v.id
    JOIN common.vehicle_models vm    ON v.model_id    = vm.id
    JOIN common.vehicle_brands vb    ON v.brand_id    = vb.id
    WHERE
        vc.contract_type             = 'ACQ'
        AND v.rebate_price           IS NOT NULL
        AND v.rebate_price::FLOAT    != 0
        AND v.entry_into_fleet_date  IS NOT NULL
        AND v.fiscal_power           IS NOT NULL
        AND v.seat_count             IS NOT NULL
        AND v.motor_power            IS NOT NULL
),
stats AS (
    SELECT
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY target)   AS q1_target,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY target)   AS q3_target
    FROM base
),
imputed AS (
    SELECT
        b.vehicle_id,
        b.target,
        COALESCE(b.energy,       'unknown')                         AS energy,
        EXTRACT(YEAR FROM CURRENT_DATE)::INT - b.entry_year         AS age,
        b.entry_year,
        COALESCE(b.segment,      'unknown')                         AS segment,
        COALESCE(b.brand,        'unknown')                         AS brand,
        b.fiscal_power,
        b.seat_count,
        COALESCE(b.transmission, 'unknown')                         AS transmission,
        b.motor_power
    FROM base b
),
outliers_bounds AS (
    SELECT
        q1_target - 1.5 * (q3_target - q1_target)  AS lower_target,
        q3_target + 1.5 * (q3_target - q1_target)  AS upper_target
    FROM stats
)
SELECT
    i.vehicle_id,
    i.target,
    i.energy,
    i.age,
    i.entry_year,
    i.segment,
    i.brand,
    i.fiscal_power,
    i.seat_count,
    i.transmission,
    i.motor_power
FROM imputed i
CROSS JOIN outliers_bounds ob
WHERE i.target BETWEEN ob.lower_target AND ob.upper_target
;
"""