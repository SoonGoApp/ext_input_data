# Requête de prédiction rent_cost.
# DOIT rester alignée avec rent_cost_training/sql_requests.py : mêmes features, mêmes
# règles d'imputation (le modèle lit les colonnes listées dans metadata.feature_names).
# Colonnes du train volontairement absentes ici car non utilisées par le modèle :
#   model, entry_year, organization, org_fleet_size.
# ecb_rate et interest_per_month ne sont PAS calculés ici : ils sont ajoutés côté Python
# (utils/ecb_rates.add_ecb_features, API publique de la BCE) à partir de 'lease_start_date'.
SELECT_ALL_FEATURES_PREDICTION = rf"""
WITH model_price AS (
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

base AS (
    SELECT
        v.id                                                 AS vehicle_id,
        'ELECTRIC'                                           AS energy,
        DATE_PART('year', AGE(v.entry_into_fleet_date))      AS age,
        vm.model_category                                    AS segment,
        vb.name                                              AS brand,
        -- bornes dures identiques aux filtres du train (durée 6-96 mois, 1 000-400 000 km)
        LEAST(GREATEST(vc.lease_months::FLOAT, 6), 96)       AS lease_months,
        LEAST(GREATEST(vc.lease_mileage::FLOAT, 1000), 400000) AS lease_mileage,
        vc.contract_type,
        v.co2_per_km::FLOAT                                  AS co2_per_km,
        v.fiscal_power::FLOAT                                AS fiscal_power,
        v.seat_count::FLOAT                                  AS seat_count,
        v.transmission,
        v.motor_power::FLOAT                                 AS motor_power,
        COALESCE(NULLIF(v.manufacturer_price_tax_exc, 0)::FLOAT,
                 mp.median_price, sp.median_price)           AS vehicle_price,
        (COALESCE(v.manufacturer_price_tax_exc, 0) > 0)::INT::FLOAT AS price_known,
        v.options_price_tax_inc::FLOAT                       AS options_price,
        v.accessories_price_tax_inc::FLOAT                   AS accessories_price,
        COALESCE(v.curb_weight, v.kerb_weight::FLOAT)::FLOAT AS curb_weight,
        v.gross_weight::FLOAT                                AS gross_weight,
        v.motor_volume::FLOAT                                AS motor_volume,
        v.door_count::FLOAT                                  AS door_count,
        v.theoretical_fuel_consumption::FLOAT                AS fuel_consumption,
        v.battery_capacity::FLOAT                            AS battery_capacity,
        -- Indicateurs de valeur manquante (identiques au train)
        -- Signaux extraits du nom de finition (vehicle_trims.name) : attributs du véhicule,
        -- connus avant le contrat, qui se généralisent d'un modèle à l'autre.
        CASE WHEN v.transmission = 'AUTOMATIC'
                  OR lower(t.name) ~ '(eat[0-9]|edc|dct|dsg|bva|cvt|tronic|automati|elec|kwh)' THEN 1.0
             WHEN v.transmission = 'MANUAL'
                  OR lower(t.name) ~ '(bvm|manuel|(^|[^a-z])mt($|[^a-z]))' THEN 0.0
             ELSE 0.5 END::FLOAT                                             AS trim_auto,
        (lower(t.name) ~ '(elec|kwh|(^|[^a-z])bev($|[^a-z]))')::INT::FLOAT                AS trim_electric,
        (lower(t.name) ~ '(hybri|phev|(^|[^a-z])hev($|[^a-z])|rechargeable)')::INT::FLOAT AS trim_hybrid,
        (lower(t.name) ~ '(business|executive)')::INT::FLOAT                AS trim_business,
        (t.name IS NULL)::INT::FLOAT                                        AS trim_missing,
        (v.fiscal_power IS NULL)::INT::FLOAT AS fiscal_power_missing,
        (v.seat_count IS NULL)::INT::FLOAT AS seat_count_missing,
        (v.motor_power IS NULL)::INT::FLOAT AS motor_power_missing,
        (v.options_price_tax_inc IS NULL)::INT::FLOAT AS options_price_missing,
        (v.accessories_price_tax_inc IS NULL)::INT::FLOAT AS accessories_price_missing,
        (COALESCE(v.curb_weight, v.kerb_weight) IS NULL)::INT::FLOAT AS curb_weight_missing,
        (v.gross_weight IS NULL)::INT::FLOAT AS gross_weight_missing,
        (v.motor_volume IS NULL)::INT::FLOAT AS motor_volume_missing,
        (v.door_count IS NULL)::INT::FLOAT AS door_count_missing,
        (v.theoretical_fuel_consumption IS NULL)::INT::FLOAT AS fuel_consumption_missing,
        (v.battery_capacity IS NULL)::INT::FLOAT AS battery_capacity_missing,
        v.fiscal_type,
        vc.supplier_id::TEXT                                 AS supplier,
        (EXTRACT(YEAR FROM vc.lease_start_date)
         + EXTRACT(MONTH FROM vc.lease_start_date) / 12.0)::FLOAT AS start_period,
        -- Périmètre du contrat (services inclus) : 1 si la composante est facturée
        (COALESCE(vc.maintenance_rent_tax_exc, 0) > 0)::INT::FLOAT          AS scope_maintenance,
        (COALESCE(vc.tires_rent_tax_exc, 0) > 0)::INT::FLOAT                AS scope_tires,
        (COALESCE(vc.insurance_rent_tax_exc, 0) > 0)::INT::FLOAT            AS scope_insurance,
        (COALESCE(vc.financial_loss_rent_tax_exc, 0) > 0)::INT::FLOAT       AS scope_financial_loss,
        (COALESCE(vc.replacement_vehicle_rent_tax_exc, 0) > 0)::INT::FLOAT  AS scope_replacement,
        (COALESCE(vc.relay_vehicle_rent_tax_exc, 0) > 0)::INT::FLOAT        AS scope_relay,
        (COALESCE(vc.management_fee_rent_tax_exc, 0) > 0)::INT::FLOAT       AS scope_mgmt_fee,
        (COALESCE(vc.other_rent_tax_exc, 0) > 0)::INT::FLOAT                AS scope_other,
        (COALESCE(vc.assistance_rent_tax_exc, 0) > 0)::INT::FLOAT           AS scope_assistance,
        (COALESCE(vc.telematics_rent_tax_exc, 0) > 0)::INT::FLOAT           AS scope_telematics,
        (COALESCE(vc.fuel_card_management_rent_tax_exc, 0) > 0)::INT::FLOAT AS scope_fuel_card,
        vc.lease_start_date::DATE                            AS lease_start_date
    FROM publ.vehicles v
    JOIN publ.vehicle_contracts vc ON vc.vehicle_id = v.id
    JOIN common.vehicle_models vm ON v.model_id = vm.id
    JOIN common.vehicle_brands vb ON v.brand_id = vb.id
    LEFT JOIN common.vehicle_trims t ON t.id::TEXT = v.trim_id::TEXT
    LEFT JOIN model_price mp ON mp.model_id = v.model_id
    LEFT JOIN segment_price sp ON sp.segment = vm.model_category
    WHERE
        v.energy != 'ELECTRIC'
        AND vc.contract_type != 'ACQ'
        AND v.entry_into_fleet_date IS NOT NULL
        AND vc.lease_months IS NOT NULL
        AND vc.lease_mileage IS NOT NULL
        -- fiscal_power / seat_count / motor_power peuvent être NULL (médiane du train
        -- appliquée côté Python), comme à l'entraînement
),

stats AS (
    SELECT
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY co2_per_km)     AS median_co2,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY vehicle_price)  AS median_price
    FROM base
)

SELECT
    b.vehicle_id,
    COALESCE(b.energy,        'unknown')        AS energy,
    b.age,
    COALESCE(b.segment,       'unknown')        AS segment,
    COALESCE(b.brand,         'unknown')        AS brand,
    b.lease_months,
    b.lease_mileage,
    COALESCE(b.contract_type, 'unknown')        AS contract_type,
    b.lease_mileage / GREATEST(b.lease_months, 1)                       AS km_per_month,
    COALESCE(b.co2_per_km,    s.median_co2)     AS co2_per_km,
    b.fiscal_power,
    b.seat_count,
    COALESCE(b.transmission,  'unknown')        AS transmission,
    b.motor_power,
    COALESCE(b.vehicle_price, s.median_price)   AS vehicle_price,
    b.price_known,
    b.options_price,
    b.accessories_price,
    COALESCE(b.vehicle_price, s.median_price) + COALESCE(b.options_price, 0)
                    + COALESCE(b.accessories_price, 0)                  AS total_price,
    b.curb_weight,
    b.gross_weight,
    b.motor_volume,
    b.door_count,
    b.fuel_consumption,
    b.battery_capacity,
    b.fiscal_power_missing,
    b.seat_count_missing,
    b.motor_power_missing,
    b.options_price_missing,
    b.accessories_price_missing,
    b.curb_weight_missing,
    b.gross_weight_missing,
    b.motor_volume_missing,
    b.door_count_missing,
    b.fuel_consumption_missing,
    b.battery_capacity_missing,
    b.trim_auto,
    b.trim_electric,
    b.trim_hybrid,
    b.trim_business,
    b.trim_missing,
    COALESCE(b.fiscal_type, 'unknown')          AS fiscal_type,
    -- loueur inconnu/rare : le modèle le traite côté Python (-> 'unknown' appris au train)
    COALESCE(b.supplier, 'unknown')             AS supplier,
    b.start_period,
    b.scope_maintenance,
    b.scope_tires,
    b.scope_insurance,
    b.scope_financial_loss,
    b.scope_replacement,
    b.scope_relay,
    b.scope_mgmt_fee,
    b.scope_other,
    b.scope_assistance,
    b.scope_telematics,
    b.scope_fuel_card,
    (b.scope_maintenance + b.scope_tires + b.scope_insurance + b.scope_financial_loss
     + b.scope_replacement + b.scope_relay + b.scope_mgmt_fee + b.scope_other
     + b.scope_assistance + b.scope_telematics + b.scope_fuel_card)     AS scope_count,
    b.lease_start_date,
    COALESCE(b.vehicle_price, s.median_price) / GREATEST(b.lease_months, 1)           AS price_per_month
FROM base b
CROSS JOIN stats s
;
"""






# SELECT_ALL_FEATURES_PREDICTION = rf"""
# WITH base AS (
#     SELECT
#         v.id                                                 AS vehicle_id,
#         'ELECTRIC'                                           AS energy,
#         DATE_PART('year', AGE(v.entry_into_fleet_date))      AS age,
#         EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT       AS entry_year,
#         vm.model_category                                    AS segment,
#         vb.name                                              AS brand,
#         vc.lease_months::FLOAT                                AS lease_months,
#         vc.lease_mileage::FLOAT                               AS lease_mileage,
#         vc.contract_type,
#         v.co2_per_km::FLOAT                                  AS co2_per_km,
#         v.fiscal_power::FLOAT                                AS fiscal_power,
#         v.seat_count::FLOAT                                  AS seat_count,
#         v.transmission,
#         v.motor_power::FLOAT                                 AS motor_power
#     FROM publ.vehicles v
#     JOIN publ.vehicle_contracts vc ON vc.vehicle_id = v.id
#     JOIN common.vehicle_models vm ON v.model_id = vm.id
#     JOIN common.vehicle_brands vb ON v.brand_id = vb.id
#     WHERE
#         v.energy != 'ELECTRIC'
#         AND vc.contract_type != 'ACQ'
#         AND v.entry_into_fleet_date IS NOT NULL
#         AND v.fiscal_power IS NOT NULL
#         AND v.seat_count IS NOT NULL
#         AND v.motor_power IS NOT NULL
#         AND vc.lease_months IS NOT NULL
#         AND vc.lease_mileage IS NOT NULL
# ),

# stats AS (
#     SELECT
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY co2_per_km) AS median_co2
#     FROM base
# )

# SELECT
#     b.vehicle_id,
#     COALESCE(b.energy,        'unknown')        AS energy,
#     b.age,
#     b.entry_year,
#     COALESCE(b.segment,       'unknown')        AS segment,
#     COALESCE(b.brand,         'unknown')        AS brand,
#     b.lease_months,
#     b.lease_mileage,
#     COALESCE(b.contract_type, 'unknown')        AS contract_type,
#     COALESCE(b.co2_per_km,    s.median_co2)     AS co2_per_km,
#     b.fiscal_power,
#     b.seat_count,
#     COALESCE(b.transmission,  'unknown')        AS transmission,
#     b.motor_power
# FROM base b
# CROSS JOIN stats s
# ;
# """