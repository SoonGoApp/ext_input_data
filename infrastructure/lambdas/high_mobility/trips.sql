/**
 * GPS Trip Aggregation and Upsert Logic
 *
 * This DuckDB SQL query processes raw GPS point data from vehicles to create and maintain
 * trip records by grouping consecutive points into trips.
 *
 * Purpose:
 * - Aggregates GPS points into logical trips for each vehicle
 * - Updates existing trips when new points extend them
 * - Creates new trips when there are significant time or distance gaps
 *
 * Key Logic:
 * 1. Trip Continuation Rules:
 *    - Points within 10 minutes of the previous point continue the same trip
 *    - Points more than 15 meters apart are considered distinct (noise filtering)
 *
 * 2. Trip Break Rules:
 *    - Time gap > 10 minutes starts a new trip
 *    - Distance > 15 meters between consecutive points (duplicate/noise removal)
 *
 * Processing Pipeline:
 * 1. last_trips: Retrieves the most recent trip for each vehicle from the database
 * 2. clean_points: Filters and deduplicates GPS points:
 *    - Removes points occurring before or at the last trip's end time
 *    - Includes last trip endpoints for continuity checking
 *    - Filters out points < 15 meters from previous point (noise reduction)
 * 3. trips: Clusters points into trip segments:
 *    - Identifies trip breaks based on 10-minute gaps
 *    - Assigns sequential trip IDs to point clusters
 *    - Aggregates points into LINESTRING geometries with start/end timestamps
 *    - Links new trips to existing trips when extending them
 * 4. updates: Extends existing trips by merging new points with last trip geometry
 * 5. inserts: Creates new trip records for point clusters not extending existing trips
 */

 -- Retrieve the most recent trip for each vehicle
create or replace table last_trips as (
    select distinct on (vehicle_id)
        vehicle_id,
        id as trip_id,
        start_at,
        end_at,
        geometry as geom
    from db.trips
    order by vehicle_id asc, end_at desc
);

create or replace table clean_points as (
    -- discard points where timestamp is before or equal to last trip end (todo: handle points in past?)
    with valid_points as (
        select
            p.*,
            t.trip_id
        from points as p
        left join last_trips as t on p.vehicle_id = t.vehicle_id
        where coalesce(t.end_at, '-infinity') < p.ts
    ),

    -- concat points from current batch and last trips end points 
    all_points as (
        select
            null as trip_id,
            p.geom,
            p.vehicle_id,
            p.ts
        from valid_points as p
        union
        select
            t.trip_id,
            case
                when st_geometrytype(t.geom::geometry) = 'LINESTRING'
                    then st_endpoint(t.geom::geometry)
                else t.geom::geometry
            end as geom,
            t.vehicle_id,
            t.end_at as ts
        from last_trips as t
        inner join (select distinct trip_id from valid_points) as p on t.trip_id = p.trip_id
    )

    -- remove points too close to previous point (< 15 meters) regardless of time gap
    select * from (
        select
            p.*,
            lag(p.geom::geometry) over (partition by p.vehicle_id order by p.ts) as prev_geom
        from all_points as p
    ) as t
    where
        t.prev_geom is null -- first point in vehicle time series
        or st_distance_sphere(t.geom::geometry, t.prev_geom) > 15 -- in meters
);

-- create new trip when time gap > 10 minutes
create or replace table trips as (
    with is_new_trip as (
        select
            *,
            ts > (lag(ts) over (partition by vehicle_id order by ts) + interval '10 minutes') as is_new_trip
        from clean_points
    ),

    trip_starts as (
        select
            vehicle_id,
            geom,
            ts,
            trip_id,
            case
                when is_new_trip then 1
                else 0
            end as trip_flag,
            -- only keep prev_geom where new trip starts or first vehicle trip
            case
                when is_new_trip then prev_geom
            end as prev_geom
        from is_new_trip
    ),

    trip_points as (
        select
            vehicle_id,
            geom,
            ts,
            trip_id,
            prev_geom,
            sum(trip_flag) over (partition by vehicle_id order by ts rows unbounded preceding) as new_trip_id
        from trip_starts
    )

    select
        vehicle_id,
        new_trip_id,
        max(trip_id) as existing_trip_id, -- not null only if an existing trip end point is included in current trip
        min(ts) as start_at,
        max(ts) as end_at,
        case
            when max(prev_geom::geometry) is null
                then -- first vehicle trip  
                    case
                        when array_length(array_agg(geom::geometry)) > 1
                            then --  with several points
                                st_makeline(array_agg(geom::geometry order by ts))
                        when max(trip_id) is not null -- with only an existing trip end point 
                            then null
                        else  -- with a single point and no existing trip
                            array_agg(geom::geometry)[1]
                    end
            else -- subsequent trips
                st_makeline(array[max(prev_geom::geometry)] || array_agg(geom::geometry order by ts))
        end as geom
    from trip_points
    group by vehicle_id, new_trip_id
    having geom is not null -- remove first vehicle trip with only an existing trip end point
);

create or replace table updates as (
    select
        lt.trip_id,
        st_linemerge(st_collect(array[lt.geom::geometry, t.geom::geometry])) as geom,
        t.end_at
    from trips as t
    inner join last_trips as lt on t.existing_trip_id = lt.trip_id
);

create or replace table inserts as (
    select
        t.vehicle_id,
        t.geom,
        t.start_at,
        t.end_at
    from trips as t
    where t.existing_trip_id is null
);
