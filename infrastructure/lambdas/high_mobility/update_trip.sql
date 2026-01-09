UPDATE db.trips t
SET
    end_at = u.end_at,
    geometry = st_astext(u.geom)
FROM updates AS u
WHERE
    u.trip_id = t.id;

SELECT
    t.id,
    t.start_at,
    t.end_at
FROM updates AS u
INNER JOIN db.trips AS t ON u.trip_id = t.id;
