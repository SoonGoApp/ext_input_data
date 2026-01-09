UPDATE publ.trips t
SET
    start_location = address,
    end_location = address
FROM publ.trips AS t2
INNER JOIN LATERAL (
    SELECT CONCAT_WS(' ', a.number, a.street, a.postal_code, a.city)
    FROM publ.ban_addresses AS a
    ORDER BY
        CASE ST_GEOMETRYTYPE(t2.geometry::geometry)
            WHEN 'ST_LineString'
                THEN ST_ENDPOINT(t2.geometry::geometry) <-> a.geom
            ELSE
                t2.geometry <-> a.geom
        END
    LIMIT 1
) AS e ON true
INNER JOIN LATERAL (
    SELECT CONCAT_WS(' ', a.number, a.street, a.postal_code, a.city)
    FROM publ.ban_addresses a
    ORDER BY
        CASE ST_GEOMETRYTYPE(t2.geometry::geometry)
            WHEN 'ST_LineString'
                THEN ST_STARTPOINT(t2.geometry::geometry) <-> a.geom
            ELSE
                t2.geometry <-> a.geom
        END
    LIMIT 1
) AS s ON true
WHERE t2.id IN :trip_ids
    AND t2.id = t.id;

SELECT ST_GEOMETRYTYPE(t2.geometry::geometry) AS t, ST_SATEXT(t2.geometry::geometry) FROM publ.trips t2;
