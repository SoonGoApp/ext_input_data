SELECT_ALL_FEATURES_PREDICTION = """
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
),
model_price AS (
    SELECT v.model_id,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY v.manufacturer_price_tax_exc::FLOAT) AS median_price
    FROM publ.vehicles v
    WHERE v.manufacturer_price_tax_exc > 0
    GROUP BY v.model_id
),
trim_price AS (
    SELECT v.trim_id,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY v.manufacturer_price_tax_exc::FLOAT) AS median_price
    FROM publ.vehicles v
    WHERE v.manufacturer_price_tax_exc > 0 AND v.trim_id IS NOT NULL
    GROUP BY v.trim_id
),
segment_price AS (
    SELECT vm.model_category AS segment,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY v.manufacturer_price_tax_exc::FLOAT) AS median_price
    FROM publ.vehicles v
    JOIN common.vehicle_models vm ON v.model_id = vm.id
    WHERE v.manufacturer_price_tax_exc > 0
    GROUP BY vm.model_category
),
global_price AS (
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY manufacturer_price_tax_exc::FLOAT) AS median_price
    FROM publ.vehicles
    WHERE manufacturer_price_tax_exc > 0
),
-- effectif des loueurs sur la population d'ENTRAÎNEMENT (mêmes filtres que le train),
-- pour que 'unknown' soit attribué exactement aux mêmes loueurs
supplier_counts AS (
    SELECT v.supplier_id, COUNT(*) AS n
    FROM publ.vehicles v
    JOIN common.vehicle_models vm ON v.model_id = vm.id
    WHERE v.rebate_price >= 1000
      AND v.entry_into_fleet_date IS NOT NULL
      AND vm.model_category IS NOT NULL
      AND UPPER(vm.model_category) NOT IN ('UNKNOWN', 'SCOOTER', 'TWO_WHEEL', 'TRUCK', 'BIKE')
    GROUP BY v.supplier_id
)
SELECT
    v.id                                                        AS vehicle_id,

    COALESCE(NULLIF(v.manufacturer_price_tax_exc, 0)::FLOAT,
             tp.median_price, mp.median_price, sp.median_price, gp.median_price) AS manufacturer_price_tax_exc,
    (COALESCE(v.manufacturer_price_tax_exc, 0) > 0)::INT::FLOAT AS price_known,
    v.options_price_tax_inc::FLOAT                              AS options_price,
    v.accessories_price_tax_inc::FLOAT                          AS accessories_price,
    v.motor_power::FLOAT                                        AS motor_power,
    v.fiscal_power::FLOAT                                       AS fiscal_power,

    COALESCE(vc.contract_type, 'unknown')                       AS contract_type,
    COALESCE(v.energy, 'unknown')                               AS energy,
    EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT             AS entry_year,
    COALESCE(vm.model_category, 'unknown')                      AS segment,
    COALESCE(vb.name, 'unknown')                                AS brand,
    vm.name                                                     AS model,
    COALESCE(v.seat_count::FLOAT, 5.0)                          AS seat_count,
    COALESCE(v.transmission, 'unknown')                         AS transmission,
    CASE WHEN v.supplier_id IS NULL
              OR COALESCE(sc.n, 0) < 30
         THEN 'unknown' ELSE v.supplier_id::TEXT END            AS supplier,
    -- ===== Variables ajoutées : MÊMES colonnes et MÊMES règles que sell_sql_requests.py (entraînement) =====
    COALESCE(v.initial_mileage, v.initial_muleage)::FLOAT       AS initial_mileage,
    (EXTRACT(EPOCH FROM (v.entry_into_fleet_date - v.entry_into_service_date)) / 2629800.0)::FLOAT AS months_service_to_fleet,
    COALESCE(v.trim_id::TEXT, 'unknown')                        AS trim_id,
    COALESCE(v.model_version, 'unknown')                        AS model_version,
    COALESCE(v.national_type, 'unknown')                        AS national_type,
    v.co2_per_km::FLOAT                                         AS co2_per_km,
    COALESCE(v.curb_weight, v.kerb_weight::FLOAT)               AS weight,
    v.motor_volume::FLOAT                                       AS motor_volume,
    v.door_count::FLOAT                                         AS door_count,
    v.fuel_tank_capacity::FLOAT                                 AS fuel_tank_capacity,
    v.gross_weight::FLOAT                                       AS gross_weight,
    v.theoretical_fuel_consumption::FLOAT                       AS theoretical_fuel_consumption,
    COALESCE(v.fiscal_type, 'unknown')                          AS fiscal_type,
    COALESCE(v.critair, 'unknown')                              AS critair,
    v.battery_capacity::FLOAT                                   AS battery_capacity,
    v.electricity_consumption::FLOAT                            AS electricity_consumption,
    v.charge_power::FLOAT                                       AS charge_power,
    v.battery_price::FLOAT                                      AS battery_price,
    oa.org_active_at_entry

FROM publ.vehicles v
INNER JOIN vc_dedup vc                ON vc.vehicle_id = v.id
LEFT JOIN common.vehicle_models vm    ON v.model_id    = vm.id
LEFT JOIN common.vehicle_brands vb    ON v.brand_id    = vb.id
LEFT JOIN model_price mp              ON mp.model_id   = v.model_id
LEFT JOIN trim_price tp               ON tp.trim_id    = v.trim_id
LEFT JOIN segment_price sp            ON sp.segment    = vm.model_category
LEFT JOIN supplier_counts sc          ON sc.supplier_id = v.supplier_id
CROSS JOIN global_price gp
LEFT JOIN LATERAL (
    SELECT COUNT(*)::FLOAT AS org_active_at_entry
    FROM publ.vehicles v2
    WHERE v2.organization_id = v.organization_id
      AND v2.entry_into_fleet_date <= v.entry_into_fleet_date
      AND (v2.exit_from_fleet_date IS NULL OR v2.exit_from_fleet_date > v.entry_into_fleet_date)
) oa ON TRUE
WHERE
    vc.contract_type = 'ACQ'   -- on prédit uniquement les véhicules dont le contrat ACTUEL est ACQ
    AND v.entry_into_fleet_date IS NOT NULL
    AND vm.model_category IS NOT NULL
    AND UPPER(vm.model_category) NOT IN
        ('UNKNOWN', 'SCOOTER', 'TWO_WHEEL', 'TRUCK', 'BIKE')
;
"""