
REF_VEHICLES = """
WITH masternaut_vehicles AS (
    SELECT m.vehicle_id
    FROM publ.mileages m
    INNER JOIN common.synchronisations s
        ON s.id = m.synchronisation_id
    WHERE s.connector_id = (
        SELECT id
        FROM common.connectors
        WHERE name = 'MASTERNAUT'
    )
    GROUP BY m.vehicle_id
    HAVING COUNT(*) > 300
)
SELECT
    v.*,
    cv.collaborator_id AS current_collaborator_id
FROM publ.vehicles v
INNER JOIN masternaut_vehicles mv
    ON mv.vehicle_id = v.id
LEFT JOIN publ.collaborators_vehicles cv
    ON cv.vehicle_id = v.id
   AND (
        cv.date_to IS NULL
        OR cv.date_to > CURRENT_DATE
   )
WHERE v.fiscal_type = 'PERSONAL_CAR'
  AND v.assignment_type = 'COMPANY_CAR'
  AND v.organization_id = (
      SELECT id
      FROM common.organizations
      WHERE slug = 'acorus'
  )
  AND cv.collaborator_id IS NOT NULL;
"""

# VEHICLES_CURRENT_COLLABORATOR = """
# CREATE OR REPLACE VIEW publ.vehicles_with_current_collaborator AS
# WITH masternaut_vehicles AS (
#     SELECT m.vehicle_id
#     FROM publ.mileages m
#     INNER JOIN common.synchronisations s
#         ON s.id = m.synchronisation_id
#     WHERE s.connector_id = (
#         SELECT id
#         FROM common.connectors
#         WHERE name = 'MASTERNAUT'
#     )
#     GROUP BY m.vehicle_id
#     HAVING COUNT(*) > 300
# )
# SELECT
#     v.id AS vehicle_id,
#     cv.collaborator_id AS current_collaborator_id
# FROM publ.vehicles v
# INNER JOIN masternaut_vehicles mv
#     ON mv.vehicle_id = v.id
# INNER JOIN publ.collaborators_vehicles cv
#     ON cv.vehicle_id = v.id
#    AND (
#         cv.date_to IS NULL
#         OR cv.date_to > CURRENT_DATE
#    )
# WHERE v.fiscal_type = 'PERSONAL_CAR'
#   AND v.assignment_type = 'COMPANY_CAR'
#   AND v.organization_id = (
#       SELECT id
#       FROM common.organizations
#       WHERE slug = 'acorus'
#   );
# """

VEHICLES_CURRENT_COLLABORATOR = """
CREATE OR REPLACE VIEW publ.vehicles_with_current_collaborator AS
WITH masternaut_vehicles AS (
    SELECT m.vehicle_id
    FROM publ.mileages m
    INNER JOIN common.synchronisations s
        ON s.id = m.synchronisation_id
    WHERE s.connector_id = (
        SELECT id
        FROM common.connectors
        WHERE name = 'MASTERNAUT'
    )
    GROUP BY m.vehicle_id
    HAVING COUNT(*) > 300
),
ranked_collaborators AS (
    SELECT
        cv.vehicle_id,
        cv.collaborator_id,
        ROW_NUMBER() OVER (
            PARTITION BY cv.vehicle_id
            ORDER BY
                CASE
                    WHEN cv.date_to IS NULL OR cv.date_to > CURRENT_DATE THEN 0
                    ELSE 1
                END,
                cv.date_to DESC NULLS LAST
        ) AS rn
    FROM publ.collaborators_vehicles cv
)
SELECT
    v.id AS vehicle_id,
    rc.collaborator_id AS current_collaborator_id
FROM publ.vehicles v
INNER JOIN masternaut_vehicles mv
    ON mv.vehicle_id = v.id
INNER JOIN ranked_collaborators rc
    ON rc.vehicle_id = v.id
   AND rc.rn = 1
WHERE v.fiscal_type = 'PERSONAL_CAR'
  AND v.assignment_type = 'COMPANY_CAR'
  AND v.organization_id = (
      SELECT id
      FROM common.organizations
      WHERE slug = 'acorus'
  );
"""

MILEAGE_PRIMITIVE_VIEW = """
    SELECT mpv.*
    FROM publ.mileage_primitive_view mpv
    INNER JOIN publ.vehicles_with_current_collaborator vcc
    ON mpv.vehicle_id = vcc.vehicle_id
    AND mpv.collaborator_id = vcc.current_collaborator_id;
"""

MILEAGES = """
    SELECT m.*
    FROM publ.mileages m
    INNER JOIN publ.vehicles_with_current_collaborator vcc
    ON m.vehicle_id = vcc.vehicle_id;
"""

EXPENSES = """
    SELECT ex.*
    FROM publ.expenses ex
    INNER JOIN publ.vehicles_with_current_collaborator vcc
    ON ex.vehicle_id = vcc.vehicle_id
    AND ex.collaborator_id = vcc.current_collaborator_id;
"""

EXPENSE_PRIMITIVE_VIEW = """
    SELECT exp.*
    FROM publ.expense_primitive_view exp
    INNER JOIN publ.vehicles_with_current_collaborator vcc
    ON exp.vehicle_id = vcc.vehicle_id
    AND exp.collaborator_id = vcc.current_collaborator_id;
"""

VEHICLES = """
    SELECT v.*
    FROM publ.vehicles v
    INNER JOIN publ.vehicles_with_current_collaborator vcc
    ON v.id = vcc.vehicle_id;
"""

queries = {
    'vehicles_current_collaborator': VEHICLES_CURRENT_COLLABORATOR,
    'mileage_primitive_view': MILEAGE_PRIMITIVE_VIEW,
    'mileages': MILEAGES,
    'expenses': EXPENSES,
    'expense_primitive_view': EXPENSE_PRIMITIVE_VIEW,
    'vehicles': VEHICLES,
}