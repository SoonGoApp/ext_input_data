
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
                cv.date_to DESC NULLS LAST
        ) AS rn
    FROM publ.collaborators_vehicles cv
),

base_vehicles AS (
    SELECT
        v.id AS vehicle_id,
        rc.collaborator_id AS current_collaborator_id,
        -- Vehicle features
        EXTRACT(YEAR FROM AGE(CURRENT_DATE, v.entry_into_fleet_date::timestamp)) AS vehicle_age_years,
        (EXTRACT(EPOCH FROM (v.lease_end_date::timestamp - v.lease_start_date::timestamp)) / 86400.0) / 30.44 AS lease_duration_months,
        CAST(v.theoretical_fuel_consumption AS NUMERIC) AS fuel_consumption,
        CAST(v.co2_per_km AS NUMERIC) AS co2_emissions,
        CAST(v.fiscal_power AS NUMERIC) AS fiscal_power_num,
        CAST(v.motor_power AS NUMERIC) AS motor_power_num,
        CAST(v.seat_count AS NUMERIC) AS seat_count_num,
        COALESCE(v.energy, 'UNKNOWN') AS energy_type,
        COALESCE(v.assignment_type, 'UNKNOWN') AS assignment_type,
        COALESCE(v.fiscal_type, 'UNKNOWN') AS fiscal_type,
        CASE WHEN v.vehicle_status = 'ACTIVE' THEN 1 ELSE 0 END AS is_active
    FROM publ.vehicles v
    INNER JOIN ranked_collaborators rc ON rc.vehicle_id = v.id AND rc.rn = 1
    WHERE v.fiscal_type = 'PERSONAL_CAR'
      AND v.assignment_type = 'COMPANY_CAR'
),

-- Mileage features
mileage_stats AS (
    SELECT
        mpv.vehicle_id,
        AVG(mpv.mileage_driven) AS mileage_driven_mean,
        STDDEV(mpv.mileage_driven) AS mileage_driven_std,
        MAX(mpv.mileage_driven) AS mileage_driven_max,
        MIN(mpv.mileage_driven) AS mileage_driven_min,
        SUM(mpv.mileage_driven) AS mileage_driven_sum,
        COUNT(mpv.mileage_month) AS mileage_month_count,
        AVG(mpv.first_days_diff) AS first_days_diff_mean,
        AVG(mpv.next_days_diff) AS next_days_diff_mean
    FROM publ.mileage_primitive_view mpv
    INNER JOIN base_vehicles bv 
        ON mpv.vehicle_id = bv.vehicle_id 
        AND mpv.collaborator_id = bv.current_collaborator_id
    GROUP BY mpv.vehicle_id
),

-- Expense features - global
expense_stats AS (
    SELECT
        epv.vehicle_id,
        SUM(epv.amount_tax_exc) AS expense_amount_tax_exc_sum,
        AVG(epv.amount_tax_exc) AS expense_amount_tax_exc_mean,
        STDDEV(epv.amount_tax_exc) AS expense_amount_tax_exc_std,
        SUM(epv.net_amount) AS expense_net_amount_sum,
        AVG(epv.net_amount) AS expense_net_amount_mean,
        SUM(epv.quantity) AS expense_quantity_sum,
        SUM(epv.co2_usage_scope_1) AS expense_co2_usage_scope_1_sum,
        SUM(epv.co2_usage_scope_2) AS expense_co2_usage_scope_2_sum,
        SUM(epv.co2_usage_scope_3) AS expense_co2_usage_scope_3_sum,
        COUNT(DISTINCT epv.month_start) AS expense_month_start_nunique
    FROM publ.expense_primitive_view epv
    INNER JOIN base_vehicles bv 
        ON epv.vehicle_id = bv.vehicle_id 
        AND epv.collaborator_id = bv.current_collaborator_id
    GROUP BY epv.vehicle_id
),

-- Fuel-specific features
fuel_expenses AS (
    SELECT
        ex.vehicle_id,
        SUM(ex.amount_tax_exc) AS fuel_amount_tax_exc_sum,
        AVG(ex.amount_tax_exc) AS fuel_amount_tax_exc_mean,
        COUNT(*) AS fuel_amount_tax_exc_count,
        SUM(ex.quantity) AS fuel_quantity_sum
    FROM publ.expenses ex
    INNER JOIN base_vehicles bv 
        ON ex.vehicle_id = bv.vehicle_id 
        AND ex.collaborator_id = bv.current_collaborator_id
    WHERE LOWER(ex.soongo_category) LIKE '%fuel%' 
       OR LOWER(ex.soongo_category) LIKE '%carburant%'
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
    WHERE (LOWER(ex.soongo_category) LIKE '%fuel%' 
        OR LOWER(ex.soongo_category) LIKE '%carburant%')
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

-- Toll features
toll_expenses AS (
    SELECT
        ex.vehicle_id,
        SUM(ex.amount_tax_exc) AS toll_total_amount,
        MAX(ex.amount_tax_exc) AS toll_max_amount,
        AVG(ex.amount_tax_exc) AS toll_mean_amount,
        COUNT(*) AS toll_count
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

-- Final feature assembly - ONLY SELECTED FEATURES (NO TARGET VARIABLE for prediction)
SELECT
    bv.vehicle_id,
    
    -- Numeric features (from select_features function)
    bv.vehicle_age_years,
    bv.lease_duration_months,
    bv.fiscal_power_num,
    bv.motor_power_num,
    
    -- Global expense behavior
    COALESCE(es.expense_amount_tax_exc_sum, 0) AS expense_amount_tax_exc_sum,
    COALESCE(es.expense_amount_tax_exc_mean, 0) AS expense_amount_tax_exc_mean,
    COALESCE(es.expense_amount_tax_exc_std, 0) AS expense_amount_tax_exc_std,
    COALESCE(es.expense_amount_tax_exc_sum / NULLIF(es.expense_month_start_nunique + 1, 0), 0) AS monthly_expense_avg,
    
    -- Fuel behavior
    COALESCE(fe.fuel_amount_tax_exc_sum, 0) AS fuel_amount_tax_exc_sum,
    COALESCE(fe.fuel_amount_tax_exc_mean, 0) AS fuel_amount_tax_exc_mean,
    COALESCE(fe.fuel_amount_tax_exc_count, 0) AS fuel_amount_tax_exc_count,
    COALESCE(fe.fuel_quantity_sum, 0) AS fuel_quantity_sum,
    COALESCE(ft.fuel_refill_count, 0) AS fuel_refill_count,
    COALESCE(ft.fuel_days_between_mean, 0) AS fuel_days_between_mean,
    COALESCE(ft.fuel_days_between_min, 0) AS fuel_days_between_min,
    COALESCE(ft.fuel_refill_close_ratio, 0) AS fuel_refill_close_ratio,
    
    -- Toll behavior
    COALESCE(te.toll_total_amount, 0) AS toll_total_amount,
    COALESCE(te.toll_max_amount, 0) AS toll_max_amount,
    COALESCE(te.toll_mean_amount, 0) AS toll_mean_amount,
    COALESCE(te.toll_count, 0) AS toll_count,
    
    -- Categorical features
    bv.energy_type,
    bv.assignment_type,
    bv.fiscal_type,
    bv.is_active

FROM base_vehicles bv
LEFT JOIN expense_stats es ON bv.vehicle_id = es.vehicle_id
LEFT JOIN fuel_expenses fe ON bv.vehicle_id = fe.vehicle_id
LEFT JOIN fuel_timing ft ON bv.vehicle_id = ft.vehicle_id
LEFT JOIN toll_expenses te ON bv.vehicle_id = te.vehicle_id
ORDER BY bv.vehicle_id;
"""