SELECT_ALL_FEATURES_PREDICTION = rf"""
WITH base AS (
    SELECT
        v.id                                                 AS vehicle_id,
        'ELECTRIC'                                           AS energy,
        DATE_PART('year', AGE(v.entry_into_fleet_date))      AS age,
        EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT       AS entry_year,
        vm.model_category                                    AS segment,
        vb.name                                              AS brand,
        vc.lease_months::FLOAT                                AS lease_months,
        vc.lease_mileage::FLOAT                               AS lease_mileage,
        vc.contract_type,
        v.co2_per_km::FLOAT                                  AS co2_per_km,
        v.fiscal_power::FLOAT                                AS fiscal_power,
        v.seat_count::FLOAT                                  AS seat_count,
        v.transmission,
        v.motor_power::FLOAT                                 AS motor_power
    FROM publ.vehicles v
    JOIN publ.vehicle_contracts vc ON vc.vehicle_id = v.id
    JOIN common.vehicle_models vm ON v.model_id = vm.id
    JOIN common.vehicle_brands vb ON v.brand_id = vb.id
    WHERE
        v.energy != 'ELECTRIC'
        AND vc.contract_type != 'ACQ'
        AND v.entry_into_fleet_date IS NOT NULL
        AND v.fiscal_power IS NOT NULL
        AND v.seat_count IS NOT NULL
        AND v.motor_power IS NOT NULL
        AND vc.lease_months IS NOT NULL
        AND vc.lease_mileage IS NOT NULL
),

stats AS (
    SELECT
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY co2_per_km) AS median_co2
    FROM base
)

SELECT
    b.vehicle_id,
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
;
"""