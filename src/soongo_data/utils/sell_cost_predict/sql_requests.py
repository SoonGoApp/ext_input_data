SELECT_ALL_FEATURES_PREDICTION = """
-- Prediction du cout de reprise (rebate_price) pour les vehicules dont le
-- contrat ACTUEL est de type ACQ.

WITH vc_current AS (
    SELECT
        id,
        vehicle_id,
        contract_type,
        date_from
    FROM publ.vehicle_contracts
    WHERE tstzrange(date_from, date_to, '[)') @> now()
),
vc_dedup AS (
    SELECT DISTINCT ON (vehicle_id)
        vehicle_id,
        contract_type
    FROM vc_current
    ORDER BY vehicle_id, date_from DESC, id DESC
)
SELECT
    v.id                                                        AS vehicle_id,

    COALESCE(
        v.manufacturer_price_tax_exc::FLOAT,
        AVG(v.manufacturer_price_tax_exc::FLOAT) OVER ()
    )                                                            AS manufacturer_price_tax_exc,

    COALESCE(
        v.motor_power::FLOAT,
        AVG(v.motor_power::FLOAT) OVER ()
    )                                                            AS motor_power,

    v.fiscal_power::FLOAT                                       AS fiscal_power,

    vc.contract_type                                            AS contract_type,
    COALESCE(v.energy, 'unknown')                                AS energy,
    EXTRACT(YEAR FROM CURRENT_DATE)::INT
        - EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT       AS age,
    EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT             AS entry_year,
    COALESCE(vm.model_category, 'unknown')                      AS segment,
    COALESCE(vb.name, 'unknown')                                AS brand,
    vm.name                                                     AS model,
    COALESCE(v.seat_count::FLOAT, 5.0)                          AS seat_count,
    COALESCE(v.transmission, 'unknown')                         AS transmission

FROM publ.vehicles v
INNER JOIN vc_dedup vc                ON vc.vehicle_id = v.id
LEFT JOIN common.vehicle_models vm    ON v.model_id    = vm.id
LEFT JOIN common.vehicle_brands vb    ON v.brand_id    = vb.id
WHERE
    vc.contract_type = 'ACQ'                                     -- on predit uniquement les vehicules dont le contrat ACTUEL est ACQ
    AND v.entry_into_fleet_date IS NOT NULL
    AND vm.model_category IS NOT NULL
    AND UPPER(vm.model_category) NOT IN                          -- hors perimetre VL, comme au training
        ('UNKNOWN', 'SCOOTER', 'TWO_WHEEL', 'TRUCK', 'BIKE')
;
"""