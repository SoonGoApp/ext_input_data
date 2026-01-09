INSERT INTO db.trips (vehicle_id, geometry, start_at, end_at)
SELECT
    vehicle_id,
    geom::geometry AS geometry,
    start_at,
    end_at
FROM inserts;

SELECT t.*
FROM db.trips AS t
INNER JOIN inserts AS tu ON t.vehicle_id = tu.vehicle_id AND t.start_at = tu.start_at;
