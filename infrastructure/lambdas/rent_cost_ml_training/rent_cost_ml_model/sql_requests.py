SELECT_ALL_FEATURES_TRAINING = """
WITH base AS (
    SELECT
        vc.vehicle_id,
        vc.total_rent_tax_exc::FLOAT                        AS target,
        v.energy,
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
    FROM publ.vehicle_contracts vc
    JOIN publ.vehicles v ON vc.vehicle_id = v.id
    WHERE
        vc.total_rent_tax_exc IS NOT NULL
        AND vc.total_rent_tax_exc != '0'
        AND v.energy IS NOT NULL
        AND v.entry_into_fleet_date IS NOT NULL
        AND vc.contract_type != 'ACQ'
),

stats AS (
    SELECT
        -- Médianes (numériques)
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY age)            AS median_age,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY entry_year)     AS median_entry_year,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lease_mileage)  AS median_lease_mileage,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY co2_per_km)     AS median_co2,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fiscal_power)   AS median_fiscal_power,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY seat_count)     AS median_seat_count,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY motor_power)    AS median_motor_power,

        -- Modes (catégorielles)
        MODE() WITHIN GROUP (ORDER BY lease_months)                  AS mode_lease_months,
        MODE() WITHIN GROUP (ORDER BY energy)                        AS mode_energy,
        MODE() WITHIN GROUP (ORDER BY segment::TEXT)                 AS mode_segment,
        MODE() WITHIN GROUP (ORDER BY brand::TEXT)                   AS mode_brand,
        MODE() WITHIN GROUP (ORDER BY contract_type)                 AS mode_contract_type,
        MODE() WITHIN GROUP (ORDER BY transmission)                  AS mode_transmission,

        -- Percentiles pour outliers target
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY target)        AS q1_target,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY target)        AS q3_target,

        -- Percentiles pour winsorization
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY age)           AS q1_age,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY age)           AS q3_age,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY lease_mileage) AS q1_mileage,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY lease_mileage) AS q3_mileage
    FROM base
),

imputed AS (
    SELECT
        b.vehicle_id,
        b.target,
        COALESCE(b.energy,          s.mode_energy)          AS energy,
        COALESCE(b.age,             s.median_age)           AS age,
        COALESCE(b.entry_year,      s.median_entry_year)    AS entry_year,
        COALESCE(b.segment::TEXT,   s.mode_segment)         AS segment,
        COALESCE(b.brand::TEXT,     s.mode_brand)           AS brand,
        COALESCE(b.lease_months,    s.mode_lease_months)    AS lease_months,
        COALESCE(b.lease_mileage,   s.median_lease_mileage) AS lease_mileage,
        COALESCE(b.contract_type,   s.mode_contract_type)   AS contract_type,
        COALESCE(b.co2_per_km,      s.median_co2)           AS co2_per_km,
        COALESCE(b.fiscal_power,    s.median_fiscal_power)  AS fiscal_power,
        COALESCE(b.seat_count,      s.median_seat_count)    AS seat_count,
        COALESCE(b.transmission,    s.mode_transmission)    AS transmission,
        COALESCE(b.motor_power,     s.median_motor_power)   AS motor_power
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
    GREATEST(ob.lower_age, LEAST(ob.upper_age, i.age))                  AS age,
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


# SELECT_ALL_FEATURES_TRAINING = """
# WITH base AS (
#     SELECT
#         vc.vehicle_id,
#         vc.total_rent_tax_exc::FLOAT                        AS target,

#         -- Features originales
#         v.energy,
#         DATE_PART('year', AGE(v.entry_into_fleet_date))     AS age,
#         v.trim_id                                           AS segment,
#         v.brand_id                                          AS brand,
#         vc.lease_months,
#         vc.lease_mileage,
#         vc.contract_type,

#         -- Nouvelles features vehicle_contracts
#         vc.financial_rent_tax_exc::FLOAT                    AS financial_rent,
#         vc.maintenance_rent_tax_exc::FLOAT                  AS maintenance_rent,
#         vc.insurance_rent_tax_exc::FLOAT                    AS insurance_rent,
#         vc.interest_rate::FLOAT                             AS interest_rate,
#         vc.residual_value::FLOAT                            AS residual_value,

#         -- Nouvelles features vehicles
#         v.co2_per_km::FLOAT                                 AS co2_per_km,
#         v.fiscal_power::FLOAT                               AS fiscal_power,
#         v.manufacturer_price_tax_exc::FLOAT                 AS manufacturer_price,
#         v.seat_count::FLOAT                                 AS seat_count,
#         v.transmission,
#         v.motor_power::FLOAT                                AS motor_power,
#         v.curb_weight::FLOAT                                AS curb_weight

#     FROM publ.vehicle_contracts vc
#     JOIN publ.vehicles v ON vc.vehicle_id = v.id
#     WHERE
#         vc.total_rent_tax_exc IS NOT NULL
#         AND vc.total_rent_tax_exc != '0'
#         AND v.energy IS NOT NULL
#         AND v.entry_into_fleet_date IS NOT NULL
# ),

# stats AS (
#     SELECT
#         -- Médianes (numériques asymétriques)
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY age)                AS median_age,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lease_mileage)      AS median_lease_mileage,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY financial_rent)     AS median_financial_rent,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY maintenance_rent)   AS median_maintenance_rent,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY insurance_rent)     AS median_insurance_rent,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY interest_rate)      AS median_interest_rate,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY residual_value)     AS median_residual_value,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY co2_per_km)         AS median_co2,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fiscal_power)       AS median_fiscal_power,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY manufacturer_price) AS median_manufacturer_price,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY motor_power)        AS median_motor_power,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY curb_weight)        AS median_curb_weight,
#         PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY seat_count)         AS median_seat_count,

#         -- Modes (catégorielles)
#         MODE() WITHIN GROUP (ORDER BY lease_months)                      AS mode_lease_months,
#         MODE() WITHIN GROUP (ORDER BY energy)                            AS mode_energy,
#         MODE() WITHIN GROUP (ORDER BY segment::TEXT)                     AS mode_segment,
#         MODE() WITHIN GROUP (ORDER BY brand::TEXT)                       AS mode_brand,
#         MODE() WITHIN GROUP (ORDER BY contract_type)                     AS mode_contract_type,
#         MODE() WITHIN GROUP (ORDER BY transmission)                      AS mode_transmission,

#         -- Percentiles pour outliers target
#         PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY target)            AS q1_target,
#         PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY target)            AS q3_target,

#         -- Percentiles pour winsorization age et mileage
#         PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY age)               AS q1_age,
#         PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY age)               AS q3_age,
#         PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY lease_mileage)     AS q1_mileage,
#         PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY lease_mileage)     AS q3_mileage
#     FROM base
# ),

# imputed AS (
#     SELECT
#         b.vehicle_id,
#         b.target,
#         COALESCE(b.energy,              s.mode_energy)                  AS energy,
#         COALESCE(b.age,                 s.median_age)                   AS age,
#         COALESCE(b.segment::TEXT,       s.mode_segment)                 AS segment,
#         COALESCE(b.brand::TEXT,         s.mode_brand)                   AS brand,
#         COALESCE(b.lease_months,        s.mode_lease_months)            AS lease_months,
#         COALESCE(b.lease_mileage,       s.median_lease_mileage)         AS lease_mileage,
#         COALESCE(b.contract_type,       s.mode_contract_type)           AS contract_type,
#         COALESCE(b.financial_rent,      s.median_financial_rent)        AS financial_rent,
#         COALESCE(b.maintenance_rent,    s.median_maintenance_rent)      AS maintenance_rent,
#         COALESCE(b.insurance_rent,      s.median_insurance_rent)        AS insurance_rent,
#         COALESCE(b.interest_rate,       s.median_interest_rate)         AS interest_rate,
#         COALESCE(b.residual_value,      s.median_residual_value)        AS residual_value,
#         COALESCE(b.co2_per_km,          s.median_co2)                   AS co2_per_km,
#         COALESCE(b.fiscal_power,        s.median_fiscal_power)          AS fiscal_power,
#         COALESCE(b.manufacturer_price,  s.median_manufacturer_price)    AS manufacturer_price,
#         COALESCE(b.seat_count,          s.median_seat_count)            AS seat_count,
#         COALESCE(b.transmission,        s.mode_transmission)            AS transmission,
#         COALESCE(b.motor_power,         s.median_motor_power)           AS motor_power,
#         COALESCE(b.curb_weight,         s.median_curb_weight)           AS curb_weight
#     FROM base b
#     CROSS JOIN stats s
# ),

# outliers_bounds AS (
#     SELECT
#         q1_target  - 1.5 * (q3_target  - q1_target)    AS lower_target,
#         q3_target  + 1.5 * (q3_target  - q1_target)    AS upper_target,
#         q1_age     - 1.5 * (q3_age     - q1_age)       AS lower_age,
#         q3_age     + 1.5 * (q3_age     - q1_age)       AS upper_age,
#         q1_mileage - 1.5 * (q3_mileage - q1_mileage)   AS lower_mileage,
#         q3_mileage + 1.5 * (q3_mileage - q1_mileage)   AS upper_mileage
#     FROM stats
# )

# SELECT
#     i.vehicle_id,
#     i.target,
#     i.energy,
#     GREATEST(ob.lower_age,     LEAST(ob.upper_age,     i.age))           AS age,
#     i.segment,
#     i.brand,
#     i.lease_months,
#     GREATEST(ob.lower_mileage, LEAST(ob.upper_mileage, i.lease_mileage)) AS lease_mileage,
#     i.contract_type,
#     i.financial_rent,
#     i.maintenance_rent,
#     i.insurance_rent,
#     i.interest_rate,
#     i.residual_value,
#     i.co2_per_km,
#     i.fiscal_power,
#     i.manufacturer_price,
#     i.seat_count,
#     i.transmission,
#     i.motor_power,
#     i.curb_weight
# FROM imputed i
# CROSS JOIN outliers_bounds ob
# WHERE
#     i.target BETWEEN ob.lower_target AND ob.upper_target
# ;
# """





