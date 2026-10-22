SELECT_ALL_FEATURES_TRAINING = """
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
)
SELECT
    v.id                                                        AS vehicle_id,
    v.rebate_price::FLOAT                                       AS target,

    COALESCE(NULLIF(v.manufacturer_price_tax_exc, 0)::FLOAT,
             mp.median_price, sp.median_price, gp.median_price) AS manufacturer_price_tax_exc,
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
    -- loueur rare (< 30 véhicules) regroupé en 'unknown' : le modèle sait gérer un loueur inconnu
    CASE WHEN v.supplier_id IS NULL
              OR COUNT(*) OVER (PARTITION BY v.supplier_id) < 30
         THEN 'unknown' ELSE v.supplier_id::TEXT END            AS supplier,
    oa.org_active_at_entry

FROM publ.vehicles v
LEFT JOIN vc_dedup vc                 ON vc.vehicle_id = v.id
LEFT JOIN common.vehicle_models vm    ON v.model_id    = vm.id
LEFT JOIN common.vehicle_brands vb    ON v.brand_id    = vb.id
LEFT JOIN model_price mp              ON mp.model_id   = v.model_id
LEFT JOIN segment_price sp            ON sp.segment    = vm.model_category
CROSS JOIN global_price gp
LEFT JOIN LATERAL (
    -- véhicules de l'organisation EN PARC à la date d'entrée de ce véhicule
    SELECT COUNT(*)::FLOAT AS org_active_at_entry
    FROM publ.vehicles v2
    WHERE v2.organization_id = v.organization_id
      AND v2.entry_into_fleet_date <= v.entry_into_fleet_date
      AND (v2.exit_from_fleet_date IS NULL OR v2.exit_from_fleet_date > v.entry_into_fleet_date)
) oa ON TRUE
WHERE
    v.rebate_price >= 1000
    AND v.entry_into_fleet_date IS NOT NULL
    AND vm.model_category IS NOT NULL
    AND UPPER(vm.model_category) NOT IN
        ('UNKNOWN', 'SCOOTER', 'TWO_WHEEL', 'TRUCK', 'BIKE')
    -- AND vc.contract_type = 'ACQ'
;
"""





# SELECT_ALL_FEATURES_TRAINING = """
# WITH vc_current AS (
#     SELECT
#         id,
#         vehicle_id,
#         contract_type,
#         date_from
#     FROM publ.vehicle_contracts
#     WHERE tstzrange(date_from, date_to, '[)') @> now()
# ),
# vc_dedup AS (
#     SELECT DISTINCT ON (vehicle_id)
#         vehicle_id,
#         contract_type
#     FROM vc_current
#     ORDER BY vehicle_id, date_from DESC, id DESC
# )
# SELECT
#     v.id                                                        AS vehicle_id,
#     v.rebate_price::FLOAT                                       AS target,
 
#     COALESCE(
#         v.manufacturer_price_tax_exc::FLOAT,
#         AVG(v.manufacturer_price_tax_exc::FLOAT) OVER ()
#     )                                                            AS manufacturer_price_tax_exc,
 
#     COALESCE(
#         v.motor_power::FLOAT,
#         AVG(v.motor_power::FLOAT) OVER ()
#     )                                                            AS motor_power,
 
#     v.fiscal_power::FLOAT                                       AS fiscal_power,
 
#     COALESCE(vc.contract_type, 'unknown')                       AS contract_type,
#     COALESCE(v.energy, 'unknown')                                AS energy,
#     EXTRACT(YEAR FROM CURRENT_DATE)::INT
#         - EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT       AS age,
#     EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT             AS entry_year,
#     COALESCE(vm.model_category, 'unknown')                      AS segment,
#     COALESCE(vb.name, 'unknown')                                AS brand,
#     vm.name                                                     AS model,
#     COALESCE(v.seat_count::FLOAT, 5.0)                          AS seat_count,
#     COALESCE(v.transmission, 'unknown')                         AS transmission
 
# FROM publ.vehicles v
# LEFT JOIN vc_dedup vc                 ON vc.vehicle_id = v.id
# LEFT JOIN common.vehicle_models vm    ON v.model_id    = vm.id
# LEFT JOIN common.vehicle_brands vb    ON v.brand_id    = vb.id
# WHERE
#     v.rebate_price >= 1000 
#     AND v.entry_into_fleet_date IS NOT NULL
#     AND vm.model_category IS NOT NULL
#     AND UPPER(vm.model_category) NOT IN 
#         ('UNKNOWN', 'SCOOTER', 'TWO_WHEEL', 'TRUCK', 'BIKE')
#     -- AND vc.contract_type = 'ACQ'
# ;
# """