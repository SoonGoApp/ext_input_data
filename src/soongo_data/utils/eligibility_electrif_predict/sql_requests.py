
SELECT_ALL_FEATURES_PREDICTION = rf"""
WITH 
-- Base vehicle selection for prediction
ranked_collaborators AS (
    SELECT
        cv.vehicle_id,
        cv.collaborator_id,
        ROW_NUMBER() OVER (
            PARTITION BY cv.vehicle_id
            ORDER BY
                CASE WHEN cv.date_to IS NULL OR cv.date_to > CURRENT_DATE THEN 0 ELSE 1 END,
                cv.date_to DESC NULLS LAST,
                cv.date_from DESC NULLS LAST,
                cv.id DESC
        ) AS rn
    FROM publ.collaborators_vehicles cv
),

base_vehicles AS (
    SELECT
        v.id AS vehicle_id,
        rc.collaborator_id AS current_collaborator_id,

        -- Age and lease duration as categories instead of raw numeric + COALESCE median
        CASE
            WHEN v.entry_into_fleet_date IS NULL THEN 'UNKNOWN'
            WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, v.entry_into_fleet_date::timestamp)) < 2  THEN '0-2'
            WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, v.entry_into_fleet_date::timestamp)) < 5  THEN '2-5'
            WHEN EXTRACT(YEAR FROM AGE(CURRENT_DATE, v.entry_into_fleet_date::timestamp)) < 10 THEN '5-10'
            ELSE '10+'
        END AS vehicle_age_category,

        CASE
            WHEN v.lease_start_date IS NULL OR v.lease_end_date IS NULL THEN 'UNKNOWN'
            WHEN (EXTRACT(EPOCH FROM (v.lease_end_date::timestamp - v.lease_start_date::timestamp)) / 86400.0) / 30.44 < 12  THEN '0-12'
            WHEN (EXTRACT(EPOCH FROM (v.lease_end_date::timestamp - v.lease_start_date::timestamp)) / 86400.0) / 30.44 < 24  THEN '12-24'
            WHEN (EXTRACT(EPOCH FROM (v.lease_end_date::timestamp - v.lease_start_date::timestamp)) / 86400.0) / 30.44 < 36  THEN '24-36'
            WHEN (EXTRACT(EPOCH FROM (v.lease_end_date::timestamp - v.lease_start_date::timestamp)) / 86400.0) / 30.44 < 48  THEN '36-48'
            ELSE '48+'
        END AS lease_duration_category,

        -- Numeric vehicle features (kept for model use)
        CAST(v.theoretical_fuel_consumption AS NUMERIC) AS fuel_consumption,
        CAST(v.co2_per_km AS NUMERIC)                   AS co2_emissions,
        CAST(v.fiscal_power AS NUMERIC)                  AS fiscal_power_num,
        CAST(v.motor_power AS NUMERIC)                   AS motor_power_num,
        CAST(v.seat_count AS NUMERIC)                    AS seat_count_num,

        -- energy_type removed (data leakage + unused)
        COALESCE(v.assignment_type, 'UNKNOWN') AS assignment_type,
        COALESCE(v.fiscal_type, 'UNKNOWN')     AS fiscal_type,
        CASE WHEN v.vehicle_status = 'ACTIVE' THEN 1 ELSE 0 END AS is_active
    FROM publ.vehicles v
    INNER JOIN ranked_collaborators rc ON rc.vehicle_id = v.id AND rc.rn = 1
    WHERE v.fiscal_type = 'PERSONAL_CAR'
),

-- Mileage features
mileage_stats AS (
    SELECT
        mpv.vehicle_id,
        AVG(mpv.mileage_driven)    AS mileage_driven_mean,
        -- std, max, min not affected by duration; sum normalized below
        STDDEV(mpv.mileage_driven) AS mileage_driven_std,
        MAX(mpv.mileage_driven)    AS mileage_driven_max,
        MIN(mpv.mileage_driven)    AS mileage_driven_min,
        -- normalize sum by month count to remove duration bias
        CASE 
            WHEN COUNT(mpv.mileage_month) > 0
            THEN SUM(mpv.mileage_driven) / COUNT(mpv.mileage_month)
            ELSE 0
        END AS mileage_driven_per_month,
        COUNT(mpv.mileage_month)   AS mileage_month_count,
        AVG(mpv.first_days_diff)   AS first_days_diff_mean,
        AVG(mpv.next_days_diff)    AS next_days_diff_mean
    FROM publ.mileage_primitive_view mpv
    INNER JOIN base_vehicles bv 
        ON mpv.vehicle_id = bv.vehicle_id 
        AND mpv.collaborator_id = bv.current_collaborator_id
    GROUP BY mpv.vehicle_id
),

-- Expense features - normalized by number of active months to remove duration bias
expense_stats AS (
    SELECT
        epv.vehicle_id,
        COUNT(DISTINCT epv.month_start)                                                        AS expense_month_start_nunique,
        COALESCE(SUM(epv.amount_tax_exc) / NULLIF(COUNT(DISTINCT epv.month_start), 0), 0)     AS expense_amount_tax_exc_per_month,
        COALESCE(AVG(epv.amount_tax_exc), 0)                                                   AS expense_amount_tax_exc_mean,
        COALESCE(STDDEV(epv.amount_tax_exc), 0)                                                AS expense_amount_tax_exc_std,
        COALESCE(SUM(epv.net_amount) / NULLIF(COUNT(DISTINCT epv.month_start), 0), 0)         AS expense_net_amount_per_month,
        COALESCE(SUM(epv.quantity) / NULLIF(COUNT(DISTINCT epv.month_start), 0), 0)           AS expense_quantity_per_month,
        COALESCE(SUM(epv.co2_usage_scope_1) / NULLIF(COUNT(DISTINCT epv.month_start), 0), 0) AS expense_co2_scope_1_per_month,
        COALESCE(SUM(epv.co2_usage_scope_2) / NULLIF(COUNT(DISTINCT epv.month_start), 0), 0) AS expense_co2_scope_2_per_month,
        COALESCE(SUM(epv.co2_usage_scope_3) / NULLIF(COUNT(DISTINCT epv.month_start), 0), 0) AS expense_co2_scope_3_per_month
    FROM publ.expense_primitive_view epv
    INNER JOIN base_vehicles bv 
        ON epv.vehicle_id = bv.vehicle_id 
        AND epv.collaborator_id = bv.current_collaborator_id
    GROUP BY epv.vehicle_id
),

-- Fuel-specific features - normalized by active months
fuel_expenses AS (
    SELECT
        ex.vehicle_id,
        COUNT(DISTINCT DATE_TRUNC('month', ex.billing_date))                                              AS fuel_active_months,
        -- per-month normalization instead of raw sums
        COALESCE(SUM(ex.amount_tax_exc) / NULLIF(COUNT(DISTINCT DATE_TRUNC('month', ex.billing_date)), 0), 0) AS fuel_amount_tax_exc_per_month,
        COALESCE(AVG(ex.amount_tax_exc), 0)                                                               AS fuel_amount_tax_exc_mean,
        COUNT(*)                                                                                           AS fuel_amount_tax_exc_count,
        COALESCE(SUM(ex.quantity) / NULLIF(COUNT(DISTINCT DATE_TRUNC('month', ex.billing_date)), 0), 0)  AS fuel_quantity_per_month
    FROM publ.expenses ex
    INNER JOIN base_vehicles bv 
        ON ex.vehicle_id = bv.vehicle_id 
        AND ex.collaborator_id = bv.current_collaborator_id
    WHERE ex.soongo_category = ANY(publ.fuel_categories())
    GROUP BY ex.vehicle_id
),

-- Fuel refill timing features
fuel_with_dates AS (
    SELECT
        ex.vehicle_id,
        ex.billing_date,
        LAG(ex.billing_date) OVER (PARTITION BY ex.vehicle_id ORDER BY ex.billing_date) AS prev_billing_date
    FROM publ.expenses ex
    INNER JOIN base_vehicles bv 
        ON ex.vehicle_id = bv.vehicle_id 
        AND ex.collaborator_id = bv.current_collaborator_id
    WHERE ex.soongo_category = ANY(publ.fuel_categories())
      AND ex.billing_date IS NOT NULL
),

fuel_timing AS (
    SELECT
        vehicle_id,
        COUNT(*) AS fuel_refill_count,
        AVG(EXTRACT(EPOCH FROM (billing_date::timestamp - prev_billing_date::timestamp)) / 86400.0) AS fuel_days_between_mean,
        MIN(EXTRACT(EPOCH FROM (billing_date::timestamp - prev_billing_date::timestamp)) / 86400.0) AS fuel_days_between_min,
        AVG(CASE 
            WHEN EXTRACT(EPOCH FROM (billing_date::timestamp - prev_billing_date::timestamp)) / 86400.0 <= 3 
            THEN 1.0 ELSE 0.0 
        END) AS fuel_refill_close_ratio
    FROM fuel_with_dates
    WHERE prev_billing_date IS NOT NULL
    GROUP BY vehicle_id
),

-- Toll features - normalized by active months
toll_expenses AS (
    SELECT
        ex.vehicle_id,
        COUNT(DISTINCT DATE_TRUNC('month', ex.billing_date))                                              AS toll_active_months,
        -- per-month normalization instead of raw sum
        COALESCE(SUM(ex.amount_tax_exc) / NULLIF(COUNT(DISTINCT DATE_TRUNC('month', ex.billing_date)), 0), 0) AS toll_amount_per_month,
        COALESCE(MAX(ex.amount_tax_exc), 0)                                                               AS toll_max_amount,
        COALESCE(AVG(ex.amount_tax_exc), 0)                                                               AS toll_mean_amount,
        COUNT(*)                                                                                           AS toll_count
    FROM publ.expenses ex
    INNER JOIN base_vehicles bv 
        ON ex.vehicle_id = bv.vehicle_id 
        AND ex.collaborator_id = bv.current_collaborator_id
    WHERE LOWER(ex.product) LIKE '%peage%'
       OR LOWER(ex.product) LIKE '%péage%'
       OR LOWER(ex.product) LIKE '%toll%'
       OR LOWER(ex.product) LIKE '%autoroute%'
    GROUP BY ex.vehicle_id
)

-- Final feature assembly - NO TARGET VARIABLE (prediction query)
SELECT
    bv.vehicle_id,

    -- Vehicle age as category with UNKNOWN bucket
    bv.vehicle_age_category,

    -- Lease duration as category with UNKNOWN bucket
    bv.lease_duration_category,

    -- Remaining numeric vehicle features
    COALESCE(bv.fiscal_power_num, 0) AS fiscal_power_num,
    COALESCE(bv.motor_power_num, 0)  AS motor_power_num,

    -- Mileage features
    -- COALESCE to 0 (not mean) for all mileage features
    COALESCE(ms.mileage_driven_mean, 0)       AS mileage_driven_mean,
    COALESCE(ms.mileage_driven_std, 0)        AS mileage_driven_std,
    COALESCE(ms.mileage_driven_max, 0)        AS mileage_driven_max,
    COALESCE(ms.mileage_driven_min, 0)        AS mileage_driven_min,
    -- replaced raw sum with per-month normalized value
    COALESCE(ms.mileage_driven_per_month, 0)  AS mileage_driven_per_month,
    -- 0 instead of mean
    COALESCE(ms.mileage_month_count, 0)       AS mileage_month_count,
    COALESCE(ms.first_days_diff_mean, 0)      AS first_days_diff_mean,
    COALESCE(ms.next_days_diff_mean, 0)       AS next_days_diff_mean,
    COALESCE(ms.mileage_driven_std / NULLIF(ms.mileage_driven_mean + 1, 0), 0) AS mileage_variability,
    COALESCE((ms.first_days_diff_mean + ms.next_days_diff_mean) / 2.0, 0)      AS avg_days_between_readings,

    -- Expense features
    -- 0 instead of mean; using per-month normalized values
    COALESCE(es.expense_amount_tax_exc_per_month, 0) AS expense_amount_tax_exc_per_month,
    COALESCE(es.expense_amount_tax_exc_mean, 0)      AS expense_amount_tax_exc_mean,
    COALESCE(es.expense_amount_tax_exc_std, 0)       AS expense_amount_tax_exc_std,
    COALESCE(es.expense_net_amount_per_month, 0)     AS expense_net_amount_per_month,
    COALESCE(es.expense_quantity_per_month, 0)       AS expense_quantity_per_month,
    COALESCE(es.expense_co2_scope_1_per_month, 0)    AS expense_co2_scope_1_per_month,
    COALESCE(es.expense_co2_scope_2_per_month, 0)    AS expense_co2_scope_2_per_month,
    COALESCE(es.expense_co2_scope_3_per_month, 0)    AS expense_co2_scope_3_per_month,

    -- Fuel features (0 if missing)
    -- per-month normalized instead of raw sums
    COALESCE(fe.fuel_amount_tax_exc_per_month, 0) AS fuel_amount_tax_exc_per_month,
    COALESCE(fe.fuel_amount_tax_exc_mean, 0)      AS fuel_amount_tax_exc_mean,
    COALESCE(fe.fuel_amount_tax_exc_count, 0)     AS fuel_amount_tax_exc_count,
    COALESCE(fe.fuel_quantity_per_month, 0)       AS fuel_quantity_per_month,
    COALESCE(ft.fuel_refill_count, 0)             AS fuel_refill_count,
    COALESCE(ft.fuel_days_between_mean, 0)        AS fuel_days_between_mean,
    COALESCE(ft.fuel_days_between_min, 0)         AS fuel_days_between_min,
    COALESCE(ft.fuel_refill_close_ratio, 0)       AS fuel_refill_close_ratio,

    -- Toll features (0 if missing)
    -- per-month normalized instead of raw sum
    COALESCE(te.toll_amount_per_month, 0) AS toll_amount_per_month,
    COALESCE(te.toll_max_amount, 0)       AS toll_max_amount,
    COALESCE(te.toll_mean_amount, 0)      AS toll_mean_amount,
    COALESCE(te.toll_count, 0)            AS toll_count,

    -- Categorical features
    -- energy_type removed (data leakage)
    bv.assignment_type,
    bv.fiscal_type,
    bv.is_active

FROM base_vehicles bv
LEFT JOIN mileage_stats ms ON bv.vehicle_id = ms.vehicle_id
LEFT JOIN expense_stats es ON bv.vehicle_id = es.vehicle_id
LEFT JOIN fuel_expenses fe ON bv.vehicle_id = fe.vehicle_id
LEFT JOIN fuel_timing ft   ON bv.vehicle_id = ft.vehicle_id
LEFT JOIN toll_expenses te ON bv.vehicle_id = te.vehicle_id
ORDER BY bv.vehicle_id;
"""