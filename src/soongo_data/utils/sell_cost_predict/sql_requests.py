SELECT_ALL_FEATURES_PREDICTION = rf"""
WITH base AS (
    SELECT
        v.id                                                            AS vehicle_id,
        v.energy,
        EXTRACT(YEAR FROM CURRENT_DATE)::INT - 
        EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT                 AS age,
        EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT                 AS entry_year,
        vm.model_category                                               AS segment,
        vb.name                                                         AS brand,
        v.fiscal_power::FLOAT                                           AS fiscal_power,
        v.seat_count::FLOAT                                             AS seat_count,
        v.transmission,
        v.motor_power::FLOAT                                            AS motor_power
    FROM publ.vehicles v
    JOIN publ.vehicle_contracts vc  ON vc.vehicle_id = v.id
    JOIN common.vehicle_models vm   ON v.model_id    = vm.id
    JOIN common.vehicle_brands vb   ON v.brand_id    = vb.id
    WHERE
        vc.contract_type            != 'ACQ'
        AND v.entry_into_fleet_date IS NOT NULL
        AND v.fiscal_power          IS NOT NULL
        AND v.seat_count            IS NOT NULL
        AND v.motor_power           IS NOT NULL
)
SELECT
    b.vehicle_id,
    COALESCE(b.energy,       'unknown')     AS energy,
    b.age,
    b.entry_year,
    COALESCE(b.segment,      'unknown')     AS segment,
    COALESCE(b.brand,        'unknown')     AS brand,
    b.fiscal_power,
    b.seat_count,
    COALESCE(b.transmission, 'unknown')     AS transmission,
    b.motor_power
FROM base b
;
"""