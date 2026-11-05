SELECT_ALL_FEATURES_TRAINING = """
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
        vc.vehicle_id,
        vc.total_rent_tax_exc::FLOAT                        AS target,
        v.energy,
        DATE_PART('year', AGE(v.entry_into_fleet_date))     AS age,
        EXTRACT(YEAR FROM v.entry_into_fleet_date)::INT      AS entry_year,
        vm.model_category                                   AS segment,
        vb.name                                             AS brand,
        vm.name                                             AS model,
        vc.lease_months::FLOAT                               AS lease_months,
        vc.lease_mileage::FLOAT                              AS lease_mileage,
        vc.contract_type,
        v.co2_per_km::FLOAT                                 AS co2_per_km,
        v.fiscal_power::FLOAT                               AS fiscal_power,
        v.seat_count::FLOAT                                 AS seat_count,
        v.transmission,
        v.motor_power::FLOAT                                AS motor_power,
        COALESCE(NULLIF(v.manufacturer_price_tax_exc, 0)::FLOAT,
                 mp.median_price, sp.median_price)          AS vehicle_price,
        (COALESCE(v.manufacturer_price_tax_exc, 0) > 0)::INT::FLOAT AS price_known,
        v.options_price_tax_inc::FLOAT                      AS options_price,
        v.accessories_price_tax_inc::FLOAT                  AS accessories_price,
        COALESCE(v.curb_weight, v.kerb_weight::FLOAT)::FLOAT AS curb_weight,
        v.gross_weight::FLOAT                               AS gross_weight,
        v.motor_volume::FLOAT                               AS motor_volume,
        v.door_count::FLOAT                                 AS door_count,
        v.theoretical_fuel_consumption::FLOAT               AS fuel_consumption,
        v.battery_capacity::FLOAT                           AS battery_capacity,
        v.fiscal_type,
        vc.supplier_id::TEXT                                AS supplier,
        vc.organization_id::TEXT                            AS organization,
        vc.lease_start_date::DATE                           AS lease_start_date,
        (EXTRACT(YEAR FROM vc.lease_start_date)
         + EXTRACT(MONTH FROM vc.lease_start_date) / 12.0)::FLOAT AS start_period,
        -- Périmètre du contrat (services inclus) : 1 si la composante est facturée.
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
        os.org_fleet_size,
        -- Indicateurs de valeur manquante (le fait qu'une caractéristique ne soit pas
        -- renseignée est une information : +0,02 de R² mesuré)
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
        -- CIBLES INTERMÉDIAIRES (préfixe label_) : montants des composantes du loyer.
        -- Jamais utilisés comme features : model_training exclut toute colonne 'label_*'.
        COALESCE(vc.financial_rent_tax_exc, 0)::FLOAT                       AS label_financial,
        COALESCE(vc.maintenance_rent_tax_exc, 0)::FLOAT                     AS label_maintenance,
        COALESCE(vc.tires_rent_tax_exc, 0)::FLOAT                           AS label_tires,
        COALESCE(vc.insurance_rent_tax_exc, 0)::FLOAT                       AS label_insurance,
        COALESCE(vc.other_rent_tax_exc, 0)::FLOAT                           AS label_other,
        (COALESCE(vc.financial_loss_rent_tax_exc, 0)
         + COALESCE(vc.replacement_vehicle_rent_tax_exc, 0)
         + COALESCE(vc.relay_vehicle_rent_tax_exc, 0)
         + COALESCE(vc.management_fee_rent_tax_exc, 0)
         + COALESCE(vc.assistance_rent_tax_exc, 0)
         + COALESCE(vc.telematics_rent_tax_exc, 0)
         + COALESCE(vc.fuel_card_management_rent_tax_exc, 0))::FLOAT        AS label_misc
    FROM publ.vehicle_contracts vc
    JOIN publ.vehicles v ON vc.vehicle_id = v.id
    JOIN common.vehicle_models vm ON v.model_id = vm.id
    JOIN common.vehicle_brands vb ON v.brand_id = vb.id
    LEFT JOIN common.vehicle_trims t ON t.id::TEXT = v.trim_id::TEXT
    LEFT JOIN model_price mp ON mp.model_id = v.model_id
    LEFT JOIN segment_price sp ON sp.segment = vm.model_category
    -- Taille de flotte : véhicules de l'organisation en parc à la date de début du contrat
    LEFT JOIN LATERAL (
        SELECT COUNT(*)::FLOAT AS org_fleet_size
        FROM publ.vehicles v2
        WHERE v2.organization_id = v.organization_id
          AND v2.entry_into_fleet_date <= COALESCE(vc.lease_start_date, NOW())
          AND (v2.exit_from_fleet_date IS NULL
               OR v2.exit_from_fleet_date > COALESCE(vc.lease_start_date, NOW()))
    ) os ON TRUE
    WHERE
        vc.total_rent_tax_exc IS NOT NULL
        AND vc.total_rent_tax_exc != '0'
        AND v.entry_into_fleet_date IS NOT NULL
        AND vc.lease_months IS NOT NULL
        AND vc.lease_mileage IS NOT NULL
        AND vc.contract_type != 'ACQ'
        -- fiscal_power / seat_count / motor_power peuvent être NULL (gérés à l'entraînement)

        -- ── Outliers : uniquement les saisies manifestement fausses (demande du client) ── ────────────────
        AND vc.total_rent_tax_exc >= 100                           -- loyer < 100 EUR : non crédible
        AND vc.lease_mileage BETWEEN 1000 AND 400000               -- km au contrat (ex. 1M km)
        AND vc.lease_months BETWEEN 6 AND 96                       -- durée
        AND vc.lease_mileage / vc.lease_months <= 10000            -- km/mois plausible
        AND v.entry_into_fleet_date <= NOW()                       -- pas d'entrée dans le futur
        -- loyer mensuel rapporté au prix catalogue (si connu) : 0,15 % a 6 % du prix
        AND (NULLIF(v.manufacturer_price_tax_exc, 0) IS NULL
             OR vc.total_rent_tax_exc / v.manufacturer_price_tax_exc BETWEEN 0.0015 AND 0.06)
        -- Total des loyers sur la durée <= 2,5 x le prix du véhicule (prix catalogue, sinon
        -- médiane modèle/segment). Médiane observée ~0,6x, 99e centile ~1,3x : au-delà,
        -- la saisie est manifestement fausse (ex. 62 000 EUR/mois pour une 3008).
        AND vc.total_rent_tax_exc * vc.lease_months
            <= 2.5 * COALESCE(NULLIF(v.manufacturer_price_tax_exc, 0), mp.median_price, sp.median_price,
                              vc.total_rent_tax_exc * vc.lease_months)
),

stats AS (
    SELECT
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY co2_per_km)     AS median_co2,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY vehicle_price)  AS median_price
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
        COALESCE(b.model,         'unknown')        AS model,
        b.lease_months,
        b.lease_mileage,
        COALESCE(b.contract_type, 'unknown')        AS contract_type,
        COALESCE(b.co2_per_km,    s.median_co2)     AS co2_per_km,
        b.fiscal_power,
        b.seat_count,
        COALESCE(b.transmission,  'unknown')        AS transmission,
        b.motor_power,
        COALESCE(b.vehicle_price, s.median_price)   AS vehicle_price,
        b.price_known,
        b.options_price,
        b.accessories_price,
        b.curb_weight,
        b.gross_weight,
        b.motor_volume,
        b.door_count,
        b.fuel_consumption,
        b.battery_capacity,
        COALESCE(b.fiscal_type, 'unknown')          AS fiscal_type,
        -- loueurs rares (< 30 contrats) regroupés en 'unknown' : le modèle apprend
        -- ainsi à gérer un loueur inconnu en production
        CASE WHEN b.supplier IS NULL
                  OR COUNT(*) OVER (PARTITION BY b.supplier) < 30
             THEN 'unknown' ELSE b.supplier END     AS supplier,
        COALESCE(b.organization, 'unknown')         AS organization,
        b.lease_start_date,
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
        b.org_fleet_size,
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
        b.label_financial,
        b.label_maintenance,
        b.label_tires,
        b.label_insurance,
        b.label_other,
        b.label_misc,
        -- groupe de contexte pour la détection d'outliers : nombre de services (plafonné à 4)
        LEAST(b.scope_maintenance + b.scope_tires + b.scope_insurance + b.scope_financial_loss
              + b.scope_replacement + b.scope_relay + b.scope_mgmt_fee + b.scope_other
              + b.scope_assistance + b.scope_telematics + b.scope_fuel_card, 4)::INT AS scope_bucket
    FROM base b
    CROSS JOIN stats s
)

SELECT
    i.vehicle_id,
    i.target,
    i.energy,
    i.age,
    i.entry_year,
    i.segment,
    i.brand,
    i.model,
    i.lease_months,
    i.lease_mileage,
    i.contract_type,
    i.lease_mileage / GREATEST(i.lease_months, 1)                        AS km_per_month,
    i.co2_per_km,
    i.fiscal_power,
    i.seat_count,
    i.transmission,
    i.motor_power,
    i.vehicle_price,
    i.price_known,
    i.options_price,
    i.accessories_price,
    i.vehicle_price + COALESCE(i.options_price, 0)
                    + COALESCE(i.accessories_price, 0)                   AS total_price,
    i.curb_weight,
    i.gross_weight,
    i.motor_volume,
    i.door_count,
    i.fuel_consumption,
    i.battery_capacity,
    i.fiscal_type,
    i.supplier,
    i.organization,
    i.lease_start_date,
    i.start_period,
    i.scope_maintenance,
    i.scope_tires,
    i.scope_insurance,
    i.scope_financial_loss,
    i.scope_replacement,
    i.scope_relay,
    i.scope_mgmt_fee,
    i.scope_other,
    i.scope_assistance,
    i.scope_telematics,
    i.scope_fuel_card,
    (i.scope_maintenance + i.scope_tires + i.scope_insurance + i.scope_financial_loss
     + i.scope_replacement + i.scope_relay + i.scope_mgmt_fee + i.scope_other
     + i.scope_assistance + i.scope_telematics + i.scope_fuel_card)      AS scope_count,
    i.org_fleet_size,
    i.fiscal_power_missing,
    i.seat_count_missing,
    i.motor_power_missing,
    i.options_price_missing,
    i.accessories_price_missing,
    i.curb_weight_missing,
    i.gross_weight_missing,
    i.motor_volume_missing,
    i.door_count_missing,
    i.fuel_consumption_missing,
    i.battery_capacity_missing,
    i.trim_auto,
    i.trim_electric,
    i.trim_hybrid,
    i.trim_business,
    i.trim_missing,
    i.label_financial,
    i.label_maintenance,
    i.label_tires,
    i.label_insurance,
    i.label_other,
    i.label_misc,
    -- Feature structurelle (le taux BCE et interest_per_month sont ajoutés côté Python)
    i.vehicle_price / GREATEST(i.lease_months, 1)                        AS price_per_month
FROM imputed i
;
"""